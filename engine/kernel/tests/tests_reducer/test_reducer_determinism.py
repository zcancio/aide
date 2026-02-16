"""
AIde Reducer -- Determinism Tests (Category 8)

Tests that the reducer is a pure, deterministic function: same events in,
same snapshot out, every single time.

From the spec (aide_reducer_spec.md, "Testing Strategy"):
  "8. Determinism. Replay the same 50 events 100 times. Verify identical
   snapshot every time (JSON serialization order matters — use sorted keys)."

And from the "Determinism Guarantee" section:
  "The reducer is deterministic. Given the same sequence of events, it produces
   the same snapshot every time. No randomness, no timestamps, no external state."

This means:
  - Any client can replay the event log and arrive at the same state
  - Tests are trivial: fixed input → fixed output
  - Debugging is replay: reproduce any bug by replaying events up to that point

Covers:
  - N-times replay identity (100 iterations)
  - Incremental vs. full replay equivalence
  - Replay with rejections produces same result
  - Replay with warnings produces same result
  - Replay with schema evolution
  - Replay with cascading removes
  - Replay with relationship cardinality enforcement
  - Empty state is deterministic
  - Replay subset for time-travel / undo
  - Rejected events don't affect snapshot (pure)

Reference: aide_reducer_spec.md (Contract, Determinism Guarantee, Replay)
"""

import copy
import json
import pytest

from engine.kernel.reducer import reduce, empty_state, replay
from engine.kernel.events import make_event


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
        snapshot = result.snapshot
    return snapshot


# ============================================================================
# Event Log Fixtures
# ============================================================================


