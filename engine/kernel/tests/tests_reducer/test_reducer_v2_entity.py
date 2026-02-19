"""
AIde v2 Reducer — Entity Primitive Tests

Tests for entity.create, entity.update, entity.remove, entity.move, entity.reorder.
"""

import pytest

from engine.kernel.reducer_v2 import empty_snapshot, reduce

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def empty():
    return empty_snapshot()


@pytest.fixture
def state_with_parent(empty):
    result = reduce(empty, {"t": "entity.create", "id": "guests", "display": "table", "p": {}})
    assert result.accepted
    return result.snapshot


@pytest.fixture
def state_with_entity(state_with_parent):
    result = reduce(
        state_with_parent,
        {"t": "entity.create", "id": "guest_linda", "parent": "guests", "p": {"name": "Aunt Linda", "rsvp": "yes"}},
    )
    assert result.accepted
    return result.snapshot


@pytest.fixture
def state_with_three_children(state_with_parent):
    snap = state_with_parent
    for name in ["guest_alice", "guest_bob", "guest_carol"]:
        result = reduce(snap, {"t": "entity.create", "id": name, "parent": "guests", "p": {"name": name}})
        assert result.accepted
        snap = result.snapshot
    return snap


# ============================================================================
# entity.create
# ============================================================================


class TestEntityCreate:
    def test_creates_root_entity(self, empty):
        result = reduce(empty, {"t": "entity.create", "id": "page_home", "display": "page", "p": {"title": "Home"}})
        assert result.accepted
        entity = result.snapshot["entities"]["page_home"]
        assert entity["id"] == "page_home"
        assert entity["parent"] == "root"
        assert entity["display"] == "page"
        assert entity["props"]["title"] == "Home"
        assert entity["_removed"] is False
        assert entity["_children"] == []

    def test_creates_child_entity(self, state_with_parent):
        result = reduce(
            state_with_parent,
            {"t": "entity.create", "id": "guest_linda", "parent": "guests", "p": {"name": "Linda"}},
        )
        assert result.accepted
        entity = result.snapshot["entities"]["guest_linda"]
        assert entity["parent"] == "guests"
        # Parent's _children is updated
        assert "guest_linda" in result.snapshot["entities"]["guests"]["_children"]

    def test_sequence_incremented(self, empty):
        assert empty["_sequence"] == 0
        result = reduce(empty, {"t": "entity.create", "id": "e1", "p": {}})
        assert result.snapshot["_sequence"] == 1
        result2 = reduce(result.snapshot, {"t": "entity.create", "id": "e2", "p": {}})
        assert result2.snapshot["_sequence"] == 2

    def test_created_seq_and_updated_seq_set(self, empty):
        result = reduce(empty, {"t": "entity.create", "id": "e1", "p": {}})
        entity = result.snapshot["entities"]["e1"]
        assert entity["_created_seq"] == 1
        assert entity["_updated_seq"] == 1

    def test_props_stored_correctly(self, empty):
        result = reduce(
            empty,
            {"t": "entity.create", "id": "item_1", "p": {"name": "Item", "done": False, "count": 5}},
        )
        assert result.accepted
        props = result.snapshot["entities"]["item_1"]["props"]
        assert props["name"] == "Item"
        assert props["done"] is False
        assert props["count"] == 5

    def test_reject_duplicate_id(self, state_with_entity):
        result = reduce(state_with_entity, {"t": "entity.create", "id": "guest_linda", "p": {}})
        assert not result.accepted
        assert "ENTITY_EXISTS" in result.reason

    def test_reject_missing_parent(self, empty):
        result = reduce(empty, {"t": "entity.create", "id": "child", "parent": "nonexistent", "p": {}})
        assert not result.accepted
        assert "PARENT_NOT_FOUND" in result.reason

    def test_reject_invalid_id_uppercase(self, empty):
        result = reduce(empty, {"t": "entity.create", "id": "GuestLinda", "p": {}})
        assert not result.accepted
        assert "INVALID_ID" in result.reason

    def test_reject_invalid_id_spaces(self, empty):
        result = reduce(empty, {"t": "entity.create", "id": "guest linda", "p": {}})
        assert not result.accepted
        assert "INVALID_ID" in result.reason

    def test_reject_invalid_id_too_long(self, empty):
        long_id = "a" * 65
        result = reduce(empty, {"t": "entity.create", "id": long_id, "p": {}})
        assert not result.accepted
        assert "INVALID_ID" in result.reason

    def test_reject_missing_id(self, empty):
        result = reduce(empty, {"t": "entity.create", "p": {}})
        assert not result.accepted
        assert "MISSING_ID" in result.reason

    def test_default_parent_is_root(self, empty):
        result = reduce(empty, {"t": "entity.create", "id": "top_level", "p": {}})
        assert result.accepted
        assert result.snapshot["entities"]["top_level"]["parent"] == "root"

    def test_display_can_be_none(self, empty):
        result = reduce(empty, {"t": "entity.create", "id": "e1", "p": {}})
        assert result.accepted
        assert result.snapshot["entities"]["e1"]["display"] is None

    def test_reject_removed_parent(self, state_with_parent):
        # Remove parent
        result = reduce(state_with_parent, {"t": "entity.remove", "ref": "guests"})
        assert result.accepted
        # Now try to create child under removed parent
        result2 = reduce(result.snapshot, {"t": "entity.create", "id": "new_child", "parent": "guests", "p": {}})
        assert not result2.accepted
        assert "PARENT_NOT_FOUND" in result2.reason


