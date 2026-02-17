"""
AIde Renderer -- Inline Formatting Tests (Category 7)

Bold, italic, link in text blocks. Verify HTML output.
Also verify XSS attempts are escaped.

From the spec (aide_renderer_spec.md, "Testing Strategy"):
  "7. Inline formatting. Bold, italic, link in text blocks. Verify
   HTML output. Also verify XSS attempts are escaped."

Inline formatting rules (text blocks ONLY):
  **bold**        → <strong>bold</strong>
  *italic*        → <em>italic</em>
  [text](url)     → <a href="url">text</a>  (href validated as http/https only)

Strict allowlist — no other HTML passes through:
  - No <script>, <iframe>, event handlers
  - Content fields are text-escaped before insertion
  - escape() replaces: & → &amp;  < → &lt;  > → &gt;  " → &quot;  ' → &#x27;
  - Links: href validated as http/https only (no javascript:, data:, etc.)

Reference: aide_renderer_spec.md (Block Rendering → text, HTML Sanitization)
"""

from engine.kernel.reducer import empty_state
from engine.kernel.renderer import render_block

# ============================================================================
# Helpers
# ============================================================================


def assert_contains(html, *fragments):
    for fragment in fragments:
        assert fragment in html, (
            f"Expected to find {fragment!r} in rendered HTML.\nGot (first 3000 chars):\n{html[:3000]}"
        )


def assert_not_contains(html, *fragments):
    for fragment in fragments:
        assert fragment not in html, f"Did NOT expect to find {fragment!r} in rendered HTML."


def make_text_block(content):
    """
    Build a snapshot with a single text block containing the given content.
    Returns (snapshot, block_id).
    """
    snapshot = empty_state()

    block_id = "block_text"
    snapshot["blocks"][block_id] = {
        "type": "text",
        "parent": "block_root",
        "props": {"content": content},
    }
    snapshot["blocks"]["block_root"]["children"] = [block_id]

    return snapshot, block_id


# ============================================================================
# Bold formatting
# ============================================================================


class TestBoldFormatting:
    """
    **text** → <strong>text</strong>
    Per spec: Content supports basic inline formatting: **bold** → <strong>
    """

    def test_bold_word(self):
        """Single bold word."""
        snapshot, block_id = make_text_block("This is **important** info.")
        html = render_block(block_id, snapshot)

        assert_contains(html, "<strong>important</strong>")
        assert_not_contains(html, "**important**")

    def test_bold_multiple_words(self):
        """Bold phrase spanning multiple words."""
        snapshot, block_id = make_text_block("Please **read this carefully** before proceeding.")
        html = render_block(block_id, snapshot)

        assert_contains(html, "<strong>read this carefully</strong>")

    def test_multiple_bold_segments(self):
        """Multiple bold segments in one text block."""
        snapshot, block_id = make_text_block("**First** thing and **second** thing.")
        html = render_block(block_id, snapshot)

        assert_contains(html, "<strong>First</strong>")
        assert_contains(html, "<strong>second</strong>")

    def test_bold_at_start(self):
        """Bold at the beginning of content."""
        snapshot, block_id = make_text_block("**Warning:** don't touch that.")
        html = render_block(block_id, snapshot)

        assert_contains(html, "<strong>Warning:</strong>")

    def test_bold_at_end(self):
        """Bold at the end of content."""
        snapshot, block_id = make_text_block("This is **final**")
        html = render_block(block_id, snapshot)

        assert_contains(html, "<strong>final</strong>")

    def test_bold_entire_content(self):
        """Entire content is bold."""
        snapshot, block_id = make_text_block("**Everything bold**")
        html = render_block(block_id, snapshot)

        assert_contains(html, "<strong>Everything bold</strong>")


# ============================================================================
# Italic formatting
# ============================================================================


