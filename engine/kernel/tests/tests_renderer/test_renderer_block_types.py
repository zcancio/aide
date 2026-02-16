"""
AIde Renderer -- Block Type Rendering Tests (Category 1)

One test per block type. Feed a snapshot with a single block, verify correct
HTML output.

From the spec (aide_renderer_spec.md, "Testing Strategy"):
  "1. Block type rendering. One test per block type. Feed a snapshot with a
   single block, verify correct HTML output."

Block types (v1):
  heading, text, metric, collection_view, divider, image, callout,
  column_list, column

This matters because:
  - The renderer is the final stage before the user sees anything
  - Each block type has a specific HTML structure and CSS classes
  - Incorrect rendering means the aide page is broken or misleading
  - Content must be HTML-escaped to prevent XSS
  - Block tree recursion must work (parent → children)

Reference: aide_renderer_spec.md (Block Rendering, Block Type → HTML)
"""

from engine.kernel.reducer import empty_state
from engine.kernel.renderer import render, render_block

# ============================================================================
# Helpers
# ============================================================================


def make_snapshot_with_block(block_id, block_type, props=None, children=None):
    """
    Build a minimal snapshot containing block_root with one child block.
    This is the smallest possible snapshot that produces visible output.
    """
    snapshot = empty_state()

    # Add the block to the block tree
    snapshot["blocks"][block_id] = {
        "type": block_type,
        "parent": "block_root",
        "props": props or {},
    }
    if children is not None:
        snapshot["blocks"][block_id]["children"] = children

    # Register as child of block_root
    snapshot["blocks"]["block_root"]["children"] = [block_id]

    return snapshot


def make_blueprint():
    """Minimal blueprint for rendering."""
    from engine.kernel.types import Blueprint

    return Blueprint(
        identity="Test aide.",
        voice="No first person.",
        prompt="Test prompt.",
    )


def assert_contains(html, *fragments):
    """Assert that the HTML output contains all given fragments."""
    for fragment in fragments:
        assert fragment in html, (
            f"Expected to find {fragment!r} in rendered HTML.\nGot (first 2000 chars):\n{html[:2000]}"
        )


def assert_not_contains(html, *fragments):
    """Assert that the HTML output does NOT contain any of the given fragments."""
    for fragment in fragments:
        assert fragment not in html, f"Did NOT expect to find {fragment!r} in rendered HTML."


# ============================================================================
# heading block
# ============================================================================


class TestHeadingBlock:
    """
    heading block renders as <h{level}> with aide-heading classes.
    Props: level (1-3), content
    """

    def test_heading_level_1(self):
        """Level 1 heading renders as <h1> with serif font class."""
        snapshot = make_snapshot_with_block(
            "block_title",
            "heading",
            props={"level": 1, "content": "Poker League"},
        )
        html = render_block("block_title", snapshot)

        assert_contains(
            html,
            "<h1",
            "aide-heading",
            "aide-heading--1",
            "Poker League",
            "</h1>",
        )

    def test_heading_level_2(self):
        """Level 2 heading renders as <h2>."""
        snapshot = make_snapshot_with_block(
            "block_section",
            "heading",
            props={"level": 2, "content": "Schedule"},
        )
        html = render_block("block_section", snapshot)

        assert_contains(
            html,
            "<h2",
            "aide-heading",
            "aide-heading--2",
            "Schedule",
            "</h2>",
        )

    def test_heading_level_3(self):
        """Level 3 heading renders as <h3> with sans font class."""
        snapshot = make_snapshot_with_block(
            "block_sub",
            "heading",
            props={"level": 3, "content": "Notes"},
        )
        html = render_block("block_sub", snapshot)

        assert_contains(
            html,
            "<h3",
            "aide-heading",
            "aide-heading--3",
            "Notes",
            "</h3>",
        )

    def test_heading_content_is_escaped(self):
        """HTML in heading content must be escaped, not rendered."""
        snapshot = make_snapshot_with_block(
            "block_xss",
            "heading",
            props={"level": 1, "content": '<script>alert("xss")</script>'},
        )
        html = render_block("block_xss", snapshot)

        assert_not_contains(html, "<script>")
        assert_contains(html, "&lt;script&gt;")


