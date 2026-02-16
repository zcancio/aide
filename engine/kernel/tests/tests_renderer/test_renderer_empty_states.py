"""
AIde Renderer -- Empty State Tests (Category 8)

No blocks, empty collection, missing view.

From the spec (aide_renderer_spec.md, "Testing Strategy"):
  "8. Empty states. No blocks, empty collection, missing view."

Three empty state patterns from spec:

1. No blocks (only block_root with empty children):
   <main class="aide-page">
     <p class="aide-empty">This page is empty.</p>
   </main>

2. Empty collection (view exists but collection has no non-removed entities):
   <p class="aide-collection-empty">No items yet.</p>

3. Missing view (block references a view that doesn't exist):
   Fall back to a default table view of the collection.
   If the collection also doesn't exist, render nothing.

Additional from render_collection_view():
   if not view or not collection:
       return render_empty_block()

Reference: aide_renderer_spec.md (Empty States, View Rendering)
"""


from engine.kernel.reducer import empty_state
from engine.kernel.renderer import render, render_block
from engine.kernel.types import Blueprint

# ============================================================================
# Helpers
# ============================================================================


def assert_contains(html, *fragments):
    for fragment in fragments:
        assert fragment in html, (
            f"Expected to find {fragment!r} in rendered HTML.\n"
            f"Got (first 3000 chars):\n{html[:3000]}"
        )


def assert_not_contains(html, *fragments):
    for fragment in fragments:
        assert fragment not in html, (
            f"Did NOT expect to find {fragment!r} in rendered HTML."
        )


def extract_main(html):
    """Extract content within <main> tags only (avoids CSS)."""
    import re
    match = re.search(r'<main[^>]*>(.*?)</main>', html, re.DOTALL)
    return match.group(1) if match else ""


def assert_not_in_main(html, *fragments):
    """Assert fragments do NOT appear within <main> content."""
    main = extract_main(html)
    for fragment in fragments:
        assert fragment not in main, (
            f"Did NOT expect to find {fragment!r} in <main> content."
        )


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
    No blocks (only block_root with empty children).
    Per spec: renders <p class="aide-empty">This page is empty.</p>
    inside <main class="aide-page">.
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
        # The empty message should be between <main> tags
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

    def test_empty_page_no_block_html(self):
        """Empty page should have no heading, text, metric, or collection HTML in <main>."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Empty"}

        html = render(snapshot, make_blueprint())

        # Check within <main> only (CSS still has class definitions)
        assert_not_in_main(html, "aide-heading")
        assert_not_in_main(html, "aide-text")
        assert_not_in_main(html, "aide-metric")
        assert_not_in_main(html, "aide-list")
        assert_not_in_main(html, "aide-table")

    def test_block_root_with_explicit_empty_children(self):
        """block_root exists with children=[] — same as default empty state."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Empty"}
        snapshot["blocks"]["block_root"]["children"] = []

        html = render(snapshot, make_blueprint())

        assert_contains(html, "aide-empty")
        assert_contains(html, "This page is empty.")


# ============================================================================
# Empty collection — view exists, no entities
# ============================================================================


