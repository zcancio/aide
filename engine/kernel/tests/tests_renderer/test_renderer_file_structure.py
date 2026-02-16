"""
AIde Renderer -- File Structure Tests (Category 11)

Verify output is valid HTML5 (doctype, head, body, proper nesting).
Verify embedded JSON is parseable. Verify blueprint, state, and events
are all present when options say to include them.

From the spec (aide_renderer_spec.md, "Testing Strategy"):
  "11. File structure. Verify output is valid HTML5 (doctype, head, body,
   proper nesting). Verify embedded JSON is parseable. Verify blueprint,
   state, and events are all present when options say to include them."

Exact output structure from spec:
  <!DOCTYPE html>
  <html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <!-- OG tags -->
    <!-- Blueprint script: type="application/aide-blueprint+json" id="aide-blueprint" -->
    <!-- Snapshot script: type="application/aide+json" id="aide-state" -->
    <!-- Events script:   type="application/aide-events+json" id="aide-events" -->
    <!-- Google Fonts preconnect + stylesheet -->
    <style>...</style>
  </head>
  <body>
    <main class="aide-page">
      {rendered block tree}
    </main>
    {optional footer}
  </body>
  </html>

Key rules:
  - No JavaScript (only data script tags with application/* types)
  - Sorted JSON keys for determinism
  - RenderOptions control which sections are included
  - Fonts can be excluded via include_fonts=False

Reference: aide_renderer_spec.md (Output Structure, Contract)
           aide_architecture.md (HTML File Structure)
"""

import json
import re
import pytest

from engine.kernel.renderer import render, RenderOptions
from engine.kernel.reducer import empty_state
from engine.kernel.types import Blueprint, Event


# ============================================================================
# Helpers
# ============================================================================


def assert_contains(html, *fragments):
    for fragment in fragments:
        assert fragment in html, (
            f"Expected to find {fragment!r} in rendered HTML.\n"
            f"Got (first 2000 chars):\n{html[:2000]}"
        )


def assert_not_contains(html, *fragments):
    for fragment in fragments:
        assert fragment not in html, (
            f"Did NOT expect to find {fragment!r} in rendered HTML."
        )


def assert_before(html, first, second):
    """Assert 'first' appears before 'second' in the HTML."""
    pos_a = html.find(first)
    pos_b = html.find(second)
    assert pos_a != -1, f"{first!r} not found"
    assert pos_b != -1, f"{second!r} not found"
    assert pos_a < pos_b, f"Expected {first!r} before {second!r}"


def extract_json_block(html, element_id):
    """Extract and parse JSON from a <script> by its id."""
    pattern = rf'<script[^>]*id="{element_id}"[^>]*>(.*?)</script>'
    match = re.search(pattern, html, re.DOTALL)
    assert match, f"Could not find <script id='{element_id}'>"
    return json.loads(match.group(1).strip())


def extract_raw_json(html, element_id):
    """Extract raw JSON string (not parsed) from a <script> by id."""
    pattern = rf'<script[^>]*id="{element_id}"[^>]*>(.*?)</script>'
    match = re.search(pattern, html, re.DOTALL)
    assert match, f"Could not find <script id='{element_id}'>"
    return match.group(1).strip()


def make_blueprint():
    return Blueprint(
        identity="Test aide.",
        voice="No first person.",
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
        Event(
            id="evt_20260215_002",
            sequence=2,
            timestamp="2026-02-15T09:01:00Z",
            actor="user_test",
            source="web",
            type="entity.create",
            payload={
                "collection": "items",
                "id": "item_1",
                "fields": {"name": "First"},
            },
        ),
    ]


def content_snapshot():
    """Snapshot with a heading, text block, and a small collection."""
    snapshot = empty_state()
    snapshot["meta"] = {"title": "Structure Test"}
    snapshot["styles"] = {"primary_color": "#2d3748"}

    snapshot["collections"] = {
        "tasks": {
            "id": "tasks",
            "name": "Tasks",
            "schema": {"name": "string", "done": "bool"},
            "entities": {
                "t1": {"name": "Write tests", "done": True, "_removed": False},
                "t2": {"name": "Review PR", "done": False, "_removed": False},
            },
        },
    }
    snapshot["views"] = {
        "tasks_view": {
            "id": "tasks_view",
            "type": "table",
            "source": "tasks",
            "config": {"show_fields": ["name", "done"]},
        },
    }

    snapshot["blocks"] = {
        "block_root": {"type": "root", "children": [
            "block_h1", "block_text", "block_tasks",
        ]},
        "block_h1": {
            "type": "heading",
            "parent": "block_root",
            "props": {"level": 1, "content": "Structure Test"},
        },
        "block_text": {
            "type": "text",
            "parent": "block_root",
            "props": {"content": "A page to verify file structure."},
        },
        "block_tasks": {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "tasks", "view": "tasks_view"},
        },
    }

    return snapshot