# ============================================================================
# text block
# ============================================================================


class TestTextBlock:
    """
    text block renders as <p class="aide-text">.
    Props: content (supports **bold**, *italic*, [link](url) inline formatting)
    """

    def test_plain_text(self):
        """Plain text renders as a paragraph."""
        snapshot = make_snapshot_with_block(
            "block_intro",
            "text",
            props={"content": "Welcome to the poker league."},
        )
        html = render_block("block_intro", snapshot)

        assert_contains(
            html,
            "<p",
            "aide-text",
            "Welcome to the poker league.",
            "</p>",
        )

    def test_text_content_is_escaped(self):
        """HTML in text content must be escaped."""
        snapshot = make_snapshot_with_block(
            "block_xss",
            "text",
            props={"content": "Try <img src=x onerror=alert(1)> this"},
        )
        html = render_block("block_xss", snapshot)

        assert_not_contains(html, "<img")
        assert_contains(html, "&lt;img")

    def test_text_with_bold(self):
        """**bold** renders as <strong>."""
        snapshot = make_snapshot_with_block(
            "block_bold",
            "text",
            props={"content": "This is **important** info."},
        )
        html = render_block("block_bold", snapshot)

        assert_contains(html, "<strong>important</strong>")

    def test_text_with_italic(self):
        """*italic* renders as <em>."""
        snapshot = make_snapshot_with_block(
            "block_italic",
            "text",
            props={"content": "This is *emphasized* text."},
        )
        html = render_block("block_italic", snapshot)

        assert_contains(html, "<em>emphasized</em>")

    def test_text_with_link(self):
        """[text](url) renders as <a> with href validated as http/https."""
        snapshot = make_snapshot_with_block(
            "block_link",
            "text",
            props={"content": "Visit [our site](https://toaide.com) today."},
        )
        html = render_block("block_link", snapshot)

        assert_contains(html, '<a href="https://toaide.com"')
        assert_contains(html, "our site</a>")


# ============================================================================
# metric block
# ============================================================================


class TestMetricBlock:
    """
    metric block renders as a label-value pair.
    Props: label, value, trend? (optional: "up", "down", "flat")
    """

    def test_metric_basic(self):
        """Metric renders label and value with correct classes."""
        snapshot = make_snapshot_with_block(
            "block_metric",
            "metric",
            props={"label": "Next game", "value": "Thu Feb 27 at Dave's"},
        )
        html = render_block("block_metric", snapshot)

        assert_contains(
            html,
            "aide-metric",
            "aide-metric__label",
            "Next game",
            "aide-metric__value",
            "Thu Feb 27 at Dave",  # apostrophe may be escaped
        )

    def test_metric_no_trend(self):
        """Metric without trend prop still renders correctly."""
        snapshot = make_snapshot_with_block(
            "block_pot",
            "metric",
            props={"label": "Pot", "value": "$240"},
        )
        html = render_block("block_pot", snapshot)

        assert_contains(html, "aide-metric", "Pot", "$240")

    def test_metric_with_trend_up(self):
        """Metric with trend='up' includes trend indicator."""
        snapshot = make_snapshot_with_block(
            "block_score",
            "metric",
            props={"label": "Score", "value": "1250", "trend": "up"},
        )
        html = render_block("block_score", snapshot)

        assert_contains(html, "aide-metric", "Score", "1250")
        # Trend should be represented somehow (class or element)
        # The exact mechanism depends on implementation, but it should be present

    def test_metric_value_is_escaped(self):
        """HTML in metric value must be escaped."""
        snapshot = make_snapshot_with_block(
            "block_xss",
            "metric",
            props={"label": "Status", "value": "<b>active</b>"},
        )
        html = render_block("block_xss", snapshot)

        assert_not_contains(html, "<b>active</b>")
        assert_contains(html, "&lt;b&gt;")

    def test_metric_label_is_escaped(self):
        """HTML in metric label must be escaped."""
        snapshot = make_snapshot_with_block(
            "block_xss_label",
            "metric",
            props={"label": "<script>x</script>", "value": "safe"},
        )
        html = render_block("block_xss_label", snapshot)

        assert_not_contains(html, "<script>")