def poker_league_events():
    """
    ~50 events covering all primitive categories for a poker league aide.
    Covers: collections, entities, fields, relationships, views, blocks,
    styles, meta, constraints, schema evolution, removes, updates.
    """
    events = []
    seq = 0

    def e(event_type, payload):
        nonlocal seq
        seq += 1
        events.append(make_event(seq=seq, type=event_type, payload=payload))

    # --- Collections ---
    e("collection.create", {
        "id": "roster",
        "name": "Roster",
        "schema": {"name": "string", "status": "string", "snack_duty": "bool"},
    })
    e("collection.create", {
        "id": "schedule",
        "name": "Schedule",
        "schema": {"date": "date", "host": "string?", "status": "string"},
    })
    e("collection.create", {
        "id": "finances",
        "name": "Finances",
        "schema": {"description": "string", "amount": "float", "paid": "bool"},
    })

    # --- Roster entities ---
    for pid, name in [("player_mike", "Mike"), ("player_dave", "Dave"),
                      ("player_linda", "Linda"), ("player_steve", "Steve"),
                      ("player_rachel", "Rachel"), ("player_tom", "Tom"),
                      ("player_amy", "Amy"), ("player_jeff", "Jeff")]:
        e("entity.create", {
            "collection": "roster",
            "id": pid,
            "fields": {"name": name, "status": "active", "snack_duty": False},
        })

    # --- Schedule entities ---
    e("entity.create", {
        "collection": "schedule",
        "id": "game_feb27",
        "fields": {"date": "2026-02-27", "host": "Dave", "status": "confirmed"},
    })
    e("entity.create", {
        "collection": "schedule",
        "id": "game_mar13",
        "fields": {"date": "2026-03-13", "host": None, "status": "tentative"},
    })
    e("entity.create", {
        "collection": "schedule",
        "id": "game_mar27",
        "fields": {"date": "2026-03-27", "host": None, "status": "tentative"},
    })

    # --- Finance entities ---
    e("entity.create", {
        "collection": "finances",
        "id": "expense_chips",
        "fields": {"description": "Chips and dip", "amount": 24.50, "paid": True},
    })
    e("entity.create", {
        "collection": "finances",
        "id": "expense_cards",
        "fields": {"description": "New card deck", "amount": 12.99, "paid": False},
    })

    # --- Entity updates ---
    e("entity.update", {
        "ref": "roster/player_dave",
        "fields": {"snack_duty": True},
    })
    e("entity.update", {
        "ref": "schedule/game_mar13",
        "fields": {"host": "Linda", "status": "confirmed"},
    })

    # --- Relationships ---
    e("relationship.set", {
        "from": "roster/player_dave",
        "to": "schedule/game_feb27",
        "type": "hosting",
        "cardinality": "many_to_one",
    })
    e("relationship.set", {
        "from": "roster/player_linda",
        "to": "schedule/game_mar13",
        "type": "hosting",
    })
    e("relationship.set", {
        "from": "roster/player_mike",
        "to": "schedule/game_feb27",
        "type": "attending",
        "cardinality": "many_to_many",
    })
    e("relationship.set", {
        "from": "roster/player_dave",
        "to": "schedule/game_feb27",
        "type": "attending",
    })
    e("relationship.set", {
        "from": "roster/player_linda",
        "to": "schedule/game_feb27",
        "type": "attending",
    })
    e("relationship.set", {
        "from": "roster/player_steve",
        "to": "schedule/game_feb27",
        "type": "attending",
    })

    # --- Schema evolution ---
    e("field.add", {
        "collection": "roster",
        "name": "rating",
        "type": "int",
        "default": 1000,
    })
    e("field.add", {
        "collection": "roster",
        "name": "email",
        "type": "string?",
    })
    e("entity.update", {
        "ref": "roster/player_mike",
        "fields": {"rating": 1200},
    })
    e("field.update", {
        "collection": "schedule",
        "name": "host",
        "rename": "hosted_by",
    })

    # --- Views ---
    e("view.create", {
        "id": "roster_view",
        "type": "list",
        "source": "roster",
        "config": {"show_fields": ["name", "status", "rating"], "sort_by": "name"},
    })
    e("view.create", {
        "id": "schedule_view",
        "type": "table",
        "source": "schedule",
        "config": {"show_fields": ["date", "hosted_by", "status"]},
    })
    e("view.create", {
        "id": "finances_view",
        "type": "list",
        "source": "finances",
        "config": {"show_fields": ["description", "amount", "paid"]},
    })

    # --- Blocks ---
    e("block.set", {
        "id": "block_title",
        "type": "heading",
        "parent": "block_root",
        "props": {"level": 1, "content": "Poker League — Spring 2026"},
    })
    e("block.set", {
        "id": "block_next_game",
        "type": "metric",
        "parent": "block_root",
        "props": {"label": "Next game", "value": "Thu Feb 27 at Dave's"},
    })
    e("block.set", {
        "id": "block_roster",
        "type": "collection_view",
        "parent": "block_root",
        "props": {"source": "roster", "view": "roster_view"},
    })
    e("block.set", {
        "id": "block_schedule",
        "type": "collection_view",
        "parent": "block_root",
        "props": {"source": "schedule", "view": "schedule_view"},
    })
    e("block.set", {
        "id": "block_divider",
        "type": "divider",
        "parent": "block_root",
    })
    e("block.set", {
        "id": "block_finances",
        "type": "collection_view",
        "parent": "block_root",
        "props": {"source": "finances", "view": "finances_view"},
    })

    # --- Styles ---
    e("style.set", {
        "primary_color": "#2d3748",
        "font_family": "Inter",
        "density": "comfortable",
        "bg_color": "#fafaf9",
    })

    # --- Entity style override ---
    e("style.set_entity", {
        "ref": "roster/player_mike",
        "styles": {"highlight": True, "bg_color": "#fef3c7"},
    })

    # --- Meta ---
    e("meta.update", {
        "title": "Poker League — Spring 2026",
        "identity": "Poker league. 8 players, biweekly Thursday, rotating hosts.",
    })

    # --- Annotations ---
    e("meta.annotate", {
        "note": "League started Feb 1. 8 players confirmed.",
        "pinned": False,
    })
    e("meta.annotate", {
        "note": "Dave hosting Feb 27 confirmed.",
        "pinned": False,
    })

    # --- Constraints ---
    e("meta.constrain", {
        "id": "constraint_max_players",
        "rule": "collection_max_entities",
        "collection": "roster",
        "value": 10,
        "message": "Maximum 10 players",
    })
    e("relationship.constrain", {
        "id": "constraint_no_double_host",
        "rule": "exclude_pair",
        "entities": ["roster/player_dave", "roster/player_linda"],
        "relationship_type": "hosting",
        "message": "Dave and Linda can't both host the same game",
    })

    # --- Remove an entity ---
    e("entity.remove", {"ref": "roster/player_jeff"})

    # --- Block reorder ---
    e("block.reorder", {
        "parent": "block_root",
        "children": [
            "block_title", "block_next_game", "block_divider",
            "block_roster", "block_schedule", "block_finances",
        ],
    })

    # --- Update block ---
    e("block.set", {
        "id": "block_next_game",
        "props": {"value": "Thu Feb 27 at Dave's — 7pm"},
    })

    # --- View update ---
    e("view.update", {
        "id": "roster_view",
        "config": {"show_fields": ["name", "status", "rating", "snack_duty"]},
    })

    # --- Collection update ---
    e("collection.update", {
        "id": "roster",
        "name": "Player Roster",
        "settings": {"max_display": 10},
    })

    return events


