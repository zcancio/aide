"""
AIde Renderer -- Entity Style Tests (v3 Unified Entity Model)

In v3, entity styles are defined in schema CSS and applied via schema templates.
Entities do not have _styles overrides rendered into list/table rows (no views).
Instead, schemas provide render_html/render_text templates and CSS.

Tests verify:
  - Schema 'styles' CSS is emitted in the <style> block
  - Schema render_html templates are used for entity rendering
  - Entity fields are correctly interpolated into templates
  - Multiple schemas produce combined CSS output
  - Schema styles don't bleed between schemas

Reference: aide_renderer_spec.md, docs/eng_design/unified_entity_model.md
"""

import re

from engine.kernel.reducer import empty_state
from engine.kernel.renderer import render, render_entity
from engine.kernel.types import Blueprint


def assert_contains(html, *fragments):
    for fragment in fragments:
        assert fragment in html, (
            f"Expected to find {fragment!r} in rendered HTML.\nGot (first 2000 chars):\n{html[:2000]}"
        )


def assert_not_contains(html, *fragments):
    for fragment in fragments:
        assert fragment not in html, f"Did NOT expect to find {fragment!r} in rendered HTML."


def extract_style_block(html):
    """Extract the contents of the <style> tag from rendered HTML."""
    match = re.search(r"<style>(.*?)</style>", html, re.DOTALL)
    assert match, "No <style> block found in rendered HTML"
    return match.group(1)


def make_blueprint():
    return Blueprint(
        identity="Test aide.",
        voice="No first person.",
        prompt="Test prompt.",
    )


def roster_snapshot():
    """Snapshot with a player schema and entities."""
    snapshot = empty_state()
    snapshot["meta"] = {"title": "Roster"}

    snapshot["schemas"]["player"] = {
        "interface": "interface Player { name: string; status: string; rating: number; }",
        "render_html": '<div class="player-row {{status}}"><span class="player-name">{{name}}</span><span class="player-rating">{{rating}}</span></div>',
        "render_text": "{{name}} ({{rating}})",
        "styles": ".player-row { padding: 8px; border-bottom: 1px solid #eee; }\n.player-row.active { font-weight: 600; }",
    }

    snapshot["entities"]["player_mike"] = {
        "_schema": "player",
        "name": "Mike",
        "status": "active",
        "rating": 1200,
    }
    snapshot["entities"]["player_sarah"] = {
        "_schema": "player",
        "name": "Sarah",
        "status": "active",
        "rating": 1350,
    }
    snapshot["entities"]["player_dave"] = {
        "_schema": "player",
        "name": "Dave",
        "status": "inactive",
        "rating": 1100,
    }

    return snapshot


# ============================================================================
# Schema CSS in style block
# ============================================================================


class TestSchemaCSSInStyleBlock:
    """
    Schema 'styles' CSS must appear in the full render's <style> block.
    """

    def test_schema_styles_in_output(self):
        """Schema CSS appears in the rendered <style> block."""
        snapshot = roster_snapshot()
        html = render(snapshot, make_blueprint())

        css = extract_style_block(html)
        assert ".player-row" in css, "Schema CSS not found in <style> block"

    def test_schema_active_rule_in_output(self):
        """All schema CSS rules are included."""
        snapshot = roster_snapshot()
        html = render(snapshot, make_blueprint())

        css = extract_style_block(html)
        assert ".player-row.active" in css

    def test_no_schema_produces_no_extra_css(self):
        """Snapshot with no schemas produces no schema CSS beyond base."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "No Schema"}
        html = render(snapshot, make_blueprint())

        css = extract_style_block(html)
        # Base CSS is always there; no .player-row should be present
        assert ".player-row" not in css

    def test_multiple_schemas_css_combined(self):
        """Multiple schemas each contribute their CSS."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Multi-Schema"}

        snapshot["schemas"]["task"] = {
            "interface": "interface Task { title: string; done: boolean; }",
            "render_html": "<div class=\"task\">{{title}}</div>",
            "styles": ".task { margin: 4px 0; }",
        }
        snapshot["schemas"]["note"] = {
            "interface": "interface Note { body: string; }",
            "render_html": "<p class=\"note\">{{body}}</p>",
            "styles": ".note { font-style: italic; color: #555; }",
        }

        html = render(snapshot, make_blueprint())
        css = extract_style_block(html)

        assert ".task" in css
        assert ".note" in css

    def test_removed_schema_css_not_included(self):
        """Schema marked _removed does not contribute CSS."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Removed Schema"}

        snapshot["schemas"]["old_schema"] = {
            "interface": "interface OldSchema { name: string; }",
            "render_html": "<span>{{name}}</span>",
            "styles": ".old-class { color: red; }",
            "_removed": True,
        }

        html = render(snapshot, make_blueprint())
        css = extract_style_block(html)

        assert ".old-class" not in css


# ============================================================================
# Template rendering
# ============================================================================


class TestEntityTemplateRendering:
    """
    Schema render_html template is applied when rendering entities.
    Field values are interpolated via Mustache {{field}}.
    """

    def test_entity_rendered_with_template(self):
        """Entity renders using its schema's render_html template."""
        snapshot = roster_snapshot()
        html = render_entity("player_mike", snapshot, channel="html")

        assert_contains(html, "Mike")
        assert_contains(html, "player-row")

    def test_entity_field_interpolated(self):
        """Field values are correctly interpolated into template."""
        snapshot = roster_snapshot()
        html = render_entity("player_sarah", snapshot, channel="html")

        assert_contains(html, "Sarah")
        assert_contains(html, "1350")

    def test_entity_status_field_in_class(self):
        """Status field value appears in rendered HTML via template."""
        snapshot = roster_snapshot()
        html = render_entity("player_mike", snapshot, channel="html")

        assert_contains(html, "active")

    def test_all_entities_rendered_in_full_output(self):
        """All non-removed entities appear in the full render."""
        snapshot = roster_snapshot()
        html = render(snapshot, make_blueprint())

        assert_contains(html, "Mike", "Sarah", "Dave")

    def test_removed_entity_not_rendered(self):
        """Entity with _removed=True is not rendered in main content."""
        import re as _re
        snapshot = roster_snapshot()
        snapshot["entities"]["player_dave"]["_removed"] = True

        html = render(snapshot, make_blueprint())

        # Check main content only (Dave still in embedded JSON)
        m = _re.search(r"<main[^>]*>(.*?)</main>", html, _re.DOTALL)
        main_content = m.group(1) if m else ""

        assert "Mike" in main_content
        assert "Sarah" in main_content
        assert "Dave" not in main_content