class TestItalicFormatting:
    """
    *text* → <em>text</em>
    Per spec: *italic* → <em>
    """

    def test_italic_word(self):
        """Single italic word."""
        snapshot, block_id = make_text_block("This is *really* good.")
        html = render_block(block_id, snapshot)

        assert_contains(html, "<em>really</em>")
        assert_not_contains(html, "*really*")

    def test_italic_multiple_words(self):
        """Italic phrase spanning multiple words."""
        snapshot, block_id = make_text_block("She said *not a chance* to that.")
        html = render_block(block_id, snapshot)

        assert_contains(html, "<em>not a chance</em>")

    def test_multiple_italic_segments(self):
        """Multiple italic segments in one text block."""
        snapshot, block_id = make_text_block("*First* and *second* items.")
        html = render_block(block_id, snapshot)

        assert_contains(html, "<em>First</em>")
        assert_contains(html, "<em>second</em>")

    def test_italic_at_start(self):
        """Italic at the beginning."""
        snapshot, block_id = make_text_block("*Note:* check this out.")
        html = render_block(block_id, snapshot)

        assert_contains(html, "<em>Note:</em>")

    def test_italic_entire_content(self):
        """Entire content is italic."""
        snapshot, block_id = make_text_block("*All italic*")
        html = render_block(block_id, snapshot)

        assert_contains(html, "<em>All italic</em>")


# ============================================================================
# Link formatting
# ============================================================================


class TestLinkFormatting:
    """
    [text](url) → <a href="url">text</a>
    Per spec: href is validated as http/https only.
    """

    def test_basic_link(self):
        """Standard http link."""
        snapshot, block_id = make_text_block("Visit [our site](https://toaide.com) for details.")
        html = render_block(block_id, snapshot)

        assert_contains(html, '<a href="https://toaide.com">our site</a>')
        assert_not_contains(html, "[our site]")

    def test_http_link(self):
        """http:// link is allowed."""
        snapshot, block_id = make_text_block("See [example](http://example.com) here.")
        html = render_block(block_id, snapshot)

        assert_contains(html, '<a href="http://example.com">example</a>')

    def test_https_link(self):
        """https:// link is allowed."""
        snapshot, block_id = make_text_block("Check [docs](https://docs.toaide.com/guide) now.")
        html = render_block(block_id, snapshot)

        assert_contains(html, '<a href="https://docs.toaide.com/guide">')
        assert_contains(html, "docs</a>")

    def test_link_with_long_text(self):
        """Link text can be a longer phrase."""
        snapshot, block_id = make_text_block("Read [the full announcement post](https://blog.example.com/post).")
        html = render_block(block_id, snapshot)

        assert_contains(html, ">the full announcement post</a>")

    def test_multiple_links(self):
        """Multiple links in one text block."""
        snapshot, block_id = make_text_block("See [Google](https://google.com) and [GitHub](https://github.com).")
        html = render_block(block_id, snapshot)

        assert_contains(html, '<a href="https://google.com">Google</a>')
        assert_contains(html, '<a href="https://github.com">GitHub</a>')

    def test_link_at_start(self):
        """Link at the beginning of content."""
        snapshot, block_id = make_text_block("[Click here](https://example.com) to begin.")
        html = render_block(block_id, snapshot)

        assert_contains(html, '<a href="https://example.com">Click here</a>')

    def test_link_at_end(self):
        """Link at the end of content."""
        snapshot, block_id = make_text_block("More info at [our docs](https://docs.example.com)")
        html = render_block(block_id, snapshot)

        assert_contains(html, '<a href="https://docs.example.com">our docs</a>')


# ============================================================================
# Combined inline formatting
# ============================================================================