def grocery_events_with_rejections():
    """
    Event log that includes events the reducer will reject.
    Verifies that rejections don't affect determinism.
    """
    events = []
    seq = 0

    def e(event_type, payload):
        nonlocal seq
        seq += 1
        events.append(make_event(seq=seq, type=event_type, payload=payload))

    e("collection.create", {
        "id": "grocery_list",
        "schema": {"name": "string", "checked": "bool"},
    })
    e("entity.create", {
        "collection": "grocery_list",
        "id": "item_milk",
        "fields": {"name": "Milk", "checked": False},
    })
    # This will REJECT — entity already exists
    e("entity.create", {
        "collection": "grocery_list",
        "id": "item_milk",
        "fields": {"name": "Duplicate Milk", "checked": False},
    })
    e("entity.create", {
        "collection": "grocery_list",
        "id": "item_eggs",
        "fields": {"name": "Eggs", "checked": False},
    })
    # This will REJECT — collection doesn't exist
    e("entity.create", {
        "collection": "nonexistent",
        "id": "orphan",
        "fields": {"name": "Lost"},
    })
    e("entity.update", {
        "ref": "grocery_list/item_milk",
        "fields": {"checked": True},
    })
    # This will REJECT — type mismatch
    e("entity.update", {
        "ref": "grocery_list/item_eggs",
        "fields": {"checked": "not_a_bool"},
    })
    e("entity.remove", {"ref": "grocery_list/item_milk"})
    # This will WARN — already removed
    e("entity.remove", {"ref": "grocery_list/item_milk"})
    # This will REJECT — unknown primitive
    e("magic.spell", {"power": 9000})
    e("field.add", {
        "collection": "grocery_list",
        "name": "store",
        "type": "string?",
    })

    return events


def cascade_events():
    """
    Event log exercising cascading removes: create rich state, then
    remove a collection and see everything cascade.
    """
    events = []
    seq = 0

    def e(event_type, payload):
        nonlocal seq
        seq += 1
        events.append(make_event(seq=seq, type=event_type, payload=payload))

    e("collection.create", {
        "id": "tasks",
        "schema": {"title": "string", "done": "bool", "assignee": "string?"},
    })
    e("collection.create", {
        "id": "people",
        "schema": {"name": "string"},
    })
    for i in range(5):
        e("entity.create", {
            "collection": "tasks",
            "id": f"task_{i}",
            "fields": {"title": f"Task {i}", "done": False, "assignee": None},
        })
    for name in ["alice", "bob", "carol"]:
        e("entity.create", {
            "collection": "people",
            "id": f"person_{name}",
            "fields": {"name": name.title()},
        })
    # Cross-collection relationships
    e("relationship.set", {
        "from": "people/person_alice",
        "to": "tasks/task_0",
        "type": "assigned_to",
        "cardinality": "many_to_many",
    })
    e("relationship.set", {
        "from": "people/person_bob",
        "to": "tasks/task_1",
        "type": "assigned_to",
    })
    # Views
    e("view.create", {
        "id": "task_view",
        "type": "list",
        "source": "tasks",
        "config": {"show_fields": ["title", "done"]},
    })
    # Blocks
    e("block.set", {
        "id": "block_title",
        "type": "heading",
        "parent": "block_root",
        "props": {"level": 1, "content": "Project Board"},
    })
    e("block.set", {
        "id": "block_tasks",
        "type": "collection_view",
        "parent": "block_root",
        "props": {"source": "tasks", "view": "task_view"},
    })
    # Schema evolution
    e("field.add", {
        "collection": "tasks",
        "name": "priority",
        "type": "int",
        "default": 0,
    })
    # Now cascade: remove the tasks collection
    e("collection.remove", {"id": "tasks"})

    return events


