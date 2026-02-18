"""
AIde Reducer -- Idempotency Tests (v3 Unified Entity Model)

Tests that applying the same event twice does not double-apply changes.
In an event-sourced system, the event log contains each event once —
idempotency here means that a duplicate event is rejected cleanly (ALREADY_EXISTS,
NOT_FOUND, etc.) rather than silently mutating state twice.

Covers:
  - Duplicate schema.create is rejected
  - Duplicate entity.create is rejected
  - Duplicate block.set updates in place (block.set is idempotent by design)
  - entity.remove applied twice — second is rejected (NOT_FOUND)
  - schema.remove applied twice — second is rejected (NOT_FOUND)
  - meta.update with same values is a no-op (state unchanged)
  - style.set with same values is a no-op (state unchanged)
  - Replay of event log with deduplication equals replay without
"""

import json

import pytest

from engine.kernel.events import make_event
from engine.kernel.reducer import empty_state, reduce, replay

# ============================================================================
# Helpers
# ============================================================================


def snap_json(snap):
    return json.dumps(snap, sort_keys=True)


TASK_INTERFACE = "interface Task { title: string; done: boolean; }"


# ============================================================================
# 1. schema.create idempotency
# ============================================================================

class TestSchemaCreateIdempotency:
    def test_duplicate_schema_create_rejected(self):
        snap = empty_state()
        ev = make_event(seq=1, type="schema.create", payload={
            "id": "task",
            "interface": TASK_INTERFACE,
            "render_html": "<li>{{title}}</li>",
            "render_text": "{{title}}",
        })
        r1 = reduce(snap, ev)
        assert r1.applied

        # Apply same event again
        ev2 = make_event(seq=2, type="schema.create", payload={
            "id": "task",
            "interface": TASK_INTERFACE,
            "render_html": "<li>{{title}}</li>",
            "render_text": "{{title}}",
        })
        r2 = reduce(r1.snapshot, ev2)
        assert not r2.applied
        assert "ALREADY_EXISTS" in r2.error

    def test_duplicate_schema_create_does_not_change_state(self):
        snap = empty_state()
        ev = make_event(seq=1, type="schema.create", payload={
            "id": "task",
            "interface": TASK_INTERFACE,
            "render_html": "<li>{{title}}</li>",
            "render_text": "{{title}}",
        })
        r1 = reduce(snap, ev)

        ev2 = make_event(seq=2, type="schema.create", payload={
            "id": "task",
            "interface": TASK_INTERFACE,
            "render_html": "<li>{{title}}</li>",
            "render_text": "{{title}}",
        })
        r2 = reduce(r1.snapshot, ev2)

        # State must be identical before and after the rejected duplicate
        assert snap_json(r1.snapshot) == snap_json(r2.snapshot)


# ============================================================================
# 2. entity.create idempotency
# ============================================================================

class TestEntityCreateIdempotency:
    @pytest.fixture
    def state_with_schema(self):
        snap = empty_state()
        r = reduce(snap, make_event(seq=1, type="schema.create", payload={
            "id": "task",
            "interface": TASK_INTERFACE,
            "render_html": "<li>{{title}}</li>",
            "render_text": "{{title}}",
        }))
        assert r.applied
        return r.snapshot

    def test_duplicate_entity_create_rejected(self, state_with_schema):
        r1 = reduce(state_with_schema, make_event(seq=2, type="entity.create", payload={
            "id": "t1",
            "_schema": "task",
            "title": "Buy milk",
            "done": False,
        }))
        assert r1.applied

        r2 = reduce(r1.snapshot, make_event(seq=3, type="entity.create", payload={
            "id": "t1",
            "_schema": "task",
            "title": "Buy milk again",
            "done": True,
        }))
        assert not r2.applied
        assert "ALREADY_EXISTS" in r2.error

    def test_duplicate_entity_create_does_not_change_state(self, state_with_schema):
        r1 = reduce(state_with_schema, make_event(seq=2, type="entity.create", payload={
            "id": "t1",
            "_schema": "task",
            "title": "Original",
            "done": False,
        }))
        snap_after_first = snap_json(r1.snapshot)

        r2 = reduce(r1.snapshot, make_event(seq=3, type="entity.create", payload={
            "id": "t1",
            "_schema": "task",
            "title": "Duplicate attempt",
            "done": True,
        }))
        # State unchanged after rejected duplicate
        assert snap_json(r2.snapshot) == snap_after_first

        # Original title preserved
        assert r2.snapshot["entities"]["t1"]["title"] == "Original"
        assert r2.snapshot["entities"]["t1"]["done"] is False


# ============================================================================
# 3. block.set idempotency (block.set is upsert — same payload twice = same state)
# ============================================================================

class TestBlockSetIdempotency:
    def test_duplicate_block_set_is_safe(self):
        snap = empty_state()
        ev = make_event(seq=1, type="block.set", payload={
            "id": "b1",
            "type": "heading",
            "parent": "block_root",
            "text": "Hello",
        })
        r1 = reduce(snap, ev)
        assert r1.applied

        # Apply identical block.set again
        ev2 = make_event(seq=2, type="block.set", payload={
            "id": "b1",
            "type": "heading",
            "parent": "block_root",
            "text": "Hello",
        })
        r2 = reduce(r1.snapshot, ev2)
        assert r2.applied  # block.set is an upsert, always applies

        # State is the same
        assert snap_json(r1.snapshot) == snap_json(r2.snapshot)

    def test_block_set_with_different_text_updates_in_place(self):
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="block.set", payload={
            "id": "b1",
            "type": "heading",
            "parent": "block_root",
            "text": "Version 1",
        }))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="block.set", payload={
            "id": "b1",
            "type": "heading",
            "parent": "block_root",
            "text": "Version 2",
        }))
        assert r2.applied
        assert r2.snapshot["blocks"]["b1"]["text"] == "Version 2"
        # block_root should still only list b1 once
        assert r2.snapshot["blocks"]["block_root"]["children"].count("b1") == 1


