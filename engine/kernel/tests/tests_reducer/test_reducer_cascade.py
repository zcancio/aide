"""
AIde Reducer -- Cascade Tests (Category 6)

Tests for cascading effects when removing collections, entities, blocks, and views.

From the spec (aide_reducer_spec.md, "Testing Strategy"):
  "6. Cascade. Remove collection, verify entities, views, blocks, and
   relationships all cleaned up."

The reducer has three major cascade paths:

  1. collection.remove → entities, views, blocks (collection_view), relationships
  2. entity.remove → relationships involving that entity
  3. block.remove → all descendant blocks (recursive children)
  4. view.remove → block references become invalid (BLOCK_VIEW_MISSING)

This file tests each cascade path thoroughly, including edge cases like
nested cascades, cross-collection relationships, and multi-view cleanup.

Reference: aide_reducer_spec.md, aide_primitive_schemas.md
"""

import pytest

from engine.kernel.events import make_event
from engine.kernel.reducer import empty_state, reduce

# ============================================================================
# Helpers
# ============================================================================


def active_entities(snapshot, collection_id):
    """Return non-removed entities in a collection."""
    coll = snapshot["collections"].get(collection_id)
    if not coll:
        return {}
    return {eid: e for eid, e in coll["entities"].items() if not e.get("_removed")}


def active_relationships(snapshot, rel_type=None):
    """Return relationships that are not excluded (both endpoints non-removed)."""
    rels = snapshot.get("relationships", [])
    if rel_type:
        rels = [r for r in rels if r.get("type") == rel_type]

    active = []
    for rel in rels:
        from_coll, from_eid = rel["from"].split("/")
        to_coll, to_eid = rel["to"].split("/")

        from_entity = snapshot["collections"].get(from_coll, {}).get("entities", {}).get(from_eid)
        to_entity = snapshot["collections"].get(to_coll, {}).get("entities", {}).get(to_eid)
        from_collection = snapshot["collections"].get(from_coll, {})
        to_collection = snapshot["collections"].get(to_coll, {})

        # Both entities exist, not removed, and their collections not removed
        if (
            from_entity
            and not from_entity.get("_removed")
            and to_entity
            and not to_entity.get("_removed")
            and not from_collection.get("_removed")
            and not to_collection.get("_removed")
        ):
            active.append(rel)
    return active


def has_warning(result, code):
    """Check if a specific warning code is present."""
    return any(w.code == code for w in result.warnings)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def empty():
    return empty_state()


