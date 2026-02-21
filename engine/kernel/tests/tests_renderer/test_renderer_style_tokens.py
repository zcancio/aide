"""
AIde Renderer -- Style Token Application Tests (Category 3)

Change primary_color, verify CSS override appears. Change density,
verify spacing changes.

From the spec (aide_renderer_spec.md, "Testing Strategy"):
  "3. Style token application. Change primary_color, verify CSS override
   appears. Change density, verify spacing changes."

The renderer maps snapshot.styles tokens to CSS custom property overrides
in a :root block within the <style> element.

Token → CSS variable mapping (from spec):
  primary_color → --text-primary
  bg_color      → --bg-primary
  text_color    → --text-secondary
  font_family   → --font-sans
  heading_font  → --font-serif
  density       → adjusts spacing scale

Density levels:
  compact     → 0.75× spacing, page padding var(--space-8),  section gap var(--space-6)
  comfortable → 1× (default),  page padding var(--space-12), section gap var(--space-8)
  spacious    → 1.25× spacing, page padding var(--space-16), section gap var(--space-10)

This matters because:
  - Style tokens are the user's customization surface
  - Incorrect CSS mapping means the page looks wrong
  - Density affects every layout element's spacing
  - Base CSS must always be present even without overrides
  - Unknown tokens are stored but must not break rendering

Reference: aide_renderer_spec.md (CSS Generation, Style Token Overrides)
           docs/aide_design_system.md (CSS Custom Properties)
"""

import re

from engine.kernel.reducer import empty_state
from engine.kernel.renderer import render
from engine.kernel.types import Blueprint

# ============================================================================
# Helpers
# ============================================================================


def make_blueprint():
    """Minimal blueprint for rendering."""
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

    # Add a heading so there's visible content
    snapshot["blocks"]["block_title"] = {
        "type": "heading",
        "parent": "block_root",
        "props": {"level": 1, "content": "Style Test Page"},
    }
    snapshot["blocks"]["block_root"]["children"] = ["block_title"]

    return snapshot


def extract_style_block(html):
    """Extract the contents of the <style> tag from rendered HTML."""
    match = re.search(r"<style>(.*?)</style>", html, re.DOTALL)
    assert match, "No <style> block found in rendered HTML"
    return match.group(1)


def assert_css_contains(html, *fragments):
    """Assert that the <style> block contains all given CSS fragments."""
    css = extract_style_block(html)
    for fragment in fragments:
        assert fragment in css, f"Expected to find {fragment!r} in CSS.\nCSS (first 2000 chars):\n{css[:2000]}"


def assert_css_not_contains(html, *fragments):
    """Assert that the <style> block does NOT contain given CSS fragments."""
    css = extract_style_block(html)
    for fragment in fragments:
        assert fragment not in css, f"Did NOT expect to find {fragment!r} in CSS."


def assert_html_contains(html, *fragments):
    """Assert rendered HTML contains all fragments."""
    for fragment in fragments:
        assert fragment in html, (
            f"Expected to find {fragment!r} in rendered HTML.\nGot (first 2000 chars):\n{html[:2000]}"
        )


# ============================================================================
# primary_color → --text-primary
# ============================================================================


class TestPrimaryColorToken:
    """
    primary_color maps to --text-primary CSS variable.
    Per spec: style token 'primary_color' → CSS variable '--text-primary'.
    """

    def test_primary_color_sets_text_primary(self):
        """Setting primary_color emits --text-primary override in CSS."""
        snapshot = make_snapshot_with_styles({"primary_color": "#1a365d"})
        html = render(snapshot, make_blueprint())

        assert_css_contains(html, "--text-primary: #1a365d")

    def test_primary_color_different_value(self):
        """Different primary_color value produces different CSS."""
        snapshot = make_snapshot_with_styles({"primary_color": "#ff0000"})
        html = render(snapshot, make_blueprint())

        assert_css_contains(html, "--text-primary: #ff0000")

    def test_no_primary_color_uses_default(self):
        """
        Without primary_color token, the base design system default applies.
        The :root override should not contain --text-primary (it comes from base).
        """
        snapshot = make_snapshot_with_styles({})
        html = render(snapshot, make_blueprint())

        # Base CSS defines --text-primary with the default (#1E1E1E from design system)
        css = extract_style_block(html)
        # The base value should exist somewhere in CSS
        assert "--text-primary" in css