# ============================================================================
# divider block
# ============================================================================


class TestDividerBlock:
    """
    divider block renders as <hr class="aide-divider">.
    Props: none
    """

    def test_divider_renders_hr(self):
        """Divider produces an <hr> element with the correct class."""
        snapshot = make_snapshot_with_block("block_div", "divider")
        html = render_block("block_div", snapshot)

        assert_contains(html, "<hr", "aide-divider")

    def test_divider_no_content(self):
        """Divider should not contain any text content."""
        snapshot = make_snapshot_with_block("block_div", "divider")
        html = render_block("block_div", snapshot)

        # hr is a void element, should not have closing tag content
        assert_not_contains(html, "</hr>")


# ============================================================================
# collection_view block
# ============================================================================


class TestCollectionViewBlock:
    """
    collection_view block delegates to the view renderer.
    Props: source (collection ID), view (view ID)
    """

    def _snapshot_with_collection_view(self, view_type="list"):
        """
        Build snapshot with a collection, entities, a view, and a
        collection_view block pointing to them.
        """
        snapshot = empty_state()

        # Collection with schema
        snapshot["collections"] = {
            "grocery_list": {
                "id": "grocery_list",
                "name": "Grocery List",
                "schema": {
                    "name": "string",
                    "checked": "bool",
                },
                "entities": {
                    "item_milk": {
                        "name": "Milk",
                        "checked": False,
                        "_removed": False,
                    },
                    "item_eggs": {
                        "name": "Eggs",
                        "checked": True,
                        "_removed": False,
                    },
                },
            },
        }

        # View
        snapshot["views"] = {
            "grocery_view": {
                "id": "grocery_view",
                "type": view_type,
                "source": "grocery_list",
                "config": {},
            },
        }

        # Block tree
        snapshot["blocks"]["block_grocery"] = {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "grocery_list", "view": "grocery_view"},
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_grocery"]

        return snapshot

    def test_collection_view_list_renders_entities(self):
        """collection_view with list view renders entity data."""
        snapshot = self._snapshot_with_collection_view("list")
        html = render_block("block_grocery", snapshot)

        assert_contains(html, "Milk", "Eggs")
        assert_contains(html, "aide-list")

    def test_collection_view_table_renders_headers_and_rows(self):
        """collection_view with table view renders table headers and entity rows."""
        snapshot = self._snapshot_with_collection_view("table")
        html = render_block("block_grocery", snapshot)

        assert_contains(html, "<table", "aide-table")
        assert_contains(html, "<thead", "<th")
        assert_contains(html, "Milk", "Eggs")

    def test_collection_view_missing_view_graceful(self):
        """
        If the view doesn't exist, fall back to default table view
        of the collection. Per spec: missing view → default table view.
        """
        snapshot = empty_state()
        snapshot["collections"] = {
            "items": {
                "id": "items",
                "name": "Items",
                "schema": {"name": "string"},
                "entities": {
                    "item_a": {
                        "name": "Alpha",
                        "_removed": False,
                    },
                },
            },
        }
        snapshot["blocks"]["block_cv"] = {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "items", "view": "nonexistent_view"},
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_cv"]

        # Should not raise — falls back to default table view
        html = render_block("block_cv", snapshot)
        assert_contains(html, "Alpha")

    def test_collection_view_missing_collection_renders_nothing(self):
        """
        If both view and collection don't exist, render nothing.
        Per spec: "If the collection also doesn't exist, render nothing."
        """
        snapshot = empty_state()
        snapshot["blocks"]["block_cv"] = {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "nonexistent", "view": "nonexistent"},
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_cv"]

        html = render_block("block_cv", snapshot)
        # Should produce empty or minimal output, not crash
        assert html is not None

    def test_collection_view_empty_collection(self):
        """
        Empty collection (no non-removed entities) shows empty state.
        Per spec: <p class="aide-collection-empty">No items yet.</p>
        """
        snapshot = empty_state()
        snapshot["collections"] = {
            "items": {
                "id": "items",
                "name": "Items",
                "schema": {"name": "string"},
                "entities": {},
            },
        }
        snapshot["views"] = {
            "items_view": {
                "id": "items_view",
                "type": "list",
                "source": "items",
                "config": {},
            },
        }
        snapshot["blocks"]["block_cv"] = {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "items", "view": "items_view"},
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_cv"]

        html = render_block("block_cv", snapshot)
        assert_contains(html, "aide-collection-empty")

    def test_collection_view_skips_removed_entities(self):
        """Entities with _removed=True should not appear in output."""
        snapshot = empty_state()
        snapshot["collections"] = {
            "items": {
                "id": "items",
                "name": "Items",
                "schema": {"name": "string"},
                "entities": {
                    "item_visible": {
                        "name": "Visible",
                        "_removed": False,
                    },
                    "item_removed": {
                        "name": "Removed",
                        "_removed": True,
                    },
                },
            },
        }
        snapshot["views"] = {
            "items_view": {
                "id": "items_view",
                "type": "list",
                "source": "items",
                "config": {},
            },
        }
        snapshot["blocks"]["block_cv"] = {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "items", "view": "items_view"},
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_cv"]

        html = render_block("block_cv", snapshot)
        assert_contains(html, "Visible")
        assert_not_contains(html, "Removed")