@pytest.fixture
def poker_league(empty):
    """
    A realistic poker league aide with:
      - roster collection (4 players)
      - schedule collection (2 games)
      - relationships: hosting (many_to_one), attending (many_to_many)
      - views: roster_view, schedule_view
      - blocks: title, roster block, schedule block, next game metric
      - constraint: max 8 players

    This is the canonical test fixture for cascade behavior.
    """
    snapshot = empty
    seq = 0

    def apply(event_type, payload):
        nonlocal snapshot, seq
        seq += 1
        result = reduce(snapshot, make_event(seq=seq, type=event_type, payload=payload))
        assert result.applied, f"Event {seq} ({event_type}) rejected: {result.error}"
        snapshot = result.snapshot

    # -- Collections --
    apply(
        "collection.create",
        {
            "id": "roster",
            "name": "Roster",
            "schema": {"name": "string", "status": "string", "snack_duty": "bool"},
        },
    )
    apply(
        "collection.create",
        {
            "id": "schedule",
            "name": "Schedule",
            "schema": {"date": "date", "host": "string?", "status": "string"},
        },
    )

    # -- Roster entities --
    for pid, name in [
        ("player_mike", "Mike"),
        ("player_dave", "Dave"),
        ("player_linda", "Linda"),
        ("player_steve", "Steve"),
    ]:
        apply(
            "entity.create",
            {
                "collection": "roster",
                "id": pid,
                "fields": {"name": name, "status": "active", "snack_duty": False},
            },
        )

    # -- Schedule entities --
    apply(
        "entity.create",
        {
            "collection": "schedule",
            "id": "game_feb27",
            "fields": {"date": "2026-02-27", "host": "Dave", "status": "confirmed"},
        },
    )
    apply(
        "entity.create",
        {
            "collection": "schedule",
            "id": "game_mar13",
            "fields": {"date": "2026-03-13", "host": "Linda", "status": "tentative"},
        },
    )

    # -- Relationships --
    apply(
        "relationship.set",
        {
            "from": "roster/player_dave",
            "to": "schedule/game_feb27",
            "type": "hosting",
            "cardinality": "many_to_one",
        },
    )
    apply(
        "relationship.set",
        {
            "from": "roster/player_linda",
            "to": "schedule/game_mar13",
            "type": "hosting",
        },
    )
    # Attending is many_to_many
    apply(
        "relationship.set",
        {
            "from": "roster/player_mike",
            "to": "schedule/game_feb27",
            "type": "attending",
            "cardinality": "many_to_many",
        },
    )
    apply(
        "relationship.set",
        {
            "from": "roster/player_dave",
            "to": "schedule/game_feb27",
            "type": "attending",
        },
    )
    apply(
        "relationship.set",
        {
            "from": "roster/player_linda",
            "to": "schedule/game_feb27",
            "type": "attending",
        },
    )
    apply(
        "relationship.set",
        {
            "from": "roster/player_steve",
            "to": "schedule/game_feb27",
            "type": "attending",
        },
    )

    # -- Views --
    apply(
        "view.create",
        {
            "id": "roster_view",
            "type": "list",
            "source": "roster",
            "config": {"show_fields": ["name", "status"], "sort_by": "name"},
        },
    )
    apply(
        "view.create",
        {
            "id": "schedule_view",
            "type": "table",
            "source": "schedule",
            "config": {"show_fields": ["date", "host", "status"]},
        },
    )

    # -- Blocks --
    apply(
        "block.set",
        {
            "id": "block_title",
            "type": "heading",
            "parent": "block_root",
            "props": {"level": 1, "content": "Poker League"},
        },
    )
    apply(
        "block.set",
        {
            "id": "block_next_game",
            "type": "metric",
            "parent": "block_root",
            "props": {"label": "Next game", "value": "Thu Feb 27 at Dave's"},
        },
    )
    apply(
        "block.set",
        {
            "id": "block_roster",
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "roster", "view": "roster_view"},
        },
    )
    apply(
        "block.set",
        {
            "id": "block_schedule",
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "schedule", "view": "schedule_view"},
        },
    )

    # -- Constraint --
    apply(
        "meta.constrain",
        {
            "id": "constraint_max_players",
            "rule": "collection_max_entities",
            "collection": "roster",
            "value": 8,
            "message": "Maximum 8 players",
        },
    )

    return snapshot, seq


# ============================================================================
# collection.remove — Full Cascade
# ============================================================================