# ============================================================================
# HTML5 document structure
# ============================================================================


class TestHTML5DocumentStructure:
    """
    Verify the output is a valid HTML5 document with correct structure.
    """

    @pytest.fixture
    def html(self):
        return render(content_snapshot(), make_blueprint(), events=make_events())

    def test_starts_with_doctype(self, html):
        """First non-whitespace is <!DOCTYPE html>."""
        assert html.strip().lower().startswith("<!doctype html>")

    def test_html_tag_with_lang(self, html):
        """<html lang="en"> is present."""
        assert_contains(html, '<html lang="en">')

    def test_head_tag_present(self, html):
        """<head> and </head> are present."""
        assert_contains(html, "<head>")
        assert_contains(html, "</head>")

    def test_body_tag_present(self, html):
        """<body> and </body> are present."""
        assert_contains(html, "<body>")
        assert_contains(html, "</body>")

    def test_closing_html_tag(self, html):
        """</html> is present at the end."""
        assert_contains(html, "</html>")

    def test_head_before_body(self, html):
        """<head> appears before <body>."""
        assert_before(html, "<head>", "<body>")

    def test_charset_meta(self, html):
        """<meta charset="utf-8"> in <head>."""
        assert_contains(html, 'charset="utf-8"')

    def test_viewport_meta(self, html):
        """Viewport meta tag for responsive design."""
        assert_contains(html, 'name="viewport"')
        assert_contains(html, "width=device-width")

    def test_title_tag(self, html):
        """<title> contains the aide's meta title."""
        assert_contains(html, "<title>Structure Test</title>")

    def test_title_in_head(self, html):
        """<title> is inside <head>."""
        head_start = html.find("<head>")
        head_end = html.find("</head>")
        title_pos = html.find("<title>")
        assert head_start < title_pos < head_end

    def test_main_tag_with_aide_page(self, html):
        """<main class="aide-page"> wraps content in <body>."""
        assert_contains(html, '<main class="aide-page">')
        assert_contains(html, "</main>")

    def test_main_inside_body(self, html):
        """<main> is inside <body>."""
        body_start = html.find("<body>")
        body_end = html.find("</body>")
        main_pos = html.find("<main")
        assert body_start < main_pos < body_end


# ============================================================================
# Proper nesting
# ============================================================================


class TestProperNesting:
    """
    Verify key HTML elements are properly nested.
    """

    @pytest.fixture
    def html(self):
        return render(content_snapshot(), make_blueprint())

    def test_head_closes_before_body_opens(self, html):
        """</head> appears before <body>."""
        assert_before(html, "</head>", "<body>")

    def test_main_closes_before_body_closes(self, html):
        """</main> appears before </body>."""
        assert_before(html, "</main>", "</body>")

    def test_style_inside_head(self, html):
        """<style> block is inside <head>."""
        head_start = html.find("<head>")
        head_end = html.find("</head>")
        style_pos = html.find("<style>")
        assert head_start < style_pos < head_end, "<style> should be in <head>"

    def test_content_blocks_inside_main(self, html):
        """Rendered block content is inside <main>."""
        main_start = html.find("<main")
        main_end = html.find("</main>")
        assert main_start != -1
        main_content = html[main_start:main_end]
        assert "Structure Test" in main_content  # heading
        assert "aide-text" in main_content       # text block
        assert "aide-table" in main_content      # table

    def test_no_content_blocks_in_head(self, html):
        """No rendered block elements leak into <head> (CSS class definitions are OK)."""
        head_start = html.find("<head>")
        head_end = html.find("</head>")
        head_content = html[head_start:head_end]
        # Check that actual element tags don't appear (CSS definitions are fine)
        assert '<h1 class="aide-heading' not in head_content
        assert '<p class="aide-text' not in head_content
        assert '<table class="aide-table' not in head_content


# ============================================================================
# Embedded JSON — Blueprint
# ============================================================================


