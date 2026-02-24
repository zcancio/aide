#!/usr/bin/env python3
"""
AIde Prompt Eval Harness (v3.0)

Validates prompts work, scores output quality, detects regressions,
and compares models — all producing consistent numeric scores.

Usage:
  # Full eval with scoring
  python eval_v3.py

  # Quick smoke test (1 per tier)
  python eval_v3.py --smoke

  # Save current run as baseline
  python eval_v3.py --save-baseline

  # Compare current run against saved baseline
  python eval_v3.py --against-baseline baselines/v3.0_sonnet4.5.json

  # Compare two models on the same prompts
  python eval_v3.py --model-compare claude-haiku-4-5-20251001 claude-haiku-5-20260301

  # Cache validation only
  python eval_v3.py --cache-only

  # Run specific scenarios
  python eval_v3.py --scenarios create_graduation update_simple

  # Override prompt version tag
  python eval_v3.py --prompt-version v3.1

  # Save golden files for mock LLM
  python eval_v3.py --save-golden

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
from datetime import datetime
from pathlib import Path

import anthropic

from scoring import (
    ScenarioScore,
    RegressionResult,
    compare_to_baseline,
    load_baseline,
    save_baseline,
    score_scenario,
    DIMENSION_WEIGHTS,
)

# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

PROMPTS_DIR = Path(__file__).parent
if (Path(__file__).parent / "prompts").exists():
    PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text()


def build_system_blocks(tier: str, snapshot: dict | None) -> list[dict]:
    """Build system prompt as content blocks with cache_control."""
    prefix = load_prompt("shared_prefix")
    tier_file = {"L2": "l2_tier", "L3": "l3_tier", "L4": "l4_tier"}[tier]
    tier_text = load_prompt(tier_file)

    blocks = [
        {
            "type": "text",
            "text": f"{prefix}\n\n{tier_text}",
            "cache_control": {"type": "ephemeral"},
        },
    ]

    if snapshot is not None:
        snapshot_json = json.dumps(snapshot, indent=2)
        blocks.append({
            "type": "text",
            "text": f"## Current Snapshot\n```json\n{snapshot_json}\n```",
        })

    return blocks


# ---------------------------------------------------------------------------
# Test snapshots
# ---------------------------------------------------------------------------

GRADUATION_SNAPSHOT = {
    "meta": {"title": "Sophie's Graduation Party", "identity": "Graduation party. May 22, UC Davis."},
    "entities": {
        "page": {"id": "page", "parent": "root", "display": "page", "props": {"title": "Sophie's Graduation Party"}},
        "ceremony": {"id": "ceremony", "parent": "page", "display": "card", "props": {"date": "2026-05-22", "time": "10:00 AM", "venue": "UC Davis", "guests": 40}},
        "guests": {"id": "guests", "parent": "page", "display": "table", "props": {"title": "Guest List"}},
        "guest_aunt_linda": {"id": "guest_aunt_linda", "parent": "guests", "display": "row", "props": {"name": "Aunt Linda", "rsvp": "pending", "traveling_from": "Portland"}},
        "guest_uncle_bob": {"id": "guest_uncle_bob", "parent": "guests", "display": "row", "props": {"name": "Uncle Bob", "rsvp": "pending"}},
        "guest_cousin_james": {"id": "guest_cousin_james", "parent": "guests", "display": "row", "props": {"name": "Cousin James", "rsvp": "pending"}},
        "guest_uncle_steve": {"id": "guest_uncle_steve", "parent": "guests", "display": "row", "props": {"name": "Uncle Steve", "rsvp": "pending"}},
        "food": {"id": "food", "parent": "page", "display": "table", "props": {"title": "Food"}},
        "food_main_dish": {"id": "food_main_dish", "parent": "food", "display": "row", "props": {"item": "Main dish", "assigned": "TBD", "confirmed": False}},
        "food_salad": {"id": "food_salad", "parent": "food", "display": "row", "props": {"item": "Salad", "assigned": "TBD", "confirmed": False}},
        "todo": {"id": "todo", "parent": "page", "display": "checklist", "props": {"title": "To Do"}},
        "todo_book_venue": {"id": "todo_book_venue", "parent": "todo", "display": "row", "props": {"task": "Book venue", "done": True}},
        "todo_send_invites": {"id": "todo_send_invites", "parent": "todo", "display": "row", "props": {"task": "Send invites", "done": False}},
        "todo_order_cake": {"id": "todo_order_cake", "parent": "todo", "display": "row", "props": {"task": "Order cake", "done": False}},
    },
}

INSPO_SNAPSHOT = {
    "meta": {"title": "Kitchen Renovation Inspo", "identity": "Kitchen renovation inspiration board."},
    "entities": {
        "page": {"id": "page", "parent": "root", "display": "page", "props": {"title": "Kitchen Renovation Inspo"}},
        "ideas": {"id": "ideas", "parent": "page", "display": "section", "props": {"title": "Ideas"}},
        "idea_walnut": {"id": "idea_walnut", "parent": "ideas", "display": "text", "props": {"content": "Walnut open shelving"}},
        "idea_brass": {"id": "idea_brass", "parent": "ideas", "display": "text", "props": {"content": "Brass cabinet hardware"}},
        "idea_herringbone": {"id": "idea_herringbone", "parent": "ideas", "display": "image", "props": {"src": "https://example.com/herringbone.jpg", "caption": "White herringbone backsplash"}},
        "idea_pendant": {"id": "idea_pendant", "parent": "ideas", "display": "image", "props": {"src": "https://example.com/pendant.jpg", "caption": "Brass pendant lights"}},
        "idea_butcher": {"id": "idea_butcher", "parent": "ideas", "display": "text", "props": {"content": "Butcher block island countertop"}},
        "idea_terracotta": {"id": "idea_terracotta", "parent": "ideas", "display": "image", "props": {"src": "https://example.com/terracotta.jpg", "caption": "Terracotta tile flooring"}},
    },
}

# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

DEFAULT_MODELS = {
    "L2": "claude-haiku-4-5-20251001",
    "L3": "claude-sonnet-4-5-20250929",
    "L4": "claude-sonnet-4-5-20250929",
}

SCENARIOS = [
    {"name": "create_graduation", "tier": "L3", "snapshot": None,
     "message": "Plan Sophie's graduation party. Ceremony May 22 at UC Davis, 10am. About 40 guests. We need to coordinate food, travel, and a to-do list."},
    {"name": "create_poker", "tier": "L3", "snapshot": None,
     "message": "Set up a poker league. 8 players, biweekly Thursday, rotating hosts and snacks. Track standings."},
    {"name": "create_inspo", "tier": "L3", "snapshot": None,
     "message": "Make me an inspiration board for my kitchen renovation. Warm wood tones, white countertops, open shelving."},
    {"name": "update_simple", "tier": "L2", "snapshot": GRADUATION_SNAPSHOT,
     "message": "Aunt Linda RSVPed yes"},
    {"name": "update_multi", "tier": "L2", "snapshot": GRADUATION_SNAPSHOT,
     "message": "Aunt Linda RSVPed yes, she's bringing potato salad, and she's driving from Portland"},
    {"name": "escalation_structural", "tier": "L2", "snapshot": GRADUATION_SNAPSHOT,
     "message": "Add a seating chart with 5 tables, 8 seats each"},
    {"name": "multi_intent", "tier": "L2", "snapshot": GRADUATION_SNAPSHOT,
     "message": "Uncle Steve is confirmed, and do we have enough food for everyone?"},
    {"name": "query_negation", "tier": "L4", "snapshot": GRADUATION_SNAPSHOT,
     "message": "Who hasn't RSVPed yet?"},
    {"name": "query_sufficiency", "tier": "L4", "snapshot": GRADUATION_SNAPSHOT,
     "message": "Do we have enough food for everyone?"},
    {"name": "inspo_reorganize", "tier": "L3", "snapshot": INSPO_SNAPSHOT,
     "message": "Group everything by area — island, backsplash, shelving, flooring, hardware"},
]

SMOKE_SCENARIOS = ["create_graduation", "update_simple", "query_negation"]

# ---------------------------------------------------------------------------
# API runner
# ---------------------------------------------------------------------------

def run_scenario(
    client: anthropic.Anthropic,
    scenario: dict,
    model_override: str | None = None,
    prompt_version: str = "v3.0",
    run_dir: Path | None = None,
) -> ScenarioScore:
    name = scenario["name"]
    tier = scenario["tier"]
    model = model_override or DEFAULT_MODELS[tier]
    snapshot = scenario.get("snapshot")
    message = scenario["message"]

    system_blocks = build_system_blocks(tier, snapshot)
    system_flat = "\n\n".join(b["text"] for b in system_blocks)

    start = time.time()
    first_token_time = None
    full_text = ""

    with client.messages.stream(
        model=model, max_tokens=4096, system=system_blocks,
        messages=[{"role": "user", "content": message}],
    ) as stream:
        for chunk in stream.text_stream:
            if first_token_time is None:
                first_token_time = time.time()
            full_text += chunk

    end = time.time()
    msg = stream.get_final_message()
    usage = msg.usage

    ttfc_ms = int((first_token_time - start) * 1000) if first_token_time else -1
    ttc_ms = int((end - start) * 1000)
    cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_total = cache_creation + cache_read
    cache_pct = (cache_read / cache_total * 100) if cache_total > 0 else 0.0

    result = score_scenario(
        name=name, tier=tier, model=model, prompt_version=prompt_version,
        output_text=full_text, output_tokens=usage.output_tokens,
        latency_ms=ttc_ms, cache_hit_pct=cache_pct,
    )
    result._raw_output = full_text  # type: ignore[attr-defined]
    result._usage = {  # type: ignore[attr-defined]
        "input": usage.input_tokens, "output": usage.output_tokens,
        "cache_creation": cache_creation, "cache_read": cache_read,
        "ttfc_ms": ttfc_ms, "ttc_ms": ttc_ms,
    }

    # Save run artifact for later review
    if run_dir:
        save_run_artifact(run_dir, name, tier, model, prompt_version,
                          system_flat, message, snapshot, full_text, result)

    return result


def save_run_artifact(
    run_dir: Path, name: str, tier: str, model: str, prompt_version: str,
    system_prompt: str, user_message: str, snapshot: dict | None,
    output_text: str, score: ScenarioScore,
):
    """
    Save a complete run artifact for later review.

    Creates a directory per scenario with:
      input.md    — full system prompt + user message (readable)
      output.txt  — raw LLM response
      score.json  — all scores + usage metrics
      snapshot.json — input snapshot (if any)
    """
    scenario_dir = run_dir / name
    scenario_dir.mkdir(parents=True, exist_ok=True)

    # input.md — human-readable, copy-pasteable into playground
    input_md = f"""# {name} — Input

