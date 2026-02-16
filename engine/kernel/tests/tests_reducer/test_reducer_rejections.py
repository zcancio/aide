"""
AIde Reducer -- Rejection Tests (Category 2)

Each rejection reason has a test. Every code path that returns
applied=False with an error code is exercised here.

16 rejection codes from aide_reducer_spec.md:
  COLLECTION_NOT_FOUND, ENTITY_NOT_FOUND, ENTITY_ALREADY_EXISTS,
  COLLECTION_ALREADY_EXISTS, FIELD_ALREADY_EXISTS, FIELD_NOT_FOUND,
  VIEW_NOT_FOUND, BLOCK_NOT_FOUND, BLOCK_TYPE_MISSING, CANT_REMOVE_ROOT,
  REQUIRED_FIELD_MISSING, TYPE_MISMATCH, INCOMPATIBLE_TYPE_CHANGE,
  REQUIRED_FIELD_NO_DEFAULT, STRICT_CONSTRAINT_VIOLATED, UNKNOWN_PRIMITIVE

Reference: aide_reducer_spec.md, aide_primitive_schemas.md
"""

import pytest

from engine.kernel.reducer import reduce, empty_state
from engine.kernel.events import make_event


# ============================================================================
# Fixtures (reused from happy path -- keep in sync or extract to conftest.py)
# ============================================================================


@pytest.fixture
def empty():
    return empty_state()


@pytest.fixture
def state_with_collection(empty):
    result = reduce(
        empty,
        make_event(
            seq=1,
            type="collection.create",
            payload={
                "id": "grocery_list",
                "name": "Grocery List",
                "schema": {
                    "name": "string",
                    "store": "string?",
                    "checked": "bool",
                },
            },
        ),
    )
    return result.snapshot


@pytest.fixture
def state_with_entity(state_with_collection):
    result = reduce(
        state_with_collection,
        make_event(
            seq=2,
            type="entity.create",
            payload={
                "collection": "grocery_list",
                "id": "item_milk",
                "fields": {"name": "Milk", "store": "Whole Foods", "checked": False},
            },
        ),
    )
    return result.snapshot


@pytest.fixture
def state_with_removed_entity(state_with_entity):
    result = reduce(
        state_with_entity,
        make_event(
            seq=3,
            type="entity.remove",
            payload={"ref": "grocery_list/item_milk"},
        ),
    )
    return result.snapshot


@pytest.fixture
def state_with_view(state_with_collection):
    result = reduce(
        state_with_collection,
        make_event(
            seq=2,
            type="view.create",
            payload={
                "id": "grocery_view",
                "type": "list",
                "source": "grocery_list",
                "config": {"show_fields": ["name", "checked"]},
            },
        ),
    )
    return result.snapshot


@pytest.fixture
def state_with_block(empty):
    result = reduce(
        empty,
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
    )
    return result.snapshot


# Helper to assert rejection
def assert_rejected(result, expected_error):
    assert not result.applied, f"Expected rejection but event was applied"
    assert result.error is not None, f"Expected error code but got None"
    assert expected_error in result.error, (
        f"Expected error containing '{expected_error}', got '{result.error}'"
    )


# ============================================================================
# COLLECTION_NOT_FOUND
# ============================================================================


