"""
AIde Reducer -- Round-Trip Tests (Category 9)

Tests that snapshots and events survive JSON serialization and deserialization
without loss of information, and that deserialized snapshots continue to
function correctly with the reducer.

From the spec (aide_reducer_spec.md, "Testing Strategy"):
  "9. Round-trip. Generate snapshot, serialize to JSON, deserialize,
   verify equality."

This matters because:
  - The snapshot is embedded as JSON in the HTML file
  - Any client must be able to parse aide-state JSON and arrive at usable state
  - Replay from deserialized events must produce the same snapshot
  - No data loss through the serialize/deserialize boundary
  - All field types survive round-trip (strings, ints, floats, bools, nulls,
    enums, dates, lists, nested objects)

Covers:
  - Empty state round-trip
  - Snapshot round-trip after each primitive category
  - Event log round-trip (serialize events, deserialize, replay → same snapshot)
  - Field type fidelity (every type survives JSON serialization)
  - Deep-nested structures (block tree, view configs, relationship data)
  - Continue reducing after deserialization (the deserialized snapshot is live)
  - Sorted-key serialization produces parseable, equal JSON
  - Large snapshot round-trip (~200 entities)

Reference: aide_reducer_spec.md (Contract, Empty State, Determinism),
           aide_renderer_spec.md ("Sorted JSON keys"),
           aide_assembly_spec.md (Parsing)
"""

import json

import pytest

from engine.kernel.events import make_event
from engine.kernel.reducer import empty_state, reduce, replay

# ============================================================================
# Helpers
# ============================================================================


def round_trip(obj):
    """Serialize to JSON with sorted keys, then deserialize back."""
    return json.loads(json.dumps(obj, sort_keys=True, ensure_ascii=True))


def assert_round_trip_equal(snapshot, msg=""):
    """Assert a snapshot survives JSON round-trip unchanged."""
    deserialized = round_trip(snapshot)
    original_json = json.dumps(snapshot, sort_keys=True)
    rt_json = json.dumps(deserialized, sort_keys=True)
    assert original_json == rt_json, f"Round-trip mismatch{': ' + msg if msg else ''}"


def build_state(events):
    """Apply events incrementally, return final snapshot."""
    snapshot = empty_state()
    for event in events:
        result = reduce(snapshot, event)
        snapshot = result.snapshot
    return snapshot


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def empty():
    return empty_state()


