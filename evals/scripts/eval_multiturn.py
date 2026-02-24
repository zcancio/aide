#!/usr/bin/env python3
"""
Multi-turn eval runner.

Runs conversational scenarios where state builds across turns.
Each turn's output becomes the next turn's snapshot context.

Usage:
  # Run all multi-turn scenarios
  python eval_multiturn.py

  # Run specific scenario
  python eval_multiturn.py --scenario graduation_realistic

  # Verbose: show full output per turn
  python eval_multiturn.py -v

  # Save run artifacts for review
  python eval_multiturn.py --save

Environment:
  ANTHROPIC_API_KEY  — required
  AIDE_EVAL_DIR      — output dir (default: ./eval_output)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path

import anthropic

from scoring import score_scenario, ScenarioScore, parse_jsonl, DIMENSION_WEIGHTS
from scenarios_multiturn import MULTI_TURN_SCENARIOS, get_scenario

# ---------------------------------------------------------------------------
# Prompt loading (same as eval_v3.py)
# ---------------------------------------------------------------------------

PROMPTS_DIR = Path(__file__).parent
if (Path(__file__).parent / "prompts").exists():
    PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text()


def build_system_blocks(tier: str, snapshot: dict | None) -> list[dict]:
    prefix = load_prompt("shared_prefix").replace(
        "{{current_date}}", date.today().strftime("%A, %B %d, %Y")  # e.g. "Tuesday, February 24, 2026"
    )
    tier_text = load_prompt({"L2": "l2_tier", "L3": "l3_tier", "L4": "l4_tier"}[tier])
    blocks = [
        {
            "type": "text",
            "text": prefix,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": tier_text,
            "cache_control": {"type": "ephemeral"},
        },
    ]
    if snapshot is not None:
        blocks.append({
            "type": "text",
            "text": f"## Current Snapshot\n```json\n{json.dumps(snapshot, indent=2)}\n```",
        })
    return blocks


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

DEFAULT_MODELS = {
    "L2": "claude-haiku-4-5-20251001",
    "L3": "claude-sonnet-4-5-20250929",
    "L4": "claude-sonnet-4-5-20250929",
}

# ---------------------------------------------------------------------------
# Snapshot builder — applies JSONL output to build next turn's state
# ---------------------------------------------------------------------------

def apply_output_to_snapshot(snapshot: dict, output_text: str, tier: str) -> dict:
    """
    Apply LLM output to snapshot to build state for next turn.

    For L2/L3: parse JSONL and apply entity mutations.
    For L4: no state change (read-only).

    This is a simplified reducer — it doesn't validate schemas or enforce
    all reducer rules. It just builds enough state for the next prompt
    to have realistic context.

    IMPORTANT: Deep copies the snapshot first so mutations don't bleed
    back into previously stored snapshots (Python dict aliasing).
    """
    if tier == "L4":
        return json.loads(json.dumps(snapshot))  # L4 doesn't mutate but still isolate

    parsed, _ = parse_jsonl(output_text)

    # Deep copy to break all references to the original snapshot's inner dicts
    working = json.loads(json.dumps(snapshot))
    entities = working.get("entities", {})
    meta = working.get("meta", {})
    relationships = working.get("relationships", [])
    rel_types = working.get("relationship_types", {})  # type → cardinality

    for event in parsed:
        t = event.get("t", "")

        if t == "meta.set" or t == "meta.update":
            p = event.get("p", {})
            meta.update(p)

        elif t == "entity.create":
            eid = event.get("id")
            if eid:
                entities[eid] = {
                    "id": eid,
                    "parent": event.get("parent", "root"),
                    "display": event.get("display", "row"),
                    "props": event.get("p", {}),
                }

        elif t == "entity.update":
            ref = event.get("ref")
            if ref and ref in entities:
                entities[ref]["props"].update(event.get("p", {}))

        elif t == "entity.remove":
            ref = event.get("ref")
            if ref and ref in entities:
                del entities[ref]

        elif t == "entity.move":
            ref = event.get("ref")
            if ref and ref in entities:
                if "parent" in event:
                    entities[ref]["parent"] = event["parent"]

        elif t == "rel.set":
            frm = event.get("from", "")
            to = event.get("to", "")
            rtype = event.get("type", "")
            card = event.get("cardinality", "many_to_one")

            # Register type cardinality on first use
            if rtype and rtype not in rel_types:
                rel_types[rtype] = card

            # Enforce cardinality
            stored_card = rel_types.get(rtype, card)
            if stored_card == "many_to_one":
                # Source can link to ONE target of this type — remove old
                relationships = [r for r in relationships
                                 if not (r["from"] == frm and r["type"] == rtype)]
            elif stored_card == "one_to_one":
                # Both sides exclusive — remove source's old AND target's old
                relationships = [r for r in relationships
                                 if not (r["from"] == frm and r["type"] == rtype)
                                 and not (r["to"] == to and r["type"] == rtype)]

            relationships.append({"from": frm, "to": to, "type": rtype})

        elif t == "rel.remove":
            frm = event.get("from", "")
            to = event.get("to", "")
            rtype = event.get("type", "")
            relationships = [r for r in relationships
                             if not (r["from"] == frm and r["to"] == to and r["type"] == rtype)]

        # Signals (voice, escalate, batch) — no state change

    return {"meta": meta, "entities": entities, "relationships": relationships, "relationship_types": rel_types}


# ---------------------------------------------------------------------------
# Conversation history for messages
# ---------------------------------------------------------------------------

def build_messages_with_history(
    history: list[dict],
    user_message: str,
    tail_size: int = 5,
) -> list[dict]:
    """Build messages array with conversation history."""
    messages = []
    for turn in history[-tail_size:]:
        messages.append({"role": "user", "content": turn["user_message"]})
        if turn.get("assistant_response"):
            messages.append({"role": "assistant", "content": turn["assistant_response"]})
    messages.append({"role": "user", "content": user_message})
    return messages


# ---------------------------------------------------------------------------
# Turn runner
# ---------------------------------------------------------------------------

def classify_tier(message: str, snapshot: dict | None) -> str:
    """
    Simple rule-based classifier (mirrors the server-side classifier).
    Returns expected tier based on message + snapshot.
    """
    msg_lower = message.lower().strip()

    # Questions → L4
    if msg_lower.endswith("?") or any(msg_lower.startswith(q) for q in
        ["how many", "who", "what's left", "what do we", "how much", "is there", "do we"]):
        return "L4"

    # No entities → L3
    if not snapshot or not snapshot.get("entities"):
        return "L3"

    # Structural keywords → L3
    structural = ["add a section", "add a new", "set up a", "create a", "track",
                   "we should do", "need a", "gonna be", "redoing"]
    if any(kw in msg_lower for kw in structural):
        return "L3"

    # Default → L2
    return "L2"


def run_turn(
    client: anthropic.Anthropic,
    message: str,
    tier: str,
    snapshot: dict | None,
    history: list[dict],
) -> dict:
    """Run a single turn and return results."""
    model = DEFAULT_MODELS[tier]
    system = build_system_blocks(tier, snapshot)
    messages = build_messages_with_history(history, message)

    start = time.time()
    first_token_time = None
    full_text = ""

    with client.messages.stream(
        model=model, max_tokens=4096, system=system, messages=messages,
    ) as stream:
        for chunk in stream.text_stream:
            if first_token_time is None:
                first_token_time = time.time()
            full_text += chunk

    end = time.time()
    usage = stream.get_final_message().usage

    # Strip code fences if model wraps output (common Sonnet behavior)
    raw_output = full_text
    clean_output = full_text.strip()
    if clean_output.startswith("```"):
        lines = clean_output.split("\n")
        # Remove opening fence (```jsonl, ```json, ```)
        lines = lines[1:]
        # Remove closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        clean_output = "\n".join(lines)

    return {
        "tier": tier,
        "model": model,
        "output": clean_output,
        "raw_output": raw_output,
        "had_fences": raw_output.strip() != clean_output.strip(),
        "ttfc_ms": int((first_token_time - start) * 1000) if first_token_time else -1,
        "ttc_ms": int((end - start) * 1000),
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_creation": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        "cache_read": getattr(usage, "cache_read_input_tokens", 0) or 0,
    }


# ---------------------------------------------------------------------------
# Scenario runner
# ---------------------------------------------------------------------------

def run_multiturn_scenario(
    client: anthropic.Anthropic,
    scenario: dict,
    verbose: bool = False,
    save_dir: Path | None = None,
) -> dict:
    """Run a complete multi-turn scenario, building state across turns."""
    name = scenario["name"]
    turns = scenario["turns"]

    print(f"\n{'='*70}")
    print(f"📖 {name}: {scenario['description']}")
    print(f"   {len(turns)} turns")
    print(f"{'='*70}")

    snapshot: dict = {"meta": {}, "entities": {}}
    history: list[dict] = []
    turn_results: list[dict] = []

    # ── Cache warming ──
    # Fire minimal requests to warm Anthropic's prompt cache for each tier.
    # The shared prefix + tier instructions are marked ephemeral (1h TTL).
    # Without this, turn 1 always pays the full cache-creation cost.
    warmed_tiers = set()
    for turn_spec in turns:
        tier = turn_spec["expected_tier"]
        warmed_tiers.add(tier)
    if warmed_tiers:
        print(f"  🔥 Warming cache for: {', '.join(sorted(warmed_tiers))}")
        for tier in sorted(warmed_tiers):
            try:
                warm_start = time.time()
                warm_system = build_system_blocks(tier, snapshot)
                # Minimal request — just enough for the API to cache the prefix
                client.messages.create(
                    model=DEFAULT_MODELS[tier],
                    max_tokens=1,
                    system=warm_system,
                    messages=[{"role": "user", "content": "ping"}],
                )
                warm_ms = int((time.time() - warm_start) * 1000)
                print(f"    {tier} warmed in {warm_ms}ms")
            except Exception as e:
                print(f"    {tier} warm failed: {e}")

    for i, turn_spec in enumerate(turns):
        message = turn_spec["message"]
        expected_tier = turn_spec["expected_tier"]
        accept_tiers = turn_spec.get("accept_tiers", [expected_tier])
        notes = turn_spec.get("notes", "")

        # Classify
        classified_tier = classify_tier(message, snapshot)

        # Override if classifier disagrees but expected tier is acceptable
        # (in production the LLM can self-escalate, so accept wider range)
        actual_tier = classified_tier if classified_tier in accept_tiers else expected_tier

        print(f"\n  Turn {i+1}/{len(turns)}: \"{message}\"")
        print(f"    expected={expected_tier}  classified={classified_tier}  actual={actual_tier}")

        try:
            # Capture state BEFORE this turn (for viewer)
            snapshot_before = json.loads(json.dumps(snapshot))
            system_prompt_text = "\n\n".join(
                b["text"] for b in build_system_blocks(
                    classified_tier if classified_tier in accept_tiers else expected_tier,
                    snapshot,
                )
            )

            result = run_turn(client, message, actual_tier, snapshot, history)

            # Check for escalation signals in L2 output
            # Production server: apply L2 mutations, then re-route to escalation tier
            escalation_result = None
            if actual_tier == "L2":
                parsed_events, _ = parse_jsonl(result["output"])
                escalation = next((e for e in parsed_events if e.get("t") == "escalate"), None)
                if escalation:
                    esc_tier = escalation.get("tier", "L3")
                    esc_extract = escalation.get("extract", message)
                    print(f"    ↗ L2 escalated to {esc_tier}: {escalation.get('reason','')}")

                    # Apply L2's mutations first (everything before the escalate)
                    pre_escalation_snapshot = apply_output_to_snapshot(
                        snapshot, result["output"], "L2"
                    )

                    # Run escalation tier with the extracted/original message
                    escalation_result = run_turn(
                        client, esc_extract, esc_tier, pre_escalation_snapshot, history
                    )

                    # Merge: L2's output + escalation output
                    result = {
                        **result,
                        "output": result["output"] + "\n" + escalation_result["output"],
                        "raw_output": result.get("raw_output", result["output"]) + "\n" + escalation_result.get("raw_output", escalation_result["output"]),
                        "had_fences": result.get("had_fences", False) or escalation_result.get("had_fences", False),
                        "output_tokens": result["output_tokens"] + escalation_result["output_tokens"],
                        "input_tokens": result["input_tokens"] + escalation_result["input_tokens"],
                        "ttc_ms": result["ttc_ms"] + escalation_result["ttc_ms"],
                        # TTFT is from the first call
                        "cache_creation": result["cache_creation"] + escalation_result.get("cache_creation", 0),
                        "cache_read": result["cache_read"] + escalation_result.get("cache_read", 0),
                        "escalated_to": esc_tier,
                    }

            # If escalated, use the escalated tier for scoring and snapshot
            # (the merged output has L3-style entity creates, not L2-only mutations)
            effective_tier = result.get("escalated_to", actual_tier)

            # Score this turn (use raw output so fence detection works)
            turn_score = score_scenario(
                name=f"{name}_t{i+1}",
                tier=effective_tier,
                model=result["model"],
                prompt_version="v3.1",
                output_text=result.get("raw_output", result["output"]),
                output_tokens=result["output_tokens"],
                latency_ms=result["ttc_ms"],
                snapshot=snapshot,
                user_message=message,
            )

            # Update snapshot from clean output (fences stripped)
            new_snapshot = apply_output_to_snapshot(snapshot, result["output"], effective_tier)
            entity_count = len(new_snapshot.get("entities", {}))
            entity_delta = entity_count - len(snapshot.get("entities", {}))

            # Track history — use natural language summaries, NOT bracket format
            # that the model will mimic in its own output
            if actual_tier == "L4":
                assistant_summary = result["output"][:200]
            else:
                # Summarize what changed in plain language
                parts = []
                parsed_events, _ = parse_jsonl(result["output"])
                creates = [e.get("id","") for e in parsed_events if e.get("t") == "entity.create"]
                updates = [e.get("ref","") for e in parsed_events if e.get("t") == "entity.update"]
                if creates:
                    parts.append(f"Created {', '.join(creates[:3])}" + (f" +{len(creates)-3} more" if len(creates) > 3 else ""))
                if updates:
                    parts.append(f"Updated {', '.join(updates[:3])}" + (f" +{len(updates)-3} more" if len(updates) > 3 else ""))
                voice_lines = [e.get("text","") for e in parsed_events if e.get("t") == "voice"]
                if voice_lines:
                    assistant_summary = voice_lines[-1]
                elif parts:
                    assistant_summary = ". ".join(parts) + "."
                else:
                    assistant_summary = "Applied changes."
            history.append({
                "user_message": message,
                "assistant_response": assistant_summary,
            })

            # Print turn result
            bar = "█" * int(turn_score.composite * 10) + "░" * (10 - int(turn_score.composite * 10))
            tier_match = "✓" if classified_tier in accept_tiers else "✗"
            print(f"    score=[{bar}] {turn_score.composite:.0%}  "
                  f"tier={tier_match}  "
                  f"{result['ttc_ms']}ms  "
                  f"{result['output_tokens']}tok  "
                  f"entities={entity_count} ({entity_delta:+d})")

            if verbose:
                preview = result["output"].strip().split("\n")[:5]
                for line in preview:
                    print(f"      {line[:90]}")
                if len(result["output"].strip().split("\n")) > 5:
                    print(f"      ... ({len(result['output'].strip().split(chr(10)))} lines)")
                if notes:
                    print(f"    📝 {notes[:100]}")

            # Save turn artifact
            if save_dir:
                turn_dir = save_dir / name / f"turn_{i+1:02d}"
                turn_dir.mkdir(parents=True, exist_ok=True)

                (turn_dir / "input.md").write_text(
                    f"# Turn {i+1}: {message}\n\n"
                    f"## Tier: {actual_tier} (expected: {expected_tier}, classified: {classified_tier})\n\n"
                    f"## Notes\n{notes}\n\n"
                    f"## Snapshot before this turn\n```json\n{json.dumps(snapshot, indent=2)}\n```\n\n"
                    f"## System prompt\n{chr(10).join(b['text'] for b in build_system_blocks(actual_tier, snapshot))}"
                )
                (turn_dir / "output.txt").write_text(result.get("raw_output", result["output"]))
                (turn_dir / "snapshot_after.json").write_text(json.dumps(new_snapshot, indent=2))
                (turn_dir / "score.json").write_text(json.dumps(turn_score.to_dict(), indent=2))
                (turn_dir / "usage.json").write_text(json.dumps({
                    "ttfc_ms": result["ttfc_ms"], "ttc_ms": result["ttc_ms"],
                    "input_tokens": result["input_tokens"], "output_tokens": result["output_tokens"],
                    "cache_creation": result["cache_creation"], "cache_read": result["cache_read"],
                }, indent=2))

            snapshot = new_snapshot

            turn_results.append({
                "turn": i + 1,
                "message": message,
                "tier": actual_tier,
                "expected_tier": expected_tier,
                "classified_tier": classified_tier,
                "tier_correct": classified_tier in accept_tiers,
                "notes": notes,
                # Full score breakdown
                "score": {
                    "composite": turn_score.composite,
                    "validity": turn_score.dimensions["validity"].score if "validity" in turn_score.dimensions else 0,
                    "voice": turn_score.dimensions["voice"].score if "voice" in turn_score.dimensions else 0,
                    "structure": turn_score.dimensions["structure"].score if "structure" in turn_score.dimensions else 0,
                    "efficiency": turn_score.dimensions["efficiency"].score if "efficiency" in turn_score.dimensions else 0,
                    "fidelity": turn_score.dimensions["fidelity"].score if "fidelity" in turn_score.dimensions else 0,
                },
                # Per-dimension checks and notes (for viewer explanations)
                "score_details": {
                    dim_name: {
                        "score": round(dim_score.score, 3),
                        "checks": {k: round(v, 3) for k, v in dim_score.checks.items()},
                        "notes": dim_score.notes,
                    }
                    for dim_name, dim_score in turn_score.dimensions.items()
                },
                # Usage
                "ttc_ms": result["ttc_ms"],
                "ttfc_ms": result["ttfc_ms"],
                "output_tokens": result["output_tokens"],
                "input_tokens": result["input_tokens"],
                "cache_creation": result["cache_creation"],
                "cache_read": result["cache_read"],
                # Content (viewer needs these inline)
                "output": result.get("raw_output", result["output"]),
                "had_fences": result.get("had_fences", False),
                "system_prompt": system_prompt_text,
                "snapshot_before": snapshot_before,
                "snapshot_after": json.loads(json.dumps(new_snapshot)),
                # Summary stats
                "entity_count": entity_count,
                "entity_delta": entity_delta,
                "escalated_to": result.get("escalated_to"),
            })

        except Exception as e:
            print(f"    ❌ ERROR: {e}")
            turn_results.append({
                "turn": i + 1, "message": message, "error": str(e),
            })

    # Scenario summary
    scores = [t["score"]["composite"] if isinstance(t.get("score"), dict) else t.get("score", 0) for t in turn_results if "score" in t]
    avg_score = sum(scores) / max(len(scores), 1)
    tier_accuracy = sum(1 for t in turn_results if t.get("tier_correct", False)) / max(len(turn_results), 1)
    total_tokens = sum(t.get("output_tokens", 0) for t in turn_results)
    total_time = sum(t.get("ttc_ms", 0) for t in turn_results)
    final_entities = turn_results[-1].get("entity_count", 0) if turn_results else 0

    print(f"\n  {'─'*50}")
    bar = "█" * int(avg_score * 20) + "░" * (20 - int(avg_score * 20))
    icon = "✅" if avg_score >= 0.8 else "⚠️" if avg_score >= 0.6 else "❌"
    print(f"  {icon} {name} [{bar}] {avg_score:.0%} avg")
    print(f"     turns: {len(turns)} | entities: {final_entities} | "
          f"tokens: {total_tokens} | time: {total_time}ms | "
          f"tier accuracy: {tier_accuracy:.0%}")

    return {
        "name": name,
        "avg_score": avg_score,
        "tier_accuracy": tier_accuracy,
        "total_tokens": total_tokens,
        "total_time_ms": total_time,
        "final_entity_count": final_entities,
        "turns": turn_results,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Multi-turn prompt eval")
    p.add_argument("--scenario", type=str, help="Run specific scenario")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--save", action="store_true", help="Save run artifacts")
    p.add_argument("--output-dir", default=os.environ.get("AIDE_EVAL_DIR", "./eval_output"))
    args = p.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set"); sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_dir = Path(args.output_dir) / f"multiturn_{ts}" if args.save else None
    if save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)
        print(f"Saving artifacts to: {save_dir}")

    # Pick scenarios
    if args.scenario:
        scenario = get_scenario(args.scenario)
        if not scenario:
            print(f"Unknown scenario: {args.scenario}")
            print(f"Available: {', '.join(s['name'] for s in MULTI_TURN_SCENARIOS)}")
            sys.exit(1)
        to_run = [scenario]
    else:
        to_run = MULTI_TURN_SCENARIOS

    print(f"AIde Multi-Turn Eval")
    print(f"Scenarios: {len(to_run)} | Started: {datetime.now().isoformat()}\n")

    # Run
    results = []
    for scenario in to_run:
        try:
            result = run_multiturn_scenario(client, scenario, verbose=args.verbose, save_dir=save_dir)
            results.append(result)
        except Exception as e:
            print(f"\n  FATAL ERROR in {scenario['name']}: {e}")

    # Final summary
    print(f"\n\n{'='*70}")
    print(f"MULTI-TURN SUMMARY")
    print(f"{'='*70}")
    print(f"{'Scenario':<26} {'Turns':>6} {'Score':>6} {'Tier%':>6} {'Tokens':>7} {'Time':>7} {'Entities':>9}")
    print(f"{'-'*70}")

    for r in results:
        print(f"{r['name']:<26} {len(r['turns']):>6} {r['avg_score']:>5.0%} "
              f"{r['tier_accuracy']:>5.0%} {r['total_tokens']:>7} "
              f"{r['total_time_ms']:>6}ms {r['final_entity_count']:>9}")

    avg = sum(r["avg_score"] for r in results) / max(len(results), 1)
    print(f"\nOverall average: {avg:.0%}")

    # Save report
    if save_dir:
        report_path = save_dir / "report.json"
        with open(report_path, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "results": results,
                "overall_average": avg,
            }, f, indent=2, default=str)
        print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
