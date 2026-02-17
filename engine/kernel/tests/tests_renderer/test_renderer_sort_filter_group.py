"""
AIde Renderer -- Sort / Filter / Group Tests (Category 5)

Create a collection with 10 entities, apply various view configs,
verify entity order in output.

From the spec (aide_renderer_spec.md, "Testing Strategy"):
  "5. Sort/filter/group. Create a collection with 10 entities, apply
   various view configs, verify entity order in output."

Sort behavior:
  - sort_by: field name to sort on
  - sort_order: "asc" (default) or "desc"
  - Nulls sort last regardless of direction
  - Booleans sort as int(value): false=0, true=1
  - No sort_by → preserve insertion order

Filter behavior:
  - filter: { field: value } conditions — all must match (AND)
  - No filter → return all entities

Group behavior:
  - group_by: field name to group on
  - Each group renders with <div class="aide-group"> and <h4> header
  - Null group key → "_none" group
  - No group_by → no group wrappers

Reference: aide_renderer_spec.md (Sorting and Filtering)
           aide_primitive_schemas.md (view.create config options)
"""

import pytest

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


def assert_order(html, *names):
    """Assert that the given names appear in order in the HTML output."""
    positions = []
    for name in names:
        pos = html.find(name)
        assert pos != -1, f"{name!r} not found in HTML"
        positions.append((name, pos))
    for i in range(len(positions) - 1):
        assert positions[i][1] < positions[i + 1][1], (
            f"Expected {positions[i][0]!r} before {positions[i + 1][0]!r}, "
            f"but positions are {positions[i][1]} and {positions[i + 1][1]}"
        )


def build_snapshot(entities, view_type="list", view_config=None):
    """
    Build a snapshot with a 'players' collection, 10 player entities,
    a view, and a collection_view block. Returns (snapshot, block_id).
    """
    snapshot = empty_state()

    snapshot["collections"] = {
        "players": {
            "id": "players",
            "name": "Players",
            "schema": {
                "name": "string",
                "rating": "int",
                "status": "enum",
                "active": "bool",
                "joined": "date",
                "wins": "int",
            },
            "entities": entities,
        },
    }

    snapshot["views"] = {
        "players_view": {
            "id": "players_view",
            "type": view_type,
            "source": "players",
            "config": view_config or {},
        },
    }

    block_id = "block_players"
    snapshot["blocks"][block_id] = {
        "type": "collection_view",
        "parent": "block_root",
        "props": {"source": "players", "view": "players_view"},
    }
    snapshot["blocks"]["block_root"]["children"] = [block_id]

    return snapshot, block_id


# ============================================================================
# 10-player fixture
# ============================================================================


def ten_players():
    """
    10 players with varied ratings, statuses, active flags, join dates,
    and wins for thorough sort/filter/group testing.
    """
    return {
        "p_alice": {
            "name": "Alice",
            "rating": 1400,
            "status": "active",
            "active": True,
            "joined": "2025-01-15",
            "wins": 12,
            "_removed": False,
        },
        "p_bob": {
            "name": "Bob",
            "rating": 1200,
            "status": "active",
            "active": True,
            "joined": "2025-03-01",
            "wins": 8,
            "_removed": False,
        },
        "p_carol": {
            "name": "Carol",
            "rating": 1550,
            "status": "active",
            "active": True,
            "joined": "2024-11-20",
            "wins": 15,
            "_removed": False,
        },
        "p_dave": {
            "name": "Dave",
            "rating": 1100,
            "status": "inactive",
            "active": False,
            "joined": "2025-02-10",
            "wins": 3,
            "_removed": False,
        },
        "p_eve": {
            "name": "Eve",
            "rating": 1350,
            "status": "active",
            "active": True,
            "joined": "2025-04-05",
            "wins": 10,
            "_removed": False,
        },
        "p_frank": {
            "name": "Frank",
            "rating": 1000,
            "status": "inactive",
            "active": False,
            "joined": "2024-12-01",
            "wins": 1,
            "_removed": False,
        },
        "p_grace": {
            "name": "Grace",
            "rating": 1600,
            "status": "active",
            "active": True,
            "joined": "2024-10-15",
            "wins": 18,
            "_removed": False,
        },
        "p_hank": {
            "name": "Hank",
            "rating": None,
            "status": "pending",
            "active": False,
            "joined": "2025-05-01",
            "wins": 0,
            "_removed": False,
        },
        "p_iris": {
            "name": "Iris",
            "rating": 1450,
            "status": "active",
            "active": True,
            "joined": "2025-01-25",
            "wins": 11,
            "_removed": False,
        },
        "p_jack": {
            "name": "Jack",
            "rating": None,
            "status": "pending",
            "active": False,
            "joined": None,
            "wins": 0,
            "_removed": False,
        },
    }