class TestCollectionNotFound:
    """Referenced collection doesn't exist."""

    def test_entity_create_no_collection(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="entity.create",
                payload={
                    "collection": "nonexistent",
                    "id": "item_1",
                    "fields": {"name": "Milk"},
                },
            ),
        )
        assert_rejected(result, "COLLECTION_NOT_FOUND")

    def test_entity_update_no_collection(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="entity.update",
                payload={
                    "ref": "nonexistent/item_1",
                    "fields": {"name": "Eggs"},
                },
            ),
        )
        assert_rejected(result, "COLLECTION_NOT_FOUND")

    def test_entity_remove_no_collection(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="entity.remove",
                payload={"ref": "nonexistent/item_1"},
            ),
        )
        assert_rejected(result, "COLLECTION_NOT_FOUND")

    def test_entity_update_filter_no_collection(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="entity.update",
                payload={
                    "filter": {
                        "collection": "nonexistent",
                        "where": {"checked": True},
                    },
                    "fields": {"archived": True},
                },
            ),
        )
        assert_rejected(result, "COLLECTION_NOT_FOUND")

    def test_collection_update_no_collection(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="collection.update",
                payload={"id": "nonexistent", "name": "New Name"},
            ),
        )
        assert_rejected(result, "COLLECTION_NOT_FOUND")

    def test_collection_remove_no_collection(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="collection.remove",
                payload={"id": "nonexistent"},
            ),
        )
        assert_rejected(result, "COLLECTION_NOT_FOUND")

    def test_field_add_no_collection(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="field.add",
                payload={
                    "collection": "nonexistent",
                    "name": "category",
                    "type": "string?",
                },
            ),
        )
        assert_rejected(result, "COLLECTION_NOT_FOUND")

    def test_field_update_no_collection(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="field.update",
                payload={
                    "collection": "nonexistent",
                    "name": "category",
                    "type": "int",
                },
            ),
        )
        assert_rejected(result, "COLLECTION_NOT_FOUND")

    def test_field_remove_no_collection(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="field.remove",
                payload={"collection": "nonexistent", "name": "category"},
            ),
        )
        assert_rejected(result, "COLLECTION_NOT_FOUND")

    def test_entity_create_on_removed_collection(self, state_with_collection):
        # Remove the collection first
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="collection.remove",
                payload={"id": "grocery_list"},
            ),
        )
        snapshot = result.snapshot

        # Try to create an entity in the removed collection
        result = reduce(
            snapshot,
            make_event(
                seq=3,
                type="entity.create",
                payload={
                    "collection": "grocery_list",
                    "id": "item_1",
                    "fields": {"name": "Milk", "checked": False},
                },
            ),
        )
        assert_rejected(result, "COLLECTION_NOT_FOUND")


# ============================================================================
# ENTITY_NOT_FOUND
# ============================================================================


class TestEntityNotFound:
    """Referenced entity doesn't exist."""

    def test_entity_update_no_entity(self, state_with_collection):
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="entity.update",
                payload={
                    "ref": "grocery_list/nonexistent",
                    "fields": {"checked": True},
                },
            ),
        )
        assert_rejected(result, "ENTITY_NOT_FOUND")

    def test_entity_remove_no_entity(self, state_with_collection):
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="entity.remove",
                payload={"ref": "grocery_list/nonexistent"},
            ),
        )
        assert_rejected(result, "ENTITY_NOT_FOUND")

    def test_entity_update_on_removed_entity(self, state_with_removed_entity):
        result = reduce(
            state_with_removed_entity,
            make_event(
                seq=4,
                type="entity.update",
                payload={
                    "ref": "grocery_list/item_milk",
                    "fields": {"checked": True},
                },
            ),
        )
        assert_rejected(result, "ENTITY_NOT_FOUND")

    def test_style_set_entity_no_entity(self, state_with_collection):
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="style.set_entity",
                payload={
                    "ref": "grocery_list/nonexistent",
                    "styles": {"highlight": True},
                },
            ),
        )
        assert_rejected(result, "ENTITY_NOT_FOUND")

    def test_style_set_entity_on_removed(self, state_with_removed_entity):
        result = reduce(
            state_with_removed_entity,
            make_event(
                seq=4,
                type="style.set_entity",
                payload={
                    "ref": "grocery_list/item_milk",
                    "styles": {"highlight": True},
                },
            ),
        )
        assert_rejected(result, "ENTITY_NOT_FOUND")

    def test_relationship_set_from_not_found(self, state_with_entity):
        result = reduce(
            state_with_entity,
            make_event(
                seq=3,
                type="relationship.set",
                payload={
                    "from": "grocery_list/nonexistent",
                    "to": "grocery_list/item_milk",
                    "type": "related_to",
                },
            ),
        )
        assert_rejected(result, "ENTITY_NOT_FOUND")

    def test_relationship_set_to_not_found(self, state_with_entity):
        result = reduce(
            state_with_entity,
            make_event(
                seq=3,
                type="relationship.set",
                payload={
                    "from": "grocery_list/item_milk",
                    "to": "grocery_list/nonexistent",
                    "type": "related_to",
                },
            ),
        )
        assert_rejected(result, "ENTITY_NOT_FOUND")


# ============================================================================
# ENTITY_ALREADY_EXISTS
# ============================================================================


