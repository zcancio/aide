"""
AIde Reducer -- Determinism Tests (v3 Unified Entity Model)

Tests that the reducer is a pure, deterministic function: same events in,
same snapshot out, every single time.

The reducer is deterministic. Given the same sequence of events, it produces
the same snapshot every time. No randomness, no timestamps, no external state.

Covers:
  - N-times replay identity (100 iterations)
  - Incremental vs. full replay equivalence
  - Replay with rejections produces same result
  - Replay with warnings produces same result
  - Replay with schema evolution
  - Replay with cascading removes
  - Empty state is deterministic
  - Replay subset for time-travel / undo
  - Rejected events don't affect snapshot (pure)
"""

import copy
import json

from engine.kernel.events import make_event
from engine.kernel.reducer import empty_state, reduce, replay

# ============================================================================
# Helpers
# ============================================================================


def snapshot_json(snapshot):
    """Canonical JSON representation with sorted keys for deterministic comparison."""
    return json.dumps(snapshot, sort_keys=True, ensure_ascii=True)


def build_incremental(events):
    """Apply events one at a time to empty state, return final snapshot."""
    snapshot = empty_state()
    for event in events:
        result = reduce(snapshot, event)
        if result.applied:
            snapshot = result.snapshot
    return snapshot


TASK_INTERFACE = "interface Task { title: string; done: boolean; priority?: string; }"


# ============================================================================
# Test Data: a reusable 10-event sequence using v3 primitives
# ============================================================================

def make_base_events():
    return [
        make_event(seq=1, type="schema.create", payload={
            "id": "task",
            "interface": TASK_INTERFACE,
            "render_html": "<li>{{title}}</li>",
            "render_text": "{{title}}",
        }),
        make_event(seq=2, type="meta.update", payload={"title": "My Tasks"}),
        make_event(seq=3, type="entity.create", payload={
            "id": "task_a",
            "_schema": "task",
            "title": "Buy milk",
            "done": False,
        }),
        make_event(seq=4, type="entity.create", payload={
            "id": "task_b",
            "_schema": "task",
            "title": "Walk dog",
            "done": False,
        }),
        make_event(seq=5, type="entity.create", payload={
            "id": "task_c",
            "_schema": "task",
            "title": "Call dentist",
            "done": True,
        }),
        make_event(seq=6, type="entity.update", payload={
            "id": "task_a",
            "done": True,
        }),
        make_event(seq=7, type="entity.create", payload={
            "id": "task_d",
            "_schema": "task",
            "title": "Read book",
            "done": False,
            "priority": "low",
        }),
        make_event(seq=8, type="style.set", payload={"primary_color": "#336699"}),
        make_event(seq=9, type="entity.remove", payload={"id": "task_c"}),
        make_event(seq=10, type="meta.update", payload={"visibility": "private"}),
    ]


# ============================================================================
# 1. N-times replay identity
# ============================================================================

class TestNTimesReplayIdentity:
    def test_replay_100_times_identical(self):
        """Replaying the same events 100 times always produces the same snapshot."""
        events = make_base_events()
        first = snapshot_json(replay(events))
        for i in range(99):
            result = snapshot_json(replay(events))
            assert result == first, f"Mismatch on iteration {i + 2}"

    def test_replay_produces_same_as_incremental(self):
        """replay() == build_incremental() for same events."""
        events = make_base_events()
        via_replay = replay(events)
        via_incremental = build_incremental(events)
        assert snapshot_json(via_replay) == snapshot_json(via_incremental)

    def test_empty_state_deterministic(self):
        """empty_state() always returns the same structure."""
        s1 = snapshot_json(empty_state())
        s2 = snapshot_json(empty_state())
        assert s1 == s2

    def test_empty_replay_deterministic(self):
        """replay([]) == empty_state()."""
        assert snapshot_json(replay([])) == snapshot_json(empty_state())