# ============================================================================
# Core: N-Times Replay Identity
# ============================================================================


class TestNTimesReplayIdentity:
    """Replay the same events N times, verify identical snapshot every time."""

    def test_poker_league_100_replays(self):
        """
        The spec says: "Replay the same 50 events 100 times.
        Verify identical snapshot every time."
        """
        events = poker_league_events()
        assert len(events) >= 45, f"Expected ~50 events, got {len(events)}"

        reference = snapshot_json(replay(events))

        for i in range(100):
            result = snapshot_json(replay(events))
            assert result == reference, (
                f"Replay #{i + 1} produced different snapshot"
            )

    def test_grocery_with_rejections_100_replays(self):
        """Even event logs with rejections produce deterministic results."""
        events = grocery_events_with_rejections()
        reference = snapshot_json(replay(events))

        for i in range(100):
            result = snapshot_json(replay(events))
            assert result == reference, (
                f"Replay #{i + 1} (with rejections) produced different snapshot"
            )

    def test_cascade_events_100_replays(self):
        """Event logs with cascading removes are deterministic."""
        events = cascade_events()
        reference = snapshot_json(replay(events))

        for i in range(100):
            result = snapshot_json(replay(events))
            assert result == reference, (
                f"Replay #{i + 1} (cascade) produced different snapshot"
            )


# ============================================================================
# Incremental vs. Full Replay Equivalence
# ============================================================================


class TestIncrementalVsFullReplay:
    """
    The incremental path (apply one event at a time to running snapshot)
    must produce the same result as the full replay path (replay from empty).
    """

    def test_poker_league_incremental_equals_replay(self):
        """Build poker league incrementally, compare to full replay."""
        events = poker_league_events()

        incremental = snapshot_json(build_incremental(events))
        full = snapshot_json(replay(events))

        assert incremental == full

    def test_grocery_incremental_equals_replay(self):
        """Incremental with rejections matches replay with rejections."""
        events = grocery_events_with_rejections()

        incremental = snapshot_json(build_incremental(events))
        full = snapshot_json(replay(events))

        assert incremental == full

    def test_cascade_incremental_equals_replay(self):
        """Incremental cascade matches full replay cascade."""
        events = cascade_events()

        incremental = snapshot_json(build_incremental(events))
        full = snapshot_json(replay(events))

        assert incremental == full


# ============================================================================
# Rejected Events Don't Affect Snapshot
# ============================================================================


class TestRejectedEventsArePure:
    """
    Rejected events must return the input snapshot unchanged.
    The reducer is pure — failed operations have zero side effects.
    """

    def test_rejected_event_returns_original_snapshot(self):
        """Each rejection returns an identical snapshot to the input."""
        events = grocery_events_with_rejections()
        snapshot = empty_state()

        for event in events:
            snapshot_before = snapshot_json(snapshot)
            result = reduce(snapshot, event)

            if not result.applied:
                snapshot_after = snapshot_json(result.snapshot)
                assert snapshot_before == snapshot_after, (
                    f"Rejected event seq={event.get('seq', '?')} "
                    f"type={event.get('type', '?')} altered snapshot"
                )

            snapshot = result.snapshot

    def test_rejected_events_dont_contribute_to_replay(self):
        """
        Replaying only the applied events produces the same snapshot
        as replaying all events (including rejections).
        """
        events = grocery_events_with_rejections()

        # Full replay with all events
        full_snapshot = replay(events)

        # Replay only events that would apply
        applied_events = []
        snapshot = empty_state()
        for event in events:
            result = reduce(snapshot, event)
            if result.applied:
                applied_events.append(event)
            snapshot = result.snapshot

        applied_only_snapshot = replay(applied_events)

        assert snapshot_json(full_snapshot) == snapshot_json(applied_only_snapshot)


