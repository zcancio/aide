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
    assert "Primitive Schemas" in prompt
    assert "Current Snapshot" in prompt
    assert "L2 System Prompt" in prompt


def test_l3_prompt_includes_snapshot():
    """L3 prompt includes snapshot JSON."""
    snapshot = {"entities": {"item_1": {"name": "Milk"}}}
    prompt = build_l3_prompt(snapshot)

    assert "Milk" in prompt
    assert "Primitive Schemas" in prompt
    assert "Current Snapshot" in prompt
    assert "L3 System Prompt" in prompt


def test_l4_prompt_includes_snapshot():
    """L4 prompt includes snapshot JSON but not primitive schemas."""
    snapshot = {"entities": {"guest_1": {"name": "Sarah", "status": "attending"}}}
    prompt = build_l4_prompt(snapshot)

    assert "Sarah" in prompt
    assert "attending" in prompt
    assert "Current Snapshot" in prompt
    assert "L4 System Prompt" in prompt
    # L4 doesn't need primitive schemas since it doesn't emit events
    assert "Primitive Schemas" not in prompt


def test_messages_includes_conversation_tail():
    """Messages array includes last 10 turns plus current message."""
    conversation = [{"role": "user", "content": f"msg{i}"} for i in range(20)]
    messages = build_messages(conversation, "new message")

    # Should include last 10 + new = 11 total
    assert len(messages) == 11
    assert messages[-1]["content"] == "new message"
    assert messages[-1]["role"] == "user"
    # Should include msg10-msg19 (last 10)
    assert messages[0]["content"] == "msg10"
    assert messages[9]["content"] == "msg19"


def test_messages_with_short_conversation():
    """Messages array works with conversations shorter than 10 turns."""
    conversation = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    messages = build_messages(conversation, "how are you?")

    # Should include all 2 + new = 3 total
    assert len(messages) == 3
    assert messages[0]["content"] == "hello"
    assert messages[1]["content"] == "hi"
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
    l2_pos = prompt.find("L2 System Prompt")
    primitives_pos = prompt.find("## Primitive Schemas")
    snapshot_pos = prompt.find("## Current Snapshot")

    assert l2_pos < primitives_pos < snapshot_pos, "Prompt sections should be in order"


def test_l3_prompt_structure():
    """L3 prompt has expected sections in order."""
    snapshot = {"entities": {}}
    prompt = build_l3_prompt(snapshot)

    l3_pos = prompt.find("L3 System Prompt")
    primitives_pos = prompt.find("## Primitive Schemas")
    snapshot_pos = prompt.find("## Current Snapshot")

    assert l3_pos < primitives_pos < snapshot_pos, "Prompt sections should be in order"


def test_l4_prompt_structure():
    """L4 prompt has expected sections in order."""
    snapshot = {"entities": {}}
    prompt = build_l4_prompt(snapshot)

    l4_pos = prompt.find("L4 System Prompt")
    snapshot_pos = prompt.find("## Current Snapshot")

    assert l4_pos < snapshot_pos, "Prompt sections should be in order"
    # L4 should not have primitive schemas
    assert "## Primitive Schemas" not in prompt