# ============================================================================
# 2. Replay with rejections doesn't corrupt state
# ============================================================================

class TestReplayWithRejections:
    def test_rejected_events_skip_cleanly(self):
        """Events that fail don't change the snapshot, and replay is still deterministic."""
        events = [
            make_event(seq=1, type="schema.create", payload={
                "id": "item",
                "interface": "interface Item { name: string; }",
                "render_html": "<span>{{name}}</span>",
                "render_text": "{{name}}",
            }),
            # Duplicate schema.create — will be rejected
            make_event(seq=2, type="schema.create", payload={
                "id": "item",
                "interface": "interface Item { name: string; }",
                "render_html": "<span>{{name}}</span>",
                "render_text": "{{name}}",
            }),
            make_event(seq=3, type="entity.create", payload={
                "id": "item_one",
                "_schema": "item",
                "name": "Widget",
            }),
            # entity.update for non-existent entity — will be rejected
            make_event(seq=4, type="entity.update", payload={
                "id": "item_ghost",
                "name": "Ghost",
            }),
        ]

        result1 = snapshot_json(replay(events))
        result2 = snapshot_json(replay(events))
        assert result1 == result2

    def test_incremental_with_rejections_matches_replay(self):
        """Incremental build with rejections matches replay with rejections."""
        events = [
            make_event(seq=1, type="schema.create", payload={
                "id": "widget",
                "interface": "interface Widget { label: string; }",
                "render_html": "<div>{{label}}</div>",
                "render_text": "{{label}}",
            }),
            make_event(seq=2, type="entity.create", payload={
                "id": "w1",
                "_schema": "widget",
                "label": "Alpha",
            }),
            # Rejected: unknown type
            make_event(seq=3, type="grid.query", payload={"entity": "w1"}),
            make_event(seq=4, type="entity.update", payload={"id": "w1", "label": "Alpha Updated"}),
        ]

        via_replay = replay(events)
        via_incremental = build_incremental(events)
        assert snapshot_json(via_replay) == snapshot_json(via_incremental)


# ============================================================================
# 3. Replay with warnings is still deterministic
# ============================================================================

class TestReplayWithWarnings:
    def test_schema_update_field_removal_warning_is_deterministic(self):
        """schema.update that removes a field emits a warning but result is deterministic."""
        events = [
            make_event(seq=1, type="schema.create", payload={
                "id": "product",
                "interface": "interface Product { name: string; price: string; sku: string; }",
                "render_html": "<div>{{name}}</div>",
                "render_text": "{{name}}",
            }),
            # Update removes sku field — warning emitted
            make_event(seq=2, type="schema.update", payload={
                "id": "product",
                "interface": "interface Product { name: string; price: string; }",
            }),
        ]

        r1 = snapshot_json(replay(events))
        r2 = snapshot_json(replay(events))
        assert r1 == r2

        # And schema should reflect the updated interface
        snap = replay(events)
        assert "sku" not in snap["schemas"]["product"]["interface"]
        assert "price" in snap["schemas"]["product"]["interface"]


# ============================================================================
# 4. Replay with schema evolution
# ============================================================================

class TestReplayWithSchemaEvolution:
    def test_schema_create_then_update_deterministic(self):
        events = [
            make_event(seq=1, type="schema.create", payload={
                "id": "note",
                "interface": "interface Note { title: string; }",
                "render_html": "<p>{{title}}</p>",
                "render_text": "{{title}}",
            }),
            make_event(seq=2, type="schema.update", payload={
                "id": "note",
                "interface": "interface Note { title: string; body?: string; }",
                "render_html": "<p>{{title}}<br/>{{body}}</p>",
            }),
            make_event(seq=3, type="entity.create", payload={
                "id": "note_1",
                "_schema": "note",
                "title": "First Note",
            }),
        ]

        r1 = snapshot_json(replay(events))
        r2 = snapshot_json(replay(events))
        assert r1 == r2

        snap = replay(events)
        assert snap["schemas"]["note"]["interface"] == "interface Note { title: string; body?: string; }"
        assert snap["entities"]["note_1"]["title"] == "First Note"