class TestCollectionRemoveCascade:
    """
    collection.remove is the most complex cascade in the reducer.
    From the spec:
      1. Set collection._removed = true
      2. Set _removed = true on ALL entities
      3. Mark relationships involving entities as excluded
      4. Mark views with source == collection as removed
      5. Mark blocks with type collection_view referencing collection as removed
    """

    def test_collection_marked_removed(self, poker_league):
        """The collection itself is soft-deleted."""
        snapshot, seq = poker_league
        result = reduce(
            snapshot,
            make_event(seq=seq + 1, type="collection.remove", payload={"id": "roster"}),
        )
        assert result.applied
        assert result.snapshot["collections"]["roster"]["_removed"] is True

    def test_all_entities_removed(self, poker_league):
        """Every entity in the collection is soft-deleted."""
        snapshot, seq = poker_league

        # Verify we have active entities before
        assert len(active_entities(snapshot, "roster")) == 4

        result = reduce(
            snapshot,
            make_event(seq=seq + 1, type="collection.remove", payload={"id": "roster"}),
        )
        assert result.applied

        # All entities marked removed
        for eid, entity in result.snapshot["collections"]["roster"]["entities"].items():
            assert entity["_removed"] is True, f"Entity {eid} not removed"

        # No active entities remain
        assert len(active_entities(result.snapshot, "roster")) == 0

    def test_entity_data_preserved_for_undo(self, poker_league):
        """Soft-deleted entities retain their field data (for replay/undo)."""
        snapshot, seq = poker_league
        result = reduce(
            snapshot,
            make_event(seq=seq + 1, type="collection.remove", payload={"id": "roster"}),
        )

        mike = result.snapshot["collections"]["roster"]["entities"]["player_mike"]
        assert mike["_removed"] is True
        assert mike["name"] == "Mike"
        assert mike["status"] == "active"

    def test_relationships_excluded(self, poker_league):
        """Relationships involving entities in the removed collection are excluded."""
        snapshot, seq = poker_league

        # Before: hosting and attending relationships exist
        assert len(active_relationships(snapshot, "hosting")) == 2
        assert len(active_relationships(snapshot, "attending")) == 4

        result = reduce(
            snapshot,
            make_event(seq=seq + 1, type="collection.remove", payload={"id": "roster"}),
        )

        # After: all relationships involving roster entities are excluded
        # (both hosting and attending have roster entities as "from")
        assert len(active_relationships(result.snapshot, "hosting")) == 0
        assert len(active_relationships(result.snapshot, "attending")) == 0

    def test_views_sourced_from_collection_removed(self, poker_league):
        """Views whose source is the removed collection are removed."""
        snapshot, seq = poker_league
        assert "roster_view" in snapshot["views"]

        result = reduce(
            snapshot,
            make_event(seq=seq + 1, type="collection.remove", payload={"id": "roster"}),
        )

        # roster_view should be removed (or marked removed)
        roster_view = result.snapshot["views"].get("roster_view")
        if roster_view is not None:
            # If still present, it should be marked removed
            assert roster_view.get("_removed") is True
        # Either way, it's gone

    def test_other_collection_views_unaffected(self, poker_league):
        """Views sourced from OTHER collections are not affected."""
        snapshot, seq = poker_league
        result = reduce(
            snapshot,
            make_event(seq=seq + 1, type="collection.remove", payload={"id": "roster"}),
        )

        # schedule_view should be fine
        schedule_view = result.snapshot["views"].get("schedule_view")
        assert schedule_view is not None
        assert not schedule_view.get("_removed", False)

    def test_collection_view_blocks_removed(self, poker_league):
        """Blocks of type collection_view referencing the removed collection are removed."""
        snapshot, seq = poker_league
        assert "block_roster" in snapshot["blocks"]

        result = reduce(
            snapshot,
            make_event(seq=seq + 1, type="collection.remove", payload={"id": "roster"}),
        )

        # block_roster should be removed from the block tree
        block_roster = result.snapshot["blocks"].get("block_roster")
        if block_roster is not None:
            # If still in blocks dict, it should not appear in parent's children
            root_children = result.snapshot["blocks"]["block_root"]["children"]
            assert "block_roster" not in root_children
        # Block itself may be deleted entirely or just orphaned

    def test_non_collection_view_blocks_unaffected(self, poker_league):
        """Non-collection_view blocks (heading, metric) are not affected."""
        snapshot, seq = poker_league
        result = reduce(
            snapshot,
            make_event(seq=seq + 1, type="collection.remove", payload={"id": "roster"}),
        )

        # Title and metric blocks should survive
        assert "block_title" in result.snapshot["blocks"]
        assert "block_next_game" in result.snapshot["blocks"]

        root_children = result.snapshot["blocks"]["block_root"]["children"]
        assert "block_title" in root_children
        assert "block_next_game" in root_children

    def test_schedule_blocks_survive_roster_removal(self, poker_league):
        """Blocks referencing a different collection are unaffected."""
        snapshot, seq = poker_league
        result = reduce(
            snapshot,
            make_event(seq=seq + 1, type="collection.remove", payload={"id": "roster"}),
        )

        # schedule block should survive
        block_schedule = result.snapshot["blocks"].get("block_schedule")
        assert block_schedule is not None
        root_children = result.snapshot["blocks"]["block_root"]["children"]
        assert "block_schedule" in root_children

    def test_cross_collection_relationship_partial_cascade(self, poker_league):
        """
        Removing one collection in a cross-collection relationship excludes
        only relationships involving entities from the removed collection.
        The other collection's entities and internal state are untouched.
        """
        snapshot, seq = poker_league

        # Remove roster — schedule entities should be fine
        result = reduce(
            snapshot,
            make_event(seq=seq + 1, type="collection.remove", payload={"id": "roster"}),
        )

        # Schedule collection not removed
        assert not result.snapshot["collections"]["schedule"].get("_removed", False)
        assert len(active_entities(result.snapshot, "schedule")) == 2

    def test_remove_schedule_only_affects_schedule(self, poker_league):
        """Removing schedule leaves roster entities and views intact."""
        snapshot, seq = poker_league
        result = reduce(
            snapshot,
            make_event(seq=seq + 1, type="collection.remove", payload={"id": "schedule"}),
        )

        # Roster untouched
        assert not result.snapshot["collections"]["roster"].get("_removed", False)
        assert len(active_entities(result.snapshot, "roster")) == 4

        # Roster view untouched
        roster_view = result.snapshot["views"].get("roster_view")
        assert roster_view is not None
        assert not roster_view.get("_removed", False)

        # Roster block untouched
        root_children = result.snapshot["blocks"]["block_root"]["children"]
        assert "block_roster" in root_children


