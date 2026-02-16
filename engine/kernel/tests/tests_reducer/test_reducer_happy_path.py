"""
AIde Reducer — Happy Path Tests (Category 1)

One test per primitive type. Apply event to appropriate state, verify snapshot.
These are the foundation tests — if any of these fail, nothing else matters.

Reference: aide_reducer_spec.md, aide_primitive_schemas.md
"""

import copy
import json
import pytest

# ---------------------------------------------------------------------------
# These imports assume the reducer module lives at backend/kernel/reducer.py
# Adjust the import path to match the actual project layout.
# ---------------------------------------------------------------------------
from engine.kernel.reducer import reduce, empty_state
from engine.kernel.events import make_event


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def empty():
    """Fresh empty state — only block_root exists."""
    return empty_state()


@pytest.fixture
def state_with_collection(empty):
    """State with a grocery_list collection (no entities)."""
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
def state_with_entity(state_with_collection):
    """State with a grocery_list collection and one entity (item_milk)."""
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
    assert result.applied
    return result.snapshot


@pytest.fixture
def state_with_two_entities(state_with_entity):
    """State with grocery_list containing item_milk and item_eggs."""
    result = reduce(
        state_with_entity,
        make_event(
            seq=3,
            type="entity.create",
            payload={
                "collection": "grocery_list",
                "id": "item_eggs",
                "fields": {"name": "Eggs", "store": None, "checked": False},
            },
        ),
    )
    assert result.applied
    return result.snapshot


@pytest.fixture
def state_with_roster_and_schedule(empty):
    """State with two collections: roster (2 players) and schedule (1 game)."""
    snapshot = empty

    # Create roster collection
    result = reduce(
        snapshot,
        make_event(
            seq=1,
            type="collection.create",
            payload={
                "id": "roster",
                "name": "Roster",
                "schema": {"name": "string", "status": "string"},
            },
        ),
    )
    snapshot = result.snapshot

    # Create schedule collection
    result = reduce(
        snapshot,
        make_event(
            seq=2,
            type="collection.create",
            payload={
                "id": "schedule",
                "name": "Schedule",
                "schema": {"date": "date", "host": "string?", "status": "string"},
            },
        ),
    )
    snapshot = result.snapshot

    # Add two players
    result = reduce(
        snapshot,
        make_event(
            seq=3,
            type="entity.create",
            payload={
                "collection": "roster",
                "id": "player_mike",
                "fields": {"name": "Mike", "status": "active"},
            },
        ),
    )
    snapshot = result.snapshot

    result = reduce(
        snapshot,
        make_event(
            seq=4,
            type="entity.create",
            payload={
                "collection": "roster",
                "id": "player_dave",
                "fields": {"name": "Dave", "status": "active"},
            },
        ),
    )
    snapshot = result.snapshot

    # Add one game
    result = reduce(
        snapshot,
        make_event(
            seq=5,
            type="entity.create",
            payload={
                "collection": "schedule",
                "id": "game_feb27",
                "fields": {
                    "date": "2026-02-27",
                    "host": None,
                    "status": "confirmed",
                },
            },
        ),
    )
    snapshot = result.snapshot

    return snapshot


@pytest.fixture
def state_with_view(state_with_collection):
    """State with a grocery_list collection and a list view."""
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
    assert result.applied
    return result.snapshot


@pytest.fixture
def state_with_block(empty):
    """State with a heading block in block_root."""
    result = reduce(
        empty,
        make_event(
            seq=1,
            type="block.set",
            payload={
                "id": "block_title",
                "type": "heading",
                "parent": "block_root",
                "props": {"level": 1, "content": "Poker League"},
            },
        ),
    )
    assert result.applied
    return result.snapshot


# ============================================================================
# 1. entity.create
# ============================================================================


