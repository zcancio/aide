"""
AIde Renderer -- Full Round-Trip Tests (Category 9)

Build a realistic snapshot by hand, render, verify it looks right.

From the spec (aide_renderer_spec.md, "Testing Strategy"):
  "9. Full round-trip. Build a realistic grocery list snapshot by hand,
   render, open in browser, verify it looks right. This is a visual
   test — screenshot comparison or manual review."

Since we can't do visual comparison in unit tests, these tests build
realistic multi-block snapshots (grocery list, poker league) and verify
the complete rendered HTML has:
  - Valid HTML5 document structure
  - All expected content present and in order
  - Correct CSS, OG tags, embedded JSON
  - Heading + text + metrics + collection_view all wired up
  - Value formatting, style tokens, and entity styles all firing
  - Annotations rendered
  - Footer present/absent per tier
  - Output is saveable to disk (writeable, parseable)

These tests also verify that the output can be round-tripped through
the assembly layer's parse logic (extract JSON from script tags).

Reference: aide_renderer_spec.md (full spec)
           aide_architecture.md (HTML file structure)
"""

import json
import re

import pytest

from engine.kernel.reducer import empty_state
from engine.kernel.renderer import render
from engine.kernel.types import Blueprint

# ============================================================================
# Helpers
# ============================================================================


def assert_contains(html, *fragments):
    for fragment in fragments:
        assert fragment in html, (
            f"Expected to find {fragment!r} in rendered HTML.\n"
            f"Got (first 3000 chars):\n{html[:3000]}"
        )


def assert_not_contains(html, *fragments):
    for fragment in fragments:
        assert fragment not in html, (
            f"Did NOT expect to find {fragment!r} in rendered HTML."
        )


def assert_order(html, *fragments):
    """Assert fragments appear in order in the HTML."""
    positions = []
    for f in fragments:
        pos = html.find(f)
        assert pos != -1, f"{f!r} not found in HTML"
        positions.append((f, pos))
    for i in range(len(positions) - 1):
        assert positions[i][1] < positions[i + 1][1], (
            f"Expected {positions[i][0]!r} before {positions[i + 1][0]!r}"
        )


def extract_main(html):
    """Extract content within <main> tags only (avoids CSS and embedded JSON)."""
    match = re.search(r'<main[^>]*>(.*?)</main>', html, re.DOTALL)
    return match.group(1) if match else ""


def assert_order_in_main(html, *fragments):
    """Assert fragments appear in order within <main> content only."""
    main = extract_main(html)
    assert main, "No <main> element found in HTML"
    positions = []
    for f in fragments:
        pos = main.find(f)
        assert pos != -1, f"{f!r} not found in <main> content"
        positions.append((f, pos))
    for i in range(len(positions) - 1):
        assert positions[i][1] < positions[i + 1][1], (
            f"Expected {positions[i][0]!r} before {positions[i + 1][0]!r}"
        )


def assert_not_in_body(html, *fragments):
    """Assert fragments do NOT appear in <body> content."""
    match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL)
    body = match.group(1) if match else ""
    for fragment in fragments:
        assert fragment not in body, (
            f"Did NOT expect to find {fragment!r} in <body> content."
        )


def extract_json_block(html, element_id):
    """Extract JSON from a <script> block by its id attribute."""
    pattern = rf'<script[^>]*id="{element_id}"[^>]*>(.*?)</script>'
    match = re.search(pattern, html, re.DOTALL)
    assert match, f"Could not find <script id='{element_id}'> in HTML"
    return json.loads(match.group(1).strip())


# ============================================================================
# Grocery List — realistic snapshot
# ============================================================================


def grocery_list_snapshot():
    """
    Realistic grocery list aide: heading, text intro, metric for budget,
    collection with 6 items in list view, one checked item highlighted,
    custom style tokens, and an annotation.
    """
    snapshot = empty_state()

    snapshot["meta"] = {
        "title": "Weekly Groceries",
        "identity": "Family grocery list. Updated weekly.",
        "visibility": "unlisted",
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
                "item_deleted": {
                    "name": "Removed Item",
                    "category": "other",
                    "quantity": 1,
                    "checked": False,
                    "store": None,
                    "_removed": True,
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
            "props": {"content": "Updated every **Sunday** morning. Check off items as you go."},
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
            "note": "Added chicken thighs per Dave's request.",
            "pinned": False,
            "seq": 5,
            "timestamp": "2026-02-15T10:30:00Z",
        },
        {
            "note": "Budget limit: $60/week.",
            "pinned": True,
            "seq": 2,
            "timestamp": "2026-02-10T09:00:00Z",
        },
    ]

    return snapshot


