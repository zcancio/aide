"""
Eval smoke test — runs after eval-smoke Makefile target.

Reads the most recent report.json from eval_output/ and asserts:
1. No scenario errors
2. Cache hits on turn 2+ (proves prompt caching works)
3. Total cost under threshold (catches prompt bloat or pricing bugs)

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


def _load_golden(scenario_id: str) -> dict | None:
    """Load per-scenario golden file from the most recent run."""
    run_dir = _find_latest_run_dir()
    if not run_dir:
        return None
    golden_path = run_dir / f"{scenario_id}.json"
    if not golden_path.exists():
        return None
    return json.loads(golden_path.read_text())


@pytest.fixture(scope="module")
def report():
    """Load the eval report. Skip all tests if no report exists."""
    r = _load_report()
    if r is None:
        pytest.skip("No eval report found. Run `make eval-smoke` first.")
    return r


@pytest.fixture(scope="module")
def golden(report):
    """Load the graduation_realistic golden file."""
    g = _load_golden("graduation_realistic")
    if g is None:
        pytest.skip("No graduation_realistic golden file found.")
    return g


# ── Tests ────────────────────────────────────────────────────────────────────


def test_no_scenario_errors(report):
    """All scenarios should complete without errors."""
    for result in report["results"]:
        assert "error" not in result, (
            f"Scenario {result['scenario_id']} errored: {result.get('error')}"
        )


def test_all_scenarios_passed(report):
    """All validation checks should pass."""
    for result in report["results"]:
        assert result.get("all_passed", False), (
            f"Scenario {result['scenario_id']} had {result.get('total_issues', '?')} issues"
        )


def test_entities_created(report):
    """Smoke test should produce entities (not an empty page)."""
    for result in report["results"]:
        assert result.get("entity_count", 0) > 0, (
            f"Scenario {result['scenario_id']} produced 0 entities"
        )


def test_cache_hits_on_turn_2_plus(golden):
    """Turn 2+ should have cache_read > 0, proving prompt caching works.

    If this fails, likely causes:
    - L4 prompt fell below 4,096-token Opus cache threshold
    - L3 prompt fell below 1,024-token Sonnet cache threshold
    - cache_control markers missing from system blocks or tools
    - Anthropic silently changed cache minimum thresholds
    """
    turns = golden["turns"]
    if len(turns) < 2:
        pytest.skip("Need at least 2 turns to test caching")

    for turn in turns[1:]:
        usage = turn["usage"]
        cache_read = usage.get("cache_read", 0)
        assert cache_read > 0, (
            f"Turn {turn['turn']} ({turn['tier']}): cache_read=0. "
            f"Caching is broken. Check prompt token counts vs model thresholds. "
            f"Full usage: {usage}"
        )


def test_cost_under_threshold(golden):
    """3-turn smoke test should cost < $0.08.

    Typical cost: ~$0.03-0.05 for 3 turns with caching.
    If this fails: prompt bloat, cache miss, or pricing change.

    Pricing (per MTok):
    - L3 Sonnet: $3 in / $15 out / $0.30 cache_read / $3.75 cache_write
    - L4 Opus:   $5 in / $25 out / $0.50 cache_read / $6.25 cache_write
    """
    total = 0.0
    for turn in golden["turns"]:
        usage = turn["usage"]
        tier = turn["tier"].split("->")[0]  # handle "L3->L4->L3"

        if tier == "L4":
            p_in, p_out, p_cr, p_cw = 5, 25, 0.5, 6.25
        else:
            p_in, p_out, p_cr, p_cw = 3, 15, 0.3, 3.75

        total += usage.get("input_tokens", 0) * p_in / 1e6
        total += usage.get("output_tokens", 0) * p_out / 1e6
        total += usage.get("cache_read", 0) * p_cr / 1e6
        total += usage.get("cache_creation", 0) * p_cw / 1e6

    assert total < 0.08, (
        f"3-turn eval cost ${total:.4f}, exceeds $0.08 threshold. "
        f"Check for cache misses or prompt bloat."
    )


def test_tool_calls_produced(golden):
    """Each turn should produce at least one tool call (even if just voice)."""
    for turn in golden["turns"]:
        tool_calls = turn.get("tool_calls", [])
        text_blocks = turn.get("text_blocks", [])
        # Either tool calls or text blocks should exist
        assert len(tool_calls) > 0 or len(text_blocks) > 0, (
            f"Turn {turn['turn']}: no tool_calls and no text_blocks. "
            f"LLM produced empty response."
        )


def test_first_turn_creates_structure(golden):
    """Turn 1 (first message) should create page + section entities."""
    turn_1 = golden["turns"][0]
    tool_calls = turn_1.get("tool_calls", [])

    # Should have at least a page creation
    creates = [
        tc
        for tc in tool_calls
        if tc.get("name") == "mutate_entity"
        and tc.get("input", {}).get("action") == "create"
    ]
    assert len(creates) >= 2, (
        f"Turn 1 created {len(creates)} entities, expected at least 2 "
        f"(page + at least one section). Tool calls: {[tc.get('input', {}).get('id') for tc in creates]}"
    )


def test_voice_present_every_turn(golden):
    """Every turn should have voice output (the user must see a response)."""
    for turn in golden["turns"]:
        text_blocks = turn.get("text_blocks", [])
        has_voice = any(
            (b.get("text", "").strip() if isinstance(b, dict) else b.strip())
            for b in text_blocks
        )
        assert has_voice, (
            f"Turn {turn['turn']}: no voice output. "
            f"User would see no response. text_blocks: {text_blocks}"
        )
