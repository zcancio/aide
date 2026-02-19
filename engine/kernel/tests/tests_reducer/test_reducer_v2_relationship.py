"""
AIde v2 Reducer — Relationship Primitive Tests

Tests for rel.set, rel.remove, rel.constrain.
"""

import pytest

from engine.kernel.reducer_v2 import empty_snapshot, reduce

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def empty():
    return empty_snapshot()


@pytest.fixture
def state_with_two_entities(empty):
    snap = empty
    for eid in ["entity_a", "entity_b"]:
        result = reduce(snap, {"t": "entity.create", "id": eid, "p": {"name": eid}})
        assert result.accepted
        snap = result.snapshot
    return snap


@pytest.fixture
def state_with_three_entities(empty):
    snap = empty
    for eid in ["entity_a", "entity_b", "entity_c"]:
        result = reduce(snap, {"t": "entity.create", "id": eid, "p": {"name": eid}})
        assert result.accepted
        snap = result.snapshot
    return snap


# ============================================================================
# rel.set
# ============================================================================


class TestRelSet:
    def test_creates_new_relationship(self, state_with_two_entities):
        result = reduce(
            state_with_two_entities,
            {"t": "rel.set", "from": "entity_a", "to": "entity_b", "type": "knows", "cardinality": "many_to_many"},
        )
        assert result.accepted
        rels = result.snapshot["relationships"]
        assert len(rels) == 1
        assert rels[0]["from"] == "entity_a"
        assert rels[0]["to"] == "entity_b"
        assert rels[0]["type"] == "knows"

    def test_cardinality_persisted_on_first_set(self, state_with_two_entities):
        result = reduce(
            state_with_two_entities,
            {"t": "rel.set", "from": "entity_a", "to": "entity_b", "type": "leads", "cardinality": "many_to_one"},
        )
        assert result.accepted
        assert result.snapshot["rel_cardinalities"]["leads"] == "many_to_one"

    def test_many_to_one_auto_removes_old_link(self, state_with_three_entities):
        snap = state_with_three_entities
        # entity_a → entity_b (many_to_one)
        result = reduce(
            snap,
            {"t": "rel.set", "from": "entity_a", "to": "entity_b", "type": "reports_to", "cardinality": "many_to_one"},
        )
        snap = result.snapshot
        # entity_a → entity_c (should replace entity_b)
        result = reduce(snap, {"t": "rel.set", "from": "entity_a", "to": "entity_c", "type": "reports_to"})
        assert result.accepted
        rels = [r for r in result.snapshot["relationships"] if r["type"] == "reports_to"]
        assert len(rels) == 1
        assert rels[0]["to"] == "entity_c"

    def test_one_to_one_auto_removes_both_sides(self, state_with_three_entities):
        snap = state_with_three_entities
        # entity_a ↔ entity_b (one_to_one)
        result = reduce(
            snap, {"t": "rel.set", "from": "entity_a", "to": "entity_b", "type": "partner", "cardinality": "one_to_one"}
        )
        snap = result.snapshot
        # entity_c → entity_b (should replace entity_a's link)
        result = reduce(snap, {"t": "rel.set", "from": "entity_c", "to": "entity_b", "type": "partner"})
        assert result.accepted
        rels = [r for r in result.snapshot["relationships"] if r["type"] == "partner"]
        assert len(rels) == 1
        assert rels[0]["from"] == "entity_c"
        assert rels[0]["to"] == "entity_b"

    def test_many_to_many_allows_multiple_links(self, state_with_three_entities):
        snap = state_with_three_entities
        result = reduce(
            snap, {"t": "rel.set", "from": "entity_a", "to": "entity_b", "type": "likes", "cardinality": "many_to_many"}
        )
        snap = result.snapshot
        result = reduce(snap, {"t": "rel.set", "from": "entity_a", "to": "entity_c", "type": "likes"})
        assert result.accepted
        rels = [r for r in result.snapshot["relationships"] if r["type"] == "likes"]
        assert len(rels) == 2

    def test_reject_from_entity_not_found(self, state_with_two_entities):
        result = reduce(
            state_with_two_entities,
            {"t": "rel.set", "from": "nobody", "to": "entity_b", "type": "x"},
        )
        assert not result.accepted
        assert "ENTITY_NOT_FOUND" in result.reason

    def test_reject_to_entity_not_found(self, state_with_two_entities):
        result = reduce(
            state_with_two_entities,
            {"t": "rel.set", "from": "entity_a", "to": "nobody", "type": "x"},
        )
        assert not result.accepted
        assert "ENTITY_NOT_FOUND" in result.reason

    def test_reject_missing_from(self, state_with_two_entities):
        result = reduce(state_with_two_entities, {"t": "rel.set", "to": "entity_b", "type": "x"})
        assert not result.accepted
        assert "MISSING_FROM" in result.reason

    def test_reject_missing_to(self, state_with_two_entities):
        result = reduce(state_with_two_entities, {"t": "rel.set", "from": "entity_a", "type": "x"})
        assert not result.accepted
        assert "MISSING_TO" in result.reason

    def test_reject_missing_type(self, state_with_two_entities):
        result = reduce(state_with_two_entities, {"t": "rel.set", "from": "entity_a", "to": "entity_b"})
        assert not result.accepted
        assert "MISSING_TYPE" in result.reason

    def test_existing_cardinality_used_not_overridden(self, state_with_three_entities):
        snap = state_with_three_entities
        # First set establishes many_to_one
        result = reduce(
            snap, {"t": "rel.set", "from": "entity_a", "to": "entity_b", "type": "owns", "cardinality": "many_to_one"}
        )
        snap = result.snapshot
        # Second set tries many_to_many — should use stored many_to_one
        result = reduce(
            snap, {"t": "rel.set", "from": "entity_a", "to": "entity_c", "type": "owns", "cardinality": "many_to_many"}
        )
        assert result.accepted
        rels = [r for r in result.snapshot["relationships"] if r["type"] == "owns"]
        # many_to_one enforced: only one "owns" from entity_a
        assert len(rels) == 1
        assert rels[0]["to"] == "entity_c"


