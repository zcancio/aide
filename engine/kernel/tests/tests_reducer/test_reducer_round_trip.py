"""
AIde Reducer -- Round-Trip Tests (v3 Unified Entity Model)

Tests that snapshots survive JSON serialization and deserialization without
loss of information, and that deserialized snapshots continue to function
correctly with the reducer.

Covers:
  - Empty state round-trip
  - Snapshot round-trip after each primitive category
  - Event log round-trip (serialize events, deserialize, replay → same snapshot)
  - Field type fidelity (strings, ints, floats, bools, nulls)
  - Nested structures survive round-trip
  - Continue reducing after deserialization (the deserialized snapshot is live)
  - Large snapshot round-trip (~100 entities)
"""

import json

import pytest

from engine.kernel.events import make_event
from engine.kernel.reducer import empty_state, reduce, replay
from engine.kernel.types import Event

# ============================================================================
# Helpers
# ============================================================================


def round_trip(obj):
    """Serialize to JSON with sorted keys, then deserialize back."""
    return json.loads(json.dumps(obj, sort_keys=True, ensure_ascii=True))


def assert_round_trip_equal(snapshot, msg=""):
    rt = round_trip(snapshot)
    a = json.dumps(snapshot, sort_keys=True)
    b = json.dumps(rt, sort_keys=True)
    assert a == b, msg or "Snapshot changed through round-trip"


TASK_INTERFACE = "interface Task { title: string; done: boolean; priority?: string; }"


# ============================================================================
# 1. Empty state round-trip
# ============================================================================

class TestEmptyStateRoundTrip:
    def test_empty_state_round_trips(self):
        snap = empty_state()
        assert_round_trip_equal(snap, "empty_state() did not survive round-trip")

    def test_empty_state_structure_preserved(self):
        rt = round_trip(empty_state())
        assert rt["version"] == 3
        assert rt["meta"] == {}
        assert rt["schemas"] == {}
        assert rt["entities"] == {}
        assert "block_root" in rt["blocks"]
        assert rt["styles"] == {}
        assert rt["annotations"] == []


# ============================================================================
# 2. Snapshot round-trip after schema operations
# ============================================================================

class TestSchemaRoundTrip:
    def test_schema_create_round_trips(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="schema.create", payload={
            "id": "task",
            "interface": TASK_INTERFACE,
            "render_html": "<li class='task'>{{title}}</li>",
            "render_text": "{{#done}}[x]{{/done}}{{^done}}[ ]{{/done}} {{title}}",
            "styles": ".task { padding: 8px; }",
        }))
        assert result.applied
        assert_round_trip_equal(result.snapshot)

    def test_schema_update_round_trips(self):
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="schema.create", payload={
            "id": "task",
            "interface": TASK_INTERFACE,
            "render_html": "<li>{{title}}</li>",
            "render_text": "{{title}}",
        }))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="schema.update", payload={
            "id": "task",
            "render_html": "<li class='updated'>{{title}}</li>",
        }))
        assert r2.applied
        assert_round_trip_equal(r2.snapshot)

    def test_schema_remove_round_trips(self):
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="schema.create", payload={
            "id": "temp",
            "interface": "interface Temp { x: string; }",
            "render_html": "<span>{{x}}</span>",
            "render_text": "{{x}}",
        }))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="schema.remove", payload={"id": "temp"}))
        assert r2.applied
        assert_round_trip_equal(r2.snapshot)


# ============================================================================
# 3. Snapshot round-trip after entity operations
# ============================================================================

class TestEntityRoundTrip:
    @pytest.fixture
    def state_with_schema(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="schema.create", payload={
            "id": "task",
            "interface": TASK_INTERFACE,
            "render_html": "<li>{{title}}</li>",
            "render_text": "{{title}}",
        }))
        assert result.applied
        return result.snapshot

    def test_entity_create_round_trips(self, state_with_schema):
        result = reduce(state_with_schema, make_event(seq=2, type="entity.create", payload={
            "id": "t1",
            "_schema": "task",
            "title": "Buy milk",
            "done": False,
        }))
        assert result.applied
        assert_round_trip_equal(result.snapshot)

    def test_entity_update_round_trips(self, state_with_schema):
        r1 = reduce(state_with_schema, make_event(seq=2, type="entity.create", payload={
            "id": "t1",
            "_schema": "task",
            "title": "Buy milk",
            "done": False,
        }))
        r2 = reduce(r1.snapshot, make_event(seq=3, type="entity.update", payload={
            "id": "t1",
            "done": True,
            "priority": "high",
        }))
        assert r2.applied
        assert_round_trip_equal(r2.snapshot)

    def test_entity_remove_round_trips(self, state_with_schema):
        r1 = reduce(state_with_schema, make_event(seq=2, type="entity.create", payload={
            "id": "t1",
            "_schema": "task",
            "title": "Buy milk",
            "done": False,
        }))
        r2 = reduce(r1.snapshot, make_event(seq=3, type="entity.remove", payload={"id": "t1"}))
        assert r2.applied
        assert_round_trip_equal(r2.snapshot)