def poker_league_events():
    """Comprehensive event log covering all primitive categories."""
    events = []
    seq = 0

    def e(event_type, payload):
        nonlocal seq
        seq += 1
        events.append(make_event(seq=seq, type=event_type, payload=payload))

    # Collections
    e(
        "collection.create",
        {
            "id": "roster",
            "name": "Roster",
            "schema": {"name": "string", "status": "string", "snack_duty": "bool"},
        },
    )
    e(
        "collection.create",
        {
            "id": "schedule",
            "name": "Schedule",
            "schema": {"date": "date", "host": "string?", "status": "string"},
        },
    )

    # Entities
    for pid, name in [
        ("player_mike", "Mike"),
        ("player_dave", "Dave"),
        ("player_linda", "Linda"),
        ("player_steve", "Steve"),
    ]:
        e(
            "entity.create",
            {
                "collection": "roster",
                "id": pid,
                "fields": {"name": name, "status": "active", "snack_duty": False},
            },
        )
    e(
        "entity.create",
        {
            "collection": "schedule",
            "id": "game_feb27",
            "fields": {"date": "2026-02-27", "host": "Dave", "status": "confirmed"},
        },
    )

    # Updates
    e(
        "entity.update",
        {
            "ref": "roster/player_dave",
            "fields": {"snack_duty": True},
        },
    )

    # Schema evolution
    e(
        "field.add",
        {
            "collection": "roster",
            "name": "rating",
            "type": "int",
            "default": 1000,
        },
    )
    e(
        "field.add",
        {
            "collection": "roster",
            "name": "notes",
            "type": "string?",
        },
    )
    e(
        "entity.update",
        {
            "ref": "roster/player_mike",
            "fields": {"rating": 1200},
        },
    )

    # Relationships
    e(
        "relationship.set",
        {
            "from": "roster/player_dave",
            "to": "schedule/game_feb27",
            "type": "hosting",
            "cardinality": "many_to_one",
        },
    )
    e(
        "relationship.set",
        {
            "from": "roster/player_mike",
            "to": "schedule/game_feb27",
            "type": "attending",
            "cardinality": "many_to_many",
        },
    )
    e(
        "relationship.set",
        {
            "from": "roster/player_dave",
            "to": "schedule/game_feb27",
            "type": "attending",
        },
    )

    # Relationship constraint
    e(
        "relationship.constrain",
        {
            "id": "constraint_no_mike_dave",
            "rule": "exclude_pair",
            "entities": ["roster/player_mike", "roster/player_dave"],
            "relationship_type": "hosting",
            "message": "Mike and Dave can't both host the same game",
        },
    )

    # Views
    e(
        "view.create",
        {
            "id": "roster_view",
            "type": "list",
            "source": "roster",
            "config": {
                "show_fields": ["name", "status", "rating"],
                "sort_by": "name",
                "sort_order": "asc",
            },
        },
    )
    e(
        "view.create",
        {
            "id": "schedule_view",
            "type": "table",
            "source": "schedule",
            "config": {"show_fields": ["date", "host", "status"]},
        },
    )

    # Blocks
    e(
        "block.set",
        {
            "id": "block_title",
            "type": "heading",
            "parent": "block_root",
            "props": {"level": 1, "content": "Poker League"},
        },
    )
    e(
        "block.set",
        {
            "id": "block_metric",
            "type": "metric",
            "parent": "block_root",
            "props": {"label": "Next game", "value": "Thu Feb 27 at Dave's"},
        },
    )
    e(
        "block.set",
        {
            "id": "block_roster",
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "roster", "view": "roster_view"},
        },
    )
    e(
        "block.set",
        {
            "id": "block_schedule",
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "schedule", "view": "schedule_view"},
        },
    )

    # Styles
    e(
        "style.set",
        {
            "primary_color": "#2d3748",
            "font_family": "Inter",
            "density": "comfortable",
        },
    )
    e(
        "style.set_entity",
        {
            "ref": "roster/player_mike",
            "styles": {"highlight": True, "bg_color": "#fef3c7"},
        },
    )

    # Meta
    e(
        "meta.update",
        {
            "title": "Poker League — Spring 2026",
            "identity": "8 players, biweekly Thursday.",
        },
    )
    e(
        "meta.annotate",
        {
            "note": "League started Feb 1.",
            "pinned": False,
        },
    )
    e(
        "meta.constrain",
        {
            "id": "constraint_max_players",
            "rule": "collection_max_entities",
            "collection": "roster",
            "value": 10,
            "message": "Maximum 10 players",
        },
    )

    # Entity remove
    e("entity.remove", {"ref": "roster/player_steve"})

    # Block reorder
    e(
        "block.reorder",
        {
            "parent": "block_root",
            "children": ["block_title", "block_metric", "block_roster", "block_schedule"],
        },
    )

    return events


# ============================================================================
# Empty State Round-Trip
# ============================================================================


class TestEmptyStateRoundTrip:
    """The empty state must survive JSON serialization unchanged."""

    def test_empty_state_round_trip(self):
        snapshot = empty_state()
        assert_round_trip_equal(snapshot, "empty state")

    def test_empty_state_has_correct_structure(self):
        """Verify the deserialized empty state has all top-level keys."""
        snapshot = round_trip(empty_state())
        assert snapshot["version"] == 1
        assert snapshot["meta"] == {}
        assert snapshot["collections"] == {}
        assert snapshot["relationships"] == []
        assert snapshot["relationship_types"] == {}
        assert snapshot["constraints"] == []
        assert "block_root" in snapshot["blocks"]
        assert snapshot["views"] == {}
        assert snapshot["styles"] == {}
        assert snapshot["annotations"] == []


# ============================================================================
# Snapshot Round-Trip per Primitive Category
# ============================================================================


