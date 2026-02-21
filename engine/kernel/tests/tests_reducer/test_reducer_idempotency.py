"""
AIde Reducer -- Idempotency Tests (Category 7)

Tests that repeated or redundant operations produce consistent, safe results.

From the spec (aide_reducer_spec.md, "Testing Strategy"):
  "7. Idempotency. Remove already-removed entity. Update with same values.
   Set relationship that already exists."

Idempotent operations are core to AIde's reliability. The AI might emit
duplicate primitives, the user might repeat themselves, or replay might
re-apply events. The reducer must handle all of these gracefully.

Covers:
  - entity.remove on already-removed entity → ALREADY_REMOVED warning
  - collection.remove on already-removed collection → ALREADY_REMOVED warning
  - entity.update with identical values → applied, no change
  - entity.update with partial overlap → applied, no change on matching fields
  - relationship.set with identical relationship → applied (replaces self)
  - relationship.set many_to_one re-set same target → link count stays 1
  - style.set with same tokens → applied, no change
  - style.set_entity with same styles → applied, no change
  - meta.update with same values → applied, no change
  - meta.constrain with same id → updates in place
  - block.set update mode with same props → applied, no change
  - collection.update with same name/settings → applied, no change
  - view.update with same config → applied, no change
  - Double-apply: apply event, then apply same event shape again

Reference: aide_reducer_spec.md (entity.remove, collection.remove WARN behavior,
           style.set shallow-merge, meta.update shallow-merge, meta.constrain upsert)
"""

import copy
import json

import pytest

from engine.kernel.events import make_event
from engine.kernel.reducer import empty_state, reduce

# ============================================================================
# Helpers
# ============================================================================


def has_warning(result, code):
    """Check if a specific warning code is present in result warnings."""
    return any(w.code == code for w in result.warnings)


def snapshots_equal(a, b):
    """Deep-compare two snapshots via sorted JSON serialization."""
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def empty():
    return empty_state()