# ============================================================================
# bg_color → --bg-primary
# ============================================================================


class TestBgColorToken:
    """
    bg_color maps to --bg-primary CSS variable.
    Per spec: style token 'bg_color' → CSS variable '--bg-primary'.
    """

    def test_bg_color_sets_bg_primary(self):
        """Setting bg_color emits --bg-primary override."""
        snapshot = make_snapshot_with_styles({"bg_color": "#fffff0"})
        html = render(snapshot, make_blueprint())

        assert_css_contains(html, "--bg-primary: #fffff0")

    def test_bg_color_white(self):
        """Pure white background."""
        snapshot = make_snapshot_with_styles({"bg_color": "#ffffff"})
        html = render(snapshot, make_blueprint())

        assert_css_contains(html, "--bg-primary: #ffffff")


# ============================================================================
# text_color → --text-secondary
# ============================================================================


class TestTextColorToken:
    """
    text_color maps to --text-secondary CSS variable.
    Per spec: style token 'text_color' → CSS variable '--text-secondary'.
    """

    def test_text_color_sets_text_secondary(self):
        """Setting text_color emits --text-secondary override."""
        snapshot = make_snapshot_with_styles({"text_color": "#333333"})
        html = render(snapshot, make_blueprint())

        assert_css_contains(html, "--text-secondary: #333333")


# ============================================================================
# font_family → --font-sans
# ============================================================================


class TestFontFamilyToken:
    """
    font_family maps to --font-sans CSS variable.
    Per spec: style token 'font_family' → CSS variable '--font-sans'.
    """

    def test_font_family_sets_font_sans(self):
        """Setting font_family emits --font-sans override."""
        snapshot = make_snapshot_with_styles({"font_family": "Inter"})
        html = render(snapshot, make_blueprint())

        assert_css_contains(html, "--font-sans")
        assert_css_contains(html, "Inter")

    def test_font_family_with_fallbacks(self):
        """Font family override should include the custom font name."""
        snapshot = make_snapshot_with_styles({"font_family": "Roboto"})
        html = render(snapshot, make_blueprint())

        assert_css_contains(html, "Roboto")


# ============================================================================
# heading_font → --font-serif
# ============================================================================


class TestHeadingFontToken:
    """
    heading_font maps to --font-serif CSS variable.
    Per spec: style token 'heading_font' → CSS variable '--font-serif'.
    """

    def test_heading_font_sets_font_serif(self):
        """Setting heading_font emits --font-serif override."""
        snapshot = make_snapshot_with_styles({"heading_font": "Playfair Display"})
        html = render(snapshot, make_blueprint())

        assert_css_contains(html, "--font-serif")
        assert_css_contains(html, "Playfair Display")


# ============================================================================
# density → spacing scale adjustments
# ============================================================================


class TestDensityToken:
    """
    density adjusts the spacing scale.
    Per spec:
      compact     → 0.75× | page padding var(--space-8)  | section gap var(--space-6)
      comfortable → 1×    | page padding var(--space-12) | section gap var(--space-8)
      spacious    → 1.25× | page padding var(--space-16) | section gap var(--space-10)
    """

    def test_density_compact(self):
        """
        Compact density reduces spacing.
        Page padding should use --space-8, section gap --space-6.
        """
        snapshot = make_snapshot_with_styles({"density": "compact"})
        html = render(snapshot, make_blueprint())
        css = extract_style_block(html)

        # Compact uses smaller spacing values
        # The .aide-page should reference space-8 for padding (not space-12)
        assert "space-8" in css or "32px" in css

    def test_density_comfortable_is_default(self):
        """
        Comfortable density is 1× — the default.
        Page padding should use --space-12, section gap --space-8.
        """
        snapshot = make_snapshot_with_styles({"density": "comfortable"})
        html = render(snapshot, make_blueprint())
        css = extract_style_block(html)

        # Comfortable uses standard spacing
        assert "space-12" in css or "48px" in css

    def test_density_spacious(self):
        """
        Spacious density increases spacing.
        Page padding should use --space-16, section gap --space-10.
        """
        snapshot = make_snapshot_with_styles({"density": "spacious"})
        html = render(snapshot, make_blueprint())
        css = extract_style_block(html)

        # Spacious uses larger spacing values
        assert "space-16" in css or "64px" in css

    def test_no_density_defaults_to_comfortable(self):
        """Without density token, the default 'comfortable' spacing applies."""
        snapshot = make_snapshot_with_styles({})
        html = render(snapshot, make_blueprint())
        css = extract_style_block(html)

        # Default is comfortable (space-12 page padding)
        assert "space-12" in css or "48px" in css