# ============================================================================
# rel.remove
# ============================================================================


class TestRelRemove:
    def test_removes_existing_relationship(self, state_with_two_entities):
        snap = state_with_two_entities
        result = reduce(snap, {"t": "rel.set", "from": "entity_a", "to": "entity_b", "type": "likes"})
        snap = result.snapshot
        assert len(snap["relationships"]) == 1

        result = reduce(snap, {"t": "rel.remove", "from": "entity_a", "to": "entity_b", "type": "likes"})
        assert result.accepted
        assert len(result.snapshot["relationships"]) == 0

    def test_no_op_if_relationship_doesnt_exist(self, state_with_two_entities):
        result = reduce(
            state_with_two_entities,
            {"t": "rel.remove", "from": "entity_a", "to": "entity_b", "type": "nonexistent"},
        )
        assert result.accepted  # Idempotent

    def test_removes_only_matching_relationship(self, state_with_three_entities):
        snap = state_with_three_entities
        result = reduce(
            snap, {"t": "rel.set", "from": "entity_a", "to": "entity_b", "type": "x", "cardinality": "many_to_many"}
        )
        snap = result.snapshot
        result = reduce(snap, {"t": "rel.set", "from": "entity_a", "to": "entity_c", "type": "x"})
        snap = result.snapshot
        assert len(snap["relationships"]) == 2

        result = reduce(snap, {"t": "rel.remove", "from": "entity_a", "to": "entity_b", "type": "x"})
        assert result.accepted
        rels = result.snapshot["relationships"]
        assert len(rels) == 1
        assert rels[0]["to"] == "entity_c"


# ============================================================================
# rel.constrain
# ============================================================================


class TestRelConstrain:
    def test_add_constraint(self, state_with_two_entities):
        result = reduce(
            state_with_two_entities,
            {
                "t": "rel.constrain",
                "id": "no_pair",
                "rule": "exclude_pair",
                "entities": ["entity_a", "entity_b"],
                "rel_type": "seated_at",
                "message": "Keep apart",
                "strict": False,
            },
        )
        assert result.accepted
        assert "no_pair" in result.snapshot["rel_constraints"]
        constraint = result.snapshot["rel_constraints"]["no_pair"]
        assert constraint["rule"] == "exclude_pair"
        assert constraint["message"] == "Keep apart"

    def test_strict_constraint_rejects_violating_state(self, state_with_three_entities):
        snap = state_with_three_entities
        # Set up entity_a and entity_b both pointing to entity_c
        result = reduce(
            snap,
            {"t": "rel.set", "from": "entity_a", "to": "entity_c", "type": "seated_at", "cardinality": "many_to_many"},
        )
        snap = result.snapshot
        result = reduce(snap, {"t": "rel.set", "from": "entity_b", "to": "entity_c", "type": "seated_at"})
        snap = result.snapshot

        # Now add strict constraint that they can't share the same target
        result = reduce(
            snap,
            {
                "t": "rel.constrain",
                "id": "no_pair",
                "rule": "exclude_pair",
                "entities": ["entity_a", "entity_b"],
                "rel_type": "seated_at",
                "strict": True,
            },
        )
        assert not result.accepted
        assert "STRICT_CONSTRAINT_VIOLATED" in result.reason

    def test_non_strict_constraint_adds_without_rejecting(self, state_with_three_entities):
        snap = state_with_three_entities
        # Even if state "violates" non-strict constraint, it's allowed
        result = reduce(
            snap,
            {"t": "rel.set", "from": "entity_a", "to": "entity_c", "type": "seated_at", "cardinality": "many_to_many"},
        )
        snap = result.snapshot
        result = reduce(snap, {"t": "rel.set", "from": "entity_b", "to": "entity_c", "type": "seated_at"})
        snap = result.snapshot

        result = reduce(
            snap,
            {
                "t": "rel.constrain",
                "id": "soft_pair",
                "rule": "exclude_pair",
                "entities": ["entity_a", "entity_b"],
                "rel_type": "seated_at",
                "strict": False,
            },
        )
        assert result.accepted

    def test_reject_missing_id(self, state_with_two_entities):
        result = reduce(
            state_with_two_entities,
            {"t": "rel.constrain", "rule": "exclude_pair"},
        )
        assert not result.accepted
        assert "MISSING_ID" in result.reason
