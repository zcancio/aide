"""
Tests for prompt builder.

Validates prompt assembly for different tiers.
"""

from __future__ import annotations

import json

from backend.services.prompt_builder import build_l2_prompt, build_l3_prompt, build_l4_prompt, build_messages


def test_l2_prompt_includes_snapshot():
    """L2 prompt includes snapshot JSON."""
    snapshot = {"entities": {"page": {"title": "Test"}}}
    prompt = build_l2_prompt(snapshot)

    assert "Test" in prompt
    assert "Current Snapshot" in prompt
    assert "L2 (Compiler)" in prompt
    assert "aide-prompt-v3.1" in prompt


def test_l3_prompt_includes_snapshot():
    """L3 prompt includes snapshot JSON."""
    snapshot = {"entities": {"item_1": {"name": "Milk"}}}
    prompt = build_l3_prompt(snapshot)

    assert "Milk" in prompt
    assert "Current Snapshot" in prompt
    assert "L3 (Architect)" in prompt
    assert "aide-prompt-v3.1" in prompt


def test_l4_prompt_includes_snapshot():
    """L4 prompt includes snapshot JSON and shared context."""
    snapshot = {"entities": {"guest_1": {"name": "Sarah", "status": "attending"}}}
    prompt = build_l4_prompt(snapshot)

    assert "Sarah" in prompt
    assert "attending" in prompt
    assert "Current Snapshot" in prompt
    assert "L4 (Analyst)" in prompt
    assert "aide-prompt-v3.1" in prompt


def test_messages_includes_conversation_tail():
    """Messages array includes last 5 turns plus current message by default."""
    conversation = [{"role": "user", "content": f"msg{i}"} for i in range(20)]
    messages = build_messages(conversation, "new message")

    # Should include last 5 + new = 6 total
    assert len(messages) == 6
    assert messages[-1]["content"] == "new message"
    assert messages[-1]["role"] == "user"
    # Should include msg15-msg19 (last 5)
    assert messages[0]["content"] == "msg15"
    # Last tail message (msg19) has cache control
    assert messages[4]["content"][0]["text"] == "msg19"
    assert messages[4]["content"][0]["cache_control"]["type"] == "ephemeral"


def test_messages_with_short_conversation():
    """Messages array works with conversations shorter than 5 turns."""
    conversation = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    messages = build_messages(conversation, "how are you?")

    # Should include all 2 + new = 3 total
    assert len(messages) == 3
    assert messages[0]["content"] == "hello"
    # Last tail message has cache control
    assert messages[1]["content"][0]["text"] == "hi"
    assert messages[1]["content"][0]["cache_control"]["type"] == "ephemeral"
    assert messages[2]["content"] == "how are you?"


def test_messages_with_empty_conversation():
    """Messages array works with empty conversation."""
    messages = build_messages([], "first message")

    assert len(messages) == 1
    assert messages[0]["content"] == "first message"
    assert messages[0]["role"] == "user"


def test_snapshot_json_is_valid():
    """Snapshot JSON in prompt is valid and parseable."""
    snapshot = {
        "entities": {
            "item_1": {"name": "Milk", "checked": False},
            "item_2": {"name": "Eggs", "checked": True},
        },
        "meta": {"title": "Grocery List"},
    }

    prompt = build_l2_prompt(snapshot)

    # Find the snapshot JSON block (not the primitive schemas block)
    snapshot_marker = "## Current Snapshot"
    snapshot_start = prompt.find(snapshot_marker)
    assert snapshot_start > 0, "Should have Current Snapshot section"

    # Extract JSON from the snapshot section
    start = prompt.find("```json\n", snapshot_start) + 8
    end = prompt.find("\n```", start)
    snapshot_json = prompt[start:end]

    # Should be valid JSON
    parsed = json.loads(snapshot_json)
    assert parsed["entities"]["item_1"]["name"] == "Milk"
    assert parsed["meta"]["title"] == "Grocery List"


def test_l2_prompt_structure():
    """L2 prompt has expected sections in order."""
    snapshot = {"entities": {}}
    prompt = build_l2_prompt(snapshot)

    # Check section ordering
    prefix_pos = prompt.find("aide-prompt-v3.1")
    l2_pos = prompt.find("L2 (Compiler)")
    snapshot_pos = prompt.find("## Current Snapshot")

    assert prefix_pos < l2_pos < snapshot_pos, "Prompt sections should be in order"


def test_l3_prompt_structure():
    """L3 prompt has expected sections in order."""
    snapshot = {"entities": {}}
    prompt = build_l3_prompt(snapshot)

    prefix_pos = prompt.find("aide-prompt-v3.1")
    l3_pos = prompt.find("L3 (Architect)")
    snapshot_pos = prompt.find("## Current Snapshot")

    assert prefix_pos < l3_pos < snapshot_pos, "Prompt sections should be in order"


def test_l4_prompt_structure():
    """L4 prompt has expected sections in order."""
    snapshot = {"entities": {}}
    prompt = build_l4_prompt(snapshot)

    prefix_pos = prompt.find("aide-prompt-v3.1")
    l4_pos = prompt.find("L4 (Analyst)")
    snapshot_pos = prompt.find("## Current Snapshot")

    assert prefix_pos < l4_pos < snapshot_pos, "Prompt sections should be in order"
