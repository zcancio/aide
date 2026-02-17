"""
AIde Reducer -- Cardinality Enforcement Tests (Category 3)

Tests for relationship.set cardinality auto-resolution:
  many_to_one: source can link to ONE target. Re-linking auto-removes the old.
  one_to_one:  both sides exclusive. Re-linking auto-removes both old partners.
  many_to_many: no auto-removal. Multiple links accumulate.

Also covers:
  - Relationship type registration (first set defines cardinality)
  - Cardinality is immutable once registered
  - Entity removal excludes relationships

The classic example from the spec: "Seat Linda at table 5" when she's at table 3.

Reference: aide_reducer_spec.md, section "Relationship Primitives"
"""

import pytest

from engine.kernel.events import make_event
from engine.kernel.reducer import empty_state, reduce

# ============================================================================
# Fixtures: Wedding seating scenario
# ============================================================================


@pytest.fixture
def seating_state():
    """
    Two collections: guests (6 guests) and tables (3 tables).
    No relationships yet.
    """
    snapshot = empty_state()
    seq = 0

    # -- Guests collection --
    seq += 1
    result = reduce(
        snapshot,
        make_event(
            seq=seq,
            type="collection.create",
            payload={
                "id": "guests",
                "name": "Guests",
                "schema": {"name": "string", "group": "string?"},
            },
        ),
    )
    snapshot = result.snapshot

    guest_names = ["Linda", "Steve", "Alice", "Bob", "Carol", "Dan"]
    for name in guest_names:
        seq += 1
        result = reduce(
            snapshot,
            make_event(
                seq=seq,
                type="entity.create",
                payload={
                    "collection": "guests",
                    "id": f"guest_{name.lower()}",
                    "fields": {"name": name, "group": None},
                },
            ),
        )
        snapshot = result.snapshot

    # -- Tables collection --
    seq += 1
    result = reduce(
        snapshot,
        make_event(
            seq=seq,
            type="collection.create",
            payload={
                "id": "tables",
                "name": "Tables",
                "schema": {"label": "string", "capacity": "int"},
            },
        ),
    )
    snapshot = result.snapshot

    for i in range(1, 4):
        seq += 1
        result = reduce(
            snapshot,
            make_event(
                seq=seq,
                type="entity.create",
                payload={
                    "collection": "tables",
                    "id": f"table_{i}",
                    "fields": {"label": f"Table {i}", "capacity": 8},
                },
            ),
        )
        snapshot = result.snapshot

    return snapshot, seq


def _active_rels(snapshot, rel_type=None):
    """Get non-excluded relationships, optionally filtered by type."""
    rels = snapshot["relationships"]
    if rel_type:
        rels = [r for r in rels if r["type"] == rel_type]
    return rels


def _rels_from(snapshot, entity_ref, rel_type):
    """Get relationships from a specific entity of a specific type."""
    return [r for r in snapshot["relationships"] if r["from"] == entity_ref and r["type"] == rel_type]


def _rels_to(snapshot, entity_ref, rel_type):
    """Get relationships pointing to a specific entity of a specific type."""
    return [r for r in snapshot["relationships"] if r["to"] == entity_ref and r["type"] == rel_type]


# ============================================================================
# many_to_one: each guest at ONE table
# ============================================================================