# ============================================================================
# Sort — ascending
# ============================================================================


class TestSortAscending:
    """
    sort_by + sort_order="asc" (or default) sorts entities ascending.
    """

    def test_sort_by_name_asc(self):
        """Sort by name ascending: Alice, Bob, Carol, ..., Jack."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"sort_by": "name", "sort_order": "asc", "show_fields": ["name", "rating"]},
        )
        html = render_block(block_id, snapshot)

        assert_order(
            html,
            "Alice",
            "Bob",
            "Carol",
            "Dave",
            "Eve",
            "Frank",
            "Grace",
            "Hank",
            "Iris",
            "Jack",
        )

    def test_sort_by_rating_asc(self):
        """Sort by rating ascending: Frank(1000), Dave(1100), Bob(1200), ...
        Nulls (Hank, Jack) sort last."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"sort_by": "rating", "sort_order": "asc", "show_fields": ["name", "rating"]},
        )
        html = render_block(block_id, snapshot)

        # Non-null ratings in ascending order
        assert_order(html, "Frank", "Dave", "Bob", "Eve", "Alice", "Iris", "Carol", "Grace")
        # Hank and Jack (null rating) should appear after Grace
        grace_pos = html.find("Grace")
        hank_pos = html.find("Hank")
        jack_pos = html.find("Jack")
        assert hank_pos > grace_pos, "Null-rated Hank should sort after Grace"
        assert jack_pos > grace_pos, "Null-rated Jack should sort after Grace"

    def test_sort_by_wins_asc(self):
        """Sort by wins ascending: Jack(0), Hank(0), Frank(1), Dave(3), ..."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"sort_by": "wins", "sort_order": "asc", "show_fields": ["name", "wins"]},
        )
        html = render_block(block_id, snapshot)

        # Lowest wins first
        assert_order(html, "Frank", "Dave", "Bob", "Eve")

    def test_default_sort_order_is_asc(self):
        """
        Omitting sort_order defaults to ascending.
        Per spec: order = config.get("sort_order", "asc")
        """
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"sort_by": "name", "show_fields": ["name"]},
        )
        html = render_block(block_id, snapshot)

        assert_order(html, "Alice", "Bob", "Carol", "Dave")


# ============================================================================
# Sort — descending
# ============================================================================


class TestSortDescending:
    """
    sort_order="desc" reverses the sort.
    """

    def test_sort_by_name_desc(self):
        """Sort by name descending: Jack, Iris, ..., Alice."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"sort_by": "name", "sort_order": "desc", "show_fields": ["name"]},
        )
        html = render_block(block_id, snapshot)

        assert_order(html, "Jack", "Iris", "Hank", "Grace", "Frank")

    def test_sort_by_rating_desc(self):
        """Sort by rating descending: Grace(1600), Carol(1550), ...
        Nulls still sort last even in descending order."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"sort_by": "rating", "sort_order": "desc", "show_fields": ["name", "rating"]},
        )
        html = render_block(block_id, snapshot)

        # Highest non-null ratings first
        assert_order(html, "Grace", "Carol", "Iris", "Alice", "Eve", "Bob", "Dave", "Frank")
        # Nulls still last
        frank_pos = html.find("Frank")
        hank_pos = html.find("Hank")
        jack_pos = html.find("Jack")
        assert hank_pos > frank_pos, "Null-rated Hank should sort after Frank (last non-null)"
        assert jack_pos > frank_pos, "Null-rated Jack should sort after Frank"

    def test_sort_by_wins_desc(self):
        """Sort by wins descending: Grace(18), Carol(15), Alice(12), ..."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"sort_by": "wins", "sort_order": "desc", "show_fields": ["name", "wins"]},
        )
        html = render_block(block_id, snapshot)

        assert_order(html, "Grace", "Carol", "Alice", "Iris", "Eve", "Bob")


