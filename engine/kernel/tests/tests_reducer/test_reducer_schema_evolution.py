"""
AIde Reducer -- Schema Evolution Tests (Category 5)

Tests for field.add, field.update, and field.remove behavior across entities,
including backfill, type compatibility, rename propagation, and view cleanup.

From the spec (aide_reducer_spec.md, "Testing Strategy"):
  "5. Schema evolution. Add field with default, verify backfill. Remove field,
   verify cleanup. Rename field, verify entities updated."

Covers:
  - field.add: backfill with default across many entities, nullable auto-null,
    required field with default, backfill skips removed entities
  - field.update: type compatibility matrix (string↔int, string↔enum, int→float,
    float→int lossy, bool→int, enum→string, rename propagation)
  - field.remove: cleanup from schema + all entities, view reference cleanup
  - Multi-step evolution: progressive schema growth over many operations
  - Entity operations after schema evolution: new entities respect new schema

Reference: aide_reducer_spec.md, aide_primitive_schemas.md
"""

import pytest

from engine.kernel.events import make_event
from engine.kernel.reducer import empty_state, reduce, replay

# ============================================================================
# Helpers
# ============================================================================


def has_warning(result, code):
    """Check if a specific warning code is present."""
    return any(w.code == code for w in result.warnings)


def entity_fields(snapshot, collection, entity_id):
    """Get an entity's field values (excluding internal keys)."""
    e = snapshot["collections"][collection]["entities"][entity_id]
    return {k: v for k, v in e.items() if not k.startswith("_")}


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def empty():
    return empty_state()


@pytest.fixture
def grocery_collection(empty):
    """Collection with schema: name(string), store(string?), checked(bool)."""
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
    assert result.applied
    return result.snapshot


@pytest.fixture
def grocery_with_items(grocery_collection):
    """Grocery collection with 5 entities for bulk schema evolution tests."""
    items = [
        ("item_milk", {"name": "Milk", "store": "Whole Foods", "checked": False}),
        ("item_eggs", {"name": "Eggs", "store": "Costco", "checked": True}),
        ("item_bread", {"name": "Bread", "store": None, "checked": False}),
        ("item_butter", {"name": "Butter", "store": "Whole Foods", "checked": False}),
        ("item_cheese", {"name": "Cheese", "store": "Costco", "checked": True}),
    ]
    snapshot = grocery_collection
    for seq_offset, (item_id, fields) in enumerate(items):
        result = reduce(
            snapshot,
            make_event(
                seq=2 + seq_offset,
                type="entity.create",
                payload={
                    "collection": "grocery_list",
                    "id": item_id,
                    "fields": fields,
                },
            ),
        )
        assert result.applied
        snapshot = result.snapshot
    return snapshot


@pytest.fixture
def grocery_with_items_and_removed(grocery_with_items):
    """Same as grocery_with_items but item_bread is soft-deleted."""
    result = reduce(
        grocery_with_items,
        make_event(
            seq=7,
            type="entity.remove",
            payload={"ref": "grocery_list/item_bread"},
        ),
    )
    assert result.applied
    return result.snapshot


@pytest.fixture
def grocery_with_view(grocery_with_items):
    """Grocery collection with items and a view referencing store and checked."""
    result = reduce(
        grocery_with_items,
        make_event(
            seq=7,
            type="view.create",
            payload={
                "id": "grocery_by_store",
                "type": "list",
                "source": "grocery_list",
                "config": {
                    "show_fields": ["name", "store", "checked"],
                    "sort_by": "store",
                    "sort_order": "asc",
                    "group_by": "store",
                },
            },
        ),
    )
    assert result.applied
    return result.snapshot


