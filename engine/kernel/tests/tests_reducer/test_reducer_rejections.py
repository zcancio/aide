"""
AIde Reducer — Rejection Tests (v3 Unified Entity Model)

Verify that invalid primitives are rejected with appropriate error codes.
Each test verifies: applied=False + specific error code prefix.

Reference: docs/eng_design/unified_entity_model.md
"""

import pytest

from engine.kernel.events import make_event
from engine.kernel.reducer import empty_state, reduce

GROCERY_ITEM_INTERFACE = "interface GroceryItem { name: string; checked: boolean; }"
GROCERY_LIST_INTERFACE = "interface GroceryList { title: string; items: Record<string, GroceryItem>; }"


@pytest.fixture
def empty():
    return empty_state()


@pytest.fixture
def state_with_schemas(empty):
    snapshot = empty
    for seq, schema_id, interface in [
        (1, "grocery_item", GROCERY_ITEM_INTERFACE),
        (2, "grocery_list", GROCERY_LIST_INTERFACE),
    ]:
        r = reduce(snapshot, make_event(seq, "schema.create", {
            "id": schema_id,
            "interface": interface,
        }))
        assert r.applied
        snapshot = r.snapshot
    return snapshot


@pytest.fixture
def state_with_entity(state_with_schemas):
    r = reduce(state_with_schemas, make_event(3, "entity.create", {
        "id": "my_list",
        "_schema": "grocery_list",
        "title": "My Groceries",
        "items": {
            "item_milk": {"name": "Milk", "checked": False, "_pos": 1.0},
        },
    }))
    assert r.applied
    return r.snapshot


# ============================================================================
# schema.create rejections
# ============================================================================

class TestSchemaCreateRejections:
    def test_rejects_missing_id(self, empty):
        r = reduce(empty, make_event(1, "schema.create", {
            "interface": GROCERY_ITEM_INTERFACE,
        }))
        assert not r.applied
        assert "MISSING_ID" in r.error

    def test_rejects_invalid_id(self, empty):
        r = reduce(empty, make_event(1, "schema.create", {
            "id": "Invalid-ID",
            "interface": GROCERY_ITEM_INTERFACE,
        }))
        assert not r.applied
        assert "INVALID_ID" in r.error

    def test_rejects_missing_interface(self, empty):
        r = reduce(empty, make_event(1, "schema.create", {
            "id": "my_schema",
        }))
        assert not r.applied
        assert "MISSING_INTERFACE" in r.error

    def test_rejects_duplicate_schema(self, state_with_schemas):
        r = reduce(state_with_schemas, make_event(3, "schema.create", {
            "id": "grocery_item",
            "interface": GROCERY_ITEM_INTERFACE,
        }))
        assert not r.applied
        assert "ALREADY_EXISTS" in r.error


# ============================================================================
# schema.update rejections
# ============================================================================

class TestSchemaUpdateRejections:
    def test_rejects_unknown_schema(self, empty):
        r = reduce(empty, make_event(1, "schema.update", {
            "id": "nonexistent",
            "render_html": "<div/>",
        }))
        assert not r.applied
        assert "NOT_FOUND" in r.error

    def test_rejects_missing_id(self, empty):
        r = reduce(empty, make_event(1, "schema.update", {
            "render_html": "<div/>",
        }))
        assert not r.applied
        assert "MISSING_ID" in r.error


# ============================================================================
# schema.remove rejections
# ============================================================================

class TestSchemaRemoveRejections:
    def test_rejects_schema_in_use(self, state_with_entity):
        r = reduce(state_with_entity, make_event(4, "schema.remove", {
            "id": "grocery_list",
        }))
        assert not r.applied
        assert "SCHEMA_IN_USE" in r.error

    def test_rejects_unknown_schema(self, empty):
        r = reduce(empty, make_event(1, "schema.remove", {"id": "nonexistent"}))
        assert not r.applied
        assert "NOT_FOUND" in r.error


# ============================================================================
# entity.create rejections
# ============================================================================

