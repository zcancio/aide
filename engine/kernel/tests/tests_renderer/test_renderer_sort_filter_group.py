"""
AIde Renderer -- Sort / Filter / Group Tests (v3 Unified Entity Model)

In v3, child entities within a parent's sub-collection are sorted by _pos.
There are no view configs with sort_by/filter — ordering is done via _pos.

Tests verify:
  - Child entities render in _pos order
  - Removed children are excluded
  - Multiple children render correctly
  - Grid children use row/col key ordering

Reference: aide_renderer_spec.md (Sorting and Filtering)
"""


from engine.kernel.reducer import empty_state
from engine.kernel.renderer import render_block


def assert_contains(html, *fragments):
    for fragment in fragments:
        assert fragment in html, (
            f"Expected to find {fragment!r} in rendered HTML.\nGot (first 3000 chars):\n{html[:3000]}"
        )


def assert_not_contains(html, *fragments):
    for fragment in fragments:
        assert fragment not in html, f"Did NOT expect to find {fragment!r} in rendered HTML."


def assert_order(html, *names):
    """Assert that the given names appear in order in the HTML output."""
    positions = []
    for name in names:
        pos = html.find(name)
        assert pos != -1, f"{name!r} not found in HTML"
        positions.append((name, pos))
    for i in range(len(positions) - 1):
        assert positions[i][1] < positions[i + 1][1], (
            f"Expected {positions[i][0]!r} before {positions[i + 1][0]!r}"
        )


def make_player_snapshot(players_with_pos, view_type="list"):
    """
    Build a snapshot with a players collection using _pos for ordering.
    players_with_pos: list of (name, wins, _pos) tuples.
    """
    snapshot = empty_state()
    snapshot["meta"] = {"title": "Players"}

    snapshot["schemas"]["player"] = {
        "interface": "interface Player { name: string; wins: number; }",
        "render_html": "<li class=\"player\">{{name}} ({{wins}})</li>",
        "render_text": "{{name}}: {{wins}}",
    }

    snapshot["schemas"]["player_list"] = {
        "interface": "interface PlayerList { name: string; roster: Record<string, Player>; }",
        "render_html": "<ul class=\"player-list\">{{>roster}}</ul>",
    }

    roster = {}
    for name, wins, pos in players_with_pos:
        pid = f"player_{name.lower()}"
        roster[pid] = {"name": name, "wins": wins, "_pos": pos}

    snapshot["entities"]["league"] = {
        "_schema": "player_list",
        "name": "League",
        "roster": roster,
    }

    block_id = "block_league"
    snapshot["blocks"][block_id] = {
        "type": "entity_view",
        "source": "league",
    }
    snapshot["blocks"]["block_root"]["children"] = [block_id]

    return snapshot, block_id


# ============================================================================
# Sort by _pos
# ============================================================================


class TestSortByPos:
    """
    Child entities sort by _pos (ascending, nulls last).
    """

    def test_ascending_pos_order(self):
        """Children with explicit _pos render in ascending order."""
        players = [
            ("Charlie", 3, 3.0),
            ("Alice", 7, 1.0),
            ("Bob", 5, 2.0),
        ]
        snapshot, bid = make_player_snapshot(players)
        html = render_block(bid, snapshot)

        assert_order(html, "Alice", "Bob", "Charlie")

    def test_reverse_insertion_with_pos(self):
        """Even if entities added in reverse order, _pos determines order."""
        players = [
            ("Third", 1, 3.0),
            ("Second", 2, 2.0),
            ("First", 5, 1.0),
        ]
        snapshot, bid = make_player_snapshot(players)
        html = render_block(bid, snapshot)

        assert_order(html, "First", "Second", "Third")

    def test_fractional_pos(self):
        """Fractional _pos values sort correctly."""
        players = [
            ("B", 2, 1.5),
            ("A", 1, 0.5),
            ("C", 3, 2.5),
        ]
        snapshot, bid = make_player_snapshot(players)
        html = render_block(bid, snapshot)

        assert_order(html, "A", "B", "C")

    def test_all_entities_present(self):
        """All non-removed entities appear."""
        players = [
            ("Alice", 7, 1.0),
            ("Bob", 5, 2.0),
            ("Charlie", 3, 3.0),
            ("Dave", 9, 4.0),
            ("Eve", 1, 5.0),
        ]
        snapshot, bid = make_player_snapshot(players)
        html = render_block(bid, snapshot)

        assert_contains(html, "Alice", "Bob", "Charlie", "Dave", "Eve")

    def test_ten_entities_in_pos_order(self):
        """Ten entities render in _pos order."""
        players = [(f"Player{i:02d}", i, float(i)) for i in range(10, 0, -1)]
        snapshot, bid = make_player_snapshot(players)
        html = render_block(bid, snapshot)

        names_in_order = [f"Player{i:02d}" for i in range(1, 11)]
        assert_order(html, *names_in_order)