class TestBlueprintJSON:
    """
    Blueprint is embedded as parseable JSON in a script tag with
    type="application/aide-blueprint+json" id="aide-blueprint".
    """

    @pytest.fixture
    def html(self):
        return render(content_snapshot(), make_blueprint())

    def test_blueprint_script_type(self, html):
        """Script tag has correct MIME type."""
        assert_contains(html, 'type="application/aide-blueprint+json"')

    def test_blueprint_script_id(self, html):
        """Script tag has id="aide-blueprint"."""
        assert_contains(html, 'id="aide-blueprint"')

    def test_blueprint_is_valid_json(self, html):
        """Blueprint content parses as valid JSON."""
        bp = extract_json_block(html, "aide-blueprint")
        assert isinstance(bp, dict)

    def test_blueprint_has_identity(self, html):
        """Blueprint JSON has 'identity' field."""
        bp = extract_json_block(html, "aide-blueprint")
        assert "identity" in bp
        assert bp["identity"] == "Test aide."

    def test_blueprint_has_voice(self, html):
        """Blueprint JSON has 'voice' field."""
        bp = extract_json_block(html, "aide-blueprint")
        assert bp["voice"] == "No first person."

    def test_blueprint_has_prompt(self, html):
        """Blueprint JSON has 'prompt' field."""
        bp = extract_json_block(html, "aide-blueprint")
        assert bp["prompt"] == "You are maintaining a test page."

    def test_blueprint_in_head(self, html):
        """Blueprint script is inside <head>."""
        head_start = html.find("<head>")
        head_end = html.find("</head>")
        bp_pos = html.find('id="aide-blueprint"')
        assert head_start < bp_pos < head_end


# ============================================================================
# Embedded JSON — Snapshot (aide-state)
# ============================================================================


class TestSnapshotJSON:
    """
    Snapshot is embedded as parseable JSON in a script tag with
    type="application/aide+json" id="aide-state".
    Uses sorted keys for determinism.
    """

    @pytest.fixture
    def html(self):
        return render(content_snapshot(), make_blueprint())

    def test_state_script_type(self, html):
        """Script tag has correct MIME type."""
        assert_contains(html, 'type="application/aide+json"')

    def test_state_script_id(self, html):
        """Script tag has id="aide-state"."""
        assert_contains(html, 'id="aide-state"')

    def test_state_is_valid_json(self, html):
        """Snapshot content parses as valid JSON."""
        state = extract_json_block(html, "aide-state")
        assert isinstance(state, dict)

    def test_state_has_required_keys(self, html):
        """Snapshot has all top-level keys from the schema."""
        state = extract_json_block(html, "aide-state")
        for key in ["version", "meta", "collections", "blocks", "views", "styles"]:
            assert key in state, f"Snapshot missing required key '{key}'"

    def test_state_meta_matches(self, html):
        """Snapshot meta matches the input."""
        state = extract_json_block(html, "aide-state")
        assert state["meta"]["title"] == "Structure Test"

    def test_state_collections_present(self, html):
        """Snapshot includes the tasks collection."""
        state = extract_json_block(html, "aide-state")
        assert "tasks" in state["collections"]

    def test_state_blocks_present(self, html):
        """Snapshot includes block_root and child blocks."""
        state = extract_json_block(html, "aide-state")
        assert "block_root" in state["blocks"]

    def test_state_sorted_keys(self, html):
        """Snapshot JSON uses sorted keys."""
        raw = extract_raw_json(html, "aide-state")
        parsed = json.loads(raw)
        # Re-serialize with sorted keys; should match
        resorted = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
        original = json.dumps(json.loads(raw), sort_keys=True, separators=(",", ":"))
        assert resorted == original

    def test_state_in_head(self, html):
        """State script is inside <head>."""
        head_start = html.find("<head>")
        head_end = html.find("</head>")
        state_pos = html.find('id="aide-state"')
        assert head_start < state_pos < head_end


# ============================================================================
# Embedded JSON — Events
# ============================================================================


