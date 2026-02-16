"""
AIde Reducer -- Walkthrough Tests (Category 10)

End-to-end scenario tests that simulate realistic user sessions, applying
events step-by-step and verifying the final snapshot matches expected state
exactly.

From the spec (aide_reducer_spec.md, "Testing Strategy"):
  "10. Walkthrough. Full grocery list scenario: create collection, add 5
   items, check off 2, add a field (category), remove an item, change
   store. Verify final state matches expected snapshot exactly."

These tests are the integration-level proof that the reducer works as a
coherent whole — not just per-primitive, but as a sequence of operations
that a real user would perform through AIde's conversational interface.

Walkthroughs:
  1. Grocery List — the spec's canonical scenario
  2. Poker League — multi-collection with relationships, views, blocks
  3. Wedding Seating — relationships, constraints, cardinality enforcement
  4. Budget Tracker — schema evolution from simple to complex

Reference: aide_reducer_spec.md, aide_primitive_schemas.md, aide_mvp_checklist.md
"""

import json
import pytest

from engine.kernel.reducer import reduce, empty_state, replay
from engine.kernel.events import make_event


# ============================================================================
# Helpers
# ============================================================================


def active_entities(snapshot, collection_id):
    """Return dict of non-removed entities in a collection."""
    coll = snapshot["collections"].get(collection_id, {})
    return {
        eid: e
        for eid, e in coll.get("entities", {}).items()
        if not e.get("_removed")
    }


def active_relationships(snapshot, rel_type=None):
    """Return relationships where both endpoints are non-removed."""
    rels = snapshot.get("relationships", [])
    if rel_type:
        rels = [r for r in rels if r.get("type") == rel_type]

    active = []
    for rel in rels:
        from_coll, from_eid = rel["from"].split("/")
        to_coll, to_eid = rel["to"].split("/")
        from_entity = snapshot["collections"].get(from_coll, {}).get("entities", {}).get(from_eid)
        to_entity = snapshot["collections"].get(to_coll, {}).get("entities", {}).get(to_eid)
        from_collection = snapshot["collections"].get(from_coll, {})
        to_collection = snapshot["collections"].get(to_coll, {})
        if (
            from_entity and not from_entity.get("_removed")
            and to_entity and not to_entity.get("_removed")
            and not from_collection.get("_removed")
            and not to_collection.get("_removed")
        ):
            active.append(rel)
    return active


# ============================================================================
# 1. Grocery List Walkthrough (the spec's canonical scenario)
# ============================================================================