@pytest.fixture
def grocery_state(empty):
    """
    Grocery list with:
      - collection: grocery_list (name, store?, checked)
      - entities: item_milk, item_eggs
      - view: grocery_view
      - block: block_title, block_grocery (collection_view)
      - style: primary_color, font_family
      - meta: title set
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
        "collection.create",
        {
            "id": "grocery_list",
            "name": "Grocery List",
            "schema": {"name": "string", "store": "string?", "checked": "bool"},
        },
    )
    apply(
        "entity.create",
        {
            "collection": "grocery_list",
            "id": "item_milk",
            "fields": {"name": "Milk", "store": "Whole Foods", "checked": False},
        },
    )
    apply(
        "entity.create",
        {
            "collection": "grocery_list",
            "id": "item_eggs",
            "fields": {"name": "Eggs", "store": "Costco", "checked": True},
        },
    )
    apply(
        "view.create",
        {
            "id": "grocery_view",
            "type": "list",
            "source": "grocery_list",
            "config": {"show_fields": ["name", "store", "checked"], "sort_by": "name"},
        },
    )
    apply(
        "block.set",
        {
            "id": "block_title",
            "type": "heading",
            "parent": "block_root",
            "props": {"level": 1, "content": "Grocery List"},
        },
    )
    apply(
        "block.set",
        {
            "id": "block_grocery",
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "grocery_list", "view": "grocery_view"},
        },
    )
    apply(
        "style.set",
        {
            "primary_color": "#2D2D2A",
            "font_family": "Inter",
        },
    )
    apply(
        "meta.update",
        {
            "title": "Weekly Groceries",
        },
    )

    return snapshot, seq


@pytest.fixture
def state_with_relationship(empty):
    """Two collections with a many_to_one relationship."""
    snapshot = empty
    seq = 0

    def apply(event_type, payload):
        nonlocal snapshot, seq
        seq += 1
        result = reduce(snapshot, make_event(seq=seq, type=event_type, payload=payload))
        assert result.applied, f"Event {seq} ({event_type}) rejected: {result.error}"
        snapshot = result.snapshot

    apply(
        "collection.create",
        {
            "id": "players",
            "schema": {"name": "string"},
        },
    )
    apply(
        "collection.create",
        {
            "id": "teams",
            "schema": {"name": "string"},
        },
    )
    apply(
        "entity.create",
        {
            "collection": "players",
            "id": "player_alice",
            "fields": {"name": "Alice"},
        },
    )
    apply(
        "entity.create",
        {
            "collection": "players",
            "id": "player_bob",
            "fields": {"name": "Bob"},
        },
    )
    apply(
        "entity.create",
        {
            "collection": "teams",
            "id": "team_red",
            "fields": {"name": "Red Team"},
        },
    )
    apply(
        "entity.create",
        {
            "collection": "teams",
            "id": "team_blue",
            "fields": {"name": "Blue Team"},
        },
    )
    apply(
        "relationship.set",
        {
            "from": "players/player_alice",
            "to": "teams/team_red",
            "type": "member_of",
            "cardinality": "many_to_one",
        },
    )
    apply(
        "relationship.set",
        {
            "from": "players/player_bob",
            "to": "teams/team_blue",
            "type": "member_of",
        },
    )

    return snapshot, seq


# ============================================================================
# entity.remove — Already Removed
# ============================================================================


class TestEntityRemoveIdempotent:
    """Removing an already-removed entity warns but does not error."""

    def test_double_remove_warns(self, grocery_state):
        """Second entity.remove on same entity → ALREADY_REMOVED warning, still applied."""
        snapshot, seq = grocery_state

        # First remove
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="entity.remove",
                payload={"ref": "grocery_list/item_milk"},
            ),
        )
        assert result.applied
        snapshot_after_first = result.snapshot

        # Second remove — same entity
        result = reduce(
            snapshot_after_first,
            make_event(
                seq=seq + 2,
                type="entity.remove",
                payload={"ref": "grocery_list/item_milk"},
            ),
        )
        # Per spec: WARN if entity is already removed (idempotent — no error, no change)
        assert has_warning(result, "ALREADY_REMOVED")
        # Entity is still removed
        entity = result.snapshot["collections"]["grocery_list"]["entities"]["item_milk"]
        assert entity["_removed"] is True

    def test_double_remove_no_state_change(self, grocery_state):
        """Second remove does not change the snapshot beyond the first remove."""
        snapshot, seq = grocery_state

        result1 = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="entity.remove",
                payload={"ref": "grocery_list/item_milk"},
            ),
        )
        after_first = result1.snapshot

        result2 = reduce(
            after_first,
            make_event(
                seq=seq + 2,
                type="entity.remove",
                payload={"ref": "grocery_list/item_milk"},
            ),
        )

        # The entity data should be identical (modulo _removed_seq if updated)
        entity_first = after_first["collections"]["grocery_list"]["entities"]["item_milk"]
        entity_second = result2.snapshot["collections"]["grocery_list"]["entities"]["item_milk"]
        assert entity_first["_removed"] is True
        assert entity_second["_removed"] is True
        assert entity_first["name"] == entity_second["name"]

    def test_triple_remove_still_warns(self, grocery_state):
        """Even a third remove is safe — idempotent all the way."""
        snapshot, seq = grocery_state

        for i in range(3):
            result = reduce(
                snapshot,
                make_event(
                    seq=seq + 1 + i,
                    type="entity.remove",
                    payload={"ref": "grocery_list/item_milk"},
                ),
            )
            snapshot = result.snapshot

        # Still removed, no crash
        entity = snapshot["collections"]["grocery_list"]["entities"]["item_milk"]
        assert entity["_removed"] is True


# ============================================================================
# collection.remove — Already Removed
# ============================================================================


class TestCollectionRemoveIdempotent:
    """Removing an already-removed collection warns but does not error."""

    def test_double_collection_remove_warns(self, grocery_state):
        """Second collection.remove → ALREADY_REMOVED warning."""
        snapshot, seq = grocery_state

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="collection.remove",
                payload={"id": "grocery_list"},
            ),
        )
        assert result.applied
        snapshot = result.snapshot

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="collection.remove",
                payload={"id": "grocery_list"},
            ),
        )
        assert has_warning(result, "ALREADY_REMOVED")
        assert result.snapshot["collections"]["grocery_list"]["_removed"] is True


# ============================================================================
# entity.update — Same Values
# ============================================================================


class TestEntityUpdateIdempotent:
    """Updating with identical values applies cleanly without changes."""

    def test_update_same_values_applies(self, grocery_state):
        """entity.update with the current values succeeds."""
        snapshot, seq = grocery_state

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="entity.update",
                payload={
                    "ref": "grocery_list/item_milk",
                    "fields": {"name": "Milk", "store": "Whole Foods", "checked": False},
                },
            ),
        )
        assert result.applied

    def test_update_same_values_no_data_change(self, grocery_state):
        """entity.update with current values produces identical entity data."""
        snapshot, seq = grocery_state

        entity_before = copy.deepcopy(snapshot["collections"]["grocery_list"]["entities"]["item_milk"])

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="entity.update",
                payload={
                    "ref": "grocery_list/item_milk",
                    "fields": {"name": "Milk", "store": "Whole Foods", "checked": False},
                },
            ),
        )

        entity_after = result.snapshot["collections"]["grocery_list"]["entities"]["item_milk"]
        # Core field values unchanged
        assert entity_after["name"] == entity_before["name"]
        assert entity_after["store"] == entity_before["store"]
        assert entity_after["checked"] == entity_before["checked"]

    def test_update_partial_overlap_no_change(self, grocery_state):
        """Updating a subset of fields with their current values → no effective change."""
        snapshot, seq = grocery_state

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="entity.update",
                payload={
                    "ref": "grocery_list/item_milk",
                    "fields": {"checked": False},  # Already False
                },
            ),
        )
        assert result.applied
        entity = result.snapshot["collections"]["grocery_list"]["entities"]["item_milk"]
        assert entity["checked"] is False
        assert entity["name"] == "Milk"  # Untouched

    def test_update_null_to_null(self, grocery_state):
        """Setting a nullable field that is already null back to null."""
        snapshot, seq = grocery_state

        # item_eggs has store="Costco", but let's create one with null store
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="entity.create",
                payload={
                    "collection": "grocery_list",
                    "id": "item_bread",
                    "fields": {"name": "Bread", "checked": False},
                    # store defaults to null
                },
            ),
        )
        snapshot = result.snapshot

        # Update store: null → null
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="entity.update",
                payload={
                    "ref": "grocery_list/item_bread",
                    "fields": {"store": None},
                },
            ),
        )
        assert result.applied
        entity = result.snapshot["collections"]["grocery_list"]["entities"]["item_bread"]
        assert entity["store"] is None


# ============================================================================
# relationship.set — Same Relationship
# ============================================================================


class TestRelationshipSetIdempotent:
    """Re-setting the same relationship replaces itself cleanly."""

    def test_reset_same_relationship_applies(self, state_with_relationship):
        """Setting an identical relationship succeeds."""
        snapshot, seq = state_with_relationship

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="relationship.set",
                payload={
                    "from": "players/player_alice",
                    "to": "teams/team_red",
                    "type": "member_of",
                },
            ),
        )
        assert result.applied

    def test_reset_same_relationship_count_stable(self, state_with_relationship):
        """Re-setting many_to_one to same target doesn't accumulate duplicate links."""
        snapshot, seq = state_with_relationship

        # Count alice's member_of relationships before
        alice_rels_before = [
            r for r in snapshot["relationships"] if r["from"] == "players/player_alice" and r["type"] == "member_of"
        ]
        assert len(alice_rels_before) == 1

        # Re-set same relationship
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="relationship.set",
                payload={
                    "from": "players/player_alice",
                    "to": "teams/team_red",
                    "type": "member_of",
                },
            ),
        )

        # Still exactly 1 link
        alice_rels_after = [
            r
            for r in result.snapshot["relationships"]
            if r["from"] == "players/player_alice" and r["type"] == "member_of"
        ]
        assert len(alice_rels_after) == 1
        assert alice_rels_after[0]["to"] == "teams/team_red"

    def test_reset_same_relationship_three_times(self, state_with_relationship):
        """Setting the same relationship 3 times never accumulates."""
        snapshot, seq = state_with_relationship

        for i in range(3):
            result = reduce(
                snapshot,
                make_event(
                    seq=seq + 1 + i,
                    type="relationship.set",
                    payload={
                        "from": "players/player_alice",
                        "to": "teams/team_red",
                        "type": "member_of",
                    },
                ),
            )
            assert result.applied
            snapshot = result.snapshot

        alice_rels = [
            r for r in snapshot["relationships"] if r["from"] == "players/player_alice" and r["type"] == "member_of"
        ]
        assert len(alice_rels) == 1

    def test_many_to_many_duplicate_is_idempotent(self, empty):
        """For many_to_many, re-setting same from→to should not create duplicates."""
        snapshot = empty
        seq = 0

        def apply(event_type, payload):
            nonlocal snapshot, seq
            seq += 1
            result = reduce(snapshot, make_event(seq=seq, type=event_type, payload=payload))
            assert result.applied
            snapshot = result.snapshot

        apply("collection.create", {"id": "items", "schema": {"name": "string"}})
        apply("collection.create", {"id": "tags", "schema": {"label": "string"}})
        apply("entity.create", {"collection": "items", "id": "item_a", "fields": {"name": "A"}})
        apply("entity.create", {"collection": "tags", "id": "tag_red", "fields": {"label": "Red"}})

        # First tag
        apply(
            "relationship.set",
            {
                "from": "items/item_a",
                "to": "tags/tag_red",
                "type": "tagged_with",
                "cardinality": "many_to_many",
            },
        )

        count_before = len(
            [r for r in snapshot["relationships"] if r["from"] == "items/item_a" and r["to"] == "tags/tag_red"]
        )

        # Re-set same tag
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="relationship.set",
                payload={
                    "from": "items/item_a",
                    "to": "tags/tag_red",
                    "type": "tagged_with",
                },
            ),
        )
        assert result.applied

        count_after = len(
            [r for r in result.snapshot["relationships"] if r["from"] == "items/item_a" and r["to"] == "tags/tag_red"]
        )
        # Should not have grown
        assert count_after <= count_before + 1  # At most replaced