class TestEntityCreateRejections:
    def test_rejects_missing_id(self, empty):
        r = reduce(empty, make_event(1, "entity.create", {
            "title": "Something",
        }))
        assert not r.applied
        assert "MISSING_ID" in r.error

    def test_rejects_invalid_path(self, empty):
        r = reduce(empty, make_event(1, "entity.create", {
            "id": "Invalid-ID!",
            "title": "Something",
        }))
        assert not r.applied
        assert "INVALID_PATH" in r.error

    def test_rejects_duplicate_entity(self, state_with_entity):
        r = reduce(state_with_entity, make_event(4, "entity.create", {
            "id": "my_list",
            "_schema": "grocery_list",
            "title": "Duplicate",
            "items": {},
        }))
        assert not r.applied
        assert "ALREADY_EXISTS" in r.error

    def test_rejects_unknown_schema(self, empty):
        r = reduce(empty, make_event(1, "entity.create", {
            "id": "my_entity",
            "_schema": "nonexistent",
            "title": "Test",
        }))
        assert not r.applied
        assert "SCHEMA_NOT_FOUND" in r.error


# ============================================================================
# entity.update rejections
# ============================================================================

class TestEntityUpdateRejections:
    def test_rejects_missing_id(self, empty):
        r = reduce(empty, make_event(1, "entity.update", {"title": "Test"}))
        assert not r.applied
        assert "MISSING_ID" in r.error

    def test_rejects_unknown_entity(self, empty):
        r = reduce(empty, make_event(1, "entity.update", {
            "id": "nonexistent",
            "title": "Test",
        }))
        assert not r.applied
        assert "NOT_FOUND" in r.error

    def test_rejects_unknown_nested_path(self, state_with_entity):
        r = reduce(state_with_entity, make_event(4, "entity.update", {
            "id": "my_list/items/nonexistent_child",
            "checked": True,
        }))
        assert not r.applied
        assert "NOT_FOUND" in r.error


# ============================================================================
# entity.remove rejections
# ============================================================================

class TestEntityRemoveRejections:
    def test_rejects_missing_id(self, empty):
        r = reduce(empty, make_event(1, "entity.remove", {}))
        assert not r.applied
        assert "MISSING_ID" in r.error

    def test_rejects_unknown_entity(self, empty):
        r = reduce(empty, make_event(1, "entity.remove", {"id": "nonexistent"}))
        assert not r.applied
        assert "NOT_FOUND" in r.error


# ============================================================================
# block.set rejections
# ============================================================================

class TestBlockSetRejections:
    def test_rejects_missing_type(self, empty):
        r = reduce(empty, make_event(1, "block.set", {
            "id": "block_a",
            "parent": "block_root",
        }))
        assert not r.applied
        assert "MISSING_TYPE" in r.error

    def test_rejects_unknown_parent(self, empty):
        r = reduce(empty, make_event(1, "block.set", {
            "id": "block_a",
            "type": "text",
            "parent": "nonexistent_parent",
            "text": "Hello",
        }))
        assert not r.applied
        assert "PARENT_NOT_FOUND" in r.error


# ============================================================================
# block.remove rejections
# ============================================================================

class TestBlockRemoveRejections:
    def test_rejects_block_root_removal(self, empty):
        r = reduce(empty, make_event(1, "block.remove", {"id": "block_root"}))
        assert not r.applied
        assert "CANNOT_REMOVE_ROOT" in r.error

    def test_rejects_unknown_block(self, empty):
        r = reduce(empty, make_event(1, "block.remove", {"id": "nonexistent"}))
        assert not r.applied
        assert "NOT_FOUND" in r.error


# ============================================================================
# Unknown primitive
# ============================================================================

class TestUnknownPrimitive:
    def test_rejects_unknown_primitive_type(self, empty):
        r = reduce(empty, make_event(1, "nonexistent.primitive", {"foo": "bar"}))
        assert not r.applied
        assert "UNKNOWN_PRIMITIVE" in r.error