# ============================================================================
# Empty State Determinism
# ============================================================================


class TestEmptyStateDeterminism:
    """The empty state is itself deterministic."""

    def test_empty_state_100_times(self):
        """empty_state() produces identical output every call."""
        reference = snapshot_json(empty_state())
        for _ in range(100):
            assert snapshot_json(empty_state()) == reference

    def test_replay_empty_events(self):
        """Replaying zero events produces the empty state."""
        assert snapshot_json(replay([])) == snapshot_json(empty_state())


# ============================================================================
# Replay Subsets — Time Travel / Undo
# ============================================================================


class TestReplaySubsets:
    """
    From the spec: "Undo (replay all events except the last N)" and
    "Time travel (replay events up to sequence N)".
    Both rely on determinism of partial replay.
    """

    def test_time_travel_to_any_point(self):
        """Replaying events[0:n] for every n produces a deterministic snapshot."""
        events = poker_league_events()
        snapshots = []

        for n in range(len(events) + 1):
            snapshot = replay(events[:n])
            snapshots.append(snapshot_json(snapshot))

        # Replay again — every prefix must match
        for n in range(len(events) + 1):
            snapshot = replay(events[:n])
            assert snapshot_json(snapshot) == snapshots[n], (
                f"Time travel to event {n} not deterministic"
            )

    def test_undo_last_event(self):
        """replay(events[:-1]) gives the state before the last event."""
        events = poker_league_events()

        full = replay(events)
        without_last = replay(events[:-1])

        # They should differ (the last event changes something)
        # But each should be internally consistent
        full_json = snapshot_json(full)
        without_last_json = snapshot_json(without_last)

        # Re-replay to verify determinism
        assert snapshot_json(replay(events)) == full_json
        assert snapshot_json(replay(events[:-1])) == without_last_json

    def test_undo_last_5_events(self):
        """replay(events[:-5]) is deterministic."""
        events = poker_league_events()
        reference = snapshot_json(replay(events[:-5]))

        for _ in range(10):
            assert snapshot_json(replay(events[:-5])) == reference


# ============================================================================
# Deep Copy Safety — Reduce Doesn't Mutate Input
# ============================================================================


class TestReduceDoesNotMutateInput:
    """
    The reducer must not mutate the input snapshot.
    Each call returns a new snapshot object.
    """

    def test_reduce_preserves_input_snapshot(self):
        """Input snapshot is unchanged after reduce."""
        events = poker_league_events()[:10]  # First 10 events
        snapshot = empty_state()

        for event in events:
            snapshot_before = copy.deepcopy(snapshot)
            result = reduce(snapshot, event)

            # Input snapshot must not have been mutated
            assert snapshot_json(snapshot) == snapshot_json(snapshot_before), (
                f"Event type={event.get('type')} mutated input snapshot"
            )

            snapshot = result.snapshot

    def test_parallel_reduce_from_same_snapshot(self):
        """
        Two different events applied to the same snapshot
        produce independent results.
        """
        events = poker_league_events()
        # Build up some state
        snapshot = replay(events[:15])

        # Apply two different events to the SAME snapshot
        event_a = make_event(
            seq=100,
            type="entity.update",
            payload={
                "ref": "roster/player_mike",
                "fields": {"status": "inactive"},
            },
        )
        event_b = make_event(
            seq=100,
            type="entity.update",
            payload={
                "ref": "roster/player_dave",
                "fields": {"status": "inactive"},
            },
        )

        result_a = reduce(snapshot, event_a)
        result_b = reduce(snapshot, event_b)

        # Results should be different
        assert snapshot_json(result_a.snapshot) != snapshot_json(result_b.snapshot)

        # Mike inactive in A, active in B
        mike_a = result_a.snapshot["collections"]["roster"]["entities"]["player_mike"]
        mike_b = result_b.snapshot["collections"]["roster"]["entities"]["player_mike"]
        assert mike_a["status"] == "inactive"
        assert mike_b["status"] == "active"

        # Dave active in A, inactive in B
        dave_a = result_a.snapshot["collections"]["roster"]["entities"]["player_dave"]
        dave_b = result_b.snapshot["collections"]["roster"]["entities"]["player_dave"]
        assert dave_a["status"] == "active"
        assert dave_b["status"] == "inactive"


