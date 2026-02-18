"""
AIde Renderer -- Inline Formatting Tests (v3 Unified Entity Model)

Bold, italic, link in text blocks. Verify HTML output.
Also verify XSS attempts are escaped.

Inline formatting rules (text blocks ONLY):
  **bold**        → <strong>bold</strong>
  *italic*        → <em>italic</em>
  [text](url)     → <a href="url">text</a>

Reference: aide_renderer_spec.md (Block Rendering → text, HTML Sanitization)
"""

from engine.kernel.reducer import empty_state
from engine.kernel.renderer import render_block


def assert_contains(html, *fragments):
    for fragment in fragments:
        assert fragment in html, (
            f"Expected to find {fragment!r} in rendered HTML.\nGot (first 3000 chars):\n{html[:3000]}"
        )


def assert_not_contains(html, *fragments):
    for fragment in fragments:
        assert fragment not in html, f"Did NOT expect to find {fragment!r} in rendered HTML."


def make_text_block(content):
    """Build a snapshot with a single text block containing content."""
    snapshot = empty_state()
    block_id = "block_text"
    snapshot["blocks"][block_id] = {"type": "text", "text": content}
    snapshot["blocks"]["block_root"]["children"] = [block_id]
    return snapshot, block_id


class TestBoldFormatting:
    """**text** → <strong>text</strong>"""

    def test_bold_word(self):
        snapshot, bid = make_text_block("This is **important** info.")
        html = render_block(bid, snapshot)
        assert_contains(html, "<strong>important</strong>")
        assert_not_contains(html, "**important**")

    def test_bold_phrase(self):
        snapshot, bid = make_text_block("**Game night** is Friday.")
        html = render_block(bid, snapshot)
        assert_contains(html, "<strong>Game night</strong>")

    def test_bold_at_start(self):
        snapshot, bid = make_text_block("**Bold** text at start.")
        html = render_block(bid, snapshot)
        assert_contains(html, "<strong>Bold</strong>")

    def test_bold_at_end(self):
        snapshot, bid = make_text_block("Text at **end**.")
        html = render_block(bid, snapshot)
        assert_contains(html, "<strong>end</strong>")

    def test_multiple_bold(self):
        snapshot, bid = make_text_block("**One** and **two** bold words.")
        html = render_block(bid, snapshot)
        assert_contains(html, "<strong>One</strong>")
        assert_contains(html, "<strong>two</strong>")

    def test_no_bold_markers(self):
        snapshot, bid = make_text_block("No formatting here.")
        html = render_block(bid, snapshot)
        assert_not_contains(html, "<strong>")

    def test_bold_with_special_chars(self):
        snapshot, bid = make_text_block("**Important: $500!**")
        html = render_block(bid, snapshot)
        assert_contains(html, "<strong>")


class TestItalicFormatting:
    """*text* → <em>text</em>"""

    def test_italic_word(self):
        snapshot, bid = make_text_block("This is *emphasized* text.")
        html = render_block(bid, snapshot)
        assert_contains(html, "<em>emphasized</em>")
        assert_not_contains(html, "*emphasized*")

    def test_italic_phrase(self):
        snapshot, bid = make_text_block("*Poker night* is cancelled.")
        html = render_block(bid, snapshot)
        assert_contains(html, "<em>Poker night</em>")

    def test_italic_at_start(self):
        snapshot, bid = make_text_block("*Italic* at start.")
        html = render_block(bid, snapshot)
        assert_contains(html, "<em>Italic</em>")

    def test_italic_at_end(self):
        snapshot, bid = make_text_block("Text at *end*.")
        html = render_block(bid, snapshot)
        assert_contains(html, "<em>end</em>")

    def test_multiple_italic(self):
        snapshot, bid = make_text_block("*First* and *second* italic.")
        html = render_block(bid, snapshot)
        assert_contains(html, "<em>First</em>")
        assert_contains(html, "<em>second</em>")

    def test_no_italic_markers(self):
        snapshot, bid = make_text_block("No formatting.")
        html = render_block(bid, snapshot)
        assert_not_contains(html, "<em>")


