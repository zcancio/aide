"""
Tests for streaming orchestrator.

Integration tests - these test the classification and routing logic.
Full E2E tests with real API calls should be done manually.
"""

from __future__ import annotations

from backend.services.classifier import classify
from backend.services.prompt_builder import build_l2_prompt, build_l3_prompt, build_l4_prompt


def test_classification_logic_no_schema():
    """Test that empty snapshots route to L3."""
    snapshot = {"entities": {}}
    result = classify("plan a party", snapshot, has_schema=False)
    assert result.tier == "L3"
    assert result.reason == "no_schema"


def test_classification_logic_question():
    """Test that questions route to L4."""
    snapshot = {"entities": {"item_1": {"name": "Milk"}}}
    result = classify("how many items?", snapshot, has_schema=True)
    assert result.tier == "L4"
    assert result.reason == "pure_query"


def test_classification_logic_simple_update():
    """Test that simple updates route to L2."""
    snapshot = {"entities": {"item_1": {"name": "Milk"}}}
    result = classify("mark it done", snapshot, has_schema=True)
    assert result.tier == "L2"
    assert result.reason == "simple_update"


def test_prompt_building_l2():
    """Test L2 prompt includes snapshot."""
    snapshot = {"entities": {"item_1": {"name": "Test"}}}
    prompt = build_l2_prompt(snapshot)
    assert "Test" in prompt
    assert "L2 System Prompt" in prompt


def test_prompt_building_l3():
    """Test L3 prompt includes snapshot."""
    snapshot = {"entities": {"item_1": {"name": "Test"}}}
    prompt = build_l3_prompt(snapshot)
    assert "Test" in prompt
    # New prompt format uses "aide-prompt-l3-v3.0" instead of "L3 System Prompt"
    assert "aide-prompt-l3" in prompt


def test_prompt_building_l4():
    """Test L4 prompt includes snapshot."""
    snapshot = {"entities": {"item_1": {"name": "Test"}}}
    prompt = build_l4_prompt(snapshot)
    assert "Test" in prompt
    # New prompt format uses "aide-prompt-l4-v3.1" instead of "L4 System Prompt"
    assert "aide-prompt-l4" in prompt