class TestGroceryListWalkthrough:
    """
    The exact scenario from the spec:
      1. Create collection
      2. Add 5 items
      3. Check off 2
      4. Add a field (category)
      5. Remove an item
      6. Change store
      Verify final state matches expected snapshot exactly.
    """

    def test_full_grocery_walkthrough(self):
        snapshot = empty_state()
        seq = 0

        def step(event_type, payload, should_apply=True):
            nonlocal snapshot, seq
            seq += 1
            result = reduce(snapshot, make_event(seq=seq, type=event_type, payload=payload))
            assert result.applied == should_apply, (
                f"Step {seq} ({event_type}): "
                f"expected applied={should_apply}, got {result.applied}"
                f"{': ' + result.error if result.error else ''}"
            )
            snapshot = result.snapshot
            return result

        # ── Step 1: Create the grocery list collection ──
        step("collection.create", {
            "id": "grocery_list",
            "name": "Grocery List",
            "schema": {
                "name": "string",
                "store": "string?",
                "checked": "bool",
            },
        })

        assert "grocery_list" in snapshot["collections"]
        assert snapshot["collections"]["grocery_list"]["entities"] == {}

        # ── Step 2: Add 5 items ──
        items = [
            ("item_milk",   {"name": "Milk",          "store": "Whole Foods", "checked": False}),
            ("item_eggs",   {"name": "Eggs",          "store": "Costco",      "checked": False}),
            ("item_bread",  {"name": "Sourdough",     "store": "Whole Foods", "checked": False}),
            ("item_butter", {"name": "Butter",        "store": None,          "checked": False}),
            ("item_olive",  {"name": "Olive Oil",     "store": "Trader Joe's","checked": False}),
        ]
        for item_id, fields in items:
            step("entity.create", {
                "collection": "grocery_list",
                "id": item_id,
                "fields": fields,
            })

        assert len(active_entities(snapshot, "grocery_list")) == 5
        assert snapshot["collections"]["grocery_list"]["entities"]["item_milk"]["name"] == "Milk"
        assert snapshot["collections"]["grocery_list"]["entities"]["item_butter"]["store"] is None

        # ── Step 3: Check off 2 items (Milk and Eggs) ──
        step("entity.update", {
            "ref": "grocery_list/item_milk",
            "fields": {"checked": True},
        })
        step("entity.update", {
            "ref": "grocery_list/item_eggs",
            "fields": {"checked": True},
        })

        assert snapshot["collections"]["grocery_list"]["entities"]["item_milk"]["checked"] is True
        assert snapshot["collections"]["grocery_list"]["entities"]["item_eggs"]["checked"] is True
        assert snapshot["collections"]["grocery_list"]["entities"]["item_bread"]["checked"] is False

        # ── Step 4: Add a field (category) — schema evolution ──
        step("field.add", {
            "collection": "grocery_list",
            "name": "category",
            "type": "string?",
        })

        schema = snapshot["collections"]["grocery_list"]["schema"]
        assert "category" in schema
        assert schema["category"] == "string?"

        # All existing entities backfilled with null
        for eid, entity in snapshot["collections"]["grocery_list"]["entities"].items():
            assert "category" in entity, f"{eid} missing category"
            assert entity["category"] is None

        # Set categories on some items
        step("entity.update", {
            "ref": "grocery_list/item_milk",
            "fields": {"category": "dairy"},
        })
        step("entity.update", {
            "ref": "grocery_list/item_eggs",
            "fields": {"category": "dairy"},
        })
        step("entity.update", {
            "ref": "grocery_list/item_bread",
            "fields": {"category": "bakery"},
        })

        # ── Step 5: Remove an item (Butter — decided we don't need it) ──
        step("entity.remove", {"ref": "grocery_list/item_butter"})

        assert snapshot["collections"]["grocery_list"]["entities"]["item_butter"]["_removed"] is True
        assert len(active_entities(snapshot, "grocery_list")) == 4

        # ── Step 6: Change store (Olive Oil was at Trader Joe's, now Whole Foods) ──
        step("entity.update", {
            "ref": "grocery_list/item_olive",
            "fields": {"store": "Whole Foods"},
        })

        assert snapshot["collections"]["grocery_list"]["entities"]["item_olive"]["store"] == "Whole Foods"

        # ══════════════════════════════════════════════════════
        # Final State Verification
        # ══════════════════════════════════════════════════════

        coll = snapshot["collections"]["grocery_list"]

        # Schema
        assert coll["schema"] == {
            "name": "string",
            "store": "string?",
            "checked": "bool",
            "category": "string?",
        }
        assert coll["_removed"] is False

        # Active entities (4 — Butter removed)
        active = active_entities(snapshot, "grocery_list")
        assert set(active.keys()) == {"item_milk", "item_eggs", "item_bread", "item_olive"}

        # item_milk: checked, dairy, Whole Foods
        milk = coll["entities"]["item_milk"]
        assert milk["name"] == "Milk"
        assert milk["store"] == "Whole Foods"
        assert milk["checked"] is True
        assert milk["category"] == "dairy"
        assert milk["_removed"] is False

        # item_eggs: checked, dairy, Costco
        eggs = coll["entities"]["item_eggs"]
        assert eggs["name"] == "Eggs"
        assert eggs["store"] == "Costco"
        assert eggs["checked"] is True
        assert eggs["category"] == "dairy"

        # item_bread: unchecked, bakery, Whole Foods
        bread = coll["entities"]["item_bread"]
        assert bread["name"] == "Sourdough"
        assert bread["store"] == "Whole Foods"
        assert bread["checked"] is False
        assert bread["category"] == "bakery"

        # item_butter: REMOVED but data preserved
        butter = coll["entities"]["item_butter"]
        assert butter["_removed"] is True
        assert butter["name"] == "Butter"

        # item_olive: unchecked, no category, Whole Foods (changed)
        olive = coll["entities"]["item_olive"]
        assert olive["name"] == "Olive Oil"
        assert olive["store"] == "Whole Foods"
        assert olive["checked"] is False
        assert olive["category"] is None

    def test_grocery_replay_matches_incremental(self):
        """The grocery walkthrough produces the same result via replay."""
        events = []
        snapshot = empty_state()
        seq = 0

        def step(event_type, payload):
            nonlocal snapshot, seq
            seq += 1
            event = make_event(seq=seq, type=event_type, payload=payload)
            events.append(event)
            result = reduce(snapshot, event)
            snapshot = result.snapshot

        step("collection.create", {
            "id": "grocery_list", "name": "Grocery List",
            "schema": {"name": "string", "store": "string?", "checked": "bool"},
        })
        for item_id, fields in [
            ("item_milk",   {"name": "Milk",      "store": "Whole Foods", "checked": False}),
            ("item_eggs",   {"name": "Eggs",      "store": "Costco",      "checked": False}),
            ("item_bread",  {"name": "Sourdough", "store": "Whole Foods", "checked": False}),
            ("item_butter", {"name": "Butter",    "store": None,          "checked": False}),
            ("item_olive",  {"name": "Olive Oil", "store": "Trader Joe's","checked": False}),
        ]:
            step("entity.create", {"collection": "grocery_list", "id": item_id, "fields": fields})
        step("entity.update", {"ref": "grocery_list/item_milk", "fields": {"checked": True}})
        step("entity.update", {"ref": "grocery_list/item_eggs", "fields": {"checked": True}})
        step("field.add", {"collection": "grocery_list", "name": "category", "type": "string?"})
        step("entity.update", {"ref": "grocery_list/item_milk", "fields": {"category": "dairy"}})
        step("entity.update", {"ref": "grocery_list/item_eggs", "fields": {"category": "dairy"}})
        step("entity.update", {"ref": "grocery_list/item_bread", "fields": {"category": "bakery"}})
        step("entity.remove", {"ref": "grocery_list/item_butter"})
        step("entity.update", {"ref": "grocery_list/item_olive", "fields": {"store": "Whole Foods"}})

        replayed = replay(events)
        assert json.dumps(snapshot, sort_keys=True) == json.dumps(replayed, sort_keys=True)