## Metadata
- **Tier:** {tier}
- **Model:** {model}
- **Prompt version:** {prompt_version}
- **Timestamp:** {datetime.now().isoformat()}

## System Prompt

{system_prompt}

## User Message

{user_message}
"""
    (scenario_dir / "input.md").write_text(input_md)

    # output.txt — raw LLM response, no wrapping
    (scenario_dir / "output.txt").write_text(output_text)

    # snapshot.json — input state (if present)
    if snapshot:
        (scenario_dir / "snapshot.json").write_text(json.dumps(snapshot, indent=2))

    # score.json — full scoring breakdown + usage
    score_data = score.to_dict()
    score_data["usage"] = score._usage if hasattr(score, "_usage") else {}  # type: ignore
    (scenario_dir / "score.json").write_text(json.dumps(score_data, indent=2))

# ---------------------------------------------------------------------------
# Cache validation
# ---------------------------------------------------------------------------

def run_cache_test(client: anthropic.Anthropic) -> list[dict]:
    results = []
    tiers = [
        ("L2", DEFAULT_MODELS["L2"], GRADUATION_SNAPSHOT, "mark milk as done"),
        ("L3", DEFAULT_MODELS["L3"], None, "Plan a birthday party for 20 guests"),
        ("L4", DEFAULT_MODELS["L4"], GRADUATION_SNAPSHOT, "How many guests?"),
    ]
    for tier, model, snapshot, message in tiers:
        system = build_system_blocks(tier, snapshot)
        msgs = [{"role": "user", "content": message}]
        tier_results = {"tier": tier, "model": model, "calls": []}
        for call_num in range(2):
            start = time.time()
            with client.messages.stream(model=model, max_tokens=512, system=system, messages=msgs) as stream:
                for _ in stream.text_stream:
                    pass
            elapsed = int((time.time() - start) * 1000)
            usage = stream.get_final_message().usage
            tier_results["calls"].append({
                "call": call_num + 1, "elapsed_ms": elapsed,
                "input_tokens": usage.input_tokens,
                "cache_creation": getattr(usage, "cache_creation_input_tokens", 0) or 0,
                "cache_read": getattr(usage, "cache_read_input_tokens", 0) or 0,
            })
            time.sleep(0.5)
        c1, c2 = tier_results["calls"]
        tier_results["cache_working"] = c2["cache_read"] > 0
        tier_results["tokens_saved"] = c2["cache_read"]
        tier_results["speedup_ms"] = c1["elapsed_ms"] - c2["elapsed_ms"]
        results.append(tier_results)
    return results

# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_score(s: ScenarioScore, verbose: bool = True):
    bar = "█" * int(s.composite * 20) + "░" * (20 - int(s.composite * 20))
    icon = "✅" if s.composite >= 0.8 else "⚠️" if s.composite >= 0.6 else "❌"
    print(f"\n{icon} {s.name} [{bar}] {s.composite:.0%}")
    print(f"   tier={s.tier}  model={s.model.split('-')[1]}  {s.latency_ms}ms  {s.output_tokens}tok  cache={s.cache_hit_pct:.0f}%")
    if verbose:
        for dim_name in DIMENSION_WEIGHTS:
            dim = s.dimensions.get(dim_name)
            if dim:
                d_bar = "█" * int(dim.score * 10) + "░" * (10 - int(dim.score * 10))
                print(f"   {dim_name:<12} [{d_bar}] {dim.score:.0%}  (×{DIMENSION_WEIGHTS[dim_name]:.0%})")
                for note in dim.notes[:2]:
                    print(f"     ↳ {note[:80]}")
    if verbose and hasattr(s, "_raw_output"):
        preview = s._raw_output.strip().split("\n")[:4]  # type: ignore
        print(f"   output:")
        for line in preview:
            print(f"     {line[:90]}")
        total = len(s._raw_output.strip().split("\n"))  # type: ignore
        if total > 4:
            print(f"     ... ({total} lines)")


def print_summary(scores: list[ScenarioScore]):
    print(f"\n{'='*90}")
    print(f"{'Scenario':<26} {'Tier':<4} {'Comp':>5} {'Valid':>6} {'Voice':>6} {'Struc':>6} {'Effic':>6} {'Fidel':>6} {'ms':>6} {'tok':>5}")
    print(f"{'-'*90}")
    for s in scores:
        d = s.dimensions
        print(
            f"{s.name:<26} {s.tier:<4} "
            f"{s.composite:>4.0%} "
            f"{d['validity'].score:>5.0%} "
            f"{d['voice'].score:>5.0%} "
            f"{d['structure'].score:>5.0%} "
            f"{d['efficiency'].score:>5.0%} "
            f"{d['fidelity'].score:>5.0%} "
            f"{s.latency_ms:>5} {s.output_tokens:>5}"
        )
    avg = sum(s.composite for s in scores) / max(len(scores), 1)
    passing = sum(1 for s in scores if s.composite >= 0.8)
    print(f"\nAverage: {avg:.0%} | Passing (≥80%): {passing}/{len(scores)}")


def print_regression(regressions: list[RegressionResult]) -> bool:
    print(f"\n{'='*70}")
    print(f"REGRESSION CHECK")
    print(f"{'='*70}")
    print(f"{'Scenario':<26} {'Base':>6} {'Curr':>6} {'Delta':>7} {'Status':>8}")
    print(f"{'-'*70}")
    for r in regressions:
        icon = {"pass": "✅", "warn": "⚠️", "fail": "❌", "new": "🆕"}[r.status]
        print(f"{r.scenario:<26} {r.baseline_composite:>5.0%} {r.current_composite:>5.0%} {r.delta:>+6.0%} {icon}")
        for dim in r.regressed_dimensions:
            print(f"  ↓ {dim}")
    failed = sum(1 for r in regressions if r.status == "fail")
    if failed:
        print(f"\n⛔ {failed} REGRESSIONS — prompt/model change degraded quality")
    return failed == 0


def print_model_comparison(model_scores: dict[str, list[ScenarioScore]]):
    models = list(model_scores.keys())
    print(f"\n{'='*80}")
    print(f"MODEL COMPARISON")
    print(f"{'='*80}")
    header = f"{'Scenario':<26}"
    for m in models:
        short = m.split("-")[1] if "-" in m else m[:15]
        header += f" {short:>12}"
    print(header)
    print("-" * len(header))
    all_names = sorted({s.name for v in model_scores.values() for s in v})
    for name in all_names:
        row = f"{name:<26}"
        for m in models:
            match = next((s for s in model_scores[m] if s.name == name), None)
            row += f" {match.composite:>11.0%}" if match else f" {'—':>12}"
        print(row)
    print("-" * len(header))
    row = f"{'AVERAGE':<26}"
    for m in models:
        avg = sum(s.composite for s in model_scores[m]) / max(len(model_scores[m]), 1)
        row += f" {avg:>11.0%}"
    print(row)


def print_cache(results: list[dict]):
    print(f"\n{'='*70}")
    print(f"CACHE VALIDATION")
    print(f"{'='*70}")
    for r in results:
        c1, c2 = r["calls"]
        icon = "✅" if r["cache_working"] else "❌"
        print(f"  {r['tier']:<4} call1={c1['elapsed_ms']}ms  call2={c2['elapsed_ms']}ms  "
              f"created={c1['cache_creation']}  read={c2['cache_read']}  {icon}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="AIde Prompt Eval & Scoring")
    p.add_argument("--scenarios", nargs="*")
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--cache-only", action="store_true")
    p.add_argument("--save-baseline", action="store_true")
    p.add_argument("--against-baseline", type=str)
    p.add_argument("--model-compare", nargs="+")
    p.add_argument("--prompt-version", default="v3.0")
    p.add_argument("--save-golden", action="store_true")
    p.add_argument("--output-dir", default=os.environ.get("AIDE_EVAL_DIR", "./eval_output"))
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set"); sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"AIde Prompt Eval — {args.prompt_version}")
    print(f"Output: {out}\n")

    # Cache only
    if args.cache_only:
        print_cache(run_cache_test(client))
        return

    # Pick scenarios
    if args.smoke:
        to_run = [s for s in SCENARIOS if s["name"] in SMOKE_SCENARIOS]
    elif args.scenarios:
        to_run = [s for s in SCENARIOS if s["name"] in args.scenarios]
    else:
        to_run = SCENARIOS

    # Model comparison
    if args.model_compare:
        model_scores: dict[str, list[ScenarioScore]] = {}
        for model in args.model_compare:
            print(f"\n── {model} ──")
            model_run_dir = out / f"runs/compare_{ts}/{model.replace('/', '_')}"
            model_run_dir.mkdir(parents=True, exist_ok=True)
            scores = []
            for sc in to_run:
                try:
                    r = run_scenario(client, sc, model_override=model,
                                     prompt_version=args.prompt_version, run_dir=model_run_dir)
                    print_score(r, verbose=False)
                    scores.append(r)
                except Exception as e:
                    print(f"  ERROR {sc['name']}: {e}")
            model_scores[model] = scores
        print_model_comparison(model_scores)
        with open(out / f"model_compare_{ts}.json", "w") as f:
            json.dump({"models": {m: [s.to_dict() for s in v] for m, v in model_scores.items()}}, f, indent=2)
        return

    # Standard run
    run_dir = out / f"runs/{args.prompt_version}_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"Run artifacts: {run_dir}\n")

    scores: list[ScenarioScore] = []
    for sc in to_run:
        try:
            r = run_scenario(client, sc, prompt_version=args.prompt_version, run_dir=run_dir)
            print_score(r, verbose=args.verbose or not args.smoke)
            scores.append(r)
            if args.save_golden and hasattr(r, "_raw_output"):
                ext = "txt" if sc["tier"] == "L4" else "jsonl"
                (out / f"{sc['name']}.{ext}").write_text(r._raw_output)  # type: ignore
        except Exception as e:
            print(f"\n  ERROR {sc['name']}: {e}")

    print_summary(scores)

    # Save baseline
    if args.save_baseline:
        bl_dir = out / "baselines"; bl_dir.mkdir(exist_ok=True)
        bl_path = bl_dir / f"{args.prompt_version}_{ts}.json"
        save_baseline(scores, str(bl_path), metadata={
            "timestamp": datetime.now().isoformat(),
            "prompt_version": args.prompt_version,
            "models": {s.name: s.model for s in scores},
        })
        print(f"\n📌 Baseline saved: {bl_path}")

    # Regression check
    if args.against_baseline:
        baseline = load_baseline(args.against_baseline)
        regressions = compare_to_baseline(scores, baseline)
        gate = print_regression(regressions)
        with open(out / f"regression_{ts}.json", "w") as f:
            json.dump({"results": [r.to_dict() for r in regressions], "gate_passed": gate}, f, indent=2)
        if not gate:
            sys.exit(1)

    # Cache (full runs only)
    if not args.smoke and not args.against_baseline:
        print_cache(run_cache_test(client))

    # Save report
    with open(out / f"eval_{args.prompt_version}_{ts}.json", "w") as f:
        json.dump({
            "prompt_version": args.prompt_version,
            "timestamp": datetime.now().isoformat(),
            "run_dir": str(run_dir),
            "average": sum(s.composite for s in scores) / max(len(scores), 1),
            "scores": [s.to_dict() for s in scores],
        }, f, indent=2)
    print(f"\nRun artifacts: {run_dir}")
    print(f"  Each scenario has: input.md, output.txt, score.json, snapshot.json")


if __name__ == "__main__":
    main()