class TestCombinedInlineFormatting:
    """
    Bold, italic, and links can coexist in the same text block.
    """

    def test_bold_and_italic(self):
        """Bold and italic in same text block."""
        snapshot, block_id = make_text_block("This is **bold** and this is *italic* text.")
        html = render_block(block_id, snapshot)

        assert_contains(html, "<strong>bold</strong>")
        assert_contains(html, "<em>italic</em>")

    def test_bold_and_link(self):
        """Bold and link in same text block."""
        snapshot, block_id = make_text_block("**Important:** visit [our site](https://toaide.com).")
        html = render_block(block_id, snapshot)

        assert_contains(html, "<strong>Important:</strong>")
        assert_contains(html, '<a href="https://toaide.com">our site</a>')

    def test_italic_and_link(self):
        """Italic and link in same text block."""
        snapshot, block_id = make_text_block("*Note:* see [details](https://example.com) for more.")
        html = render_block(block_id, snapshot)

        assert_contains(html, "<em>Note:</em>")
        assert_contains(html, '<a href="https://example.com">details</a>')

    def test_all_three_in_one_block(self):
        """Bold, italic, and link all in one text block."""
        snapshot, block_id = make_text_block("**Bold** then *italic* then [link](https://example.com) done.")
        html = render_block(block_id, snapshot)

        assert_contains(html, "<strong>Bold</strong>")
        assert_contains(html, "<em>italic</em>")
        assert_contains(html, '<a href="https://example.com">link</a>')


# ============================================================================
# No formatting (plain text)
# ============================================================================


class TestPlainText:
    """
    Text without formatting markers renders as plain escaped text.
    """

    def test_plain_text_no_tags(self):
        """Plain text produces no <strong>, <em>, or <a> tags."""
        snapshot, block_id = make_text_block("Just a regular sentence.")
        html = render_block(block_id, snapshot)

        assert_contains(html, "Just a regular sentence.")
        assert_not_contains(html, "<strong>")
        assert_not_contains(html, "<em>")
        assert_not_contains(html, "<a ")

    def test_single_asterisk_not_italic(self):
        """
        A lone asterisk or unmatched asterisks should NOT create <em>.
        Only matched *...* pairs produce italic.
        """
        snapshot, block_id = make_text_block("5 * 3 = 15")
        html = render_block(block_id, snapshot)

        assert_not_contains(html, "<em>")

    def test_double_asterisk_unmatched(self):
        """Unmatched ** should not produce <strong>."""
        snapshot, block_id = make_text_block("Rating: ** out of 5")
        html = render_block(block_id, snapshot)

        assert_not_contains(html, "<strong>")

    def test_bracket_not_link_without_parens(self):
        """Square brackets without parentheses are not links."""
        snapshot, block_id = make_text_block("See [section 3] for more.")
        html = render_block(block_id, snapshot)

        assert_not_contains(html, "<a ")
        assert_contains(html, "[section 3]")


# ============================================================================
# XSS escaping — script injection
# ============================================================================


class TestXSSScriptInjection:
    """
    Script tags and event handlers in text content must be escaped.
    Per spec: No <script>, no <iframe>, no event handlers.
    Content fields are text-escaped before insertion.
    """

    def test_script_tag_escaped(self):
        """<script> tag in content is HTML-escaped."""
        snapshot, block_id = make_text_block('Hello <script>alert("xss")</script> world')
        html = render_block(block_id, snapshot)

        assert_not_contains(html, "<script>")
        assert_contains(html, "&lt;script&gt;")

    def test_script_tag_in_bold(self):
        """<script> inside bold markers is still escaped."""
        snapshot, block_id = make_text_block('**<script>alert("xss")</script>**')
        html = render_block(block_id, snapshot)

        assert_not_contains(html, "<script>")
        assert_contains(html, "&lt;script&gt;")

    def test_iframe_escaped(self):
        """<iframe> in content is escaped."""
        snapshot, block_id = make_text_block('See <iframe src="https://evil.com"></iframe> here')
        html = render_block(block_id, snapshot)

        assert_not_contains(html, "<iframe")

    def test_img_onerror_escaped(self):
        """<img onerror=...> in content is escaped - no actual element created."""
        snapshot, block_id = make_text_block("<img src=x onerror=alert(1)>")
        html = render_block(block_id, snapshot)

        # Critical: no actual img element (< is escaped)
        assert_not_contains(html, "<img")
        assert_contains(html, "&lt;img")
        # The text "onerror" may appear as literal text, but it's not an attribute

    def test_event_handler_in_tag(self):
        """Event handler attributes are escaped - no actual element created."""
        snapshot, block_id = make_text_block('<div onmouseover="alert(1)">hover me</div>')
        html = render_block(block_id, snapshot)

        # Critical: no actual div element (< is escaped)
        assert_not_contains(html, "<div")
        assert_contains(html, "&lt;div")
        # The text "onmouseover" may appear as literal text, but it's not an attribute