# ============================================================================
# entity.update
# ============================================================================


class TestEntityUpdate:
    def test_merges_props(self, state_with_entity):
        result = reduce(
            state_with_entity,
            {"t": "entity.update", "ref": "guest_linda", "p": {"rsvp": "confirmed", "dietary": "vegetarian"}},
        )
        assert result.accepted
        props = result.snapshot["entities"]["guest_linda"]["props"]
        assert props["rsvp"] == "confirmed"
        assert props["dietary"] == "vegetarian"
        assert props["name"] == "Aunt Linda"  # Unchanged

    def test_updated_seq_incremented(self, state_with_entity):
        old_seq = state_with_entity["entities"]["guest_linda"]["_updated_seq"]
        result = reduce(state_with_entity, {"t": "entity.update", "ref": "guest_linda", "p": {"rsvp": "no"}})
        assert result.accepted
        new_seq = result.snapshot["entities"]["guest_linda"]["_updated_seq"]
        assert new_seq > old_seq

    def test_new_prop_extends_entity(self, state_with_entity):
        result = reduce(state_with_entity, {"t": "entity.update", "ref": "guest_linda", "p": {"table": "Table 1"}})
        assert result.accepted
        assert result.snapshot["entities"]["guest_linda"]["props"]["table"] == "Table 1"

    def test_multiple_props_in_one_update(self, state_with_entity):
        result = reduce(
            state_with_entity,
            {"t": "entity.update", "ref": "guest_linda", "p": {"a": 1, "b": 2, "c": 3}},
        )
        assert result.accepted
        props = result.snapshot["entities"]["guest_linda"]["props"]
        assert props["a"] == 1 and props["b"] == 2 and props["c"] == 3

    def test_reject_nonexistent_entity(self, empty):
        result = reduce(empty, {"t": "entity.update", "ref": "nobody", "p": {"x": 1}})
        assert not result.accepted
        assert "ENTITY_NOT_FOUND" in result.reason

    def test_reject_removed_entity(self, state_with_entity):
        remove_result = reduce(state_with_entity, {"t": "entity.remove", "ref": "guest_linda"})
        result = reduce(remove_result.snapshot, {"t": "entity.update", "ref": "guest_linda", "p": {"x": 1}})
        assert not result.accepted
        assert "ENTITY_NOT_FOUND" in result.reason

    def test_reject_missing_ref(self, empty):
        result = reduce(empty, {"t": "entity.update", "p": {"x": 1}})
        assert not result.accepted
        assert "MISSING_REF" in result.reason