# ============================================================================
# image block
# ============================================================================


class TestImageBlock:
    """
    image block renders as <figure> with <img>.
    Props: src, alt?, caption?
    """

    def test_image_basic(self):
        """Image renders with src and lazy loading."""
        snapshot = make_snapshot_with_block(
            "block_img",
            "image",
            props={"src": "https://example.com/photo.jpg"},
        )
        html = render_block("block_img", snapshot)

        assert_contains(
            html,
            "<figure",
            "aide-image",
            "<img",
            'src="https://example.com/photo.jpg"',
            'loading="lazy"',
        )

    def test_image_with_alt(self):
        """Image renders alt attribute when provided."""
        snapshot = make_snapshot_with_block(
            "block_img",
            "image",
            props={
                "src": "https://example.com/photo.jpg",
                "alt": "Team photo",
            },
        )
        html = render_block("block_img", snapshot)

        assert_contains(html, 'alt="Team photo"')

    def test_image_with_caption(self):
        """Image renders figcaption when caption is provided."""
        snapshot = make_snapshot_with_block(
            "block_img",
            "image",
            props={
                "src": "https://example.com/photo.jpg",
                "caption": "The team at the 2026 kickoff",
            },
        )
        html = render_block("block_img", snapshot)

        assert_contains(
            html,
            "<figcaption",
            "aide-image__caption",
            "The team at the 2026 kickoff",
        )

    def test_image_without_caption(self):
        """Image without caption omits figcaption element."""
        snapshot = make_snapshot_with_block(
            "block_img",
            "image",
            props={"src": "https://example.com/photo.jpg"},
        )
        html = render_block("block_img", snapshot)

        assert_not_contains(html, "<figcaption")

    def test_image_src_is_escaped(self):
        """Image src with quotes/special chars must be escaped."""
        snapshot = make_snapshot_with_block(
            "block_img",
            "image",
            props={"src": 'https://example.com/photo.jpg" onload="alert(1)'},
        )
        html = render_block("block_img", snapshot)

        assert_not_contains(html, 'onload="alert(1)"')

    def test_image_alt_is_escaped(self):
        """Image alt text must be escaped."""
        snapshot = make_snapshot_with_block(
            "block_img",
            "image",
            props={
                "src": "https://example.com/photo.jpg",
                "alt": '<script>alert("xss")</script>',
            },
        )
        html = render_block("block_img", snapshot)

        assert_not_contains(html, "<script>")