class TestEntityCreate:
    def test_creates_entity_in_collection(self, state_with_collection):
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="entity.create",
                payload={
                    "collection": "grocery_list",
                    "id": "item_milk",
                    "fields": {
                        "name": "Milk",
                        "store": "Whole Foods",
                        "checked": False,
                    },
                },
            ),
        )

        assert result.applied
        assert result.error is None

        entity = result.snapshot["collections"]["grocery_list"]["entities"]["item_milk"]
        assert entity["name"] == "Milk"
        assert entity["store"] == "Whole Foods"
        assert entity["checked"] is False
        assert entity["_removed"] is False

    def test_nullable_fields_default_to_null(self, state_with_collection):
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="entity.create",
                payload={
                    "collection": "grocery_list",
                    "id": "item_bread",
                    "fields": {"name": "Bread", "checked": False},
                    # store (string?) not provided
                },
            ),
        )

        assert result.applied
        entity = result.snapshot["collections"]["grocery_list"]["entities"][
            "item_bread"
        ]
        assert entity["store"] is None


# ============================================================================
# 2. entity.update
# ============================================================================


class TestEntityUpdate:
    def test_merges_fields(self, state_with_entity):
        result = reduce(
            state_with_entity,
            make_event(
                seq=3,
                type="entity.update",
                payload={
                    "ref": "grocery_list/item_milk",
                    "fields": {"checked": True},
                },
            ),
        )

        assert result.applied
        entity = result.snapshot["collections"]["grocery_list"]["entities"]["item_milk"]
        assert entity["checked"] is True
        # Unmentioned fields unchanged
        assert entity["name"] == "Milk"
        assert entity["store"] == "Whole Foods"

    def test_can_set_nullable_to_null(self, state_with_entity):
        result = reduce(
            state_with_entity,
            make_event(
                seq=3,
                type="entity.update",
                payload={
                    "ref": "grocery_list/item_milk",
                    "fields": {"store": None},
                },
            ),
        )

        assert result.applied
        entity = result.snapshot["collections"]["grocery_list"]["entities"]["item_milk"]
        assert entity["store"] is None


# ============================================================================
# 3. entity.remove
# ============================================================================


class TestEntityRemove:
    def test_soft_deletes_entity(self, state_with_entity):
        result = reduce(
            state_with_entity,
            make_event(
                seq=3,
                type="entity.remove",
                payload={"ref": "grocery_list/item_milk"},
            ),
        )

        assert result.applied
        entity = result.snapshot["collections"]["grocery_list"]["entities"]["item_milk"]
        assert entity["_removed"] is True
        # Data is preserved for undo
        assert entity["name"] == "Milk"


# ============================================================================
# 4. collection.create
# ============================================================================


class TestCollectionCreate:
    def test_creates_empty_collection(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="collection.create",
                payload={
                    "id": "tasks",
                    "name": "Tasks",
                    "schema": {
                        "title": "string",
                        "done": "bool",
                        "due": "date?",
                    },
                },
            ),
        )

        assert result.applied
        coll = result.snapshot["collections"]["tasks"]
        assert coll["name"] == "Tasks"
        assert coll["schema"]["title"] == "string"
        assert coll["schema"]["done"] == "bool"
        assert coll["schema"]["due"] == "date?"
        assert coll["entities"] == {}
        assert coll["_removed"] is False


# ============================================================================
# 5. collection.update
# ============================================================================


class TestCollectionUpdate:
    def test_updates_name_and_settings(self, state_with_collection):
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="collection.update",
                payload={
                    "id": "grocery_list",
                    "name": "Weekly Groceries",
                    "settings": {"default_store": "Whole Foods"},
                },
            ),
        )

        assert result.applied
        coll = result.snapshot["collections"]["grocery_list"]
        assert coll["name"] == "Weekly Groceries"
        assert coll["settings"]["default_store"] == "Whole Foods"


# ============================================================================
# 6. collection.remove
# ============================================================================


class TestCollectionRemove:
    def test_removes_collection_and_entities(self, state_with_two_entities):
        result = reduce(
            state_with_two_entities,
            make_event(
                seq=4,
                type="collection.remove",
                payload={"id": "grocery_list"},
            ),
        )

        assert result.applied
        coll = result.snapshot["collections"]["grocery_list"]
        assert coll["_removed"] is True
        # All entities also removed
        for entity in coll["entities"].values():
            assert entity["_removed"] is True


# ============================================================================
# 7. field.add
# ============================================================================