# ============================================================================
# entity.remove
# ============================================================================


class TestEntityRemove:
    def test_soft_deletes_entity(self, state_with_entity):
        result = reduce(state_with_entity, {"t": "entity.remove", "ref": "guest_linda"})
        assert result.accepted
        entity = result.snapshot["entities"]["guest_linda"]
        assert entity["_removed"] is True
        # Data preserved for undo
        assert entity["props"]["name"] == "Aunt Linda"

    def test_cascade_removes_children(self, state_with_parent):
        # Add children
        snap = state_with_parent
        for child_id in ["c1", "c2", "c3"]:
            result = reduce(snap, {"t": "entity.create", "id": child_id, "parent": "guests", "p": {}})
            snap = result.snapshot
        # Remove parent
        result = reduce(snap, {"t": "entity.remove", "ref": "guests"})
        assert result.accepted
        # All children removed
        for child_id in ["c1", "c2", "c3"]:
            assert result.snapshot["entities"][child_id]["_removed"] is True

    def test_cascade_removes_nested_descendants(self, empty):
        snap = empty
        # Create grandparent → parent → child
        for eid, parent in [("gp", "root"), ("p1", "gp"), ("c1", "p1")]:
            result = reduce(snap, {"t": "entity.create", "id": eid, "parent": parent, "p": {}})
            snap = result.snapshot
        result = reduce(snap, {"t": "entity.remove", "ref": "gp"})
        assert result.accepted
        for eid in ["gp", "p1", "c1"]:
            assert result.snapshot["entities"][eid]["_removed"] is True

    def test_reject_nonexistent_entity(self, empty):
        result = reduce(empty, {"t": "entity.remove", "ref": "nobody"})
        assert not result.accepted
        assert "ENTITY_NOT_FOUND" in result.reason

    def test_reject_already_removed(self, state_with_entity):
        result = reduce(state_with_entity, {"t": "entity.remove", "ref": "guest_linda"})
        result2 = reduce(result.snapshot, {"t": "entity.remove", "ref": "guest_linda"})
        assert not result2.accepted
        assert "ALREADY_REMOVED" in result2.reason

    def test_reject_missing_ref(self, empty):
        result = reduce(empty, {"t": "entity.remove"})
        assert not result.accepted
        assert "MISSING_REF" in result.reason


# ============================================================================
# entity.move
# ============================================================================