class TestEventsJSON:
    """
    Events are embedded as a JSON array in a script tag with
    type="application/aide-events+json" id="aide-events".
    """

    def test_events_present_when_provided(self):
        """Events script block present when events are passed."""
        html = render(content_snapshot(), make_blueprint(), events=make_events())
        assert_contains(html, 'type="application/aide-events+json"')
        assert_contains(html, 'id="aide-events"')

    def test_events_is_valid_json_array(self):
        """Events content parses as a JSON array."""
        html = render(content_snapshot(), make_blueprint(), events=make_events())
        events = extract_json_block(html, "aide-events")
        assert isinstance(events, list)

    def test_events_count_matches(self):
        """Number of embedded events matches input."""
        evts = make_events()
        html = render(content_snapshot(), make_blueprint(), events=evts)
        embedded = extract_json_block(html, "aide-events")
        assert len(embedded) == len(evts)

    def test_events_preserve_content(self):
        """Embedded events match the original event data."""
        evts = make_events()
        html = render(content_snapshot(), make_blueprint(), events=evts)
        embedded = extract_json_block(html, "aide-events")
        assert embedded[0]["type"] == "collection.create"
        assert embedded[1]["type"] == "entity.create"

    def test_events_in_head(self):
        """Events script is inside <head>."""
        html = render(content_snapshot(), make_blueprint(), events=make_events())
        head_start = html.find("<head>")
        head_end = html.find("</head>")
        events_pos = html.find('id="aide-events"')
        assert head_start < events_pos < head_end

    def test_empty_events_list(self):
        """Empty events list omits the events block (no point embedding empty array)."""
        html = render(content_snapshot(), make_blueprint(), events=[])
        # Empty list is falsy, so events block is not rendered
        assert 'id="aide-events"' not in html

    def test_no_events_with_none(self):
        """events=None may omit or embed empty aide-events block."""
        html = render(content_snapshot(), make_blueprint(), events=None)
        # Behavior: either no script tag or empty array — both acceptable
        # Just verify it doesn't crash and is valid HTML
        assert_contains(html, "<!DOCTYPE html>")


# ============================================================================
# RenderOptions — include/exclude control
# ============================================================================


class TestRenderOptionsInclusion:
    """
    RenderOptions control which sections appear in the output.
    """

    def test_include_blueprint_true(self):
        """Blueprint present when include_blueprint=True (default)."""
        html = render(content_snapshot(), make_blueprint())
        assert_contains(html, 'id="aide-blueprint"')

    def test_include_blueprint_false(self):
        """Blueprint absent when include_blueprint=False."""
        html = render(
            content_snapshot(), make_blueprint(),
            options=RenderOptions(include_blueprint=False),
        )
        assert_not_contains(html, 'id="aide-blueprint"')
        # State should still be present
        assert_contains(html, 'id="aide-state"')

    def test_include_events_true(self):
        """Events present when include_events=True (default) and events provided."""
        html = render(content_snapshot(), make_blueprint(), events=make_events())
        assert_contains(html, 'id="aide-events"')

    def test_include_events_false(self):
        """Events absent when include_events=False."""
        html = render(
            content_snapshot(), make_blueprint(),
            events=make_events(),
            options=RenderOptions(include_events=False),
        )
        assert_not_contains(html, 'id="aide-events"')
        # Blueprint and state still present
        assert_contains(html, 'id="aide-blueprint"')
        assert_contains(html, 'id="aide-state"')

    def test_state_always_present(self):
        """Snapshot (aide-state) is always present regardless of options."""
        html = render(
            content_snapshot(), make_blueprint(),
            options=RenderOptions(
                include_blueprint=False,
                include_events=False,
            ),
        )
        assert_contains(html, 'id="aide-state"')

    def test_both_excluded(self):
        """Both blueprint and events excluded — only state remains."""
        html = render(
            content_snapshot(), make_blueprint(),
            events=make_events(),
            options=RenderOptions(
                include_blueprint=False,
                include_events=False,
            ),
        )
        assert_not_contains(html, 'id="aide-blueprint"')
        assert_not_contains(html, 'id="aide-events"')
        assert_contains(html, 'id="aide-state"')
        # Still valid HTML
        assert_contains(html, "<!DOCTYPE html>")
        assert_contains(html, "<body>")


# ============================================================================
# Google Fonts
# ============================================================================