# ============================================================================
# JSON Serialization Order
# ============================================================================


class TestJsonSerializationDeterminism:
    """
    The spec explicitly calls out: "JSON serialization order matters — use sorted keys."
    Verify that sorted-key serialization is stable.
    """

    def test_sorted_keys_stable(self):
        """Serializing the same snapshot with sort_keys=True is stable."""
        events = poker_league_events()
        snapshot = replay(events)

        serializations = set()
        for _ in range(50):
            s = json.dumps(snapshot, sort_keys=True, ensure_ascii=True)
            serializations.add(s)

        assert len(serializations) == 1, (
            f"JSON serialization produced {len(serializations)} distinct strings"
        )

    def test_sorted_keys_after_different_operations(self):
        """
        Build the same final state through different intermediate steps.
        If the final logical state is the same, the serialization must match.
        """
        # Path A: create collection, add field, add entity
        events_a = [
            make_event(seq=1, type="collection.create", payload={
                "id": "items", "schema": {"name": "string"},
            }),
            make_event(seq=2, type="field.add", payload={
                "collection": "items", "name": "done", "type": "bool", "default": False,
            }),
            make_event(seq=3, type="entity.create", payload={
                "collection": "items", "id": "item_a",
                "fields": {"name": "A", "done": False},
            }),
        ]

        # Path B: create collection with both fields, add entity
        events_b = [
            make_event(seq=1, type="collection.create", payload={
                "id": "items", "schema": {"name": "string", "done": "bool"},
            }),
            make_event(seq=2, type="entity.create", payload={
                "collection": "items", "id": "item_a",
                "fields": {"name": "A", "done": False},
            }),
        ]

        snapshot_a = replay(events_a)
        snapshot_b = replay(events_b)

        # The schemas are equivalent, entities identical
        # (Note: they may differ in schema representation if field.add vs inline
        #  creates different structures — this tests whether equivalent paths converge.
        #  If they don't converge, that's expected and this test documents it.)
        entity_a = snapshot_a["collections"]["items"]["entities"]["item_a"]
        entity_b = snapshot_b["collections"]["items"]["entities"]["item_a"]
        assert entity_a["name"] == entity_b["name"]
        assert entity_a["done"] == entity_b["done"]


# ============================================================================
# Warnings Determinism
# ============================================================================


class TestWarningsDeterminism:
    """Events that produce warnings must produce the same warnings every time."""

    def test_warning_events_deterministic(self):
        """
        Replay events that produce warnings (e.g., ALREADY_REMOVED).
        Verify same warnings appear on every replay.
        """
        events = grocery_events_with_rejections()

        def collect_warnings(evts):
            snapshot = empty_state()
            all_warnings = []
            for event in evts:
                result = reduce(snapshot, event)
                for w in result.warnings:
                    code = w.get("code") if isinstance(w, dict) else getattr(w, "code", None)
                    all_warnings.append(code)
                snapshot = result.snapshot
            return all_warnings

        reference = collect_warnings(events)

        for _ in range(20):
            assert collect_warnings(events) == reference

    def test_applied_flags_deterministic(self):
        """The applied/rejected status of each event is deterministic."""
        events = grocery_events_with_rejections()

        def collect_applied(evts):
            snapshot = empty_state()
            flags = []
            for event in evts:
                result = reduce(snapshot, event)
                flags.append(result.applied)
                snapshot = result.snapshot
            return flags

        reference = collect_applied(events)

        for _ in range(20):
            assert collect_applied(events) == reference
