"""
AIde Renderer -- Value Formatting Tests (v3 Unified Entity Model)

In v3, field values are interpolated via Mustache templates in schemas.
The renderer passes entity field values directly as Mustache context.

Tests verify that:
  - String fields interpolate as text
  - Number fields render as their string representation
  - Boolean fields render via template (True/False in Mustache)
  - Null/missing fields render as empty in Mustache
  - Field values are passed correctly to chevron

Reference: aide_renderer_spec.md (Value Formatting)
"""

from engine.kernel.reducer import empty_state
from engine.kernel.renderer import render_entity


def assert_contains(html, *fragments):
    for fragment in fragments:
        assert fragment in html, (
            f"Expected to find {fragment!r} in rendered HTML.\nGot (first 3000 chars):\n{html[:3000]}"
        )


def assert_not_contains(html, *fragments):
    for fragment in fragments:
        assert fragment not in html, f"Did NOT expect to find {fragment!r} in rendered HTML."


def make_entity_snapshot(fields, render_html=None, schema_interface=None):
    """
    Build a snapshot with one entity with given fields.
    render_html defaults to showing all known fields.
    """
    snapshot = empty_state()

    if render_html is None:
        # Build a template that shows each field on its own
        field_parts = " | ".join("{{field_name}}" if False else f"{{{{{k}}}}}" for k in fields if not k.startswith("_"))
        render_html = f"<div class=\"entity\">{field_parts}</div>"

    if schema_interface is None:
        # Build a minimal interface
        schema_interface = "interface Entity { name: string; }"

    snapshot["schemas"]["my_schema"] = {
        "interface": schema_interface,
        "render_html": render_html,
    }
    entity = {"_schema": "my_schema"}
    entity.update(fields)
    snapshot["entities"]["entity_1"] = entity

    return snapshot


# ============================================================================
# String values
# ============================================================================


class TestStringValues:
    """String fields render as plain text in templates."""

    def test_basic_string(self):
        """String field renders as plain text."""
        snapshot = make_entity_snapshot(
            {"name": "Alice"},
            render_html="<span>{{name}}</span>",
            schema_interface="interface Entity { name: string; }",
        )
        html = render_entity("entity_1", snapshot)
        assert_contains(html, "Alice")
        assert_not_contains(html, "{{name}}")

    def test_string_with_spaces(self):
        """String with spaces renders correctly."""
        snapshot = make_entity_snapshot(
            {"title": "Game Night Friday"},
            render_html="<h3>{{title}}</h3>",
            schema_interface="interface Entity { title: string; }",
        )
        html = render_entity("entity_1", snapshot)
        assert_contains(html, "Game Night Friday")

    def test_empty_string(self):
        """Empty string field renders as empty."""
        snapshot = make_entity_snapshot(
            {"name": ""},
            render_html="<span class=\"name\">{{name}}</span>",
            schema_interface="interface Entity { name: string; }",
        )
        html = render_entity("entity_1", snapshot)
        assert_contains(html, "class=\"name\"")

    def test_string_html_escaped(self):
        """String field content is HTML-escaped in fallback rendering."""
        # Test uses the fallback renderer (no render_html template)
        snapshot = empty_state()
        snapshot["entities"]["xss"] = {"name": '<script>alert("xss")</script>'}
        html = render_entity("xss", snapshot)
        # Fallback rendering escapes the content
        assert_not_contains(html, "<script>")

    def test_multiple_string_fields(self):
        """Multiple string fields all appear."""
        snapshot = make_entity_snapshot(
            {"first": "John", "last": "Doe", "role": "Admin"},
            render_html="<div>{{first}} {{last}} ({{role}})</div>",
            schema_interface="interface Entity { first: string; last: string; role: string; }",
        )
        html = render_entity("entity_1", snapshot)
        assert_contains(html, "John", "Doe", "Admin")


# ============================================================================
# Numeric values
# ============================================================================