class TestEntityMove:
    def test_move_to_different_parent(self, empty):
        snap = empty
        for eid, parent in [("section_a", "root"), ("section_b", "root"), ("item_x", "section_a")]:
            result = reduce(snap, {"t": "entity.create", "id": eid, "parent": parent, "p": {}})
            snap = result.snapshot

        result = reduce(snap, {"t": "entity.move", "ref": "item_x", "parent": "section_b"})
        assert result.accepted
        assert result.snapshot["entities"]["item_x"]["parent"] == "section_b"
        assert "item_x" not in result.snapshot["entities"]["section_a"]["_children"]
        assert "item_x" in result.snapshot["entities"]["section_b"]["_children"]

    def test_move_with_position(self, state_with_three_children):
        snap = state_with_three_children
        # Add a separate parent and move guest_bob to it at position 0
        result = reduce(snap, {"t": "entity.create", "id": "vip_section", "p": {}})
        snap = result.snapshot
        result = reduce(snap, {"t": "entity.move", "ref": "guest_bob", "parent": "vip_section", "position": 0})
        assert result.accepted
        assert result.snapshot["entities"]["vip_section"]["_children"][0] == "guest_bob"

    def test_move_to_end_without_position(self, empty):
        snap = empty
        for eid, parent in [("sect_a", "root"), ("sect_b", "root"), ("item_1", "sect_a")]:
            result = reduce(snap, {"t": "entity.create", "id": eid, "parent": parent, "p": {}})
            snap = result.snapshot
        result = reduce(snap, {"t": "entity.move", "ref": "item_1", "parent": "sect_b"})
        assert result.accepted
        assert result.snapshot["entities"]["sect_b"]["_children"][-1] == "item_1"

    def test_reject_nonexistent_entity(self, state_with_parent):
        result = reduce(state_with_parent, {"t": "entity.move", "ref": "nobody", "parent": "guests"})
        assert not result.accepted
        assert "ENTITY_NOT_FOUND" in result.reason

    def test_reject_nonexistent_parent(self, state_with_entity):
        result = reduce(state_with_entity, {"t": "entity.move", "ref": "guest_linda", "parent": "nosuchparent"})
        assert not result.accepted
        assert "PARENT_NOT_FOUND" in result.reason

    def test_reject_move_to_self(self, state_with_entity):
        result = reduce(state_with_entity, {"t": "entity.move", "ref": "guest_linda", "parent": "guest_linda"})
        assert not result.accepted
        assert "CYCLE" in result.reason

    def test_reject_move_to_own_descendant(self, empty):
        snap = empty
        for eid, parent in [("gp", "root"), ("child", "gp")]:
            result = reduce(snap, {"t": "entity.create", "id": eid, "parent": parent, "p": {}})
            snap = result.snapshot
        result = reduce(snap, {"t": "entity.move", "ref": "gp", "parent": "child"})
        assert not result.accepted
        assert "CYCLE" in result.reason

    def test_reject_missing_ref(self, empty):
        result = reduce(empty, {"t": "entity.move", "parent": "root"})
        assert not result.accepted
        assert "MISSING_REF" in result.reason


# ============================================================================
# entity.reorder
# ============================================================================


class TestEntityReorder:
    def test_reorders_children(self, state_with_three_children):
        snap = state_with_three_children
        result = reduce(
            snap,
            {"t": "entity.reorder", "ref": "guests", "children": ["guest_carol", "guest_alice", "guest_bob"]},
        )
        assert result.accepted
        children = result.snapshot["entities"]["guests"]["_children"]
        assert children[:3] == ["guest_carol", "guest_alice", "guest_bob"]

    def test_reject_missing_children(self, state_with_three_children):
        result = reduce(
            state_with_three_children,
            {"t": "entity.reorder", "ref": "guests", "children": ["guest_alice", "guest_bob"]},  # missing carol
        )
        assert not result.accepted
        assert "REORDER_MISMATCH" in result.reason

    def test_reject_extra_children(self, state_with_three_children):
        result = reduce(
            state_with_three_children,
            {"t": "entity.reorder", "ref": "guests", "children": ["guest_alice", "guest_bob", "guest_carol", "extra"]},
        )
        assert not result.accepted
        assert "REORDER_MISMATCH" in result.reason

    def test_removed_children_excluded_from_required_set(self, state_with_three_children):
        snap = state_with_three_children
        # Remove one child
        result = reduce(snap, {"t": "entity.remove", "ref": "guest_carol"})
        snap = result.snapshot
        # Reorder without removed child — should work
        result = reduce(snap, {"t": "entity.reorder", "ref": "guests", "children": ["guest_bob", "guest_alice"]})
        assert result.accepted

    def test_reject_nonexistent_entity(self, empty):
        result = reduce(empty, {"t": "entity.reorder", "ref": "nobody", "children": []})
        assert not result.accepted
        assert "ENTITY_NOT_FOUND" in result.reason

    def test_reject_missing_ref(self, empty):
        result = reduce(empty, {"t": "entity.reorder", "children": []})
        assert not result.accepted
        assert "MISSING_REF" in result.reason
