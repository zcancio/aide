"""
AIde Reducer — Happy Path Tests (v3 Unified Entity Model)

One test per primitive type. Apply event to appropriate state, verify snapshot.
These are the foundation tests — if any of these fail, nothing else matters.

Reference: docs/eng_design/unified_entity_model.md
"""

import pytest

from engine.kernel.events import make_event
from engine.kernel.reducer import empty_state, reduce

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def empty():
    """Fresh empty state — only block_root exists."""
    return empty_state()


GROCERY_ITEM_INTERFACE = "interface GroceryItem { name: string; store?: string; checked: boolean; }"
GROCERY_LIST_INTERFACE = "interface GroceryList { title: string; items: Record<string, GroceryItem>; }"


@pytest.fixture
def state_with_schema(empty):
    """State with GroceryItem schema."""
    result = reduce(
        empty,
        make_event(
            seq=1,
            type="schema.create",
            payload={
                "id": "grocery_item",
                "interface": GROCERY_ITEM_INTERFACE,
                "render_html": "<li>{{name}}</li>",
                "render_text": "{{#checked}}✓{{/checked}}{{^checked}}○{{/checked}} {{name}}",
                "styles": ".item { padding: 8px; }",
            },
        ),
    )
    assert result.applied
    return result.snapshot


@pytest.fixture
def state_with_two_schemas(state_with_schema):
    """State with GroceryItem and GroceryList schemas."""
    result = reduce(
        state_with_schema,
        make_event(
            seq=2,
            type="schema.create",
            payload={
                "id": "grocery_list",
                "interface": GROCERY_LIST_INTERFACE,
                "render_html": "<div><h2>{{title}}</h2><ul>{{>items}}</ul></div>",
                "render_text": "{{title}}\n{{>items}}",
            },
        ),
    )
    assert result.applied
    return result.snapshot


@pytest.fixture
def state_with_entity(state_with_two_schemas):
    """State with a grocery_list entity containing item_milk."""
    result = reduce(
        state_with_two_schemas,
        make_event(
            seq=3,
            type="entity.create",
            payload={
                "id": "my_list",
                "_schema": "grocery_list",
                "title": "My Groceries",
                "items": {
                    "item_milk": {"name": "Milk", "checked": False, "_pos": 1.0},
                },
            },
        ),
    )
    assert result.applied
    return result.snapshot


@pytest.fixture
def state_with_two_entities(state_with_two_schemas):
    """State with two top-level entities."""
    snapshot = state_with_two_schemas

    result = reduce(
        snapshot,
        make_event(
            seq=3,
            type="entity.create",
            payload={
                "id": "list_a",
                "_schema": "grocery_list",
                "title": "List A",
                "items": {},
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
                "id": "list_b",
                "_schema": "grocery_list",
                "title": "List B",
                "items": {},
            },
        ),
    )
    assert result.applied
    return result.snapshot


# ============================================================================
# 1. schema.create
# ============================================================================


class TestSchemaCreate:
    def test_creates_schema(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="schema.create",
                payload={
                    "id": "task",
                    "interface": "interface Task { title: string; done: boolean; }",
                    "render_html": "<li>{{title}}</li>",
                    "render_text": "{{#done}}✓{{/done}} {{title}}",
                    "styles": ".task { padding: 4px; }",
                },
            ),
        )

        assert result.applied
        assert result.error is None

        schema = result.snapshot["schemas"]["task"]
        assert "interface Task" in schema["interface"]
        assert schema["render_html"] == "<li>{{title}}</li>"
        assert schema["render_text"] == "{{#done}}✓{{/done}} {{title}}"
        assert schema["styles"] == ".task { padding: 4px; }"

    def test_requires_interface(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="schema.create",
                payload={"id": "task"},
            ),
        )
        assert not result.applied
        assert "MISSING_INTERFACE" in result.error

    def test_rejects_duplicate_id(self, state_with_schema):
        result = reduce(
            state_with_schema,
            make_event(
                seq=2,
                type="schema.create",
                payload={
                    "id": "grocery_item",
                    "interface": GROCERY_ITEM_INTERFACE,
                },
            ),
        )
        assert not result.applied
        assert "ALREADY_EXISTS" in result.error


# ============================================================================
# 2. schema.update
# ============================================================================