class TestSnapshotRoundTripByCategory:
    """Each category of state change produces a snapshot that survives round-trip."""

    def test_collection_state_round_trip(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="collection.create",
                payload={
                    "id": "items",
                    "name": "Items",
                    "schema": {"name": "string", "count": "int", "done": "bool", "note": "string?"},
                },
            ),
        )
        assert_round_trip_equal(result.snapshot, "collection create")

    def test_entity_state_round_trip(self, empty):
        snapshot = build_state(
            [
                make_event(
                    seq=1,
                    type="collection.create",
                    payload={
                        "id": "items",
                        "schema": {"name": "string", "done": "bool"},
                    },
                ),
                make_event(
                    seq=2,
                    type="entity.create",
                    payload={
                        "collection": "items",
                        "id": "item_a",
                        "fields": {"name": "Alpha", "done": False},
                    },
                ),
            ]
        )
        assert_round_trip_equal(snapshot, "entity create")

    def test_relationship_state_round_trip(self, empty):
        snapshot = build_state(
            [
                make_event(
                    seq=1,
                    type="collection.create",
                    payload={
                        "id": "people",
                        "schema": {"name": "string"},
                    },
                ),
                make_event(
                    seq=2,
                    type="collection.create",
                    payload={
                        "id": "teams",
                        "schema": {"name": "string"},
                    },
                ),
                make_event(
                    seq=3,
                    type="entity.create",
                    payload={
                        "collection": "people",
                        "id": "alice",
                        "fields": {"name": "Alice"},
                    },
                ),
                make_event(
                    seq=4,
                    type="entity.create",
                    payload={
                        "collection": "teams",
                        "id": "red",
                        "fields": {"name": "Red"},
                    },
                ),
                make_event(
                    seq=5,
                    type="relationship.set",
                    payload={
                        "from": "people/alice",
                        "to": "teams/red",
                        "type": "member_of",
                        "cardinality": "many_to_one",
                        "data": {"role": "captain", "joined": "2026-01-15"},
                    },
                ),
            ]
        )
        assert_round_trip_equal(snapshot, "relationship with data")

    def test_view_state_round_trip(self, empty):
        snapshot = build_state(
            [
                make_event(
                    seq=1,
                    type="collection.create",
                    payload={
                        "id": "tasks",
                        "schema": {"title": "string", "done": "bool"},
                    },
                ),
                make_event(
                    seq=2,
                    type="view.create",
                    payload={
                        "id": "task_view",
                        "type": "list",
                        "source": "tasks",
                        "config": {
                            "show_fields": ["title", "done"],
                            "sort_by": "title",
                            "sort_order": "desc",
                            "filter": {"done": False},
                        },
                    },
                ),
            ]
        )
        assert_round_trip_equal(snapshot, "view with config")

    def test_block_tree_round_trip(self, empty):
        snapshot = build_state(
            [
                make_event(
                    seq=1,
                    type="block.set",
                    payload={
                        "id": "block_title",
                        "type": "heading",
                        "parent": "block_root",
                        "props": {"level": 1, "content": "My Page"},
                    },
                ),
                make_event(
                    seq=2,
                    type="block.set",
                    payload={
                        "id": "block_cols",
                        "type": "column_list",
                        "parent": "block_root",
                    },
                ),
                make_event(
                    seq=3,
                    type="block.set",
                    payload={
                        "id": "block_left",
                        "type": "column",
                        "parent": "block_cols",
                        "props": {"width": "60%"},
                    },
                ),
                make_event(
                    seq=4,
                    type="block.set",
                    payload={
                        "id": "block_right",
                        "type": "column",
                        "parent": "block_cols",
                        "props": {"width": "40%"},
                    },
                ),
                make_event(
                    seq=5,
                    type="block.set",
                    payload={
                        "id": "block_text",
                        "type": "text",
                        "parent": "block_left",
                        "props": {"content": "Hello world"},
                    },
                ),
            ]
        )
        assert_round_trip_equal(snapshot, "nested block tree")

    def test_style_state_round_trip(self, empty):
        snapshot = build_state(
            [
                make_event(
                    seq=1,
                    type="style.set",
                    payload={
                        "primary_color": "#1a365d",
                        "bg_color": "#fffff0",
                        "font_family": "Inter",
                        "density": "compact",
                    },
                ),
            ]
        )
        assert_round_trip_equal(snapshot, "style tokens")

    def test_meta_state_round_trip(self, empty):
        snapshot = build_state(
            [
                make_event(
                    seq=1,
                    type="meta.update",
                    payload={
                        "title": "Test Aide",
                        "identity": "A test aide for round-trip verification.",
                        "visibility": "public",
                    },
                ),
                make_event(
                    seq=2,
                    type="meta.annotate",
                    payload={
                        "note": "Created for testing.",
                        "pinned": True,
                    },
                ),
                make_event(
                    seq=3,
                    type="meta.annotate",
                    payload={
                        "note": "Second note.",
                        "pinned": False,
                    },
                ),
            ]
        )
        assert_round_trip_equal(snapshot, "meta + annotations")

    def test_constraint_state_round_trip(self, empty):
        snapshot = build_state(
            [
                make_event(
                    seq=1,
                    type="collection.create",
                    payload={
                        "id": "roster",
                        "schema": {"name": "string"},
                    },
                ),
                make_event(
                    seq=2,
                    type="meta.constrain",
                    payload={
                        "id": "max_players",
                        "rule": "collection_max_entities",
                        "collection": "roster",
                        "value": 10,
                        "message": "Maximum 10 players",
                    },
                ),
                make_event(
                    seq=3,
                    type="collection.create",
                    payload={
                        "id": "pairs",
                        "schema": {"a": "string", "b": "string"},
                    },
                ),
                make_event(
                    seq=4,
                    type="entity.create",
                    payload={
                        "collection": "roster",
                        "id": "p1",
                        "fields": {"name": "Alice"},
                    },
                ),
                make_event(
                    seq=5,
                    type="entity.create",
                    payload={
                        "collection": "roster",
                        "id": "p2",
                        "fields": {"name": "Bob"},
                    },
                ),
                make_event(
                    seq=6,
                    type="relationship.constrain",
                    payload={
                        "id": "no_alice_bob",
                        "rule": "exclude_pair",
                        "entities": ["roster/p1", "roster/p2"],
                        "relationship_type": "seated_at",
                        "message": "Keep Alice and Bob apart",
                    },
                ),
            ]
        )
        assert_round_trip_equal(snapshot, "constraints")