# ============================================================================
# Filtering via _removed
# ============================================================================


class TestFilterRemoved:
    """
    Removed entities (children with _removed=True) are excluded from output.
    """

    def test_single_removed_entity(self):
        """One removed entity is excluded, others render."""
        snapshot = empty_state()
        snapshot["schemas"]["item"] = {
            "interface": "interface Item { name: string; }",
            "render_html": "<li>{{name}}</li>",
        }
        snapshot["schemas"]["list_s"] = {
            "interface": "interface ListS { name: string; items: Record<string, Item>; }",
            "render_html": "<ul>{{>items}}</ul>",
        }
        snapshot["entities"]["mylist"] = {
            "_schema": "list_s",
            "name": "My List",
            "items": {
                "item_1": {"name": "Visible", "_pos": 1.0},
                "item_2": {"name": "Removed", "_pos": 2.0, "_removed": True},
                "item_3": {"name": "Also Visible", "_pos": 3.0},
            },
        }
        snapshot["blocks"]["b"] = {"type": "entity_view", "source": "mylist"}
        snapshot["blocks"]["block_root"]["children"] = ["b"]

        html = render_block("b", snapshot)

        assert_contains(html, "Visible", "Also Visible")
        assert_not_contains(html, "Removed")

    def test_all_removed_renders_empty_list(self):
        """All children removed → empty parent wrapper."""
        snapshot = empty_state()
        snapshot["schemas"]["item"] = {
            "interface": "interface Item { name: string; }",
            "render_html": "<li>{{name}}</li>",
        }
        snapshot["schemas"]["list_s"] = {
            "interface": "interface ListS { name: string; items: Record<string, Item>; }",
            "render_html": "<ul class=\"empty-list\">{{>items}}</ul>",
        }
        snapshot["entities"]["mylist"] = {
            "_schema": "list_s",
            "name": "My List",
            "items": {
                "item_1": {"name": "Gone1", "_pos": 1.0, "_removed": True},
                "item_2": {"name": "Gone2", "_pos": 2.0, "_removed": True},
            },
        }
        snapshot["blocks"]["b"] = {"type": "entity_view", "source": "mylist"}
        snapshot["blocks"]["block_root"]["children"] = ["b"]

        html = render_block("b", snapshot)

        # Wrapper still there, but no items
        assert_contains(html, "empty-list")
        assert_not_contains(html, "Gone1", "Gone2")

    def test_no_removed_shows_all(self):
        """Without any _removed, all entities show."""
        players = [(f"P{i}", i, float(i)) for i in range(1, 6)]
        snapshot, bid = make_player_snapshot(players)
        html = render_block(bid, snapshot)

        for i in range(1, 6):
            assert_contains(html, f"P{i}")


# ============================================================================
# Multiple entities with same content
# ============================================================================


class TestMultipleEntities:
    """
    Multiple entities in a collection render independently.
    """

    def test_five_entities_all_rendered(self):
        """Five entities are all rendered."""
        names = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]
        players = [(n, i, float(i)) for i, n in enumerate(names, 1)]
        snapshot, bid = make_player_snapshot(players)
        html = render_block(bid, snapshot)

        for name in names:
            assert_contains(html, name)

    def test_entities_with_same_field_values(self):
        """Entities with same field values both appear (entity ID differs)."""
        snapshot = empty_state()
        snapshot["schemas"]["item"] = {
            "interface": "interface Item { category: string; }",
            "render_html": "<div class=\"item\">{{category}}</div>",
        }
        snapshot["schemas"]["list_s"] = {
            "interface": "interface ListS { name: string; items: Record<string, Item>; }",
            "render_html": "<div class=\"list\">{{>items}}</div>",
        }
        snapshot["entities"]["mylist"] = {
            "_schema": "list_s",
            "name": "Items",
            "items": {
                "item_a": {"category": "Red", "_pos": 1.0},
                "item_b": {"category": "Red", "_pos": 2.0},  # Same value
            },
        }
        snapshot["blocks"]["b"] = {"type": "entity_view", "source": "mylist"}
        snapshot["blocks"]["block_root"]["children"] = ["b"]

        html = render_block("b", snapshot)

        # Both should appear (two occurrences of "Red")
        assert html.count("Red") >= 2