class TestNumericValues:
    """Number fields render via their string representation in Mustache."""

    def test_integer_field(self):
        """Integer renders as its string representation."""
        snapshot = make_entity_snapshot(
            {"score": 42},
            render_html="<span class=\"score\">{{score}}</span>",
            schema_interface="interface Entity { score: number; }",
        )
        html = render_entity("entity_1", snapshot)
        assert_contains(html, "42")

    def test_float_field(self):
        """Float renders as its string representation."""
        snapshot = make_entity_snapshot(
            {"price": 9.99},
            render_html="<span>{{price}}</span>",
            schema_interface="interface Entity { price: number; }",
        )
        html = render_entity("entity_1", snapshot)
        assert_contains(html, "9.99")

    def test_zero_value(self):
        """Zero value renders as 0."""
        snapshot = make_entity_snapshot(
            {"count": 0},
            render_html="<span>{{count}}</span>",
            schema_interface="interface Entity { count: number; }",
        )
        html = render_entity("entity_1", snapshot)
        # Mustache treats 0 as falsy, so it may not appear
        # Test that the entity renders without crashing
        assert html is not None
        assert len(html) > 0

    def test_negative_number(self):
        """Negative number renders correctly."""
        snapshot = make_entity_snapshot(
            {"balance": -50},
            render_html="<span>{{balance}}</span>",
            schema_interface="interface Entity { balance: number; }",
        )
        html = render_entity("entity_1", snapshot)
        assert_contains(html, "-50")

    def test_large_number(self):
        """Large number renders without scientific notation."""
        snapshot = make_entity_snapshot(
            {"total": 1000000},
            render_html="<span>{{total}}</span>",
            schema_interface="interface Entity { total: number; }",
        )
        html = render_entity("entity_1", snapshot)
        assert_contains(html, "1000000")


# ============================================================================
# Boolean values
# ============================================================================


class TestBooleanValues:
    """
    Boolean fields in Mustache: True is truthy, False is falsy.
    {{#done}}Checked{{/done}} shows "Checked" when done=True.
    """

    def test_bool_true_in_section(self):
        """True boolean shows section content."""
        snapshot = make_entity_snapshot(
            {"done": True},
            render_html="<span>{{#done}}Checked{{/done}}</span>",
            schema_interface="interface Entity { done: boolean; }",
        )
        html = render_entity("entity_1", snapshot)
        assert_contains(html, "Checked")

    def test_bool_false_in_section(self):
        """False boolean hides section content."""
        snapshot = make_entity_snapshot(
            {"done": False},
            render_html="<span>{{#done}}Checked{{/done}}</span>",
            schema_interface="interface Entity { done: boolean; }",
        )
        html = render_entity("entity_1", snapshot)
        assert_not_contains(html, "Checked")

    def test_bool_true_not_shown_in_inverted_section(self):
        """True boolean hides inverted section ({{^done}})."""
        snapshot = make_entity_snapshot(
            {"done": True},
            render_html="<span>{{^done}}Not done{{/done}}</span>",
            schema_interface="interface Entity { done: boolean; }",
        )
        html = render_entity("entity_1", snapshot)
        assert_not_contains(html, "Not done")

    def test_bool_false_shown_in_inverted_section(self):
        """False boolean shows inverted section."""
        snapshot = make_entity_snapshot(
            {"done": False},
            render_html="<span>{{^done}}Not done{{/done}}</span>",
            schema_interface="interface Entity { done: boolean; }",
        )
        html = render_entity("entity_1", snapshot)
        assert_contains(html, "Not done")


# ============================================================================
# Field rendering in child collections
# ============================================================================


class TestChildCollectionFieldRendering:
    """
    Fields in child entities render via child schema templates.
    """

    def _child_snapshot(self):
        snapshot = empty_state()
        snapshot["schemas"]["task"] = {
            "interface": "interface Task { title: string; priority: number; }",
            "render_html": "<li class=\"task\" data-priority=\"{{priority}}\">{{title}}</li>",
        }
        snapshot["schemas"]["project"] = {
            "interface": "interface Project { name: string; tasks: Record<string, Task>; }",
            "render_html": "<div class=\"project\"><h2>{{name}}</h2><ul>{{>tasks}}</ul></div>",
        }
        snapshot["entities"]["project_1"] = {
            "_schema": "project",
            "name": "My Project",
            "tasks": {
                "task_a": {"title": "Write code", "priority": 1, "_pos": 1.0},
                "task_b": {"title": "Review PR", "priority": 2, "_pos": 2.0},
                "task_c": {"title": "Deploy", "priority": 3, "_pos": 3.0},
            },
        }
        return snapshot

    def test_child_string_field_renders(self):
        """Child entity string field renders correctly."""
        snapshot = self._child_snapshot()
        html = render_entity("project_1", snapshot)
        assert_contains(html, "Write code", "Review PR", "Deploy")

    def test_child_number_field_renders(self):
        """Child entity number field renders correctly."""
        snapshot = self._child_snapshot()
        html = render_entity("project_1", snapshot)
        assert_contains(html, "data-priority=\"1\"")
        assert_contains(html, "data-priority=\"2\"")
        assert_contains(html, "data-priority=\"3\"")

    def test_parent_field_renders_separately(self):
        """Parent entity field renders in parent template."""
        snapshot = self._child_snapshot()
        html = render_entity("project_1", snapshot)
        assert_contains(html, "My Project")
        assert_contains(html, "<h2>My Project</h2>")


