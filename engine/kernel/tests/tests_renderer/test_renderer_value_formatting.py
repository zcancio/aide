"""
AIde Renderer -- Value Formatting Tests (Category 6)

Every field type with real and null values. Dates, bools, enums, lists.

From the spec (aide_renderer_spec.md, "Testing Strategy"):
  "6. Value formatting. Every field type with real and null values.
   Dates, bools, enums, lists."

Value formatting table (from spec):
  string    "Mike"                    → Mike
  int       20                        → 20
  float     9.99                      → 9.99
  bool      true                      → ✓ (with CSS class)
  bool      false                     → ○ (with CSS class)
  date      "2026-02-27"              → Feb 27
  datetime  "2026-02-27T19:00:00Z"    → Feb 27, 7:00 PM
  enum      "produce"                 → Produce (title case)
  list      ["milk","eggs"]           → milk, eggs
  null      null                      → — (em dash)
  string?   null                      → —

Additional rendering rules from spec:
  - Table cells get type-specific CSS classes: aide-table__td--bool,
    aide-table__td--int, aide-table__td--float
  - Bool cells: text-align center
  - Int/float cells: text-align right, font-variant-numeric tabular-nums
  - List view bool fields: aide-list__field--bool (true), aide-list__field--bool-false (false)
  - Date formatting defaults to en-US short format
  - Field display names: snake_case → Title Case

Reference: aide_renderer_spec.md (Value Formatting, View Rendering)
           aide_primitive_schemas.md (Field types)
"""

from engine.kernel.reducer import empty_state
from engine.kernel.renderer import render_block

# ============================================================================
# Helpers
# ============================================================================


EM_DASH = "\u2014"  # —


def assert_contains(html, *fragments):
    for fragment in fragments:
        assert fragment in html, (
            f"Expected to find {fragment!r} in rendered HTML.\nGot (first 3000 chars):\n{html[:3000]}"
        )


def assert_not_contains(html, *fragments):
    for fragment in fragments:
        assert fragment not in html, f"Did NOT expect to find {fragment!r} in rendered HTML."