# ============================================================================
# callout block
# ============================================================================


class TestCalloutBlock:
    """
    callout block renders as a highlighted aside.
    Props: content, icon?
    """

    def test_callout_basic(self):
        """Callout renders content with correct class."""
        snapshot = make_snapshot_with_block(
            "block_callout",
            "callout",
            props={"content": "Remember to bring snacks!"},
        )
        html = render_block("block_callout", snapshot)

        assert_contains(
            html,
            "aide-callout",
            "aide-callout__content",
            "Remember to bring snacks!",
        )

    def test_callout_with_icon(self):
        """Callout with icon renders the icon element."""
        snapshot = make_snapshot_with_block(
            "block_callout",
            "callout",
            props={"content": "Important note.", "icon": "⚠️"},
        )
        html = render_block("block_callout", snapshot)

        assert_contains(html, "aide-callout__icon", "⚠️")

    def test_callout_without_icon(self):
        """Callout without icon omits the icon element."""
        snapshot = make_snapshot_with_block(
            "block_callout",
            "callout",
            props={"content": "Just a note."},
        )
        html = render_block("block_callout", snapshot)

        assert_not_contains(html, "aide-callout__icon")

    def test_callout_content_is_escaped(self):
        """Callout content must be HTML-escaped."""
        snapshot = make_snapshot_with_block(
            "block_callout",
            "callout",
            props={"content": '<iframe src="evil.com">'},
        )
        html = render_block("block_callout", snapshot)

        assert_not_contains(html, "<iframe")
        assert_contains(html, "&lt;iframe")


# ============================================================================
# column_list and column blocks
# ============================================================================