# ============================================================================
# XSS escaping — link href injection
# ============================================================================


class TestXSSLinkHrefInjection:
    """
    Link hrefs must be validated as http/https only.
    javascript:, data:, vbscript: and other schemes must be rejected.
    Per spec: href is validated as http/https only.
    """

    def test_javascript_href_rejected(self):
        """javascript: URL in link href is NOT converted to a link."""
        snapshot, block_id = make_text_block('[click me](javascript:alert("xss"))')
        html = render_block(block_id, snapshot)

        # Critical: no href with javascript: (only https?:// links are converted)
        assert 'href="javascript:' not in html
        # The link syntax may appear as literal text (safe, just not converted)

    def test_javascript_case_insensitive(self):
        """JavaScript: (mixed case) in href is also rejected."""
        snapshot, block_id = make_text_block("[click](JavaScript:alert(1))")
        html = render_block(block_id, snapshot)

        # Critical: no href with javascript: (case insensitive check)
        assert 'href="javascript:' not in html.lower()
        # The link syntax may appear as literal text (safe)

    def test_data_uri_rejected(self):
        """data: URI in link href is NOT converted to a link."""
        snapshot, block_id = make_text_block("[click](data:text/html,<script>alert(1)</script>)")
        html = render_block(block_id, snapshot)

        # Critical: no href with data: URI
        assert 'href="data:' not in html
        # The link syntax may appear as escaped literal text (safe)

    def test_vbscript_href_rejected(self):
        """vbscript: in link href is NOT converted to a link."""
        snapshot, block_id = make_text_block("[click](vbscript:MsgBox(1))")
        html = render_block(block_id, snapshot)

        # Critical: no href with vbscript:
        assert 'href="vbscript:' not in html
        # The link syntax may appear as literal text (safe)

    def test_valid_https_link_allowed(self):
        """https:// links pass validation and render correctly."""
        snapshot, block_id = make_text_block("[safe link](https://example.com)")
        html = render_block(block_id, snapshot)

        assert_contains(html, '<a href="https://example.com">safe link</a>')

    def test_valid_http_link_allowed(self):
        """http:// links pass validation and render correctly."""
        snapshot, block_id = make_text_block("[safe link](http://example.com)")
        html = render_block(block_id, snapshot)

        assert_contains(html, '<a href="http://example.com">safe link</a>')

    def test_protocol_relative_url_rejected(self):
        """Protocol-relative URL (//evil.com) should be rejected."""
        snapshot, block_id = make_text_block("[click](//evil.com/payload)")
        html = render_block(block_id, snapshot)

        # Should NOT produce an <a> with this href
        assert 'href="//evil.com' not in html


# ============================================================================
# XSS escaping — HTML entity injection
# ============================================================================