class TestEntityAlreadyExists:
    """entity.create with duplicate ID (on a non-removed entity)."""

    def test_duplicate_entity_id(self, state_with_entity):
        result = reduce(
            state_with_entity,
            make_event(
                seq=3,
                type="entity.create",
                payload={
                    "collection": "grocery_list",
                    "id": "item_milk",  # Already exists
                    "fields": {"name": "Oat Milk", "checked": False},
                },
            ),
        )
        assert_rejected(result, "ENTITY_ALREADY_EXISTS")

    def test_recreate_removed_entity_is_allowed(self, state_with_removed_entity):
        """Re-creating a removed entity is NOT a rejection -- it's a re-creation."""
        result = reduce(
            state_with_removed_entity,
            make_event(
                seq=4,
                type="entity.create",
                payload={
                    "collection": "grocery_list",
                    "id": "item_milk",
                    "fields": {"name": "Oat Milk", "checked": False},
                },
            ),
        )
        # This should succeed -- removed entities can be re-created
        assert result.applied
        entity = result.snapshot["collections"]["grocery_list"]["entities"]["item_milk"]
        assert entity["name"] == "Oat Milk"
        assert entity["_removed"] is False


# ============================================================================
# COLLECTION_ALREADY_EXISTS
# ============================================================================


class TestCollectionAlreadyExists:
    """collection.create with duplicate ID."""

    def test_duplicate_collection_id(self, state_with_collection):
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="collection.create",
                payload={
                    "id": "grocery_list",  # Already exists
                    "name": "Another List",
                    "schema": {"title": "string"},
                },
            ),
        )
        assert_rejected(result, "COLLECTION_ALREADY_EXISTS")


# ============================================================================
# FIELD_ALREADY_EXISTS
# ============================================================================


class TestFieldAlreadyExists:
    """field.add with duplicate field name."""

    def test_duplicate_field_name(self, state_with_collection):
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="field.add",
                payload={
                    "collection": "grocery_list",
                    "name": "name",  # Already in schema
                    "type": "string",
                },
            ),
        )
        assert_rejected(result, "FIELD_ALREADY_EXISTS")


# ============================================================================
# FIELD_NOT_FOUND
# ============================================================================


class TestFieldNotFound:
    """field.update or field.remove on nonexistent field."""

    def test_field_update_not_found(self, state_with_collection):
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="field.update",
                payload={
                    "collection": "grocery_list",
                    "name": "nonexistent",
                    "type": "int",
                },
            ),
        )
        assert_rejected(result, "FIELD_NOT_FOUND")

    def test_field_remove_not_found(self, state_with_collection):
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="field.remove",
                payload={"collection": "grocery_list", "name": "nonexistent"},
            ),
        )
        assert_rejected(result, "FIELD_NOT_FOUND")


# ============================================================================
# VIEW_NOT_FOUND
# ============================================================================


class TestViewNotFound:
    """view.update or view.remove on nonexistent view."""

    def test_view_update_not_found(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="view.update",
                payload={
                    "id": "nonexistent",
                    "config": {"sort_by": "name"},
                },
            ),
        )
        assert_rejected(result, "VIEW_NOT_FOUND")

    def test_view_remove_not_found(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="view.remove",
                payload={"id": "nonexistent"},
            ),
        )
        assert_rejected(result, "VIEW_NOT_FOUND")


# ============================================================================
# BLOCK_NOT_FOUND
# ============================================================================


class TestBlockNotFound:
    """block.remove on nonexistent block. block.set with parent that doesn't exist."""

    def test_block_remove_not_found(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="block.remove",
                payload={"id": "nonexistent"},
            ),
        )
        assert_rejected(result, "BLOCK_NOT_FOUND")

    def test_block_set_parent_not_found(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="block.set",
                payload={
                    "id": "block_orphan",
                    "type": "text",
                    "parent": "nonexistent_parent",
                    "props": {"content": "Hello"},
                },
            ),
        )
        assert_rejected(result, "BLOCK_NOT_FOUND")

    def test_block_reorder_parent_not_found(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="block.reorder",
                payload={
                    "parent": "nonexistent_parent",
                    "children": ["a", "b"],
                },
            ),
        )
        assert_rejected(result, "BLOCK_NOT_FOUND")


# ============================================================================
# BLOCK_TYPE_MISSING
# ============================================================================


