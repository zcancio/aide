"""
AIde Renderer -- Style Token Application Tests (v3 Unified Entity Model)

Change style tokens, verify CSS custom property overrides appear.

Token → CSS variable mapping (v3 renderer):
  primary_color → --accent
  bg_color      → --bg-primary
  text_color    → --text-primary
  font_family   → --font-body
  heading_font  → --font-heading

Reference: aide_renderer_spec.md (CSS Generation, Style Token Overrides)
"""

import re

from engine.kernel.reducer import empty_state
from engine.kernel.renderer import render
from engine.kernel.types import Blueprint


def make_blueprint():
    return Blueprint(
        identity="Test aide.",
        voice="No first person.",
        prompt="Test prompt.",
    )


def make_snapshot_with_styles(styles=None):
    """Build a minimal snapshot with optional style tokens and a heading block."""
    snapshot = empty_state()
    snapshot["meta"] = {"title": "Style Test"}
    snapshot["styles"] = styles or {}
    snapshot["blocks"]["block_title"] = {
        "type": "heading",
        "level": 1,
        "text": "Style Test Page",
    }
    snapshot["blocks"]["block_root"]["children"] = ["block_title"]
    return snapshot


def extract_style_block(html):
    """Extract the contents of the <style> tag from rendered HTML."""
    match = re.search(r"<style>(.*?)</style>", html, re.DOTALL)
    assert match, "No <style> block found in rendered HTML"
    return match.group(1)


def assert_css_contains(html, *fragments):
    css = extract_style_block(html)
    for fragment in fragments:
        assert fragment in css, f"Expected to find {fragment!r} in CSS.\nCSS:\n{css[:2000]}"


def assert_css_not_contains(html, *fragments):
    css = extract_style_block(html)
    for fragment in fragments:
        assert fragment not in css, f"Did NOT expect to find {fragment!r} in CSS."


def assert_html_contains(html, *fragments):
    for fragment in fragments:
        assert fragment in html, f"Expected to find {fragment!r} in HTML."


# ============================================================================
# primary_color → --accent
# ============================================================================


class TestPrimaryColorToken:
    """primary_color maps to --accent CSS variable."""

    def test_primary_color_sets_accent(self):
        """primary_color sets --accent CSS variable."""
        html = render(make_snapshot_with_styles({"primary_color": "#1a365d"}), make_blueprint())
        assert_css_contains(html, "--accent: #1a365d")

    def test_primary_color_different_value(self):
        """Different primary_color value sets different --accent."""
        html = render(make_snapshot_with_styles({"primary_color": "#ff0000"}), make_blueprint())
        assert_css_contains(html, "--accent: #ff0000")

    def test_default_primary_color(self):
        """Without primary_color, --accent has a default value."""
        html = render(make_snapshot_with_styles({}), make_blueprint())
        assert_css_contains(html, "--accent:")

    def test_primary_color_in_root_selector(self):
        """primary_color override is inside :root {}."""
        html = render(make_snapshot_with_styles({"primary_color": "#2d3748"}), make_blueprint())
        css = extract_style_block(html)
        root_start = css.find(":root")
        root_end = css.find("}", root_start)
        root_block = css[root_start:root_end]
        assert "--accent: #2d3748" in root_block


# ============================================================================
# bg_color → --bg-primary
# ============================================================================


class TestBgColorToken:
    """bg_color maps to --bg-primary CSS variable."""

    def test_bg_color_sets_bg_primary(self):
        html = render(make_snapshot_with_styles({"bg_color": "#f0f0f0"}), make_blueprint())
        assert_css_contains(html, "--bg-primary: #f0f0f0")

    def test_bg_color_white(self):
        html = render(make_snapshot_with_styles({"bg_color": "#ffffff"}), make_blueprint())
        assert_css_contains(html, "--bg-primary: #ffffff")

    def test_default_bg_color_present(self):
        html = render(make_snapshot_with_styles({}), make_blueprint())
        assert_css_contains(html, "--bg-primary:")


# ============================================================================
# text_color → --text-primary
# ============================================================================