class TestFieldAdd:
    def test_adds_nullable_field_with_backfill(self, state_with_two_entities):
        result = reduce(
            state_with_two_entities,
            make_event(
                seq=4,
                type="field.add",
                payload={
                    "collection": "grocery_list",
                    "name": "category",
                    "type": "string?",
                    "default": None,
                },
            ),
        )

        assert result.applied
        schema = result.snapshot["collections"]["grocery_list"]["schema"]
        assert "category" in schema
        assert schema["category"] == "string?"

        # Existing entities backfilled with default
        for entity in result.snapshot["collections"]["grocery_list"][
            "entities"
        ].values():
            assert entity["category"] is None


# ============================================================================
# 8. field.update
# ============================================================================


class TestFieldUpdate:
    def test_changes_field_type(self, state_with_collection):
        # First add a field we can change
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="field.add",
                payload={
                    "collection": "grocery_list",
                    "name": "category",
                    "type": "string?",
                    "default": None,
                },
            ),
        )
        snapshot = result.snapshot

        # Now change it to an enum
        result = reduce(
            snapshot,
            make_event(
                seq=3,
                type="field.update",
                payload={
                    "collection": "grocery_list",
                    "name": "category",
                    "type": {
                        "enum": ["produce", "dairy", "meat", "pantry", "other"]
                    },
                },
            ),
        )

        assert result.applied
        schema = result.snapshot["collections"]["grocery_list"]["schema"]
        assert schema["category"] == {
            "enum": ["produce", "dairy", "meat", "pantry", "other"]
        }


# ============================================================================
# 9. field.remove
# ============================================================================


class TestFieldRemove:
    def test_removes_field_from_schema_and_entities(self, state_with_two_entities):
        result = reduce(
            state_with_two_entities,
            make_event(
                seq=4,
                type="field.remove",
                payload={"collection": "grocery_list", "name": "store"},
            ),
        )

        assert result.applied
        schema = result.snapshot["collections"]["grocery_list"]["schema"]
        assert "store" not in schema

        # Field removed from all entities
        for entity in result.snapshot["collections"]["grocery_list"][
            "entities"
        ].values():
            assert "store" not in entity


# ============================================================================
# 10. relationship.set
# ============================================================================


class TestRelationshipSet:
    def test_creates_relationship(self, state_with_roster_and_schedule):
        result = reduce(
            state_with_roster_and_schedule,
            make_event(
                seq=6,
                type="relationship.set",
                payload={
                    "from": "roster/player_dave",
                    "to": "schedule/game_feb27",
                    "type": "hosting",
                    "cardinality": "many_to_one",
                },
            ),
        )

        assert result.applied
        rels = result.snapshot["relationships"]
        assert len(rels) == 1
        assert rels[0]["from"] == "roster/player_dave"
        assert rels[0]["to"] == "schedule/game_feb27"
        assert rels[0]["type"] == "hosting"

        # Relationship type registered
        assert "hosting" in result.snapshot["relationship_types"]
        assert (
            result.snapshot["relationship_types"]["hosting"]["cardinality"]
            == "many_to_one"
        )


# ============================================================================
# 11. relationship.constrain
# ============================================================================


class TestRelationshipConstrain:
    def test_stores_constraint(self, state_with_roster_and_schedule):
        result = reduce(
            state_with_roster_and_schedule,
            make_event(
                seq=6,
                type="relationship.constrain",
                payload={
                    "id": "constraint_no_mike_dave",
                    "rule": "exclude_pair",
                    "entities": [
                        "roster/player_mike",
                        "roster/player_dave",
                    ],
                    "relationship_type": "hosting",
                    "message": "Mike and Dave can't both host the same game",
                },
            ),
        )

        assert result.applied
        constraints = result.snapshot["constraints"]
        assert len(constraints) == 1
        assert constraints[0]["id"] == "constraint_no_mike_dave"
        assert constraints[0]["rule"] == "exclude_pair"


# ============================================================================
# 12. block.set (create mode)
# ============================================================================