class TestBlockTypeMissing:
    """block.set in create mode without a type."""

    def test_new_block_no_type(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="block.set",
                payload={
                    "id": "block_mystery",
                    # No type -- required for create mode
                    "parent": "block_root",
                    "props": {"content": "Hello"},
                },
            ),
        )
        assert_rejected(result, "BLOCK_TYPE_MISSING")

    def test_existing_block_update_without_type_is_ok(self, state_with_block):
        """Updating an existing block doesn't need type (it's already set)."""
        result = reduce(
            state_with_block,
            make_event(
                seq=2,
                type="block.set",
                payload={
                    "id": "block_title",
                    # No type -- but block already exists, so this is update mode
                    "props": {"content": "Updated"},
                },
            ),
        )
        assert result.applied


# ============================================================================
# CANT_REMOVE_ROOT
# ============================================================================


class TestCantRemoveRoot:
    """block.remove on block_root."""

    def test_remove_root(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="block.remove",
                payload={"id": "block_root"},
            ),
        )
        assert_rejected(result, "CANT_REMOVE_ROOT")


# ============================================================================
# REQUIRED_FIELD_MISSING
# ============================================================================


class TestRequiredFieldMissing:
    """entity.create missing required (non-nullable) schema fields."""

    def test_missing_required_field(self, state_with_collection):
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="entity.create",
                payload={
                    "collection": "grocery_list",
                    "id": "item_1",
                    "fields": {
                        # "name" (string, required) is missing
                        # "checked" (bool, required) is missing
                        "store": "Trader Joe's",
                    },
                },
            ),
        )
        assert_rejected(result, "REQUIRED_FIELD_MISSING")

    def test_nullable_field_missing_is_ok(self, state_with_collection):
        """Missing a nullable field (string?) should NOT reject."""
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="entity.create",
                payload={
                    "collection": "grocery_list",
                    "id": "item_1",
                    "fields": {
                        "name": "Milk",
                        "checked": False,
                        # "store" (string?, nullable) is omitted -- that's fine
                    },
                },
            ),
        )
        assert result.applied


# ============================================================================
# TYPE_MISMATCH
# ============================================================================


class TestTypeMismatch:
    """Field value doesn't match schema type."""

    def test_string_field_gets_int(self, state_with_collection):
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="entity.create",
                payload={
                    "collection": "grocery_list",
                    "id": "item_1",
                    "fields": {
                        "name": 12345,  # Should be string
                        "checked": False,
                    },
                },
            ),
        )
        assert_rejected(result, "TYPE_MISMATCH")

    def test_bool_field_gets_string(self, state_with_collection):
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="entity.create",
                payload={
                    "collection": "grocery_list",
                    "id": "item_1",
                    "fields": {
                        "name": "Milk",
                        "checked": "yes",  # Should be bool
                    },
                },
            ),
        )
        assert_rejected(result, "TYPE_MISMATCH")

    def test_entity_update_type_mismatch(self, state_with_entity):
        result = reduce(
            state_with_entity,
            make_event(
                seq=3,
                type="entity.update",
                payload={
                    "ref": "grocery_list/item_milk",
                    "fields": {"checked": "not_a_bool"},
                },
            ),
        )
        assert_rejected(result, "TYPE_MISMATCH")

    def test_required_field_set_to_null(self, state_with_entity):
        """Setting a required (non-nullable) field to null is a type mismatch."""
        result = reduce(
            state_with_entity,
            make_event(
                seq=3,
                type="entity.update",
                payload={
                    "ref": "grocery_list/item_milk",
                    "fields": {"name": None},  # name is "string", not "string?"
                },
            ),
        )
        assert_rejected(result, "TYPE_MISMATCH")


# ============================================================================
# INCOMPATIBLE_TYPE_CHANGE
# ============================================================================