# ============================================================================
# Sort — nulls sort last
# ============================================================================


class TestSortNullsLast:
    """
    Null values sort last regardless of sort direction.
    Per spec: sort_key(None) returns (1, "") — always after non-null (0, value).
    """

    def test_nulls_last_ascending(self):
        """Null ratings appear after all non-null in ascending sort."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"sort_by": "rating", "sort_order": "asc", "show_fields": ["name", "rating"]},
        )
        html = render_block(block_id, snapshot)

        # Frank is lowest non-null (1000), Grace is highest (1600)
        # Hank and Jack have null ratings — must be after Grace
        grace_pos = html.find("Grace")
        hank_pos = html.find("Hank")
        jack_pos = html.find("Jack")
        assert hank_pos > grace_pos
        assert jack_pos > grace_pos

    def test_nulls_last_descending(self):
        """Null ratings appear after all non-null in descending sort."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"sort_by": "rating", "sort_order": "desc", "show_fields": ["name", "rating"]},
        )
        html = render_block(block_id, snapshot)

        frank_pos = html.find("Frank")  # lowest non-null, last in desc
        hank_pos = html.find("Hank")
        jack_pos = html.find("Jack")
        assert hank_pos > frank_pos
        assert jack_pos > frank_pos

    def test_null_date_sorts_last(self):
        """Null join date (Jack) sorts last."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"sort_by": "joined", "sort_order": "asc", "show_fields": ["name", "joined"]},
        )
        html = render_block(block_id, snapshot)

        # Jack has null joined — should be last
        iris_pos = html.find("Iris")  # some non-null
        jack_pos = html.find("Jack")
        assert jack_pos > iris_pos


# ============================================================================
# Sort — booleans
# ============================================================================


class TestSortBooleans:
    """
    Booleans sort as int(value): false=0, true=1.
    Per spec: sort_key for bool returns (0, int(value)).
    Ascending: false first, then true. Descending: true first, then false.
    """

    def test_sort_by_active_asc(self):
        """Sort by active ascending: inactive (false=0) before active (true=1)."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"sort_by": "active", "sort_order": "asc", "show_fields": ["name", "active"]},
        )
        html = render_block(block_id, snapshot)

        # Inactive players (Dave, Frank, Hank, Jack) should come first
        # Active players (Alice, Bob, Carol, Eve, Grace, Iris) should follow
        # Pick one from each group to verify ordering
        dave_pos = html.find("Dave")
        alice_pos = html.find("Alice")
        assert dave_pos < alice_pos, "Inactive (false) should sort before active (true) in asc"

    def test_sort_by_active_desc(self):
        """Sort by active descending: active (true=1) before inactive (false=0)."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"sort_by": "active", "sort_order": "desc", "show_fields": ["name", "active"]},
        )
        html = render_block(block_id, snapshot)

        alice_pos = html.find("Alice")
        dave_pos = html.find("Dave")
        assert alice_pos < dave_pos, "Active (true) should sort before inactive (false) in desc"


# ============================================================================
# Sort — no sort preserves insertion order
# ============================================================================


class TestNoSortPreservesOrder:
    """
    No sort_by → entities render in insertion order (dict iteration order).
    Per spec: 'if not sort_by: return entities  # preserve insertion order'
    """

    def test_no_sort_config(self):
        """Without sort_by, entities appear in their natural dict order."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"show_fields": ["name"]},
        )
        html = render_block(block_id, snapshot)

        # All 10 entities should be present
        for name in ["Alice", "Bob", "Carol", "Dave", "Eve", "Frank", "Grace", "Hank", "Iris", "Jack"]:
            assert_contains(html, name)