@pytest.fixture
def numeric_collection(empty):
    """Collection with int and float fields for type conversion tests."""
    result = reduce(
        empty,
        make_event(
            seq=1,
            type="collection.create",
            payload={
                "id": "measurements",
                "name": "Measurements",
                "schema": {
                    "label": "string",
                    "count": "int",
                    "weight": "float",
                    "active": "bool",
                },
            },
        ),
    )
    assert result.applied

    # Add some entities with varied values
    items = [
        ("m1", {"label": "Alpha", "count": 10, "weight": 3.14, "active": True}),
        ("m2", {"label": "Beta", "count": 0, "weight": 2.0, "active": False}),
        ("m3", {"label": "42", "count": 42, "weight": 7.5, "active": True}),
    ]
    snapshot = result.snapshot
    for i, (item_id, fields) in enumerate(items):
        r = reduce(
            snapshot,
            make_event(
                seq=2 + i,
                type="entity.create",
                payload={
                    "collection": "measurements",
                    "id": item_id,
                    "fields": fields,
                },
            ),
        )
        assert r.applied
        snapshot = r.snapshot
    return snapshot


# ============================================================================
# field.add — Backfill
# ============================================================================


class TestFieldAddBackfill:
    """field.add backfills existing entities with the default value."""

    def test_nullable_field_backfills_null(self, grocery_with_items):
        """Adding a nullable field without explicit default → all entities get null."""
        result = reduce(
            grocery_with_items,
            make_event(
                seq=7,
                type="field.add",
                payload={
                    "collection": "grocery_list",
                    "name": "category",
                    "type": "string?",
                },
            ),
        )
        assert result.applied

        entities = result.snapshot["collections"]["grocery_list"]["entities"]
        for eid, entity in entities.items():
            assert "category" in entity, f"Entity {eid} missing backfilled field"
            assert entity["category"] is None

    def test_required_field_with_default_backfills(self, grocery_with_items):
        """Adding a required field with default → all entities get that default."""
        result = reduce(
            grocery_with_items,
            make_event(
                seq=7,
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

        entities = result.snapshot["collections"]["grocery_list"]["entities"]
        for eid, entity in entities.items():
            assert entity["priority"] == 0, f"Entity {eid} not backfilled with default"

    def test_backfill_with_non_trivial_default(self, grocery_with_items):
        """Backfill with a string default value."""
        result = reduce(
            grocery_with_items,
            make_event(
                seq=7,
                type="field.add",
                payload={
                    "collection": "grocery_list",
                    "name": "aisle",
                    "type": "string",
                    "default": "unknown",
                },
            ),
        )
        assert result.applied

        entities = result.snapshot["collections"]["grocery_list"]["entities"]
        for eid, entity in entities.items():
            assert entity["aisle"] == "unknown"

    def test_backfill_with_bool_default(self, grocery_with_items):
        """Backfill with a boolean default."""
        result = reduce(
            grocery_with_items,
            make_event(
                seq=7,
                type="field.add",
                payload={
                    "collection": "grocery_list",
                    "name": "organic",
                    "type": "bool",
                    "default": False,
                },
            ),
        )
        assert result.applied

        entities = result.snapshot["collections"]["grocery_list"]["entities"]
        for eid, entity in entities.items():
            assert entity["organic"] is False

    def test_backfill_skips_removed_entities(self, grocery_with_items_and_removed):
        """Removed entities still get backfilled (data preserved for undo)."""
        result = reduce(
            grocery_with_items_and_removed,
            make_event(
                seq=8,
                type="field.add",
                payload={
                    "collection": "grocery_list",
                    "name": "category",
                    "type": "string?",
                },
            ),
        )
        assert result.applied

        # Even removed entity gets the field (preserved for undo/replay)
        bread = result.snapshot["collections"]["grocery_list"]["entities"]["item_bread"]
        assert bread["_removed"] is True
        assert "category" in bread

    def test_schema_updated_after_add(self, grocery_with_items):
        """Schema itself is updated with the new field definition."""
        result = reduce(
            grocery_with_items,
            make_event(
                seq=7,
                type="field.add",
                payload={
                    "collection": "grocery_list",
                    "name": "quantity",
                    "type": "int",
                    "default": 1,
                },
            ),
        )
        assert result.applied

        schema = result.snapshot["collections"]["grocery_list"]["schema"]
        assert "quantity" in schema
        assert schema["quantity"] == "int"

    def test_new_entity_after_field_add_uses_schema(self, grocery_with_items):
        """After adding a field, new entities must provide it (or use nullable default)."""
        # Add required field with default
        result = reduce(
            grocery_with_items,
            make_event(
                seq=7,
                type="field.add",
                payload={
                    "collection": "grocery_list",
                    "name": "quantity",
                    "type": "int",
                    "default": 1,
                },
            ),
        )
        snapshot = result.snapshot

        # Create new entity providing the new field
        result = reduce(
            snapshot,
            make_event(
                seq=8,
                type="entity.create",
                payload={
                    "collection": "grocery_list",
                    "id": "item_yogurt",
                    "fields": {
                        "name": "Yogurt",
                        "checked": False,
                        "quantity": 3,
                    },
                },
            ),
        )
        assert result.applied
        yogurt = result.snapshot["collections"]["grocery_list"]["entities"]["item_yogurt"]
        assert yogurt["quantity"] == 3

    def test_backfill_on_empty_collection_is_noop(self, grocery_collection):
        """Adding a field to an empty collection just updates the schema."""
        result = reduce(
            grocery_collection,
            make_event(
                seq=2,
                type="field.add",
                payload={
                    "collection": "grocery_list",
                    "name": "category",
                    "type": "string?",
                },
            ),
        )
        assert result.applied
        schema = result.snapshot["collections"]["grocery_list"]["schema"]
        assert "category" in schema
        assert result.snapshot["collections"]["grocery_list"]["entities"] == {}


# ============================================================================
# field.update — Type Compatibility
# ============================================================================


class TestFieldUpdateTypeCompatibility:
    """Type changes must follow the compatibility matrix from the spec."""

    def test_int_to_float_always_ok(self, numeric_collection):
        """int → float: always compatible (no data loss)."""
        result = reduce(
            numeric_collection,
            make_event(
                seq=5,
                type="field.update",
                payload={
                    "collection": "measurements",
                    "name": "count",
                    "type": "float",
                },
            ),
        )
        assert result.applied
        schema = result.snapshot["collections"]["measurements"]["schema"]
        assert schema["count"] == "float"

    def test_int_to_string_always_ok(self, numeric_collection):
        """int → string: always compatible."""
        result = reduce(
            numeric_collection,
            make_event(
                seq=5,
                type="field.update",
                payload={
                    "collection": "measurements",
                    "name": "count",
                    "type": "string",
                },
            ),
        )
        assert result.applied

    def test_float_to_int_lossy_warns(self, numeric_collection):
        """float → int: lossy conversion truncates decimals → WARN."""
        result = reduce(
            numeric_collection,
            make_event(
                seq=5,
                type="field.update",
                payload={
                    "collection": "measurements",
                    "name": "weight",
                    "type": "int",
                },
            ),
        )
        assert result.applied
        assert has_warning(result, "LOSSY_TYPE_CONVERSION")

    def test_bool_to_int_ok(self, numeric_collection):
        """bool → int: compatible (True→1, False→0)."""
        result = reduce(
            numeric_collection,
            make_event(
                seq=5,
                type="field.update",
                payload={
                    "collection": "measurements",
                    "name": "active",
                    "type": "int",
                },
            ),
        )
        assert result.applied

    def test_bool_to_string_ok(self, numeric_collection):
        """bool → string: always compatible."""
        result = reduce(
            numeric_collection,
            make_event(
                seq=5,
                type="field.update",
                payload={
                    "collection": "measurements",
                    "name": "active",
                    "type": "string",
                },
            ),
        )
        assert result.applied

    def test_string_to_int_checks_values_ok(self, numeric_collection):
        """string → int: check* — succeeds if all existing values are numeric."""
        # Entity m3 has label="42" which is numeric
        # But m1 has "Alpha" and m2 has "Beta" — this should reject
        result = reduce(
            numeric_collection,
            make_event(
                seq=5,
                type="field.update",
                payload={
                    "collection": "measurements",
                    "name": "label",
                    "type": "int",
                },
            ),
        )
        # "Alpha" and "Beta" can't convert to int
        assert not result.applied

    def test_string_to_int_all_numeric_succeeds(self, empty):
        """string → int succeeds when all existing values are numeric strings."""
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="collection.create",
                payload={
                    "id": "scores",
                    "schema": {"value": "string"},
                },
            ),
        )
        snapshot = result.snapshot

        # Add entities with numeric string values
        for i, val in enumerate(["10", "20", "30"]):
            result = reduce(
                snapshot,
                make_event(
                    seq=2 + i,
                    type="entity.create",
                    payload={
                        "collection": "scores",
                        "id": f"s{i}",
                        "fields": {"value": val},
                    },
                ),
            )
            snapshot = result.snapshot

        # Now convert string → int: all values are numeric, should succeed
        result = reduce(
            snapshot,
            make_event(
                seq=5,
                type="field.update",
                payload={
                    "collection": "scores",
                    "name": "value",
                    "type": "int",
                },
            ),
        )
        assert result.applied

    def test_string_to_enum_checks_values(self, grocery_with_items):
        """string → enum: check** — succeeds if all values are in the enum."""
        # store has values: "Whole Foods", "Costco", None (nullable)
        result = reduce(
            grocery_with_items,
            make_event(
                seq=7,
                type="field.update",
                payload={
                    "collection": "grocery_list",
                    "name": "store",
                    "type": {"enum": ["Whole Foods", "Costco", "Target"]},
                },
            ),
        )
        # All non-null values are in the enum
        assert result.applied

    def test_string_to_enum_rejects_if_value_not_in_enum(self, grocery_with_items):
        """string → enum rejects if any existing value is not in the enum list."""
        result = reduce(
            grocery_with_items,
            make_event(
                seq=7,
                type="field.update",
                payload={
                    "collection": "grocery_list",
                    "name": "store",
                    "type": {"enum": ["Costco", "Target"]},
                    # "Whole Foods" is NOT in this enum
                },
            ),
        )
        assert not result.applied

    def test_enum_to_string_always_ok(self, empty):
        """enum → string: always compatible (widening)."""
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="collection.create",
                payload={
                    "id": "tasks",
                    "schema": {"status": {"enum": ["todo", "done"]}},
                },
            ),
        )
        snapshot = result.snapshot

        result = reduce(
            snapshot,
            make_event(
                seq=2,
                type="entity.create",
                payload={
                    "collection": "tasks",
                    "id": "t1",
                    "fields": {"status": "todo"},
                },
            ),
        )
        snapshot = result.snapshot

        result = reduce(
            snapshot,
            make_event(
                seq=3,
                type="field.update",
                payload={
                    "collection": "tasks",
                    "name": "status",
                    "type": "string",
                },
            ),
        )
        assert result.applied

    def test_enum_to_int_rejects(self, empty):
        """enum → int: incompatible per the type matrix."""
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="collection.create",
                payload={
                    "id": "tasks",
                    "schema": {"priority": {"enum": ["low", "high"]}},
                },
            ),
        )
        result = reduce(
            result.snapshot,
            make_event(
                seq=2,
                type="field.update",
                payload={
                    "collection": "tasks",
                    "name": "priority",
                    "type": "int",
                },
            ),
        )
        assert not result.applied

    def test_date_to_string_ok(self, empty):
        """date → string: always compatible."""
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="collection.create",
                payload={
                    "id": "events",
                    "schema": {"when": "date"},
                },
            ),
        )
        result = reduce(
            result.snapshot,
            make_event(
                seq=2,
                type="field.update",
                payload={
                    "collection": "events",
                    "name": "when",
                    "type": "string",
                },
            ),
        )
        assert result.applied

    def test_list_to_anything_rejects(self, empty):
        """list → anything (except list): incompatible per the matrix."""
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="collection.create",
                payload={
                    "id": "data",
                    "schema": {"tags": "list"},
                },
            ),
        )

        for target_type in ["string", "int", "float", "bool"]:
            r = reduce(
                result.snapshot,
                make_event(
                    seq=2,
                    type="field.update",
                    payload={
                        "collection": "data",
                        "name": "tags",
                        "type": target_type,
                    },
                ),
            )
            assert not r.applied, f"list → {target_type} should reject"

    def test_type_change_on_empty_collection_always_ok(self, empty):
        """Type changes on collections with no entities skip value checks."""
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="collection.create",
                payload={
                    "id": "data",
                    "schema": {"value": "string"},
                },
            ),
        )

        # string → int with no entities: should succeed (no values to check)
        result = reduce(
            result.snapshot,
            make_event(
                seq=2,
                type="field.update",
                payload={
                    "collection": "data",
                    "name": "value",
                    "type": "int",
                },
            ),
        )
        assert result.applied