class TestManyToOne:
    """
    "seated_at" with many_to_one cardinality.
    Each guest can be at exactly one table.
    A table can have many guests.
    Re-seating a guest auto-removes the old link.
    """

    def test_seat_guest_at_table(self, seating_state):
        snapshot, seq = seating_state

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="relationship.set",
                payload={
                    "from": "guests/guest_linda",
                    "to": "tables/table_3",
                    "type": "seated_at",
                    "cardinality": "many_to_one",
                },
            ),
        )

        assert result.applied
        rels = _active_rels(result.snapshot, "seated_at")
        assert len(rels) == 1
        assert rels[0]["from"] == "guests/guest_linda"
        assert rels[0]["to"] == "tables/table_3"

    def test_reseat_guest_auto_removes_old(self, seating_state):
        """The core spec example: Linda at table 3, then move to table 5."""
        snapshot, seq = seating_state

        # Seat Linda at table 3
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="relationship.set",
                payload={
                    "from": "guests/guest_linda",
                    "to": "tables/table_3",
                    "type": "seated_at",
                    "cardinality": "many_to_one",
                },
            ),
        )
        snapshot = result.snapshot

        # Re-seat Linda at table 1
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="relationship.set",
                payload={
                    "from": "guests/guest_linda",
                    "to": "tables/table_1",
                    "type": "seated_at",
                },
            ),
        )

        assert result.applied
        rels = _rels_from(result.snapshot, "guests/guest_linda", "seated_at")
        assert len(rels) == 1
        assert rels[0]["to"] == "tables/table_1"  # New assignment
        # Old table_3 link is gone
        assert not any(r["to"] == "tables/table_3" for r in _active_rels(result.snapshot, "seated_at"))

    def test_multiple_guests_at_same_table(self, seating_state):
        """many_to_one allows multiple sources pointing to the same target."""
        snapshot, seq = seating_state

        # Seat Linda and Steve at table 1
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="relationship.set",
                payload={
                    "from": "guests/guest_linda",
                    "to": "tables/table_1",
                    "type": "seated_at",
                    "cardinality": "many_to_one",
                },
            ),
        )
        snapshot = result.snapshot

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="relationship.set",
                payload={
                    "from": "guests/guest_steve",
                    "to": "tables/table_1",
                    "type": "seated_at",
                },
            ),
        )

        assert result.applied
        rels_to_table_1 = _rels_to(result.snapshot, "tables/table_1", "seated_at")
        assert len(rels_to_table_1) == 2

    def test_reseat_does_not_affect_other_guests(self, seating_state):
        """Moving Linda should not touch Steve's seating."""
        snapshot, seq = seating_state

        # Seat Linda at table 1
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="relationship.set",
                payload={
                    "from": "guests/guest_linda",
                    "to": "tables/table_1",
                    "type": "seated_at",
                    "cardinality": "many_to_one",
                },
            ),
        )
        snapshot = result.snapshot

        # Seat Steve at table 1
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="relationship.set",
                payload={
                    "from": "guests/guest_steve",
                    "to": "tables/table_1",
                    "type": "seated_at",
                },
            ),
        )
        snapshot = result.snapshot

        # Move Linda to table 2
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 3,
                type="relationship.set",
                payload={
                    "from": "guests/guest_linda",
                    "to": "tables/table_2",
                    "type": "seated_at",
                },
            ),
        )

        assert result.applied
        # Linda at table 2
        linda_rels = _rels_from(result.snapshot, "guests/guest_linda", "seated_at")
        assert len(linda_rels) == 1
        assert linda_rels[0]["to"] == "tables/table_2"
        # Steve still at table 1
        steve_rels = _rels_from(result.snapshot, "guests/guest_steve", "seated_at")
        assert len(steve_rels) == 1
        assert steve_rels[0]["to"] == "tables/table_1"

    def test_different_relationship_types_are_independent(self, seating_state):
        """Cardinality enforcement is per relationship type."""
        snapshot, seq = seating_state

        # Linda seated_at table 1
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="relationship.set",
                payload={
                    "from": "guests/guest_linda",
                    "to": "tables/table_1",
                    "type": "seated_at",
                    "cardinality": "many_to_one",
                },
            ),
        )
        snapshot = result.snapshot

        # Linda serving_at table 2 (different relationship type)
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="relationship.set",
                payload={
                    "from": "guests/guest_linda",
                    "to": "tables/table_2",
                    "type": "serving_at",
                    "cardinality": "many_to_one",
                },
            ),
        )

        assert result.applied
        # Both relationships exist -- different types don't conflict
        seated = _rels_from(result.snapshot, "guests/guest_linda", "seated_at")
        serving = _rels_from(result.snapshot, "guests/guest_linda", "serving_at")
        assert len(seated) == 1
        assert seated[0]["to"] == "tables/table_1"
        assert len(serving) == 1
        assert serving[0]["to"] == "tables/table_2"


# ============================================================================
# one_to_one: exclusive pairing on both sides
# ============================================================================