# ============================================================================
# 2. Poker League Walkthrough
# ============================================================================


class TestPokerLeagueWalkthrough:
    """
    Multi-collection scenario with relationships, views, blocks, styles:
      1. Create roster + schedule collections
      2. Add 6 players and 2 games
      3. Assign hosts (relationship, many_to_one)
      4. Create views and page layout (blocks)
      5. A player drops out (entity remove)
      6. Substitute player joins, host reassigned
      7. Schema evolves (add rating field)
      8. Style the page
    """

    def test_full_poker_walkthrough(self):
        snapshot = empty_state()
        seq = 0

        def step(event_type, payload):
            nonlocal snapshot, seq
            seq += 1
            result = reduce(snapshot, make_event(seq=seq, type=event_type, payload=payload))
            assert result.applied, f"Step {seq} ({event_type}) rejected: {result.error}"
            snapshot = result.snapshot
            return result

        # ── 1. Create collections ──
        step("collection.create", {
            "id": "roster", "name": "Roster",
            "schema": {"name": "string", "status": "string", "snack_duty": "bool"},
        })
        step("collection.create", {
            "id": "schedule", "name": "Schedule",
            "schema": {"date": "date", "status": "string"},
        })

        # ── 2. Add players and games ──
        for pid, name in [("mike", "Mike"), ("dave", "Dave"), ("linda", "Linda"),
                          ("steve", "Steve"), ("rachel", "Rachel"), ("tom", "Tom")]:
            step("entity.create", {
                "collection": "roster", "id": f"player_{pid}",
                "fields": {"name": name, "status": "active", "snack_duty": False},
            })

        step("entity.create", {
            "collection": "schedule", "id": "game_feb27",
            "fields": {"date": "2026-02-27", "status": "confirmed"},
        })
        step("entity.create", {
            "collection": "schedule", "id": "game_mar13",
            "fields": {"date": "2026-03-13", "status": "tentative"},
        })

        assert len(active_entities(snapshot, "roster")) == 6
        assert len(active_entities(snapshot, "schedule")) == 2

        # ── 3. Assign hosts ──
        # one_to_one: each player hosts one game, each game has one host
        step("relationship.set", {
            "from": "roster/player_dave", "to": "schedule/game_feb27",
            "type": "hosting", "cardinality": "one_to_one",
        })
        step("relationship.set", {
            "from": "roster/player_linda", "to": "schedule/game_mar13",
            "type": "hosting",
        })

        # Dave is snack duty for his hosting
        step("entity.update", {
            "ref": "roster/player_dave",
            "fields": {"snack_duty": True},
        })

        assert len(active_relationships(snapshot, "hosting")) == 2

        # ── 4. Create views and page layout ──
        step("view.create", {
            "id": "roster_view", "type": "list", "source": "roster",
            "config": {"show_fields": ["name", "status"], "sort_by": "name"},
        })
        step("view.create", {
            "id": "schedule_view", "type": "table", "source": "schedule",
            "config": {"show_fields": ["date", "status"]},
        })

        step("block.set", {
            "id": "block_title", "type": "heading", "parent": "block_root",
            "props": {"level": 1, "content": "Poker League"},
        })
        step("block.set", {
            "id": "block_next", "type": "metric", "parent": "block_root",
            "props": {"label": "Next game", "value": "Thu Feb 27 at Dave's"},
        })
        step("block.set", {
            "id": "block_roster", "type": "collection_view", "parent": "block_root",
            "props": {"source": "roster", "view": "roster_view"},
        })
        step("block.set", {
            "id": "block_schedule", "type": "collection_view", "parent": "block_root",
            "props": {"source": "schedule", "view": "schedule_view"},
        })

        # ── 5. Tom drops out ──
        step("entity.remove", {"ref": "roster/player_tom"})

        assert len(active_entities(snapshot, "roster")) == 5
        assert snapshot["collections"]["roster"]["entities"]["player_tom"]["_removed"] is True

        # ── 6. Sub joins, host reassigned ──
        step("entity.create", {
            "collection": "roster", "id": "player_amy",
            "fields": {"name": "Amy", "status": "active", "snack_duty": False},
        })

        # Linda can't host Mar 13 anymore — Rachel takes over
        step("relationship.set", {
            "from": "roster/player_rachel", "to": "schedule/game_mar13",
            "type": "hosting",
        })

        # Verify auto-unlink: Linda no longer hosting
        hosting_mar13 = [
            r for r in active_relationships(snapshot, "hosting")
            if r["to"] == "schedule/game_mar13"
        ]
        assert len(hosting_mar13) == 1
        assert hosting_mar13[0]["from"] == "roster/player_rachel"

        assert len(active_entities(snapshot, "roster")) == 6  # 5 original - Tom + Amy

        # ── 7. Schema evolves: add rating ──
        step("field.add", {
            "collection": "roster", "name": "rating",
            "type": "int", "default": 1000,
        })

        # All active entities should have rating=1000
        for eid, entity in active_entities(snapshot, "roster").items():
            assert entity["rating"] == 1000, f"{eid} missing rating"

        step("entity.update", {
            "ref": "roster/player_mike",
            "fields": {"rating": 1350},
        })

        # ── 8. Style the page ──
        step("style.set", {
            "primary_color": "#2d3748",
            "font_family": "Inter",
            "density": "comfortable",
        })
        step("meta.update", {
            "title": "Poker League — Spring 2026",
            "identity": "Biweekly Thursday poker. Rotating hosts.",
        })
        step("meta.annotate", {
            "note": "League started with 6 players, Tom replaced by Amy.",
            "pinned": False,
        })

        # ══════════════════════════════════════════════════════
        # Final State Verification
        # ══════════════════════════════════════════════════════

        # Collections
        assert set(snapshot["collections"].keys()) == {"roster", "schedule"}

        # Roster: 7 total entities (6 active + Tom removed)
        roster_entities = snapshot["collections"]["roster"]["entities"]
        assert len(roster_entities) == 7
        assert len(active_entities(snapshot, "roster")) == 6

        # Schema evolved
        assert "rating" in snapshot["collections"]["roster"]["schema"]

        # Mike's rating updated
        assert roster_entities["player_mike"]["rating"] == 1350
        assert roster_entities["player_amy"]["rating"] == 1000

        # Tom removed but preserved
        assert roster_entities["player_tom"]["_removed"] is True
        assert roster_entities["player_tom"]["name"] == "Tom"

        # Relationships: Dave→Feb27, Rachel→Mar13
        hosting = active_relationships(snapshot, "hosting")
        assert len(hosting) == 2
        host_map = {r["to"]: r["from"] for r in hosting}
        assert host_map["schedule/game_feb27"] == "roster/player_dave"
        assert host_map["schedule/game_mar13"] == "roster/player_rachel"

        # Views exist
        assert "roster_view" in snapshot["views"]
        assert "schedule_view" in snapshot["views"]

        # Block tree
        root_children = snapshot["blocks"]["block_root"]["children"]
        assert root_children == ["block_title", "block_next", "block_roster", "block_schedule"]

        # Styles
        assert snapshot["styles"]["primary_color"] == "#2d3748"

        # Meta
        assert snapshot["meta"]["title"] == "Poker League — Spring 2026"
        assert len(snapshot["annotations"]) == 1