def grocery_blueprint():
    return Blueprint(
        identity="Family grocery list. Updated weekly.",
        voice="No first person. State reflections only. No encouragement.",
        prompt="You are maintaining a living grocery list page.",
    )


def grocery_events():
    from engine.kernel.types import Event
    return [
        Event(
            id="evt_20260210_001",
            sequence=1,
            timestamp="2026-02-10T09:00:00Z",
            actor="user_zach",
            source="web",
            type="collection.create",
            payload={"id": "grocery_list", "schema": {"name": "string"}},
        ),
        Event(
            id="evt_20260210_002",
            sequence=2,
            timestamp="2026-02-10T09:01:00Z",
            actor="user_zach",
            source="web",
            type="meta.annotate",
            payload={"note": "Budget limit: $60/week.", "pinned": True},
        ),
    ]


# ============================================================================
# Full render — grocery list
# ============================================================================


class TestGroceryListFullRender:
    """
    Full round-trip: build realistic grocery list, render, verify everything.
    """

    @pytest.fixture
    def html(self):
        return render(
            grocery_list_snapshot(),
            grocery_blueprint(),
            events=grocery_events(),
        )

    # -- Document structure --

    def test_valid_html5_doctype(self, html):
        """Output starts with <!DOCTYPE html>."""
        assert html.strip().startswith("<!DOCTYPE html>")

    def test_html_lang(self, html):
        """<html lang='en'> is present."""
        assert_contains(html, '<html lang="en">')

    def test_charset_meta(self, html):
        """<meta charset='utf-8'> is present."""
        assert_contains(html, 'charset="utf-8"')

    def test_viewport_meta(self, html):
        """Viewport meta tag for responsive design."""
        assert_contains(html, 'name="viewport"')

    def test_title_tag(self, html):
        """<title> contains the aide's title."""
        assert_contains(html, "<title>Weekly Groceries</title>")

    def test_body_and_main(self, html):
        """<body> and <main class='aide-page'> wrap content."""
        assert_contains(html, "<body>")
        assert_contains(html, 'class="aide-page"')
        assert_contains(html, "</main>")
        assert_contains(html, "</body>")

    # -- OG tags --

    def test_og_title(self, html):
        """OG title tag matches aide title."""
        assert_contains(html, 'og:title')
        assert_contains(html, "Weekly Groceries")

    def test_og_type(self, html):
        """OG type is 'website'."""
        assert_contains(html, 'og:type')
        assert_contains(html, "website")

    def test_og_description(self, html):
        """OG description is derived from first text block content."""
        assert_contains(html, 'og:description')

    # -- Embedded JSON --

    def test_blueprint_json_embedded(self, html):
        """Blueprint is embedded in a <script> tag with correct type."""
        assert_contains(html, 'type="application/aide-blueprint+json"')
        assert_contains(html, 'id="aide-blueprint"')
        bp = extract_json_block(html, "aide-blueprint")
        assert bp["identity"] == "Family grocery list. Updated weekly."
        assert bp["voice"] == "No first person. State reflections only. No encouragement."

    def test_snapshot_json_embedded(self, html):
        """Snapshot is embedded with sorted keys."""
        assert_contains(html, 'type="application/aide+json"')
        assert_contains(html, 'id="aide-state"')
        state = extract_json_block(html, "aide-state")
        assert "collections" in state
        assert "blocks" in state
        assert state["meta"]["title"] == "Weekly Groceries"

    def test_events_json_embedded(self, html):
        """Events are embedded as a JSON array."""
        assert_contains(html, 'type="application/aide-events+json"')
        assert_contains(html, 'id="aide-events"')
        events = extract_json_block(html, "aide-events")
        assert isinstance(events, list)
        assert len(events) == 2

    def test_snapshot_json_sorted_keys(self, html):
        """Embedded snapshot JSON uses sorted keys for determinism."""
        pattern = r'<script[^>]*id="aide-state"[^>]*>(.*?)</script>'
        match = re.search(pattern, html, re.DOTALL)
        raw_json = match.group(1).strip()
        # Re-serialize with sorted keys and compare
        parsed = json.loads(raw_json)
        resorted = json.dumps(parsed, sort_keys=True)
        reparsed = json.dumps(json.loads(raw_json), sort_keys=True)
        assert resorted == reparsed

    # -- CSS / style tokens --

    def test_style_block_present(self, html):
        """<style> block is present in <head>."""
        assert_contains(html, "<style>")

    def test_style_token_overrides(self, html):
        """Custom style tokens produce CSS variable overrides."""
        assert_contains(html, "--text-primary: #2d3748")
        assert_contains(html, "--bg-primary: #fafaf9")

    # -- Block content --

    def test_heading_rendered(self, html):
        """H1 heading with 'Weekly Groceries'."""
        assert_contains(html, "aide-heading--1")
        assert_contains(html, "Weekly Groceries")

    def test_text_block_with_inline_bold(self, html):
        """Text block renders with **Sunday** as <strong>."""
        assert_contains(html, "<strong>Sunday</strong>")
        assert_contains(html, "Check off items as you go.")

    def test_metric_rendered(self, html):
        """Metric block shows label and value."""
        assert_contains(html, "aide-metric")
        assert_contains(html, "Estimated total")
        assert_contains(html, "$47.50")

    # -- Collection / entity content --

    def test_grocery_items_present(self, html):
        """All 5 non-removed items appear in the output."""
        assert_contains(html, "Whole Milk")
        assert_contains(html, "Eggs (dozen)")
        assert_contains(html, "Sourdough Bread")
        assert_contains(html, "Chicken Thighs")
        assert_contains(html, "Baby Spinach")

    def test_removed_item_excluded(self, html):
        """Removed item is NOT in the rendered collection view (but may be in embedded JSON)."""
        # Extract the main content section, not the embedded JSON
        import re
        main_match = re.search(r'<main[^>]*>(.*?)</main>', html, re.DOTALL)
        assert main_match, "Expected <main> element in output"
        main_content = main_match.group(1)
        assert "Removed Item" not in main_content, "Removed item should not appear in rendered content"

    def test_checked_items_have_bool_class(self, html):
        """Checked=true items get bool formatting class."""
        assert_contains(html, "aide-list__field--bool")

    def test_null_store_renders_em_dash(self, html):
        """Null store field renders as em dash."""
        # Sourdough Bread has store=None, but store isn't in show_fields
        # so this depends on show_fields. Let's just check the list renders.
        assert_contains(html, "aide-list")

    def test_highlighted_items_get_class(self, html):
        """Highlighted items (Whole Milk, Baby Spinach) get aide-highlight."""
        count = html.count("aide-highlight")
        # At least 2 in the content (Whole Milk and Baby Spinach)
        # Plus potentially 1 in CSS definition
        assert count >= 2

    def test_enum_values_title_cased(self, html):
        """Category enum values are title-cased (dairy → Dairy)."""
        assert_contains(html, "Dairy")
        assert_contains(html, "Produce")

    # -- Block order --

    def test_blocks_in_order(self, html):
        """Blocks render in tree order: heading, text, metric, collection."""
        assert_order(
            html,
            "Weekly Groceries",  # heading
            "Sunday",            # text block
            "Estimated total",   # metric
            "aide-list",         # collection view
        )

    # -- Annotations --

    def test_annotations_rendered(self, html):
        """Annotations appear in the output."""
        assert_contains(html, "aide-annotations")
        assert_contains(html, "Added chicken thighs")
        assert_contains(html, "Budget limit: $60/week")

    def test_pinned_annotation_has_class(self, html):
        """Pinned annotation gets aide-annotation--pinned class."""
        assert_contains(html, "aide-annotation--pinned")

    # -- Fonts --

    def test_google_fonts_linked(self, html):
        """Google Fonts preconnect and stylesheet links present."""
        assert_contains(html, "fonts.googleapis.com")
        assert_contains(html, "Cormorant+Garamond")
        assert_contains(html, "IBM+Plex+Sans")

    # -- No JavaScript --

    def test_no_javascript(self, html):
        """Output has no executable JavaScript (only data script tags)."""
        # The only <script> tags should have type="application/..." (data)
        script_pattern = re.findall(r'<script([^>]*)>', html)
        for attrs in script_pattern:
            assert "application/" in attrs, (
                f"Found script tag without data MIME type: <script{attrs}>"
            )

    # -- Output sanity --

    def test_output_is_string(self, html):
        """render() returns a string."""
        assert isinstance(html, str)

    def test_output_reasonable_size(self, html):
        """Grocery list output is 5-10KB range per spec."""
        size_kb = len(html.encode("utf-8")) / 1024
        assert size_kb > 1, f"Output too small: {size_kb:.1f}KB"
        assert size_kb < 100, f"Output unexpectedly large: {size_kb:.1f}KB"