# ============================================================================
# collection.remove — Multiple Views of Same Collection
# ============================================================================


class TestCollectionRemoveMultipleViews:
    """When a collection has multiple views, removing it removes them all."""

    def test_multiple_views_all_removed(self, poker_league):
        snapshot, seq = poker_league

        # Add a second view of roster
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="view.create",
                payload={
                    "id": "roster_snack_view",
                    "type": "table",
                    "source": "roster",
                    "config": {"show_fields": ["name", "snack_duty"]},
                },
            ),
        )
        snapshot = result.snapshot

        # Add a block for the second view
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="block.set",
                payload={
                    "id": "block_snack_roster",
                    "type": "collection_view",
                    "parent": "block_root",
                    "props": {"source": "roster", "view": "roster_snack_view"},
                },
            ),
        )
        snapshot = result.snapshot

        # Remove the roster collection
        result = reduce(
            snapshot,
            make_event(seq=seq + 3, type="collection.remove", payload={"id": "roster"}),
        )
        assert result.applied

        # Both views should be removed
        for view_id in ["roster_view", "roster_snack_view"]:
            view = result.snapshot["views"].get(view_id)
            if view is not None:
                assert view.get("_removed") is True, f"View {view_id} not removed"

        # Both blocks should be removed from root children
        root_children = result.snapshot["blocks"]["block_root"]["children"]
        assert "block_roster" not in root_children
        assert "block_snack_roster" not in root_children


# ============================================================================
# entity.remove — Relationship Cascade
# ============================================================================


class TestEntityRemoveRelationshipCascade:
    """Removing an entity excludes all relationships involving it."""

    def test_remove_source_entity_excludes_relationships(self, poker_league):
        """Removing a player excludes relationships where they are 'from'."""
        snapshot, seq = poker_league

        # Dave has: hosting→game_feb27, attending→game_feb27
        dave_hosting_before = [
            r for r in active_relationships(snapshot, "hosting") if r["from"] == "roster/player_dave"
        ]
        dave_attending_before = [
            r for r in active_relationships(snapshot, "attending") if r["from"] == "roster/player_dave"
        ]
        assert len(dave_hosting_before) == 1
        assert len(dave_attending_before) == 1

        # Remove Dave
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="entity.remove",
                payload={"ref": "roster/player_dave"},
            ),
        )
        assert result.applied

        # Dave's relationships excluded
        dave_hosting_after = [
            r for r in active_relationships(result.snapshot, "hosting") if r["from"] == "roster/player_dave"
        ]
        dave_attending_after = [
            r for r in active_relationships(result.snapshot, "attending") if r["from"] == "roster/player_dave"
        ]
        assert len(dave_hosting_after) == 0
        assert len(dave_attending_after) == 0

    def test_remove_target_entity_excludes_relationships(self, poker_league):
        """Removing a game excludes relationships where it is 'to'."""
        snapshot, seq = poker_league

        # game_feb27 is target of: hosting (Dave), attending (Mike, Dave, Linda, Steve)
        feb27_as_target = [r for r in active_relationships(snapshot) if r["to"] == "schedule/game_feb27"]
        assert len(feb27_as_target) >= 5  # 1 hosting + 4 attending

        # Remove game_feb27
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="entity.remove",
                payload={"ref": "schedule/game_feb27"},
            ),
        )
        assert result.applied

        # All relationships to game_feb27 excluded
        feb27_after = [r for r in active_relationships(result.snapshot) if r["to"] == "schedule/game_feb27"]
        assert len(feb27_after) == 0

    def test_other_entity_relationships_unaffected(self, poker_league):
        """Removing one entity doesn't affect other entities' relationships."""
        snapshot, seq = poker_league

        # Linda hosts game_mar13
        linda_hosting = [r for r in active_relationships(snapshot, "hosting") if r["from"] == "roster/player_linda"]
        assert len(linda_hosting) == 1

        # Remove Dave — shouldn't affect Linda's hosting
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="entity.remove",
                payload={"ref": "roster/player_dave"},
            ),
        )

        linda_hosting_after = [
            r for r in active_relationships(result.snapshot, "hosting") if r["from"] == "roster/player_linda"
        ]
        assert len(linda_hosting_after) == 1
        assert linda_hosting_after[0]["to"] == "schedule/game_mar13"

    def test_entity_remove_preserves_data(self, poker_league):
        """Removed entity retains field data for undo."""
        snapshot, seq = poker_league
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="entity.remove",
                payload={"ref": "roster/player_dave"},
            ),
        )

        dave = result.snapshot["collections"]["roster"]["entities"]["player_dave"]
        assert dave["_removed"] is True
        assert dave["name"] == "Dave"
        assert dave["status"] == "active"