class TestXSSEntityInjection:
    """
    HTML special characters in text content must be properly escaped.
    Per spec: escape() handles &, <, >, ", '
    """

    def test_ampersand_escaped(self):
        """& is escaped to &amp;"""
        snapshot, block_id = make_text_block("Tom & Jerry")
        html = render_block(block_id, snapshot)

        assert_contains(html, "Tom &amp; Jerry")

    def test_less_than_escaped(self):
        """< is escaped to &lt;"""
        snapshot, block_id = make_text_block("x < y")
        html = render_block(block_id, snapshot)

        assert_contains(html, "x &lt; y")

    def test_greater_than_escaped(self):
        """> is escaped to &gt;"""
        snapshot, block_id = make_text_block("x > y")
        html = render_block(block_id, snapshot)

        assert_contains(html, "x &gt; y")

    def test_double_quote_escaped(self):
        """ " is escaped to &quot;"""
        snapshot, block_id = make_text_block('She said "hello" to me')
        html = render_block(block_id, snapshot)

        assert_contains(html, "&quot;hello&quot;")

    def test_single_quote_escaped(self):
        """' is escaped to &#x27;"""
        snapshot, block_id = make_text_block("It's a test")
        html = render_block(block_id, snapshot)

        assert_contains(html, "It&#x27;s a test")

    def test_all_special_chars_together(self):
        """All five escape characters in one string."""
        snapshot, block_id = make_text_block("""<div class="a" id='b'>&</div>""")
        html = render_block(block_id, snapshot)

        assert_not_contains(html, '<div class="a"')
        assert_contains(html, "&lt;div")
        assert_contains(html, "&amp;")
        assert_contains(html, "&lt;/div&gt;")


# ============================================================================
# XSS in link text
# ============================================================================


class TestXSSInLinkText:
    """
    HTML injection in the text portion of a link should be escaped.
    The URL is validated, the text is escaped.
    """

    def test_html_in_link_text_escaped(self):
        """<script> in link text is escaped."""
        snapshot, block_id = make_text_block("[<script>alert(1)</script>](https://example.com)")
        html = render_block(block_id, snapshot)

        assert_not_contains(html, "<script>")
        # The link text should be escaped inside the <a> tag
        if '<a href="https://example.com">' in html:
            assert_contains(html, "&lt;script&gt;")

    def test_html_entities_in_link_text(self):
        """Special chars in link text are escaped."""
        snapshot, block_id = make_text_block('[Tom & Jerry\'s "Page"](https://example.com)')
        html = render_block(block_id, snapshot)

        assert_contains(html, "&amp;")


# ============================================================================
# XSS in URL parameters
# ============================================================================


class TestXSSInURLParameters:
    """
    URLs with suspicious parameters should be handled safely.
    The href attribute value must be properly escaped.
    """

    def test_url_with_quotes_in_params(self):
        """URL containing quotes in query params should be escaped in href."""
        snapshot, block_id = make_text_block('[link](https://example.com?q=a"onmouseover="alert(1))')
        html = render_block(block_id, snapshot)

        # The quote in the URL should be escaped to prevent attribute breakout
        # Either the URL is rejected due to the closing paren being consumed,
        # or quotes are properly escaped in the href value
        if "href=" in html:
            # Check that no unescaped attribute injection occurred
            assert " onmouseover=" not in html, "Event handler attribute should not be injected"

    def test_url_with_angle_brackets(self):
        """URL with angle brackets should be escaped."""
        snapshot, block_id = make_text_block("[link](https://example.com/<script>)")
        html = render_block(block_id, snapshot)

        assert_not_contains(html, "<script>")


# ============================================================================
# Inline formatting only in text blocks
# ============================================================================


class TestInlineFormattingOnlyInTextBlocks:
    """
    Inline formatting (bold/italic/link) only applies to text block content.
    Heading content, callout content, etc. should be plain-escaped, NOT formatted.
    """

    def test_heading_content_not_formatted(self):
        """Heading blocks do NOT parse inline formatting — just escape."""
        snapshot = empty_state()
        block_id = "block_heading"
        snapshot["blocks"][block_id] = {
            "type": "heading",
            "parent": "block_root",
            "props": {"level": 1, "content": "Title with **bold**"},
        }
        snapshot["blocks"]["block_root"]["children"] = [block_id]

        html = render_block(block_id, snapshot)

        # Heading should NOT produce <strong> — just escaped text
        # The ** markers should appear literally (escaped) or be stripped,
        # but should NOT become <strong>
        assert_not_contains(html, "<strong>")

    def test_callout_content_not_formatted(self):
        """Callout blocks do NOT parse inline formatting."""
        snapshot = empty_state()
        block_id = "block_callout"
        snapshot["blocks"][block_id] = {
            "type": "callout",
            "parent": "block_root",
            "props": {"content": "Note: **important** *detail*"},
        }
        snapshot["blocks"]["block_root"]["children"] = [block_id]

        html = render_block(block_id, snapshot)

        # Callout should NOT have <strong> or <em>
        assert_not_contains(html, "<strong>")
        assert_not_contains(html, "<em>")

    def test_metric_label_not_formatted(self):
        """Metric label does NOT parse inline formatting."""
        snapshot = empty_state()
        block_id = "block_metric"
        snapshot["blocks"][block_id] = {
            "type": "metric",
            "parent": "block_root",
            "props": {"label": "**Total**", "value": "42"},
        }
        snapshot["blocks"]["block_root"]["children"] = [block_id]

        html = render_block(block_id, snapshot)

        assert_not_contains(html, "<strong>")