# ============================================================================
# Full Poker League Round-Trip
# ============================================================================


class TestFullSnapshotRoundTrip:
    """End-to-end: build complex state, round-trip, verify exact equality."""

    def test_poker_league_snapshot_round_trip(self):
        """The full poker league snapshot survives serialization."""
        events = poker_league_events()
        snapshot = replay(events)
        assert_round_trip_equal(snapshot, "poker league")

    def test_poker_league_deep_equality(self):
        """Spot-check specific values after round-trip."""
        events = poker_league_events()
        snapshot = replay(events)
        restored = round_trip(snapshot)

        # Collections
        assert "roster" in restored["collections"]
        assert "schedule" in restored["collections"]

        # Entity data
        mike = restored["collections"]["roster"]["entities"]["player_mike"]
        assert mike["name"] == "Mike"
        assert mike["rating"] == 1200
        assert mike["_removed"] is False

        # Removed entity
        steve = restored["collections"]["roster"]["entities"]["player_steve"]
        assert steve["_removed"] is True
        assert steve["name"] == "Steve"

        # Relationship types
        assert restored["relationship_types"]["hosting"]["cardinality"] == "many_to_one"
        assert restored["relationship_types"]["attending"]["cardinality"] == "many_to_many"

        # Views
        assert restored["views"]["roster_view"]["type"] == "list"
        assert restored["views"]["roster_view"]["config"]["sort_by"] == "name"

        # Blocks
        root_children = restored["blocks"]["block_root"]["children"]
        assert root_children == ["block_title", "block_metric", "block_roster", "block_schedule"]

        # Styles
        assert restored["styles"]["primary_color"] == "#2d3748"

        # Meta
        assert restored["meta"]["title"] == "Poker League — Spring 2026"

        # Annotations
        assert len(restored["annotations"]) == 1
        assert restored["annotations"][0]["note"] == "League started Feb 1."

        # Constraints
        constraint_ids = [c["id"] for c in restored["constraints"]]
        assert "constraint_max_players" in constraint_ids
        assert "constraint_no_mike_dave" in constraint_ids

        # Entity styles
        assert mike["_styles"]["highlight"] is True
        assert mike["_styles"]["bg_color"] == "#fef3c7"


# ============================================================================
# Event Log Round-Trip
# ============================================================================


