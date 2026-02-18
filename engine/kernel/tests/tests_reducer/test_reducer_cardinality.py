"""
AIde Reducer -- Cardinality Tests (v3 Unified Entity Model)

In v3, there are no relationship primitives (no collection.add_member,
no relationship.link, etc.). Instead, cardinality is expressed through
entity path addressing: entities can be nested at multiple levels.

These tests cover path addressing:
  - Depth 1: top-level entity CRUD
  - Depth 2: child entity via path (entity_id/field/child_id)
  - Depth 3: grandchild entity via extended path
  - Multiple children at the same level
  - Child entity IDs are unique within their parent field
  - Paths with invalid segment count are rejected
  - Accessing a non-existent path is rejected cleanly

Note: v3 does not enforce cardinality constraints (one-to-one, one-to-many)
at the reducer level — cardinality is an application-level concern defined
in the TypeScript interface (Record<string, T> = zero-to-many).
"""

import pytest

from engine.kernel.events import make_event
from engine.kernel.reducer import empty_state, reduce

# ============================================================================
# Helpers
# ============================================================================

ITEM_INTERFACE = "interface Item { name: string; }"


def make_schema_event(seq, schema_id, iface="interface Item { name: string; }"):
    return make_event(seq=seq, type="schema.create", payload={
        "id": schema_id,
        "interface": iface,
        "render_html": "<span>{{name}}</span>",
        "render_text": "{{name}}",
    })


# ============================================================================
# 1. Depth 1: top-level entity addressing
# ============================================================================

class TestDepth1Addressing:
    def test_create_top_level_entity(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "entity_a",
            "name": "Alpha",
        }))
        assert result.applied
        assert "entity_a" in result.snapshot["entities"]
        assert result.snapshot["entities"]["entity_a"]["name"] == "Alpha"

    def test_update_top_level_entity(self):
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "entity_a",
            "name": "Alpha",
        }))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="entity.update", payload={
            "id": "entity_a",
            "name": "Alpha Updated",
        }))
        assert r2.applied
        assert r2.snapshot["entities"]["entity_a"]["name"] == "Alpha Updated"

    def test_remove_top_level_entity(self):
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "entity_a",
            "name": "Alpha",
        }))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="entity.remove", payload={
            "id": "entity_a",
        }))
        assert r2.applied
        assert r2.snapshot["entities"]["entity_a"]["_removed"] is True

    def test_many_top_level_entities(self):
        snap = empty_state()
        for i in range(10):
            result = reduce(snap, make_event(seq=i + 1, type="entity.create", payload={
                "id": f"entity_{i:02d}",
                "name": f"Entity {i}",
                "index": i,
            }))
            assert result.applied
            snap = result.snapshot

        assert len(snap["entities"]) == 10
        for i in range(10):
            assert snap["entities"][f"entity_{i:02d}"]["index"] == i


# ============================================================================
# 2. Depth 2: child entities via nested field path
# ============================================================================

class TestDepth2Addressing:
    @pytest.fixture
    def state_with_parent(self):
        snap = empty_state()
        r = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "parent",
            "name": "Parent Entity",
            "children": {},
        }))
        assert r.applied
        return r.snapshot

    def test_create_child_entity_via_path(self, state_with_parent):
        result = reduce(state_with_parent, make_event(seq=2, type="entity.create", payload={
            "id": "parent/children/child_a",
            "name": "Child A",
        }))
        assert result.applied
        children = result.snapshot["entities"]["parent"]["children"]
        assert "child_a" in children
        assert children["child_a"]["name"] == "Child A"

    def test_create_multiple_children_at_same_depth(self, state_with_parent):
        r1 = reduce(state_with_parent, make_event(seq=2, type="entity.create", payload={
            "id": "parent/children/child_a",
            "name": "Child A",
        }))
        r2 = reduce(r1.snapshot, make_event(seq=3, type="entity.create", payload={
            "id": "parent/children/child_b",
            "name": "Child B",
        }))
        r3 = reduce(r2.snapshot, make_event(seq=4, type="entity.create", payload={
            "id": "parent/children/child_c",
            "name": "Child C",
        }))
        assert r3.applied

        children = r3.snapshot["entities"]["parent"]["children"]
        assert len([k for k in children if not k.startswith("_")]) == 3
        assert children["child_a"]["name"] == "Child A"
        assert children["child_b"]["name"] == "Child B"
        assert children["child_c"]["name"] == "Child C"

    def test_update_child_entity_via_path(self, state_with_parent):
        r1 = reduce(state_with_parent, make_event(seq=2, type="entity.create", payload={
            "id": "parent/children/child_a",
            "name": "Child A",
        }))
        r2 = reduce(r1.snapshot, make_event(seq=3, type="entity.update", payload={
            "id": "parent/children/child_a",
            "name": "Child A Updated",
        }))
        assert r2.applied
        children = r2.snapshot["entities"]["parent"]["children"]
        assert children["child_a"]["name"] == "Child A Updated"

    def test_remove_child_entity_via_path(self, state_with_parent):
        r1 = reduce(state_with_parent, make_event(seq=2, type="entity.create", payload={
            "id": "parent/children/child_a",
            "name": "Child A",
        }))
        r2 = reduce(state_with_parent, make_event(seq=2, type="entity.create", payload={
            "id": "parent/children/child_b",
            "name": "Child B",
        }))
        # Use r1 state, add child_b
        r3 = reduce(r1.snapshot, make_event(seq=3, type="entity.create", payload={
            "id": "parent/children/child_b",
            "name": "Child B",
        }))
        r4 = reduce(r3.snapshot, make_event(seq=4, type="entity.remove", payload={
            "id": "parent/children/child_a",
        }))
        assert r4.applied
        children = r4.snapshot["entities"]["parent"]["children"]
        assert children["child_a"]["_removed"] is True
        assert children["child_b"].get("_removed") is not True

    def test_duplicate_child_id_at_same_path_rejected(self, state_with_parent):
        r1 = reduce(state_with_parent, make_event(seq=2, type="entity.create", payload={
            "id": "parent/children/child_a",
            "name": "Child A",
        }))
        r2 = reduce(r1.snapshot, make_event(seq=3, type="entity.create", payload={
            "id": "parent/children/child_a",
            "name": "Duplicate Child A",
        }))
        assert not r2.applied
        assert "ALREADY_EXISTS" in r2.error