class TestIncompatibleTypeChange:
    """field.update with incompatible type conversion."""

    def test_string_to_list(self, state_with_collection):
        """string -> list is always incompatible per the type matrix."""
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="field.update",
                payload={
                    "collection": "grocery_list",
                    "name": "name",
                    "type": "list",
                },
            ),
        )
        assert_rejected(result, "INCOMPATIBLE_TYPE_CHANGE")

    def test_bool_to_float(self, state_with_collection):
        """bool -> float is incompatible per the type matrix."""
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="field.update",
                payload={
                    "collection": "grocery_list",
                    "name": "checked",
                    "type": "float",
                },
            ),
        )
        assert_rejected(result, "INCOMPATIBLE_TYPE_CHANGE")

    def test_date_to_int(self, empty):
        """date -> int is incompatible."""
        # Create a collection with a date field
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="collection.create",
                payload={
                    "id": "events",
                    "name": "Events",
                    "schema": {"title": "string", "when": "date"},
                },
            ),
        )
        snapshot = result.snapshot

        result = reduce(
            snapshot,
            make_event(
                seq=2,
                type="field.update",
                payload={
                    "collection": "events",
                    "name": "when",
                    "type": "int",
                },
            ),
        )
        assert_rejected(result, "INCOMPATIBLE_TYPE_CHANGE")

    def test_string_to_int_with_non_numeric_values(self, state_with_entity):
        """string -> int is a check*: rejects if existing values can't convert."""
        result = reduce(
            state_with_entity,
            make_event(
                seq=3,
                type="field.update",
                payload={
                    "collection": "grocery_list",
                    "name": "name",  # Has value "Milk" -- not numeric
                    "type": "int",
                },
            ),
        )
        assert_rejected(result, "INCOMPATIBLE_TYPE_CHANGE")

    def test_string_to_enum_with_values_not_in_enum(self, state_with_entity):
        """string -> enum rejects if existing values aren't in the enum list."""
        result = reduce(
            state_with_entity,
            make_event(
                seq=3,
                type="field.update",
                payload={
                    "collection": "grocery_list",
                    "name": "store",  # Has value "Whole Foods"
                    "type": {"enum": ["Costco", "Target"]},
                    # "Whole Foods" is not in the enum
                },
            ),
        )
        assert_rejected(result, "INCOMPATIBLE_TYPE_CHANGE")


# ============================================================================
# REQUIRED_FIELD_NO_DEFAULT
# ============================================================================


class TestRequiredFieldNoDefault:
    """field.add with required type but no default value."""

    def test_required_field_no_default(self, state_with_entity):
        """Adding a required field to a collection with existing entities
        requires a default -- otherwise those entities would be invalid."""
        result = reduce(
            state_with_entity,
            make_event(
                seq=3,
                type="field.add",
                payload={
                    "collection": "grocery_list",
                    "name": "priority",
                    "type": "int",  # Required (no ?), no default
                },
            ),
        )
        assert_rejected(result, "REQUIRED_FIELD_NO_DEFAULT")

    def test_required_field_with_default_is_ok(self, state_with_entity):
        """Adding a required field WITH a default should succeed."""
        result = reduce(
            state_with_entity,
            make_event(
                seq=3,
                type="field.add",
                payload={
                    "collection": "grocery_list",
                    "name": "priority",
                    "type": "int",
                    "default": 0,
                },
            ),
        )
        assert result.applied

    def test_nullable_field_no_default_is_ok(self, state_with_entity):
        """Adding a nullable field without a default is fine -- defaults to null."""
        result = reduce(
            state_with_entity,
            make_event(
                seq=3,
                type="field.add",
                payload={
                    "collection": "grocery_list",
                    "name": "notes",
                    "type": "string?",
                    # No default -- nullable fields auto-default to null
                },
            ),
        )
        assert result.applied

    def test_required_field_on_empty_collection_is_ok(self, state_with_collection):
        """Adding a required field without a default is OK if there are no entities."""
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="field.add",
                payload={
                    "collection": "grocery_list",
                    "name": "priority",
                    "type": "int",
                    # No default, but collection is empty, so no backfill needed
                },
            ),
        )
        assert result.applied


# ============================================================================
# STRICT_CONSTRAINT_VIOLATED
# ============================================================================