class TestTextColorToken:
    """text_color maps to --text-primary CSS variable."""

    def test_text_color_sets_text_primary(self):
        html = render(make_snapshot_with_styles({"text_color": "#333333"}), make_blueprint())
        assert_css_contains(html, "--text-primary: #333333")

    def test_text_color_dark(self):
        html = render(make_snapshot_with_styles({"text_color": "#000000"}), make_blueprint())
        assert_css_contains(html, "--text-primary: #000000")

    def test_default_text_color_present(self):
        html = render(make_snapshot_with_styles({}), make_blueprint())
        assert_css_contains(html, "--text-primary:")


# ============================================================================
# font_family → --font-body
# ============================================================================


class TestFontFamilyToken:
    """font_family maps to --font-body CSS variable."""

    def test_font_family_sets_font_body(self):
        html = render(make_snapshot_with_styles({"font_family": "Inter, sans-serif"}), make_blueprint())
        assert_css_contains(html, "--font-body: Inter, sans-serif")

    def test_font_family_monospace(self):
        html = render(make_snapshot_with_styles({"font_family": "JetBrains Mono, monospace"}), make_blueprint())
        assert_css_contains(html, "--font-body: JetBrains Mono, monospace")

    def test_default_font_body_present(self):
        html = render(make_snapshot_with_styles({}), make_blueprint())
        assert_css_contains(html, "--font-body:")


# ============================================================================
# heading_font → --font-heading
# ============================================================================


class TestHeadingFontToken:
    """heading_font maps to --font-heading CSS variable."""

    def test_heading_font_sets_font_heading(self):
        html = render(make_snapshot_with_styles({"heading_font": "Georgia, serif"}), make_blueprint())
        assert_css_contains(html, "--font-heading: Georgia, serif")

    def test_heading_font_sans(self):
        html = render(make_snapshot_with_styles({"heading_font": "Inter, sans-serif"}), make_blueprint())
        assert_css_contains(html, "--font-heading: Inter, sans-serif")

    def test_default_font_heading_present(self):
        html = render(make_snapshot_with_styles({}), make_blueprint())
        assert_css_contains(html, "--font-heading:")


# ============================================================================
# Multiple tokens combined
# ============================================================================


class TestMultipleTokensCombined:
    """Multiple style tokens can be set simultaneously."""

    def test_all_color_tokens_together(self):
        html = render(
            make_snapshot_with_styles({
                "primary_color": "#1a365d",
                "bg_color": "#f7f7f7",
                "text_color": "#222222",
            }),
            make_blueprint(),
        )
        assert_css_contains(html, "--accent: #1a365d")
        assert_css_contains(html, "--bg-primary: #f7f7f7")
        assert_css_contains(html, "--text-primary: #222222")

    def test_fonts_and_colors_together(self):
        html = render(
            make_snapshot_with_styles({
                "primary_color": "#2d3748",
                "font_family": "IBM Plex Sans, sans-serif",
                "heading_font": "Cormorant Garamond, serif",
            }),
            make_blueprint(),
        )
        assert_css_contains(html, "--accent: #2d3748")
        assert_css_contains(html, "--font-body: IBM Plex Sans, sans-serif")
        assert_css_contains(html, "--font-heading: Cormorant Garamond, serif")

    def test_full_style_set(self):
        html = render(
            make_snapshot_with_styles({
                "primary_color": "#2d3748",
                "bg_color": "#fafaf9",
                "text_color": "#1a1a1a",
                "font_family": "IBM Plex Sans, sans-serif",
                "heading_font": "Cormorant Garamond, serif",
            }),
            make_blueprint(),
        )
        assert_css_contains(html, "--accent: #2d3748")
        assert_css_contains(html, "--bg-primary: #fafaf9")
        assert_css_contains(html, "--text-primary: #1a1a1a")
        assert_css_contains(html, "--font-body: IBM Plex Sans, sans-serif")
        assert_css_contains(html, "--font-heading: Cormorant Garamond, serif")


# ============================================================================
# Base CSS always present
# ============================================================================


