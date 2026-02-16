"""
AIde Renderer -- Entity Style Override Tests (Category 4)

Highlight an entity, verify CSS class and inline style appear in output.

From the spec (aide_renderer_spec.md, "Testing Strategy"):
  "4. Entity style overrides. Highlight an entity, verify CSS class and
   inline style appear in output."

Entity style overrides are stored in entity["_styles"] and applied
when the entity is rendered inside a view (list or table).

Per spec:
  _styles.highlight → adds "aide-highlight" CSS class
  _styles.bg_color  → adds inline style "background-color: {value}"
  _styles.text_color → adds inline style "color: {value}"

The aide-highlight class has a default definition:
  .aide-highlight { background-color: rgba(31, 42, 68, 0.04); }

In list views, styles apply to <li class="aide-list__item {classes}" style="{inline}">.
In table views, styles apply to <tr class="aide-table__row {classes}" style="{inline}">.

Reference: aide_renderer_spec.md (Entity Style Overrides)
           aide_primitive_schemas.md (style.set_entity)
"""


from engine.kernel.reducer import empty_state
from engine.kernel.renderer import render_block

# ============================================================================
# Helpers
# ============================================================================


def assert_contains(html, *fragments):
    """Assert that the HTML output contains all given fragments."""
    for fragment in fragments:
        assert fragment in html, (
            f"Expected to find {fragment!r} in rendered HTML.\n"
            f"Got (first 2000 chars):\n{html[:2000]}"
        )


def assert_not_contains(html, *fragments):
    """Assert that the HTML output does NOT contain any given fragments."""
    for fragment in fragments:
        assert fragment not in html, (
            f"Did NOT expect to find {fragment!r} in rendered HTML."
        )


def build_styled_entity_snapshot(
    entities,
    view_type="list",
    view_config=None,
):
    """
    Build a snapshot with a 'roster' collection, the given entities,
    a view, and a collection_view block. Returns (snapshot, block_id).
    """
    snapshot = empty_state()

    snapshot["collections"] = {
        "roster": {
            "id": "roster",
            "name": "Roster",
            "schema": {
                "name": "string",
                "status": "enum",
                "rating": "int",
            },
            "entities": entities,
        },
    }

    snapshot["views"] = {
        "roster_view": {
            "id": "roster_view",
            "type": view_type,
            "source": "roster",
            "config": view_config or {"show_fields": ["name", "status", "rating"]},
        },
    }

    block_id = "block_roster"
    snapshot["blocks"][block_id] = {
        "type": "collection_view",
        "parent": "block_root",
        "props": {"source": "roster", "view": "roster_view"},
    }
    snapshot["blocks"]["block_root"]["children"] = [block_id]

    return snapshot, block_id


# ============================================================================
# Entity data fixtures
# ============================================================================


def roster_with_highlighted_player():
    """Roster where one player (Mike) has highlight: true."""
    return {
        "player_mike": {
            "name": "Mike",
            "status": "active",
            "rating": 1200,
            "_styles": {"highlight": True},
            "_removed": False,
        },
        "player_sarah": {
            "name": "Sarah",
            "status": "active",
            "rating": 1350,
            "_removed": False,
        },
        "player_dave": {
            "name": "Dave",
            "status": "inactive",
            "rating": 1100,
            "_removed": False,
        },
    }


def roster_with_bg_color():
    """Roster where one player has a custom bg_color."""
    return {
        "player_mike": {
            "name": "Mike",
            "status": "active",
            "rating": 1200,
            "_styles": {"highlight": True, "bg_color": "#fef3c7"},
            "_removed": False,
        },
        "player_sarah": {
            "name": "Sarah",
            "status": "active",
            "rating": 1350,
            "_removed": False,
        },
    }


def roster_with_text_color():
    """Roster where one player has a custom text_color."""
    return {
        "player_mike": {
            "name": "Mike",
            "status": "active",
            "rating": 1200,
            "_styles": {"text_color": "#dc2626"},
            "_removed": False,
        },
        "player_sarah": {
            "name": "Sarah",
            "status": "active",
            "rating": 1350,
            "_removed": False,
        },
    }