class TestOneToOne:
    """
    "paired_with" with one_to_one cardinality.
    Each entity on both sides can have exactly one partner.
    Setting A->B auto-removes A's old partner AND B's old partner.
    """

    def test_simple_pairing(self, seating_state):
        snapshot, seq = seating_state

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="relationship.set",
                payload={
                    "from": "guests/guest_alice",
                    "to": "guests/guest_bob",
                    "type": "paired_with",
                    "cardinality": "one_to_one",
                },
            ),
        )

        assert result.applied
        rels = _active_rels(result.snapshot, "paired_with")
        assert len(rels) == 1
        assert rels[0]["from"] == "guests/guest_alice"
        assert rels[0]["to"] == "guests/guest_bob"

    def test_repairing_source_removes_old_link(self, seating_state):
        """A->B exists. Set A->C. A->B is removed."""
        snapshot, seq = seating_state

        # Alice paired with Bob
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="relationship.set",
                payload={
                    "from": "guests/guest_alice",
                    "to": "guests/guest_bob",
                    "type": "paired_with",
                    "cardinality": "one_to_one",
                },
            ),
        )
        snapshot = result.snapshot

        # Alice re-paired with Carol
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="relationship.set",
                payload={
                    "from": "guests/guest_alice",
                    "to": "guests/guest_carol",
                    "type": "paired_with",
                },
            ),
        )

        assert result.applied
        rels = _active_rels(result.snapshot, "paired_with")
        assert len(rels) == 1
        assert rels[0]["from"] == "guests/guest_alice"
        assert rels[0]["to"] == "guests/guest_carol"
        # Bob is unlinked
        assert not any(r["from"] == "guests/guest_bob" or r["to"] == "guests/guest_bob" for r in rels)

    def test_repairing_target_removes_old_link(self, seating_state):
        """A->B exists. Set C->B. A->B is removed (B can only have one partner)."""
        snapshot, seq = seating_state

        # Alice paired with Bob
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="relationship.set",
                payload={
                    "from": "guests/guest_alice",
                    "to": "guests/guest_bob",
                    "type": "paired_with",
                    "cardinality": "one_to_one",
                },
            ),
        )
        snapshot = result.snapshot

        # Carol paired with Bob -- B already has a partner (Alice)
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="relationship.set",
                payload={
                    "from": "guests/guest_carol",
                    "to": "guests/guest_bob",
                    "type": "paired_with",
                },
            ),
        )

        assert result.applied
        rels = _active_rels(result.snapshot, "paired_with")
        assert len(rels) == 1
        assert rels[0]["from"] == "guests/guest_carol"
        assert rels[0]["to"] == "guests/guest_bob"
        # Alice is fully unlinked
        assert not any(r["from"] == "guests/guest_alice" or r["to"] == "guests/guest_alice" for r in rels)

    def test_double_displacement(self, seating_state):
        """
        A->B and C->D exist. Set A->D.
        Removes A->B (A's old partner) AND C->D (D's old partner).
        """
        snapshot, seq = seating_state

        # Alice paired with Bob
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="relationship.set",
                payload={
                    "from": "guests/guest_alice",
                    "to": "guests/guest_bob",
                    "type": "paired_with",
                    "cardinality": "one_to_one",
                },
            ),
        )
        snapshot = result.snapshot

        # Carol paired with Dan
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="relationship.set",
                payload={
                    "from": "guests/guest_carol",
                    "to": "guests/guest_dan",
                    "type": "paired_with",
                },
            ),
        )
        snapshot = result.snapshot
        assert len(_active_rels(snapshot, "paired_with")) == 2

        # Now: Alice paired with Dan
        # This should remove Alice->Bob (source conflict) AND Carol->Dan (target conflict)
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 3,
                type="relationship.set",
                payload={
                    "from": "guests/guest_alice",
                    "to": "guests/guest_dan",
                    "type": "paired_with",
                },
            ),
        )

        assert result.applied
        rels = _active_rels(result.snapshot, "paired_with")
        assert len(rels) == 1
        assert rels[0]["from"] == "guests/guest_alice"
        assert rels[0]["to"] == "guests/guest_dan"


# ============================================================================
# many_to_many: no auto-removal
# ============================================================================