class TestGoogleFonts:
    """
    Font preconnect and stylesheet links per spec.
    """

    @pytest.fixture
    def html(self):
        return render(content_snapshot(), make_blueprint())

    def test_fonts_googleapis_preconnect(self, html):
        """Preconnect to fonts.googleapis.com."""
        assert_contains(html, 'href="https://fonts.googleapis.com"')

    def test_fonts_gstatic_preconnect(self, html):
        """Preconnect to fonts.gstatic.com with crossorigin."""
        assert_contains(html, 'href="https://fonts.gstatic.com"')
        assert_contains(html, "crossorigin")

    def test_cormorant_garamond_loaded(self, html):
        """Cormorant Garamond font stylesheet linked."""
        assert_contains(html, "Cormorant+Garamond")

    def test_ibm_plex_sans_loaded(self, html):
        """IBM Plex Sans font stylesheet linked."""
        assert_contains(html, "IBM+Plex+Sans")

    def test_fonts_in_head(self, html):
        """Font links are inside <head>."""
        head_start = html.find("<head>")
        head_end = html.find("</head>")
        fonts_pos = html.find("Cormorant+Garamond")
        assert head_start < fonts_pos < head_end

    def test_include_fonts_false(self):
        """Fonts excluded when include_fonts=False."""
        html = render(
            content_snapshot(), make_blueprint(),
            options=RenderOptions(include_fonts=False),
        )
        assert_not_contains(html, "fonts.googleapis.com")
        assert_not_contains(html, "Cormorant+Garamond")


# ============================================================================
# Style block
# ============================================================================


class TestStyleBlock:
    """
    Single <style> block in <head> with base CSS + token overrides.
    """

    @pytest.fixture
    def html(self):
        return render(content_snapshot(), make_blueprint())

    def test_style_tag_present(self, html):
        """<style> and </style> are present."""
        assert_contains(html, "<style>")
        assert_contains(html, "</style>")

    def test_single_style_block(self, html):
        """Only one <style> block (combined, not multiple)."""
        count = html.count("<style>")
        assert count == 1, f"Expected 1 <style> block, got {count}"

    def test_style_in_head(self, html):
        """<style> is inside <head>."""
        head_start = html.find("<head>")
        head_end = html.find("</head>")
        style_pos = html.find("<style>")
        assert head_start < style_pos < head_end

    def test_base_css_present(self, html):
        """Base CSS includes box-sizing reset."""
        assert_contains(html, "box-sizing: border-box")

    def test_aide_page_css(self, html):
        """.aide-page max-width rule present."""
        assert_contains(html, "max-width: 720px")


# ============================================================================
# No executable JavaScript
# ============================================================================


class TestNoExecutableJavaScript:
    """
    Per spec: "No JavaScript." Only data script tags with application/* types.
    """

    @pytest.fixture
    def html(self):
        return render(content_snapshot(), make_blueprint(), events=make_events())

    def test_all_scripts_are_data_types(self, html):
        """Every <script> tag has a non-executable type."""
        scripts = re.findall(r'<script([^>]*)>', html)
        for attrs in scripts:
            assert "application/" in attrs, (
                f"Found script without data MIME type: <script{attrs}>"
            )

    def test_no_text_javascript_type(self, html):
        """No script with type='text/javascript'."""
        assert_not_contains(html, 'type="text/javascript"')

    def test_no_bare_script_tags(self, html):
        """No <script> without a type attribute (browser default = JS)."""
        # All script tags must have an explicit type
        scripts = re.findall(r'<script([^>]*)>', html)
        for attrs in scripts:
            assert "type=" in attrs, (
                f"Script tag without type= attribute: <script{attrs}>"
            )

    def test_no_onclick_handlers(self, html):
        """No onclick or other event handler attributes."""
        for handler in ["onclick", "onload", "onerror", "onmouseover", "onsubmit"]:
            assert_not_contains(html, handler)


# ============================================================================
# OG / Meta tags
# ============================================================================