# ============================================================================
# field.update — Rename
# ============================================================================


class TestFieldRename:
    """field.update with rename propagates to schema and all entities."""

    def test_rename_updates_schema(self, grocery_with_items):
        """Rename changes the field key in the schema."""
        result = reduce(
            grocery_with_items,
            make_event(
                seq=7,
                type="field.update",
                payload={
                    "collection": "grocery_list",
                    "name": "store",
                    "rename": "shop",
                },
            ),
        )
        assert result.applied

        schema = result.snapshot["collections"]["grocery_list"]["schema"]
        assert "shop" in schema
        assert "store" not in schema

    def test_rename_propagates_to_all_entities(self, grocery_with_items):
        """Rename changes the field key in every entity."""
        result = reduce(
            grocery_with_items,
            make_event(
                seq=7,
                type="field.update",
                payload={
                    "collection": "grocery_list",
                    "name": "store",
                    "rename": "shop",
                },
            ),
        )
        assert result.applied

        entities = result.snapshot["collections"]["grocery_list"]["entities"]
        for eid, entity in entities.items():
            assert "shop" in entity, f"Entity {eid} missing renamed field 'shop'"
            assert "store" not in entity, f"Entity {eid} still has old field 'store'"

    def test_rename_preserves_values(self, grocery_with_items):
        """Rename doesn't change field values."""
        result = reduce(
            grocery_with_items,
            make_event(
                seq=7,
                type="field.update",
                payload={
                    "collection": "grocery_list",
                    "name": "store",
                    "rename": "shop",
                },
            ),
        )
        assert result.applied

        milk = result.snapshot["collections"]["grocery_list"]["entities"]["item_milk"]
        assert milk["shop"] == "Whole Foods"

        bread = result.snapshot["collections"]["grocery_list"]["entities"]["item_bread"]
        assert bread["shop"] is None  # Was null, stays null

    def test_rename_to_existing_field_rejects(self, grocery_with_items):
        """Rename to a name that already exists should reject."""
        result = reduce(
            grocery_with_items,
            make_event(
                seq=7,
                type="field.update",
                payload={
                    "collection": "grocery_list",
                    "name": "store",
                    "rename": "name",  # "name" already exists
                },
            ),
        )
        assert not result.applied

    def test_rename_and_type_change_together(self, grocery_collection):
        """Rename + type change in a single field.update."""
        # Add a string field, then rename + change to enum
        result = reduce(
            grocery_collection,
            make_event(
                seq=2,
                type="field.add",
                payload={
                    "collection": "grocery_list",
                    "name": "priority_text",
                    "type": "string?",
                },
            ),
        )
        result = reduce(
            result.snapshot,
            make_event(
                seq=3,
                type="field.update",
                payload={
                    "collection": "grocery_list",
                    "name": "priority_text",
                    "rename": "priority",
                    "type": {"enum": ["low", "medium", "high"]},
                },
            ),
        )
        assert result.applied

        schema = result.snapshot["collections"]["grocery_list"]["schema"]
        assert "priority" in schema
        assert "priority_text" not in schema