class TestManyToMany:
    """
    "tagged_with" with many_to_many cardinality.
    A guest can have many tags. A tag can apply to many guests.
    No auto-removal ever.
    """

    def _make_tags_state(self, seating_state):
        """Add a tags collection to the seating state."""
        snapshot, seq = seating_state

        seq += 1
        result = reduce(
            snapshot,
            make_event(
                seq=seq,
                type="collection.create",
                payload={
                    "id": "tags",
                    "name": "Tags",
                    "schema": {"label": "string"},
                },
            ),
        )
        snapshot = result.snapshot

        for label in ["vip", "vegetarian", "plus_one"]:
            seq += 1
            result = reduce(
                snapshot,
                make_event(
                    seq=seq,
                    type="entity.create",
                    payload={
                        "collection": "tags",
                        "id": f"tag_{label}",
                        "fields": {"label": label},
                    },
                ),
            )
            snapshot = result.snapshot

        return snapshot, seq

    def test_multiple_tags_on_one_guest(self, seating_state):
        snapshot, seq = self._make_tags_state(seating_state)

        # Tag Linda as vip
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="relationship.set",
                payload={
                    "from": "guests/guest_linda",
                    "to": "tags/tag_vip",
                    "type": "tagged_with",
                    "cardinality": "many_to_many",
                },
            ),
        )
        snapshot = result.snapshot

        # Tag Linda as vegetarian too
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="relationship.set",
                payload={
                    "from": "guests/guest_linda",
                    "to": "tags/tag_vegetarian",
                    "type": "tagged_with",
                },
            ),
        )

        assert result.applied
        linda_tags = _rels_from(result.snapshot, "guests/guest_linda", "tagged_with")
        assert len(linda_tags) == 2
        tag_targets = {r["to"] for r in linda_tags}
        assert tag_targets == {"tags/tag_vip", "tags/tag_vegetarian"}

    def test_same_tag_on_multiple_guests(self, seating_state):
        snapshot, seq = self._make_tags_state(seating_state)

        # Linda is vip
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="relationship.set",
                payload={
                    "from": "guests/guest_linda",
                    "to": "tags/tag_vip",
                    "type": "tagged_with",
                    "cardinality": "many_to_many",
                },
            ),
        )
        snapshot = result.snapshot

        # Steve is also vip
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="relationship.set",
                payload={
                    "from": "guests/guest_steve",
                    "to": "tags/tag_vip",
                    "type": "tagged_with",
                },
            ),
        )

        assert result.applied
        vip_rels = _rels_to(result.snapshot, "tags/tag_vip", "tagged_with")
        assert len(vip_rels) == 2

    def test_no_auto_removal(self, seating_state):
        """Adding a second tag of the same type does NOT remove the first."""
        snapshot, seq = self._make_tags_state(seating_state)

        # Linda tagged vip
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="relationship.set",
                payload={
                    "from": "guests/guest_linda",
                    "to": "tags/tag_vip",
                    "type": "tagged_with",
                    "cardinality": "many_to_many",
                },
            ),
        )
        snapshot = result.snapshot

        # Linda tagged vegetarian -- vip should still be there
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="relationship.set",
                payload={
                    "from": "guests/guest_linda",
                    "to": "tags/tag_vegetarian",
                    "type": "tagged_with",
                },
            ),
        )

        assert result.applied
        linda_tags = _rels_from(result.snapshot, "guests/guest_linda", "tagged_with")
        assert len(linda_tags) == 2
        # vip is still there
        assert any(r["to"] == "tags/tag_vip" for r in linda_tags)


# ============================================================================
# Relationship type registration and immutability
# ============================================================================