# ============================================================================
# 3. Wedding Seating Walkthrough
# ============================================================================


class TestWeddingSeatingWalkthrough:
    """
    Relationship-heavy scenario: seat guests at tables with constraints.
      1. Create guests + tables collections
      2. Add guests and tables
      3. Seat guests (many_to_one relationships)
      4. Add constraint: keep feuding relatives apart
      5. Move a guest (auto-unlink via many_to_one)
      6. Remove a guest who RSVPed no
      7. Verify final seating chart
    """

    def test_full_wedding_walkthrough(self):
        snapshot = empty_state()
        seq = 0

        def step(event_type, payload):
            nonlocal snapshot, seq
            seq += 1
            result = reduce(snapshot, make_event(seq=seq, type=event_type, payload=payload))
            assert result.applied, f"Step {seq} ({event_type}) rejected: {result.error}"
            snapshot = result.snapshot
            return result

        # ── 1. Collections ──
        step("collection.create", {
            "id": "guests", "name": "Guests",
            "schema": {"name": "string", "group": "string?", "dietary": "string?"},
        })
        step("collection.create", {
            "id": "tables", "name": "Tables",
            "schema": {"name": "string", "capacity": "int"},
        })

        # ── 2. Guests and tables ──
        guests_data = [
            ("guest_linda", "Linda", "bride", None),
            ("guest_steve", "Steve", "bride", "vegetarian"),
            ("guest_mike",  "Mike",  "groom", None),
            ("guest_dave",  "Dave",  "groom", "gluten-free"),
            ("guest_rachel","Rachel","bride", None),
            ("guest_tom",   "Tom",   "groom", None),
            ("guest_carol", "Carol", "bride", "vegan"),
            ("guest_jeff",  "Jeff",  "groom", None),
        ]
        for gid, name, group, dietary in guests_data:
            step("entity.create", {
                "collection": "guests", "id": gid,
                "fields": {"name": name, "group": group, "dietary": dietary},
            })

        for tid, name, cap in [("table_1", "Table 1", 4), ("table_2", "Table 2", 4),
                                ("table_3", "Table 3", 4)]:
            step("entity.create", {
                "collection": "tables", "id": tid,
                "fields": {"name": name, "capacity": cap},
            })

        # ── 3. Initial seating ──
        seating = [
            ("guest_linda",  "table_1"),
            ("guest_steve",  "table_1"),
            ("guest_mike",   "table_1"),
            ("guest_dave",   "table_2"),
            ("guest_rachel", "table_2"),
            ("guest_tom",    "table_2"),
            ("guest_carol",  "table_3"),
            ("guest_jeff",   "table_3"),
        ]
        for gid, tid in seating:
            step("relationship.set", {
                "from": f"guests/{gid}", "to": f"tables/{tid}",
                "type": "seated_at", "cardinality": "many_to_one",
            })

        assert len(active_relationships(snapshot, "seated_at")) == 8

        # ── 4. Constraint: Linda and Steve shouldn't be at the same table ──
        step("relationship.constrain", {
            "id": "no_linda_steve",
            "rule": "exclude_pair",
            "entities": ["guests/guest_linda", "guests/guest_steve"],
            "relationship_type": "seated_at",
            "message": "Keep Linda and Steve at different tables",
        })

        # ── 5. Move Steve to table 2 (auto-unlinks from table 1) ──
        step("relationship.set", {
            "from": "guests/guest_steve", "to": "tables/table_2",
            "type": "seated_at",
        })

        # Verify Steve moved: only 1 seated_at for Steve, and it's table 2
        steve_rels = [
            r for r in active_relationships(snapshot, "seated_at")
            if r["from"] == "guests/guest_steve"
        ]
        assert len(steve_rels) == 1
        assert steve_rels[0]["to"] == "tables/table_2"

        # ── 6. Jeff can't make it ──
        step("entity.remove", {"ref": "guests/guest_jeff"})

        assert snapshot["collections"]["guests"]["entities"]["guest_jeff"]["_removed"] is True

        # ══════════════════════════════════════════════════════
        # Final Seating Chart Verification
        # ══════════════════════════════════════════════════════

        active_seated = active_relationships(snapshot, "seated_at")

        # 7 active guests seated (Jeff removed)
        assert len(active_seated) == 7

        # Build seating map: guest → table
        seat_map = {r["from"]: r["to"] for r in active_seated}

        # Table 1: Linda, Mike (Steve moved away)
        table_1_guests = [g for g, t in seat_map.items() if t == "tables/table_1"]
        assert set(table_1_guests) == {"guests/guest_linda", "guests/guest_mike"}

        # Table 2: Dave, Rachel, Tom, Steve (Steve moved here)
        table_2_guests = [g for g, t in seat_map.items() if t == "tables/table_2"]
        assert set(table_2_guests) == {
            "guests/guest_dave", "guests/guest_rachel",
            "guests/guest_tom", "guests/guest_steve",
        }

        # Table 3: Carol (Jeff removed)
        table_3_guests = [g for g, t in seat_map.items() if t == "tables/table_3"]
        assert set(table_3_guests) == {"guests/guest_carol"}

        # Linda and Steve are NOT at the same table
        assert seat_map["guests/guest_linda"] != seat_map["guests/guest_steve"]

        # Constraint exists
        assert any(c["id"] == "no_linda_steve" for c in snapshot["constraints"])

        # 7 active guests, 3 active tables
        assert len(active_entities(snapshot, "guests")) == 7
        assert len(active_entities(snapshot, "tables")) == 3