# ============================================================================
# field.remove — Cleanup
# ============================================================================


class TestFieldRemoveCleanup:
    """field.remove strips the field from schema and all entities."""

    def test_removes_field_from_all_entities(self, grocery_with_items):
        """Field data is removed from every entity in the collection."""
        result = reduce(
            grocery_with_items,
            make_event(
                seq=7,
                type="field.remove",
                payload={"collection": "grocery_list", "name": "store"},
            ),
        )
        assert result.applied

        entities = result.snapshot["collections"]["grocery_list"]["entities"]
        for eid, entity in entities.items():
            assert "store" not in entity, f"Entity {eid} still has removed field"

    def test_removes_field_from_schema(self, grocery_with_items):
        """Schema no longer lists the removed field."""
        result = reduce(
            grocery_with_items,
            make_event(
                seq=7,
                type="field.remove",
                payload={"collection": "grocery_list", "name": "store"},
            ),
        )
        assert result.applied

        schema = result.snapshot["collections"]["grocery_list"]["schema"]
        assert "store" not in schema
        # Other fields untouched
        assert "name" in schema
        assert "checked" in schema

    def test_remove_field_from_removed_entities_too(self, grocery_with_items_and_removed):
        """Even removed entities lose the field (they keep other data for undo)."""
        result = reduce(
            grocery_with_items_and_removed,
            make_event(
                seq=8,
                type="field.remove",
                payload={"collection": "grocery_list", "name": "store"},
            ),
        )
        assert result.applied

        bread = result.snapshot["collections"]["grocery_list"]["entities"]["item_bread"]
        assert bread["_removed"] is True
        assert "store" not in bread
        # Other fields preserved
        assert "name" in bread

    def test_remove_field_cleans_view_show_fields(self, grocery_with_view):
        """Removing a field used in a view's show_fields emits VIEW_FIELD_MISSING warning."""
        result = reduce(
            grocery_with_view,
            make_event(
                seq=8,
                type="field.remove",
                payload={"collection": "grocery_list", "name": "store"},
            ),
        )
        assert result.applied
        assert has_warning(result, "VIEW_FIELD_MISSING")

        # View config should have "store" removed from show_fields
        view = result.snapshot["views"]["grocery_by_store"]
        config = view.get("config", {})
        if "show_fields" in config:
            assert "store" not in config["show_fields"]

    def test_remove_field_cleans_view_sort_by(self, grocery_with_view):
        """Removing the field used in sort_by cleans the view config."""
        result = reduce(
            grocery_with_view,
            make_event(
                seq=8,
                type="field.remove",
                payload={"collection": "grocery_list", "name": "store"},
            ),
        )
        assert result.applied

        view = result.snapshot["views"]["grocery_by_store"]
        config = view.get("config", {})
        # sort_by referencing removed field should be cleaned
        assert config.get("sort_by") != "store"

    def test_remove_field_cleans_view_group_by(self, grocery_with_view):
        """Removing the field used in group_by cleans the view config."""
        result = reduce(
            grocery_with_view,
            make_event(
                seq=8,
                type="field.remove",
                payload={"collection": "grocery_list", "name": "store"},
            ),
        )
        assert result.applied

        view = result.snapshot["views"]["grocery_by_store"]
        config = view.get("config", {})
        assert config.get("group_by") != "store"

    def test_entity_create_after_field_remove(self, grocery_with_items):
        """After removing a field, new entities don't need to provide it."""
        result = reduce(
            grocery_with_items,
            make_event(
                seq=7,
                type="field.remove",
                payload={"collection": "grocery_list", "name": "store"},
            ),
        )
        snapshot = result.snapshot

        result = reduce(
            snapshot,
            make_event(
                seq=8,
                type="entity.create",
                payload={
                    "collection": "grocery_list",
                    "id": "item_yogurt",
                    "fields": {"name": "Yogurt", "checked": False},
                    # No "store" — it's been removed
                },
            ),
        )
        assert result.applied
        yogurt = result.snapshot["collections"]["grocery_list"]["entities"]["item_yogurt"]
        assert "store" not in yogurt