class TestSchemaUpdate:
    def test_updates_interface(self, state_with_schema):
        new_interface = "interface GroceryItem { name: string; checked: boolean; store?: string; quantity?: number; }"
        result = reduce(
            state_with_schema,
            make_event(
                seq=2,
                type="schema.update",
                payload={
                    "id": "grocery_item",
                    "interface": new_interface,
                },
            ),
        )

        assert result.applied
        schema = result.snapshot["schemas"]["grocery_item"]
        assert "quantity" in schema["interface"]

    def test_updates_render_templates(self, state_with_schema):
        result = reduce(
            state_with_schema,
            make_event(
                seq=2,
                type="schema.update",
                payload={
                    "id": "grocery_item",
                    "render_html": "<li class=\"updated\">{{name}}</li>",
                    "render_text": "- {{name}}",
                },
            ),
        )

        assert result.applied
        schema = result.snapshot["schemas"]["grocery_item"]
        assert "updated" in schema["render_html"]
        assert schema["render_text"] == "- {{name}}"
        # Unchanged field preserved
        assert schema.get("styles") == ".item { padding: 8px; }"

    def test_rejects_unknown_schema(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="schema.update",
                payload={"id": "nonexistent", "render_html": "<div/>"},
            ),
        )
        assert not result.applied
        assert "NOT_FOUND" in result.error


# ============================================================================
# 3. schema.remove
# ============================================================================


class TestSchemaRemove:
    def test_removes_unused_schema(self, state_with_schema):
        result = reduce(
            state_with_schema,
            make_event(
                seq=2,
                type="schema.remove",
                payload={"id": "grocery_item"},
            ),
        )

        assert result.applied
        schema = result.snapshot["schemas"]["grocery_item"]
        assert schema["_removed"] is True

    def test_rejects_if_entities_reference_it(self, state_with_entity):
        result = reduce(
            state_with_entity,
            make_event(
                seq=4,
                type="schema.remove",
                payload={"id": "grocery_list"},
            ),
        )

        assert not result.applied
        assert "SCHEMA_IN_USE" in result.error


# ============================================================================
# 4. entity.create
# ============================================================================


class TestEntityCreate:
    def test_creates_top_level_entity(self, state_with_two_schemas):
        result = reduce(
            state_with_two_schemas,
            make_event(
                seq=3,
                type="entity.create",
                payload={
                    "id": "my_list",
                    "_schema": "grocery_list",
                    "title": "My Groceries",
                    "items": {
                        "item_milk": {"name": "Milk", "checked": False, "_pos": 1.0},
                    },
                },
            ),
        )

        assert result.applied
        assert result.error is None

        entity = result.snapshot["entities"]["my_list"]
        assert entity["title"] == "My Groceries"
        assert entity["_schema"] == "grocery_list"
        assert "item_milk" in entity["items"]
        assert entity["items"]["item_milk"]["name"] == "Milk"

    def test_creates_entity_without_schema(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="entity.create",
                payload={
                    "id": "freeform_note",
                    "content": "Just a note",
                },
            ),
        )
        assert result.applied
        assert result.snapshot["entities"]["freeform_note"]["content"] == "Just a note"

    def test_rejects_duplicate_id(self, state_with_entity):
        result = reduce(
            state_with_entity,
            make_event(
                seq=4,
                type="entity.create",
                payload={
                    "id": "my_list",
                    "_schema": "grocery_list",
                    "title": "Duplicate",
                    "items": {},
                },
            ),
        )
        assert not result.applied
        assert "ALREADY_EXISTS" in result.error

    def test_rejects_unknown_schema(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="entity.create",
                payload={
                    "id": "my_entity",
                    "_schema": "nonexistent_schema",
                    "title": "Test",
                },
            ),
        )
        assert not result.applied
        assert "SCHEMA_NOT_FOUND" in result.error

    def test_sets_pos_for_ordering(self, state_with_two_schemas):
        result = reduce(
            state_with_two_schemas,
            make_event(
                seq=3,
                type="entity.create",
                payload={
                    "id": "my_list",
                    "_schema": "grocery_list",
                    "title": "My List",
                    "_pos": 1.5,
                    "items": {},
                },
            ),
        )
        assert result.applied
        assert result.snapshot["entities"]["my_list"]["_pos"] == 1.5


# ============================================================================
# 5. entity.update
# ============================================================================