# ============================================================================
# 4. Budget Tracker Walkthrough
# ============================================================================


class TestBudgetTrackerWalkthrough:
    """
    Schema evolution scenario: start simple, grow complex over time.
      1. Start with basic expenses (description, amount)
      2. User mentions categories → L3 adds field
      3. User mentions who paid → L3 adds field
      4. Evolve category from freetext to enum
      5. Add a view, blocks, style
      6. Remove a duplicate entry
      7. Rename a field
    """

    def test_full_budget_walkthrough(self):
        snapshot = empty_state()
        seq = 0

        def step(event_type, payload):
            nonlocal snapshot, seq
            seq += 1
            result = reduce(snapshot, make_event(seq=seq, type=event_type, payload=payload))
            assert result.applied, f"Step {seq} ({event_type}) rejected: {result.error}"
            snapshot = result.snapshot
            return result

        # ── 1. Basic budget ──
        step("collection.create", {
            "id": "expenses", "name": "Expenses",
            "schema": {"description": "string", "amount": "float", "paid": "bool"},
        })

        step("entity.create", {
            "collection": "expenses", "id": "exp_dinner",
            "fields": {"description": "Team dinner", "amount": 245.50, "paid": True},
        })
        step("entity.create", {
            "collection": "expenses", "id": "exp_supplies",
            "fields": {"description": "Office supplies", "amount": 67.99, "paid": False},
        })
        step("entity.create", {
            "collection": "expenses", "id": "exp_software",
            "fields": {"description": "Software license", "amount": 199.00, "paid": True},
        })
        step("entity.create", {
            "collection": "expenses", "id": "exp_duplicate",
            "fields": {"description": "Team dinner (duplicate)", "amount": 245.50, "paid": True},
        })

        # ── 2. User mentions categories → schema evolves ──
        step("field.add", {
            "collection": "expenses", "name": "category",
            "type": "string?",
        })

        # Backfill: all entities now have category=null
        for entity in snapshot["collections"]["expenses"]["entities"].values():
            assert "category" in entity

        step("entity.update", {
            "ref": "expenses/exp_dinner",
            "fields": {"category": "meals"},
        })
        step("entity.update", {
            "ref": "expenses/exp_supplies",
            "fields": {"category": "office"},
        })
        step("entity.update", {
            "ref": "expenses/exp_software",
            "fields": {"category": "software"},
        })

        # ── 3. User mentions who paid → another field ──
        step("field.add", {
            "collection": "expenses", "name": "paid_by",
            "type": "string?",
        })

        step("entity.update", {
            "ref": "expenses/exp_dinner",
            "fields": {"paid_by": "Alice"},
        })
        step("entity.update", {
            "ref": "expenses/exp_software",
            "fields": {"paid_by": "Bob"},
        })

        # ── 4. Evolve category from freetext to enum ──
        step("field.update", {
            "collection": "expenses", "name": "category",
            "type": {"enum": ["meals", "office", "software", "travel", "other"]},
        })

        schema = snapshot["collections"]["expenses"]["schema"]
        assert schema["category"] == {"enum": ["meals", "office", "software", "travel", "other"]}

        # ── 5. Add view and page layout ──
        step("view.create", {
            "id": "expense_view", "type": "table", "source": "expenses",
            "config": {
                "show_fields": ["description", "amount", "category", "paid", "paid_by"],
                "sort_by": "amount",
                "sort_order": "desc",
            },
        })

        step("block.set", {
            "id": "block_title", "type": "heading", "parent": "block_root",
            "props": {"level": 1, "content": "Team Budget"},
        })
        step("block.set", {
            "id": "block_expenses", "type": "collection_view", "parent": "block_root",
            "props": {"source": "expenses", "view": "expense_view"},
        })

        step("style.set", {
            "primary_color": "#1a365d",
            "font_family": "IBM Plex Sans",
        })

        step("meta.update", {
            "title": "Q1 Team Budget",
        })

        # ── 6. Remove duplicate entry ──
        step("entity.remove", {"ref": "expenses/exp_duplicate"})

        # ── 7. Rename field: paid → settled ──
        step("field.update", {
            "collection": "expenses", "name": "paid",
            "rename": "settled",
        })

        # ══════════════════════════════════════════════════════
        # Final State Verification
        # ══════════════════════════════════════════════════════

        coll = snapshot["collections"]["expenses"]

        # Schema has evolved fields and rename
        assert "settled" in coll["schema"]
        assert "paid" not in coll["schema"]
        assert "category" in coll["schema"]
        assert "paid_by" in coll["schema"]
        assert coll["schema"]["category"] == {"enum": ["meals", "office", "software", "travel", "other"]}

        # 3 active entities (duplicate removed)
        active = active_entities(snapshot, "expenses")
        assert len(active) == 3

        # Field renamed across entities
        dinner = coll["entities"]["exp_dinner"]
        assert "settled" in dinner
        assert "paid" not in dinner
        assert dinner["settled"] is True
        assert dinner["category"] == "meals"
        assert dinner["paid_by"] == "Alice"
        assert dinner["amount"] == 245.50

        supplies = coll["entities"]["exp_supplies"]
        assert supplies["settled"] is False
        assert supplies["category"] == "office"
        assert supplies["paid_by"] is None

        software = coll["entities"]["exp_software"]
        assert software["settled"] is True
        assert software["paid_by"] == "Bob"

        # Duplicate removed
        assert coll["entities"]["exp_duplicate"]["_removed"] is True

        # View + blocks
        assert "expense_view" in snapshot["views"]
        root_children = snapshot["blocks"]["block_root"]["children"]
        assert "block_title" in root_children
        assert "block_expenses" in root_children

        # Meta
        assert snapshot["meta"]["title"] == "Q1 Team Budget"

        # Styles
        assert snapshot["styles"]["primary_color"] == "#1a365d"