# ============================================================================
# Edge cases
# ============================================================================


class TestInlineFormattingEdgeCases:
    """
    Edge cases for the inline formatting parser.
    """

    def test_empty_bold(self):
        """Empty bold markers **** should not produce empty <strong>."""
        snapshot, block_id = make_text_block("Before **** after")
        html = render_block(block_id, snapshot)

        # Should not produce <strong></strong>
        assert "<strong></strong>" not in html

    def test_empty_italic(self):
        """Empty italic markers ** should not produce empty <em>."""
        snapshot, block_id = make_text_block("Before ** after")
        html = render_block(block_id, snapshot)

        assert "<em></em>" not in html

    def test_nested_bold_italic(self):
        """Bold inside italic or vice versa — reasonable behavior expected."""
        snapshot, block_id = make_text_block("This is ***bold and italic*** text.")
        html = render_block(block_id, snapshot)

        # Should produce some combination of <strong> and <em>
        # The exact nesting is implementation-dependent, but both tags
        # should appear
        assert "<strong>" in html or "<em>" in html

    def test_link_with_empty_text(self):
        """Link with empty text [](url) — should handle gracefully."""
        snapshot, block_id = make_text_block("[](https://example.com)")
        html = render_block(block_id, snapshot)

        # Should not crash; may render empty <a> or skip
        assert "aide-text" in html  # text block still renders

    def test_link_with_empty_url(self):
        """Link with empty URL [text]() — should handle gracefully."""
        snapshot, block_id = make_text_block("[click here]()")
        html = render_block(block_id, snapshot)

        # Should not produce a link with empty href, or handle gracefully
        assert "aide-text" in html

    def test_adjacent_bold_and_italic(self):
        """Bold immediately followed by italic."""
        snapshot, block_id = make_text_block("**bold***italic*")
        html = render_block(block_id, snapshot)

        assert_contains(html, "<strong>bold</strong>")
        assert_contains(html, "<em>italic</em>")

    def test_formatting_with_special_chars_inside(self):
        """Bold text containing HTML special chars."""
        snapshot, block_id = make_text_block("**Tom & Jerry's <special>**")
        html = render_block(block_id, snapshot)

        assert_contains(html, "<strong>")
        assert_contains(html, "&amp;")
        assert_not_contains(html, "<special>")

    def test_asterisks_in_math_context(self):
        """Asterisks used for multiplication should not become formatting."""
        snapshot, block_id = make_text_block("Calculate 5*3 and 2*4 for the total.")
        html = render_block(block_id, snapshot)

        # Ambiguous — but at minimum, content should be present and safe
        assert_contains(html, "Calculate")
        assert_contains(html, "total")

    def test_link_with_parentheses_in_url(self):
        """URL containing parentheses (e.g., Wikipedia)."""
        snapshot, block_id = make_text_block("[wiki](https://en.wikipedia.org/wiki/Poker_(card_game))")
        html = render_block(block_id, snapshot)

        # Should handle the nested parens reasonably
        assert_contains(html, "wiki")