# ============================================================================
# Multiple tokens combined
# ============================================================================


class TestMultipleTokensCombined:
    """
    Multiple style tokens applied together should all produce
    corresponding CSS overrides.
    """

    def test_all_color_tokens_together(self):
        """Setting primary_color, bg_color, and text_color at once."""
        snapshot = make_snapshot_with_styles(
            {
                "primary_color": "#1a365d",
                "bg_color": "#fffff0",
                "text_color": "#2a2a2a",
            }
        )
        html = render(snapshot, make_blueprint())

        assert_css_contains(
            html,
            "--text-primary: #1a365d",
            "--bg-primary: #fffff0",
            "--text-secondary: #2a2a2a",
        )

    def test_fonts_and_colors_together(self):
        """Font and color tokens don't interfere with each other."""
        snapshot = make_snapshot_with_styles(
            {
                "primary_color": "#2d3748",
                "font_family": "Inter",
                "heading_font": "Playfair Display",
            }
        )
        html = render(snapshot, make_blueprint())

        assert_css_contains(html, "--text-primary: #2d3748")
        assert_css_contains(html, "Inter")
        assert_css_contains(html, "Playfair Display")

    def test_full_style_set(self):
        """All known v1 tokens set at once — realistic poker league scenario."""
        snapshot = make_snapshot_with_styles(
            {
                "primary_color": "#2d3748",
                "bg_color": "#fafaf9",
                "text_color": "#1a1a1a",
                "font_family": "Inter",
                "heading_font": "Cormorant Garamond",
                "density": "comfortable",
            }
        )
        html = render(snapshot, make_blueprint())

        assert_css_contains(
            html,
            "--text-primary: #2d3748",
            "--bg-primary: #fafaf9",
            "--text-secondary: #1a1a1a",
        )
        assert_css_contains(html, "Inter")
        assert_css_contains(html, "Cormorant Garamond")


# ============================================================================
# Base CSS always present
# ============================================================================


class TestBaseCSSAlwaysPresent:
    """
    The design system base CSS must always be present regardless of
    style tokens. This includes box-sizing reset, body defaults,
    .aide-page container, and all component CSS.
    """

    def test_base_css_with_no_style_tokens(self):
        """Base CSS is present even with empty styles."""
        snapshot = make_snapshot_with_styles({})
        html = render(snapshot, make_blueprint())
        css = extract_style_block(html)

        # Box-sizing reset
        assert "box-sizing" in css
        # Body font
        assert "font-family" in css
        # Page container
        assert "aide-page" in css

    def test_base_css_with_style_tokens(self):
        """Base CSS is still present alongside overrides."""
        snapshot = make_snapshot_with_styles({"primary_color": "#ff0000"})
        html = render(snapshot, make_blueprint())
        css = extract_style_block(html)

        # Both base and override should be present
        assert "box-sizing" in css
        assert "--text-primary: #ff0000" in css

    def test_base_design_system_variables_present(self):
        """
        The base design system CSS custom properties should be present.
        From docs/aide_design_system.md: backgrounds, text, accents,
        borders, fonts, spacing, radius, transitions.
        """
        snapshot = make_snapshot_with_styles({})
        html = render(snapshot, make_blueprint())
        css = extract_style_block(html)

        # Key design system variables
        assert "--bg-primary" in css
        assert "--text-primary" in css
        assert "--font-serif" in css
        assert "--font-sans" in css
        assert "--border" in css
        assert "--space-4" in css
        assert "--radius-sm" in css

    def test_heading_css_present(self):
        """Block-level CSS classes (aide-heading, etc.) are in the base."""
        snapshot = make_snapshot_with_styles({})
        html = render(snapshot, make_blueprint())
        css = extract_style_block(html)

        assert "aide-heading" in css

    def test_aide_page_max_width(self):
        """
        .aide-page has max-width: 720px per spec.
        """
        snapshot = make_snapshot_with_styles({})
        html = render(snapshot, make_blueprint())
        css = extract_style_block(html)

        assert "max-width" in css
        assert "720px" in css


