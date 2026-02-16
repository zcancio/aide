"""
AIde Renderer -- Determinism Tests (Category 10)

Render the same snapshot 100 times, verify identical output every time.

From the spec (aide_renderer_spec.md, "Testing Strategy"):
  "10. Determinism. Render the same snapshot 100 times, verify identical
   output every time."

From the renderer contract:
  "Deterministic: same input → same output, always."

From the reducer spec (determinism guarantee):
  "No randomness, no timestamps, no external state."

This verifies:
  - String output is byte-identical across repeated renders
  - JSON embedding uses sorted keys for determinism
  - CSS generation is stable
  - Block tree walk order is stable
  - Entity iteration order is stable
  - Sort/filter/group produce stable ordering
  - Style token mapping is stable
  - Value formatting produces identical strings

Reference: aide_renderer_spec.md (Contract, CSS Generation, Testing Strategy)
           aide_architecture.md (Renderer description)
"""


from engine.kernel.reducer import empty_state
from engine.kernel.renderer import render
from engine.kernel.types import Blueprint, Event

# ============================================================================
# Snapshot fixtures (realistic, exercising many renderer paths)
# ============================================================================


def make_blueprint():
    return Blueprint(
        identity="Test aide for determinism checks.",
        voice="No first person. State reflections only.",
        prompt="You are maintaining a test page.",
    )


def make_events():
    return [
        Event(
            id="evt_20260215_001",
            sequence=1,
            timestamp="2026-02-15T09:00:00Z",
            actor="user_test",
            source="web",
            type="collection.create",
            payload={"id": "items", "schema": {"name": "string"}},
        ),
    ]


def grocery_list_snapshot():
    """
    Grocery list with heading, text (inline bold), metric, list view,
    multiple entities with mixed types, highlights, null values,
    sort config, style tokens, and annotations.
    """
    snapshot = empty_state()

    snapshot["meta"] = {
        "title": "Weekly Groceries",
        "identity": "Family grocery list.",
    }

    snapshot["styles"] = {
        "primary_color": "#2d3748",
        "bg_color": "#fafaf9",
        "density": "comfortable",
    }

    snapshot["collections"] = {
        "grocery_list": {
            "id": "grocery_list",
            "name": "Grocery List",
            "schema": {
                "name": "string",
                "category": "enum",
                "quantity": "int",
                "checked": "bool",
                "store": "string?",
            },
            "entities": {
                "item_milk": {
                    "name": "Whole Milk",
                    "category": "dairy",
                    "quantity": 2,
                    "checked": True,
                    "store": "Trader Joe's",
                    "_removed": False,
                    "_styles": {"highlight": True},
                },
                "item_eggs": {
                    "name": "Eggs (dozen)",
                    "category": "dairy",
                    "quantity": 1,
                    "checked": False,
                    "store": "Trader Joe's",
                    "_removed": False,
                },
                "item_bread": {
                    "name": "Sourdough Bread",
                    "category": "bakery",
                    "quantity": 1,
                    "checked": False,
                    "store": None,
                    "_removed": False,
                },
                "item_chicken": {
                    "name": "Chicken Thighs",
                    "category": "meat",
                    "quantity": 2,
                    "checked": False,
                    "store": "Whole Foods",
                    "_removed": False,
                },
                "item_spinach": {
                    "name": "Baby Spinach",
                    "category": "produce",
                    "quantity": 1,
                    "checked": True,
                    "store": None,
                    "_removed": False,
                    "_styles": {"highlight": True},
                },
            },
        },
    }

    snapshot["views"] = {
        "grocery_view": {
            "id": "grocery_view",
            "type": "list",
            "source": "grocery_list",
            "config": {
                "show_fields": ["name", "category", "quantity", "checked"],
                "sort_by": "category",
                "sort_order": "asc",
            },
        },
    }

    snapshot["blocks"] = {
        "block_root": {"type": "root", "children": [
            "block_title", "block_intro", "block_budget", "block_groceries",
        ]},
        "block_title": {
            "type": "heading",
            "parent": "block_root",
            "props": {"level": 1, "content": "Weekly Groceries"},
        },
        "block_intro": {
            "type": "text",
            "parent": "block_root",
            "props": {"content": "Updated every **Sunday** morning."},
        },
        "block_budget": {
            "type": "metric",
            "parent": "block_root",
            "props": {"label": "Estimated total", "value": "$47.50"},
        },
        "block_groceries": {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "grocery_list", "view": "grocery_view"},
        },
    }

    snapshot["annotations"] = [
        {
            "note": "Budget limit: $60/week.",
            "pinned": True,
            "seq": 1,
            "timestamp": "2026-02-10T09:00:00Z",
        },
    ]

    return snapshot


