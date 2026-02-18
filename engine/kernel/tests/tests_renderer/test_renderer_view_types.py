"""
AIde Renderer -- View Type Rendering Tests (v3 Unified Entity Model)

In v3, entities are rendered via Mustache templates in schemas.
Child collections are rendered via {{>field_name}} partials.
Grid layout uses _shape on a child collection dict.

v3 replaces the v2 collection_view/list/table/grid with:
  - entity_view block pointing to an entity
  - Schema render_html template defines the output format
  - {{>field}} partials render child sub-collections
  - _shape: [rows, cols] triggers CSS grid layout

Reference: aide_renderer_spec.md, docs/eng_design/unified_entity_model.md
"""

from engine.kernel.reducer import empty_state
from engine.kernel.renderer import render, render_block, render_entity


def assert_contains(html, *fragments):
    for fragment in fragments:
        assert fragment in html, (
            f"Expected to find {fragment!r} in rendered HTML.\nGot (first 2000 chars):\n{html[:2000]}"
        )


def assert_not_contains(html, *fragments):
    for fragment in fragments:
        assert fragment not in html, f"Did NOT expect to find {fragment!r} in rendered HTML."


def make_blueprint():
    from engine.kernel.types import Blueprint
    return Blueprint(identity="Test.", voice="No first person.", prompt="Test.")


# ============================================================================
# Grocery list: list-style rendering
# ============================================================================


