"""
AIde Reducer -- Cascade Tests (v3 Unified Entity Model)

Tests that entity.remove cascades correctly to nested children.

In v3, entities can have child collections stored as Record fields
(nested dicts where values are child entity dicts). When the parent
entity is removed, all children should be soft-removed too (_removed: True).

Covers:
  - Top-level entity remove marks entity as _removed
  - Nested children are cascaded: all children get _removed = True
  - Deeply nested (3 levels) cascade works
  - Sibling entities are unaffected by cascade
  - Removed entity not accessible via entity.update
  - Removed entity not accessible via entity.remove (already removed)
  - Path-based remove of a single child (non-cascading remove of leaf)
  - Block cascade: block.remove removes descendants
"""


from engine.kernel.events import make_event
from engine.kernel.reducer import empty_state, reduce, replay

# ============================================================================
# Helpers
# ============================================================================

# Schema with nested items collection
LIST_INTERFACE = "interface GroceryList { name: string; items: Record<string, GroceryItem>; }"
ITEM_INTERFACE = "interface GroceryItem { name: string; }"


def build_state_with_nested_entity():
    """
    Build a state with:
      my_list (top-level, schema=grocery_list)
        items:
          item_milk (child)
          item_eggs (child)
    """
    events = [
        make_event(seq=1, type="schema.create", payload={
            "id": "grocery_list",
            "interface": LIST_INTERFACE,
            "render_html": "<ul>{{name}}</ul>",
            "render_text": "{{name}}",
        }),
        make_event(seq=2, type="entity.create", payload={
            "id": "my_list",
            "_schema": "grocery_list",
            "name": "My List",
            "items": {
                "item_milk": {"name": "Milk", "_pos": 1.0},
                "item_eggs": {"name": "Eggs", "_pos": 2.0},
            },
        }),
    ]
    return replay(events)


# ============================================================================
# 1. Top-level entity.remove
# ============================================================================

class TestTopLevelEntityRemove:
    def test_entity_remove_marks_removed(self):
        snap = build_state_with_nested_entity()
        result = reduce(snap, make_event(seq=3, type="entity.remove", payload={"id": "my_list"}))
        assert result.applied
        assert result.snapshot["entities"]["my_list"]["_removed"] is True

    def test_entity_remove_cascades_to_children(self):
        snap = build_state_with_nested_entity()
        result = reduce(snap, make_event(seq=3, type="entity.remove", payload={"id": "my_list"}))
        assert result.applied
        items = result.snapshot["entities"]["my_list"]["items"]
        assert items["item_milk"]["_removed"] is True
        assert items["item_eggs"]["_removed"] is True

    def test_entity_remove_does_not_affect_sibling_entities(self):
        snap = build_state_with_nested_entity()

        # Add a sibling entity (no schema, freeform)
        r1 = reduce(snap, make_event(seq=3, type="entity.create", payload={
            "id": "other_list",
            "name": "Other List",
        }))
        assert r1.applied

        r2 = reduce(r1.snapshot, make_event(seq=4, type="entity.remove", payload={"id": "my_list"}))
        assert r2.applied

        # other_list should not be removed
        assert r2.snapshot["entities"]["other_list"].get("_removed") is not True
        assert r2.snapshot["entities"]["other_list"]["name"] == "Other List"


# ============================================================================
# 2. Cascade through 3 levels of nesting
# ============================================================================

class TestDeepNestingCascade:
    def test_three_level_cascade(self):
        """
        Build:
          root_entity (freeform, no schema)
            children:
              child_a
                grandchildren:
                  grandchild_1
                  grandchild_2

        Remove root_entity — all descendants should be _removed.
        """
        snap = empty_state()
        r = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "root_entity",
            "name": "Root",
            "children": {
                "child_a": {
                    "name": "Child A",
                    "grandchildren": {
                        "grandchild_1": {"name": "Grandchild 1"},
                        "grandchild_2": {"name": "Grandchild 2"},
                    },
                },
            },
        }))
        assert r.applied

        r2 = reduce(r.snapshot, make_event(seq=2, type="entity.remove", payload={"id": "root_entity"}))
        assert r2.applied

        entities = r2.snapshot["entities"]
        root = entities["root_entity"]
        assert root["_removed"] is True

        child_a = root["children"]["child_a"]
        assert child_a["_removed"] is True

        grandchild_1 = child_a["grandchildren"]["grandchild_1"]
        grandchild_2 = child_a["grandchildren"]["grandchild_2"]
        assert grandchild_1["_removed"] is True
        assert grandchild_2["_removed"] is True


# ============================================================================
# 3. Removed entity not accessible for update
# ============================================================================