def poker_league_snapshot():
    """
    Poker league with two collections (roster table, schedule table),
    entity style overrides, multiple headings, metrics, divider,
    text with link, and different style tokens.
    """
    snapshot = empty_state()

    snapshot["meta"] = {
        "title": "Poker League — Spring 2026",
    }

    snapshot["styles"] = {
        "primary_color": "#1a365d",
        "bg_color": "#fffff0",
        "font_family": "Inter",
        "heading_font": "Georgia",
        "density": "compact",
    }

    snapshot["collections"] = {
        "roster": {
            "id": "roster",
            "name": "Roster",
            "schema": {
                "name": "string",
                "buy_ins": "int",
                "winnings": "float",
                "active": "bool",
            },
            "entities": {
                "player_mike": {
                    "name": "Mike",
                    "buy_ins": 8,
                    "winnings": 340.0,
                    "active": True,
                    "_removed": False,
                },
                "player_sarah": {
                    "name": "Sarah",
                    "buy_ins": 7,
                    "winnings": 520.5,
                    "active": True,
                    "_removed": False,
                    "_styles": {"highlight": True, "bg_color": "#fef3c7"},
                },
                "player_dave": {
                    "name": "Dave",
                    "buy_ins": 8,
                    "winnings": 180.0,
                    "active": True,
                    "_removed": False,
                },
            },
        },
        "schedule": {
            "id": "schedule",
            "name": "Schedule",
            "schema": {
                "date": "date",
                "host": "string",
                "status": "enum",
            },
            "entities": {
                "game_1": {
                    "date": "2026-02-13",
                    "host": "Mike",
                    "status": "completed",
                    "_removed": False,
                },
                "game_2": {
                    "date": "2026-02-27",
                    "host": "Dave",
                    "status": "upcoming",
                    "_removed": False,
                },
            },
        },
    }

    snapshot["views"] = {
        "roster_view": {
            "id": "roster_view",
            "type": "table",
            "source": "roster",
            "config": {
                "show_fields": ["name", "buy_ins", "winnings", "active"],
                "sort_by": "winnings",
                "sort_order": "desc",
            },
        },
        "schedule_view": {
            "id": "schedule_view",
            "type": "table",
            "source": "schedule",
            "config": {
                "show_fields": ["date", "host", "status"],
                "sort_by": "date",
                "sort_order": "asc",
            },
        },
    }

    snapshot["blocks"] = {
        "block_root": {"type": "root", "children": [
            "block_title", "block_intro", "block_metric",
            "block_divider", "block_roster_h", "block_roster",
            "block_schedule_h", "block_schedule",
        ]},
        "block_title": {
            "type": "heading",
            "parent": "block_root",
            "props": {"level": 1, "content": "Poker League — Spring 2026"},
        },
        "block_intro": {
            "type": "text",
            "parent": "block_root",
            "props": {"content": "Biweekly Thursday. See [rules](https://example.com/rules)."},
        },
        "block_metric": {
            "type": "metric",
            "parent": "block_root",
            "props": {"label": "Next game", "value": "Feb 27 at Dave's"},
        },
        "block_divider": {
            "type": "divider",
            "parent": "block_root",
            "props": {},
        },
        "block_roster_h": {
            "type": "heading",
            "parent": "block_root",
            "props": {"level": 2, "content": "Roster"},
        },
        "block_roster": {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "roster", "view": "roster_view"},
        },
        "block_schedule_h": {
            "type": "heading",
            "parent": "block_root",
            "props": {"level": 2, "content": "Schedule"},
        },
        "block_schedule": {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "schedule", "view": "schedule_view"},
        },
    }

    snapshot["annotations"] = []

    return snapshot


def minimal_snapshot():
    """Minimal: just a heading."""
    snapshot = empty_state()
    snapshot["meta"] = {"title": "Minimal"}
    snapshot["blocks"]["block_h"] = {
        "type": "heading",
        "parent": "block_root",
        "props": {"level": 1, "content": "Hello"},
    }
    snapshot["blocks"]["block_root"]["children"] = ["block_h"]
    return snapshot