class TestEntityUpdate:
    def test_merges_top_level_fields(self, state_with_entity):
        result = reduce(
            state_with_entity,
            make_event(
                seq=4,
                type="entity.update",
                payload={
                    "id": "my_list",
                    "title": "Updated Groceries",
                },
            ),
        )

        assert result.applied
        entity = result.snapshot["entities"]["my_list"]
        assert entity["title"] == "Updated Groceries"
        # Children untouched
        assert "item_milk" in entity["items"]

    def test_updates_nested_child_via_path(self, state_with_entity):
        result = reduce(
            state_with_entity,
            make_event(
                seq=4,
                type="entity.update",
                payload={
                    "id": "my_list/items/item_milk",
                    "checked": True,
                },
            ),
        )

        assert result.applied
        entity = result.snapshot["entities"]["my_list"]
        assert entity["items"]["item_milk"]["checked"] is True
        # Other fields preserved
        assert entity["items"]["item_milk"]["name"] == "Milk"

    def test_merges_child_collection(self, state_with_entity):
        result = reduce(
            state_with_entity,
            make_event(
                seq=4,
                type="entity.update",
                payload={
                    "id": "my_list",
                    "items": {
                        "item_eggs": {"name": "Eggs", "checked": False, "_pos": 2.0},
                        "item_milk": {"checked": True},
                    },
                },
            ),
        )

        assert result.applied
        items = result.snapshot["entities"]["my_list"]["items"]
        # New child added
        assert "item_eggs" in items
        assert items["item_eggs"]["name"] == "Eggs"
        # Existing child updated
        assert items["item_milk"]["checked"] is True
        # Existing child data preserved
        assert items["item_milk"]["name"] == "Milk"

    def test_removes_child_via_null(self, state_with_entity):
        result = reduce(
            state_with_entity,
            make_event(
                seq=4,
                type="entity.update",
                payload={
                    "id": "my_list",
                    "items": {"item_milk": None},
                },
            ),
        )

        assert result.applied
        item = result.snapshot["entities"]["my_list"]["items"]["item_milk"]
        assert item["_removed"] is True

    def test_updates_pos(self, state_with_entity):
        result = reduce(
            state_with_entity,
            make_event(
                seq=4,
                type="entity.update",
                payload={"id": "my_list", "_pos": 2.0},
            ),
        )
        assert result.applied
        assert result.snapshot["entities"]["my_list"]["_pos"] == 2.0


# ============================================================================
# 6. entity.remove
# ============================================================================


class TestEntityRemove:
    def test_soft_deletes_entity(self, state_with_entity):
        result = reduce(
            state_with_entity,
            make_event(
                seq=4,
                type="entity.remove",
                payload={"id": "my_list"},
            ),
        )

        assert result.applied
        entity = result.snapshot["entities"]["my_list"]
        assert entity["_removed"] is True
        # Data preserved for event replay
        assert entity["title"] == "My Groceries"

    def test_rejects_unknown_entity(self, empty):
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="entity.remove",
                payload={"id": "nonexistent"},
            ),
        )
        assert not result.applied
        assert "NOT_FOUND" in result.error


# ============================================================================
# 7. block.set (create mode)
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
                    "level": 1,
                    "text": "My Page",
                },
            ),
        )

        assert result.applied
        blocks = result.snapshot["blocks"]
        assert "block_title" in blocks
        assert blocks["block_title"]["type"] == "heading"
        assert blocks["block_title"]["text"] == "My Page"
        assert "block_title" in blocks["block_root"]["children"]

    def test_updates_existing_block(self, empty):
        # Create
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="block.set",
                payload={
                    "id": "block_title",
                    "type": "heading",
                    "parent": "block_root",
                    "level": 1,
                    "text": "Original",
                },
            ),
        )
        snapshot = result.snapshot

        # Update
        result = reduce(
            snapshot,
            make_event(
                seq=2,
                type="block.set",
                payload={
                    "id": "block_title",
                    "type": "heading",
                    "parent": "block_root",
                    "text": "Updated",
                },
            ),
        )

        assert result.applied
        assert result.snapshot["blocks"]["block_title"]["text"] == "Updated"
        # Type unchanged
        assert result.snapshot["blocks"]["block_title"]["type"] == "heading"


# ============================================================================
# 8. block.remove
# ============================================================================


class TestBlockRemove:
    def test_removes_block_from_tree(self, empty):
        # Create
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="block.set",
                payload={
                    "id": "block_title",
                    "type": "heading",
                    "parent": "block_root",
                    "text": "My Page",
                },
            ),
        )
        snapshot = result.snapshot

        # Remove
        result = reduce(
            snapshot,
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
# 9. block.reorder
# ============================================================================


class TestBlockReorder:
    def test_reorders_children(self, empty):
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
                        "text": block_id,
                    },
                ),
            )
            snapshot = result.snapshot

        assert snapshot["blocks"]["block_root"]["children"] == [
            "block_a",
            "block_b",
            "block_c",
        ]

        result = reduce(
            snapshot,
            make_event(
                seq=4,
                type="block.reorder",
                payload={
                    "parent": "block_root",
                    "order": ["block_c", "block_a", "block_b"],
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
# 10. style.set
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
            make_event(seq=1, type="style.set", payload={"primary_color": "#1a365d"}),
        )
        snapshot = result.snapshot

        result = reduce(
            snapshot,
            make_event(seq=2, type="style.set", payload={"font_family": "Georgia"}),
        )

        assert result.applied
        styles = result.snapshot["styles"]
        assert styles["primary_color"] == "#1a365d"
        assert styles["font_family"] == "Georgia"


# ============================================================================
# 11. meta.update
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
# 12. meta.annotate
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