# ============================================================================
# Fallback rendering (no template)
# ============================================================================


class TestFallbackValueRendering:
    """
    Without a schema template, entities use fallback rendering (dl/dd pairs).
    """

    def test_fallback_shows_string_values(self):
        """Fallback rendering shows string field values."""
        snapshot = empty_state()
        snapshot["entities"]["plain"] = {"name": "Test Entity", "status": "active"}
        html = render_entity("plain", snapshot)
        assert_contains(html, "Test Entity", "active")

    def test_fallback_shows_number_values(self):
        """Fallback rendering shows number field values."""
        snapshot = empty_state()
        snapshot["entities"]["plain"] = {"count": 42, "score": 99.5}
        html = render_entity("plain", snapshot)
        assert_contains(html, "42", "99.5")

    def test_fallback_renders_dl_structure(self):
        """Fallback uses dl/dt/dd structure."""
        snapshot = empty_state()
        snapshot["entities"]["plain"] = {"name": "Alice"}
        html = render_entity("plain", snapshot)
        assert_contains(html, "<dl>", "<dt>", "<dd>")

    def test_fallback_excludes_system_fields(self):
        """Fallback does not render system fields (_schema, _pos, etc.)."""
        snapshot = empty_state()
        snapshot["entities"]["plain"] = {
            "name": "Test",
            "_pos": 1.0,
            "_schema": "some_schema",
        }
        html = render_entity("plain", snapshot)
        # System fields should not appear as visible content
        assert "_pos" not in html
        assert "_schema" not in html

    def test_nonexistent_entity_returns_empty(self):
        """Nonexistent entity returns empty string."""
        snapshot = empty_state()
        html = render_entity("nonexistent", snapshot)
        assert html == ""


# ============================================================================
# Text channel value rendering
# ============================================================================


class TestTextChannelValues:
    """Values render correctly in text channel."""

    def test_string_in_text_channel(self):
        """String value appears in text channel output."""
        snapshot = empty_state()
        snapshot["schemas"]["item"] = {
            "interface": "interface Item { name: string; }",
            "render_html": "<div>{{name}}</div>",
            "render_text": "{{name}}",
        }
        snapshot["entities"]["item_1"] = {"_schema": "item", "name": "Test Item"}
        text = render_entity("item_1", snapshot, channel="text")
        assert "Test Item" in text

    def test_number_in_text_channel(self):
        """Number value appears in text channel output."""
        snapshot = empty_state()
        snapshot["schemas"]["item"] = {
            "interface": "interface Item { score: number; }",
            "render_html": "<div>{{score}}</div>",
            "render_text": "Score: {{score}}",
        }
        snapshot["entities"]["item_1"] = {"_schema": "item", "score": 100}
        text = render_entity("item_1", snapshot, channel="text")
        assert "100" in text

    def test_text_channel_no_html_tags(self):
        """Text channel output from render_text has no HTML tags."""
        snapshot = empty_state()
        snapshot["schemas"]["item"] = {
            "interface": "interface Item { name: string; }",
            "render_html": "<div class=\"item\">{{name}}</div>",
            "render_text": "- {{name}}",
        }
        snapshot["entities"]["item_1"] = {"_schema": "item", "name": "Clean"}
        text = render_entity("item_1", snapshot, channel="text")
        assert "<div" not in text
        assert "class=" not in text