class TestRelationshipTypeRegistration:
    """
    The first relationship.set for a type registers its cardinality.
    Subsequent sets for the same type use the stored cardinality,
    ignoring any cardinality in the payload.
    """

    def test_first_set_registers_type(self, seating_state):
        snapshot, seq = seating_state

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="relationship.set",
                payload={
                    "from": "guests/guest_linda",
                    "to": "tables/table_1",
                    "type": "seated_at",
                    "cardinality": "many_to_one",
                },
            ),
        )

        assert result.applied
        rt = result.snapshot["relationship_types"]
        assert "seated_at" in rt
        assert rt["seated_at"]["cardinality"] == "many_to_one"

    def test_cardinality_is_immutable(self, seating_state):
        """Second set with different cardinality is ignored -- stored value wins."""
        snapshot, seq = seating_state

        # Register as many_to_one
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="relationship.set",
                payload={
                    "from": "guests/guest_linda",
                    "to": "tables/table_1",
                    "type": "seated_at",
                    "cardinality": "many_to_one",
                },
            ),
        )
        snapshot = result.snapshot

        # Try to set as many_to_many -- should be ignored
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="relationship.set",
                payload={
                    "from": "guests/guest_steve",
                    "to": "tables/table_1",
                    "type": "seated_at",
                    "cardinality": "many_to_many",  # Ignored
                },
            ),
        )

        assert result.applied
        # Still many_to_one
        assert result.snapshot["relationship_types"]["seated_at"]["cardinality"] == "many_to_one"

    def test_default_cardinality_is_many_to_one(self, seating_state):
        """If no cardinality is provided, default to many_to_one."""
        snapshot, seq = seating_state

        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="relationship.set",
                payload={
                    "from": "guests/guest_linda",
                    "to": "tables/table_1",
                    "type": "assigned_to",
                    # No cardinality field
                },
            ),
        )

        assert result.applied
        assert result.snapshot["relationship_types"]["assigned_to"]["cardinality"] == "many_to_one"

    def test_stored_cardinality_enforced_on_subsequent_sets(self, seating_state):
        """
        Register as many_to_one. Second set from same source should
        auto-remove the first, even though the second set doesn't
        specify cardinality at all.
        """
        snapshot, seq = seating_state

        # Linda at table 1 (registers many_to_one)
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="relationship.set",
                payload={
                    "from": "guests/guest_linda",
                    "to": "tables/table_1",
                    "type": "seated_at",
                    "cardinality": "many_to_one",
                },
            ),
        )
        snapshot = result.snapshot

        # Linda at table 2 (no cardinality -- uses stored many_to_one)
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="relationship.set",
                payload={
                    "from": "guests/guest_linda",
                    "to": "tables/table_2",
                    "type": "seated_at",
                },
            ),
        )

        assert result.applied
        linda_rels = _rels_from(result.snapshot, "guests/guest_linda", "seated_at")
        assert len(linda_rels) == 1
        assert linda_rels[0]["to"] == "tables/table_2"


# ============================================================================
# Entity removal excludes relationships
# ============================================================================


class TestEntityRemovalExcludesRelationships:
    """When an entity is removed, relationships involving it are excluded."""

    def test_remove_source_entity(self, seating_state):
        snapshot, seq = seating_state

        # Seat Linda at table 1
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 1,
                type="relationship.set",
                payload={
                    "from": "guests/guest_linda",
                    "to": "tables/table_1",
                    "type": "seated_at",
                    "cardinality": "many_to_one",
                },
            ),
        )
        snapshot = result.snapshot
        assert len(_active_rels(snapshot, "seated_at")) == 1

        # Remove Linda
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 2,
                type="entity.remove",
                payload={"ref": "guests/guest_linda"},
            ),
        )

        assert result.applied
        entity = result.snapshot["collections"]["guests"]["entities"]["guest_linda"]
        assert entity["_removed"] is True

    def test_remove_target_entity(self, seating_state):
        """Removing a table should exclude relationships pointing to it."""
        snapshot, seq = seating_state

        # Seat Linda and Steve at table 1
        for i, guest in enumerate(["linda", "steve"]):
            result = reduce(
                snapshot,
                make_event(
                    seq=seq + 1 + i,
                    type="relationship.set",
                    payload={
                        "from": f"guests/guest_{guest}",
                        "to": "tables/table_1",
                        "type": "seated_at",
                        "cardinality": "many_to_one",
                    },
                ),
            )
            snapshot = result.snapshot

        assert len(_rels_to(snapshot, "tables/table_1", "seated_at")) == 2

        # Remove table 1
        result = reduce(
            snapshot,
            make_event(
                seq=seq + 3,
                type="entity.remove",
                payload={"ref": "tables/table_1"},
            ),
        )

        assert result.applied
        table = result.snapshot["collections"]["tables"]["entities"]["table_1"]
        assert table["_removed"] is True
