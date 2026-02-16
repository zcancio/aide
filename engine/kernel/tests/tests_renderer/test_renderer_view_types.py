"""
AIde Renderer -- View Type Rendering Tests (Category 2)

One test per view type × realistic data. Grocery list in list view,
schedule in table view, squares in grid view.

From the spec (aide_renderer_spec.md, "Testing Strategy"):
  "2. View type rendering. One test per view type × realistic data.
   Grocery list in list view, schedule in table view, squares in grid view."

View types (v1): list, table, grid.
Unknown view types fall back to table.

This matters because:
  - Views are how structured data becomes visible HTML
  - Each view type has distinct HTML structure (ul/li vs table/tr vs grid cells)
  - Field visibility (show_fields, hide_fields) controls what the user sees
  - Primary field styling, boolean rendering, field type CSS classes must be correct
  - Grid view uses positional mapping (row/col labels → entity cells)
  - Unknown view types must degrade gracefully to table

Reference: aide_renderer_spec.md (View Rendering, Value Formatting, Sorting and Filtering)
"""

import pytest

from engine.kernel.renderer import render_block
from engine.kernel.reducer import empty_state


# ============================================================================
# Helpers
# ============================================================================


def assert_contains(html, *fragments):
    """Assert that the HTML output contains all given fragments."""
    for fragment in fragments:
        assert fragment in html, (
            f"Expected to find {fragment!r} in rendered HTML.\n"
            f"Got (first 2000 chars):\n{html[:2000]}"
        )


def assert_not_contains(html, *fragments):
    """Assert that the HTML output does NOT contain any given fragments."""
    for fragment in fragments:
        assert fragment not in html, (
            f"Did NOT expect to find {fragment!r} in rendered HTML."
        )


def build_view_snapshot(
    collection_id,
    collection_name,
    schema,
    entities,
    view_id,
    view_type,
    view_config=None,
):
    """
    Build a snapshot with a collection, entities, a view, and a
    collection_view block wired together. Returns (snapshot, block_id).
    """
    snapshot = empty_state()

    snapshot["collections"] = {
        collection_id: {
            "id": collection_id,
            "name": collection_name,
            "schema": schema,
            "entities": entities,
        },
    }

    snapshot["views"] = {
        view_id: {
            "id": view_id,
            "type": view_type,
            "source": collection_id,
            "config": view_config or {},
        },
    }

    block_id = f"block_{view_id}"
    snapshot["blocks"][block_id] = {
        "type": "collection_view",
        "parent": "block_root",
        "props": {"source": collection_id, "view": view_id},
    }
    snapshot["blocks"]["block_root"]["children"] = [block_id]

    return snapshot, block_id


# ============================================================================
# Realistic data fixtures
# ============================================================================


def grocery_entities():
    """Realistic grocery list: 5 items, mixed checked/unchecked, some with store."""
    return {
        "item_milk": {
            "name": "Whole Milk",
            "store": "Trader Joe's",
            "category": "dairy",
            "checked": False,
            "_removed": False,
        },
        "item_eggs": {
            "name": "Eggs (dozen)",
            "store": "Trader Joe's",
            "category": "dairy",
            "checked": True,
            "_removed": False,
        },
        "item_bread": {
            "name": "Sourdough Bread",
            "store": "Whole Foods",
            "category": "bakery",
            "checked": False,
            "_removed": False,
        },
        "item_apples": {
            "name": "Honeycrisp Apples",
            "store": "Whole Foods",
            "category": "produce",
            "checked": False,
            "_removed": False,
        },
        "item_chicken": {
            "name": "Chicken Thighs",
            "store": None,
            "category": "meat",
            "checked": True,
            "_removed": False,
        },
    }


GROCERY_SCHEMA = {
    "name": "string",
    "store": "string?",
    "category": "enum",
    "checked": "bool",
}


def schedule_entities():
    """Realistic poker schedule: 4 games with dates, hosts, status."""
    return {
        "game_1": {
            "date": "2026-02-13",
            "hosted_by": "Mike",
            "status": "completed",
            "buy_in": 20,
            "_removed": False,
        },
        "game_2": {
            "date": "2026-02-27",
            "hosted_by": "Dave",
            "status": "upcoming",
            "buy_in": 20,
            "_removed": False,
        },
        "game_3": {
            "date": "2026-03-13",
            "hosted_by": "Sarah",
            "status": "planned",
            "buy_in": 25,
            "_removed": False,
        },
        "game_4": {
            "date": "2026-03-27",
            "hosted_by": "Alex",
            "status": "planned",
            "buy_in": 25,
            "_removed": False,
        },
    }


