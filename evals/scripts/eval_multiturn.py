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

  # Test candidate prompt version
  python eval_multiturn.py --prompt-version v2

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
import uuid
from datetime import datetime
from pathlib import Path

import anthropic
from scenarios_multiturn import MULTI_TURN_SCENARIOS, get_scenario
from scoring import parse_jsonl, score_scenario

# ---------------------------------------------------------------------------
# Prompt loading — unified with backend
# ---------------------------------------------------------------------------

# Add backend to path and import modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from backend.services.classifier import classify as backend_classify
from backend.services.prompt_builder import build_system_blocks
from backend.services.tool_defs import TOOLS
from backend.services.tool_utils import tool_use_to_reducer_event
from engine.kernel.kernel import apply, empty_snapshot

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

DEFAULT_MODELS = {
    "L3": "claude-sonnet-4-5-20250929",
    "L4": "claude-sonnet-4-5-20250929",
}

# ---------------------------------------------------------------------------
# Snapshot builder — applies JSONL output to build next turn's state
# ---------------------------------------------------------------------------


def apply_output_to_snapshot(snapshot: dict, output_text: str, tier: str) -> dict:
    """
    Apply LLM output through the production kernel.

    Both L3 and L4 can emit mutations (L4 creates initial structure).
    """
    parsed, _ = parse_jsonl(output_text)
    working = json.loads(json.dumps(snapshot))

    for event in parsed:
        # Skip signals - they don't mutate state
        if event.get("t") in ("voice", "escalate", "clarify", "batch.start", "batch.end"):
            continue

        result = apply(working, event)
        if result.accepted:
            working = result.snapshot

    return working


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
    Classify message to appropriate tier using the backend classifier.
    Returns tier string (L3 or L4).
    """
    snapshot = snapshot or {"entities": {}}
    has_schema = bool(snapshot.get("entities"))
    result = backend_classify(message, snapshot, has_schema)
    return result.tier


def run_turn(
    client: anthropic.Anthropic,
    message: str,
    tier: str,
    snapshot: dict | None,
    history: list[dict],
    prompt_version: str | None = None,
) -> dict:
    """Run a single turn and return results."""
    model = DEFAULT_MODELS[tier]
    system = build_system_blocks(tier, snapshot, version=prompt_version)
    messages = build_messages_with_history(history, message)

    start = time.time()
    first_token_time = None
    tool_calls: list[dict] = []
    text_blocks: list[str] = []

    # Use tools like production
    with client.messages.stream(
        model=model,
        max_tokens=4096,
        system=system,
        messages=messages,
        tools=TOOLS,
    ) as stream:
        for event in stream:
            if first_token_time is None and event.type in ("content_block_start", "content_block_delta"):
                first_token_time = time.time()

    end = time.time()
    final_message = stream.get_final_message()
    usage = final_message.usage

    # Extract tool calls and text from response
    for block in final_message.content:
        if block.type == "tool_use":
            tool_calls.append({"name": block.name, "input": block.input})
        elif block.type == "text":
            text_blocks.append(block.text)

    # Convert tool calls to reducer events (JSONL format for scoring compatibility)
    reducer_events = []
    voice_text = ""
    for tc in tool_calls:
        if tc["name"] == "voice":
            voice_text = tc["input"].get("text", "")
            reducer_events.append({"t": "voice", "text": voice_text})
        else:
            event = tool_use_to_reducer_event(tc["name"], tc["input"])
            if event:
                reducer_events.append(event)

    # Build JSONL output for scoring (maintains compatibility with existing scoring code)
    output_lines = [json.dumps(e) for e in reducer_events]
    clean_output = "\n".join(output_lines)

    return {
        "tier": tier,
        "model": model,
        "output": clean_output,
        "raw_output": clean_output,
        "had_fences": False,
        "tool_calls": tool_calls,
        "text_blocks": text_blocks,
        "voice_text": voice_text,
        "reducer_events": reducer_events,
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
    max_turns: int | None = None,
    prompt_version: str | None = None,
) -> dict:
    """Run a complete multi-turn scenario, building state across turns."""
    name = scenario["name"]
    turns = scenario["turns"]
    if max_turns is not None:
        turns = turns[:max_turns]

    print(f"\n{'=' * 70}")
    print(f"📖 {name}: {scenario['description']}")
    print(f"   {len(turns)} turns")
    print(f"{'=' * 70}")

    snapshot: dict = empty_snapshot()
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
                warm_system = build_system_blocks(tier, snapshot, version=prompt_version)
                # Minimal request — must include tools to match actual calls
                # Anthropic cache is prefix-based: system + tools must match
                client.messages.create(
                    model=DEFAULT_MODELS[tier],
                    max_tokens=1,
                    system=warm_system,
                    messages=[{"role": "user", "content": "ping"}],
                    tools=TOOLS,
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

        print(f'\n  Turn {i + 1}/{len(turns)}: "{message}"')
        print(f"    expected={expected_tier}  classified={classified_tier}  actual={actual_tier}")

        try:
            # Capture state BEFORE this turn (for viewer)
            snapshot_before = json.loads(json.dumps(snapshot))
            system_prompt_text = "\n\n".join(
                b["text"]
                for b in build_system_blocks(
                    classified_tier if classified_tier in accept_tiers else expected_tier,
                    snapshot,
                    version=prompt_version,
                )
            )

            result = run_turn(client, message, actual_tier, snapshot, history, prompt_version=prompt_version)

            # Retry guard: if L3 produced zero parseable JSONL, it slipped
            # into conversational mode. Retry once with explicit nudge.
            if actual_tier == "L3":
                check_parsed, _ = parse_jsonl(result["output"])
                if not check_parsed:
                    print(f"    ⚠ {actual_tier} produced plain text, retrying with nudge...")
                    retry_msg = message + "\n\n[System: respond with JSONL operations only. No prose.]"
                    retry_result = run_turn(
                        client, retry_msg, actual_tier, snapshot, history, prompt_version=prompt_version
                    )
                    retry_parsed, _ = parse_jsonl(retry_result["output"])
                    if retry_parsed:
                        result = retry_result
                        result["retried"] = True
                        print(f"    ✓ Retry produced {len(retry_parsed)} operations")
                    else:
                        result["retried"] = True
                        print("    ✗ Retry also failed — plain text output")

            effective_tier = actual_tier

            # Update snapshot from clean output (fences stripped)
            # Done BEFORE scoring so structure scorer can detect orphans
            new_snapshot = apply_output_to_snapshot(snapshot, result["output"], effective_tier)
            entity_count = len(new_snapshot.get("entities", {}))
            entity_delta = entity_count - len(snapshot.get("entities", {}))

            # Score this turn (use raw output so fence detection works)
            # Pass new_snapshot so structure scorer can check for orphans
            turn_score = score_scenario(
                name=f"{name}_t{i + 1}",
                tier=effective_tier,
                model=result["model"],
                prompt_version="v3.1",
                output_text=result.get("raw_output", result["output"]),
                output_tokens=result["output_tokens"],
                latency_ms=result["ttc_ms"],
                snapshot=new_snapshot,
                user_message=message,
                turn_hints=turn_spec.get("checks", {}),
            )

            # Track history — use natural language summaries, NOT bracket format
            # that the model will mimic in its own output
            if actual_tier == "L4":
                assistant_summary = result["output"][:200]
            else:
                # Summarize what changed in plain language
                parts = []
                parsed_events, _ = parse_jsonl(result["output"])
                creates = [e.get("id", "") for e in parsed_events if e.get("t") == "entity.create"]
                updates = [e.get("ref", "") for e in parsed_events if e.get("t") == "entity.update"]
                if creates:
                    suffix = f" +{len(creates) - 3} more" if len(creates) > 3 else ""
                    parts.append(f"Created {', '.join(creates[:3])}" + suffix)
                if updates:
                    suffix = f" +{len(updates) - 3} more" if len(updates) > 3 else ""
                    parts.append(f"Updated {', '.join(updates[:3])}" + suffix)
                voice_lines = [e.get("text", "") for e in parsed_events if e.get("t") == "voice"]
                clarify_lines = [e.get("text", "") for e in parsed_events if e.get("t") == "clarify"]
                if clarify_lines:
                    # Clarification takes priority — it's what the user sees
                    assistant_summary = "Question: " + clarify_lines[-1]
                elif voice_lines:
                    assistant_summary = voice_lines[-1]
                elif parts:
                    assistant_summary = ". ".join(parts) + "."
                else:
                    assistant_summary = "Applied changes."
            history.append(
                {
                    "user_message": message,
                    "assistant_response": assistant_summary,
                }
            )

            # Print turn result
            bar = "█" * int(turn_score.composite * 10) + "░" * (10 - int(turn_score.composite * 10))
            tier_match = "✓" if classified_tier in accept_tiers else "✗"
            print(
                f"    score=[{bar}] {turn_score.composite:.0%}  "
                f"tier={tier_match}  "
                f"{result['ttc_ms']}ms  "
                f"{result['output_tokens']}tok  "
                f"entities={entity_count} ({entity_delta:+d})"
            )

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
                turn_dir = save_dir / name / f"turn_{i + 1:02d}"
                turn_dir.mkdir(parents=True, exist_ok=True)

                sys_prompt_blocks = build_system_blocks(actual_tier, snapshot, version=prompt_version)
                sys_prompt_text = chr(10).join(b["text"] for b in sys_prompt_blocks)
                (turn_dir / "input.md").write_text(
                    f"# Turn {i + 1}: {message}\n\n"
                    f"## Tier: {actual_tier} (expected: {expected_tier}, classified: {classified_tier})\n\n"
                    f"## Notes\n{notes}\n\n"
                    f"## Snapshot before this turn\n```json\n{json.dumps(snapshot, indent=2)}\n```\n\n"
                    f"## System prompt\n{sys_prompt_text}"
                )
                (turn_dir / "output.txt").write_text(result.get("raw_output", result["output"]))
                (turn_dir / "snapshot_after.json").write_text(json.dumps(new_snapshot, indent=2))
                (turn_dir / "score.json").write_text(json.dumps(turn_score.to_dict(), indent=2))
                (turn_dir / "usage.json").write_text(
                    json.dumps(
                        {
                            "ttfc_ms": result["ttfc_ms"],
                            "ttc_ms": result["ttc_ms"],
                            "input_tokens": result["input_tokens"],
                            "output_tokens": result["output_tokens"],
                            "cache_creation": result["cache_creation"],
                            "cache_read": result["cache_read"],
                        },
                        indent=2,
                    )
                )

            snapshot = new_snapshot

            turn_results.append(
                {
                    "turn": i + 1,
                    "message": message,
                    "tier": actual_tier,
                    "expected_tier": expected_tier,
                    "classified_tier": actual_tier,  # Tier actually used in the prompt
                    "classifier_raw": classified_tier,  # Raw classifier output (before fallback)
                    "tier_correct": actual_tier in accept_tiers,
                    "notes": notes,
                    # Full score breakdown
                    "score": {
                        "composite": turn_score.composite,
                        "validity": (
                            turn_score.dimensions["validity"].score if "validity" in turn_score.dimensions else 0
                        ),
                        "voice": turn_score.dimensions["voice"].score if "voice" in turn_score.dimensions else 0,
                        "structure": (
                            turn_score.dimensions["structure"].score if "structure" in turn_score.dimensions else 0
                        ),
                        "efficiency": (
                            turn_score.dimensions["efficiency"].score if "efficiency" in turn_score.dimensions else 0
                        ),
                        "fidelity": (
                            turn_score.dimensions["fidelity"].score if "fidelity" in turn_score.dimensions else 0
                        ),
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
                    "tool_calls": result.get("tool_calls", []),
                    "text_blocks": result.get("text_blocks", []),
                    "voice_text": result.get("voice_text", ""),
                    "system_prompt": system_prompt_text,
                    "snapshot_before": snapshot_before,
                    "snapshot_after": json.loads(json.dumps(new_snapshot)),
                    # Summary stats
                    "entity_count": entity_count,
                    "entity_delta": entity_delta,
                    "escalated_to": result.get("escalated_to"),
                    "retried": result.get("retried", False),
                    # Clarification signals
                    "clarify": [
                        {"text": e.get("text", ""), "options": e.get("options", [])}
                        for e in (parse_jsonl(result["output"])[0] if actual_tier != "L4" else [])
                        if e.get("t") == "clarify"
                    ],
                }
            )

        except Exception as e:
            print(f"    ❌ ERROR: {e}")
            turn_results.append(
                {
                    "turn": i + 1,
                    "message": message,
                    "error": str(e),
                }
            )

    # Scenario summary
    scores = [
        t["score"]["composite"] if isinstance(t.get("score"), dict) else t.get("score", 0)
        for t in turn_results
        if "score" in t
    ]
    avg_score = sum(scores) / max(len(scores), 1)
    tier_accuracy = sum(1 for t in turn_results if t.get("tier_correct", False)) / max(len(turn_results), 1)
    total_tokens = sum(t.get("output_tokens", 0) for t in turn_results)
    total_time = sum(t.get("ttc_ms", 0) for t in turn_results)
    final_entities = turn_results[-1].get("entity_count", 0) if turn_results else 0

    print(f"\n  {'─' * 50}")
    bar = "█" * int(avg_score * 20) + "░" * (20 - int(avg_score * 20))
    icon = "✅" if avg_score >= 0.8 else "⚠️" if avg_score >= 0.6 else "❌"
    print(f"  {icon} {name} [{bar}] {avg_score:.0%} avg")
    print(
        f"     turns: {len(turns)} | entities: {final_entities} | "
        f"tokens: {total_tokens} | time: {total_time}ms | "
        f"tier accuracy: {tier_accuracy:.0%}"
    )

    # Save telemetry.json in flight recorder format
    if save_dir:

        def build_validation(t: dict) -> dict:
            """Convert eval score to flight recorder validation format."""
            score = t.get("score", {})
            composite = score.get("composite", 0) if isinstance(score, dict) else 0
            issues = []

            # Collect issues from score_details
            details = t.get("score_details", {})
            for dim_name, dim_data in details.items():
                if dim_data.get("score", 1.0) < 1.0:
                    for note in dim_data.get("notes", []):
                        issues.append(f"{dim_name}: {note}")

            return {
                "passed": composite >= 0.8,
                "score": composite,
                "issues": issues,
            }

        telemetry = {
            "aide_id": str(uuid.uuid4()),
            "name": name,
            "scenario_id": name,
            "timestamp": datetime.now().isoformat(),
            "turns": [
                {
                    "turn": t["turn"],
                    "tier": t.get("tier", "L3"),
                    "model": DEFAULT_MODELS.get(t.get("tier", "L3"), "unknown"),
                    "message": t["message"],
                    "tool_calls": t.get("tool_calls", []),
                    "text_blocks": t.get("text_blocks", []),
                    "system_prompt": t.get("system_prompt"),
                    "usage": {
                        "input_tokens": t.get("input_tokens", 0),
                        "output_tokens": t.get("output_tokens", 0),
                        "cache_read": t.get("cache_read", 0),
                        "cache_creation": t.get("cache_creation", 0),
                    },
                    "ttfc_ms": t.get("ttfc_ms", 0),
                    "ttc_ms": t.get("ttc_ms", 0),
                    "validation": build_validation(t),
                }
                for t in turn_results
                if "error" not in t
            ],
            "final_snapshot": turn_results[-1].get("snapshot_after") if turn_results else None,
        }
        telemetry_path = save_dir / name / "telemetry.json"
        telemetry_path.write_text(json.dumps(telemetry, indent=2))
        print(f"  📼 Telemetry saved: {telemetry_path}")

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
    p.add_argument("--turns", type=int, help="Limit number of turns (for smoke tests)")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--save", action="store_true", help="Save run artifacts")
    p.add_argument("--output-dir", default=os.environ.get("AIDE_EVAL_DIR", "./eval_output"))
    p.add_argument("--prompt-version", type=str, help="Prompt version to use (e.g., v1, v2)")
    args = p.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

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

    print("AIde Multi-Turn Eval")
    print(f"Scenarios: {len(to_run)} | Started: {datetime.now().isoformat()}\n")

    # Run
    results = []
    for scenario in to_run:
        try:
            result = run_multiturn_scenario(
                client,
                scenario,
                verbose=args.verbose,
                save_dir=save_dir,
                max_turns=args.turns,
                prompt_version=args.prompt_version,
            )
            results.append(result)
        except Exception as e:
            print(f"\n  FATAL ERROR in {scenario['name']}: {e}")

    # Final summary
    print(f"\n\n{'=' * 70}")
    print("MULTI-TURN SUMMARY")
    print(f"{'=' * 70}")
    print(f"{'Scenario':<26} {'Turns':>6} {'Score':>6} {'Tier%':>6} {'Tokens':>7} {'Time':>7} {'Entities':>9}")
    print(f"{'-' * 70}")

    for r in results:
        print(
            f"{r['name']:<26} {len(r['turns']):>6} {r['avg_score']:>5.1%} "
            f"{r['tier_accuracy']:>5.0%} {r['total_tokens']:>7} "
            f"{r['total_time_ms']:>6}ms {r['final_entity_count']:>9}"
        )

    avg = sum(r["avg_score"] for r in results) / max(len(results), 1)
    print(f"\nOverall average: {avg:.1%}")

    # Save report
    if save_dir:
        report_path = save_dir / "report.json"
        with open(report_path, "w") as f:
            json.dump(
                {
                    "timestamp": datetime.now().isoformat(),
                    "results": results,
                    "overall_average": avg,
                },
                f,
                indent=2,
                default=str,
            )
        print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