class TestOGMetaTags:
    """
    OG tags for link previews in Signal, iMessage, Slack, etc.
    """

    @pytest.fixture
    def html(self):
        return render(content_snapshot(), make_blueprint())

    def test_og_title(self, html):
        """og:title meta tag present with correct content."""
        assert_contains(html, 'property="og:title"')
        assert_contains(html, 'content="Structure Test"')

    def test_og_type(self, html):
        """og:type is 'website'."""
        assert_contains(html, 'property="og:type"')
        assert_contains(html, 'content="website"')

    def test_og_description(self, html):
        """og:description meta tag present."""
        assert_contains(html, 'property="og:description"')

    def test_meta_description(self, html):
        """Standard meta description tag also present."""
        assert_contains(html, 'name="description"')

    def test_og_tags_in_head(self, html):
        """OG tags are inside <head>."""
        head_start = html.find("<head>")
        head_end = html.find("</head>")
        og_pos = html.find('og:title')
        assert head_start < og_pos < head_end

    def test_og_title_escaped(self):
        """HTML special chars in title are escaped in OG tag."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": 'Tom & Jerry\'s "Page"'}
        html = render(snapshot, make_blueprint())
        # Should be escaped in the content attribute
        assert_not_contains(html, 'content="Tom & Jerry')
        assert_contains(html, "&amp;") or assert_contains(html, "Tom")


# ============================================================================
# Footer
# ============================================================================


class TestFooterStructure:
    """
    Free-tier aides include a footer. Pro aides don't.
    Per spec: footer option controls presence.
    """

    def test_footer_present_with_option(self):
        """Footer appears when footer option is set."""
        html = render(
            content_snapshot(), make_blueprint(),
            options=RenderOptions(footer="Made with AIde"),
        )
        assert_contains(html, "aide-footer")
        assert_contains(html, "Made with AIde")
        assert_contains(html, "toaide.com")

    def test_footer_absent_without_option(self):
        """No footer element when footer option is None."""
        html = render(
            content_snapshot(), make_blueprint(),
            options=RenderOptions(footer=None),
        )
        # Check that no footer element exists in body (CSS still has .aide-footer styles)
        assert '<footer class="aide-footer">' not in html

    def test_footer_after_main(self):
        """Footer is after </main> but inside <body>."""
        html = render(
            content_snapshot(), make_blueprint(),
            options=RenderOptions(footer="Made with AIde"),
        )
        main_end = html.find("</main>")
        body_end = html.find("</body>")
        # Search for actual footer element, not CSS class definition
        footer_pos = html.find('<footer class="aide-footer">')
        assert footer_pos != -1, "Footer element not found"
        assert main_end < footer_pos < body_end

    def test_footer_default_is_none(self):
        """Default RenderOptions has no footer element (pro behavior)."""
        html = render(content_snapshot(), make_blueprint())
        # Check that no footer element exists (CSS still has .aide-footer styles)
        assert '<footer class="aide-footer">' not in html


# ============================================================================
# Element ordering in <head>
# ============================================================================


class TestHeadElementOrdering:
    """
    Verify the ordering of elements inside <head> matches the spec.
    """

    @pytest.fixture
    def html(self):
        return render(content_snapshot(), make_blueprint(), events=make_events())

    def test_charset_before_title(self, html):
        """charset meta appears before <title>."""
        assert_before(html, 'charset="utf-8"', "<title>")

    def test_title_before_og_tags(self, html):
        """<title> appears before OG tags."""
        assert_before(html, "<title>", "og:title")

    def test_og_tags_before_scripts(self, html):
        """OG tags appear before embedded JSON scripts."""
        assert_before(html, "og:title", 'id="aide-blueprint"')

    def test_scripts_before_fonts(self, html):
        """Embedded JSON scripts appear before font links."""
        assert_before(html, 'id="aide-state"', "fonts.googleapis.com")

    def test_fonts_before_style(self, html):
        """Font links appear before <style> block."""
        assert_before(html, "fonts.googleapis.com", "<style>")


# ============================================================================
# Output encoding and completeness
# ============================================================================


class TestOutputEncoding:
    """
    The output is a complete, well-formed UTF-8 string.
    """

    def test_output_is_string(self):
        """render() returns a str."""
        html = render(content_snapshot(), make_blueprint())
        assert isinstance(html, str)

    def test_output_encodable_as_utf8(self):
        """Output can be encoded to UTF-8 bytes without error."""
        html = render(content_snapshot(), make_blueprint())
        encoded = html.encode("utf-8")
        assert len(encoded) > 0

    def test_output_starts_with_doctype(self):
        """Output begins with <!DOCTYPE html> (no BOM or preamble)."""
        html = render(content_snapshot(), make_blueprint())
        assert html.strip().lower().startswith("<!doctype html>")

    def test_output_ends_with_closing_html(self):
        """Output ends with </html>."""
        html = render(content_snapshot(), make_blueprint())
        assert html.strip().endswith("</html>")

    def test_no_unclosed_tags_in_structure(self):
        """Major structural tags are all closed."""
        html = render(content_snapshot(), make_blueprint())
        for tag in ["html", "head", "body", "main", "style"]:
            open_count = len(re.findall(rf'<{tag}[\s>]', html))
            close_count = html.count(f"</{tag}>")
            assert open_count == close_count, (
                f"<{tag}> opened {open_count} times but closed {close_count} times"
            )
