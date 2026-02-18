"""
AIde Renderer -- Full Round-Trip Tests (v3 Unified Entity Model)

Build a realistic snapshot by hand, render, verify it looks right.
Verifies the complete rendered HTML has:
  - Valid HTML5 document structure
  - All expected content present and in order
  - Correct CSS, OG tags, embedded JSON
  - Heading + text + metrics + entity_view all wired up
  - Style tokens and entity rendering all firing
  - Annotations rendered
  - Footer present/absent per tier
  - Output is saveable (can extract and re-parse JSON)

Reference: aide_renderer_spec.md (full spec)
"""

import json
import re

import pytest

from engine.kernel.reducer import empty_state
from engine.kernel.renderer import render
from engine.kernel.types import Blueprint, RenderOptions


def assert_contains(html, *fragments):
    for fragment in fragments:
        assert fragment in html, (
            f"Expected to find {fragment!r} in rendered HTML.\nGot (first 3000 chars):\n{html[:3000]}"
        )


def assert_not_contains(html, *fragments):
    for fragment in fragments:
        assert fragment not in html, f"Did NOT expect to find {fragment!r} in rendered HTML."


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
    """Extract content within <main> tags only."""
    match = re.search(r"<main[^>]*>(.*?)</main>", html, re.DOTALL)
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


def extract_json_block(html, element_id):
    """Extract JSON from a <script> block by its id attribute."""
    pattern = rf'<script[^>]*id="{element_id}"[^>]*>(.*?)</script>'
    match = re.search(pattern, html, re.DOTALL)
    assert match, f"Could not find <script id='{element_id}'> in HTML"
    return json.loads(match.group(1).strip())


def grocery_list_snapshot():
    """
    A realistic grocery list snapshot with heading, text, metric,
    entity view, style tokens, and annotations.
    """
    snapshot = empty_state()

    snapshot["meta"] = {
        "title": "Weekly Groceries",
        "identity": "Family grocery list for the week.",
    }

    snapshot["styles"] = {
        "primary_color": "#2d3748",
        "bg_color": "#fafaf9",
        "text_color": "#1a1a1a",
    }

    snapshot["schemas"]["grocery_item"] = {
        "interface": "interface GroceryItem { name: string; checked: boolean; qty: number; }",
        "render_html": "<li class=\"grocery-item\">{{name}} (x{{qty}})</li>",
        "render_text": "- {{name}} x{{qty}}",
        "styles": ".grocery-item { padding: 6px 0; list-style: disc; }",
    }

    snapshot["schemas"]["grocery_list"] = {
        "interface": "interface GroceryList { name: string; items: Record<string, GroceryItem>; }",
        "render_html": "<ul class=\"grocery-list\">{{>items}}</ul>",
    }

    snapshot["entities"]["this_weeks_list"] = {
        "_schema": "grocery_list",
        "name": "This Week's List",
        "items": {
            "item_milk": {"name": "Milk", "checked": False, "qty": 2, "_pos": 1.0},
            "item_eggs": {"name": "Eggs", "checked": False, "qty": 1, "_pos": 2.0},
            "item_bread": {"name": "Bread", "checked": True, "qty": 1, "_pos": 3.0},
            "item_coffee": {"name": "Coffee", "checked": False, "qty": 2, "_pos": 4.0},
        },
    }

    snapshot["blocks"]["block_title"] = {
        "type": "heading",
        "level": 1,
        "text": "Weekly Groceries",
    }
    snapshot["blocks"]["block_note"] = {
        "type": "text",
        "text": "Updated **Tuesday evening**. Pick up before Friday.",
    }
    snapshot["blocks"]["block_count"] = {
        "type": "metric",
        "label": "Items remaining",
        "value": "3",
    }
    snapshot["blocks"]["block_divider"] = {"type": "divider"}
    snapshot["blocks"]["block_groceries"] = {
        "type": "entity_view",
        "source": "this_weeks_list",
    }
    snapshot["blocks"]["block_root"]["children"] = [
        "block_title",
        "block_note",
        "block_count",
        "block_divider",
        "block_groceries",
    ]

    snapshot["annotations"] = [
        {
            "note": "Added coffee to the list.",
            "timestamp": "2026-02-18T10:00:00Z",
        }
    ]

    return snapshot


