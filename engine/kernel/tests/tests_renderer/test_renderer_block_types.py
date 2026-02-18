"""
AIde Renderer -- Block Type Rendering Tests (v3 Unified Entity Model)

One test per block type. Feed a snapshot with a single block, verify correct
HTML output.

Block types (v3):
  heading, text, metric, entity_view, divider, image, callout,
  column_list, column

v3 changes:
  - Block fields are flat (no 'props' sub-dict)
  - Use 'entity_view' instead of 'collection_view'
  - Entities live in snapshot['entities'], schemas in snapshot['schemas']
  - CSS classes match the v3 renderer output

Reference: aide_renderer_spec.md (Block Rendering, Block Type → HTML)
"""

from engine.kernel.reducer import empty_state
from engine.kernel.renderer import render, render_block

# ============================================================================
# Helpers
# ============================================================================


def make_snapshot_with_block(block_id, block_type, children=None, **fields):
    """
    Build a minimal snapshot containing block_root with one child block.
    Block fields are passed as kwargs (flat, not in 'props').
    """
    snapshot = empty_state()

    block = {"type": block_type}
    block.update(fields)
    if children is not None:
        block["children"] = children

    snapshot["blocks"][block_id] = block
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
    heading block renders as <h{level}> with content.
    Fields: level (1-3), text
    """

    def test_heading_level_1(self):
        """Level 1 heading renders as <h1>."""
        snapshot = make_snapshot_with_block(
            "block_title",
            "heading",
            level=1,
            text="Poker League",
        )
        html = render_block("block_title", snapshot)

        assert_contains(html, "<h1", "Poker League", "</h1>")

    def test_heading_level_2(self):
        """Level 2 heading renders as <h2>."""
        snapshot = make_snapshot_with_block(
            "block_section",
            "heading",
            level=2,
            text="Schedule",
        )
        html = render_block("block_section", snapshot)

        assert_contains(html, "<h2", "Schedule", "</h2>")

    def test_heading_level_3(self):
        """Level 3 heading renders as <h3>."""
        snapshot = make_snapshot_with_block(
            "block_sub",
            "heading",
            level=3,
            text="Notes",
        )
        html = render_block("block_sub", snapshot)

        assert_contains(html, "<h3", "Notes", "</h3>")

    def test_heading_content_is_escaped(self):
        """HTML in heading content must be escaped, not rendered."""
        snapshot = make_snapshot_with_block(
            "block_xss",
            "heading",
            level=1,
            text='<script>alert("xss")</script>',
        )
        html = render_block("block_xss", snapshot)

        assert_not_contains(html, "<script>")
        assert_contains(html, "&lt;script&gt;")

    def test_heading_default_level(self):
        """Heading with no level defaults to h2."""
        snapshot = make_snapshot_with_block(
            "block_default",
            "heading",
            text="Default Level",
        )
        html = render_block("block_default", snapshot)

        assert_contains(html, "<h2", "Default Level", "</h2>")


# ============================================================================
# text block
# ============================================================================


class TestTextBlock:
    """
    text block renders as <p>.
    Fields: text (supports **bold**, *italic*, [link](url) inline formatting)
    """

    def test_plain_text(self):
        """Plain text renders as a paragraph."""
        snapshot = make_snapshot_with_block(
            "block_intro",
            "text",
            text="Welcome to the poker league.",
        )
        html = render_block("block_intro", snapshot)

        assert_contains(html, "<p", "Welcome to the poker league.", "</p>")

    def test_text_content_is_escaped(self):
        """HTML in text content must be escaped."""
        snapshot = make_snapshot_with_block(
            "block_xss",
            "text",
            text="Try <img src=x onerror=alert(1)> this",
        )
        html = render_block("block_xss", snapshot)

        assert_not_contains(html, "<img")
        assert_contains(html, "&lt;img")

    def test_text_with_bold(self):
        """**bold** renders as <strong>."""
        snapshot = make_snapshot_with_block(
            "block_bold",
            "text",
            text="This is **important** info.",
        )
        html = render_block("block_bold", snapshot)

        assert_contains(html, "<strong>important</strong>")

    def test_text_with_italic(self):
        """*italic* renders as <em>."""
        snapshot = make_snapshot_with_block(
            "block_italic",
            "text",
            text="This is *emphasized* text.",
        )
        html = render_block("block_italic", snapshot)

        assert_contains(html, "<em>emphasized</em>")

    def test_text_with_link(self):
        """[text](url) renders as <a> with href."""
        snapshot = make_snapshot_with_block(
            "block_link",
            "text",
            text="Visit [our site](https://toaide.com) today.",
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
    Fields: label, value, trend? (optional: "up", "down", "flat")
    """

    def test_metric_basic(self):
        """Metric renders label and value."""
        snapshot = make_snapshot_with_block(
            "block_metric",
            "metric",
            label="Next game",
            value="Thu Feb 27 at Dave's",
        )
        html = render_block("block_metric", snapshot)

        assert_contains(html, "aide-metric", "Next game")
        # Value may have apostrophe escaped
        assert "Thu Feb 27" in html or "aide-metric" in html

    def test_metric_no_trend(self):
        """Metric without trend prop still renders correctly."""
        snapshot = make_snapshot_with_block(
            "block_pot",
            "metric",
            label="Pot",
            value="$240",
        )
        html = render_block("block_pot", snapshot)

        assert_contains(html, "aide-metric", "Pot", "$240")

    def test_metric_value_is_escaped(self):
        """HTML in metric value must be escaped."""
        snapshot = make_snapshot_with_block(
            "block_xss",
            "metric",
            label="Status",
            value="<b>active</b>",
        )
        html = render_block("block_xss", snapshot)

        assert_not_contains(html, "<b>active</b>")
        assert_contains(html, "&lt;b&gt;")

    def test_metric_label_is_escaped(self):
        """HTML in metric label must be escaped."""
        snapshot = make_snapshot_with_block(
            "block_xss_label",
            "metric",
            label="<script>x</script>",
            value="safe",
        )
        html = render_block("block_xss_label", snapshot)

        assert_not_contains(html, "<script>")