# ============================================================================
# 4. Snapshot round-trip after block/style/meta operations
# ============================================================================

class TestBlockStyleMetaRoundTrip:
    def test_block_set_round_trips(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="block.set", payload={
            "id": "block_heading",
            "type": "heading",
            "parent": "block_root",
            "text": "My Aide",
        }))
        assert result.applied
        assert_round_trip_equal(result.snapshot)

    def test_block_reorder_round_trips(self):
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="block.set", payload={
            "id": "b1", "type": "text", "parent": "block_root", "text": "First",
        }))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="block.set", payload={
            "id": "b2", "type": "text", "parent": "block_root", "text": "Second",
        }))
        r3 = reduce(r2.snapshot, make_event(seq=3, type="block.reorder", payload={
            "parent": "block_root",
            "order": ["b2", "b1"],
        }))
        assert r3.applied
        assert_round_trip_equal(r3.snapshot)

    def test_style_set_round_trips(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="style.set", payload={
            "primary_color": "#ff6600",
            "font_family": "Georgia",
            "density": "compact",
        }))
        assert result.applied
        assert_round_trip_equal(result.snapshot)

    def test_meta_update_round_trips(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="meta.update", payload={
            "title": "Weekend Plans",
            "visibility": "private",
        }))
        assert result.applied
        assert_round_trip_equal(result.snapshot)

    def test_meta_annotate_round_trips(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="meta.annotate", payload={
            "note": "This aide tracks the renovation budget.",
            "pinned": True,
            "author": "user_abc",
        }))
        assert result.applied
        assert_round_trip_equal(result.snapshot)


# ============================================================================
# 5. Event log round-trip
# ============================================================================

class TestEventLogRoundTrip:
    def test_event_log_round_trips_via_to_dict(self):
        """Events serialized with to_dict() then reconstructed via from_dict()
        produce the same snapshot when replayed."""
        events = [
            make_event(seq=1, type="schema.create", payload={
                "id": "task",
                "interface": TASK_INTERFACE,
                "render_html": "<li>{{title}}</li>",
                "render_text": "{{title}}",
            }),
            make_event(seq=2, type="entity.create", payload={
                "id": "t1",
                "_schema": "task",
                "title": "Learn Python",
                "done": False,
            }),
            make_event(seq=3, type="entity.update", payload={"id": "t1", "done": True}),
        ]

        # Serialize events to dicts then reconstruct
        serialized = [e.to_dict() for e in events]
        reconstructed = [Event.from_dict(d) for d in serialized]

        snap_original = replay(events)
        snap_reconstructed = replay(reconstructed)

        assert json.dumps(snap_original, sort_keys=True) == json.dumps(snap_reconstructed, sort_keys=True)

    def test_event_round_trip_preserves_all_fields(self):
        event = make_event(
            seq=42,
            type="entity.create",
            payload={"id": "t1", "title": "Test", "done": False},
            actor="user_xyz",
            source="mobile",
            intent="Add task",
            message="Add test task",
            message_id="msg_001",
        )
        rt = Event.from_dict(event.to_dict())
        assert rt.sequence == event.sequence
        assert rt.actor == event.actor
        assert rt.source == event.source
        assert rt.type == event.type
        assert rt.payload == event.payload
        assert rt.intent == event.intent
        assert rt.message == event.message
        assert rt.message_id == event.message_id


# ============================================================================
# 6. Field type fidelity through round-trip
# ============================================================================