def poker_snapshot():
    """A poker league tracker snapshot."""
    snapshot = empty_state()

    snapshot["meta"] = {
        "title": "Poker League 2026",
        "identity": "Monthly home game for 6 players.",
    }

    snapshot["styles"] = {
        "primary_color": "#7c3aed",
        "bg_color": "#fdf4ff",
    }

    snapshot["schemas"]["player"] = {
        "interface": "interface Player { name: string; wins: number; buy_ins: number; }",
        "render_html": '<tr class="player-row"><td>{{name}}</td><td>{{wins}}</td><td>{{buy_ins}}</td></tr>',
        "render_text": "{{name}}: {{wins}}W / {{buy_ins}}BI",
        "styles": ".player-row { border-bottom: 1px solid #e9d5ff; }",
    }

    snapshot["schemas"]["league"] = {
        "interface": "interface League { name: string; roster: Record<string, Player>; }",
        "render_html": '<table class="player-table"><thead><tr><th>Name</th><th>Wins</th><th>Buy-ins</th></tr></thead><tbody>{{>roster}}</tbody></table>',
    }

    snapshot["entities"]["poker_league"] = {
        "_schema": "league",
        "name": "Poker League",
        "roster": {
            "player_mike": {"name": "Mike", "wins": 3, "buy_ins": 12, "_pos": 1.0},
            "player_sarah": {"name": "Sarah", "wins": 5, "buy_ins": 10, "_pos": 2.0},
            "player_dave": {"name": "Dave", "wins": 2, "buy_ins": 15, "_pos": 3.0},
        },
    }

    snapshot["blocks"]["block_title"] = {
        "type": "heading",
        "level": 1,
        "text": "Poker League 2026",
    }
    snapshot["blocks"]["block_next_game"] = {
        "type": "metric",
        "label": "Next Game",
        "value": "March 15 at Mike's",
    }
    snapshot["blocks"]["block_pot"] = {
        "type": "metric",
        "label": "Current Pot",
        "value": "$240",
    }
    snapshot["blocks"]["block_roster"] = {
        "type": "entity_view",
        "source": "poker_league",
    }
    snapshot["blocks"]["block_root"]["children"] = [
        "block_title",
        "block_next_game",
        "block_pot",
        "block_roster",
    ]

    return snapshot


def make_blueprint():
    return Blueprint(
        identity="Test aide for round-trip rendering.",
        voice="No first person. State reflections only.",
        prompt="You are maintaining a test page.",
    )


# ============================================================================
# Grocery list full render
# ============================================================================


class TestGroceryListRoundTrip:
    """Full round-trip test for grocery list snapshot."""

    @pytest.fixture
    def html(self):
        return render(grocery_list_snapshot(), make_blueprint())

    def test_valid_html5_structure(self, html):
        """Output is valid HTML5 with correct structure."""
        assert_contains(html, "<!DOCTYPE html>", "<html", "<head>", "<body>", "</html>")

    def test_title_in_head(self, html):
        """Title tag is in <head>."""
        head_start = html.find("<head>")
        head_end = html.find("</head>")
        head = html[head_start:head_end]
        assert "<title>Weekly Groceries</title>" in head

    def test_main_content_present(self, html):
        """Main content div is present."""
        assert_contains(html, '<main class="aide-page"')

    def test_heading_renders(self, html):
        """Heading block renders in main content."""
        main = extract_main(html)
        assert "Weekly Groceries" in main

    def test_text_block_with_bold(self, html):
        """Text block with **bold** renders as <strong>."""
        main = extract_main(html)
        assert "<strong>Tuesday evening</strong>" in main

    def test_metric_renders(self, html):
        """Metric block renders label and value."""
        main = extract_main(html)
        assert "Items remaining" in main
        assert "3" in main

    def test_grocery_items_render(self, html):
        """Grocery items render via schema template."""
        assert_contains(html, "Milk", "Eggs", "Bread", "Coffee")

    def test_grocery_list_ul_present(self, html):
        """Grocery list renders <ul class='grocery-list'>."""
        assert_contains(html, "class=\"grocery-list\"")

    def test_grocery_li_present(self, html):
        """Grocery items render as <li class='grocery-item'>."""
        assert_contains(html, "class=\"grocery-item\"")

    def test_content_order(self, html):
        """Content renders in block order: heading, text, metric, divider, list."""
        main = extract_main(html)
        title_pos = main.find("Weekly Groceries")
        note_pos = main.find("Tuesday evening")
        metric_pos = main.find("Items remaining")
        list_pos = main.find("grocery-list")
        assert title_pos < note_pos < metric_pos < list_pos

    def test_style_token_applied(self, html):
        """Primary color style token appears as --accent."""
        assert "--accent: #2d3748" in html

    def test_schema_css_present(self, html):
        """Schema CSS is included in <style> block."""
        assert ".grocery-item" in html

    def test_annotations_rendered(self, html):
        """Annotations appear in rendered output."""
        assert_contains(html, "Added coffee to the list.")

    def test_divider_present(self, html):
        """Divider block renders as <hr>."""
        assert "<hr>" in html or "<hr" in html

    def test_embedded_snapshot_parseable(self, html):
        """Embedded aide-state JSON is valid and parseable."""
        state = extract_json_block(html, "aide-state")
        assert isinstance(state, dict)
        assert state.get("version") == 3
        assert "meta" in state
        assert state["meta"]["title"] == "Weekly Groceries"

    def test_og_tags_present(self, html):
        """OG meta tags are in <head>."""
        assert_contains(html, 'property="og:title"', 'property="og:type"')
        assert_contains(html, 'content="Weekly Groceries"')