# ============================================================================
# 5. MVP Checklist Scenario (from aide_mvp_checklist.md)
# ============================================================================


class TestMvpGrocerySignalWalkthrough:
    """
    From aide_mvp_checklist.md:
      "Can you and your partner manage groceries through a Signal group
       chat with an aide, and share the live page URL with anyone?"

    Simulates a multi-turn conversation:
      Partner A: "we need milk, eggs, and sourdough"
      Partner B: "also get olive oil from Trader Joe's"
      Partner A: "got the milk and eggs" (checks them off)
      Partner B: "oh and can we track which store for each item?"
      Partner A: "actually skip the sourdough, got some yesterday"
    """

    def test_multi_turn_conversation(self):
        snapshot = empty_state()
        seq = 0

        def step(event_type, payload):
            nonlocal snapshot, seq
            seq += 1
            result = reduce(snapshot, make_event(seq=seq, type=event_type, payload=payload))
            assert result.applied, f"Step {seq} ({event_type}) rejected: {result.error}"
            snapshot = result.snapshot

        # ── Turn 1: L3 creates the aide from first message ──
        # "we need milk, eggs, and sourdough"
        step("collection.create", {
            "id": "grocery_list", "name": "Grocery List",
            "schema": {"name": "string", "checked": "bool"},
        })
        step("entity.create", {
            "collection": "grocery_list", "id": "item_milk",
            "fields": {"name": "Milk", "checked": False},
        })
        step("entity.create", {
            "collection": "grocery_list", "id": "item_eggs",
            "fields": {"name": "Eggs", "checked": False},
        })
        step("entity.create", {
            "collection": "grocery_list", "id": "item_sourdough",
            "fields": {"name": "Sourdough", "checked": False},
        })
        step("meta.update", {"title": "Grocery List"})
        step("view.create", {
            "id": "grocery_view", "type": "list", "source": "grocery_list",
            "config": {"show_fields": ["name", "checked"]},
        })
        step("block.set", {
            "id": "block_title", "type": "heading", "parent": "block_root",
            "props": {"level": 1, "content": "Grocery List"},
        })
        step("block.set", {
            "id": "block_list", "type": "collection_view", "parent": "block_root",
            "props": {"source": "grocery_list", "view": "grocery_view"},
        })

        # ── Turn 2: Partner B adds olive oil with store ──
        # "also get olive oil from Trader Joe's"
        # L3 sees new field (store) → schema evolution
        step("field.add", {
            "collection": "grocery_list", "name": "store",
            "type": "string?",
        })
        step("entity.create", {
            "collection": "grocery_list", "id": "item_olive_oil",
            "fields": {"name": "Olive Oil", "checked": False, "store": "Trader Joe's"},
        })

        # Existing items backfilled with store=null
        assert snapshot["collections"]["grocery_list"]["entities"]["item_milk"]["store"] is None

        # ── Turn 3: Partner A checks off milk and eggs ──
        # "got the milk and eggs"
        step("entity.update", {"ref": "grocery_list/item_milk", "fields": {"checked": True}})
        step("entity.update", {"ref": "grocery_list/item_eggs", "fields": {"checked": True}})

        # ── Turn 4: Partner B wants store tracking visible ──
        # "can we track which store for each item?"
        step("view.update", {
            "id": "grocery_view",
            "config": {"show_fields": ["name", "store", "checked"]},
        })

        # ── Turn 5: Partner A removes sourdough ──
        # "skip the sourdough, got some yesterday"
        step("entity.remove", {"ref": "grocery_list/item_sourdough"})

        # ══════════════════════════════════════════════════════
        # Final State — what the shared page URL shows
        # ══════════════════════════════════════════════════════

        active = active_entities(snapshot, "grocery_list")
        assert len(active) == 3  # milk, eggs, olive oil (sourdough removed)
        assert set(active.keys()) == {"item_milk", "item_eggs", "item_olive_oil"}

        # Schema evolved to include store
        assert "store" in snapshot["collections"]["grocery_list"]["schema"]

        # Checked status
        assert active["item_milk"]["checked"] is True
        assert active["item_eggs"]["checked"] is True
        assert active["item_olive_oil"]["checked"] is False

        # Store field
        assert active["item_olive_oil"]["store"] == "Trader Joe's"
        assert active["item_milk"]["store"] is None

        # View updated to show store
        view_config = snapshot["views"]["grocery_view"]["config"]
        assert "store" in view_config["show_fields"]

        # Page layout intact
        assert snapshot["meta"]["title"] == "Grocery List"
        root_children = snapshot["blocks"]["block_root"]["children"]
        assert "block_title" in root_children
        assert "block_list" in root_children