class TestFieldTypeFidelity:
    def test_all_field_types_survive_round_trip(self):
        """Strings, booleans, ints, floats, nulls, and lists survive round-trip."""
        snap = empty_state()
        snap["entities"]["test_entity"] = {
            "str_field": "hello world",
            "bool_true": True,
            "bool_false": False,
            "int_field": 42,
            "float_field": 3.14,
            "nested_dict": {"inner": "value", "num": 7},
            "_pos": 1.5,
        }
        rt = round_trip(snap)
        ent = rt["entities"]["test_entity"]
        assert ent["str_field"] == "hello world"
        assert ent["bool_true"] is True
        assert ent["bool_false"] is False
        assert ent["int_field"] == 42
        assert abs(ent["float_field"] - 3.14) < 1e-9
        assert ent["nested_dict"]["inner"] == "value"
        assert ent["nested_dict"]["num"] == 7

    def test_unicode_strings_survive_round_trip(self):
        snap = empty_state()
        snap["meta"]["title"] = "Café schedule — spring ☀"
        rt = round_trip(snap)
        assert rt["meta"]["title"] == "Café schedule — spring ☀"

    def test_empty_string_survives_round_trip(self):
        snap = empty_state()
        snap["entities"]["e1"] = {"title": "", "done": False}
        rt = round_trip(snap)
        assert rt["entities"]["e1"]["title"] == ""

    def test_deeply_nested_child_collection_survives_round_trip(self):
        snap = empty_state()
        snap["entities"]["list_a"] = {
            "_schema": "grocery_list",
            "title": "Groceries",
            "items": {
                "item_milk": {"name": "Milk", "checked": False, "_pos": 1.0},
                "item_eggs": {"name": "Eggs", "checked": True, "_pos": 2.0},
            },
        }
        rt = round_trip(snap)
        items = rt["entities"]["list_a"]["items"]
        assert items["item_milk"]["name"] == "Milk"
        assert items["item_eggs"]["checked"] is True


# ============================================================================
# 7. Continue reducing after deserialization
# ============================================================================

class TestContinueAfterDeserialization:
    def test_deserialized_snapshot_accepts_new_events(self):
        """A snapshot loaded from JSON can accept further reduce() calls."""
        events = [
            make_event(seq=1, type="schema.create", payload={
                "id": "task",
                "interface": TASK_INTERFACE,
                "render_html": "<li>{{title}}</li>",
                "render_text": "{{title}}",
            }),
            make_event(seq=2, type="entity.create", payload={
                "id": "t1",
                "_schema": "task",
                "title": "Initial task",
                "done": False,
            }),
        ]
        snap = replay(events)
        snap_rt = round_trip(snap)

        # Continue reducing on the deserialized snapshot
        new_event = make_event(seq=3, type="entity.update", payload={
            "id": "t1",
            "done": True,
        })
        result = reduce(snap_rt, new_event)
        assert result.applied
        assert result.snapshot["entities"]["t1"]["done"] is True

    def test_deserialized_snapshot_rejects_duplicate_entity(self):
        """After round-trip, ALREADY_EXISTS rejection still works correctly."""
        events = [
            make_event(seq=1, type="schema.create", payload={
                "id": "task",
                "interface": TASK_INTERFACE,
                "render_html": "<li>{{title}}</li>",
                "render_text": "{{title}}",
            }),
            make_event(seq=2, type="entity.create", payload={
                "id": "t1",
                "_schema": "task",
                "title": "Existing task",
                "done": False,
            }),
        ]
        snap = round_trip(replay(events))

        dup_event = make_event(seq=3, type="entity.create", payload={
            "id": "t1",
            "_schema": "task",
            "title": "Duplicate",
            "done": False,
        })
        result = reduce(snap, dup_event)
        assert not result.applied
        assert "ALREADY_EXISTS" in result.error


# ============================================================================
# 8. Large snapshot round-trip
# ============================================================================

class TestLargeSnapshotRoundTrip:
    def test_100_entities_round_trip(self):
        events = [
            make_event(seq=1, type="schema.create", payload={
                "id": "task",
                "interface": TASK_INTERFACE,
                "render_html": "<li>{{title}}</li>",
                "render_text": "{{title}}",
            }),
        ]
        for i in range(100):
            events.append(make_event(seq=i + 2, type="entity.create", payload={
                "id": f"task_{i:03d}",
                "_schema": "task",
                "title": f"Task number {i}",
                "done": i % 2 == 0,
            }))

        snap = replay(events)
        assert len(snap["entities"]) == 100

        rt = round_trip(snap)
        assert len(rt["entities"]) == 100

        a = json.dumps(snap, sort_keys=True)
        b = json.dumps(rt, sort_keys=True)
        assert a == b