class TestEmptyCollection:
    """
    View exists but collection has no non-removed entities.
    Per spec: renders <p class="aide-collection-empty">No items yet.</p>
    """

    def _build_empty_collection_snapshot(self, view_type="list"):
        """Snapshot with a collection (no entities), view, and collection_view block."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Empty Collection"}

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
                "type": view_type,
                "source": "items",
                "config": {},
            },
        }

        block_id = "block_items"
        snapshot["blocks"][block_id] = {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "items", "view": "items_view"},
        }
        snapshot["blocks"]["block_root"]["children"] = [block_id]

        return snapshot, block_id

    def test_empty_collection_message(self):
        """Empty collection shows 'No items yet.' message."""
        snapshot, block_id = self._build_empty_collection_snapshot()
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-collection-empty")
        assert_contains(html, "No items yet.")

    def test_empty_collection_no_list_html(self):
        """Empty list view produces no <ul> or <li> elements."""
        snapshot, block_id = self._build_empty_collection_snapshot("list")
        html = render_block(block_id, snapshot)

        assert_not_contains(html, "<ul")
        assert_not_contains(html, "<li")

    def test_empty_collection_no_table_html(self):
        """Empty table view produces no <table> or <thead> elements."""
        snapshot, block_id = self._build_empty_collection_snapshot("table")
        html = render_block(block_id, snapshot)

        assert_not_contains(html, "<table")
        assert_not_contains(html, "<thead")

    def test_empty_collection_in_full_render(self):
        """Empty collection message appears in full render() output."""
        snapshot, _ = self._build_empty_collection_snapshot()
        html = render(snapshot, make_blueprint())

        assert_contains(html, "aide-collection-empty")
        assert_contains(html, "No items yet.")
        # Page should NOT show "This page is empty" because there IS a block
        assert_not_contains(html, "This page is empty.")


# ============================================================================
# All entities removed — effectively empty collection
# ============================================================================


class TestAllEntitiesRemoved:
    """
    Collection where all entities have _removed=True is effectively empty.
    Per spec: entities = [e for e in ... if not e.get("_removed")]
    """

    def test_all_removed_shows_empty_state(self):
        """Collection with only removed entities shows empty message."""
        snapshot = empty_state()

        snapshot["collections"] = {
            "items": {
                "id": "items",
                "name": "Items",
                "schema": {"name": "string"},
                "entities": {
                    "item_1": {
                        "name": "Deleted Item",
                        "_removed": True,
                    },
                    "item_2": {
                        "name": "Also Deleted",
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

        block_id = "block_items"
        snapshot["blocks"][block_id] = {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "items", "view": "items_view"},
        }
        snapshot["blocks"]["block_root"]["children"] = [block_id]

        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-collection-empty")
        assert_not_contains(html, "Deleted Item")
        assert_not_contains(html, "Also Deleted")

    def test_some_removed_some_not(self):
        """Mix of removed and non-removed: only non-removed render."""
        snapshot = empty_state()

        snapshot["collections"] = {
            "items": {
                "id": "items",
                "name": "Items",
                "schema": {"name": "string"},
                "entities": {
                    "item_alive": {
                        "name": "Still Here",
                        "_removed": False,
                    },
                    "item_dead": {
                        "name": "Gone",
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

        block_id = "block_items"
        snapshot["blocks"][block_id] = {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "items", "view": "items_view"},
        }
        snapshot["blocks"]["block_root"]["children"] = [block_id]

        html = render_block(block_id, snapshot)

        assert_contains(html, "Still Here")
        assert_not_contains(html, "Gone")
        assert_not_contains(html, "aide-collection-empty")


# ============================================================================
# Missing view — fallback behavior
# ============================================================================


class TestMissingView:
    """
    Block references a view that doesn't exist.
    Per spec: 'Fall back to a default table view of the collection.
    If the collection also doesn't exist, render nothing.'
    """

    def test_missing_view_falls_back_to_table(self):
        """
        View ID doesn't exist but collection does → default table view.
        """
        snapshot = empty_state()

        snapshot["collections"] = {
            "items": {
                "id": "items",
                "name": "Items",
                "schema": {"name": "string", "count": "int"},
                "entities": {
                    "item_1": {
                        "name": "Milk",
                        "count": 2,
                        "_removed": False,
                    },
                    "item_2": {
                        "name": "Eggs",
                        "count": 12,
                        "_removed": False,
                    },
                },
            },
        }

        # No views at all
        snapshot["views"] = {}

        block_id = "block_items"
        snapshot["blocks"][block_id] = {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "items", "view": "nonexistent_view"},
        }
        snapshot["blocks"]["block_root"]["children"] = [block_id]

        html = render_block(block_id, snapshot)

        # Should fall back to table view of the collection
        assert_contains(html, "Milk")
        assert_contains(html, "Eggs")
        assert_contains(html, "<table") or assert_contains(html, "aide-table")

    def test_missing_view_and_missing_collection_renders_nothing(self):
        """
        Both view and collection don't exist → render nothing.
        Per spec: 'If the collection also doesn't exist, render nothing.'
        """
        snapshot = empty_state()

        snapshot["collections"] = {}
        snapshot["views"] = {}

        block_id = "block_items"
        snapshot["blocks"][block_id] = {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "nonexistent_collection", "view": "nonexistent_view"},
        }
        snapshot["blocks"]["block_root"]["children"] = [block_id]

        html = render_block(block_id, snapshot)

        # Should render nothing (or empty string / minimal wrapper)
        assert_not_contains(html, "aide-list")
        assert_not_contains(html, "aide-table")
        assert_not_contains(html, "<table")
        assert_not_contains(html, "<ul")

    def test_view_exists_but_collection_missing(self):
        """
        View exists but its source collection doesn't → render nothing.
        Per spec: if not view or not collection: return render_empty_block()
        """
        snapshot = empty_state()

        snapshot["collections"] = {}
        snapshot["views"] = {
            "orphan_view": {
                "id": "orphan_view",
                "type": "list",
                "source": "nonexistent_collection",
                "config": {},
            },
        }

        block_id = "block_items"
        snapshot["blocks"][block_id] = {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "nonexistent_collection", "view": "orphan_view"},
        }
        snapshot["blocks"]["block_root"]["children"] = [block_id]

        html = render_block(block_id, snapshot)

        # No collection → render nothing or empty block
        assert_not_contains(html, "aide-list")
        assert_not_contains(html, "aide-table")

    def test_missing_view_with_empty_collection_shows_empty(self):
        """
        Missing view + existing but empty collection.
        Should fall back to table → then show empty state.
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

        snapshot["views"] = {}

        block_id = "block_items"
        snapshot["blocks"][block_id] = {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "items", "view": "nonexistent_view"},
        }
        snapshot["blocks"]["block_root"]["children"] = [block_id]

        html = render_block(block_id, snapshot)

        # Fallback to table → but no entities → "No items yet."
        assert_contains(html, "aide-collection-empty")


# ============================================================================
# Missing source on block props
# ============================================================================