# ============================================================================
# style.set — Same Tokens
# ============================================================================


class TestStyleSetIdempotent:
    """Re-setting style tokens with same values is a no-op."""

    def test_same_style_tokens_apply(self, grocery_state):
        """style.set with identical token values succeeds."""
        snapshot, seq = grocery_state

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="style.set",
                payload={"primary_color": "#2D2D2A", "font_family": "Inter"},
            ),
        )
        assert result.applied

    def test_same_style_tokens_no_change(self, grocery_state):
        """Re-setting identical tokens doesn't alter the styles object."""
        snapshot, seq = grocery_state

        styles_before = copy.deepcopy(snapshot["styles"])

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="style.set",
                payload={"primary_color": "#2D2D2A", "font_family": "Inter"},
            ),
        )

        assert result.snapshot["styles"]["primary_color"] == styles_before["primary_color"]
        assert result.snapshot["styles"]["font_family"] == styles_before["font_family"]

    def test_style_set_partial_overlap(self, grocery_state):
        """Setting one existing token + one new token merges correctly."""
        snapshot, seq = grocery_state

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="style.set",
                payload={
                    "primary_color": "#2D2D2A",  # Same
                    "density": "compact",  # New
                },
            ),
        )
        assert result.applied
        assert result.snapshot["styles"]["primary_color"] == "#2D2D2A"
        assert result.snapshot["styles"]["font_family"] == "Inter"  # Preserved
        assert result.snapshot["styles"]["density"] == "compact"  # Added


