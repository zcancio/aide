#!/usr/bin/env python3
"""
Test that eval_multiturn uses the production kernel for applying events.

The eval system must apply LLM output through the same kernel that powers
the production app. This test verifies that apply_output_to_snapshot in
eval_multiturn produces identical results to the production kernel.
"""

import json
import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from engine.kernel.kernel import apply, empty_snapshot


def _build_snapshot_with_parent(parent_id: str, display: str) -> dict:
    """Build a snapshot with a parent entity using the kernel API."""
    snap = empty_snapshot()
    event = {"t": "entity.create", "id": parent_id, "parent": "root", "display": display, "p": {}}
    result = apply(snap, event)
    return result.snapshot


def test_eval_apply_matches_kernel():
    """
    eval_multiturn apply must produce same result as kernel.

    Given a JSONL event, applying it through both the eval system and the
    production kernel should yield identical entity state.
    """
    from evals.scripts.eval_multiturn import apply_output_to_snapshot

    # Build snapshot with parent entity using kernel API
    snap = _build_snapshot_with_parent("guests", "table")

    # Event to apply
    jsonl = '{"t": "entity.create", "id": "guest_1", "parent": "guests", "p": {"name": "Alice"}}'

    # Apply through eval system
    eval_result = apply_output_to_snapshot(snap, jsonl, "L3")

    # Apply through kernel
    event = {"t": "entity.create", "id": "guest_1", "parent": "guests", "p": {"name": "Alice"}}
    kernel_result = apply(snap, event)

    # Compare entity state
    assert eval_result["entities"]["guest_1"]["id"] == kernel_result.snapshot["entities"]["guest_1"]["id"]
    assert eval_result["entities"]["guest_1"]["parent"] == kernel_result.snapshot["entities"]["guest_1"]["parent"]
    assert eval_result["entities"]["guest_1"]["props"] == kernel_result.snapshot["entities"]["guest_1"]["props"]


def test_eval_apply_handles_multiple_events():
    """
    eval system must correctly apply a sequence of events through the kernel.
    """
    from evals.scripts.eval_multiturn import apply_output_to_snapshot

    # Build snapshot with parent entity using kernel API
    snap = _build_snapshot_with_parent("tasks", "checklist")

    # Multiple events in JSONL
    jsonl = """{"t": "entity.create", "id": "task_1", "parent": "tasks", "p": {"title": "Buy milk"}}
{"t": "entity.create", "id": "task_2", "parent": "tasks", "p": {"title": "Pay bills"}}
{"t": "entity.update", "ref": "task_1", "p": {"done": true}}"""

    # Apply through eval system
    eval_result = apply_output_to_snapshot(snap, jsonl, "L3")

    # Apply through kernel
    events = [
        {"t": "entity.create", "id": "task_1", "parent": "tasks", "p": {"title": "Buy milk"}},
        {"t": "entity.create", "id": "task_2", "parent": "tasks", "p": {"title": "Pay bills"}},
        {"t": "entity.update", "ref": "task_1", "p": {"done": True}},
    ]

    kernel_snap = json.loads(json.dumps(snap))
    for event in events:
        result = apply(kernel_snap, event)
        if result.accepted:
            kernel_snap = result.snapshot

    # Compare final state
    assert "task_1" in eval_result["entities"]
    assert "task_2" in eval_result["entities"]
    assert eval_result["entities"]["task_1"]["props"]["done"] is True
    assert eval_result["entities"]["task_1"]["props"]["title"] == kernel_snap["entities"]["task_1"]["props"]["title"]
    assert eval_result["entities"]["task_2"]["props"]["title"] == kernel_snap["entities"]["task_2"]["props"]["title"]


def test_eval_apply_skips_signals():
    """
    Signals (voice, escalate, clarify) don't mutate state and should be skipped.
    """
    from evals.scripts.eval_multiturn import apply_output_to_snapshot

    # Build snapshot with parent entity using kernel API
    snap = _build_snapshot_with_parent("page", "page")

    # Mix of mutations and signals
    jsonl = """{"t": "voice", "text": "Creating the task"}
{"t": "entity.create", "id": "task_1", "parent": "page", "p": {"title": "Do thing"}}
{"t": "escalate", "tier": "L3", "reason": "structural change"}"""

    # Apply through eval system
    eval_result = apply_output_to_snapshot(snap, jsonl, "L2")

    # Should have the entity but signals shouldn't break anything
    assert "task_1" in eval_result["entities"]
    assert eval_result["entities"]["task_1"]["props"]["title"] == "Do thing"
    # Snapshot structure should be clean (no signal artifacts)
    assert "voice" not in str(eval_result)


def test_eval_apply_l4_readonly():
    """
    L4 tier is read-only and should not mutate snapshot.
    """
    from evals.scripts.eval_multiturn import apply_output_to_snapshot

    # Build snapshot with parent entity using kernel API, then update props
    snap = empty_snapshot()
    create_result = apply(snap, {"t": "entity.create", "id": "page", "parent": "root", "display": "page", "p": {}})
    snap = create_result.snapshot
    update_result = apply(snap, {"t": "entity.update", "ref": "page", "p": {"title": "Test"}})
    snap = update_result.snapshot

    original_entity_count = len(snap["entities"])

    # L4 outputs plain text, not JSONL
    output = "The page has a title of 'Test'."

    eval_result = apply_output_to_snapshot(snap, output, "L4")

    # State should be unchanged
    assert len(eval_result["entities"]) == original_entity_count
    assert eval_result["entities"]["page"]["props"]["title"] == "Test"


if __name__ == "__main__":
    # Run tests
    test_eval_apply_matches_kernel()
    print("✓ test_eval_apply_matches_kernel")

    test_eval_apply_handles_multiple_events()
    print("✓ test_eval_apply_handles_multiple_events")

    test_eval_apply_skips_signals()
    print("✓ test_eval_apply_skips_signals")

    test_eval_apply_l4_readonly()
    print("✓ test_eval_apply_l4_readonly")

    print("\nAll tests passed!")