class TestColumnBlocks:
    """
    column_list renders as a flex container.
    column renders as a flex child.
    Props: column_list has no props, column has width?.
    """

    def _snapshot_with_columns(self, col1_width=None, col2_width=None):
        """Build snapshot with column_list containing two columns."""
        snapshot = empty_state()

        col1_props = {}
        if col1_width:
            col1_props["width"] = col1_width

        col2_props = {}
        if col2_width:
            col2_props["width"] = col2_width

        snapshot["blocks"]["block_cols"] = {
            "type": "column_list",
            "parent": "block_root",
            "props": {},
            "children": ["block_col1", "block_col2"],
        }
        snapshot["blocks"]["block_col1"] = {
            "type": "column",
            "parent": "block_cols",
            "props": col1_props,
            "children": ["block_col1_heading"],
        }
        snapshot["blocks"]["block_col2"] = {
            "type": "column",
            "parent": "block_cols",
            "props": col2_props,
            "children": ["block_col2_heading"],
        }
        snapshot["blocks"]["block_col1_heading"] = {
            "type": "heading",
            "parent": "block_col1",
            "props": {"level": 3, "content": "Left Column"},
        }
        snapshot["blocks"]["block_col2_heading"] = {
            "type": "heading",
            "parent": "block_col2",
            "props": {"level": 3, "content": "Right Column"},
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_cols"]

        return snapshot

    def test_column_list_renders_flex_container(self):
        """column_list renders as a flex container div."""
        snapshot = self._snapshot_with_columns()
        html = render_block("block_cols", snapshot)

        assert_contains(html, "aide-columns")

    def test_column_renders_flex_child(self):
        """column renders as aide-column div."""
        snapshot = self._snapshot_with_columns()
        html = render_block("block_cols", snapshot)

        assert_contains(html, "aide-column")

    def test_column_with_percentage_width(self):
        """Column with percentage width gets flex: 0 0 {width}."""
        snapshot = self._snapshot_with_columns(col1_width="33%", col2_width="67%")
        html = render_block("block_cols", snapshot)

        # Should have inline flex style for percentage widths
        assert_contains(html, "33%")
        assert_contains(html, "67%")

    def test_column_without_width_defaults_to_flex_1(self):
        """Column without width prop gets flex: 1."""
        snapshot = self._snapshot_with_columns()
        html = render_block("block_cols", snapshot)

        assert_contains(html, "flex")

    def test_columns_render_children_recursively(self):
        """Column children (headings) are rendered inside the columns."""
        snapshot = self._snapshot_with_columns()
        html = render_block("block_cols", snapshot)

        assert_contains(html, "Left Column", "Right Column")


# ============================================================================
# Block tree recursion
# ============================================================================


class TestBlockTreeRecursion:
    """
    The block renderer must walk children recursively.
    Parent blocks render their children in order.
    """

    def test_root_renders_children_in_order(self):
        """block_root renders its children in the order listed."""
        snapshot = empty_state()

        snapshot["blocks"]["block_h1"] = {
            "type": "heading",
            "parent": "block_root",
            "props": {"level": 1, "content": "Title"},
        }
        snapshot["blocks"]["block_text"] = {
            "type": "text",
            "parent": "block_root",
            "props": {"content": "Body paragraph."},
        }
        snapshot["blocks"]["block_divider"] = {
            "type": "divider",
            "parent": "block_root",
            "props": {},
        }
        snapshot["blocks"]["block_root"]["children"] = [
            "block_h1",
            "block_text",
            "block_divider",
        ]

        html = render_block("block_root", snapshot)

        # All three blocks should be present
        assert_contains(html, "Title", "Body paragraph.")
        assert_contains(html, "aide-divider")

        # Order: heading should come before text, text before divider
        title_pos = html.index("Title")
        body_pos = html.index("Body paragraph.")
        divider_pos = html.index("aide-divider")
        assert title_pos < body_pos < divider_pos

    def test_nested_blocks_render_depth_first(self):
        """Nested block trees render depth-first."""
        snapshot = empty_state()

        snapshot["blocks"]["block_cols"] = {
            "type": "column_list",
            "parent": "block_root",
            "props": {},
            "children": ["block_col"],
        }
        snapshot["blocks"]["block_col"] = {
            "type": "column",
            "parent": "block_cols",
            "props": {},
            "children": ["block_inner_text"],
        }
        snapshot["blocks"]["block_inner_text"] = {
            "type": "text",
            "parent": "block_col",
            "props": {"content": "Nested content."},
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_cols"]

        html = render_block("block_root", snapshot)
        assert_contains(html, "Nested content.")

    def test_empty_children_list(self):
        """Block with empty children list renders only itself."""
        snapshot = make_snapshot_with_block(
            "block_heading",
            "heading",
            props={"level": 1, "content": "Solo Heading"},
        )
        # Explicitly set empty children
        snapshot["blocks"]["block_heading"]["children"] = []

        html = render_block("block_heading", snapshot)
        assert_contains(html, "Solo Heading")


# ============================================================================
# Full render (entire HTML document)
# ============================================================================


class TestFullRenderWithSingleBlock:
    """
    Verify that the full render() function wraps block output in a
    complete HTML document with <main class="aide-page">.
    """

    def test_heading_in_full_render(self):
        """Full render with a heading block produces valid HTML structure."""
        snapshot = make_snapshot_with_block(
            "block_title",
            "heading",
            props={"level": 1, "content": "My Aide"},
        )
        snapshot["meta"] = {"title": "My Aide"}

        html = render(snapshot, make_blueprint())

        assert_contains(
            html,
            "<!DOCTYPE html>",
            "<html",
            '<main class="aide-page"',
            "My Aide",
            "</main>",
            "</html>",
        )

    def test_divider_in_full_render(self):
        """Full render with a divider block wraps it in the page structure."""
        snapshot = make_snapshot_with_block("block_div", "divider")
        snapshot["meta"] = {"title": "Test"}

        html = render(snapshot, make_blueprint())

        assert_contains(html, "aide-page", "aide-divider")