SCHEDULE_SCHEMA = {
    "date": "date",
    "hosted_by": "string",
    "status": "enum",
    "buy_in": "int",
}


def squares_entities():
    """
    Super Bowl squares: a few claimed cells on a 10×10 grid.
    Entities use a 'position' field to map to row/col.
    """
    return {
        "sq_a3": {
            "position": "A3",
            "owner": "Mike",
            "paid": True,
            "_removed": False,
        },
        "sq_b7": {
            "position": "B7",
            "owner": "Sarah",
            "paid": True,
            "_removed": False,
        },
        "sq_c1": {
            "position": "C1",
            "owner": "Dave",
            "paid": False,
            "_removed": False,
        },
        "sq_e5": {
            "position": "E5",
            "owner": "Alex",
            "paid": True,
            "_removed": False,
        },
    }


SQUARES_SCHEMA = {
    "position": "string",
    "owner": "string",
    "paid": "bool",
}


# ============================================================================
# List View — Grocery List
# ============================================================================


class TestListViewGroceryList:
    """
    List view: simple vertical list of entities as <ul>/<li>.
    Realistic scenario: grocery list with name, store, category, checked.
    """

    def test_list_view_renders_ul(self):
        """List view produces a <ul class='aide-list'>."""
        snapshot, block_id = build_view_snapshot(
            "grocery_list", "Grocery List", GROCERY_SCHEMA,
            grocery_entities(), "grocery_view", "list",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "<ul", "aide-list")

    def test_list_view_renders_all_entities(self):
        """All non-removed entities appear in the list."""
        snapshot, block_id = build_view_snapshot(
            "grocery_list", "Grocery List", GROCERY_SCHEMA,
            grocery_entities(), "grocery_view", "list",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Whole Milk", "Eggs (dozen)", "Sourdough Bread")
        assert_contains(html, "Honeycrisp Apples", "Chicken Thighs")

    def test_list_view_items_are_li_elements(self):
        """Each entity renders as an <li class='aide-list__item'>."""
        snapshot, block_id = build_view_snapshot(
            "grocery_list", "Grocery List", GROCERY_SCHEMA,
            grocery_entities(), "grocery_view", "list",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "<li", "aide-list__item")
        # 5 entities → 5 list items
        assert html.count("aide-list__item") >= 5

    def test_list_view_primary_field_has_stronger_weight(self):
        """
        The first visible field renders with aide-list__field--primary.
        Per spec: 'The first visible field renders with
        .aide-list__field--primary (stronger weight).'
        """
        snapshot, block_id = build_view_snapshot(
            "grocery_list", "Grocery List", GROCERY_SCHEMA,
            grocery_entities(), "grocery_view", "list",
            view_config={"show_fields": ["name", "store", "checked"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-list__field--primary")

    def test_list_view_show_fields_whitelist(self):
        """
        show_fields limits which fields appear.
        Per spec: 'If show_fields is set, show only those fields in that order.'
        """
        snapshot, block_id = build_view_snapshot(
            "grocery_list", "Grocery List", GROCERY_SCHEMA,
            grocery_entities(), "grocery_view", "list",
            view_config={"show_fields": ["name", "checked"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Whole Milk")
        # Store values should NOT appear since show_fields excludes them
        assert_not_contains(html, "Trader Joe")
        assert_not_contains(html, "Whole Foods")

    def test_list_view_hide_fields_blacklist(self):
        """
        hide_fields excludes specific fields.
        Per spec: 'If hide_fields is set, show all fields except those.'
        """
        snapshot, block_id = build_view_snapshot(
            "grocery_list", "Grocery List", GROCERY_SCHEMA,
            grocery_entities(), "grocery_view", "list",
            view_config={"hide_fields": ["category"]},
        )
        html = render_block(block_id, snapshot)

        # Name and store should appear
        assert_contains(html, "Whole Milk", "Trader Joe")
        # Category values should NOT appear
        assert_not_contains(html, "dairy")
        assert_not_contains(html, "produce")

    def test_list_view_skips_internal_fields(self):
        """
        Fields starting with _ are internal and not shown.
        Per spec: 'If neither, show all non-internal fields
        (skip fields starting with _).'
        """
        entities = grocery_entities()
        # Add internal field to an entity
        entities["item_milk"]["_internal_score"] = 42
        entities["item_milk"]["_styles"] = {"highlight": True}

        snapshot, block_id = build_view_snapshot(
            "grocery_list", "Grocery List",
            {**GROCERY_SCHEMA, "_internal_score": "int"},
            entities, "grocery_view", "list",
        )
        html = render_block(block_id, snapshot)

        # Internal field value should not be rendered as a visible field
        # (though _styles may affect CSS classes)
        assert_not_contains(html, "_internal_score")

    def test_list_view_boolean_rendering(self):
        """
        Boolean fields render with check/circle markers.
        Per spec: true → ✓ (aide-list__field--bool),
                  false → ○ (aide-list__field--bool-false)
        """
        snapshot, block_id = build_view_snapshot(
            "grocery_list", "Grocery List", GROCERY_SCHEMA,
            grocery_entities(), "grocery_view", "list",
            view_config={"show_fields": ["name", "checked"]},
        )
        html = render_block(block_id, snapshot)

        # Should have both bool classes (some items checked, some not)
        assert "aide-list__field--bool" in html


# ============================================================================
# Table View — Poker Schedule
# ============================================================================


class TestTableViewPokerSchedule:
    """
    Table view: tabular data with headers as <table>.
    Realistic scenario: poker schedule with date, host, status, buy_in.
    """

    def test_table_view_renders_table_element(self):
        """Table view produces <table class='aide-table'> inside a wrapper."""
        snapshot, block_id = build_view_snapshot(
            "schedule", "Schedule", SCHEDULE_SCHEMA,
            schedule_entities(), "schedule_view", "table",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "<table", "aide-table", "aide-table-wrap")

    def test_table_view_renders_thead_with_headers(self):
        """Table has <thead> with <th> for each visible field."""
        snapshot, block_id = build_view_snapshot(
            "schedule", "Schedule", SCHEDULE_SCHEMA,
            schedule_entities(), "schedule_view", "table",
            view_config={"show_fields": ["date", "hosted_by", "status", "buy_in"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "<thead", "<th", "aide-table__th")

    def test_table_view_field_display_names_title_case(self):
        """
        Field names are converted from snake_case to Title Case.
        Per spec: 'Convert snake_case to Title Case.
        requested_by → "Requested By". checked → "Checked".'
        """
        snapshot, block_id = build_view_snapshot(
            "schedule", "Schedule", SCHEDULE_SCHEMA,
            schedule_entities(), "schedule_view", "table",
            view_config={"show_fields": ["date", "hosted_by", "status", "buy_in"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Hosted By")
        assert_contains(html, "Buy In")
        assert_contains(html, "Date")
        assert_contains(html, "Status")

    def test_table_view_renders_all_entities_as_rows(self):
        """Each entity becomes a <tr> in <tbody>."""
        snapshot, block_id = build_view_snapshot(
            "schedule", "Schedule", SCHEDULE_SCHEMA,
            schedule_entities(), "schedule_view", "table",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "<tbody", "<tr", "aide-table__row")
        assert_contains(html, "Mike", "Dave", "Sarah", "Alex")

    def test_table_view_renders_field_type_css_classes(self):
        """
        Table cells have type-specific CSS classes.
        Per spec: aide-table__td--bool, aide-table__td--int, aide-table__td--float
        """
        snapshot, block_id = build_view_snapshot(
            "schedule", "Schedule", SCHEDULE_SCHEMA,
            schedule_entities(), "schedule_view", "table",
            view_config={"show_fields": ["date", "hosted_by", "buy_in"]},
        )
        html = render_block(block_id, snapshot)

        # buy_in is an int field
        assert_contains(html, "aide-table__td--int")

    def test_table_view_show_fields_controls_columns(self):
        """show_fields limits which columns appear in the table."""
        snapshot, block_id = build_view_snapshot(
            "schedule", "Schedule", SCHEDULE_SCHEMA,
            schedule_entities(), "schedule_view", "table",
            view_config={"show_fields": ["date", "hosted_by"]},
        )
        html = render_block(block_id, snapshot)

        # Date and hosted_by should appear
        assert_contains(html, "Date", "Hosted By")
        # Buy-in values should NOT appear
        assert_not_contains(html, "Buy In")

    def test_table_view_date_formatting(self):
        """
        Date fields are formatted as short dates.
        Per spec: "2026-02-27" → "Feb 27"
        """
        snapshot, block_id = build_view_snapshot(
            "schedule", "Schedule", SCHEDULE_SCHEMA,
            schedule_entities(), "schedule_view", "table",
        )
        html = render_block(block_id, snapshot)

        # Raw ISO dates should not appear; formatted dates should
        assert_not_contains(html, "2026-02-13")
        assert_contains(html, "Feb 13")

    def test_table_view_enum_title_case(self):
        """
        Enum values are rendered in Title Case.
        Per spec: "produce" → "Produce"
        """
        snapshot, block_id = build_view_snapshot(
            "schedule", "Schedule", SCHEDULE_SCHEMA,
            schedule_entities(), "schedule_view", "table",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Completed")
        assert_contains(html, "Upcoming")
        assert_contains(html, "Planned")

    def test_table_view_int_right_aligned(self):
        """
        Int and float cells use tabular-nums and right alignment via CSS class.
        Per spec: aide-table__td--int, aide-table__td--float
        """
        snapshot, block_id = build_view_snapshot(
            "schedule", "Schedule", SCHEDULE_SCHEMA,
            schedule_entities(), "schedule_view", "table",
            view_config={"show_fields": ["date", "buy_in"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-table__td--int")


# ============================================================================
# Grid View — Super Bowl Squares
# ============================================================================


class TestGridViewSuperBowlSquares:
    """
    Grid view: structured grid with row/col labels for positional data.
    Realistic scenario: Super Bowl squares board.
    """

    def _squares_snapshot(self, row_labels=None, col_labels=None):
        """Build snapshot with squares grid."""
        config = {
            "row_labels": row_labels or ["A", "B", "C", "D", "E"],
            "col_labels": col_labels or ["1", "2", "3", "4", "5", "6", "7"],
            "show_fields": ["owner"],
        }
        return build_view_snapshot(
            "squares", "Super Bowl Squares", SQUARES_SCHEMA,
            squares_entities(), "squares_view", "grid",
            view_config=config,
        )

    def test_grid_view_renders_grid_table(self):
        """Grid view produces a <table class='aide-grid'>."""
        snapshot, block_id = self._squares_snapshot()
        html = render_block(block_id, snapshot)

        assert_contains(html, "<table", "aide-grid", "aide-grid-wrap")

    def test_grid_view_renders_column_labels(self):
        """Column labels appear in <thead>."""
        snapshot, block_id = self._squares_snapshot()
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-grid__col-label")
        for col in ["1", "2", "3", "4", "5", "6", "7"]:
            assert_contains(html, col)

    def test_grid_view_renders_row_labels(self):
        """Row labels appear as <th> in each row."""
        snapshot, block_id = self._squares_snapshot()
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-grid__row-label")
        for row in ["A", "B", "C", "D", "E"]:
            assert_contains(html, row)

    def test_grid_view_filled_cells_have_entity_data(self):
        """Cells with matching entities show the entity content."""
        snapshot, block_id = self._squares_snapshot()
        html = render_block(block_id, snapshot)

        # These owners have positions on the grid
        assert_contains(html, "Mike")   # position A3
        assert_contains(html, "Sarah")  # position B7
        assert_contains(html, "Dave")   # position C1
        assert_contains(html, "Alex")   # position E5

    def test_grid_view_filled_cells_have_filled_class(self):
        """
        Filled cells get aide-grid__cell--filled class.
        Per spec: filled cells have background color and stronger text.
        """
        snapshot, block_id = self._squares_snapshot()
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-grid__cell--filled")

    def test_grid_view_empty_cells_have_empty_class(self):
        """
        Empty cells (no entity at that position) get aide-grid__cell--empty.
        With 5×7=35 cells and only 4 entities, most cells are empty.
        """
        snapshot, block_id = self._squares_snapshot()
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-grid__cell--empty")
        # Should have significantly more empty cells than filled
        empty_count = html.count("aide-grid__cell--empty")
        filled_count = html.count("aide-grid__cell--filled")
        assert empty_count > filled_count

    def test_grid_view_correct_cell_count(self):
        """Grid has rows × cols cells."""
        snapshot, block_id = self._squares_snapshot()
        html = render_block(block_id, snapshot)

        # 5 rows × 7 cols = 35 cells
        cell_count = html.count("aide-grid__cell")
        assert cell_count >= 35

    def test_grid_view_empty_corner_cell(self):
        """
        Top-left corner (where row and col headers intersect) is an empty <th>.
        Per spec: first cell in thead row is empty.
        """
        snapshot, block_id = self._squares_snapshot()
        html = render_block(block_id, snapshot)

        # The thead row starts with an empty th
        assert_contains(html, "<thead")
        assert_contains(html, "<th></th>")


# ============================================================================
# Unknown View Type — Fallback to Table
# ============================================================================


class TestUnknownViewTypeFallback:
    """
    Unknown view types fall back to table rendering.
    Per spec: 'For v1, unknown view types fall back to table.'
    """

    def test_unknown_view_type_renders_as_table(self):
        """A view with type 'kanban' (not in v1) falls back to table."""
        snapshot, block_id = build_view_snapshot(
            "tasks", "Tasks",
            {"name": "string", "status": "enum"},
            {
                "task_1": {
                    "name": "Fix bug",
                    "status": "todo",
                    "_removed": False,
                },
                "task_2": {
                    "name": "Write docs",
                    "status": "in_progress",
                    "_removed": False,
                },
            },
            "task_view", "kanban",
        )
        html = render_block(block_id, snapshot)

        # Should render as table (the fallback)
        assert_contains(html, "<table", "aide-table")
        assert_contains(html, "Fix bug", "Write docs")

    def test_calendar_view_falls_back_to_table(self):
        """Calendar view (not in v1) falls back to table."""
        snapshot, block_id = build_view_snapshot(
            "events", "Events",
            {"name": "string", "date": "date"},
            {
                "evt_1": {
                    "name": "Kickoff",
                    "date": "2026-03-01",
                    "_removed": False,
                },
            },
            "events_view", "calendar",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "<table", "aide-table")
        assert_contains(html, "Kickoff")

    def test_dashboard_view_falls_back_to_table(self):
        """Dashboard view (not in v1) falls back to table."""
        snapshot, block_id = build_view_snapshot(
            "metrics", "Metrics",
            {"label": "string", "value": "float"},
            {
                "m_1": {
                    "label": "Revenue",
                    "value": 9999.50,
                    "_removed": False,
                },
            },
            "metrics_view", "dashboard",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "<table", "aide-table")
        assert_contains(html, "Revenue")


# ============================================================================
# Field Visibility Rules (across view types)
# ============================================================================


class TestFieldVisibilityRules:
    """
    Field visibility applies to both list and table views:
    - show_fields → whitelist, fields appear in that order
    - hide_fields → blacklist, everything except these
    - neither → all non-internal fields
    """

    def test_show_fields_order_in_list(self):
        """
        show_fields determines the order of field spans in list items.
        First field in show_fields becomes the primary field.
        """
        snapshot, block_id = build_view_snapshot(
            "grocery_list", "Grocery List", GROCERY_SCHEMA,
            grocery_entities(), "grocery_view", "list",
            view_config={"show_fields": ["store", "name"]},
        )
        html = render_block(block_id, snapshot)

        # Store should be the primary field (appears first)
        assert_contains(html, "aide-list__field--primary")
        # Both name and store should be present
        assert_contains(html, "Trader Joe", "Whole Milk")

    def test_show_fields_order_in_table_headers(self):
        """
        show_fields determines the order of <th> headers in table.
        """
        snapshot, block_id = build_view_snapshot(
            "schedule", "Schedule", SCHEDULE_SCHEMA,
            schedule_entities(), "schedule_view", "table",
            view_config={"show_fields": ["status", "hosted_by", "date"]},
        )
        html = render_block(block_id, snapshot)

        # Headers should appear — verify they're present
        assert_contains(html, "Status", "Hosted By", "Date")

        # Status should appear before Hosted By in the HTML
        status_pos = html.index("Status")
        hosted_pos = html.index("Hosted By")
        date_pos = html.index("Date")
        assert status_pos < hosted_pos < date_pos

    def test_no_field_config_shows_all_non_internal(self):
        """With no show_fields or hide_fields, all non-_ fields appear."""
        entities = {
            "item_a": {
                "name": "Alpha",
                "score": 100,
                "active": True,
                "_styles": {"highlight": True},
                "_removed": False,
            },
        }
        snapshot, block_id = build_view_snapshot(
            "items", "Items",
            {"name": "string", "score": "int", "active": "bool"},
            entities, "items_view", "table",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Alpha", "100")
        assert_not_contains(html, "_styles")


# ============================================================================
# Null / Missing Value Rendering in Views
# ============================================================================


class TestNullValuesInViews:
    """
    Null values render as em dashes across all view types.
    Per spec: null → "—" (em dash)
    """

    def test_null_string_in_list_view(self):
        """Null optional string renders as em dash in list view."""
        entities = {
            "item_1": {
                "name": "Chicken Thighs",
                "store": None,
                "_removed": False,
            },
        }
        snapshot, block_id = build_view_snapshot(
            "grocery_list", "Grocery List",
            {"name": "string", "store": "string?"},
            entities, "grocery_view", "list",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Chicken Thighs")
        # Null store should be rendered as em dash
        assert_contains(html, "\u2014")  # em dash character

    def test_null_value_in_table_view(self):
        """Null value renders as em dash in table cell."""
        entities = {
            "row_1": {
                "name": "Item A",
                "amount": None,
                "_removed": False,
            },
        }
        snapshot, block_id = build_view_snapshot(
            "items", "Items",
            {"name": "string", "amount": "int?"},
            entities, "items_view", "table",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "\u2014")


# ============================================================================
# Removed Entities Excluded from Views
# ============================================================================


class TestRemovedEntitiesExcluded:
    """
    Entities with _removed=True must be excluded from all view types.
    Per spec: 'Get non-removed entities' before rendering.
    """

    def test_removed_entities_excluded_from_list(self):
        """Removed entities don't appear in list view."""
        entities = grocery_entities()
        entities["item_milk"]["_removed"] = True

        snapshot, block_id = build_view_snapshot(
            "grocery_list", "Grocery List", GROCERY_SCHEMA,
            entities, "grocery_view", "list",
        )
        html = render_block(block_id, snapshot)

        assert_not_contains(html, "Whole Milk")
        assert_contains(html, "Eggs (dozen)")

    def test_removed_entities_excluded_from_table(self):
        """Removed entities don't appear in table view."""
        entities = schedule_entities()
        entities["game_1"]["_removed"] = True

        snapshot, block_id = build_view_snapshot(
            "schedule", "Schedule", SCHEDULE_SCHEMA,
            entities, "schedule_view", "table",
        )
        html = render_block(block_id, snapshot)

        # game_1 (Mike, Feb 13) should not appear
        assert_not_contains(html, "Mike")
        assert_contains(html, "Dave", "Sarah", "Alex")

    def test_removed_entities_excluded_from_grid(self):
        """Removed entities don't fill grid cells."""
        entities = squares_entities()
        entities["sq_a3"]["_removed"] = True

        config = {
            "row_labels": ["A", "B", "C", "D", "E"],
            "col_labels": ["1", "2", "3", "4", "5", "6", "7"],
            "show_fields": ["owner"],
        }
        snapshot, block_id = build_view_snapshot(
            "squares", "Squares", SQUARES_SCHEMA,
            entities, "squares_view", "grid",
            view_config=config,
        )
        html = render_block(block_id, snapshot)

        # Mike (position A3) was removed, should not appear as owner
        assert_not_contains(html, "Mike")
        assert_contains(html, "Sarah", "Dave", "Alex")


# ============================================================================
# Empty Collection in Different View Types
# ============================================================================


class TestEmptyCollectionViews:
    """
    Empty collections show the empty state message.
    Per spec: <p class="aide-collection-empty">No items yet.</p>
    """

    def test_empty_list_view(self):
        """Empty collection in list view shows empty state."""
        snapshot, block_id = build_view_snapshot(
            "items", "Items", {"name": "string"},
            {}, "items_view", "list",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-collection-empty")

    def test_empty_table_view(self):
        """Empty collection in table view shows empty state."""
        snapshot, block_id = build_view_snapshot(
            "items", "Items", {"name": "string"},
            {}, "items_view", "table",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-collection-empty")

    def test_empty_grid_view(self):
        """
        Empty grid still renders the grid structure (labels) but no filled cells.
        """
        config = {
            "row_labels": ["A", "B"],
            "col_labels": ["1", "2"],
        }
        snapshot, block_id = build_view_snapshot(
            "board", "Board", {"position": "string", "owner": "string"},
            {}, "board_view", "grid",
            view_config=config,
        )
        html = render_block(block_id, snapshot)

        # Empty collection shows empty message (same as list/table)
        assert_contains(html, "aide-collection-empty")

    def test_all_removed_equals_empty(self):
        """Collection with all entities removed is effectively empty."""
        entities = {
            "item_1": {
                "name": "Gone",
                "_removed": True,
            },
        }
        snapshot, block_id = build_view_snapshot(
            "items", "Items", {"name": "string"},
            entities, "items_view", "list",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-collection-empty")
        assert_not_contains(html, "Gone")