class TestBaseCSSAlwaysPresent:
    """Base CSS must always be present, even with no style tokens."""

    def test_base_css_without_tokens(self):
        """Empty styles still produce base CSS."""
        html = render(make_snapshot_with_styles({}), make_blueprint())
        assert_css_contains(html, ":root")
        assert_css_contains(html, "--font-body:")
        assert_css_contains(html, "--font-heading:")
        assert_css_contains(html, "--text-primary:")
        assert_css_contains(html, "--bg-primary:")

    def test_base_css_with_style_tokens(self):
        """Style tokens override specific variables, rest of base CSS unchanged."""
        html = render(make_snapshot_with_styles({"primary_color": "#ff0000"}), make_blueprint())
        assert_css_contains(html, "--accent: #ff0000")
        # Base CSS still present
        assert_css_contains(html, "box-sizing: border-box")
        assert_css_contains(html, ".aide-page")

    def test_body_element_css_present(self):
        """body element CSS always present."""
        html = render(make_snapshot_with_styles({}), make_blueprint())
        assert_css_contains(html, "body {")
        assert_css_contains(html, "font-family: var(--font-body)")

    def test_heading_css_present(self):
        """Heading element CSS is always present."""
        html = render(make_snapshot_with_styles({}), make_blueprint())
        assert_css_contains(html, "h1")
        assert_css_contains(html, "h2")
        assert_css_contains(html, "h3")

    def test_aide_page_class_present(self):
        """aide-page class CSS is always present."""
        html = render(make_snapshot_with_styles({}), make_blueprint())
        assert_css_contains(html, ".aide-page")

    def test_aide_empty_class_present(self):
        """aide-empty class CSS is always present."""
        html = render(make_snapshot_with_styles({}), make_blueprint())
        assert_css_contains(html, ".aide-empty")


# ============================================================================
# Override placement in :root
# ============================================================================


class TestOverridePlacement:
    """CSS overrides must be inside :root {}."""

    def test_overrides_in_root_selector(self):
        """All overrides are inside the :root selector."""
        html = render(make_snapshot_with_styles({"primary_color": "#1a365d"}), make_blueprint())
        css = extract_style_block(html)

        root_start = css.find(":root")
        assert root_start != -1, ":root not found in CSS"
        root_end = css.find("}", root_start)
        root_block = css[root_start:root_end]

        assert "--accent: #1a365d" in root_block

    def test_css_variables_inside_root(self):
        """CSS custom properties are in :root block."""
        html = render(make_snapshot_with_styles({"bg_color": "#eee"}), make_blueprint())
        css = extract_style_block(html)

        root_start = css.find(":root")
        root_end = css.find("}", root_start)
        root_block = css[root_start:root_end]

        assert "--bg-primary:" in root_block


# ============================================================================
# Unknown style tokens
# ============================================================================


class TestUnknownStyleTokens:
    """Unknown tokens are stored but must not break rendering."""

    def test_unknown_token_does_not_crash(self):
        """Unknown style token is silently ignored."""
        html = render(
            make_snapshot_with_styles({"unknown_property": "some_value"}),
            make_blueprint(),
        )
        # Should render without crashing
        assert "<!DOCTYPE html>" in html

    def test_known_tokens_still_work_alongside_unknown(self):
        """Known tokens still work when unknown tokens are present."""
        html = render(
            make_snapshot_with_styles({
                "primary_color": "#1a365d",
                "unknown_property": "some_value",
            }),
            make_blueprint(),
        )
        assert_css_contains(html, "--accent: #1a365d")

    def test_empty_styles_does_not_crash(self):
        """Empty styles dict renders without error."""
        html = render(make_snapshot_with_styles({}), make_blueprint())
        assert "<!DOCTYPE html>" in html


# ============================================================================
# CSS used by body element
# ============================================================================


class TestStyleTokensAffectContent:
    """Verify CSS variables are referenced in element rules."""

    def test_body_uses_font_body_variable(self):
        """body element references --font-body variable."""
        html = render(make_snapshot_with_styles({"font_family": "Inter"}), make_blueprint())
        assert_css_contains(html, "var(--font-body)")

    def test_body_uses_bg_primary(self):
        """body element references --bg-primary variable."""
        html = render(make_snapshot_with_styles({"bg_color": "#eee"}), make_blueprint())
        assert_css_contains(html, "var(--bg-primary)")

    def test_body_uses_text_primary(self):
        """body element references --text-primary variable."""
        html = render(make_snapshot_with_styles({"text_color": "#333"}), make_blueprint())
        assert_css_contains(html, "var(--text-primary)")

    def test_headings_use_font_heading(self):
        """Heading elements reference --font-heading variable."""
        html = render(make_snapshot_with_styles({"heading_font": "Georgia"}), make_blueprint())
        assert_css_contains(html, "var(--font-heading)")