class TestMissingBlockProps:
    """
    collection_view block with missing or null source/view props.
    Should degrade gracefully without crashing.
    """

    def test_null_source_prop(self):
        """collection_view block with source=None should not crash."""
        snapshot = empty_state()

        block_id = "block_items"
        snapshot["blocks"][block_id] = {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": None, "view": None},
        }
        snapshot["blocks"]["block_root"]["children"] = [block_id]

        # Should not raise
        html = render_block(block_id, snapshot)
        assert_not_contains(html, "aide-list")
        assert_not_contains(html, "aide-table")

    def test_missing_props_entirely(self):
        """collection_view block with empty props dict should not crash."""
        snapshot = empty_state()

        block_id = "block_items"
        snapshot["blocks"][block_id] = {
            "type": "collection_view",
            "parent": "block_root",
            "props": {},
        }
        snapshot["blocks"]["block_root"]["children"] = [block_id]

        # Should not raise
        html = render_block(block_id, snapshot)
        assert_not_contains(html, "aide-list")


# ============================================================================
# Empty collection alongside non-empty content
# ============================================================================


class TestEmptyCollectionWithOtherContent:
    """
    A page can have both regular blocks and an empty collection.
    The empty collection shows its message; other blocks render normally.
    """

    def test_heading_plus_empty_collection(self):
        """Heading renders, empty collection shows 'No items yet.'"""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Mixed"}

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

        snapshot["blocks"]["block_heading"] = {
            "type": "heading",
            "parent": "block_root",
            "props": {"level": 1, "content": "My Page"},
        }
        snapshot["blocks"]["block_collection"] = {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "items", "view": "items_view"},
        }
        snapshot["blocks"]["block_root"]["children"] = [
            "block_heading", "block_collection",
        ]

        html = render(snapshot, make_blueprint())

        # Heading renders
        assert_contains(html, "My Page")
        assert_contains(html, "aide-heading")
        # Empty collection shows message
        assert_contains(html, "aide-collection-empty")
        assert_contains(html, "No items yet.")
        # Page is NOT "empty" (has blocks)
        assert_not_contains(html, "This page is empty.")

    def test_text_block_plus_empty_collection(self):
        """Text block renders normally alongside empty collection."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Mixed"}

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
                "type": "table",
                "source": "items",
                "config": {},
            },
        }

        snapshot["blocks"]["block_text"] = {
            "type": "text",
            "parent": "block_root",
            "props": {"content": "Welcome to this page."},
        }
        snapshot["blocks"]["block_collection"] = {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "items", "view": "items_view"},
        }
        snapshot["blocks"]["block_root"]["children"] = [
            "block_text", "block_collection",
        ]

        html = render(snapshot, make_blueprint())

        assert_contains(html, "Welcome to this page.")
        assert_contains(html, "aide-collection-empty")
        assert_not_contains(html, "This page is empty.")


# ============================================================================
# Multiple empty collections
# ============================================================================


class TestMultipleEmptyCollections:
    """
    Multiple empty collections on the same page each show their own
    empty state message.
    """

    def test_two_empty_collections(self):
        """Two empty collections each render 'No items yet.'"""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Two Empty"}

        for coll_id in ["tasks", "notes"]:
            snapshot["collections"][coll_id] = {
                "id": coll_id,
                "name": coll_id.title(),
                "schema": {"name": "string"},
                "entities": {},
            }
            view_id = f"{coll_id}_view"
            snapshot["views"][view_id] = {
                "id": view_id,
                "type": "list",
                "source": coll_id,
                "config": {},
            }
            block_id = f"block_{coll_id}"
            snapshot["blocks"][block_id] = {
                "type": "collection_view",
                "parent": "block_root",
                "props": {"source": coll_id, "view": view_id},
            }

        snapshot["blocks"]["block_root"]["children"] = [
            "block_tasks", "block_notes",
        ]

        html = render(snapshot, make_blueprint())

        # Two empty messages (count only in <main>, not in CSS)
        main = extract_main(html)
        count = main.count("aide-collection-empty")
        assert count == 2, f"Expected 2 aide-collection-empty in <main>, got {count}"


# ============================================================================
# CSS classes for empty states
# ============================================================================


class TestEmptyStateCSSClasses:
    """
    Empty state CSS classes should be present in the base stylesheet.
    """

    def test_aide_empty_css_in_base(self):
        """The .aide-empty class should be defined in the <style> block."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "CSS Test"}

        html = render(snapshot, make_blueprint())

        assert_contains(html, "aide-empty")

    def test_aide_collection_empty_css(self):
        """
        The rendered HTML should include the aide-collection-empty
        class when an empty collection is present.
        """
        snapshot = empty_state()
        snapshot["meta"] = {"title": "CSS Test"}

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
        block_id = "block_items"
        snapshot["blocks"][block_id] = {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "items", "view": "items_view"},
        }
        snapshot["blocks"]["block_root"]["children"] = [block_id]

        html = render(snapshot, make_blueprint())

        assert_contains(html, "aide-collection-empty")