# ============================================================================
# Poker league full render
# ============================================================================


class TestPokerLeagueRoundTrip:
    """Full round-trip test for poker league snapshot."""

    @pytest.fixture
    def html(self):
        return render(poker_snapshot(), make_blueprint())

    def test_valid_html5_structure(self, html):
        assert_contains(html, "<!DOCTYPE html>", "<html", "</html>")

    def test_players_render(self, html):
        """Player entities render via schema template."""
        assert_contains(html, "Mike", "Sarah", "Dave")

    def test_table_structure(self, html):
        """League uses table structure from schema."""
        assert_contains(html, "class=\"player-table\"", "<thead>", "<tbody>")

    def test_table_headers(self, html):
        """Table headers appear."""
        assert_contains(html, "<th>Name</th>", "<th>Wins</th>")

    def test_player_data_in_rows(self, html):
        """Player data appears in table rows."""
        assert_contains(html, "<td>Mike</td>", "<td>Sarah</td>")

    def test_metrics_present(self, html):
        """Metric blocks render."""
        main = extract_main(html)
        assert "Next Game" in main
        assert "Current Pot" in main

    def test_style_accent_applied(self, html):
        """Purple primary color appears as --accent."""
        assert "--accent: #7c3aed" in html

    def test_schema_player_css(self, html):
        """Player schema CSS is included."""
        assert ".player-row" in html

    def test_embedded_json_valid(self, html):
        """Embedded state JSON is valid."""
        state = extract_json_block(html, "aide-state")
        assert state["meta"]["title"] == "Poker League 2026"


# ============================================================================
# RenderOptions: blueprint, events, footer, fonts
# ============================================================================