class TestLinkFormatting:
    """[text](url) → <a href="url">text</a>"""

    def test_link_basic(self):
        snapshot, bid = make_text_block("Visit [our site](https://toaide.com) today.")
        html = render_block(bid, snapshot)
        assert_contains(html, '<a href="https://toaide.com"')
        assert_contains(html, "our site</a>")

    def test_link_http(self):
        snapshot, bid = make_text_block("[Click here](http://example.com)")
        html = render_block(bid, snapshot)
        assert_contains(html, 'href="http://example.com"')

    def test_link_text_displayed(self):
        snapshot, bid = make_text_block("[Read more](https://example.com)")
        html = render_block(bid, snapshot)
        assert_contains(html, ">Read more<")

    def test_link_in_sentence(self):
        snapshot, bid = make_text_block("See [the docs](https://docs.example.com) for details.")
        html = render_block(bid, snapshot)
        assert_contains(html, "See ")
        assert_contains(html, 'href="https://docs.example.com"')
        assert_contains(html, " for details.")

    def test_multiple_links(self):
        snapshot, bid = make_text_block("[One](https://one.com) and [Two](https://two.com).")
        html = render_block(bid, snapshot)
        assert_contains(html, 'href="https://one.com"')
        assert_contains(html, 'href="https://two.com"')

    def test_link_text_escaped(self):
        snapshot, bid = make_text_block("[<script>](https://example.com)")
        html = render_block(bid, snapshot)
        assert_not_contains(html, "<script>")

    def test_no_link_without_url(self):
        snapshot, bid = make_text_block("Just [text] without a URL.")
        html = render_block(bid, snapshot)
        assert_not_contains(html, "<a href")


class TestXSSEscaping:
    """HTML content must be escaped to prevent XSS."""

    def test_script_tag_escaped(self):
        snapshot, bid = make_text_block('<script>alert("xss")</script>')
        html = render_block(bid, snapshot)
        assert_not_contains(html, "<script>")
        assert_contains(html, "&lt;script&gt;")

    def test_img_onerror_escaped(self):
        snapshot, bid = make_text_block('<img src=x onerror=alert(1)>')
        html = render_block(bid, snapshot)
        assert_not_contains(html, "<img")
        assert_contains(html, "&lt;img")

    def test_iframe_escaped(self):
        snapshot, bid = make_text_block('<iframe src="evil.com"></iframe>')
        html = render_block(bid, snapshot)
        assert_not_contains(html, "<iframe")

    def test_event_handler_escaped(self):
        snapshot, bid = make_text_block('<p onclick="evil()">Click me</p>')
        html = render_block(bid, snapshot)
        # The raw <p onclick tag must be escaped
        assert_not_contains(html, "<p onclick")
        # The text 'onclick' may appear escaped as &quot; etc., that's fine
        assert "evil()" not in html or "&quot;evil()&quot;" in html

    def test_ampersand_escaped(self):
        snapshot, bid = make_text_block("Fish & chips")
        html = render_block(bid, snapshot)
        assert_contains(html, "&amp;")
        assert_not_contains(html, "Fish & chips")  # raw & should be escaped

    def test_angle_brackets_escaped(self):
        snapshot, bid = make_text_block("Score: 5 > 3 and 2 < 4")
        html = render_block(bid, snapshot)
        assert_contains(html, "&gt;")
        assert_contains(html, "&lt;")

    def test_quote_in_content(self):
        snapshot, bid = make_text_block('He said "hello" to her.')
        html = render_block(bid, snapshot)
        # Quotes should be present (rendered safe since it's inside <p> content)
        assert "hello" in html


class TestCombinedFormatting:
    """Bold, italic, and links can be combined."""

    def test_bold_and_italic(self):
        snapshot, bid = make_text_block("**Bold** and *italic*.")
        html = render_block(bid, snapshot)
        assert_contains(html, "<strong>Bold</strong>")
        assert_contains(html, "<em>italic</em>")

    def test_bold_and_link(self):
        snapshot, bid = make_text_block("**Click** [here](https://example.com).")
        html = render_block(bid, snapshot)
        assert_contains(html, "<strong>Click</strong>")
        assert_contains(html, 'href="https://example.com"')

    def test_plain_text_unchanged(self):
        content = "Just a plain sentence with no formatting."
        snapshot, bid = make_text_block(content)
        html = render_block(bid, snapshot)
        assert_contains(html, content)
        assert_not_contains(html, "<strong>")
        assert_not_contains(html, "<em>")
        assert_not_contains(html, "<a href")


class TestHeadingBlockContent:
    """Heading blocks use escape but NOT inline markdown formatting."""

    def test_heading_content_not_formatted(self):
        """Headings do not apply bold/italic markdown."""
        snapshot = empty_state()
        snapshot["blocks"]["block_h"] = {
            "type": "heading",
            "level": 1,
            "text": "**Bold** Title",
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_h"]
        html = render_block("block_h", snapshot)

        # Heading content is escaped, not markdown-processed
        assert_contains(html, "**Bold** Title")
        assert_not_contains(html, "<strong>Bold</strong>")

    def test_heading_html_escaped(self):
        """Heading HTML chars are escaped."""
        snapshot = empty_state()
        snapshot["blocks"]["block_h"] = {
            "type": "heading",
            "level": 2,
            "text": "<evil>Heading</evil>",
        }
        snapshot["blocks"]["block_root"]["children"] = ["block_h"]
        html = render_block("block_h", snapshot)

        assert_not_contains(html, "<evil>")
        assert_contains(html, "&lt;evil&gt;")
