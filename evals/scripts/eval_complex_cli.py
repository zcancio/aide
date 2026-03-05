#!/usr/bin/env python3
"""
Complex scenario eval runner using Claude Code CLI.

Runs complex conversational scenarios using the Claude Code CLI instead of
the Anthropic API directly. This allows testing with the same tool environment
that users experience.

Usage:
  # Run all complex scenarios
  python eval_complex_cli.py

  # Run specific scenario
  python eval_complex_cli.py --scenario christmas_week_realistic

  # Verbose: show full output per turn
  python eval_complex_cli.py -v

  # Save run artifacts for review
  python eval_complex_cli.py --save

Requirements:
  - Claude Code CLI installed and authenticated (`claude` command available)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path

from complex_scenarios import COMPLEX_SCENARIOS

# ---------------------------------------------------------------------------
# Add backend to path for imports
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from backend.services.classifier import classify as backend_classify
from backend.services.prompt_builder import build_system_blocks
from engine.kernel.kernel import apply, empty_snapshot

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

DEFAULT_MODELS = {
    "L3": "claude-sonnet-4-5-20250929",
    "L4": "claude-opus-4-5-20251101",
}

# ---------------------------------------------------------------------------
# CLI Output Parser
# ---------------------------------------------------------------------------


def parse_cli_output(output: str) -> dict:
    """
    Parse Claude Code CLI stream-json output.

    Returns dict with:
      - tool_calls: list of tool calls from assistant messages
      - text_blocks: list of text outputs
      - usage: token usage stats
      - duration_ms: total duration
      - cost_usd: total cost
      - result: final text result
    """
    tool_calls = []
    text_blocks = []
    usage = {}
    duration_ms = 0
    cost_usd = 0
    result = ""

    for line in output.strip().split("\n"):
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        msg_type = data.get("type")

        if msg_type == "assistant":
            # Extract content from assistant message
            message = data.get("message", {})
            content = message.get("content", [])
            for block in content:
                if block.get("type") == "tool_use":
                    tool_calls.append({
                        "name": block.get("name"),
                        "input": block.get("input", {}),
                        "id": block.get("id"),
                    })
                elif block.get("type") == "text":
                    text_blocks.append(block.get("text", ""))

        elif msg_type == "result":
            usage = data.get("usage", {})
            duration_ms = data.get("duration_ms", 0)
            cost_usd = data.get("total_cost_usd", 0)
            result = data.get("result", "")

            # Also check permission_denials for attempted tool calls
            for denial in data.get("permission_denials", []):
                tool_calls.append({
                    "name": denial.get("tool_name"),
                    "input": denial.get("tool_input", {}),
                    "id": denial.get("tool_use_id"),
                    "denied": True,
                })

    return {
        "tool_calls": tool_calls,
        "text_blocks": text_blocks,
        "usage": usage,
        "duration_ms": duration_ms,
        "cost_usd": cost_usd,
        "result": result,
    }


# ---------------------------------------------------------------------------
# Snapshot builder
# ---------------------------------------------------------------------------


def apply_tool_calls_to_snapshot(snapshot: dict, tool_calls: list[dict]) -> dict:
    """Apply tool calls to snapshot using the kernel."""
    working = json.loads(json.dumps(snapshot))

    for tc in tool_calls:
        name = tc.get("name", "")
        inp = tc.get("input", {})

        # Convert tool call to reducer event
        event = None
        if name == "mutate_entity":
            action = inp.get("action")
            if action == "create":
                event = {
                    "t": "entity.create",
                    "id": inp.get("id"),
                    "parent": inp.get("parent"),
                    "display": inp.get("display"),
                    "p": inp.get("props", {}),
                }
            elif action == "update":
                event = {
                    "t": "entity.update",
                    "ref": inp.get("ref"),
                    "p": inp.get("props", {}),
                }
            elif action == "remove":
                event = {
                    "t": "entity.remove",
                    "ref": inp.get("ref"),
                }
        elif name == "set_relationship":
            event = {
                "t": "rel.set" if inp.get("action") != "remove" else "rel.remove",
                "from": inp.get("from"),
                "to": inp.get("to"),
                "type": inp.get("type"),
                "cardinality": inp.get("cardinality"),
            }

        if event:
            result = apply(working, event)
            if result.accepted:
                working = result.snapshot

    return working


# ---------------------------------------------------------------------------
# Turn runner using CLI
# ---------------------------------------------------------------------------


def classify_tier(message: str, snapshot: dict | None) -> str:
    """Classify message to appropriate tier."""
    snapshot = snapshot or {"entities": {}}
    has_schema = bool(snapshot.get("entities"))
    result = backend_classify(message, snapshot, has_schema)
    return result.tier


def run_turn_cli(
    message: str,
    tier: str,
    snapshot: dict | None,
    history: list[dict],
    prompt_version: str | None = None,
) -> dict:
    """Run a single turn using Claude Code CLI."""
    model = DEFAULT_MODELS[tier]
    system_blocks = build_system_blocks(tier, snapshot, version=prompt_version)
    system_prompt = "\n\n".join(b["text"] for b in system_blocks)

    # Build conversation context
    context_parts = []
    for turn in history[-5:]:
        context_parts.append(f"User: {turn['user_message']}")
        if turn.get("assistant_response"):
            context_parts.append(f"Assistant: {turn['assistant_response']}")
    context_parts.append(f"User: {message}")
    full_prompt = "\n\n".join(context_parts)

    # Write system prompt to temp file (can be very long)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(system_prompt)
        system_file = f.name

    start = time.time()
    try:
        # Run Claude Code CLI
        result = subprocess.run(
            [
                "claude",
                "-p",
                "--output-format", "stream-json",
                "--verbose",
                "--model", model,
                "--system-prompt", f"@{system_file}",
                "--dangerously-skip-permissions",  # For eval, skip permission prompts
                full_prompt,
            ],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(Path(__file__).parent),
        )
        output = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired:
        output = ""
        stderr = "Timeout"
    finally:
        os.unlink(system_file)

    end = time.time()
    wall_time_ms = int((end - start) * 1000)

    # Parse CLI output
    parsed = parse_cli_output(output)

    # Extract voice text from tool calls
    voice_text = ""
    for tc in parsed["tool_calls"]:
        if tc.get("name") == "voice":
            voice_text = tc.get("input", {}).get("text", "")

    # Build JSONL-style output for compatibility with scoring
    reducer_events = []
    for tc in parsed["tool_calls"]:
        name = tc.get("name", "")
        inp = tc.get("input", {})

        if name == "voice":
            reducer_events.append({"t": "voice", "text": inp.get("text", "")})
        elif name == "mutate_entity":
            action = inp.get("action")
            if action == "create":
                reducer_events.append({
                    "t": "entity.create",
                    "id": inp.get("id"),
                    "parent": inp.get("parent"),
                    "display": inp.get("display"),
                    "p": inp.get("props", {}),
                })
            elif action == "update":
                reducer_events.append({
                    "t": "entity.update",
                    "ref": inp.get("ref"),
                    "p": inp.get("props", {}),
                })
            elif action == "remove":
                reducer_events.append({
                    "t": "entity.remove",
                    "ref": inp.get("ref"),
                })
        elif name == "set_relationship":
            reducer_events.append({
                "t": "rel.set" if inp.get("action") != "remove" else "rel.remove",
                "from": inp.get("from"),
                "to": inp.get("to"),
                "type": inp.get("type"),
                "cardinality": inp.get("cardinality"),
            })

    output_lines = [json.dumps(e) for e in reducer_events]
    clean_output = "\n".join(output_lines)

    usage = parsed["usage"]

    return {
        "tier": tier,
        "model": model,
        "output": clean_output,
        "raw_output": output,  # Full CLI output for debugging
        "tool_calls": parsed["tool_calls"],
        "text_blocks": parsed["text_blocks"],
        "voice_text": voice_text,
        "reducer_events": reducer_events,
        "result": parsed["result"],
        "ttc_ms": parsed["duration_ms"] or wall_time_ms,
        "ttfc_ms": -1,  # Not available from CLI
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_creation": usage.get("cache_creation_input_tokens", 0),
        "cache_read": usage.get("cache_read_input_tokens", 0),
        "cost_usd": parsed["cost_usd"],
        "stderr": stderr,
    }


# ---------------------------------------------------------------------------
# Scenario runner
# ---------------------------------------------------------------------------


def run_scenario(
    scenario: dict,
    verbose: bool = False,
    save_dir: Path | None = None,
    max_turns: int | None = None,
    prompt_version: str | None = None,
) -> dict:
    """Run a complete multi-turn scenario using CLI."""
    name = scenario["name"]
    turns = scenario["turns"]
    if max_turns is not None:
        turns = turns[:max_turns]

    print(f"\n{'=' * 70}")
    print(f"📖 {name}: {scenario['description']}")
    print(f"   {len(turns)} turns (using Claude Code CLI)")
    print(f"{'=' * 70}")

    snapshot: dict = empty_snapshot()
    history: list[dict] = []
    turn_results: list[dict] = []
    total_cost = 0.0

    for i, turn_spec in enumerate(turns):
        message = turn_spec["message"]
        expected_tier = turn_spec["expected_tier"]
        accept_tiers = turn_spec.get("accept_tiers", [expected_tier])
        notes = turn_spec.get("notes", "")

        # Classify
        classified_tier = classify_tier(message, snapshot)
        actual_tier = classified_tier if classified_tier in accept_tiers else expected_tier

        print(f'\n  Turn {i + 1}/{len(turns)}: "{message[:60]}..."')
        print(f"    expected={expected_tier}  classified={classified_tier}  actual={actual_tier}")

        try:
            snapshot_before = json.loads(json.dumps(snapshot))

            result = run_turn_cli(
                message, actual_tier, snapshot, history,
                prompt_version=prompt_version
            )

            # Update snapshot
            new_snapshot = apply_tool_calls_to_snapshot(snapshot, result["tool_calls"])
            entity_count = len(new_snapshot.get("entities", {}))
            entity_delta = entity_count - len(snapshot.get("entities", {}))

            total_cost += result.get("cost_usd", 0)

            # Track history
            if result["voice_text"]:
                assistant_summary = result["voice_text"]
            elif result["text_blocks"]:
                assistant_summary = result["text_blocks"][0][:200]
            else:
                assistant_summary = f"Applied {len(result['tool_calls'])} operations."

            history.append({
                "user_message": message,
                "assistant_response": assistant_summary,
            })

            # Print result
            tier_match = "✓" if classified_tier in accept_tiers else "✗"
            print(
                f"    tier={tier_match}  "
                f"{result['ttc_ms']}ms  "
                f"{result['output_tokens']}tok  "
                f"${result.get('cost_usd', 0):.4f}  "
                f"entities={entity_count} ({entity_delta:+d})  "
                f"tools={len(result['tool_calls'])}"
            )

            if verbose:
                for tc in result["tool_calls"][:5]:
                    denied = " [DENIED]" if tc.get("denied") else ""
                    print(f"      → {tc['name']}{denied}: {str(tc['input'])[:60]}...")
                if len(result["tool_calls"]) > 5:
                    print(f"      ... +{len(result['tool_calls']) - 5} more")
                if result["voice_text"]:
                    print(f"      💬 {result['voice_text'][:80]}")
                if notes:
                    print(f"    📝 {notes[:80]}")

            # Save turn artifact
            if save_dir:
                turn_dir = save_dir / name / f"turn_{i + 1:02d}"
                turn_dir.mkdir(parents=True, exist_ok=True)
                (turn_dir / "output.json").write_text(json.dumps({
                    "message": message,
                    "tier": actual_tier,
                    "tool_calls": result["tool_calls"],
                    "text_blocks": result["text_blocks"],
                    "voice_text": result["voice_text"],
                    "usage": {
                        "input_tokens": result["input_tokens"],
                        "output_tokens": result["output_tokens"],
                        "cache_creation": result["cache_creation"],
                        "cache_read": result["cache_read"],
                    },
                    "ttc_ms": result["ttc_ms"],
                    "cost_usd": result.get("cost_usd", 0),
                }, indent=2))
                (turn_dir / "snapshot_after.json").write_text(json.dumps(new_snapshot, indent=2))
                (turn_dir / "cli_output.txt").write_text(result["raw_output"])

            snapshot = new_snapshot

            turn_results.append({
                "turn": i + 1,
                "message": message,
                "tier": actual_tier,
                "expected_tier": expected_tier,
                "tier_correct": classified_tier in accept_tiers,
                "tool_calls": result["tool_calls"],
                "voice_text": result["voice_text"],
                "ttc_ms": result["ttc_ms"],
                "output_tokens": result["output_tokens"],
                "cost_usd": result.get("cost_usd", 0),
                "entity_count": entity_count,
                "entity_delta": entity_delta,
                "snapshot_before": snapshot_before,
                "snapshot_after": json.loads(json.dumps(new_snapshot)),
            })

        except Exception as e:
            print(f"    ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            turn_results.append({
                "turn": i + 1,
                "message": message,
                "error": str(e),
            })

    # Summary
    tier_accuracy = sum(1 for t in turn_results if t.get("tier_correct", False)) / max(len(turn_results), 1)
    total_tokens = sum(t.get("output_tokens", 0) for t in turn_results)
    total_time = sum(t.get("ttc_ms", 0) for t in turn_results)
    final_entities = turn_results[-1].get("entity_count", 0) if turn_results else 0

    print(f"\n  {'─' * 50}")
    print(f"  ✅ {name}")
    print(
        f"     turns: {len(turns)} | entities: {final_entities} | "
        f"tokens: {total_tokens} | time: {total_time}ms | "
        f"cost: ${total_cost:.4f} | tier accuracy: {tier_accuracy:.0%}"
    )

    # Save telemetry
    if save_dir:
        telemetry = {
            "aide_id": str(uuid.uuid4()),
            "name": name,
            "scenario_id": name,
            "timestamp": datetime.now().isoformat(),
            "runner": "claude-code-cli",
            "turns": [
                {
                    "turn": t["turn"],
                    "tier": t.get("tier", "L3"),
                    "model": DEFAULT_MODELS.get(t.get("tier", "L3"), "unknown"),
                    "message": t["message"],
                    "tool_calls": t.get("tool_calls", []),
                    "voice_text": t.get("voice_text", ""),
                    "usage": {
                        "output_tokens": t.get("output_tokens", 0),
                    },
                    "ttc_ms": t.get("ttc_ms", 0),
                    "cost_usd": t.get("cost_usd", 0),
                }
                for t in turn_results
                if "error" not in t
            ],
            "final_snapshot": turn_results[-1].get("snapshot_after") if turn_results else None,
            "total_cost_usd": total_cost,
        }
        telemetry_path = save_dir / name / "telemetry.json"
        telemetry_path.write_text(json.dumps(telemetry, indent=2))
        print(f"  📼 Telemetry saved: {telemetry_path}")

    return {
        "name": name,
        "tier_accuracy": tier_accuracy,
        "total_tokens": total_tokens,
        "total_time_ms": total_time,
        "total_cost_usd": total_cost,
        "final_entity_count": final_entities,
        "turns": turn_results,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def get_scenario(name: str) -> dict | None:
    return next((s for s in COMPLEX_SCENARIOS if s["name"] == name), None)


def main():
    p = argparse.ArgumentParser(description="Complex scenario eval using Claude Code CLI")
    p.add_argument("--scenario", type=str, help="Run specific scenario")
    p.add_argument("--turns", type=int, help="Limit number of turns")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--save", action="store_true", help="Save run artifacts")
    p.add_argument("--output-dir", default=os.environ.get("AIDE_EVAL_DIR", "./eval_output"))
    p.add_argument("--prompt-version", type=str, help="Prompt version to use")
    args = p.parse_args()

    # Check claude CLI is available
    try:
        subprocess.run(["claude", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code")
        sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_dir = Path(args.output_dir) / f"complex_cli_{ts}" if args.save else None
    if save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)
        print(f"Saving artifacts to: {save_dir}")

    # Pick scenarios
    if args.scenario:
        scenario = get_scenario(args.scenario)
        if not scenario:
            print(f"Unknown scenario: {args.scenario}")
            print(f"Available: {', '.join(s['name'] for s in COMPLEX_SCENARIOS)}")
            sys.exit(1)
        to_run = [scenario]
    else:
        to_run = COMPLEX_SCENARIOS

    print("AIde Complex Scenario Eval (Claude Code CLI)")
    print(f"Scenarios: {len(to_run)} | Started: {datetime.now().isoformat()}\n")

    # Run
    results = []
    for scenario in to_run:
        try:
            result = run_scenario(
                scenario,
                verbose=args.verbose,
                save_dir=save_dir,
                max_turns=args.turns,
                prompt_version=args.prompt_version,
            )
            results.append(result)
        except Exception as e:
            print(f"\n  FATAL ERROR in {scenario['name']}: {e}")
            import traceback
            traceback.print_exc()

    # Final summary
    print(f"\n\n{'=' * 70}")
    print("COMPLEX SCENARIO SUMMARY (CLI)")
    print(f"{'=' * 70}")
    print(f"{'Scenario':<26} {'Turns':>6} {'Tier%':>6} {'Tokens':>7} {'Time':>7} {'Cost':>8} {'Entities':>9}")
    print(f"{'-' * 70}")

    for r in results:
        print(
            f"{r['name']:<26} {len(r['turns']):>6} "
            f"{r['tier_accuracy']:>5.0%} {r['total_tokens']:>7} "
            f"{r['total_time_ms']:>6}ms ${r['total_cost_usd']:>6.2f} {r['final_entity_count']:>9}"
        )

    total_cost = sum(r["total_cost_usd"] for r in results)
    print(f"\nTotal cost: ${total_cost:.2f}")

    # Save report
    if save_dir:
        report_path = save_dir / "report.json"
        with open(report_path, "w") as f:
            json.dump(
                {
                    "timestamp": datetime.now().isoformat(),
                    "runner": "claude-code-cli",
                    "results": results,
                    "total_cost_usd": total_cost,
                },
                f,
                indent=2,
                default=str,
            )
        print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