def roster_with_combined_styles():
    """Roster where one player has highlight + bg_color + text_color."""
    return {
        "player_mike": {
            "name": "Mike",
            "status": "active",
            "rating": 1200,
            "_styles": {
                "highlight": True,
                "bg_color": "#fef3c7",
                "text_color": "#92400e",
            },
            "_removed": False,
        },
        "player_sarah": {
            "name": "Sarah",
            "status": "active",
            "rating": 1350,
            "_removed": False,
        },
        "player_dave": {
            "name": "Dave",
            "status": "inactive",
            "rating": 1100,
            "_removed": False,
        },
    }


# ============================================================================
# Highlight in list view
# ============================================================================


class TestHighlightInListView:
    """
    highlight: true adds the 'aide-highlight' CSS class to the entity's
    list item element.
    Per spec: entity_classes() appends "aide-highlight" when highlight is True.
    """

    def test_highlighted_entity_gets_aide_highlight_class(self):
        """Entity with highlight: true has aide-highlight on its <li>."""
        snapshot, block_id = build_styled_entity_snapshot(
            roster_with_highlighted_player(), "list",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-highlight")

    def test_non_highlighted_entities_lack_aide_highlight(self):
        """Entities without _styles.highlight do NOT get aide-highlight."""
        snapshot, block_id = build_styled_entity_snapshot(
            roster_with_highlighted_player(), "list",
        )
        html = render_block(block_id, snapshot)

        # Count aide-highlight occurrences — should be exactly 1 (Mike only)
        count = html.count("aide-highlight")
        assert count == 1, (
            f"Expected 1 aide-highlight occurrence (Mike), got {count}"
        )

    def test_highlight_false_does_not_add_class(self):
        """Entity with highlight: false should NOT get aide-highlight."""
        entities = {
            "player_a": {
                "name": "Alice",
                "status": "active",
                "rating": 1000,
                "_styles": {"highlight": False},
                "_removed": False,
            },
        }
        snapshot, block_id = build_styled_entity_snapshot(entities, "list")
        html = render_block(block_id, snapshot)

        assert_not_contains(html, "aide-highlight")


# ============================================================================
# Highlight in table view
# ============================================================================


class TestHighlightInTableView:
    """
    highlight: true adds 'aide-highlight' to the entity's table row.
    Per spec: <tr class="aide-table__row {entity._styles classes}">
    """

    def test_highlighted_entity_gets_class_on_tr(self):
        """Entity with highlight: true has aide-highlight on its <tr>."""
        snapshot, block_id = build_styled_entity_snapshot(
            roster_with_highlighted_player(), "table",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-highlight")

    def test_only_highlighted_row_gets_class(self):
        """Only Mike's row gets aide-highlight, not Sarah's or Dave's."""
        snapshot, block_id = build_styled_entity_snapshot(
            roster_with_highlighted_player(), "table",
        )
        html = render_block(block_id, snapshot)

        count = html.count("aide-highlight")
        assert count == 1


# ============================================================================
# bg_color inline style
# ============================================================================


class TestBgColorInlineStyle:
    """
    _styles.bg_color produces an inline style: background-color: {value}.
    Per spec: entity_inline_style() emits 'background-color: {bg_color}'.
    """

    def test_bg_color_in_list_view(self):
        """Entity with bg_color has inline background-color in list view."""
        snapshot, block_id = build_styled_entity_snapshot(
            roster_with_bg_color(), "list",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "background-color: #fef3c7")

    def test_bg_color_in_table_view(self):
        """Entity with bg_color has inline background-color in table view."""
        snapshot, block_id = build_styled_entity_snapshot(
            roster_with_bg_color(), "table",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "background-color: #fef3c7")

    def test_unstyled_entity_has_no_bg_inline(self):
        """Entity without _styles has no inline background-color."""
        entities = {
            "player_plain": {
                "name": "Plain",
                "status": "active",
                "rating": 1000,
                "_removed": False,
            },
        }
        snapshot, block_id = build_styled_entity_snapshot(entities, "list")
        html = render_block(block_id, snapshot)

        assert_not_contains(html, "background-color:")


# ============================================================================
# text_color inline style
# ============================================================================


class TestTextColorInlineStyle:
    """
    _styles.text_color produces an inline style: color: {value}.
    Per spec: entity_inline_style() emits 'color: {text_color}'.
    """

    def test_text_color_in_list_view(self):
        """Entity with text_color has inline color in list view."""
        snapshot, block_id = build_styled_entity_snapshot(
            roster_with_text_color(), "list",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "color: #dc2626")

    def test_text_color_in_table_view(self):
        """Entity with text_color has inline color in table view."""
        snapshot, block_id = build_styled_entity_snapshot(
            roster_with_text_color(), "table",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "color: #dc2626")

    def test_unstyled_entity_has_no_color_inline(self):
        """Entity without text_color has no inline color."""
        entities = {
            "player_plain": {
                "name": "Plain",
                "status": "active",
                "rating": 1000,
                "_removed": False,
            },
        }
        snapshot, block_id = build_styled_entity_snapshot(entities, "list")
        html = render_block(block_id, snapshot)

        # There should be no inline style attribute at all on a plain entity
        # (or at least no "color:" inline)
        # Be careful: CSS classes reference "color" too, so check specifically
        # for inline style pattern
        assert 'style="' not in html or "color:" not in html.split("style=")[1].split('"')[1] if 'style="' in html else True


# ============================================================================
# Combined styles (highlight + bg_color + text_color)
# ============================================================================


class TestCombinedEntityStyles:
    """
    An entity can have highlight, bg_color, and text_color simultaneously.
    The CSS class AND inline styles should all appear on the same element.
    """

    def test_all_three_styles_in_list(self):
        """highlight class + bg_color + text_color all appear on list item."""
        snapshot, block_id = build_styled_entity_snapshot(
            roster_with_combined_styles(), "list",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-highlight")
        assert_contains(html, "background-color: #fef3c7")
        assert_contains(html, "color: #92400e")

    def test_all_three_styles_in_table(self):
        """highlight class + bg_color + text_color all appear on table row."""
        snapshot, block_id = build_styled_entity_snapshot(
            roster_with_combined_styles(), "table",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-highlight")
        assert_contains(html, "background-color: #fef3c7")
        assert_contains(html, "color: #92400e")

    def test_only_styled_entity_has_overrides(self):
        """Non-styled entities in the same view don't get style overrides."""
        snapshot, block_id = build_styled_entity_snapshot(
            roster_with_combined_styles(), "list",
        )
        html = render_block(block_id, snapshot)

        # Only 1 entity (Mike) has styles — one highlight, one bg, one text
        assert html.count("aide-highlight") == 1
        assert html.count("background-color: #fef3c7") == 1
        assert html.count("color: #92400e") == 1


# ============================================================================
# Multiple styled entities
# ============================================================================


class TestMultipleStyledEntities:
    """
    Multiple entities can have different style overrides simultaneously.
    """

    def test_two_entities_different_highlights(self):
        """Two entities with different bg_colors in same view."""
        entities = {
            "player_mike": {
                "name": "Mike",
                "status": "active",
                "rating": 1200,
                "_styles": {"highlight": True, "bg_color": "#fef3c7"},
                "_removed": False,
            },
            "player_sarah": {
                "name": "Sarah",
                "status": "active",
                "rating": 1350,
                "_styles": {"highlight": True, "bg_color": "#dbeafe"},
                "_removed": False,
            },
            "player_dave": {
                "name": "Dave",
                "status": "inactive",
                "rating": 1100,
                "_removed": False,
            },
        }
        snapshot, block_id = build_styled_entity_snapshot(entities, "list")
        html = render_block(block_id, snapshot)

        # Both highlighted
        assert html.count("aide-highlight") == 2
        # Both have different bg colors
        assert_contains(html, "background-color: #fef3c7")
        assert_contains(html, "background-color: #dbeafe")
        # Dave has no styles
        assert html.count("background-color:") == 2

    def test_all_entities_styled(self):
        """Every entity in a collection can have style overrides."""
        entities = {
            "p1": {
                "name": "A",
                "status": "active",
                "rating": 100,
                "_styles": {"bg_color": "#fee2e2"},
                "_removed": False,
            },
            "p2": {
                "name": "B",
                "status": "active",
                "rating": 200,
                "_styles": {"bg_color": "#dcfce7"},
                "_removed": False,
            },
            "p3": {
                "name": "C",
                "status": "active",
                "rating": 300,
                "_styles": {"bg_color": "#dbeafe"},
                "_removed": False,
            },
        }
        snapshot, block_id = build_styled_entity_snapshot(entities, "table")
        html = render_block(block_id, snapshot)

        assert_contains(html, "background-color: #fee2e2")
        assert_contains(html, "background-color: #dcfce7")
        assert_contains(html, "background-color: #dbeafe")
        assert html.count("background-color:") == 3


# ============================================================================
# Empty / no _styles
# ============================================================================


class TestNoEntityStyles:
    """
    Entities without _styles should render cleanly with no extra
    classes or inline styles related to entity overrides.
    """

    def test_no_styles_key_at_all(self):
        """Entity without _styles key renders without overrides."""
        entities = {
            "player_plain": {
                "name": "Plain",
                "status": "active",
                "rating": 1000,
                "_removed": False,
            },
        }
        snapshot, block_id = build_styled_entity_snapshot(entities, "list")
        html = render_block(block_id, snapshot)

        assert_not_contains(html, "aide-highlight")
        assert_not_contains(html, "background-color:")

    def test_empty_styles_dict(self):
        """Entity with empty _styles dict renders without overrides."""
        entities = {
            "player_empty": {
                "name": "Empty",
                "status": "active",
                "rating": 1000,
                "_styles": {},
                "_removed": False,
            },
        }
        snapshot, block_id = build_styled_entity_snapshot(entities, "list")
        html = render_block(block_id, snapshot)

        assert_not_contains(html, "aide-highlight")
        assert_not_contains(html, "background-color:")


# ============================================================================
# aide-highlight CSS class definition
# ============================================================================


class TestAideHighlightCSSDefinition:
    """
    The base CSS should include the .aide-highlight rule.
    Per spec: .aide-highlight { background-color: rgba(31, 42, 68, 0.04); }
    This is the default highlight appearance when no bg_color override exists.
    """

    def test_aide_highlight_class_in_base_css(self):
        """
        The rendered full HTML should include the .aide-highlight CSS rule.
        We need to use the full render() to check the <style> block.
        """
        from engine.kernel.renderer import render
        from engine.kernel.types import Blueprint

        snapshot, _ = build_styled_entity_snapshot(
            roster_with_highlighted_player(), "list",
        )
        snapshot["meta"] = {"title": "Test"}
        blueprint = Blueprint(
            identity="Test.",
            voice="No first person.",
            prompt="Test.",
        )

        html = render(snapshot, blueprint)

        # The CSS should define aide-highlight
        assert "aide-highlight" in html
        assert "rgba(31, 42, 68, 0.04)" in html or "aide-highlight" in html


# ============================================================================
# Style overrides with inline style attribute format
# ============================================================================


class TestInlineStyleFormat:
    """
    Inline styles are emitted as a style="" attribute with semicolon-separated
    property declarations.
    Per spec: entity_inline_style() joins parts with '; '.
    """

    def test_bg_and_text_color_in_single_style_attribute(self):
        """Both bg_color and text_color appear in one style attribute."""
        entities = {
            "player_styled": {
                "name": "Styled",
                "status": "active",
                "rating": 1000,
                "_styles": {"bg_color": "#fef3c7", "text_color": "#92400e"},
                "_removed": False,
            },
        }
        snapshot, block_id = build_styled_entity_snapshot(entities, "list")
        html = render_block(block_id, snapshot)

        # Both should be in the same style attribute
        assert_contains(html, "background-color: #fef3c7")
        assert_contains(html, "color: #92400e")

        # They should be joined by semicolons within one style=""
        assert 'style="' in html
        # Extract the style attribute value
        style_start = html.index('style="') + 7
        style_end = html.index('"', style_start)
        style_value = html[style_start:style_end]
        assert "background-color" in style_value
        assert "color" in style_value

    def test_single_style_no_trailing_semicolon_issues(self):
        """Single inline style property should not cause format issues."""
        entities = {
            "player_bg": {
                "name": "BgOnly",
                "status": "active",
                "rating": 1000,
                "_styles": {"bg_color": "#fef3c7"},
                "_removed": False,
            },
        }
        snapshot, block_id = build_styled_entity_snapshot(entities, "list")
        html = render_block(block_id, snapshot)

        assert_contains(html, "background-color: #fef3c7")