def build_single_entity_view(schema, fields, view_type="table", view_config=None):
    """
    Build a snapshot with one collection, one entity, one view, and a
    collection_view block. Returns (snapshot, block_id).

    This isolates value formatting: one entity, visible fields controlled
    by show_fields so we know exactly what's rendered.
    """
    snapshot = empty_state()

    # Entity uses flat structure (fields at top level) with _removed flag
    entity_data = {**fields, "_removed": False}

    snapshot["collections"] = {
        "items": {
            "id": "items",
            "name": "Items",
            "schema": schema,
            "entities": {
                "item_1": entity_data,
            },
        },
    }

    config = view_config or {"show_fields": list(schema.keys())}
    snapshot["views"] = {
        "items_view": {
            "id": "items_view",
            "type": view_type,
            "source": "items",
            "config": config,
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


def build_multi_entity_view(schema, entities_fields, view_type="table", view_config=None):
    """
    Build a snapshot with multiple entities for testing formatting
    across several rows.
    """
    snapshot = empty_state()

    # Entities use flat structure (fields at top level) with _removed flag
    entities = {}
    for i, fields in enumerate(entities_fields):
        eid = f"item_{i}"
        entities[eid] = {**fields, "_removed": False}

    snapshot["collections"] = {
        "items": {
            "id": "items",
            "name": "Items",
            "schema": schema,
            "entities": entities,
        },
    }

    config = view_config or {"show_fields": list(schema.keys())}
    snapshot["views"] = {
        "items_view": {
            "id": "items_view",
            "type": view_type,
            "source": "items",
            "config": config,
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


# ============================================================================
# String formatting
# ============================================================================


class TestStringFormatting:
    """
    string → rendered as-is (HTML-escaped).
    Per spec: "Mike" → Mike
    """

    def test_string_value_in_table(self):
        """String value renders as plain text in table cell."""
        snapshot, block_id = build_single_entity_view(
            {"name": "string"},
            {"name": "Mike"},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Mike")

    def test_string_with_special_chars(self):
        """String with HTML special chars is escaped."""
        snapshot, block_id = build_single_entity_view(
            {"name": "string"},
            {"name": "Tom & Jerry <Bros>"},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Tom &amp; Jerry &lt;Bros&gt;")
        assert_not_contains(html, "Tom & Jerry <Bros>")

    def test_string_in_list_view(self):
        """String value renders in list view."""
        snapshot, block_id = build_single_entity_view(
            {"name": "string"},
            {"name": "Alice"},
            view_type="list",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Alice")


# ============================================================================
# Int formatting
# ============================================================================


class TestIntFormatting:
    """
    int → rendered as number string.
    Per spec: 20 → 20
    Table cells get aide-table__td--int class (right-aligned, tabular-nums).
    """

    def test_int_value_in_table(self):
        """Int value renders as number."""
        snapshot, block_id = build_single_entity_view(
            {"score": "int"},
            {"score": 20},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "20")

    def test_int_table_cell_has_type_class(self):
        """Int cells in table get aide-table__td--int class."""
        snapshot, block_id = build_single_entity_view(
            {"score": "int"},
            {"score": 42},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-table__td--int")

    def test_int_zero(self):
        """Zero renders as '0', not empty or em dash."""
        snapshot, block_id = build_single_entity_view(
            {"count": "int"},
            {"count": 0},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "0")
        assert_not_contains(html, EM_DASH)

    def test_int_negative(self):
        """Negative int renders correctly."""
        snapshot, block_id = build_single_entity_view(
            {"balance": "int"},
            {"balance": -15},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "-15")

    def test_int_large(self):
        """Large int renders without truncation."""
        snapshot, block_id = build_single_entity_view(
            {"big": "int"},
            {"big": 1000000},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "1000000")


# ============================================================================
# Float formatting
# ============================================================================


class TestFloatFormatting:
    """
    float → rendered as decimal number.
    Per spec: 9.99 → 9.99
    Table cells get aide-table__td--float class.
    """

    def test_float_value_in_table(self):
        """Float value renders with decimal."""
        snapshot, block_id = build_single_entity_view(
            {"price": "float"},
            {"price": 9.99},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "9.99")

    def test_float_table_cell_has_type_class(self):
        """Float cells in table get aide-table__td--float class."""
        snapshot, block_id = build_single_entity_view(
            {"price": "float"},
            {"price": 3.14},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-table__td--float")

    def test_float_zero(self):
        """Float 0.0 renders as '0.0' or '0', not em dash."""
        snapshot, block_id = build_single_entity_view(
            {"amount": "float"},
            {"amount": 0.0},
        )
        html = render_block(block_id, snapshot)

        # Should contain 0, not em dash
        assert_not_contains(html, EM_DASH)

    def test_float_whole_number(self):
        """Float with no fractional part (10.0) renders reasonably."""
        snapshot, block_id = build_single_entity_view(
            {"score": "float"},
            {"score": 10.0},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "10")


# ============================================================================
# Bool formatting
# ============================================================================


class TestBoolFormatting:
    """
    bool true  → ✓ (with CSS class aide-list__field--bool or aide-table__td--bool)
    bool false → ○ (with CSS class aide-list__field--bool-false)

    Per spec:
      List view: .aide-list__field--bool::before { content: '✓' }
                 .aide-list__field--bool-false::before { content: '○' }
      Table view: .aide-table__td--bool { text-align: center }
    """

    def test_bool_true_in_list_view(self):
        """Bool true gets aide-list__field--bool class in list view."""
        snapshot, block_id = build_single_entity_view(
            {"name": "string", "checked": "bool"},
            {"name": "Item", "checked": True},
            view_type="list",
            view_config={"show_fields": ["name", "checked"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-list__field--bool")

    def test_bool_false_in_list_view(self):
        """Bool false gets aide-list__field--bool-false class in list view."""
        snapshot, block_id = build_single_entity_view(
            {"name": "string", "checked": "bool"},
            {"name": "Item", "checked": False},
            view_type="list",
            view_config={"show_fields": ["name", "checked"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-list__field--bool-false")

    def test_bool_true_and_false_in_same_list(self):
        """Both true and false booleans render with correct classes."""
        snapshot, block_id = build_multi_entity_view(
            {"name": "string", "checked": "bool"},
            [
                {"name": "Done", "checked": True},
                {"name": "Pending", "checked": False},
            ],
            view_type="list",
            view_config={"show_fields": ["name", "checked"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-list__field--bool")
        assert_contains(html, "aide-list__field--bool-false")

    def test_bool_table_cell_has_type_class(self):
        """Bool cells in table get aide-table__td--bool class."""
        snapshot, block_id = build_single_entity_view(
            {"checked": "bool"},
            {"checked": True},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-table__td--bool")


# ============================================================================
# Date formatting
# ============================================================================


class TestDateFormatting:
    """
    date "2026-02-27" → "Feb 27" (en-US short format)
    Per spec: Date formatting defaults to en-US short format.
    Raw ISO dates should NOT appear in rendered output.
    """

    def test_date_formatted_short(self):
        """Date renders as 'Feb 27' not '2026-02-27'."""
        snapshot, block_id = build_single_entity_view(
            {"event_date": "date"},
            {"event_date": "2026-02-27"},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Feb 27")
        assert_not_contains(html, "2026-02-27")

    def test_date_january(self):
        """January date formats correctly."""
        snapshot, block_id = build_single_entity_view(
            {"joined": "date"},
            {"joined": "2025-01-15"},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Jan 15")
        assert_not_contains(html, "2025-01-15")

    def test_date_december(self):
        """December date formats correctly."""
        snapshot, block_id = build_single_entity_view(
            {"deadline": "date"},
            {"deadline": "2025-12-31"},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Dec 31")

    def test_date_first_of_month(self):
        """Date on the 1st of the month."""
        snapshot, block_id = build_single_entity_view(
            {"start": "date"},
            {"start": "2026-03-01"},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Mar 1")

    def test_multiple_dates_in_table(self):
        """Multiple date values format independently."""
        snapshot, block_id = build_multi_entity_view(
            {"name": "string", "date": "date"},
            [
                {"name": "Game 1", "date": "2026-02-13"},
                {"name": "Game 2", "date": "2026-02-27"},
                {"name": "Game 3", "date": "2026-03-13"},
            ],
            view_config={"show_fields": ["name", "date"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Feb 13", "Feb 27", "Mar 13")
        assert_not_contains(html, "2026-02-13", "2026-02-27", "2026-03-13")


# ============================================================================
# Datetime formatting
# ============================================================================


class TestDatetimeFormatting:
    """
    datetime "2026-02-27T19:00:00Z" → "Feb 27, 7:00 PM"
    Per spec: datetime renders with date and time in en-US format.
    """

    def test_datetime_formatted(self):
        """Datetime renders as 'Feb 27, 7:00 PM' (or similar)."""
        snapshot, block_id = build_single_entity_view(
            {"event_time": "datetime"},
            {"event_time": "2026-02-27T19:00:00Z"},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Feb 27")
        assert_contains(html, "7:00 PM")
        assert_not_contains(html, "2026-02-27T19:00:00Z")

    def test_datetime_morning(self):
        """Morning datetime renders with AM."""
        snapshot, block_id = build_single_entity_view(
            {"start": "datetime"},
            {"start": "2026-03-15T09:30:00Z"},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Mar 15")
        assert_contains(html, "9:30 AM")

    def test_datetime_midnight(self):
        """Midnight datetime renders as 12:00 AM."""
        snapshot, block_id = build_single_entity_view(
            {"created": "datetime"},
            {"created": "2026-01-01T00:00:00Z"},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Jan 1")
        assert_contains(html, "12:00 AM")

    def test_datetime_noon(self):
        """Noon datetime renders as 12:00 PM."""
        snapshot, block_id = build_single_entity_view(
            {"lunch": "datetime"},
            {"lunch": "2026-06-15T12:00:00Z"},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "12:00 PM")


# ============================================================================
# Enum formatting
# ============================================================================


class TestEnumFormatting:
    """
    enum "produce" → "Produce" (title case)
    Per spec: enum values are rendered in Title Case.
    """

    def test_enum_title_case(self):
        """Lowercase enum renders as Title Case."""
        snapshot, block_id = build_single_entity_view(
            {"category": "enum"},
            {"category": "produce"},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Produce")

    def test_enum_multi_word_snake_case(self):
        """Snake_case enum renders as Title Case with spaces."""
        snapshot, block_id = build_single_entity_view(
            {"status": "enum"},
            {"status": "in_progress"},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "In Progress")

    def test_enum_already_capitalized(self):
        """Already capitalized enum should still render properly."""
        snapshot, block_id = build_single_entity_view(
            {"tier": "enum"},
            {"tier": "Gold"},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Gold")

    def test_multiple_enum_values(self):
        """Different enum values format independently."""
        snapshot, block_id = build_multi_entity_view(
            {"name": "string", "status": "enum"},
            [
                {"name": "Task A", "status": "completed"},
                {"name": "Task B", "status": "in_progress"},
                {"name": "Task C", "status": "pending"},
            ],
            view_config={"show_fields": ["name", "status"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Completed", "In Progress", "Pending")


# ============================================================================
# List formatting
# ============================================================================


class TestListFormatting:
    """
    list ["milk","eggs"] → "milk, eggs" (comma-separated)
    Per spec: list values are joined with commas.
    """

    def test_list_comma_separated(self):
        """List renders as comma-separated string."""
        snapshot, block_id = build_single_entity_view(
            {"tags": {"list": "string"}},
            {"tags": ["milk", "eggs"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "milk, eggs")

    def test_list_single_item(self):
        """Single-item list renders without comma."""
        snapshot, block_id = build_single_entity_view(
            {"tags": {"list": "string"}},
            {"tags": ["only"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "only")
        assert_not_contains(html, ",")

    def test_list_empty(self):
        """Empty list renders as em dash (effectively null/empty)."""
        snapshot, block_id = build_single_entity_view(
            {"tags": {"list": "string"}},
            {"tags": []},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, EM_DASH)

    def test_list_three_items(self):
        """Three-item list renders all items comma-separated."""
        snapshot, block_id = build_single_entity_view(
            {"ingredients": {"list": "string"}},
            {"ingredients": ["flour", "sugar", "butter"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "flour, sugar, butter")

    def test_list_items_are_escaped(self):
        """List items with HTML special chars are escaped."""
        snapshot, block_id = build_single_entity_view(
            {"items": {"list": "string"}},
            {"items": ["<script>", "a&b"]},
        )
        html = render_block(block_id, snapshot)

        assert_not_contains(html, "<script>")
        assert_contains(html, "&lt;script&gt;")
        assert_contains(html, "a&amp;b")


# ============================================================================
# Null formatting
# ============================================================================


class TestNullFormatting:
    """
    null → — (em dash, U+2014)
    Applies to all nullable field types when value is null.
    Per spec: null → "—", string? null → "—"
    """

    def test_null_string(self):
        """Null optional string renders as em dash."""
        snapshot, block_id = build_single_entity_view(
            {"notes": "string?"},
            {"notes": None},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, EM_DASH)

    def test_null_int(self):
        """Null optional int renders as em dash."""
        snapshot, block_id = build_single_entity_view(
            {"score": "int?"},
            {"score": None},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, EM_DASH)

    def test_null_float(self):
        """Null optional float renders as em dash."""
        snapshot, block_id = build_single_entity_view(
            {"price": "float?"},
            {"price": None},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, EM_DASH)

    def test_null_date(self):
        """Null optional date renders as em dash."""
        snapshot, block_id = build_single_entity_view(
            {"deadline": "date?"},
            {"deadline": None},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, EM_DASH)

    def test_null_datetime(self):
        """Null optional datetime renders as em dash."""
        snapshot, block_id = build_single_entity_view(
            {"event_time": "datetime?"},
            {"event_time": None},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, EM_DASH)

    def test_null_in_list_view(self):
        """Null value renders as em dash in list view."""
        snapshot, block_id = build_single_entity_view(
            {"name": "string", "store": "string?"},
            {"name": "Chicken", "store": None},
            view_type="list",
            view_config={"show_fields": ["name", "store"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Chicken")
        assert_contains(html, EM_DASH)

    def test_null_among_non_null(self):
        """Null values interspersed with real values."""
        snapshot, block_id = build_multi_entity_view(
            {"name": "string", "rating": "int?"},
            [
                {"name": "Alice", "rating": 1400},
                {"name": "Bob", "rating": None},
                {"name": "Carol", "rating": 1550},
            ],
            view_config={"show_fields": ["name", "rating"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Alice", "1400", "Carol", "1550")
        assert_contains(html, EM_DASH)  # Bob's null rating


# ============================================================================
# Mixed field types in one entity
# ============================================================================


class TestMixedFieldTypes:
    """
    An entity with all field types renders each value with the correct
    formatting rule.
    """

    def test_all_types_in_one_entity_table(self):
        """Entity with every field type — table view."""
        schema = {
            "name": "string",
            "score": "int",
            "avg": "float",
            "active": "bool",
            "joined": "date",
            "last_login": "datetime",
            "role": "enum",
            "tags": {"list": "string"},
            "notes": "string?",
        }
        fields = {
            "name": "Mike",
            "score": 20,
            "avg": 9.99,
            "active": True,
            "joined": "2026-02-27",
            "last_login": "2026-02-27T19:00:00Z",
            "role": "admin",
            "tags": ["poker", "league"],
            "notes": None,
        }
        snapshot, block_id = build_single_entity_view(schema, fields)
        html = render_block(block_id, snapshot)

        # String
        assert_contains(html, "Mike")
        # Int
        assert_contains(html, "20")
        # Float
        assert_contains(html, "9.99")
        # Bool (CSS class in table)
        assert_contains(html, "aide-table__td--bool")
        # Date formatted
        assert_contains(html, "Feb 27")
        assert_not_contains(html, "2026-02-27T")
        # Datetime formatted
        assert_contains(html, "7:00 PM")
        # Enum title case
        assert_contains(html, "Admin")
        # List comma-separated
        assert_contains(html, "poker, league")
        # Null → em dash
        assert_contains(html, EM_DASH)

    def test_all_types_in_one_entity_list(self):
        """Entity with every field type — list view."""
        schema = {
            "name": "string",
            "count": "int",
            "checked": "bool",
            "category": "enum",
            "store": "string?",
        }
        fields = {
            "name": "Milk",
            "count": 2,
            "checked": False,
            "category": "dairy",
            "store": None,
        }
        snapshot, block_id = build_single_entity_view(
            schema,
            fields,
            view_type="list",
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Milk")
        assert_contains(html, "2")
        assert_contains(html, "aide-list__field--bool-false")
        assert_contains(html, "Dairy")
        assert_contains(html, EM_DASH)


# ============================================================================
# Field display names (snake_case → Title Case)
# ============================================================================


class TestFieldDisplayNames:
    """
    Table headers convert field names from snake_case to Title Case.
    Per spec: "requested_by" → "Requested By", "checked" → "Checked"
    """

    def test_single_word_field_name(self):
        """Single word field name is title-cased in table header."""
        snapshot, block_id = build_single_entity_view(
            {"name": "string", "checked": "bool"},
            {"name": "Item", "checked": True},
            view_config={"show_fields": ["name", "checked"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Name")
        assert_contains(html, "Checked")

    def test_multi_word_snake_case(self):
        """Multi-word snake_case → Title Case with spaces."""
        snapshot, block_id = build_single_entity_view(
            {"requested_by": "string", "due_date": "date"},
            {"requested_by": "Alice", "due_date": "2026-03-01"},
            view_config={"show_fields": ["requested_by", "due_date"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Requested By")
        assert_contains(html, "Due Date")

    def test_three_word_field_name(self):
        """Three-word snake_case field name."""
        snapshot, block_id = build_single_entity_view(
            {"first_name_initial": "string"},
            {"first_name_initial": "M"},
            view_config={"show_fields": ["first_name_initial"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "First Name Initial")


# ============================================================================
# Table cell type CSS classes
# ============================================================================


class TestTableCellTypeClasses:
    """
    Table cells get type-specific CSS classes for alignment and formatting.
    Per spec:
      aide-table__td--bool  → text-align: center
      aide-table__td--int   → text-align: right, font-variant-numeric: tabular-nums
      aide-table__td--float → text-align: right, font-variant-numeric: tabular-nums
    """

    def test_bool_cell_class(self):
        """Bool field gets aide-table__td--bool."""
        snapshot, block_id = build_single_entity_view(
            {"active": "bool"},
            {"active": True},
        )
        html = render_block(block_id, snapshot)
        assert_contains(html, "aide-table__td--bool")

    def test_int_cell_class(self):
        """Int field gets aide-table__td--int."""
        snapshot, block_id = build_single_entity_view(
            {"score": "int"},
            {"score": 42},
        )
        html = render_block(block_id, snapshot)
        assert_contains(html, "aide-table__td--int")

    def test_float_cell_class(self):
        """Float field gets aide-table__td--float."""
        snapshot, block_id = build_single_entity_view(
            {"price": "float"},
            {"price": 9.99},
        )
        html = render_block(block_id, snapshot)
        assert_contains(html, "aide-table__td--float")

    def test_multiple_type_classes_in_one_row(self):
        """A row with bool, int, and float fields gets all three classes."""
        snapshot, block_id = build_single_entity_view(
            {"active": "bool", "score": "int", "avg": "float"},
            {"active": True, "score": 42, "avg": 3.14},
            view_config={"show_fields": ["active", "score", "avg"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-table__td--bool")
        assert_contains(html, "aide-table__td--int")
        assert_contains(html, "aide-table__td--float")