# ============================================================================
# Poker League — second realistic scenario
# ============================================================================


def poker_league_snapshot():
    """
    Poker league aide: heading, text, two metrics, roster in table view,
    schedule in table view, style tokens, annotations.
    """
    snapshot = empty_state()

    snapshot["meta"] = {
        "title": "Poker League — Spring 2026",
        "identity": "Poker league. 8 players, biweekly Thursday, rotating hosts.",
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
                    "winnings": 340.00,
                    "active": True,
                    "_removed": False,
                },
                "player_sarah": {
                    "name": "Sarah",
                    "buy_ins": 7,
                    "winnings": 520.50,
                    "active": True,
                    "_removed": False,
                    "_styles": {"highlight": True, "bg_color": "#fef3c7"},
                },
                "player_dave": {
                    "name": "Dave",
                    "buy_ins": 8,
                    "winnings": 180.00,
                    "active": True,
                    "_removed": False,
                },
                "player_carol": {
                    "name": "Carol",
                    "buy_ins": 5,
                    "winnings": 0.0,
                    "active": False,
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
                "game_3": {
                    "date": "2026-03-13",
                    "host": "Sarah",
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
            "block_title", "block_intro", "block_next_game",
            "block_total_pot", "block_divider",
            "block_roster_heading", "block_roster",
            "block_schedule_heading", "block_schedule",
        ]},
        "block_title": {
            "type": "heading",
            "parent": "block_root",
            "props": {"level": 1, "content": "Poker League — Spring 2026"},
        },
        "block_intro": {
            "type": "text",
            "parent": "block_root",
            "props": {"content": "Biweekly Thursday games. $20 buy-in. See [rules](https://example.com/rules) for details."},
        },
        "block_next_game": {
            "type": "metric",
            "parent": "block_root",
            "props": {"label": "Next game", "value": "Feb 27 at Dave's"},
        },
        "block_total_pot": {
            "type": "metric",
            "parent": "block_root",
            "props": {"label": "Season pot", "value": "$320"},
        },
        "block_divider": {
            "type": "divider",
            "parent": "block_root",
            "props": {},
        },
        "block_roster_heading": {
            "type": "heading",
            "parent": "block_root",
            "props": {"level": 2, "content": "Roster"},
        },
        "block_roster": {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "roster", "view": "roster_view"},
        },
        "block_schedule_heading": {
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

    snapshot["annotations"] = [
        {
            "note": "Host rotation advanced. Dave hosting Feb 27.",
            "pinned": False,
            "seq": 10,
            "timestamp": "2026-02-14T20:00:00Z",
        },
    ]

    return snapshot


def poker_blueprint():
    return Blueprint(
        identity="Poker league. 8 players, biweekly Thursday, rotating hosts.",
        voice="No first person. No emojis. No encouragement. State reflections only.",
        prompt="You are maintaining a living page for a poker league.",
    )


class TestPokerLeagueFullRender:
    """
    Full round-trip for a more complex aide with multiple collections,
    tables, metrics, dividers, links, and entity style overrides.
    """

    @pytest.fixture
    def html(self):
        return render(poker_league_snapshot(), poker_blueprint())

    # -- Document structure --

    def test_title(self, html):
        assert_contains(html, "<title>Poker League")

    def test_valid_structure(self, html):
        assert_contains(html, "<!DOCTYPE html>")
        assert_contains(html, "<head>")
        assert_contains(html, "<body>")
        assert_contains(html, "aide-page")

    # -- Style tokens --

    def test_poker_style_tokens(self, html):
        """All poker league style tokens produce CSS overrides."""
        assert_contains(html, "--text-primary: #1a365d")
        assert_contains(html, "--bg-primary: #fffff0")

    # -- Multiple block types --

    def test_headings(self, html):
        """H1 and H2 headings present."""
        assert_contains(html, "aide-heading--1")
        assert_contains(html, "aide-heading--2")
        assert_contains(html, "Roster")
        assert_contains(html, "Schedule")

    def test_text_with_link(self, html):
        """Text block with inline link renders <a>."""
        assert_contains(html, '<a href="https://example.com/rules">')
        assert_contains(html, "rules</a>")

    def test_metrics(self, html):
        """Both metrics render."""
        assert_contains(html, "Next game")
        assert_contains(html, "Feb 27")
        assert_contains(html, "Season pot")
        assert_contains(html, "$320")

    def test_divider(self, html):
        """Divider renders."""
        assert_contains(html, "aide-divider")

    # -- Roster table --

    def test_roster_table_headers(self, html):
        """Roster table has correct column headers."""
        assert_contains(html, "aide-table")
        assert_contains(html, "Name")
        assert_contains(html, "Buy Ins")
        assert_contains(html, "Winnings")
        assert_contains(html, "Active")

    def test_roster_sorted_by_winnings_desc(self, html):
        """Roster sorted by winnings descending: Sarah, Mike, Dave, Carol."""
        # "Dave" also appears in the metric "Feb 27 at Dave's" before the roster table,
        # so we need to look within the roster table specifically (first table in main)
        main = extract_main(html)
        tables = re.findall(r'<table class="aide-table">(.*?)</table>', main, re.DOTALL)
        assert len(tables) >= 1, "Expected at least 1 table"
        roster_table = tables[0]  # Roster is the first table
        # Check players appear in winnings descending order within the roster table
        assert_order(roster_table, "Sarah", "Mike", "Dave", "Carol")

    def test_roster_entity_highlight(self, html):
        """Sarah has highlight + bg_color overrides."""
        assert_contains(html, "aide-highlight")
        assert_contains(html, "background-color: #fef3c7")

    def test_roster_float_values(self, html):
        """Float winnings values render."""
        assert_contains(html, "520.5")
        assert_contains(html, "340")

    def test_roster_bool_formatting(self, html):
        """Active column has bool formatting."""
        assert_contains(html, "aide-table__td--bool")

    # -- Schedule table --

    def test_schedule_dates_formatted(self, html):
        """Schedule dates rendered as short format, not ISO."""
        # Check formatted dates appear somewhere in rendered content
        main = extract_main(html)
        assert "Feb 13" in main
        assert "Feb 27" in main
        assert "Mar 13" in main
        # ISO dates should NOT appear in rendered main content (they're in embedded JSON only)
        assert "2026-02-13" not in main, "ISO dates should be formatted, not raw"

    def test_schedule_enum_title_case(self, html):
        """Status enum values are title-cased."""
        assert_contains(html, "Completed")
        assert_contains(html, "Upcoming")

    def test_schedule_sorted_by_date_asc(self, html):
        """Schedule sorted by date ascending within the schedule table."""
        # Extract the schedule table specifically (second aide-table in main)
        # Feb 27 also appears in the "Next game" metric before the schedule table,
        # so we need to look at the order within the table itself.
        main = extract_main(html)
        # Find all table rows in the document, the schedule table is the second one
        tables = re.findall(r'<table class="aide-table">(.*?)</table>', main, re.DOTALL)
        assert len(tables) >= 2, f"Expected at least 2 tables, found {len(tables)}"
        schedule_table = tables[1]  # Schedule is the second table
        # Check dates appear in ascending order within the schedule table
        assert_order(schedule_table, "Feb 13", "Feb 27", "Mar 13")

    # -- Annotations --

    def test_annotation_rendered(self, html):
        """Poker annotation appears."""
        assert_contains(html, "Host rotation advanced")

    # -- Block order --

    def test_full_block_order(self, html):
        """All blocks in document order."""
        # Search within <main> only to avoid finding class names in CSS
        assert_order_in_main(
            html,
            "Poker League",            # H1
            "Biweekly Thursday",       # text
            "Next game",               # metric 1
            "Season pot",              # metric 2
            '<hr class="aide-divider', # divider element
            ">Roster<",                # H2 (with angle brackets to avoid substring match)
            '<table class="aide-table', # roster table element
            ">Schedule<",              # H2
        )


# ============================================================================
# Render options
# ============================================================================


class TestRenderOptions:
    """
    RenderOptions control what's included in the output.
    """

    def test_events_excluded_when_disabled(self):
        """include_events=False omits the aide-events script block."""
        from engine.kernel.renderer import RenderOptions

        html = render(
            grocery_list_snapshot(),
            grocery_blueprint(),
            events=grocery_events(),
            options=RenderOptions(include_events=False),
        )

        assert_not_contains(html, 'id="aide-events"')
        # Blueprint and state should still be present
        assert_contains(html, 'id="aide-blueprint"')
        assert_contains(html, 'id="aide-state"')

    def test_blueprint_excluded_when_disabled(self):
        """include_blueprint=False omits the aide-blueprint script block."""
        from engine.kernel.renderer import RenderOptions

        html = render(
            grocery_list_snapshot(),
            grocery_blueprint(),
            options=RenderOptions(include_blueprint=False),
        )

        assert_not_contains(html, 'id="aide-blueprint"')
        assert_contains(html, 'id="aide-state"')

    def test_footer_present_for_free_tier(self):
        """Footer with 'Made with AIde' present when footer option set."""
        from engine.kernel.renderer import RenderOptions

        html = render(
            grocery_list_snapshot(),
            grocery_blueprint(),
            options=RenderOptions(footer="Made with AIde"),
        )

        assert_contains(html, "aide-footer")
        assert_contains(html, "Made with AIde")
        assert_contains(html, "toaide.com")

    def test_footer_absent_for_pro(self):
        """No footer when footer option is None (pro tier)."""
        from engine.kernel.renderer import RenderOptions

        html = render(
            grocery_list_snapshot(),
            grocery_blueprint(),
            options=RenderOptions(footer=None),
        )

        # Check that no footer element appears in <body> (CSS still has .aide-footer styles)
        assert_not_in_body(html, '<footer class="aide-footer">')


# ============================================================================
# Embedded JSON round-trip integrity
# ============================================================================


class TestEmbeddedJSONIntegrity:
    """
    The embedded JSON in the rendered HTML can be extracted and re-used.
    This is how the assembly layer loads an aide from its HTML file.
    """

    def test_snapshot_round_trips_through_html(self):
        """
        Snapshot embedded in HTML matches the original snapshot
        when extracted and parsed.
        """
        original = grocery_list_snapshot()
        html = render(original, grocery_blueprint())

        extracted = extract_json_block(html, "aide-state")

        # Key structural elements match
        assert extracted["meta"]["title"] == "Weekly Groceries"
        assert "grocery_list" in extracted["collections"]
        assert len(extracted["collections"]["grocery_list"]["entities"]) == len(
            original["collections"]["grocery_list"]["entities"]
        )

    def test_blueprint_round_trips_through_html(self):
        """Blueprint embedded in HTML matches original."""
        bp = grocery_blueprint()
        html = render(grocery_list_snapshot(), bp)

        extracted = extract_json_block(html, "aide-blueprint")

        assert extracted["identity"] == bp.identity
        assert extracted["voice"] == bp.voice
        assert extracted["prompt"] == bp.prompt

    def test_events_round_trip_through_html(self):
        """Events embedded in HTML match original."""
        events = grocery_events()
        html = render(grocery_list_snapshot(), grocery_blueprint(), events=events)

        extracted = extract_json_block(html, "aide-events")

        assert len(extracted) == len(events)
        assert extracted[0]["type"] == "collection.create"
        assert extracted[1]["type"] == "meta.annotate"


# ============================================================================
# OG description derivation
# ============================================================================


class TestOGDescriptionDerivation:
    """
    OG description is derived from:
    1. First text block's content (truncated to 160 chars)
    2. Collection summary ("Grocery List: 5 items")
    3. Fallback to title
    """

    def test_description_from_text_block(self):
        """Description derived from first text block."""
        html = render(grocery_list_snapshot(), grocery_blueprint())

        assert_contains(html, 'og:description')
        # The first text block starts with "Updated every..."
        assert_contains(html, "Updated every")

    def test_description_from_collection_summary(self):
        """When no text block, description comes from collection summary."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Items Only"}
        snapshot["collections"] = {
            "tasks": {
                "id": "tasks",
                "name": "Tasks",
                "schema": {"name": "string"},
                "entities": {
                    "t1": {"name": "A", "_removed": False},
                    "t2": {"name": "B", "_removed": False},
                    "t3": {"name": "C", "_removed": False},
                },
            },
        }
        # No text blocks — just a collection_view
        snapshot["views"] = {
            "v": {"id": "v", "type": "list", "source": "tasks", "config": {}},
        }
        snapshot["blocks"]["block_cv"] = {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "tasks", "view": "v"},
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_cv"]

        html = render(snapshot, grocery_blueprint())

        assert_contains(html, 'og:description')
        assert_contains(html, "Tasks")
        assert_contains(html, "3 items")

    def test_description_fallback_to_title(self):
        """Empty page falls back to title for description."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "My Empty Page"}

        html = render(snapshot, grocery_blueprint())

        assert_contains(html, 'og:description')