class TestListStyleRendering:
    """
    Entities with a list-style template render as list items.
    The schema render_html defines the output for each child.
    """

    def _grocery_snapshot(self):
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Grocery List"}

        snapshot["schemas"]["grocery_item"] = {
            "interface": "interface GroceryItem { name: string; checked: boolean; }",
            "render_html": "<li class=\"grocery-item\">{{name}}</li>",
            "render_text": "- {{name}}",
        }

        snapshot["schemas"]["grocery_list"] = {
            "interface": "interface GroceryList { name: string; items: Record<string, GroceryItem>; }",
            "render_html": "<ul class=\"grocery-list\">{{>items}}</ul>",
        }

        snapshot["entities"]["groceries"] = {
            "_schema": "grocery_list",
            "name": "Groceries",
            "items": {
                "item_milk": {"name": "Milk", "checked": False, "_pos": 1.0},
                "item_eggs": {"name": "Eggs", "checked": True, "_pos": 2.0},
                "item_bread": {"name": "Bread", "checked": False, "_pos": 3.0},
            },
        }

        snapshot["blocks"]["block_grocery"] = {
            "type": "entity_view",
            "source": "groceries",
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_grocery"]

        return snapshot

    def test_list_renders_entity_names(self):
        """List view renders all entity names."""
        snapshot = self._grocery_snapshot()
        html = render_block("block_grocery", snapshot)
        assert_contains(html, "Milk", "Eggs", "Bread")

    def test_list_uses_ul_element(self):
        """List-style schema renders ul element."""
        snapshot = self._grocery_snapshot()
        html = render_block("block_grocery", snapshot)
        assert_contains(html, "<ul", "grocery-list")

    def test_list_items_use_li_element(self):
        """Each item renders as li."""
        snapshot = self._grocery_snapshot()
        html = render_block("block_grocery", snapshot)
        assert_contains(html, "<li", "grocery-item")

    def test_list_skips_removed_entities(self):
        """Removed child entities are not rendered."""
        snapshot = self._grocery_snapshot()
        snapshot["entities"]["groceries"]["items"]["item_bread"]["_removed"] = True
        html = render_block("block_grocery", snapshot)
        assert_contains(html, "Milk", "Eggs")
        assert_not_contains(html, "Bread")


# ============================================================================
# Schedule: table-style rendering
# ============================================================================


class TestTableStyleRendering:
    """
    Entities with a table-style template render rows.
    """

    def _schedule_snapshot(self):
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Schedule"}

        snapshot["schemas"]["game"] = {
            "interface": "interface Game { date: string; opponent: string; location: string; }",
            "render_html": "<tr><td>{{date}}</td><td>{{opponent}}</td><td>{{location}}</td></tr>",
        }

        snapshot["schemas"]["schedule"] = {
            "interface": "interface Schedule { name: string; games: Record<string, Game>; }",
            "render_html": "<table class=\"schedule-table\"><thead><tr><th>Date</th><th>Opponent</th><th>Location</th></tr></thead><tbody>{{>games}}</tbody></table>",
        }

        snapshot["entities"]["schedule"] = {
            "_schema": "schedule",
            "name": "2026 Schedule",
            "games": {
                "game_1": {"date": "Feb 27", "opponent": "Team A", "location": "Home", "_pos": 1.0},
                "game_2": {"date": "Mar 6", "opponent": "Team B", "location": "Away", "_pos": 2.0},
            },
        }

        snapshot["blocks"]["block_schedule"] = {
            "type": "entity_view",
            "source": "schedule",
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_schedule"]

        return snapshot

    def test_table_renders_entity_data(self):
        """Table-style view renders game data."""
        snapshot = self._schedule_snapshot()
        html = render_block("block_schedule", snapshot)
        assert_contains(html, "Team A", "Team B", "Feb 27", "Mar 6")

    def test_table_uses_table_element(self):
        """Table-style schema renders <table>."""
        snapshot = self._schedule_snapshot()
        html = render_block("block_schedule", snapshot)
        assert_contains(html, "<table", "schedule-table")

    def test_table_has_headers_and_rows(self):
        """Table has thead and tbody."""
        snapshot = self._schedule_snapshot()
        html = render_block("block_schedule", snapshot)
        assert_contains(html, "<thead", "<tbody", "<th>", "<tr>", "<td>")


# ============================================================================
# Grid layout: _shape-based rendering
# ============================================================================


class TestGridRendering:
    """
    Grid layout is triggered by _shape: [rows, cols] on a child collection.
    Renders as CSS grid with .aide-grid and .aide-grid-cell.
    """

    def _grid_snapshot(self):
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Grid"}

        snapshot["schemas"]["cell"] = {
            "interface": "interface Cell { value: string; }",
            "render_html": "{{value}}",
        }

        snapshot["schemas"]["grid_entity"] = {
            "interface": "interface GridEntity { name: string; cells: Record<string, Cell>; }",
            "render_html": "<div class=\"grid-wrapper\">{{>cells}}</div>",
        }

        snapshot["entities"]["my_grid"] = {
            "_schema": "grid_entity",
            "name": "My Grid",
            "cells": {
                "_shape": [2, 3],
                "0_0": {"value": "A1", "_pos": 0.0},
                "0_1": {"value": "B1", "_pos": 1.0},
                "0_2": {"value": "C1", "_pos": 2.0},
                "1_0": {"value": "A2", "_pos": 3.0},
                "1_1": {"value": "B2", "_pos": 4.0},
                "1_2": {"value": "C2", "_pos": 5.0},
            },
        }

        snapshot["blocks"]["block_grid"] = {
            "type": "entity_view",
            "source": "my_grid",
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_grid"]

        return snapshot

    def test_grid_renders_css_grid(self):
        """Grid with _shape renders using CSS grid."""
        snapshot = self._grid_snapshot()
        html = render_block("block_grid", snapshot)
        assert_contains(html, "aide-grid")

    def test_grid_cells_rendered(self):
        """Grid cells are rendered with their values."""
        snapshot = self._grid_snapshot()
        html = render_block("block_grid", snapshot)
        assert_contains(html, "A1", "B1", "C1", "A2", "B2", "C2")

    def test_grid_has_correct_column_count(self):
        """Grid template has correct number of columns."""
        snapshot = self._grid_snapshot()
        html = render_block("block_grid", snapshot)
        # 3 columns → when child schema has template, uses "repeat(3, 1fr)"
        # otherwise uses "auto auto auto"
        assert "repeat(3, 1fr)" in html or "auto auto auto" in html


# ============================================================================
# entity_view in full render
# ============================================================================


class TestEntityViewInFullRender:
    """entity_view blocks render correctly in the full HTML document."""

    def test_entity_view_in_full_html(self):
        """Entity content appears in the full render output."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Test"}
        snapshot["schemas"]["player"] = {
            "interface": "interface Player { name: string; score: number; }",
            "render_html": "<div class=\"player\"><b>{{name}}</b>: {{score}}</div>",
        }
        snapshot["entities"]["player_1"] = {
            "_schema": "player",
            "name": "Alice",
            "score": 1500,
        }
        snapshot["blocks"]["block_player"] = {
            "type": "entity_view",
            "source": "player_1",
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_player"]

        html = render(snapshot, make_blueprint())

        assert_contains(html, "Alice", "1500", "class=\"player\"")
        assert_contains(html, "<!DOCTYPE html>", "<main class=\"aide-page\"")


# ============================================================================
# Auto-render (no explicit blocks)
# ============================================================================


class TestAutoRenderEntities:
    """When no blocks are set, entities are auto-rendered."""

    def test_entities_auto_render(self):
        """Entities auto-render using their schema templates."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Auto"}
        snapshot["schemas"]["item"] = {
            "interface": "interface Item { name: string; }",
            "render_html": "<p class=\"item\">{{name}}</p>",
        }
        snapshot["entities"]["item_a"] = {"_schema": "item", "name": "Alpha"}
        snapshot["entities"]["item_b"] = {"_schema": "item", "name": "Beta"}
        # No blocks added to block_root

        html = render(snapshot, make_blueprint())

        assert_contains(html, "Alpha", "Beta")

    def test_only_non_removed_entities_auto_render(self):
        """Removed entities are excluded from auto-render."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Auto"}
        snapshot["schemas"]["item"] = {
            "interface": "interface Item { name: string; }",
            "render_html": "<p class=\"item\">{{name}}</p>",
        }
        snapshot["entities"]["item_a"] = {"_schema": "item", "name": "Visible"}
        snapshot["entities"]["item_b"] = {"_schema": "item", "name": "Hidden", "_removed": True}

        import re
        html = render(snapshot, make_blueprint())
        m = re.search(r"<main[^>]*>(.*?)</main>", html, re.DOTALL)
        main = m.group(1) if m else ""

        assert "Visible" in main
        assert "Hidden" not in main


# ============================================================================
# Empty entity collection views
# ============================================================================


class TestEmptyCollectionViews:
    """
    In v3, empty child collections produce no child output.
    Missing or removed entities produce empty string.
    """

    def test_empty_child_collection_renders_nothing_in_partial(self):
        """Empty child collection renders parent template without child items."""
        snapshot = empty_state()
        snapshot["schemas"]["list_schema"] = {
            "interface": "interface ListSchema { name: string; }",
            "render_html": "<ul class=\"my-list\">{{>items}}</ul>",
        }
        snapshot["entities"]["empty_list"] = {
            "_schema": "list_schema",
            "name": "Empty List",
            "items": {},
        }
        html = render_entity("empty_list", snapshot, channel="html")

        assert_contains(html, "class=\"my-list\"")
        assert_not_contains(html, "<li")

    def test_removed_entity_view_renders_empty(self):
        """entity_view pointing to removed entity renders empty string."""
        snapshot = empty_state()
        snapshot["entities"]["removed"] = {"name": "Gone", "_removed": True}
        snapshot["blocks"]["block_v"] = {
            "type": "entity_view",
            "source": "removed",
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_v"]

        html = render_block("block_v", snapshot)
        assert html == ""

    def test_missing_entity_view_renders_empty(self):
        """entity_view pointing to nonexistent entity renders empty string."""
        snapshot = empty_state()
        snapshot["blocks"]["block_v"] = {
            "type": "entity_view",
            "source": "nonexistent",
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_v"]

        html = render_block("block_v", snapshot)
        assert html == ""


# ============================================================================
# Text channel
# ============================================================================


class TestTextChannelRendering:
    """render with channel='text' uses render_text templates."""

    def test_text_channel_uses_render_text(self):
        """Text channel uses schema render_text template."""
        from engine.kernel.types import RenderOptions

        snapshot = empty_state()
        snapshot["meta"] = {"title": "Text Test"}
        snapshot["schemas"]["item"] = {
            "interface": "interface Item { name: string; }",
            "render_html": "<li>{{name}}</li>",
            "render_text": "- {{name}}",
        }
        snapshot["entities"]["item_1"] = {"_schema": "item", "name": "Alpha"}

        opts = RenderOptions(channel="text")
        text = render(snapshot, make_blueprint(), options=opts)

        assert "Text Test" in text
        assert "Alpha" in text

    def test_render_entity_text_channel(self):
        """render_entity with text channel uses render_text."""
        snapshot = empty_state()
        snapshot["schemas"]["player"] = {
            "interface": "interface Player { name: string; score: number; }",
            "render_html": "<div>{{name}}: {{score}}</div>",
            "render_text": "{{name}} scored {{score}}",
        }
        snapshot["entities"]["p1"] = {
            "_schema": "player",
            "name": "Mike",
            "score": 1200,
        }

        text = render_entity("p1", snapshot, channel="text")

        assert "Mike" in text
        assert "1200" in text