class TestStrictConstraintViolated:
    """Strict constraint violated causes rejection."""

    def test_strict_collection_max_entities(self, state_with_collection):
        # Add a strict constraint: max 1 entity
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="meta.constrain",
                payload={
                    "id": "max_1_item",
                    "rule": "collection_max_entities",
                    "collection": "grocery_list",
                    "value": 1,
                    "message": "Max 1 item",
                    "strict": True,
                },
            ),
        )
        snapshot = result.snapshot

        # Add first entity -- should succeed
        result = reduce(
            snapshot,
            make_event(
                seq=3,
                type="entity.create",
                payload={
                    "collection": "grocery_list",
                    "id": "item_1",
                    "fields": {"name": "Milk", "checked": False},
                },
            ),
        )
        assert result.applied
        snapshot = result.snapshot

        # Add second entity -- should be rejected by strict constraint
        result = reduce(
            snapshot,
            make_event(
                seq=4,
                type="entity.create",
                payload={
                    "collection": "grocery_list",
                    "id": "item_2",
                    "fields": {"name": "Eggs", "checked": False},
                },
            ),
        )
        assert_rejected(result, "STRICT_CONSTRAINT_VIOLATED")

    def test_non_strict_constraint_warns_but_applies(self, state_with_collection):
        """A non-strict constraint produces a warning, NOT a rejection."""
        # Add a non-strict constraint: max 1 entity
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="meta.constrain",
                payload={
                    "id": "max_1_item",
                    "rule": "collection_max_entities",
                    "collection": "grocery_list",
                    "value": 1,
                    "message": "Max 1 item",
                    # strict defaults to False
                },
            ),
        )
        snapshot = result.snapshot

        # Add first entity
        result = reduce(
            snapshot,
            make_event(
                seq=3,
                type="entity.create",
                payload={
                    "collection": "grocery_list",
                    "id": "item_1",
                    "fields": {"name": "Milk", "checked": False},
                },
            ),
        )
        snapshot = result.snapshot

        # Add second entity -- non-strict constraint: should apply with warning
        result = reduce(
            snapshot,
            make_event(
                seq=4,
                type="entity.create",
                payload={
                    "collection": "grocery_list",
                    "id": "item_2",
                    "fields": {"name": "Eggs", "checked": False},
                },
            ),
        )
        assert result.applied
        assert len(result.warnings) > 0
        assert any("CONSTRAINT_VIOLATED" in str(w) for w in result.warnings)


# ============================================================================
# UNKNOWN_PRIMITIVE
# ============================================================================


class TestUnknownPrimitive:
    """Unrecognized event type."""

    def test_unknown_type(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="widget.create",
                payload={"id": "w1"},
            ),
        )
        assert_rejected(result, "UNKNOWN_PRIMITIVE")

    def test_typo_in_type(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="entty.create",  # typo
                payload={
                    "collection": "tasks",
                    "id": "t1",
                    "fields": {"name": "Do laundry"},
                },
            ),
        )
        assert_rejected(result, "UNKNOWN_PRIMITIVE")

    def test_reserved_primitive_type(self, empty):
        """Reserved primitives (23-25) should reject as unknown until implemented."""
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="trigger.create",
                payload={"id": "trigger_1"},
            ),
        )
        assert_rejected(result, "UNKNOWN_PRIMITIVE")


# ============================================================================
# VIEW_CREATE_SOURCE_NOT_FOUND
# ============================================================================


class TestViewCreateSourceNotFound:
    """view.create referencing a collection that doesn't exist."""

    def test_view_source_missing(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="view.create",
                payload={
                    "id": "orphan_view",
                    "type": "list",
                    "source": "nonexistent_collection",
                    "config": {},
                },
            ),
        )
        assert_rejected(result, "COLLECTION_NOT_FOUND")

    def test_view_already_exists(self, state_with_view):
        result = reduce(
            state_with_view,
            make_event(
                seq=3,
                type="view.create",
                payload={
                    "id": "grocery_view",  # Already exists
                    "type": "table",
                    "source": "grocery_list",
                    "config": {},
                },
            ),
        )
        assert_rejected(result, "VIEW_ALREADY_EXISTS")


# ============================================================================
# Snapshot unchanged on rejection
# ============================================================================


class TestSnapshotUnchangedOnReject:
    """The snapshot must not be modified when an event is rejected."""

    def test_snapshot_unchanged_after_entity_not_found(self, state_with_collection):
        original = state_with_collection
        result = reduce(
            original,
            make_event(
                seq=2,
                type="entity.update",
                payload={
                    "ref": "grocery_list/nonexistent",
                    "fields": {"checked": True},
                },
            ),
        )
        assert not result.applied
        # Snapshot should be identical to the input
        assert result.snapshot == original

    def test_snapshot_unchanged_after_type_mismatch(self, state_with_entity):
        original = state_with_entity
        result = reduce(
            original,
            make_event(
                seq=3,
                type="entity.update",
                payload={
                    "ref": "grocery_list/item_milk",
                    "fields": {"checked": "not_a_bool"},
                },
            ),
        )
        assert not result.applied
        assert result.snapshot == original

    def test_snapshot_unchanged_after_unknown_primitive(self, empty):
        original = empty
        result = reduce(
            original,
            make_event(
                seq=1,
                type="magic.spell",
                payload={"power": 9000},
            ),
        )
        assert not result.applied
        assert result.snapshot == original