def empty_page_snapshot():
    """Truly empty page — no blocks at all."""
    snapshot = empty_state()
    snapshot["meta"] = {"title": "Empty"}
    return snapshot


# ============================================================================
# Core determinism: 100 renders must be identical
# ============================================================================


class TestDeterminism100Renders:
    """
    Render the same snapshot 100 times, verify identical output every time.
    This is the primary spec requirement for Category 10.
    """

    def test_grocery_list_100_renders(self):
        """Grocery list: 100 renders produce identical output."""
        snapshot = grocery_list_snapshot()
        bp = make_blueprint()
        events = make_events()

        first = render(snapshot, bp, events=events)
        for i in range(99):
            result = render(snapshot, bp, events=events)
            assert result == first, (
                f"Render #{i + 2} differs from first render.\n"
                f"First 200 chars of diff region: {_find_diff(first, result)}"
            )

    def test_poker_league_100_renders(self):
        """Poker league: 100 renders produce identical output."""
        snapshot = poker_league_snapshot()
        bp = make_blueprint()

        first = render(snapshot, bp)
        for i in range(99):
            result = render(snapshot, bp)
            assert result == first, f"Render #{i + 2} differs from first render."

    def test_minimal_page_100_renders(self):
        """Minimal page: 100 renders produce identical output."""
        snapshot = minimal_snapshot()
        bp = make_blueprint()

        first = render(snapshot, bp)
        for i in range(99):
            assert render(snapshot, bp) == first

    def test_empty_page_100_renders(self):
        """Empty page: 100 renders produce identical output."""
        snapshot = empty_page_snapshot()
        bp = make_blueprint()

        first = render(snapshot, bp)
        for i in range(99):
            assert render(snapshot, bp) == first


# ============================================================================
# Determinism of specific sub-systems
# ============================================================================


class TestCSSGenerationDeterminism:
    """CSS generation is stable across renders."""

    def test_css_identical_across_renders(self):
        """The <style> block is byte-identical across 50 renders."""
        import re

        snapshot = grocery_list_snapshot()
        bp = make_blueprint()

        first_html = render(snapshot, bp)
        first_css = re.search(r'<style>(.*?)</style>', first_html, re.DOTALL).group(1)

        for _ in range(49):
            html = render(snapshot, bp)
            css = re.search(r'<style>(.*?)</style>', html, re.DOTALL).group(1)
            assert css == first_css


class TestJSONEmbeddingDeterminism:
    """Embedded JSON is stable (sorted keys, consistent serialization)."""

    def test_snapshot_json_identical_across_renders(self):
        """The aide-state JSON block is identical across 50 renders."""
        import re

        snapshot = grocery_list_snapshot()
        bp = make_blueprint()

        first_html = render(snapshot, bp)
        pattern = r'<script[^>]*id="aide-state"[^>]*>(.*?)</script>'
        first_json = re.search(pattern, first_html, re.DOTALL).group(1).strip()

        for _ in range(49):
            html = render(snapshot, bp)
            json_block = re.search(pattern, html, re.DOTALL).group(1).strip()
            assert json_block == first_json

    def test_blueprint_json_identical_across_renders(self):
        """The aide-blueprint JSON block is identical across 50 renders."""
        import re

        snapshot = grocery_list_snapshot()
        bp = make_blueprint()

        first_html = render(snapshot, bp)
        pattern = r'<script[^>]*id="aide-blueprint"[^>]*>(.*?)</script>'
        first_json = re.search(pattern, first_html, re.DOTALL).group(1).strip()

        for _ in range(49):
            html = render(snapshot, bp)
            json_block = re.search(pattern, html, re.DOTALL).group(1).strip()
            assert json_block == first_json

    def test_events_json_identical_across_renders(self):
        """The aide-events JSON block is identical across 50 renders."""
        import re

        snapshot = grocery_list_snapshot()
        bp = make_blueprint()
        events = make_events()

        first_html = render(snapshot, bp, events=events)
        pattern = r'<script[^>]*id="aide-events"[^>]*>(.*?)</script>'
        first_json = re.search(pattern, first_html, re.DOTALL).group(1).strip()

        for _ in range(49):
            html = render(snapshot, bp, events=events)
            json_block = re.search(pattern, html, re.DOTALL).group(1).strip()
            assert json_block == first_json