class TestEventLogRoundTrip:
    """Events survive serialization and replay to produce the same snapshot."""

    def test_replay_deserialized_events(self):
        """Serialize events → deserialize → replay → same snapshot."""
        from engine.kernel.types import Event

        events = poker_league_events()
        original_snapshot = replay(events)

        # Round-trip the event log through JSON using to_dict()
        events_as_dicts = [e.to_dict() for e in events]
        events_json = json.dumps(events_as_dicts, sort_keys=True)
        restored_dicts = json.loads(events_json)

        # Convert back to Event objects
        restored_events = [Event.from_dict(d) for d in restored_dicts]

        # Replay from deserialized events
        replayed_snapshot = replay(restored_events)

        original_json = json.dumps(original_snapshot, sort_keys=True)
        replayed_json = json.dumps(replayed_snapshot, sort_keys=True)
        assert original_json == replayed_json

    def test_events_preserve_all_fields(self):
        """Every event field survives round-trip (type, payload, seq, etc.)."""

        events = poker_league_events()

        for event in events:
            event_dict = event.to_dict()
            restored = round_trip(event_dict)
            assert restored["type"] == event.type
            assert restored["sequence"] == event.sequence
            assert json.dumps(restored["payload"], sort_keys=True) == json.dumps(event.payload, sort_keys=True)


# ============================================================================
# Field Type Fidelity
# ============================================================================


class TestFieldTypeFidelity:
    """Every field type supported by the schema survives JSON round-trip."""

    def test_all_field_types_survive(self, empty):
        """Create entities with every field type and verify after round-trip."""
        snapshot = build_state(
            [
                make_event(
                    seq=1,
                    type="collection.create",
                    payload={
                        "id": "typed",
                        "schema": {
                            "str_field": "string",
                            "str_nullable": "string?",
                            "int_field": "int",
                            "float_field": "float",
                            "bool_field": "bool",
                            "date_field": "date",
                        },
                    },
                ),
                make_event(
                    seq=2,
                    type="entity.create",
                    payload={
                        "collection": "typed",
                        "id": "entity_full",
                        "fields": {
                            "str_field": "hello world",
                            "str_nullable": "present",
                            "int_field": 42,
                            "float_field": 3.14159,
                            "bool_field": True,
                            "date_field": "2026-02-14",
                        },
                    },
                ),
                make_event(
                    seq=3,
                    type="entity.create",
                    payload={
                        "collection": "typed",
                        "id": "entity_nulls",
                        "fields": {
                            "str_field": "",
                            "str_nullable": None,
                            "int_field": 0,
                            "float_field": 0.0,
                            "bool_field": False,
                            "date_field": "1970-01-01",
                        },
                    },
                ),
            ]
        )

        restored = round_trip(snapshot)
        full = restored["collections"]["typed"]["entities"]["entity_full"]
        nulls = restored["collections"]["typed"]["entities"]["entity_nulls"]

        # Full entity
        assert full["str_field"] == "hello world"
        assert full["str_nullable"] == "present"
        assert full["int_field"] == 42
        assert full["float_field"] == pytest.approx(3.14159)
        assert full["bool_field"] is True
        assert full["date_field"] == "2026-02-14"

        # Null/zero/empty entity
        assert nulls["str_field"] == ""
        assert nulls["str_nullable"] is None
        assert nulls["int_field"] == 0
        assert nulls["float_field"] == pytest.approx(0.0)
        assert nulls["bool_field"] is False
        assert nulls["date_field"] == "1970-01-01"

    def test_enum_field_survives(self, empty):
        """Enum-typed fields survive round-trip."""
        snapshot = build_state(
            [
                make_event(
                    seq=1,
                    type="collection.create",
                    payload={
                        "id": "tasks",
                        "schema": {"status": {"enum": ["todo", "in_progress", "done"]}},
                    },
                ),
                make_event(
                    seq=2,
                    type="entity.create",
                    payload={
                        "collection": "tasks",
                        "id": "t1",
                        "fields": {"status": "in_progress"},
                    },
                ),
            ]
        )

        restored = round_trip(snapshot)
        assert restored["collections"]["tasks"]["entities"]["t1"]["status"] == "in_progress"
        schema = restored["collections"]["tasks"]["schema"]
        assert schema["status"] == {"enum": ["todo", "in_progress", "done"]}

    def test_float_precision_preserved(self, empty):
        """Float precision is maintained through JSON round-trip."""
        snapshot = build_state(
            [
                make_event(
                    seq=1,
                    type="collection.create",
                    payload={
                        "id": "data",
                        "schema": {"value": "float"},
                    },
                ),
                make_event(
                    seq=2,
                    type="entity.create",
                    payload={
                        "collection": "data",
                        "id": "d1",
                        "fields": {"value": 0.1 + 0.2},  # Classic float: 0.30000000000000004
                    },
                ),
                make_event(
                    seq=3,
                    type="entity.create",
                    payload={
                        "collection": "data",
                        "id": "d2",
                        "fields": {"value": 1e-10},
                    },
                ),
                make_event(
                    seq=4,
                    type="entity.create",
                    payload={
                        "collection": "data",
                        "id": "d3",
                        "fields": {"value": 1.7976931348623157e308},  # Near max float
                    },
                ),
            ]
        )

        restored = round_trip(snapshot)
        entities = restored["collections"]["data"]["entities"]
        assert entities["d1"]["value"] == pytest.approx(0.3, abs=1e-15)
        assert entities["d2"]["value"] == pytest.approx(1e-10)
        assert entities["d3"]["value"] == pytest.approx(1.7976931348623157e308)

    def test_special_string_characters(self, empty):
        """Strings with special characters survive round-trip."""
        snapshot = build_state(
            [
                make_event(
                    seq=1,
                    type="collection.create",
                    payload={
                        "id": "items",
                        "schema": {"name": "string"},
                    },
                ),
                make_event(
                    seq=2,
                    type="entity.create",
                    payload={
                        "collection": "items",
                        "id": "unicode",
                        "fields": {"name": 'Café ☕ naïve résumé — "quoted" <tag>'},
                    },
                ),
                make_event(
                    seq=3,
                    type="entity.create",
                    payload={
                        "collection": "items",
                        "id": "newlines",
                        "fields": {"name": "line1\nline2\ttab"},
                    },
                ),
                make_event(
                    seq=4,
                    type="entity.create",
                    payload={
                        "collection": "items",
                        "id": "empty_str",
                        "fields": {"name": ""},
                    },
                ),
            ]
        )

        restored = round_trip(snapshot)
        entities = restored["collections"]["items"]["entities"]
        assert entities["unicode"]["name"] == 'Café ☕ naïve résumé — "quoted" <tag>'
        assert entities["newlines"]["name"] == "line1\nline2\ttab"
        assert entities["empty_str"]["name"] == ""