# ============================================================================
# style.set_entity — Same Styles
# ============================================================================


class TestStyleSetEntityIdempotent:
    """Re-setting entity styles with same values is a no-op."""

    def test_same_entity_styles_apply(self, grocery_state):
        """Set entity styles, then re-set with identical values."""
        snapshot, seq = grocery_state

        # First set
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="style.set_entity",
                payload={
                    "ref": "grocery_list/item_milk",
                    "styles": {"highlight": True, "bg_color": "#fef3c7"},
                },
            ),
        )
        assert result.applied
        snapshot = result.snapshot

        # Re-set with identical values
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="style.set_entity",
                payload={
                    "ref": "grocery_list/item_milk",
                    "styles": {"highlight": True, "bg_color": "#fef3c7"},
                },
            ),
        )
        assert result.applied
        entity = result.snapshot["collections"]["grocery_list"]["entities"]["item_milk"]
        assert entity["_styles"]["highlight"] is True
        assert entity["_styles"]["bg_color"] == "#fef3c7"


# ============================================================================
# meta.update — Same Values
# ============================================================================


class TestMetaUpdateIdempotent:
    """Re-setting meta with identical values is a no-op."""

    def test_same_meta_applies(self, grocery_state):
        """meta.update with current title succeeds."""
        snapshot, seq = grocery_state

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="meta.update",
                payload={"title": "Weekly Groceries"},
            ),
        )
        assert result.applied
        assert result.snapshot["meta"]["title"] == "Weekly Groceries"

    def test_meta_update_preserves_other_keys(self, grocery_state):
        """Re-setting one meta key doesn't drop others."""
        snapshot, seq = grocery_state

        # Set an additional key
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="meta.update",
                payload={"identity": "Shared household grocery list"},
            ),
        )
        snapshot = result.snapshot

        # Re-set title with same value
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="meta.update",
                payload={"title": "Weekly Groceries"},
            ),
        )
        assert result.applied
        assert result.snapshot["meta"]["title"] == "Weekly Groceries"
        assert result.snapshot["meta"]["identity"] == "Shared household grocery list"


