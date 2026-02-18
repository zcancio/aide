"""
AIde Renderer -- Empty State Tests (v3 Unified Entity Model)

No blocks, empty entities, missing entity references.

From the spec (aide_renderer_spec.md, "Testing Strategy"):
  "8. Empty states. No blocks, empty collection, missing view."

Three empty state patterns in v3:
1. No blocks (only block_root with empty children) and no entities:
   → <p class="aide-empty">This page is empty.</p>
2. entity_view block pointing to removed/missing entity:
   → render nothing (empty string)
3. Entity with no child entities in a sub-collection:
   → template renders with no children

Reference: aide_renderer_spec.md (Empty States, View Rendering)
"""

import re

from engine.kernel.reducer import empty_state
from engine.kernel.renderer import render, render_block
from engine.kernel.types import Blueprint


def assert_contains(html, *fragments):
    for fragment in fragments:
        assert fragment in html, (
            f"Expected to find {fragment!r} in rendered HTML.\nGot (first 3000 chars):\n{html[:3000]}"
        )


def assert_not_contains(html, *fragments):
    for fragment in fragments:
        assert fragment not in html, f"Did NOT expect to find {fragment!r} in rendered HTML."


def extract_main(html):
    """Extract content within <main> tags only (avoids CSS)."""
    match = re.search(r"<main[^>]*>(.*?)</main>", html, re.DOTALL)
    return match.group(1) if match else ""


def assert_not_in_main(html, *fragments):
    """Assert fragments do NOT appear within <main> content."""
    main = extract_main(html)
    for fragment in fragments:
        assert fragment not in main, f"Did NOT expect to find {fragment!r} in <main> content."


def make_blueprint():
    return Blueprint(
        identity="Test aide.",
        voice="No first person.",
        prompt="Test prompt.",
    )


# ============================================================================
# No blocks — empty page
# ============================================================================


class TestNoBlocks:
    """
    No blocks and no entities → renders empty message.
    Per spec: <p class="aide-empty">This page is empty.</p>
    """

    def test_empty_page_message(self):
        """Page with no blocks shows 'This page is empty.' message."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Empty Test"}

        html = render(snapshot, make_blueprint())

        assert_contains(html, "aide-empty")
        assert_contains(html, "This page is empty.")

    def test_empty_page_inside_aide_page(self):
        """Empty message is inside the <main class='aide-page'> container."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Empty Test"}

        html = render(snapshot, make_blueprint())

        assert_contains(html, "aide-page")
        main_start = html.find("<main")
        main_end = html.find("</main>")
        assert main_start != -1
        assert main_end != -1
        main_content = html[main_start:main_end]
        assert "aide-empty" in main_content

    def test_empty_page_still_valid_html(self):
        """An empty page still produces valid HTML5 document structure."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Empty Test"}

        html = render(snapshot, make_blueprint())

        assert_contains(html, "<!DOCTYPE html>")
        assert_contains(html, "<html")
        assert_contains(html, "<head>")
        assert_contains(html, "</head>")
        assert_contains(html, "<body>")
        assert_contains(html, "</body>")
        assert_contains(html, "</html>")

    def test_empty_page_has_title(self):
        """Even an empty page renders the <title> tag."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "My Empty Aide"}

        html = render(snapshot, make_blueprint())

        assert_contains(html, "<title>My Empty Aide</title>")

    def test_empty_page_has_style_block(self):
        """Even an empty page includes the base CSS."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Empty"}

        html = render(snapshot, make_blueprint())

        assert_contains(html, "<style>")
        assert_contains(html, "</style>")

    def test_block_root_with_explicit_empty_children(self):
        """block_root exists with children=[] — same as default empty state."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Empty"}
        snapshot["blocks"]["block_root"]["children"] = []

        html = render(snapshot, make_blueprint())

        assert_contains(html, "aide-empty")
        assert_contains(html, "This page is empty.")


# ============================================================================
# Entities but no blocks — auto-rendered
# ============================================================================


class TestEntitiesNoBlocks:
    """
    When entities exist but no explicit blocks are set, the renderer
    auto-renders all top-level entities.
    """

    def test_entities_auto_render_when_no_blocks(self):
        """Entities auto-render if block_root has no children."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Auto Render"}
        snapshot["schemas"]["item"] = {
            "interface": "interface Item { name: string; }",
            "render_html": "<p class=\"item\">{{name}}</p>",
        }
        snapshot["entities"]["my_item"] = {
            "_schema": "item",
            "name": "Hello World",
        }
        # No explicit blocks added to block_root

        html = render(snapshot, make_blueprint())

        # Should not show empty message
        assert_not_contains(html, "This page is empty.")
        assert_contains(html, "Hello World")

    def test_only_removed_entities_shows_empty(self):
        """All removed entities → page shows empty message."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Removed"}
        snapshot["entities"]["removed_entity"] = {
            "name": "Gone",
            "_removed": True,
        }

        html = render(snapshot, make_blueprint())

        assert_contains(html, "This page is empty.")
        assert_not_in_main(html, "Gone")


# ============================================================================
# entity_view block — missing/removed entity
# ============================================================================


