#!/usr/bin/env python3
"""
Compare two eval runs and show regressions/improvements.

Usage:
  python eval_compare.py run_v1/ run_v2/

Output:
  - Comparison table showing scores and token deltas
  - Regressions (>2% drop)
  - Improvements (>2% gain)
"""

import argparse
import json
from pathlib import Path


def compare_runs(run_a: Path, run_b: Path) -> None:
    """Compare two eval runs and print results."""
    # Load reports
    a_report = json.loads((run_a / "report.json").read_text())
    b_report = json.loads((run_b / "report.json").read_text())

    # Match scenarios
    scenarios = match_scenarios(a_report["results"], b_report["results"])

    # Print comparison table
    print_comparison_table(scenarios, run_a.name, run_b.name)

    # Calculate overall stats
    if scenarios:
        overall_a = sum(s["a_score"] for s in scenarios) / len(scenarios)
        overall_b = sum(s["b_score"] for s in scenarios) / len(scenarios)
        overall_delta = overall_b - overall_a
        overall_tokens_a = sum(s["a_tokens"] for s in scenarios)
        overall_tokens_b = sum(s["b_tokens"] for s in scenarios)
        token_delta_pct = (overall_tokens_b - overall_tokens_a) / max(overall_tokens_a, 1) * 100

        print_overall_row(overall_a, overall_b, overall_delta, token_delta_pct)

    # Print regressions
    regressions = [s for s in scenarios if s["delta"] < -0.02]
    if regressions:
        print("\nRegressions (>2% drop):")
        for r in regressions:
            print(f"  ⚠ {r['name']}: {r['delta']:+.1%}")

    # Print improvements
    improvements = [s for s in scenarios if s["delta"] > 0.02]
    if improvements:
        print("\nImprovements (>2% gain):")
        for i in improvements:
            print(f"  ✓ {i['name']}: {i['delta']:+.1%}")


def match_scenarios(a_results: list, b_results: list) -> list:
    """Match scenarios between two runs."""
    b_by_name = {r["name"]: r for r in b_results}
    scenarios = []

    for a in a_results:
        b = b_by_name.get(a["name"])
        if b:
            scenarios.append(
                {
                    "name": a["name"],
                    "a_score": a["avg_score"],
                    "b_score": b["avg_score"],
                    "delta": b["avg_score"] - a["avg_score"],
                    "a_tokens": a.get("total_tokens", 0),
                    "b_tokens": b.get("total_tokens", 0),
                }
            )

    return scenarios


def print_comparison_table(scenarios: list, run_a_name: str, run_b_name: str) -> None:
    """Print formatted comparison table."""
    print("╔" + "═" * 70 + "╗")
    # Calculate padding for header
    header = f"║  EVAL COMPARISON: {run_a_name[:15]} vs {run_b_name[:15]}"
    padding = 70 - len(header) + 2
    print(header + " " * padding + "║")
    print("╠" + "═" * 70 + "╣")
    print("║  Scenario                  │ v1 Score │ v2 Score │ Delta │ Tokens   ║")
    print("╠" + "═" * 28 + "╪" + "═" * 10 + "╪" + "═" * 10 + "╪" + "═" * 7 + "╪" + "═" * 10 + "╣")

    for s in scenarios:
        delta_str = f"{s['delta']:+.1%}"
        token_delta = (s["b_tokens"] - s["a_tokens"]) / max(s["a_tokens"], 1) * 100 if s["a_tokens"] > 0 else 0
        token_str = f"{token_delta:+.0f}%"
        arrow = "↓" if token_delta < 0 else "↑" if token_delta > 0 else "→"
        row = (
            f"║  {s['name']:<26} │ {s['a_score']:>7.1%} │ {s['b_score']:>7.1%} │ "
            f"{delta_str:>5} │ {token_str:>5} {arrow}  ║"
        )
        print(row)


def print_overall_row(overall_a: float, overall_b: float, overall_delta: float, token_delta_pct: float) -> None:
    """Print overall summary row."""
    print("╠" + "═" * 28 + "╧" + "═" * 10 + "╧" + "═" * 10 + "╧" + "═" * 7 + "╧" + "═" * 10 + "╣")
    delta_str = f"{overall_delta:+.1%}"
    token_str = f"{token_delta_pct:+.0f}%"
    arrow = "↓" if token_delta_pct < 0 else "↑" if token_delta_pct > 0 else "→"
    print(f"║  {'OVERALL':<26} │ {overall_a:>7.1%} │ {overall_b:>7.1%} │ {delta_str:>5} │ {token_str:>5} {arrow}  ║")
    print("╚" + "═" * 70 + "╝")


def main() -> None:
    """Main entry point."""
    p = argparse.ArgumentParser(description="Compare two eval runs and show regressions/improvements")
    p.add_argument("run_a", type=Path, help="First run directory")
    p.add_argument("run_b", type=Path, help="Second run directory")
    args = p.parse_args()

    if not (args.run_a / "report.json").exists():
        print(f"ERROR: {args.run_a / 'report.json'} not found")
        return

    if not (args.run_b / "report.json").exists():
        print(f"ERROR: {args.run_b / 'report.json'} not found")
        return

    compare_runs(args.run_a, args.run_b)


if __name__ == "__main__":
    main()