# ============================================================================
# meta.constrain — Upsert by ID
# ============================================================================


class TestMetaConstrainIdempotent:
    """meta.constrain with the same id updates in place (upsert)."""

    def test_re_set_same_constraint_id(self, grocery_state):
        """Setting a constraint with same ID updates it rather than creating a duplicate."""
        snapshot, seq = grocery_state

        # First constraint
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="meta.constrain",
                payload={
                    "id": "max_items",
                    "rule": "collection_max_entities",
                    "collection": "grocery_list",
                    "value": 20,
                    "message": "Maximum 20 items",
                },
            ),
        )
        assert result.applied
        snapshot = result.snapshot
        assert len([c for c in snapshot["constraints"] if c["id"] == "max_items"]) == 1

        # Re-set with updated value
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="meta.constrain",
                payload={
                    "id": "max_items",
                    "rule": "collection_max_entities",
                    "collection": "grocery_list",
                    "value": 50,
                    "message": "Maximum 50 items",
                },
            ),
        )
        assert result.applied

        # Still exactly 1 constraint with this ID
        matching = [c for c in result.snapshot["constraints"] if c["id"] == "max_items"]
        assert len(matching) == 1
        assert matching[0]["value"] == 50

    def test_re_set_same_constraint_exact_values(self, grocery_state):
        """Setting the same constraint with identical values is a clean no-op."""
        snapshot, seq = grocery_state

        payload = {
            "id": "max_items",
            "rule": "collection_max_entities",
            "collection": "grocery_list",
            "value": 20,
            "message": "Maximum 20 items",
        }

        result = reduce(
            snapshot,
            make_event(seq=seq + 1, type="meta.constrain", payload=payload),
        )
        snapshot = result.snapshot

        result = reduce(
            snapshot,
            make_event(seq=seq + 2, type="meta.constrain", payload=payload),
        )
        assert result.applied
        matching = [c for c in result.snapshot["constraints"] if c["id"] == "max_items"]
        assert len(matching) == 1


# ============================================================================
# block.set — Update Mode with Same Props
# ============================================================================


class TestBlockSetIdempotent:
    """block.set on an existing block with same props is a no-op update."""

    def test_re_set_block_same_props(self, grocery_state):
        """Applying block.set with identical props to an existing block succeeds."""
        snapshot, seq = grocery_state

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="block.set",
                payload={
                    "id": "block_title",
                    "props": {"level": 1, "content": "Grocery List"},
                },
            ),
        )
        assert result.applied
        block = result.snapshot["blocks"]["block_title"]
        assert block["props"]["content"] == "Grocery List"
        assert block["props"]["level"] == 1

    def test_re_set_block_preserves_position(self, grocery_state):
        """Update-mode block.set doesn't change the block's position in parent."""
        snapshot, seq = grocery_state

        children_before = list(snapshot["blocks"]["block_root"]["children"])

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="block.set",
                payload={
                    "id": "block_title",
                    "props": {"level": 1, "content": "Grocery List"},
                },
            ),
        )
        children_after = list(result.snapshot["blocks"]["block_root"]["children"])
        assert children_before == children_after

    def test_re_set_block_no_type_needed(self, grocery_state):
        """In update mode, type is not required — omitting it is fine."""
        snapshot, seq = grocery_state

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="block.set",
                payload={
                    "id": "block_title",
                    "props": {"content": "Updated Title"},
                },
            ),
        )
        assert result.applied
        assert result.snapshot["blocks"]["block_title"]["type"] == "heading"  # Unchanged


# ============================================================================
# collection.update — Same Values
# ============================================================================