# ============================================================================
# Multi-step Schema Evolution
# ============================================================================


class TestProgressiveSchemaEvolution:
    """Simulate realistic schema growth over multiple operations."""

    def test_grocery_schema_grows_over_time(self, grocery_collection):
        """
        Start with minimal schema, progressively add fields as the user
        discovers new patterns — the L3 use case from the MVP checklist.
        """
        snapshot = grocery_collection
        seq = 2

        # Step 1: Add some items with initial schema
        for item_id, fields in [
            ("item_milk", {"name": "Milk", "checked": False}),
            ("item_eggs", {"name": "Eggs", "checked": False}),
        ]:
            result = reduce(
                snapshot,
                make_event(
                    seq=seq,
                    type="entity.create",
                    payload={
                        "collection": "grocery_list",
                        "id": item_id,
                        "fields": fields,
                    },
                ),
            )
            assert result.applied
            snapshot = result.snapshot
            seq += 1

        # Step 2: User mentions categories → L3 adds a field
        result = reduce(
            snapshot,
            make_event(
                seq=seq,
                type="field.add",
                payload={
                    "collection": "grocery_list",
                    "name": "category",
                    "type": "string?",
                },
            ),
        )
        assert result.applied
        snapshot = result.snapshot
        seq += 1

        # Verify backfill
        assert snapshot["collections"]["grocery_list"]["entities"]["item_milk"]["category"] is None
        assert snapshot["collections"]["grocery_list"]["entities"]["item_eggs"]["category"] is None

        # Step 3: Update entities with category
        result = reduce(
            snapshot,
            make_event(
                seq=seq,
                type="entity.update",
                payload={
                    "ref": "grocery_list/item_milk",
                    "fields": {"category": "dairy"},
                },
            ),
        )
        snapshot = result.snapshot
        seq += 1

        # Step 4: User mentions quantities → add quantity field
        result = reduce(
            snapshot,
            make_event(
                seq=seq,
                type="field.add",
                payload={
                    "collection": "grocery_list",
                    "name": "quantity",
                    "type": "int",
                    "default": 1,
                },
            ),
        )
        assert result.applied
        snapshot = result.snapshot
        seq += 1

        # Existing entities should have quantity=1
        assert snapshot["collections"]["grocery_list"]["entities"]["item_milk"]["quantity"] == 1

        # Step 5: Evolve category from free-text to enum
        result = reduce(
            snapshot,
            make_event(
                seq=seq,
                type="field.update",
                payload={
                    "collection": "grocery_list",
                    "name": "category",
                    "type": {"enum": ["dairy", "produce", "meat", "pantry", "other"]},
                },
            ),
        )
        assert result.applied
        snapshot = result.snapshot
        seq += 1

        # Step 6: Rename "store" to "shop"
        result = reduce(
            snapshot,
            make_event(
                seq=seq,
                type="field.update",
                payload={
                    "collection": "grocery_list",
                    "name": "store",
                    "rename": "shop",
                },
            ),
        )
        assert result.applied
        snapshot = result.snapshot
        seq += 1

        # Step 7: Add a new entity — should work with evolved schema
        result = reduce(
            snapshot,
            make_event(
                seq=seq,
                type="entity.create",
                payload={
                    "collection": "grocery_list",
                    "id": "item_steak",
                    "fields": {
                        "name": "Steak",
                        "checked": False,
                        "category": "meat",
                        "quantity": 2,
                    },
                },
            ),
        )
        assert result.applied
        snapshot = result.snapshot

        # Final verification: schema has all evolved fields
        schema = snapshot["collections"]["grocery_list"]["schema"]
        assert "name" in schema
        assert "checked" in schema
        assert "shop" in schema  # Renamed from "store"
        assert "store" not in schema
        assert "category" in schema
        assert "quantity" in schema

    def test_add_then_remove_field_roundtrip(self, grocery_with_items):
        """Add a field, use it, then remove it — schema and entities are clean."""
        snapshot = grocery_with_items
        seq = 7

        # Add
        result = reduce(
            snapshot,
            make_event(
                seq=seq,
                type="field.add",
                payload={
                    "collection": "grocery_list",
                    "name": "notes",
                    "type": "string?",
                },
            ),
        )
        snapshot = result.snapshot
        seq += 1

        # Use it
        result = reduce(
            snapshot,
            make_event(
                seq=seq,
                type="entity.update",
                payload={
                    "ref": "grocery_list/item_milk",
                    "fields": {"notes": "Get the organic kind"},
                },
            ),
        )
        snapshot = result.snapshot
        seq += 1

        assert snapshot["collections"]["grocery_list"]["entities"]["item_milk"]["notes"] == "Get the organic kind"

        # Remove it
        result = reduce(
            snapshot,
            make_event(
                seq=seq,
                type="field.remove",
                payload={"collection": "grocery_list", "name": "notes"},
            ),
        )
        assert result.applied
        snapshot = result.snapshot

        # Completely gone
        assert "notes" not in snapshot["collections"]["grocery_list"]["schema"]
        for entity in snapshot["collections"]["grocery_list"]["entities"].values():
            assert "notes" not in entity

    def test_multiple_field_adds_then_removes(self, grocery_collection):
        """Add several fields, remove some — only survivors remain."""
        snapshot = grocery_collection
        seq = 2

        # Add 3 fields
        for field_name, field_type, default in [
            ("category", "string?", None),
            ("quantity", "int", 1),
            ("notes", "string?", None),
        ]:
            result = reduce(
                snapshot,
                make_event(
                    seq=seq,
                    type="field.add",
                    payload={
                        "collection": "grocery_list",
                        "name": field_name,
                        "type": field_type,
                        "default": default,
                    },
                ),
            )
            assert result.applied
            snapshot = result.snapshot
            seq += 1

        # Remove 2 of them
        for field_name in ["category", "notes"]:
            result = reduce(
                snapshot,
                make_event(
                    seq=seq,
                    type="field.remove",
                    payload={"collection": "grocery_list", "name": field_name},
                ),
            )
            assert result.applied
            snapshot = result.snapshot
            seq += 1

        schema = snapshot["collections"]["grocery_list"]["schema"]
        assert "quantity" in schema
        assert "category" not in schema
        assert "notes" not in schema
        # Original fields still there
        assert "name" in schema
        assert "store" in schema
        assert "checked" in schema