class TestBlockSet:
    def test_creates_block_in_tree(self, empty):
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

        assert result.applied
        blocks = result.snapshot["blocks"]
        assert "block_title" in blocks
        assert blocks["block_title"]["type"] == "heading"
        assert blocks["block_title"]["props"]["content"] == "My Page"
        assert "block_title" in blocks["block_root"]["children"]

    def test_updates_existing_block_props(self, state_with_block):
        result = reduce(
            state_with_block,
            make_event(
                seq=2,
                type="block.set",
                payload={
                    "id": "block_title",
                    "props": {"content": "Updated Title"},
                },
            ),
        )

        assert result.applied
        assert (
            result.snapshot["blocks"]["block_title"]["props"]["content"]
            == "Updated Title"
        )
        # Type unchanged
        assert result.snapshot["blocks"]["block_title"]["type"] == "heading"


# ============================================================================
# 13. block.remove
# ============================================================================


class TestBlockRemove:
    def test_removes_block_from_tree(self, state_with_block):
        result = reduce(
            state_with_block,
            make_event(
                seq=2,
                type="block.remove",
                payload={"id": "block_title"},
            ),
        )

        assert result.applied
        assert "block_title" not in result.snapshot["blocks"]
        assert "block_title" not in result.snapshot["blocks"]["block_root"]["children"]


# ============================================================================
# 14. block.reorder
# ============================================================================


class TestBlockReorder:
    def test_reorders_children(self, empty):
        # Create 3 blocks
        snapshot = empty
        for i, block_id in enumerate(["block_a", "block_b", "block_c"]):
            result = reduce(
                snapshot,
                make_event(
                    seq=i + 1,
                    type="block.set",
                    payload={
                        "id": block_id,
                        "type": "text",
                        "parent": "block_root",
                        "props": {"content": block_id},
                    },
                ),
            )
            snapshot = result.snapshot

        assert snapshot["blocks"]["block_root"]["children"] == [
            "block_a",
            "block_b",
            "block_c",
        ]

        # Reorder: c, a, b
        result = reduce(
            snapshot,
            make_event(
                seq=4,
                type="block.reorder",
                payload={
                    "parent": "block_root",
                    "children": ["block_c", "block_a", "block_b"],
                },
            ),
        )

        assert result.applied
        assert result.snapshot["blocks"]["block_root"]["children"] == [
            "block_c",
            "block_a",
            "block_b",
        ]


# ============================================================================
# 15. view.create
# ============================================================================


class TestViewCreate:
    def test_creates_view(self, state_with_collection):
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="view.create",
                payload={
                    "id": "grocery_view",
                    "type": "list",
                    "source": "grocery_list",
                    "config": {
                        "show_fields": ["name", "checked"],
                        "sort_by": "name",
                        "sort_order": "asc",
                    },
                },
            ),
        )

        assert result.applied
        view = result.snapshot["views"]["grocery_view"]
        assert view["type"] == "list"
        assert view["source"] == "grocery_list"
        assert view["config"]["show_fields"] == ["name", "checked"]


# ============================================================================
# 16. view.update
# ============================================================================


class TestViewUpdate:
    def test_merges_config(self, state_with_view):
        result = reduce(
            state_with_view,
            make_event(
                seq=3,
                type="view.update",
                payload={
                    "id": "grocery_view",
                    "config": {"show_fields": ["name", "store", "checked"]},
                },
            ),
        )

        assert result.applied
        view = result.snapshot["views"]["grocery_view"]
        assert view["config"]["show_fields"] == ["name", "store", "checked"]
        # View type unchanged
        assert view["type"] == "list"


# ============================================================================
# 17. view.remove
# ============================================================================


class TestViewRemove:
    def test_removes_view(self, state_with_view):
        result = reduce(
            state_with_view,
            make_event(
                seq=3,
                type="view.remove",
                payload={"id": "grocery_view"},
            ),
        )

        assert result.applied
        assert "grocery_view" not in result.snapshot["views"]


# ============================================================================
# 18. style.set
# ============================================================================