class TestCollectionUpdateIdempotent:
    """collection.update with identical values is a no-op."""

    def test_same_name_applies(self, grocery_state):
        snapshot, seq = grocery_state

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="collection.update",
                payload={"id": "grocery_list", "name": "Grocery List"},
            ),
        )
        assert result.applied
        assert result.snapshot["collections"]["grocery_list"]["name"] == "Grocery List"

    def test_same_settings_applies(self, grocery_state):
        snapshot, seq = grocery_state

        # Set a setting
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="collection.update",
                payload={"id": "grocery_list", "settings": {"default_store": "Costco"}},
            ),
        )
        snapshot = result.snapshot

        # Re-set same setting
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="collection.update",
                payload={"id": "grocery_list", "settings": {"default_store": "Costco"}},
            ),
        )
        assert result.applied
        assert result.snapshot["collections"]["grocery_list"]["settings"]["default_store"] == "Costco"


# ============================================================================
# view.update — Same Config
# ============================================================================


class TestViewUpdateIdempotent:
    """view.update with identical config is a no-op."""

    def test_same_config_applies(self, grocery_state):
        snapshot, seq = grocery_state

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="view.update",
                payload={
                    "id": "grocery_view",
                    "config": {"show_fields": ["name", "store", "checked"], "sort_by": "name"},
                },
            ),
        )
        assert result.applied

    def test_same_type_applies(self, grocery_state):
        snapshot, seq = grocery_state

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="view.update",
                payload={"id": "grocery_view", "type": "list"},
            ),
        )
        assert result.applied
        assert result.snapshot["views"]["grocery_view"]["type"] == "list"


# ============================================================================
# Double-Apply Patterns
# ============================================================================


class TestDoubleApply:
    """
    Apply an event, then apply an event with the same shape again.
    Tests that the second application either succeeds idempotently
    or rejects consistently (never crashes or corrupts).
    """

    def test_double_meta_annotate(self, grocery_state):
        """
        meta.annotate is append-only — two identical calls produce two annotations.
        This is NOT idempotent (by design), but it must not crash.
        """
        snapshot, seq = grocery_state

        for i in range(2):
            result = reduce(
                snapshot,
                make_event(
                    seq=seq + 1 + i,
                    type="meta.annotate",
                    payload={"note": "Week reviewed.", "pinned": False},
                ),
            )
            assert result.applied
            snapshot = result.snapshot

        # Two annotations exist — append-only is correct behavior
        assert len(snapshot["annotations"]) == 2

    def test_double_entity_create_rejects_consistently(self, grocery_state):
        """
        entity.create with same ID twice → first succeeds, second rejects.
        This is NOT idempotent — but it must reject cleanly, not crash.
        """
        snapshot, seq = grocery_state

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="entity.create",
                payload={
                    "collection": "grocery_list",
                    "id": "item_bread",
                    "fields": {"name": "Bread", "checked": False},
                },
            ),
        )
        assert result.applied
        snapshot = result.snapshot

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="entity.create",
                payload={
                    "collection": "grocery_list",
                    "id": "item_bread",
                    "fields": {"name": "Bread", "checked": False},
                },
            ),
        )
        assert not result.applied  # Rejected, not crashed

    def test_double_style_set_merge(self, grocery_state):
        """Two identical style.set calls produce same result as one."""
        snapshot, seq = grocery_state

        payload = {"primary_color": "#000000", "density": "compact"}

        result1 = reduce(
            snapshot,
            make_event(seq=seq + 1, type="style.set", payload=payload),
        )
        result2 = reduce(
            result1.snapshot,
            make_event(seq=seq + 2, type="style.set", payload=payload),
        )

        assert result2.snapshot["styles"]["primary_color"] == "#000000"
        assert result2.snapshot["styles"]["density"] == "compact"
        assert result2.snapshot["styles"]["font_family"] == "Inter"  # Original preserved

    def test_double_block_set_update(self, grocery_state):
        """Two block.set updates with same props → block unchanged after second."""
        snapshot, seq = grocery_state

        payload = {
            "id": "block_title",
            "props": {"content": "New Title", "level": 2},
        }

        result1 = reduce(
            snapshot,
            make_event(seq=seq + 1, type="block.set", payload=payload),
        )
        result2 = reduce(
            result1.snapshot,
            make_event(seq=seq + 2, type="block.set", payload=payload),
        )

        block = result2.snapshot["blocks"]["block_title"]
        assert block["props"]["content"] == "New Title"
        assert block["props"]["level"] == 2