# ============================================================================
# Replay Determinism with Schema Evolution
# ============================================================================


class TestSchemaEvolutionReplay:
    """Schema evolution events produce identical results on replay."""

    def test_replay_with_schema_evolution(self, empty):
        """
        Build a state incrementally, then replay all events from scratch.
        Both should produce the same snapshot.
        """
        events = []
        snapshot = empty

        def apply(seq, event_type, payload):
            nonlocal snapshot
            event = make_event(seq=seq, type=event_type, payload=payload)
            events.append(event)
            result = reduce(snapshot, event)
            assert result.applied, f"Event {seq} ({event_type}) rejected: {result.error}"
            snapshot = result.snapshot

        # Build up a schema evolution scenario
        apply(1, "collection.create", {
            "id": "roster",
            "schema": {"name": "string", "active": "bool"},
        })
        apply(2, "entity.create", {
            "collection": "roster",
            "id": "p1",
            "fields": {"name": "Alice", "active": True},
        })
        apply(3, "entity.create", {
            "collection": "roster",
            "id": "p2",
            "fields": {"name": "Bob", "active": False},
        })
        apply(4, "field.add", {
            "collection": "roster",
            "name": "role",
            "type": "string?",
        })
        apply(5, "entity.update", {
            "ref": "roster/p1",
            "fields": {"role": "captain"},
        })
        apply(6, "field.add", {
            "collection": "roster",
            "name": "jersey",
            "type": "int",
            "default": 0,
        })
        apply(7, "field.update", {
            "collection": "roster",
            "name": "active",
            "type": "string",
        })
        apply(8, "field.remove", {
            "collection": "roster",
            "name": "jersey",
        })

        # Now replay from scratch
        replayed = replay(events)

        # Compare — JSON serialize with sorted keys for deterministic comparison
        import json
        original_json = json.dumps(snapshot, sort_keys=True)
        replayed_json = json.dumps(replayed, sort_keys=True)
        assert original_json == replayed_json
