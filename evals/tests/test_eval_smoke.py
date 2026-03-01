"""
Eval smoke test — runs after eval-smoke Makefile target.

Reads the most recent report.json from eval_output/ and asserts:
1. No scenario errors
2. Good average scores (>= 80%)
3. Entities created
4. Cache hits on turn 2+

Prerequisites:
- eval_multiturn.py must have been run first (via `make eval-smoke`)
- ANTHROPIC_API_KEY must be set in environment

These tests read the eval output — they do NOT call the Anthropic API themselves.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ── Fixtures ─────────────────────────────────────────────────────────────────

EVAL_OUTPUT = Path("eval_output")


def _find_latest_run_dir() -> Path | None:
    """Find the most recent eval run directory."""
    if not EVAL_OUTPUT.exists():
        return None
    dirs = sorted(EVAL_OUTPUT.glob("multiturn_*"), reverse=True)
    return dirs[0] if dirs else None


def _load_report() -> dict | None:
    """Load report.json from the most recent run."""
    run_dir = _find_latest_run_dir()
    if not run_dir:
        return None
    report_path = run_dir / "report.json"
    if not report_path.exists():
        return None
    return json.loads(report_path.read_text())


@pytest.fixture(scope="module")
def report():
    """Load the eval report. Skip all tests if no report exists."""
    r = _load_report()
    if r is None:
        pytest.skip("No eval report found. Run `make eval-smoke` first.")
    return r


@pytest.fixture(scope="module")
def graduation_result(report):
    """Get the graduation_realistic result from the report."""
    for result in report["results"]:
        if result["name"] == "graduation_realistic":
            return result
    pytest.skip("No graduation_realistic scenario in report.")
    return None


# ── Tests ────────────────────────────────────────────────────────────────────


def test_no_scenario_errors(report):
    """All scenarios should complete without errors."""
    for result in report["results"]:
        assert "error" not in result, (
            f"Scenario {result['name']} errored: {result.get('error')}"
        )


def test_all_scenarios_passed(report):
    """All scenarios should have good average scores (>= 80%)."""
    for result in report["results"]:
        avg_score = result.get("avg_score", 0)
        assert avg_score >= 0.8, (
            f"Scenario {result['name']} scored {avg_score:.0%}, below 80% threshold"
        )


def test_entities_created(report):
    """Smoke test should produce entities (not an empty page)."""
    for result in report["results"]:
        assert result.get("final_entity_count", 0) > 0, (
            f"Scenario {result['name']} produced 0 entities"
        )


def test_cache_hits_on_turn_2_plus(graduation_result):
    """Turn 2+ should have cache_read > 0, proving prompt caching works.

    If this fails, likely causes:
    - Prompt fell below cache threshold
    - cache_control markers missing from system blocks or tools
    - Anthropic silently changed cache minimum thresholds
    """
    turns = graduation_result["turns"]
    if len(turns) < 2:
        pytest.skip("Need at least 2 turns to test caching")

    for turn in turns[1:]:
        cache_read = turn.get("cache_read", 0)
        assert cache_read > 0, (
            f"Turn {turn['turn']}: cache_read=0. "
            f"Caching may be broken. Check prompt token counts vs model thresholds."
        )


def test_tier_accuracy(graduation_result):
    """Tier routing should be accurate."""
    tier_accuracy = graduation_result.get("tier_accuracy", 0)
    assert tier_accuracy >= 0.8, (
        f"Tier accuracy {tier_accuracy:.0%} below 80% threshold"
    )


def test_reasonable_token_usage(graduation_result):
    """Token usage should be reasonable (not exploding)."""
    total_tokens = graduation_result.get("total_tokens", 0)
    num_turns = len(graduation_result.get("turns", []))
    if num_turns == 0:
        pytest.skip("No turns in result")

    avg_tokens_per_turn = total_tokens / num_turns
    # Expect < 500 tokens per turn on average for simple updates
    assert avg_tokens_per_turn < 500, (
        f"Average {avg_tokens_per_turn:.0f} tokens/turn exceeds 500 threshold"
    )


def test_reasonable_latency(graduation_result):
    """Latency should be reasonable."""
    total_time_ms = graduation_result.get("total_time_ms", 0)
    num_turns = len(graduation_result.get("turns", []))
    if num_turns == 0:
        pytest.skip("No turns in result")

    avg_time_per_turn = total_time_ms / num_turns
    # Expect < 5 seconds per turn on average
    assert avg_time_per_turn < 5000, (
        f"Average {avg_time_per_turn:.0f}ms/turn exceeds 5000ms threshold"
    )


def test_no_turn_errors(graduation_result):
    """No individual turns should have errors."""
    for turn in graduation_result["turns"]:
        assert "error" not in turn, (
            f"Turn {turn.get('turn', '?')} errored: {turn.get('error')}"
        )