# ============================================================================
# 4. entity.remove idempotency
# ============================================================================

class TestEntityRemoveIdempotency:
    @pytest.fixture
    def state_with_entity(self):
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="schema.create", payload={
            "id": "task",
            "interface": TASK_INTERFACE,
            "render_html": "<li>{{title}}</li>",
            "render_text": "{{title}}",
        }))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="entity.create", payload={
            "id": "t1",
            "_schema": "task",
            "title": "To remove",
            "done": False,
        }))
        assert r2.applied
        return r2.snapshot

    def test_second_entity_remove_rejected(self, state_with_entity):
        r1 = reduce(state_with_entity, make_event(seq=3, type="entity.remove", payload={"id": "t1"}))
        assert r1.applied
        assert r1.snapshot["entities"]["t1"]["_removed"] is True

        r2 = reduce(r1.snapshot, make_event(seq=4, type="entity.remove", payload={"id": "t1"}))
        assert not r2.applied
        assert "NOT_FOUND" in r2.error

    def test_second_entity_remove_does_not_change_state(self, state_with_entity):
        r1 = reduce(state_with_entity, make_event(seq=3, type="entity.remove", payload={"id": "t1"}))
        snap_after_first_remove = snap_json(r1.snapshot)

        r2 = reduce(r1.snapshot, make_event(seq=4, type="entity.remove", payload={"id": "t1"}))
        assert snap_json(r2.snapshot) == snap_after_first_remove


# ============================================================================
# 5. schema.remove idempotency
# ============================================================================

class TestSchemaRemoveIdempotency:
    def test_second_schema_remove_rejected(self):
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="schema.create", payload={
            "id": "temp",
            "interface": "interface Temp { x: string; }",
            "render_html": "<span>{{x}}</span>",
            "render_text": "{{x}}",
        }))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="schema.remove", payload={"id": "temp"}))
        assert r2.applied

        r3 = reduce(r2.snapshot, make_event(seq=3, type="schema.remove", payload={"id": "temp"}))
        assert not r3.applied
        assert "NOT_FOUND" in r3.error

    def test_second_schema_remove_does_not_change_state(self):
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="schema.create", payload={
            "id": "temp",
            "interface": "interface Temp { x: string; }",
            "render_html": "<span>{{x}}</span>",
            "render_text": "{{x}}",
        }))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="schema.remove", payload={"id": "temp"}))
        snap_after_remove = snap_json(r2.snapshot)

        r3 = reduce(r2.snapshot, make_event(seq=3, type="schema.remove", payload={"id": "temp"}))
        assert snap_json(r3.snapshot) == snap_after_remove


# ============================================================================
# 6. meta.update with same values
# ============================================================================

class TestMetaUpdateIdempotency:
    def test_same_meta_update_twice_is_idempotent(self):
        snap = empty_state()
        payload = {"title": "My Budget", "visibility": "private"}
        r1 = reduce(snap, make_event(seq=1, type="meta.update", payload=payload))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="meta.update", payload=payload))

        # Both apply
        assert r1.applied
        assert r2.applied
        # State identical
        assert snap_json(r1.snapshot) == snap_json(r2.snapshot)


# ============================================================================
# 7. style.set with same values
# ============================================================================

class TestStyleSetIdempotency:
    def test_same_style_set_twice_is_idempotent(self):
        snap = empty_state()
        payload = {"primary_color": "#ff0000", "font_family": "Arial"}
        r1 = reduce(snap, make_event(seq=1, type="style.set", payload=payload))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="style.set", payload=payload))

        assert r1.applied
        assert r2.applied
        assert snap_json(r1.snapshot) == snap_json(r2.snapshot)


# ============================================================================
# 8. Replay of deduplicated event log equals replay without duplicates
# ============================================================================

class TestEventLogDeduplication:
    def test_deduplicated_replay_matches_original(self):
        """Removing exact duplicate events from a log produces the same final state."""
        events_with_dup = [
            make_event(seq=1, type="schema.create", payload={
                "id": "task",
                "interface": TASK_INTERFACE,
                "render_html": "<li>{{title}}</li>",
                "render_text": "{{title}}",
            }),
            make_event(seq=2, type="entity.create", payload={
                "id": "t1",
                "_schema": "task",
                "title": "Task One",
                "done": False,
            }),
            # Duplicate of seq=2 — will be rejected by reducer
            make_event(seq=3, type="entity.create", payload={
                "id": "t1",
                "_schema": "task",
                "title": "Task One",
                "done": False,
            }),
            make_event(seq=4, type="entity.update", payload={"id": "t1", "done": True}),
        ]
        events_clean = [events_with_dup[0], events_with_dup[1], events_with_dup[3]]

        snap_dup = replay(events_with_dup)
        snap_clean = replay(events_clean)

        # The rejected duplicate event doesn't change state, so results match
        assert snap_json(snap_dup) == snap_json(snap_clean)