# ============================================================================
# 3. Depth 3: grandchild entities
# ============================================================================

class TestDepth3Addressing:
    def test_create_grandchild_entity(self):
        snap = empty_state()

        # Create grandparent with a child collection
        r1 = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "grandparent",
            "name": "Grandparent",
            "children": {
                "parent_a": {
                    "name": "Parent A",
                    "items": {},
                },
            },
        }))
        assert r1.applied

        # Create grandchild via 3-level path
        r2 = reduce(r1.snapshot, make_event(seq=2, type="entity.create", payload={
            "id": "grandparent/children/parent_a/items/grandchild_1",
            "name": "Grandchild 1",
        }))
        assert r2.applied

        items = r2.snapshot["entities"]["grandparent"]["children"]["parent_a"]["items"]
        assert "grandchild_1" in items
        assert items["grandchild_1"]["name"] == "Grandchild 1"

    def test_update_grandchild_entity(self):
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "grandparent",
            "name": "Grandparent",
            "children": {
                "parent_a": {
                    "name": "Parent A",
                    "items": {
                        "grandchild_1": {"name": "Grandchild 1"},
                    },
                },
            },
        }))
        assert r1.applied

        r2 = reduce(r1.snapshot, make_event(seq=2, type="entity.update", payload={
            "id": "grandparent/children/parent_a/items/grandchild_1",
            "name": "Grandchild 1 Updated",
        }))
        assert r2.applied
        items = r2.snapshot["entities"]["grandparent"]["children"]["parent_a"]["items"]
        assert items["grandchild_1"]["name"] == "Grandchild 1 Updated"


# ============================================================================
# 4. Invalid path addressing
# ============================================================================

class TestInvalidPaths:
    def test_path_to_nonexistent_parent_rejected(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "ghost_parent/children/child_a",
            "name": "Child",
        }))
        assert not result.applied
        # PATH_ERROR or NOT_FOUND since ghost_parent doesn't exist
        assert result.error is not None

    def test_path_with_nonexistent_field_auto_creates_collection(self):
        """The reducer auto-creates a field collection when it does not exist yet."""
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "parent",
            "name": "Parent",
            # No 'new_field' field defined yet
        }))
        assert r1.applied

        # Reducer auto-creates the field collection for child entities
        r2 = reduce(r1.snapshot, make_event(seq=2, type="entity.create", payload={
            "id": "parent/new_field/child_a",
            "name": "Child",
        }))
        assert r2.applied
        # The field was auto-created and child is inside it
        assert "child_a" in r2.snapshot["entities"]["parent"]["new_field"]

    def test_update_nonexistent_entity_rejected(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="entity.update", payload={
            "id": "ghost_entity",
            "name": "Ghost",
        }))
        assert not result.applied
        assert "NOT_FOUND" in result.error

    def test_remove_nonexistent_entity_rejected(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="entity.remove", payload={
            "id": "ghost_entity",
        }))
        assert not result.applied
        assert "NOT_FOUND" in result.error


# ============================================================================
# 5. _pos field for ordering entities at a given depth
# ============================================================================

class TestEntityPositionOrdering:
    def test_entities_can_have_pos_field(self):
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "item_a",
            "name": "Item A",
            "_pos": 1.0,
        }))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="entity.create", payload={
            "id": "item_b",
            "name": "Item B",
            "_pos": 2.0,
        }))
        r3 = reduce(r2.snapshot, make_event(seq=3, type="entity.create", payload={
            "id": "item_c",
            "name": "Item C",
            "_pos": 1.5,
        }))
        assert r3.applied

        entities = r3.snapshot["entities"]
        assert entities["item_a"]["_pos"] == 1.0
        assert entities["item_b"]["_pos"] == 2.0
        assert entities["item_c"]["_pos"] == 1.5

    def test_pos_can_be_updated(self):
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "item_a",
            "name": "Item A",
            "_pos": 1.0,
        }))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="entity.update", payload={
            "id": "item_a",
            "_pos": 0.5,
        }))
        assert r2.applied
        assert r2.snapshot["entities"]["item_a"]["_pos"] == 0.5

    def test_children_with_pos_ordering(self):
        snap = empty_state()
        r = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "list",
            "name": "My List",
            "items": {
                "item_z": {"name": "Last", "_pos": 3.0},
                "item_a": {"name": "First", "_pos": 1.0},
                "item_m": {"name": "Middle", "_pos": 2.0},
            },
        }))
        assert r.applied
        items = r.snapshot["entities"]["list"]["items"]
        assert items["item_z"]["_pos"] == 3.0
        assert items["item_a"]["_pos"] == 1.0
        assert items["item_m"]["_pos"] == 2.0