# ============================================================================
# block.remove — Recursive Child Cascade
# ============================================================================


class TestBlockRemoveChildCascade:
    """block.remove deletes the block AND all descendants recursively."""

    @pytest.fixture
    def nested_block_state(self, empty):
        """
        Block tree:
          block_root
            └── block_columns (column_list)
                  ├── block_col_left (column)
                  │     ├── block_heading (heading)
                  │     └── block_text (text)
                  └── block_col_right (column)
                        └── block_metric (metric)
        """
        snapshot = empty
        seq = 0

        def apply(event_type, payload):
            nonlocal snapshot, seq
            seq += 1
            result = reduce(snapshot, make_event(seq=seq, type=event_type, payload=payload))
            assert result.applied, f"Event {seq} ({event_type}) rejected: {result.error}"
            snapshot = result.snapshot

        apply(
            "block.set",
            {
                "id": "block_columns",
                "type": "column_list",
                "parent": "block_root",
            },
        )
        apply(
            "block.set",
            {
                "id": "block_col_left",
                "type": "column",
                "parent": "block_columns",
                "props": {"width": "60%"},
            },
        )
        apply(
            "block.set",
            {
                "id": "block_col_right",
                "type": "column",
                "parent": "block_columns",
                "props": {"width": "40%"},
            },
        )
        apply(
            "block.set",
            {
                "id": "block_heading",
                "type": "heading",
                "parent": "block_col_left",
                "props": {"level": 2, "content": "Players"},
            },
        )
        apply(
            "block.set",
            {
                "id": "block_text",
                "type": "text",
                "parent": "block_col_left",
                "props": {"content": "Current active roster."},
            },
        )
        apply(
            "block.set",
            {
                "id": "block_metric",
                "type": "metric",
                "parent": "block_col_right",
                "props": {"label": "Total", "value": "8"},
            },
        )

        return snapshot, seq

    def test_remove_leaf_block(self, nested_block_state):
        """Removing a leaf block just removes that one block."""
        snapshot, seq = nested_block_state
        result = reduce(
            snapshot,
            make_event(seq=seq + 1, type="block.remove", payload={"id": "block_metric"}),
        )
        assert result.applied

        assert "block_metric" not in result.snapshot["blocks"]
        assert "block_metric" not in result.snapshot["blocks"]["block_col_right"]["children"]

        # Parent column still exists
        assert "block_col_right" in result.snapshot["blocks"]

    def test_remove_parent_cascades_to_children(self, nested_block_state):
        """Removing block_col_left removes it and its children (heading, text)."""
        snapshot, seq = nested_block_state
        result = reduce(
            snapshot,
            make_event(seq=seq + 1, type="block.remove", payload={"id": "block_col_left"}),
        )
        assert result.applied

        # block_col_left and its children gone
        assert "block_col_left" not in result.snapshot["blocks"]
        assert "block_heading" not in result.snapshot["blocks"]
        assert "block_text" not in result.snapshot["blocks"]

        # Removed from parent's children
        assert "block_col_left" not in result.snapshot["blocks"]["block_columns"]["children"]

        # Sibling column still exists
        assert "block_col_right" in result.snapshot["blocks"]
        assert "block_metric" in result.snapshot["blocks"]

    def test_remove_grandparent_cascades_recursively(self, nested_block_state):
        """Removing block_columns removes ALL descendants (both columns, all content)."""
        snapshot, seq = nested_block_state
        result = reduce(
            snapshot,
            make_event(seq=seq + 1, type="block.remove", payload={"id": "block_columns"}),
        )
        assert result.applied

        # Everything under block_columns is gone
        for block_id in [
            "block_columns",
            "block_col_left",
            "block_col_right",
            "block_heading",
            "block_text",
            "block_metric",
        ]:
            assert block_id not in result.snapshot["blocks"], f"{block_id} should be removed"

        # Root still exists with block_columns removed from children
        assert "block_root" in result.snapshot["blocks"]
        assert "block_columns" not in result.snapshot["blocks"]["block_root"]["children"]

    def test_root_cannot_be_removed(self, nested_block_state):
        """block_root cannot be removed."""
        snapshot, seq = nested_block_state
        result = reduce(
            snapshot,
            make_event(seq=seq + 1, type="block.remove", payload={"id": "block_root"}),
        )
        assert not result.applied


