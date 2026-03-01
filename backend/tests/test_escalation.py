"""Tests for escalation detection logic."""

from backend.services.escalation import needs_escalation

# ── Voice signal detection ───────────────────────────────────────────────────


def test_detects_needs_new_section():
    result = {
        "text_blocks": [{"text": "This needs a new section structure."}],
        "tool_calls": [],
    }
    assert needs_escalation(result) is True


def test_detects_needs_structural():
    result = {
        "text_blocks": [{"text": "This needs structural changes."}],
        "tool_calls": [],
    }
    assert needs_escalation(result) is True


def test_detects_escalation_keyword():
    result = {
        "text_blocks": [{"text": "I'll escalate this to handle the new schema."}],
        "tool_calls": [],
    }
    assert needs_escalation(result) is True


def test_ignores_normal_voice():
    result = {
        "text_blocks": [{"text": "Budget: $1,350."}],
        "tool_calls": [],
    }
    assert needs_escalation(result) is False


def test_ignores_empty_text():
    result = {
        "text_blocks": [],
        "tool_calls": [],
    }
    assert needs_escalation(result) is False


# ── Structural creation detection ────────────────────────────────────────────


def test_detects_page_creation():
    """L3 creating a page entity is an escalation signal — that's L4's job."""
    result = {
        "text_blocks": [],
        "tool_calls": [
            {"name": "mutate_entity", "input": {"action": "create", "id": "page", "display": "page"}},
        ],
    }
    assert needs_escalation(result) is True


def test_detects_section_creation():
    result = {
        "text_blocks": [],
        "tool_calls": [
            {"name": "mutate_entity", "input": {"action": "create", "id": "guests", "display": "section"}},
        ],
    }
    assert needs_escalation(result) is True


def test_detects_table_creation():
    result = {
        "text_blocks": [],
        "tool_calls": [
            {"name": "mutate_entity", "input": {"action": "create", "id": "roster", "display": "table"}},
        ],
    }
    assert needs_escalation(result) is True


def test_detects_grid_creation():
    result = {
        "text_blocks": [],
        "tool_calls": [
            {"name": "mutate_entity", "input": {"action": "create", "id": "board", "display": "grid"}},
        ],
    }
    assert needs_escalation(result) is True


def test_ignores_card_creation():
    """Creating a card or list item is normal L3 work, not escalation."""
    result = {
        "text_blocks": [],
        "tool_calls": [
            {"name": "mutate_entity", "input": {"action": "create", "id": "guest_mike", "display": "card"}},
        ],
    }
    assert needs_escalation(result) is False


def test_ignores_entity_updates():
    """Updates to existing entities are normal L3 work."""
    result = {
        "text_blocks": [],
        "tool_calls": [
            {"name": "mutate_entity", "input": {"action": "update", "ref": "guests", "props": {"status": "active"}}},
        ],
    }
    assert needs_escalation(result) is False


def test_ignores_voice_tool_calls():
    """Voice tool calls are never an escalation signal."""
    result = {
        "text_blocks": [],
        "tool_calls": [
            {"name": "voice", "input": {"text": "3 guests added."}},
        ],
    }
    assert needs_escalation(result) is False


def test_voice_signal_with_tool_calls():
    """Voice escalation signal should trigger even when tool_calls are present,
    because the voice text is what the LLM chose to communicate."""
    result = {
        "text_blocks": [{"text": "This needs a new section structure."}],
        "tool_calls": [
            {"name": "mutate_entity", "input": {"action": "update", "ref": "x", "props": {}}},
        ],
    }
    assert needs_escalation(result) is True


def test_handles_string_text_blocks():
    """text_blocks may contain plain strings instead of dicts."""
    result = {
        "text_blocks": ["This needs a new section structure."],
        "tool_calls": [],
    }
    assert needs_escalation(result) is True


def test_case_insensitive():
    result = {
        "text_blocks": [{"text": "NEEDS A NEW SECTION STRUCTURE"}],
        "tool_calls": [],
    }
    assert needs_escalation(result) is True