class TestStyleSet:
    def test_sets_style_tokens(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="style.set",
                payload={
                    "primary_color": "#1a365d",
                    "font_family": "Georgia",
                    "density": "compact",
                },
            ),
        )

        assert result.applied
        styles = result.snapshot["styles"]
        assert styles["primary_color"] == "#1a365d"
        assert styles["font_family"] == "Georgia"
        assert styles["density"] == "compact"

    def test_merges_with_existing_styles(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="style.set",
                payload={"primary_color": "#1a365d"},
            ),
        )
        snapshot = result.snapshot

        result = reduce(
            snapshot,
            make_event(
                seq=2,
                type="style.set",
                payload={"font_family": "Georgia"},
            ),
        )

        assert result.applied
        styles = result.snapshot["styles"]
        assert styles["primary_color"] == "#1a365d"  # Preserved
        assert styles["font_family"] == "Georgia"  # Added


# ============================================================================
# 19. style.set_entity
# ============================================================================


class TestStyleSetEntity:
    def test_sets_entity_style_overrides(self, state_with_entity):
        result = reduce(
            state_with_entity,
            make_event(
                seq=3,
                type="style.set_entity",
                payload={
                    "ref": "grocery_list/item_milk",
                    "styles": {"highlight": True, "bg_color": "#fef3c7"},
                },
            ),
        )

        assert result.applied
        entity = result.snapshot["collections"]["grocery_list"]["entities"]["item_milk"]
        assert entity["_styles"]["highlight"] is True
        assert entity["_styles"]["bg_color"] == "#fef3c7"


# ============================================================================
# 20. meta.update
# ============================================================================


class TestMetaUpdate:
    def test_updates_meta_properties(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="meta.update",
                payload={
                    "title": "Poker League",
                    "identity": "Poker league. 8 players, biweekly Thursday.",
                    "visibility": "unlisted",
                },
            ),
        )

        assert result.applied
        meta = result.snapshot["meta"]
        assert meta["title"] == "Poker League"
        assert meta["identity"] == "Poker league. 8 players, biweekly Thursday."
        assert meta["visibility"] == "unlisted"


# ============================================================================
# 21. meta.annotate
# ============================================================================


class TestMetaAnnotate:
    def test_appends_annotation(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="meta.annotate",
                payload={
                    "note": "League started. 8 players confirmed.",
                    "pinned": False,
                },
            ),
        )

        assert result.applied
        annotations = result.snapshot["annotations"]
        assert len(annotations) == 1
        assert annotations[0]["note"] == "League started. 8 players confirmed."
        assert annotations[0]["pinned"] is False
        assert annotations[0]["seq"] == 1

    def test_pinned_annotation(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="meta.annotate",
                payload={
                    "note": "Important: venue changed.",
                    "pinned": True,
                },
            ),
        )

        assert result.applied
        assert result.snapshot["annotations"][0]["pinned"] is True


# ============================================================================
# 22. meta.constrain
# ============================================================================


class TestMetaConstrain:
    def test_stores_collection_constraint(self, state_with_collection):
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="meta.constrain",
                payload={
                    "id": "constraint_max_items",
                    "rule": "collection_max_entities",
                    "collection": "grocery_list",
                    "value": 50,
                    "message": "Maximum 50 items",
                },
            ),
        )

        assert result.applied
        constraints = result.snapshot["constraints"]
        assert len(constraints) == 1
        assert constraints[0]["id"] == "constraint_max_items"
        assert constraints[0]["rule"] == "collection_max_entities"
        assert constraints[0]["value"] == 50

    def test_updates_existing_constraint(self, state_with_collection):
        # Create constraint
        result = reduce(
            state_with_collection,
            make_event(
                seq=2,
                type="meta.constrain",
                payload={
                    "id": "constraint_max_items",
                    "rule": "collection_max_entities",
                    "collection": "grocery_list",
                    "value": 50,
                    "message": "Maximum 50 items",
                },
            ),
        )
        snapshot = result.snapshot

        # Update same constraint
        result = reduce(
            snapshot,
            make_event(
                seq=3,
                type="meta.constrain",
                payload={
                    "id": "constraint_max_items",
                    "rule": "collection_max_entities",
                    "collection": "grocery_list",
                    "value": 100,
                    "message": "Maximum 100 items",
                },
            ),
        )

        assert result.applied
        constraints = result.snapshot["constraints"]
        assert len(constraints) == 1  # Updated, not duplicated
        assert constraints[0]["value"] == 100