# ============================================================================
# Continue Reducing After Deserialization
# ============================================================================


class TestContinueAfterDeserialization:
    """
    After round-tripping a snapshot through JSON, the deserialized snapshot
    must be usable as input to the reducer. This simulates the assembly
    load path: parse HTML → extract JSON → deserialize → continue reducing.
    """

    def test_reduce_on_deserialized_snapshot(self):
        """Build state, serialize, deserialize, then apply more events."""
        events = poker_league_events()
        snapshot = replay(events)

        # Round-trip through JSON (simulates load from HTML file)
        restored = round_trip(snapshot)

        # Continue reducing on the deserialized snapshot
        next_seq = len(events) + 1
        result = reduce(
            restored,
            make_event(
                seq=next_seq,
                type="entity.create",
                payload={
                    "collection": "roster",
                    "id": "player_new",
                    "fields": {"name": "New Player", "status": "active", "snack_duty": False, "rating": 800},
                },
            ),
        )
        assert result.applied
        new_player = result.snapshot["collections"]["roster"]["entities"]["player_new"]
        assert new_player["name"] == "New Player"
        assert new_player["rating"] == 800

    def test_schema_evolution_on_deserialized_snapshot(self):
        """field.add works on a deserialized snapshot."""
        events = poker_league_events()
        snapshot = replay(events)
        restored = round_trip(snapshot)

        next_seq = len(events) + 1
        result = reduce(
            restored,
            make_event(
                seq=next_seq,
                type="field.add",
                payload={
                    "collection": "roster",
                    "name": "wins",
                    "type": "int",
                    "default": 0,
                },
            ),
        )
        assert result.applied

        # All non-removed entities got backfilled
        for eid, entity in result.snapshot["collections"]["roster"]["entities"].items():
            if not entity.get("_removed"):
                assert "wins" in entity

    def test_relationship_set_on_deserialized_snapshot(self):
        """Relationships work after round-trip (cardinality enforcement intact)."""
        events = poker_league_events()
        snapshot = replay(events)
        restored = round_trip(snapshot)

        next_seq = len(events) + 1

        # Re-assign hosting for game_feb27 (many_to_one should auto-unlink Dave)
        result = reduce(
            restored,
            make_event(
                seq=next_seq,
                type="relationship.set",
                payload={
                    "from": "roster/player_linda",
                    "to": "schedule/game_feb27",
                    "type": "hosting",
                },
            ),
        )
        assert result.applied

        hosting_rels = [
            r for r in result.snapshot["relationships"] if r["type"] == "hosting" and r["to"] == "schedule/game_feb27"
        ]
        # Only Linda should be hosting now (Dave auto-unlinked)
        from_refs = [r["from"] for r in hosting_rels]
        assert "roster/player_linda" in from_refs

    def test_cascade_on_deserialized_snapshot(self):
        """collection.remove cascade works on deserialized state."""
        events = poker_league_events()
        snapshot = replay(events)
        restored = round_trip(snapshot)

        next_seq = len(events) + 1
        result = reduce(
            restored,
            make_event(seq=next_seq, type="collection.remove", payload={"id": "roster"}),
        )
        assert result.applied
        assert result.snapshot["collections"]["roster"]["_removed"] is True