class TestRemovedEntityNotAccessible:
    def test_update_removed_entity_rejected(self):
        snap = build_state_with_nested_entity()
        r1 = reduce(snap, make_event(seq=3, type="entity.remove", payload={"id": "my_list"}))
        assert r1.applied

        r2 = reduce(r1.snapshot, make_event(seq=4, type="entity.update", payload={
            "id": "my_list",
            "name": "Attempted update",
        }))
        assert not r2.applied
        assert "NOT_FOUND" in r2.error

    def test_remove_already_removed_entity_rejected(self):
        snap = build_state_with_nested_entity()
        r1 = reduce(snap, make_event(seq=3, type="entity.remove", payload={"id": "my_list"}))
        assert r1.applied

        r2 = reduce(r1.snapshot, make_event(seq=4, type="entity.remove", payload={"id": "my_list"}))
        assert not r2.applied
        assert "NOT_FOUND" in r2.error


# ============================================================================
# 4. Path-based removal of a single child (leaf remove)
# ============================================================================

class TestPathBasedChildRemove:
    def test_remove_specific_child_via_path(self):
        """entity.remove with path 'my_list/items/item_milk' removes only that child."""
        snap = build_state_with_nested_entity()
        result = reduce(snap, make_event(seq=3, type="entity.remove", payload={
            "id": "my_list/items/item_milk",
        }))
        assert result.applied

        # item_milk is removed
        items = result.snapshot["entities"]["my_list"]["items"]
        assert items["item_milk"]["_removed"] is True

        # item_eggs is untouched
        assert items["item_eggs"].get("_removed") is not True
        assert items["item_eggs"]["name"] == "Eggs"

        # Parent entity (my_list) is not removed
        assert result.snapshot["entities"]["my_list"].get("_removed") is not True

    def test_remove_one_child_leaves_parent_accessible(self):
        snap = build_state_with_nested_entity()
        r1 = reduce(snap, make_event(seq=3, type="entity.remove", payload={
            "id": "my_list/items/item_milk",
        }))
        assert r1.applied

        # Parent can still be updated
        r2 = reduce(r1.snapshot, make_event(seq=4, type="entity.update", payload={
            "id": "my_list",
            "name": "Updated List Name",
        }))
        assert r2.applied
        assert r2.snapshot["entities"]["my_list"]["name"] == "Updated List Name"


# ============================================================================
# 5. Block cascade: block.remove removes descendants
# ============================================================================

class TestBlockRemoveCascade:
    def test_block_remove_cascades_to_children(self):
        snap = empty_state()

        # Create parent and children
        r1 = reduce(snap, make_event(seq=1, type="block.set", payload={
            "id": "col_list",
            "type": "column_list",
            "parent": "block_root",
        }))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="block.set", payload={
            "id": "col_a",
            "type": "column",
            "parent": "col_list",
        }))
        r3 = reduce(r2.snapshot, make_event(seq=3, type="block.set", payload={
            "id": "col_b",
            "type": "column",
            "parent": "col_list",
        }))
        r4 = reduce(r3.snapshot, make_event(seq=4, type="block.set", payload={
            "id": "heading_in_a",
            "type": "heading",
            "parent": "col_a",
            "text": "Column A header",
        }))
        assert r4.applied

        # Remove the column_list — should cascade to col_a, col_b, heading_in_a
        r5 = reduce(r4.snapshot, make_event(seq=5, type="block.remove", payload={"id": "col_list"}))
        assert r5.applied

        blocks = r5.snapshot["blocks"]
        assert "col_list" not in blocks
        assert "col_a" not in blocks
        assert "col_b" not in blocks
        assert "heading_in_a" not in blocks
        assert "block_root" in blocks  # root is untouched

    def test_block_remove_updates_parent_children_list(self):
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="block.set", payload={
            "id": "b1",
            "type": "text",
            "parent": "block_root",
            "text": "First",
        }))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="block.set", payload={
            "id": "b2",
            "type": "text",
            "parent": "block_root",
            "text": "Second",
        }))
        r3 = reduce(r2.snapshot, make_event(seq=3, type="block.remove", payload={"id": "b1"}))
        assert r3.applied

        root_children = r3.snapshot["blocks"]["block_root"]["children"]
        assert "b1" not in root_children
        assert "b2" in root_children

    def test_cannot_remove_block_root(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="block.remove", payload={"id": "block_root"}))
        assert not result.applied
        assert "CANNOT_REMOVE_ROOT" in result.error


# ============================================================================
# 6. Multiple entities — cascade is isolated
# ============================================================================

class TestCascadeIsolation:
    def test_remove_one_entity_does_not_cascade_to_unrelated_entity(self):
        events = [
            make_event(seq=1, type="entity.create", payload={
                "id": "entity_a",
                "name": "Entity A",
            }),
            make_event(seq=2, type="entity.create", payload={
                "id": "entity_b",
                "name": "Entity B",
            }),
            make_event(seq=3, type="entity.remove", payload={"id": "entity_a"}),
        ]
        snap = replay(events)

        assert snap["entities"]["entity_a"]["_removed"] is True
        assert snap["entities"]["entity_b"].get("_removed") is not True
        assert snap["entities"]["entity_b"]["name"] == "Entity B"