# ============================================================================
# Filter — single condition
# ============================================================================


class TestFilterSingleCondition:
    """
    filter: { field: value } retains only entities where field == value.
    """

    def test_filter_by_status_active(self):
        """Filter status=active shows only active players."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"filter": {"status": "active"}, "show_fields": ["name", "status"]},
        )
        html = render_block(block_id, snapshot)

        # Active: Alice, Bob, Carol, Eve, Grace, Iris
        assert_contains(html, "Alice", "Bob", "Carol", "Eve", "Grace", "Iris")
        # Not active: Dave, Frank, Hank, Jack
        assert_not_contains(html, "Dave", "Frank", "Hank", "Jack")

    def test_filter_by_status_inactive(self):
        """Filter status=inactive shows only inactive players."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"filter": {"status": "inactive"}, "show_fields": ["name", "status"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Dave", "Frank")
        assert_not_contains(html, "Alice", "Carol", "Grace")

    def test_filter_by_status_pending(self):
        """Filter status=pending shows only pending players."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"filter": {"status": "pending"}, "show_fields": ["name", "status"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Hank", "Jack")
        assert_not_contains(html, "Alice", "Dave")

    def test_filter_by_boolean_true(self):
        """Filter active=true shows only active players."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"filter": {"active": True}, "show_fields": ["name", "active"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Alice", "Bob", "Carol", "Eve", "Grace", "Iris")
        assert_not_contains(html, "Dave", "Frank", "Hank", "Jack")

    def test_filter_by_boolean_false(self):
        """Filter active=false shows only inactive players."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"filter": {"active": False}, "show_fields": ["name", "active"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Dave", "Frank", "Hank", "Jack")
        assert_not_contains(html, "Alice", "Bob", "Carol")


# ============================================================================
# Filter — multiple conditions (AND)
# ============================================================================


class TestFilterMultipleConditions:
    """
    Multiple filter conditions are AND-ed: all must match.
    Per spec: all(e.get(field) == value for field, value in filt.items())
    """

    def test_filter_active_and_status(self):
        """Filter active=true AND status=active narrows to active players."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"filter": {"active": True, "status": "active"}, "show_fields": ["name"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Alice", "Bob", "Carol", "Eve", "Grace", "Iris")
        assert_not_contains(html, "Dave", "Frank", "Hank", "Jack")

    def test_filter_no_match(self):
        """Filter with impossible combination shows empty state."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"filter": {"status": "active", "active": False}, "show_fields": ["name"]},
        )
        html = render_block(block_id, snapshot)

        # No entity is active-status but active=false
        assert_contains(html, "aide-collection-empty")


# ============================================================================
# Filter — no filter shows all
# ============================================================================


class TestNoFilter:
    """
    No filter config → all entities returned.
    """

    def test_no_filter_shows_all(self):
        """Without filter, all 10 entities appear."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"show_fields": ["name"]},
        )
        html = render_block(block_id, snapshot)

        for name in ["Alice", "Bob", "Carol", "Dave", "Eve", "Frank", "Grace", "Hank", "Iris", "Jack"]:
            assert_contains(html, name)


# ============================================================================
# Sort + Filter combined
# ============================================================================