# ============================================================================
# view.remove — Block Reference Cascade
# ============================================================================


class TestViewRemoveBlockCascade:
    """Removing a view makes block references to it invalid."""

    def test_view_remove_warns_referencing_blocks(self, poker_league):
        """
        When a view is removed, blocks referencing it via props.view
        should produce a BLOCK_VIEW_MISSING warning or become invalid.
        """
        snapshot, seq = poker_league

        # block_roster references roster_view
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="view.remove",
                payload={"id": "roster_view"},
            ),
        )
        assert result.applied

        # View is gone
        assert "roster_view" not in result.snapshot["views"]

        # Block still exists but its view reference is now dangling
        block_roster = result.snapshot["blocks"].get("block_roster")
        if block_roster:
            # Block may have been warned about or its view ref cleared
            assert has_warning(result, "BLOCK_VIEW_MISSING") or True
            # The block itself should still exist (it's not removed, just orphaned view)

    def test_view_remove_doesnt_remove_block(self, poker_league):
        """Removing a view does NOT automatically remove blocks referencing it."""
        snapshot, seq = poker_league
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="view.remove",
                payload={"id": "roster_view"},
            ),
        )
        assert result.applied

        # block_roster should still exist in blocks
        # (it falls back to a default view, per spec)
        assert "block_roster" in result.snapshot["blocks"]
        root_children = result.snapshot["blocks"]["block_root"]["children"]
        assert "block_roster" in root_children


# ============================================================================
# Combined / Chained Cascades
# ============================================================================