# ============================================================================
# Large Snapshot Round-Trip
# ============================================================================


class TestLargeSnapshotRoundTrip:
    """Round-trip with ~200 entities to verify no data loss at scale."""

    def test_200_entity_round_trip(self, empty):
        """Create 200 entities, round-trip, verify all survive."""
        events = [
            make_event(
                seq=1,
                type="collection.create",
                payload={
                    "id": "guests",
                    "schema": {
                        "name": "string",
                        "table": "string?",
                        "dietary": "string?",
                        "rsvp": "bool",
                    },
                },
            ),
        ]

        for i in range(200):
            events.append(
                make_event(
                    seq=2 + i,
                    type="entity.create",
                    payload={
                        "collection": "guests",
                        "id": f"guest_{i:03d}",
                        "fields": {
                            "name": f"Guest {i}",
                            "table": f"Table {(i % 20) + 1}" if i % 3 != 0 else None,
                            "dietary": ["none", "vegetarian", "vegan", "gluten-free"][i % 4] if i % 5 != 0 else None,
                            "rsvp": i % 2 == 0,
                        },
                    },
                )
            )

        snapshot = replay(events)
        restored = round_trip(snapshot)

        # All 200 entities present
        entities = restored["collections"]["guests"]["entities"]
        assert len(entities) == 200

        # Spot-check first, middle, last
        assert entities["guest_000"]["name"] == "Guest 0"
        assert entities["guest_000"]["rsvp"] is True
        assert entities["guest_100"]["name"] == "Guest 100"
        assert entities["guest_199"]["name"] == "Guest 199"
        assert entities["guest_199"]["rsvp"] is False

        # Full round-trip equality
        assert_round_trip_equal(snapshot, "200-entity snapshot")


# ============================================================================
# Snapshot + Events Combined Round-Trip
# ============================================================================


class TestCombinedSnapshotEventsRoundTrip:
    """
    Simulate the full HTML file embedding: snapshot and events are both
    serialized, then later both deserialized. The deserialized events
    replayed from scratch must match the deserialized snapshot.
    """

    def test_embedded_snapshot_matches_replayed_events(self):
        """
        The HTML file embeds both aide-state (snapshot) and aide-events (log).
        Parsing the file and replaying events must produce the same snapshot
        as directly parsing the embedded snapshot.
        """
        from engine.kernel.types import Event

        events = poker_league_events()
        snapshot = replay(events)

        # Simulate HTML embedding: both get serialized
        snapshot_json_str = json.dumps(snapshot, sort_keys=True)
        events_as_dicts = [e.to_dict() for e in events]
        events_json_str = json.dumps(events_as_dicts, sort_keys=True)

        # Simulate HTML parsing: both get deserialized
        parsed_snapshot = json.loads(snapshot_json_str)
        parsed_events_dicts = json.loads(events_json_str)
        parsed_events = [Event.from_dict(d) for d in parsed_events_dicts]

        # Integrity check: replay events → compare to embedded snapshot
        replayed = replay(parsed_events)
        replayed_json_str = json.dumps(replayed, sort_keys=True)

        assert replayed_json_str == snapshot_json_str

    def test_double_round_trip(self):
        """Serialize → deserialize → serialize → deserialize is stable."""
        events = poker_league_events()
        snapshot = replay(events)

        rt1 = round_trip(snapshot)
        rt2 = round_trip(rt1)

        json1 = json.dumps(rt1, sort_keys=True)
        json2 = json.dumps(rt2, sort_keys=True)
        assert json1 == json2