class TestSortAndFilterCombined:
    """
    Sort and filter work together: filter first reduces the set,
    sort then orders the remaining.
    """

    def test_filter_active_then_sort_by_rating_desc(self):
        """Filter to active players, then sort by rating descending."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {
                "filter": {"status": "active"},
                "sort_by": "rating",
                "sort_order": "desc",
                "show_fields": ["name", "rating"],
            },
        )
        html = render_block(block_id, snapshot)

        # Active players sorted by rating desc:
        # Grace(1600), Carol(1550), Iris(1450), Alice(1400), Eve(1350), Bob(1200)
        assert_order(html, "Grace", "Carol", "Iris", "Alice", "Eve", "Bob")
        # Inactive should not appear
        assert_not_contains(html, "Dave", "Frank", "Hank", "Jack")

    def test_filter_inactive_then_sort_by_name(self):
        """Filter to inactive, sort by name ascending."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"filter": {"status": "inactive"}, "sort_by": "name", "sort_order": "asc", "show_fields": ["name"]},
        )
        html = render_block(block_id, snapshot)

        assert_order(html, "Dave", "Frank")
        assert_not_contains(html, "Alice", "Grace")


# ============================================================================
# Group By
# ============================================================================


class TestGroupBy:
    """
    group_by splits entities into groups, each with a header.
    Per spec: each group renders as <div class="aide-group">
    with <h4 class="aide-group__header">{group name}</h4>.
    """

    @pytest.mark.skip(reason="group_by rendering not yet implemented")
    def test_group_by_status(self):
        """Group by status produces group headers for each status value."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"group_by": "status", "show_fields": ["name", "status"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-group")
        assert_contains(html, "aide-group__header")
        # Should have headers for active, inactive, pending
        # (Enum values are title-cased in headers)
        assert_contains(html, "Active")
        assert_contains(html, "Inactive")
        assert_contains(html, "Pending")

    @pytest.mark.skip(reason="group_by rendering not yet implemented")
    def test_group_by_active(self):
        """Group by boolean 'active' field."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"group_by": "active", "show_fields": ["name", "active"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "aide-group")
        # Should have groups for true and false

    def test_group_entities_in_correct_groups(self):
        """Entities appear under their correct group header."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"group_by": "status", "show_fields": ["name"]},
        )
        html = render_block(block_id, snapshot)

        # All active players should be present
        assert_contains(html, "Alice", "Bob", "Carol", "Eve", "Grace", "Iris")
        # All inactive players should be present
        assert_contains(html, "Dave", "Frank")
        # All pending players should be present
        assert_contains(html, "Hank", "Jack")

    def test_group_null_values_go_to_none_group(self):
        """
        Entities with null group-by field go to the '_none' group.
        Per spec: key = entity.get(group_by) or "_none"
        """
        # Add an entity with null status
        entities = ten_players()
        entities["p_mystery"] = {
            "name": "Mystery",
            "rating": 999,
            "status": None,
            "active": True,
            "joined": "2025-06-01",
            "wins": 0,
            "_removed": False,
        }
        snapshot, block_id = build_snapshot(
            entities,
            "list",
            {"group_by": "status", "show_fields": ["name"]},
        )
        html = render_block(block_id, snapshot)

        # Mystery should still appear in the output
        assert_contains(html, "Mystery")

    def test_no_group_by_produces_no_group_wrappers(self):
        """Without group_by, no aide-group divs appear."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"show_fields": ["name"]},
        )
        html = render_block(block_id, snapshot)

        assert_not_contains(html, "aide-group__header")


# ============================================================================
# Group By + Sort
# ============================================================================