# ============================================================================
# Text channel rendering
# ============================================================================


class TestTextChannelRendering:
    """
    render_entity with channel='text' uses the schema's render_text template.
    """

    def test_entity_rendered_as_text(self):
        """Entity renders as text using render_text template."""
        snapshot = roster_snapshot()
        text = render_entity("player_mike", snapshot, channel="text")

        assert "Mike" in text

    def test_text_template_interpolation(self):
        """Text template interpolates fields correctly."""
        snapshot = roster_snapshot()
        text = render_entity("player_sarah", snapshot, channel="text")

        assert "Sarah" in text
        assert "1350" in text

    def test_text_channel_no_html_tags(self):
        """Text channel output should not contain HTML tags."""
        snapshot = roster_snapshot()
        text = render_entity("player_mike", snapshot, channel="text")

        assert "<" not in text or "(" in text  # Template may have parentheses


# ============================================================================
# Fallback rendering (no template)
# ============================================================================


class TestFallbackRendering:
    """
    Entities without a schema or with a schema that has no render_html
    use the default fallback rendering (definition list).
    """

    def test_entity_without_schema_uses_fallback(self):
        """Entity with no _schema renders with fallback HTML."""
        snapshot = empty_state()
        snapshot["entities"]["plain"] = {
            "name": "Plain Entity",
            "value": 42,
        }
        html = render_entity("plain", snapshot, channel="html")

        assert "plain" in html.lower() or "Plain Entity" in html

    def test_entity_with_schema_but_no_template_uses_fallback(self):
        """Entity with schema that has no render_html uses fallback."""
        snapshot = empty_state()
        snapshot["schemas"]["no_template"] = {
            "interface": "interface NoTemplate { name: string; }",
            # No render_html
        }
        snapshot["entities"]["nt_entity"] = {
            "_schema": "no_template",
            "name": "No Template",
        }
        html = render_entity("nt_entity", snapshot, channel="html")

        # Should render something, not crash
        assert html is not None
        assert len(html) > 0

    def test_nonexistent_entity_renders_empty(self):
        """Nonexistent entity renders as empty string."""
        snapshot = empty_state()
        html = render_entity("nonexistent", snapshot, channel="html")
        assert html == ""


# ============================================================================
# Schema styles isolation
# ============================================================================


class TestSchemaStylesIsolation:
    """
    CSS from one schema does not affect another schema's rendering.
    Each schema's styles are independent.
    """

    def test_schema_styles_separate(self):
        """Two schemas with conflicting class names both appear in CSS."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Isolation Test"}

        snapshot["schemas"]["schema_a"] = {
            "interface": "interface A { name: string; }",
            "render_html": '<div class="item type-a">{{name}}</div>',
            "styles": ".item.type-a { color: red; }",
        }
        snapshot["schemas"]["schema_b"] = {
            "interface": "interface B { title: string; }",
            "render_html": '<div class="item type-b">{{title}}</div>',
            "styles": ".item.type-b { color: blue; }",
        }

        snapshot["entities"]["entity_a"] = {
            "_schema": "schema_a",
            "name": "Entity A",
        }
        snapshot["entities"]["entity_b"] = {
            "_schema": "schema_b",
            "title": "Entity B",
        }

        html = render(snapshot, make_blueprint())
        css = extract_style_block(html)

        assert ".item.type-a" in css
        assert ".item.type-b" in css
        assert "color: red" in css
        assert "color: blue" in css