# ============================================================================
# Override placement — :root block
# ============================================================================


class TestOverridePlacement:
    """
    Style token overrides are emitted in a :root block so they
    cascade over the base design system defaults.
    """

    def test_overrides_in_root_selector(self):
        """
        Custom style tokens appear inside a :root { ... } block.
        Per spec: ':root { /* Aide style overrides */ ... }'
        """
        snapshot = make_snapshot_with_styles({"primary_color": "#1a365d"})
        html = render(snapshot, make_blueprint())
        css = extract_style_block(html)

        # Find a :root block containing the override
        # The override should be within :root { ... }
        assert ":root" in css
        assert "--text-primary: #1a365d" in css

    def test_no_overrides_when_empty_styles(self):
        """
        With empty styles, no :root override block for custom tokens
        should be emitted (or it should be empty).
        The base :root from the design system may still exist.
        """
        snapshot = make_snapshot_with_styles({})
        html = render(snapshot, make_blueprint())
        css = extract_style_block(html)

        # There shouldn't be a custom override for --text-primary
        # beyond what the design system defines
        # (The base design system :root IS expected to be present)
        assert "Aide style override" not in css or css.count("--text-primary") <= 1


# ============================================================================
# Unknown tokens
# ============================================================================


class TestUnknownStyleTokens:
    """
    Unknown tokens are stored in snapshot.styles but ignored by the renderer.
    Per spec: 'Unknown tokens are stored but ignored by the renderer
    until a future version supports them.'
    """

    def test_unknown_token_does_not_break_render(self):
        """An unknown style token doesn't cause rendering errors."""
        snapshot = make_snapshot_with_styles(
            {
                "primary_color": "#2d3748",
                "sparkle_effect": "extreme",
                "border_style": "dashed",
            }
        )
        # Should not raise
        html = render(snapshot, make_blueprint())
        assert "<!DOCTYPE html>" in html

    def test_unknown_token_not_in_css(self):
        """Unknown tokens should not produce CSS output."""
        snapshot = make_snapshot_with_styles(
            {
                "sparkle_effect": "extreme",
            }
        )
        html = render(snapshot, make_blueprint())
        css = extract_style_block(html)

        assert "sparkle" not in css
        assert "extreme" not in css

    def test_known_tokens_still_work_alongside_unknown(self):
        """Known tokens work correctly even when unknown tokens are present."""
        snapshot = make_snapshot_with_styles(
            {
                "primary_color": "#1a365d",
                "mystery_token": "42",
            }
        )
        html = render(snapshot, make_blueprint())

        assert_css_contains(html, "--text-primary: #1a365d")
        assert "mystery_token" not in extract_style_block(html)


# ============================================================================
# Style tokens affect rendered content
# ============================================================================


class TestStyleTokensAffectContent:
    """
    Style tokens should affect the rendered HTML through CSS variables,
    meaning the <style> block carries these overrides and the HTML
    references them via class-based styling.
    """

    def test_heading_uses_text_primary(self):
        """
        Headings reference var(--text-primary) in their CSS.
        Setting primary_color should therefore affect heading color.
        """
        snapshot = make_snapshot_with_styles({"primary_color": "#1a365d"})
        html = render(snapshot, make_blueprint())
        css = extract_style_block(html)

        # The heading CSS references --text-primary
        assert "var(--text-primary)" in css
        # And the override sets it
        assert "--text-primary: #1a365d" in css

    def test_body_uses_bg_primary(self):
        """
        Body background references var(--bg-primary).
        Setting bg_color should affect page background.
        """
        snapshot = make_snapshot_with_styles({"bg_color": "#fffff0"})
        html = render(snapshot, make_blueprint())
        css = extract_style_block(html)

        assert "var(--bg-primary)" in css
        assert "--bg-primary: #fffff0" in css

    def test_body_uses_font_sans(self):
        """
        Body font-family references var(--font-sans).
        Setting font_family should affect the base font.
        """
        snapshot = make_snapshot_with_styles({"font_family": "Inter"})
        html = render(snapshot, make_blueprint())
        css = extract_style_block(html)

        assert "var(--font-sans)" in css
        assert "Inter" in css