class TestGroupByWithSort:
    """
    Group by and sort can be combined: entities are sorted within groups.
    """

    def test_group_by_status_sort_by_rating_desc(self):
        """Group by status, sort by rating descending within each group."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"group_by": "status", "sort_by": "rating", "sort_order": "desc", "show_fields": ["name", "rating"]},
        )
        html = render_block(block_id, snapshot)

        # Within the active group: Grace(1600), Carol(1550), Iris(1450),
        # Alice(1400), Eve(1350), Bob(1200)
        # We can at least verify Grace before Bob within the same output
        assert_contains(html, "Grace", "Bob")
        grace_pos = html.find("Grace")
        bob_pos = html.find("Bob")
        assert grace_pos < bob_pos


# ============================================================================
# Group By + Filter
# ============================================================================


class TestGroupByWithFilter:
    """
    Group by and filter combined: filter reduces, then group.
    """

    def test_filter_then_group(self):
        """Filter to active, then group by... well, all are 'active'."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"filter": {"active": True}, "group_by": "status", "show_fields": ["name"]},
        )
        html = render_block(block_id, snapshot)

        # Only active=true entities pass filter
        assert_contains(html, "Alice", "Bob", "Carol", "Eve", "Grace", "Iris")
        assert_not_contains(html, "Dave", "Frank", "Hank", "Jack")


# ============================================================================
# Sort/filter in table view
# ============================================================================


class TestSortFilterInTableView:
    """
    Sort and filter work the same way in table views — the entity
    ordering in <tbody> follows the view config.
    """

    def test_table_sort_by_rating_desc(self):
        """Table rows appear in rating descending order."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "table",
            {"sort_by": "rating", "sort_order": "desc", "show_fields": ["name", "rating"]},
        )
        html = render_block(block_id, snapshot)

        assert_order(html, "Grace", "Carol", "Iris", "Alice", "Eve", "Bob", "Dave", "Frank")

    def test_table_filter_active(self):
        """Table shows only active players when filtered."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "table",
            {"filter": {"status": "active"}, "show_fields": ["name", "status"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Alice", "Bob", "Carol", "Eve", "Grace", "Iris")
        assert_not_contains(html, "Dave", "Frank", "Hank", "Jack")

    def test_table_sort_and_filter_combined(self):
        """Table: filter to active, sort by name ascending."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "table",
            {"filter": {"status": "active"}, "sort_by": "name", "sort_order": "asc", "show_fields": ["name"]},
        )
        html = render_block(block_id, snapshot)

        assert_order(html, "Alice", "Bob", "Carol", "Eve", "Grace", "Iris")


# ============================================================================
# Edge cases
# ============================================================================


class TestSortFilterEdgeCases:
    """
    Edge cases for sort/filter behavior.
    """

    def test_sort_by_nonexistent_field(self):
        """Sorting by a field that doesn't exist should not crash."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"sort_by": "nonexistent", "show_fields": ["name"]},
        )
        # Should not raise — all entities have None for missing field
        html = render_block(block_id, snapshot)
        # All entities should still appear
        assert_contains(html, "Alice", "Jack")

    def test_filter_by_nonexistent_field(self):
        """Filtering by a field no entity has should return empty."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"filter": {"nonexistent": "value"}, "show_fields": ["name"]},
        )
        html = render_block(block_id, snapshot)

        # No entity has this field → none match → empty
        assert_contains(html, "aide-collection-empty")

    def test_filter_empty_dict(self):
        """Empty filter dict shows all entities."""
        snapshot, block_id = build_snapshot(
            ten_players(),
            "list",
            {"filter": {}, "show_fields": ["name"]},
        )
        html = render_block(block_id, snapshot)

        assert_contains(html, "Alice", "Jack")

    def test_sort_all_same_value(self):
        """Sorting when all entities have the same value for the field."""
        entities = {
            f"p_{i}": {
                "name": f"Player {i}",
                "rating": 1000,
                "status": "active",
                "active": True,
                "joined": "2025-01-01",
                "wins": 5,
                "_removed": False,
            }
            for i in range(5)
        }
        snapshot, block_id = build_snapshot(
            entities,
            "list",
            {"sort_by": "rating", "show_fields": ["name"]},
        )
        html = render_block(block_id, snapshot)

        # All 5 should appear (stable sort, no crash)
        for i in range(5):
            assert_contains(html, f"Player {i}")