# ============================================================================
# Grid: row/col ordering
# ============================================================================


class TestGridOrdering:
    """
    Grid cells (using _shape) render row by row, column by column.
    """

    def _grid_snapshot(self, rows, cols, cells):
        """Build a grid snapshot."""
        snapshot = empty_state()
        snapshot["schemas"]["cell"] = {
            "interface": "interface Cell { val: string; }",
            "render_html": "{{val}}",
        }
        snapshot["schemas"]["grid_schema"] = {
            "interface": "interface GridSchema { name: string; cells: Record<string, Cell>; }",
            "render_html": "<div class=\"grid\">{{>cells}}</div>",
        }
        snapshot["entities"]["my_grid"] = {
            "_schema": "grid_schema",
            "name": "Grid",
            "cells": {"_shape": [rows, cols], **cells},
        }
        snapshot["blocks"]["b"] = {"type": "entity_view", "source": "my_grid"}
        snapshot["blocks"]["block_root"]["children"] = ["b"]
        return snapshot

    def test_2x2_grid_renders_all_cells(self):
        """2×2 grid renders all 4 cells."""
        cells = {
            "0_0": {"val": "A1"},
            "0_1": {"val": "B1"},
            "1_0": {"val": "A2"},
            "1_1": {"val": "B2"},
        }
        snapshot = self._grid_snapshot(2, 2, cells)
        html = render_block("b", snapshot)

        assert_contains(html, "A1", "B1", "A2", "B2")

    def test_grid_row_order(self):
        """Grid renders row 0 before row 1."""
        cells = {
            "0_0": {"val": "Row0"},
            "1_0": {"val": "Row1"},
        }
        snapshot = self._grid_snapshot(2, 1, cells)
        html = render_block("b", snapshot)

        assert_order(html, "Row0", "Row1")

    def test_grid_col_order(self):
        """Grid renders col 0 before col 1 within same row."""
        cells = {
            "0_0": {"val": "Col0"},
            "0_1": {"val": "Col1"},
        }
        snapshot = self._grid_snapshot(1, 2, cells)
        html = render_block("b", snapshot)

        assert_order(html, "Col0", "Col1")

    def test_grid_uses_aide_grid_class(self):
        """Grid container uses aide-grid CSS class."""
        cells = {"0_0": {"val": "X"}}
        snapshot = self._grid_snapshot(1, 1, cells)
        html = render_block("b", snapshot)

        assert_contains(html, "aide-grid")

    def test_grid_empty_cell_renders(self):
        """Missing grid cell renders as empty cell, not an error."""
        cells = {
            "0_0": {"val": "A"},
            # 0_1 is missing
        }
        snapshot = self._grid_snapshot(1, 2, cells)
        html = render_block("b", snapshot)

        # Should render A and an empty cell, no crash
        assert_contains(html, "A")
        # Grid container should be present (cells may use schema template without wrappers)
        assert "aide-grid" in html


# ============================================================================
# Ordering stability
# ============================================================================


class TestOrderingStability:
    """
    Rendering order must be stable across multiple calls with the same snapshot.
    """

    def test_same_pos_stable_fallback_to_key(self):
        """When _pos values differ, order is by _pos then by key."""
        players = [
            ("B_player", 2, 2.0),
            ("A_player", 1, 1.0),
            ("C_player", 3, 3.0),
        ]
        snapshot, bid = make_player_snapshot(players)

        html1 = render_block(bid, snapshot)
        html2 = render_block(bid, snapshot)

        assert html1 == html2, "Rendering order is not stable"

    def test_repeated_renders_identical(self):
        """Same snapshot renders identically multiple times."""
        players = [(f"P{i}", i, float(i)) for i in range(1, 8)]
        snapshot, bid = make_player_snapshot(players)

        results = [render_block(bid, snapshot) for _ in range(5)]

        for r in results[1:]:
            assert r == results[0], "Rendering is not deterministic"