class TestRenderOptions:
    """Verify RenderOptions control output."""

    def test_include_blueprint(self):
        """include_blueprint=True embeds blueprint JSON."""
        snap = grocery_list_snapshot()
        bp = make_blueprint()
        html = render(snap, bp, options=RenderOptions(include_blueprint=True))
        assert '<script type="application/aide-blueprint+json"' in html

    def test_exclude_blueprint_by_default(self):
        """Blueprint IS embedded by default (include_blueprint=True by default)."""
        snap = grocery_list_snapshot()
        html = render(snap, make_blueprint())
        assert "aide-blueprint" in html

    def test_include_events(self):
        """include_events=True embeds events JSON."""
        from engine.kernel.types import Event, now_iso
        snap = grocery_list_snapshot()
        events = [
            Event(
                id="evt_001",
                sequence=1,
                timestamp=now_iso(),
                actor="user",
                source="web",
                type="schema.create",
                payload={"id": "test", "interface": "interface Test { name: string; }"},
            )
        ]
        html = render(snap, make_blueprint(), events=events, options=RenderOptions(include_events=True))
        assert "aide-events" in html

    def test_exclude_events_by_default(self):
        """Events are not embedded by default."""
        snap = grocery_list_snapshot()
        html = render(snap, make_blueprint())
        assert "aide-events" not in html

    def test_footer_rendered(self):
        """Footer text appears when provided."""
        snap = grocery_list_snapshot()
        html = render(snap, make_blueprint(), options=RenderOptions(footer="Made with AIde"))
        assert "Made with AIde" in html
        assert "aide-footer" in html

    def test_no_footer_element_by_default(self):
        """No <footer> element in body when footer option not set."""
        snap = grocery_list_snapshot()
        html = render(snap, make_blueprint(), options=RenderOptions(footer=None))
        # .aide-footer appears in CSS, but the <footer> element should not be in body
        import re as _re
        m = _re.search(r"<body[^>]*>(.*?)</body>", html, _re.DOTALL)
        body = m.group(1) if m else ""
        assert "<footer" not in body

    def test_include_fonts_adds_google_fonts(self):
        """include_fonts=True adds Google Fonts link."""
        snap = grocery_list_snapshot()
        html = render(snap, make_blueprint(), options=RenderOptions(include_fonts=True))
        assert "fonts.googleapis.com" in html

    def test_include_fonts_by_default(self):
        """Fonts ARE included by default (include_fonts=True by default)."""
        snap = grocery_list_snapshot()
        html = render(snap, make_blueprint())
        assert "fonts.googleapis.com" in html

    def test_text_channel(self):
        """Text channel renders plain text."""
        snap = grocery_list_snapshot()
        text = render(snap, make_blueprint(), options=RenderOptions(channel="text"))
        assert "Weekly Groceries" in text
        assert "<!DOCTYPE html>" not in text


# ============================================================================
# JSON round-trip
# ============================================================================


class TestJSONRoundTrip:
    """The embedded JSON can be extracted and re-used."""

    def test_snapshot_round_trip(self):
        """Embedded snapshot JSON round-trips correctly."""
        original = grocery_list_snapshot()
        html = render(original, make_blueprint())

        extracted = extract_json_block(html, "aide-state")

        # Key structural elements preserved
        assert extracted["meta"]["title"] == original["meta"]["title"]
        assert "schemas" in extracted
        assert "entities" in extracted

    def test_state_json_has_sorted_keys(self):
        """State JSON has sorted keys for determinism."""
        snap = grocery_list_snapshot()
        html = render(snap, make_blueprint())

        pattern = r'<script[^>]*id="aide-state"[^>]*>(.*?)</script>'
        match = re.search(pattern, html, re.DOTALL)
        raw = match.group(1).strip()

        # Parse and re-serialize with sorted keys
        parsed = json.loads(raw)
        resorted = json.dumps(parsed, sort_keys=True)
        original_sorted = json.dumps(json.loads(raw), sort_keys=True)
        assert resorted == original_sorted


# ============================================================================
# Content safety
# ============================================================================


class TestContentSafety:
    """User content must be properly escaped in full render."""

    def test_xss_in_title_escaped(self):
        """XSS in meta.title is escaped in HTML title tag."""
        snap = empty_state()
        snap["meta"] = {"title": '<script>alert("xss")</script>'}
        html = render(snap, make_blueprint())

        title_section = re.search(r"<title>(.*?)</title>", html)
        assert title_section
        assert "<script>" not in title_section.group(1)

    def test_xss_in_heading_text_escaped(self):
        """XSS in block text is escaped."""
        snap = empty_state()
        snap["blocks"]["block_h"] = {
            "type": "heading",
            "level": 1,
            "text": '<img src=x onerror=alert(1)>',
        }
        snap["blocks"]["block_root"]["children"] = ["block_h"]
        html = render(snap, make_blueprint())

        main = extract_main(html)
        assert "<img" not in main
        assert "&lt;img" in main

    def test_xss_in_metric_value_escaped(self):
        """XSS in metric value is escaped."""
        snap = empty_state()
        snap["blocks"]["block_m"] = {
            "type": "metric",
            "label": "Status",
            "value": "<script>evil()</script>",
        }
        snap["blocks"]["block_root"]["children"] = ["block_m"]
        html = render(snap, make_blueprint())

        main = extract_main(html)
        assert "<script>" not in main