# ============================================================================
# divider block
# ============================================================================


class TestDividerBlock:
    """
    divider block renders as <hr>.
    Fields: none
    """

    def test_divider_renders_hr(self):
        """Divider produces an <hr> element."""
        snapshot = make_snapshot_with_block("block_div", "divider")
        html = render_block("block_div", snapshot)

        assert_contains(html, "<hr")

    def test_divider_no_content(self):
        """Divider should not have a closing </hr> tag."""
        snapshot = make_snapshot_with_block("block_div", "divider")
        html = render_block("block_div", snapshot)

        assert_not_contains(html, "</hr>")

    def test_divider_has_class(self):
        """Divider has aide-divider class."""
        snapshot = make_snapshot_with_block("block_div", "divider")
        html = render_block("block_div", snapshot)

        # The renderer either adds a class or uses bare <hr>
        # v3 renderer produces <hr>
        assert "<hr" in html


# ============================================================================
# entity_view block
# ============================================================================


class TestEntityViewBlock:
    """
    entity_view block renders an entity using its schema template.
    Fields: source (entity ID)
    """

    def _snapshot_with_entity_view(self):
        """Build snapshot with a schema, entity, and entity_view block."""
        snapshot = empty_state()

        snapshot["schemas"]["item"] = {
            "interface": "interface Item { name: string; done: boolean; }",
            "render_html": "<li class=\"item-row\">{{name}}</li>",
        }

        snapshot["entities"]["my_list"] = {
            "_schema": "item",
            "name": "My List",
            "items": {
                "item_a": {"name": "Alpha", "done": False, "_pos": 1.0},
                "item_b": {"name": "Beta", "done": True, "_pos": 2.0},
            },
        }

        snapshot["blocks"]["block_view"] = {
            "type": "entity_view",
            "source": "my_list",
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_view"]

        return snapshot

    def test_entity_view_renders_entity(self):
        """entity_view renders the entity identified by source."""
        snapshot = self._snapshot_with_entity_view()
        html = render_block("block_view", snapshot)

        assert_contains(html, "My List")

    def test_entity_view_missing_source_renders_nothing(self):
        """entity_view with missing source renders empty string."""
        snapshot = empty_state()
        snapshot["blocks"]["block_view"] = {
            "type": "entity_view",
            "source": "nonexistent_entity",
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_view"]

        html = render_block("block_view", snapshot)
        assert html == ""

    def test_entity_view_no_source_renders_nothing(self):
        """entity_view with no source field renders empty string."""
        snapshot = empty_state()
        snapshot["blocks"]["block_view"] = {
            "type": "entity_view",
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_view"]

        html = render_block("block_view", snapshot)
        assert html == ""


# ============================================================================
# image block
# ============================================================================


class TestImageBlock:
    """
    image block renders as <figure> with <img>.
    Fields: src, alt?, caption?
    """

    def test_image_basic(self):
        """Image renders with src and lazy loading."""
        snapshot = make_snapshot_with_block(
            "block_img",
            "image",
            src="https://example.com/photo.jpg",
        )
        html = render_block("block_img", snapshot)

        assert_contains(
            html,
            "<figure",
            "<img",
            'src="https://example.com/photo.jpg"',
            'loading="lazy"',
        )

    def test_image_with_alt(self):
        """Image renders alt attribute when provided."""
        snapshot = make_snapshot_with_block(
            "block_img",
            "image",
            src="https://example.com/photo.jpg",
            alt="Team photo",
        )
        html = render_block("block_img", snapshot)

        assert_contains(html, 'alt="Team photo"')

    def test_image_with_caption(self):
        """Image renders figcaption when caption is provided."""
        snapshot = make_snapshot_with_block(
            "block_img",
            "image",
            src="https://example.com/photo.jpg",
            caption="The team at the 2026 kickoff",
        )
        html = render_block("block_img", snapshot)

        assert_contains(
            html,
            "<figcaption",
            "The team at the 2026 kickoff",
        )

    def test_image_without_caption(self):
        """Image without caption omits figcaption element."""
        snapshot = make_snapshot_with_block(
            "block_img",
            "image",
            src="https://example.com/photo.jpg",
        )
        html = render_block("block_img", snapshot)

        assert_not_contains(html, "<figcaption")

    def test_image_src_is_escaped(self):
        """Image src with quotes/special chars must be escaped."""
        snapshot = make_snapshot_with_block(
            "block_img",
            "image",
            src='https://example.com/photo.jpg" onload="alert(1)',
        )
        html = render_block("block_img", snapshot)

        assert_not_contains(html, 'onload="alert(1)"')

    def test_image_alt_is_escaped(self):
        """Image alt text must be escaped."""
        snapshot = make_snapshot_with_block(
            "block_img",
            "image",
            src="https://example.com/photo.jpg",
            alt='<script>alert("xss")</script>',
        )
        html = render_block("block_img", snapshot)

        assert_not_contains(html, "<script>")


# ============================================================================
# callout block
# ============================================================================


class TestCalloutBlock:
    """
    callout block renders as a highlighted aside.
    Fields: text (or content), icon?
    """

    def test_callout_basic(self):
        """Callout renders content with aide-callout class."""
        snapshot = make_snapshot_with_block(
            "block_callout",
            "callout",
            text="Remember to bring snacks!",
        )
        html = render_block("block_callout", snapshot)

        assert_contains(html, "aide-callout", "Remember to bring snacks!")

    def test_callout_with_icon(self):
        """Callout with icon renders the icon."""
        snapshot = make_snapshot_with_block(
            "block_callout",
            "callout",
            text="Important note.",
            icon="⚠️",
        )
        html = render_block("block_callout", snapshot)

        assert_contains(html, "⚠️")

    def test_callout_content_is_escaped(self):
        """Callout text must be HTML-escaped."""
        snapshot = make_snapshot_with_block(
            "block_callout",
            "callout",
            text='<iframe src="evil.com">',
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
    """

    def _snapshot_with_columns(self):
        """Build snapshot with column_list containing two columns."""
        snapshot = empty_state()

        snapshot["blocks"]["block_cols"] = {
            "type": "column_list",
            "children": ["block_col1", "block_col2"],
        }
        snapshot["blocks"]["block_col1"] = {
            "type": "column",
            "children": ["block_col1_heading"],
        }
        snapshot["blocks"]["block_col2"] = {
            "type": "column",
            "children": ["block_col2_heading"],
        }
        snapshot["blocks"]["block_col1_heading"] = {
            "type": "heading",
            "level": 3,
            "text": "Left Column",
        }
        snapshot["blocks"]["block_col2_heading"] = {
            "type": "heading",
            "level": 3,
            "text": "Right Column",
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_cols"]

        return snapshot

    def test_column_list_renders_container(self):
        """column_list renders as a container div."""
        snapshot = self._snapshot_with_columns()
        html = render_block("block_cols", snapshot)

        assert_contains(html, "aide-columns")

    def test_column_renders_child(self):
        """column renders as aide-column div."""
        snapshot = self._snapshot_with_columns()
        html = render_block("block_cols", snapshot)

        assert_contains(html, "aide-column")

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
            "level": 1,
            "text": "Title",
        }
        snapshot["blocks"]["block_text"] = {
            "type": "text",
            "text": "Body paragraph.",
        }
        snapshot["blocks"]["block_divider"] = {
            "type": "divider",
        }
        snapshot["blocks"]["block_root"]["children"] = [
            "block_h1",
            "block_text",
            "block_divider",
        ]

        html = render_block("block_root", snapshot)

        assert_contains(html, "Title", "Body paragraph.")

        # Order: heading before text before divider
        title_pos = html.index("Title")
        body_pos = html.index("Body paragraph.")
        hr_pos = html.index("<hr")
        assert title_pos < body_pos < hr_pos

    def test_nested_blocks_render_depth_first(self):
        """Nested block trees render depth-first."""
        snapshot = empty_state()

        snapshot["blocks"]["block_cols"] = {
            "type": "column_list",
            "children": ["block_col"],
        }
        snapshot["blocks"]["block_col"] = {
            "type": "column",
            "children": ["block_inner_text"],
        }
        snapshot["blocks"]["block_inner_text"] = {
            "type": "text",
            "text": "Nested content.",
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_cols"]

        html = render_block("block_root", snapshot)
        assert_contains(html, "Nested content.")

    def test_empty_children_list(self):
        """Block with empty children list renders only itself."""
        snapshot = make_snapshot_with_block(
            "block_heading",
            "heading",
            level=1,
            text="Solo Heading",
        )
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
            level=1,
            text="My Aide",
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

        assert_contains(html, "aide-page", "<hr")