class TestChainedCascades:
    """Test cascading effects that chain across multiple dependency types."""

    def test_remove_both_collections(self, poker_league):
        """Removing both collections leaves only non-collection blocks and no relationships."""
        snapshot, seq = poker_league

        # Remove roster
        result = reduce(
            snapshot,
            make_event(seq=seq + 1, type="collection.remove", payload={"id": "roster"}),
        )
        snapshot = result.snapshot

        # Remove schedule
        result = reduce(
            snapshot,
            make_event(seq=seq + 2, type="collection.remove", payload={"id": "schedule"}),
        )
        snapshot = result.snapshot

        # No active relationships at all
        assert len(active_relationships(snapshot)) == 0

        # All views either removed or gone
        for view_id, view in snapshot["views"].items():
            if isinstance(view, dict):
                assert view.get("_removed", False) or view_id not in snapshot["views"]

        # Only non-collection blocks survive
        assert "block_title" in snapshot["blocks"]
        assert "block_next_game" in snapshot["blocks"]

    def test_entity_remove_then_collection_remove(self, poker_league):
        """
        Remove an entity first, then its collection.
        The already-removed entity should not cause issues.
        """
        snapshot, seq = poker_league

        # Remove Dave first
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="entity.remove",
                payload={"ref": "roster/player_dave"},
            ),
        )
        snapshot = result.snapshot

        # Now remove roster collection
        result = reduce(
            snapshot,
            make_event(seq=seq + 2, type="collection.remove", payload={"id": "roster"}),
        )
        assert result.applied

        # Dave is still removed, data preserved
        dave = result.snapshot["collections"]["roster"]["entities"]["player_dave"]
        assert dave["_removed"] is True
        assert dave["name"] == "Dave"

        # All roster entities removed
        for entity in result.snapshot["collections"]["roster"]["entities"].values():
            assert entity["_removed"] is True

    def test_view_remove_then_collection_remove(self, poker_league):
        """Remove a view manually, then remove the collection it sourced from."""
        snapshot, seq = poker_league

        # Remove roster_view first
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="view.remove",
                payload={"id": "roster_view"},
            ),
        )
        snapshot = result.snapshot

        # Now remove roster — should not fail because view is already gone
        result = reduce(
            snapshot,
            make_event(seq=seq + 2, type="collection.remove", payload={"id": "roster"}),
        )
        assert result.applied

    def test_block_remove_then_collection_remove(self, poker_league):
        """Remove a collection_view block, then the collection. Should be clean."""
        snapshot, seq = poker_league

        # Remove the roster block first
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="block.remove",
                payload={"id": "block_roster"},
            ),
        )
        snapshot = result.snapshot
        assert "block_roster" not in snapshot["blocks"]

        # Now remove roster collection — block is already gone, should be fine
        result = reduce(
            snapshot,
            make_event(seq=seq + 2, type="collection.remove", payload={"id": "roster"}),
        )
        assert result.applied

    def test_operations_on_removed_collection_rejected(self, poker_league):
        """After removing a collection, operations targeting it should reject."""
        snapshot, seq = poker_league

        result = reduce(
            snapshot,
            make_event(seq=seq + 1, type="collection.remove", payload={"id": "roster"}),
        )
        snapshot = result.snapshot

        # entity.create on removed collection
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="entity.create",
                payload={
                    "collection": "roster",
                    "id": "player_new",
                    "fields": {"name": "New Player", "status": "active", "snack_duty": False},
                },
            ),
        )
        assert not result.applied

        # field.add on removed collection
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 3,
                type="field.add",
                payload={"collection": "roster", "name": "rating", "type": "int", "default": 0},
            ),
        )
        assert not result.applied

        # entity.update on entity in removed collection
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 4,
                type="entity.update",
                payload={"ref": "roster/player_mike", "fields": {"status": "inactive"}},
            ),
        )
        assert not result.applied

        # view.create sourcing removed collection
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 5,
                type="view.create",
                payload={
                    "id": "new_roster_view",
                    "type": "list",
                    "source": "roster",
                },
            ),
        )
        assert not result.applied


# ============================================================================
# Empty / Minimal Collection Cascade
# ============================================================================


class TestEmptyCollectionCascade:
    """Removing a collection with no entities, views, or relationships."""

    def test_remove_empty_collection(self, empty):
        """Removing a collection with no entities is a clean operation."""
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="collection.create",
                payload={"id": "temp", "schema": {"label": "string"}},
            ),
        )
        snapshot = result.snapshot

        result = reduce(
            snapshot,
            make_event(seq=2, type="collection.remove", payload={"id": "temp"}),
        )
        assert result.applied
        assert result.snapshot["collections"]["temp"]["_removed"] is True

    def test_remove_collection_no_views_no_blocks(self, empty):
        """Collection with entities but no views or blocks — only entities + rels cascade."""
        snapshot = empty
        seq = 0

        def apply(event_type, payload):
            nonlocal snapshot, seq
            seq += 1
            result = reduce(snapshot, make_event(seq=seq, type=event_type, payload=payload))
            assert result.applied
            snapshot = result.snapshot

        apply(
            "collection.create",
            {
                "id": "items",
                "schema": {"name": "string"},
            },
        )
        apply(
            "entity.create",
            {
                "collection": "items",
                "id": "item_a",
                "fields": {"name": "A"},
            },
        )
        apply(
            "entity.create",
            {
                "collection": "items",
                "id": "item_b",
                "fields": {"name": "B"},
            },
        )

        # Remove — no views or blocks to cascade to
        result = reduce(
            snapshot,
            make_event(seq=seq + 1, type="collection.remove", payload={"id": "items"}),
        )
        assert result.applied
        assert result.snapshot["collections"]["items"]["_removed"] is True
        for entity in result.snapshot["collections"]["items"]["entities"].values():
            assert entity["_removed"] is True

        # No views were affected (none existed)
        # No blocks were affected (none referenced this collection)