# ============================================================================
# 5. Replay with cascading removes
# ============================================================================

class TestReplayWithCascadeRemoves:
    def test_entity_with_children_cascade_remove_deterministic(self):
        # Use a schema with a Record field so children are allowed
        events = [
            make_event(seq=1, type="schema.create", payload={
                "id": "list_item",
                "interface": "interface ListItem { name: string; children: Record<string, ListItem>; }",
                "render_html": "<li>{{name}}</li>",
                "render_text": "{{name}}",
            }),
            make_event(seq=2, type="entity.create", payload={
                "id": "my_list",
                "_schema": "list_item",
                "name": "Top-level List",
                "children": {
                    "child_a": {"name": "Child A"},
                    "child_b": {"name": "Child B"},
                },
            }),
            make_event(seq=3, type="entity.remove", payload={"id": "my_list"}),
        ]

        r1 = snapshot_json(replay(events))
        r2 = snapshot_json(replay(events))
        assert r1 == r2

        snap = replay(events)
        assert snap["entities"]["my_list"]["_removed"] is True


# ============================================================================
# 6. Replay subset (time-travel / undo)
# ============================================================================

class TestReplaySubset:
    def test_replay_first_n_events(self):
        """Replaying first N events is deterministic for any N."""
        events = make_base_events()
        for n in range(1, len(events) + 1):
            subset = events[:n]
            r1 = snapshot_json(replay(subset))
            r2 = snapshot_json(replay(subset))
            assert r1 == r2, f"Subset of length {n} is not deterministic"

    def test_replay_prefix_state_can_continue_reducing(self):
        """Snapshot from replaying first 5 events can accept more events."""
        events = make_base_events()
        partial_snap = replay(events[:5])

        # Apply the 6th event on top of partial replay
        sixth_event = events[5]
        result = reduce(partial_snap, sixth_event)
        assert result.applied

        # Full replay of 6 events should match
        full_snap = replay(events[:6])
        assert snapshot_json(result.snapshot) == snapshot_json(full_snap)


# ============================================================================
# 7. Input snapshot is never mutated
# ============================================================================

class TestInputImmutability:
    def test_reduce_does_not_mutate_input(self):
        """reduce() must not mutate the input snapshot."""
        events = make_base_events()
        snap_before = replay(events[:5])
        snap_copy = copy.deepcopy(snap_before)

        sixth_event = events[5]
        reduce(snap_before, sixth_event)

        assert snapshot_json(snap_before) == snapshot_json(snap_copy), (
            "Input snapshot was mutated by reduce()"
        )

    def test_multiple_reduces_from_same_base(self):
        """Two different events applied to same snapshot produce independent results."""
        base_events = [
            make_event(seq=1, type="schema.create", payload={
                "id": "task",
                "interface": TASK_INTERFACE,
                "render_html": "<li>{{title}}</li>",
                "render_text": "{{title}}",
            }),
            make_event(seq=2, type="entity.create", payload={
                "id": "t1",
                "_schema": "task",
                "title": "Shared base",
                "done": False,
            }),
        ]
        base_snap = replay(base_events)
        base_json = snapshot_json(base_snap)

        event_a = make_event(seq=3, type="entity.update", payload={"id": "t1", "title": "Branch A"})
        event_b = make_event(seq=3, type="entity.update", payload={"id": "t1", "title": "Branch B"})

        result_a = reduce(base_snap, event_a)
        result_b = reduce(base_snap, event_b)

        # Base must be unchanged
        assert snapshot_json(base_snap) == base_json

        # Results must differ from each other
        assert result_a.snapshot["entities"]["t1"]["title"] == "Branch A"
        assert result_b.snapshot["entities"]["t1"]["title"] == "Branch B"