class TestEntityOrderDeterminism:
    """Entity ordering is stable when sort config is present."""

    def test_sorted_entity_order_stable(self):
        """Sorted entities appear in the same order every render."""
        snapshot = grocery_list_snapshot()
        bp = make_blueprint()

        first_html = render(snapshot, bp)
        # Extract the order of entity names in the output
        first_order = _extract_entity_order(first_html, [
            "Whole Milk", "Eggs (dozen)", "Sourdough Bread",
            "Chicken Thighs", "Baby Spinach",
        ])

        for _ in range(49):
            html = render(snapshot, bp)
            order = _extract_entity_order(html, [
                "Whole Milk", "Eggs (dozen)", "Sourdough Bread",
                "Chicken Thighs", "Baby Spinach",
            ])
            assert order == first_order, (
                f"Entity order changed. First: {first_order}, Now: {order}"
            )


class TestBlockOrderDeterminism:
    """Block tree walk order is stable."""

    def test_block_order_stable(self):
        """Blocks appear in the same document order every render."""
        snapshot = poker_league_snapshot()
        bp = make_blueprint()

        markers = [
            "Poker League", "Biweekly Thursday", "Next game",
            "aide-divider", "Roster", "Schedule",
        ]

        first_html = render(snapshot, bp)
        first_positions = [first_html.find(m) for m in markers]

        for _ in range(49):
            html = render(snapshot, bp)
            positions = [html.find(m) for m in markers]
            assert positions == first_positions


class TestStyleTokenDeterminism:
    """Style token CSS overrides are stable."""

    def test_style_overrides_stable(self):
        """CSS variable overrides appear identically each render."""
        snapshot = poker_league_snapshot()
        bp = make_blueprint()

        overrides = ["--text-primary: #1a365d", "--bg-primary: #fffff0"]

        first_html = render(snapshot, bp)
        for override in overrides:
            assert override in first_html

        for _ in range(49):
            html = render(snapshot, bp)
            for override in overrides:
                pos_first = first_html.find(override)
                pos_now = html.find(override)
                assert pos_first == pos_now, (
                    f"Override {override!r} moved from position {pos_first} to {pos_now}"
                )


# ============================================================================
# Determinism with different RenderOptions
# ============================================================================


class TestDeterminismWithOptions:
    """Determinism holds regardless of RenderOptions."""

    def test_determinism_without_events(self):
        """Stable when events excluded."""
        from engine.kernel.renderer import RenderOptions

        snapshot = grocery_list_snapshot()
        bp = make_blueprint()
        opts = RenderOptions(include_events=False)

        first = render(snapshot, bp, options=opts)
        for _ in range(49):
            assert render(snapshot, bp, options=opts) == first

    def test_determinism_without_blueprint(self):
        """Stable when blueprint excluded."""
        from engine.kernel.renderer import RenderOptions

        snapshot = grocery_list_snapshot()
        bp = make_blueprint()
        opts = RenderOptions(include_blueprint=False)

        first = render(snapshot, bp, options=opts)
        for _ in range(49):
            assert render(snapshot, bp, options=opts) == first

    def test_determinism_with_footer(self):
        """Stable when footer included."""
        from engine.kernel.renderer import RenderOptions

        snapshot = grocery_list_snapshot()
        bp = make_blueprint()
        opts = RenderOptions(footer="Made with AIde")

        first = render(snapshot, bp, options=opts)
        for _ in range(49):
            assert render(snapshot, bp, options=opts) == first


# ============================================================================
# Helpers
# ============================================================================


def _find_diff(a, b, context=200):
    """Find the first point where two strings differ and return context."""
    for i, (ca, cb) in enumerate(zip(a, b, strict=False)):
        if ca != cb:
            start = max(0, i - 50)
            return (
                f"Position {i}: ...{a[start:i+context]!r}... vs "
                f"...{b[start:i+context]!r}..."
            )
    if len(a) != len(b):
        return f"Lengths differ: {len(a)} vs {len(b)}"
    return "Strings are identical"


def _extract_entity_order(html, names):
    """Return the names in the order they appear in the HTML."""
    positions = [(name, html.find(name)) for name in names]
    positions = [(name, pos) for name, pos in positions if pos != -1]
    positions.sort(key=lambda x: x[1])
    return [name for name, _ in positions]