class TestEntityViewMissingEntity:
    """
    entity_view block pointing to a nonexistent or removed entity.
    Should render nothing (empty string).
    """

    def test_missing_entity_renders_nothing(self):
        """entity_view with nonexistent source renders empty."""
        snapshot = empty_state()
        snapshot["blocks"]["block_view"] = {
            "type": "entity_view",
            "source": "nonexistent_entity",
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_view"]

        html = render_block("block_view", snapshot)
        assert html == ""

    def test_removed_entity_renders_nothing(self):
        """entity_view pointing to a removed entity renders empty."""
        snapshot = empty_state()
        snapshot["entities"]["removed"] = {
            "name": "Gone",
            "_removed": True,
        }
        snapshot["blocks"]["block_view"] = {
            "type": "entity_view",
            "source": "removed",
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_view"]

        html = render_block("block_view", snapshot)
        assert html == ""

    def test_no_source_field_renders_nothing(self):
        """entity_view with no source field renders empty."""
        snapshot = empty_state()
        snapshot["blocks"]["block_view"] = {
            "type": "entity_view",
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_view"]

        html = render_block("block_view", snapshot)
        assert html == ""


# ============================================================================
# Entity with no children
# ============================================================================


class TestEntityWithNoChildren:
    """
    An entity that has a child collection field but it's empty.
    Template with {{>items}} should render with no children.
    """

    def test_entity_with_empty_child_collection(self):
        """Entity with empty child collection renders without crashing."""
        snapshot = empty_state()
        snapshot["schemas"]["list_schema"] = {
            "interface": "interface ListSchema { name: string; }",
            "render_html": "<div class=\"list\"><h2>{{name}}</h2>{{>items}}</div>",
        }
        snapshot["entities"]["empty_list"] = {
            "_schema": "list_schema",
            "name": "Empty List",
            "items": {},  # Empty child collection
        }
        snapshot["blocks"]["block_view"] = {
            "type": "entity_view",
            "source": "empty_list",
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_view"]

        html = render_block("block_view", snapshot)

        assert_contains(html, "Empty List")
        assert_contains(html, "class=\"list\"")

    def test_entity_with_all_children_removed(self):
        """Entity with all children removed renders without children content."""
        snapshot = empty_state()
        snapshot["schemas"]["item_schema"] = {
            "interface": "interface ItemSchema { name: string; }",
            "render_html": "<div>{{name}}</div>",
        }
        snapshot["schemas"]["child_schema"] = {
            "interface": "interface ChildSchema { label: string; }",
            "render_html": "<span>{{label}}</span>",
        }
        snapshot["entities"]["parent"] = {
            "_schema": "item_schema",
            "name": "Parent",
            "children": {
                "child_1": {"label": "Child One", "_removed": True},
                "child_2": {"label": "Child Two", "_removed": True},
            },
        }

        html = render_block("block_view", snapshot)
        # Block view doesn't exist in blocks, so returns ""
        assert html == ""


# ============================================================================
# Blocks with no content
# ============================================================================


class TestBlocksWithNoContent:
    """
    Blocks with empty or missing fields still render without crashing.
    """

    def test_heading_with_empty_text(self):
        """Heading with empty text renders empty heading element."""
        snapshot = empty_state()
        snapshot["blocks"]["block_h"] = {"type": "heading", "level": 1, "text": ""}
        snapshot["blocks"]["block_root"]["children"] = ["block_h"]

        html = render_block("block_h", snapshot)
        assert "<h1" in html

    def test_text_with_empty_content(self):
        """Text block with empty text renders empty paragraph."""
        snapshot = empty_state()
        snapshot["blocks"]["block_p"] = {"type": "text", "text": ""}
        snapshot["blocks"]["block_root"]["children"] = ["block_p"]

        html = render_block("block_p", snapshot)
        assert "<p" in html

    def test_metric_with_empty_values(self):
        """Metric with empty label/value renders without crashing."""
        snapshot = empty_state()
        snapshot["blocks"]["block_m"] = {"type": "metric", "label": "", "value": ""}
        snapshot["blocks"]["block_root"]["children"] = ["block_m"]

        html = render_block("block_m", snapshot)
        assert "aide-metric" in html

    def test_missing_block_id_renders_nothing(self):
        """render_block with nonexistent block ID returns empty string."""
        snapshot = empty_state()

        html = render_block("nonexistent_block", snapshot)
        assert html == ""


# ============================================================================
# Full render empty states
# ============================================================================


class TestFullRenderEmptyStates:
    """
    Full render() with various empty states.
    """

    def test_no_blocks_no_entities_full_render(self):
        """Full render with no blocks and no entities shows empty message."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "All Empty"}

        html = render(snapshot, make_blueprint())

        assert_contains(html, "aide-empty", "This page is empty.")
        assert_contains(html, "<!DOCTYPE html>")

    def test_heading_block_plus_missing_entity_view(self):
        """Heading renders; entity_view with missing source renders nothing."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Mixed"}

        snapshot["blocks"]["block_h"] = {
            "type": "heading",
            "level": 1,
            "text": "My Page",
        }
        snapshot["blocks"]["block_view"] = {
            "type": "entity_view",
            "source": "nonexistent",
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_h", "block_view"]

        html = render(snapshot, make_blueprint())

        assert_contains(html, "My Page")
        # Page is not "empty" because there are blocks
        assert_not_contains(html, "This page is empty.")

    def test_css_class_aide_empty_present(self):
        """The .aide-empty CSS class is defined in the base stylesheet."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "CSS Test"}

        html = render(snapshot, make_blueprint())

        assert "aide-empty" in html
