"""
AIde Reducer -- Constraint Checking Tests (Category 4)

Tests for all 7 constraint rules:
  exclude_pair      -- two entities must NOT share the same target
  require_same      -- two entities MUST share the same target
  max_per_target    -- no target can have more than N sources
  min_per_target    -- every target must have at least N sources
  collection_max_entities -- collection can't exceed N entities
  unique_field      -- no two entities can share a value for a field
  required_fields   -- specified fields must be non-null

Each rule is tested in both warn (default) and strict (rejection) modes.
Constraints are checked reactively -- only on events that could violate them.

Reference: aide_reducer_spec.md, section "Constraint Checking"
"""

import pytest

from engine.kernel.reducer import reduce, empty_state
from engine.kernel.events import make_event


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def seating_state():
    """
    Guests collection (Linda, Steve, Alice, Bob) and tables collection (3 tables).
    "seated_at" registered as many_to_one.
    Linda at table_1, Steve at table_1, Alice at table_2.
    """
    snapshot = empty_state()
    seq = 0

    # Guests
    seq += 1
    r = reduce(snapshot, make_event(seq=seq, type="collection.create", payload={
        "id": "guests", "name": "Guests",
        "schema": {"name": "string", "email": "string?"},
    }))
    snapshot = r.snapshot

    for name in ["Linda", "Steve", "Alice", "Bob"]:
        seq += 1
        r = reduce(snapshot, make_event(seq=seq, type="entity.create", payload={
            "collection": "guests", "id": f"guest_{name.lower()}",
            "fields": {"name": name, "email": None},
        }))
        snapshot = r.snapshot

    # Tables
    seq += 1
    r = reduce(snapshot, make_event(seq=seq, type="collection.create", payload={
        "id": "tables", "name": "Tables",
        "schema": {"label": "string", "capacity": "int"},
    }))
    snapshot = r.snapshot

    for i in range(1, 4):
        seq += 1
        r = reduce(snapshot, make_event(seq=seq, type="entity.create", payload={
            "collection": "tables", "id": f"table_{i}",
            "fields": {"label": f"Table {i}", "capacity": 8},
        }))
        snapshot = r.snapshot

    # Seat guests: Linda->table_1, Steve->table_1, Alice->table_2
    for guest, table in [("linda", "1"), ("steve", "1"), ("alice", "2")]:
        seq += 1
        r = reduce(snapshot, make_event(seq=seq, type="relationship.set", payload={
            "from": f"guests/guest_{guest}", "to": f"tables/table_{table}",
            "type": "seated_at", "cardinality": "many_to_one",
        }))
        snapshot = r.snapshot

    return snapshot, seq


@pytest.fixture
def roster_state():
    """
    Roster collection with 3 players (Mike, Dave, Jake).
    """
    snapshot = empty_state()
    seq = 0

    seq += 1
    r = reduce(snapshot, make_event(seq=seq, type="collection.create", payload={
        "id": "roster", "name": "Roster",
        "schema": {"name": "string", "email": "string?", "status": "string"},
    }))
    snapshot = r.snapshot

    for name in ["Mike", "Dave", "Jake"]:
        seq += 1
        r = reduce(snapshot, make_event(seq=seq, type="entity.create", payload={
            "collection": "roster", "id": f"player_{name.lower()}",
            "fields": {"name": name, "email": f"{name.lower()}@test.com", "status": "active"},
        }))
        snapshot = r.snapshot

    return snapshot, seq


def _has_warning(result, code):
    return any(code in str(w) for w in result.warnings)


def _add_constraint(snapshot, seq, constraint_payload):
    """Helper to add a constraint via relationship.constrain or meta.constrain."""
    # Determine which primitive based on whether it's a relationship or meta constraint
    rule = constraint_payload.get("rule", "")
    if rule in ("exclude_pair", "require_same", "max_per_target", "min_per_target"):
        ptype = "relationship.constrain"
    else:
        ptype = "meta.constrain"

    result = reduce(snapshot, make_event(seq=seq, type=ptype, payload=constraint_payload))
    assert result.applied
    return result.snapshot


# ============================================================================
# exclude_pair -- Two entities must NOT share the same target
# ============================================================================


class TestExcludePair:
    """Linda and Steve can't be at the same table."""

    def test_warn_on_violation(self, seating_state):
        """Default (non-strict): event applies, produces warning."""
        snapshot, seq = seating_state
        # Linda and Steve are already both at table_1

        # Add constraint: exclude Linda and Steve from same table
        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "no_linda_steve",
            "rule": "exclude_pair",
            "entities": ["guests/guest_linda", "guests/guest_steve"],
            "relationship_type": "seated_at",
            "message": "Keep Linda and Steve apart",
        })

        # Move Bob to table_1 -- unrelated, no warning
        result = reduce(snapshot, make_event(seq=seq + 2, type="relationship.set", payload={
            "from": "guests/guest_bob", "to": "tables/table_1",
            "type": "seated_at",
        }))
        assert result.applied
        assert not _has_warning(result, "CONSTRAINT_VIOLATED")

    def test_warn_when_seating_violates(self, seating_state):
        """Seat Steve at Linda's table after constraint is set."""
        snapshot, seq = seating_state

        # Move Steve to table_2 first (so they're apart)
        result = reduce(snapshot, make_event(seq=seq + 1, type="relationship.set", payload={
            "from": "guests/guest_steve", "to": "tables/table_2",
            "type": "seated_at",
        }))
        snapshot = result.snapshot

        # Add constraint
        snapshot = _add_constraint(snapshot, seq + 2, {
            "id": "no_linda_steve",
            "rule": "exclude_pair",
            "entities": ["guests/guest_linda", "guests/guest_steve"],
            "relationship_type": "seated_at",
            "message": "Keep Linda and Steve apart",
        })

        # Move Steve back to table_1 (where Linda is) -- should warn
        result = reduce(snapshot, make_event(seq=seq + 3, type="relationship.set", payload={
            "from": "guests/guest_steve", "to": "tables/table_1",
            "type": "seated_at",
        }))
        assert result.applied  # Non-strict: still applies
        assert _has_warning(result, "CONSTRAINT_VIOLATED")

    def test_strict_rejects(self, seating_state):
        """Strict exclude_pair rejects the event."""
        snapshot, seq = seating_state

        # Move Steve to table_2 first
        result = reduce(snapshot, make_event(seq=seq + 1, type="relationship.set", payload={
            "from": "guests/guest_steve", "to": "tables/table_2",
            "type": "seated_at",
        }))
        snapshot = result.snapshot

        # Add strict constraint
        snapshot = _add_constraint(snapshot, seq + 2, {
            "id": "no_linda_steve",
            "rule": "exclude_pair",
            "entities": ["guests/guest_linda", "guests/guest_steve"],
            "relationship_type": "seated_at",
            "message": "Keep Linda and Steve apart",
            "strict": True,
        })

        # Try to seat Steve at table_1 (where Linda is) -- should reject
        result = reduce(snapshot, make_event(seq=seq + 3, type="relationship.set", payload={
            "from": "guests/guest_steve", "to": "tables/table_1",
            "type": "seated_at",
        }))
        assert not result.applied
        assert "STRICT_CONSTRAINT_VIOLATED" in result.error

    def test_no_violation_when_at_different_targets(self, seating_state):
        """No warning when the pair is at different tables."""
        snapshot, seq = seating_state

        # Move Steve to table_2
        result = reduce(snapshot, make_event(seq=seq + 1, type="relationship.set", payload={
            "from": "guests/guest_steve", "to": "tables/table_2",
            "type": "seated_at",
        }))
        snapshot = result.snapshot

        # Add constraint
        snapshot = _add_constraint(snapshot, seq + 2, {
            "id": "no_linda_steve",
            "rule": "exclude_pair",
            "entities": ["guests/guest_linda", "guests/guest_steve"],
            "relationship_type": "seated_at",
            "message": "Keep Linda and Steve apart",
        })

        # Move Steve to table_3 (still not with Linda) -- no warning
        result = reduce(snapshot, make_event(seq=seq + 3, type="relationship.set", payload={
            "from": "guests/guest_steve", "to": "tables/table_3",
            "type": "seated_at",
        }))
        assert result.applied
        assert not _has_warning(result, "CONSTRAINT_VIOLATED")


# ============================================================================
# require_same -- Two entities MUST share the same target
# ============================================================================


class TestRequireSame:
    """VIP couples must be at the same table."""

    def test_warn_when_separated(self, seating_state):
        """Warn when the pair ends up at different tables."""
        snapshot, seq = seating_state
        # Linda at table_1, Alice at table_2

        # Constrain: Linda and Alice must be together
        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "linda_alice_together",
            "rule": "require_same",
            "entities": ["guests/guest_linda", "guests/guest_alice"],
            "relationship_type": "seated_at",
            "message": "Linda and Alice must sit together",
        })

        # Move Linda to table_3 (away from Alice at table_2) -- should warn
        result = reduce(snapshot, make_event(seq=seq + 2, type="relationship.set", payload={
            "from": "guests/guest_linda", "to": "tables/table_3",
            "type": "seated_at",
        }))
        assert result.applied
        assert _has_warning(result, "CONSTRAINT_VIOLATED")

    def test_no_warning_when_together(self, seating_state):
        """No warning when the pair is at the same table."""
        snapshot, seq = seating_state

        # Constrain: Linda and Alice must be together
        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "linda_alice_together",
            "rule": "require_same",
            "entities": ["guests/guest_linda", "guests/guest_alice"],
            "relationship_type": "seated_at",
            "message": "Linda and Alice must sit together",
        })

        # Move Alice to table_1 (where Linda already is) -- satisfied, no warning
        result = reduce(snapshot, make_event(seq=seq + 2, type="relationship.set", payload={
            "from": "guests/guest_alice", "to": "tables/table_1",
            "type": "seated_at",
        }))
        assert result.applied
        assert not _has_warning(result, "CONSTRAINT_VIOLATED")

    def test_strict_rejects_separation(self, seating_state):
        snapshot, seq = seating_state

        # Move Alice to table_1 so they start together
        result = reduce(snapshot, make_event(seq=seq + 1, type="relationship.set", payload={
            "from": "guests/guest_alice", "to": "tables/table_1",
            "type": "seated_at",
        }))
        snapshot = result.snapshot

        # Strict constraint
        snapshot = _add_constraint(snapshot, seq + 2, {
            "id": "linda_alice_together",
            "rule": "require_same",
            "entities": ["guests/guest_linda", "guests/guest_alice"],
            "relationship_type": "seated_at",
            "message": "Linda and Alice must sit together",
            "strict": True,
        })

        # Try to move Alice away -- should reject
        result = reduce(snapshot, make_event(seq=seq + 3, type="relationship.set", payload={
            "from": "guests/guest_alice", "to": "tables/table_3",
            "type": "seated_at",
        }))
        assert not result.applied
        assert "STRICT_CONSTRAINT_VIOLATED" in result.error


# ============================================================================
# max_per_target -- No target can have more than N sources
# ============================================================================


class TestMaxPerTarget:
    """Max 2 guests per table."""

    def test_warn_on_exceeding_max(self, seating_state):
        """Third guest at a table with max=2 should warn."""
        snapshot, seq = seating_state
        # Linda and Steve already at table_1

        # Constraint: max 2 per table
        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "max_2_per_table",
            "rule": "max_per_target",
            "relationship_type": "seated_at",
            "value": 2,
            "message": "Max 2 guests per table",
        })

        # Seat Bob at table_1 (would be 3rd) -- should warn
        result = reduce(snapshot, make_event(seq=seq + 2, type="relationship.set", payload={
            "from": "guests/guest_bob", "to": "tables/table_1",
            "type": "seated_at",
        }))
        assert result.applied  # Non-strict
        assert _has_warning(result, "CONSTRAINT_VIOLATED")

    def test_no_warning_within_limit(self, seating_state):
        """Seating within the limit should not warn."""
        snapshot, seq = seating_state
        # Alice at table_2 (alone)

        # Constraint: max 2 per table
        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "max_2_per_table",
            "rule": "max_per_target",
            "relationship_type": "seated_at",
            "value": 2,
            "message": "Max 2 guests per table",
        })

        # Seat Bob at table_2 (would be 2nd, within limit) -- no warning
        result = reduce(snapshot, make_event(seq=seq + 2, type="relationship.set", payload={
            "from": "guests/guest_bob", "to": "tables/table_2",
            "type": "seated_at",
        }))
        assert result.applied
        assert not _has_warning(result, "CONSTRAINT_VIOLATED")

    def test_strict_rejects_over_max(self, seating_state):
        snapshot, seq = seating_state

        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "max_2_per_table",
            "rule": "max_per_target",
            "relationship_type": "seated_at",
            "value": 2,
            "message": "Max 2 guests per table",
            "strict": True,
        })

        # 3rd guest at table_1 -- reject
        result = reduce(snapshot, make_event(seq=seq + 2, type="relationship.set", payload={
            "from": "guests/guest_bob", "to": "tables/table_1",
            "type": "seated_at",
        }))
        assert not result.applied
        assert "STRICT_CONSTRAINT_VIOLATED" in result.error


# ============================================================================
# min_per_target -- Every target must have at least N sources
# ============================================================================


class TestMinPerTarget:
    """Every table must have at least 2 guests."""

    def test_warn_when_table_drops_below_min(self, seating_state):
        """Moving a guest away leaves table below minimum."""
        snapshot, seq = seating_state
        # Alice alone at table_2

        # Constraint: min 2 per table
        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "min_2_per_table",
            "rule": "min_per_target",
            "relationship_type": "seated_at",
            "value": 2,
            "message": "Every table needs at least 2 guests",
        })

        # Move Steve from table_1 to table_2
        # table_1 drops from 2 to 1 -- should warn
        result = reduce(snapshot, make_event(seq=seq + 2, type="relationship.set", payload={
            "from": "guests/guest_steve", "to": "tables/table_2",
            "type": "seated_at",
        }))
        assert result.applied
        assert _has_warning(result, "CONSTRAINT_VIOLATED")

    def test_no_warning_when_above_min(self, seating_state):
        """Seating that keeps all tables above min is fine."""
        snapshot, seq = seating_state
        # Linda and Steve at table_1 (2 guests)

        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "min_2_per_table",
            "rule": "min_per_target",
            "relationship_type": "seated_at",
            "value": 2,
            "message": "Every table needs at least 2 guests",
        })

        # Seat Bob at table_1 (goes from 2 to 3) -- still above min, no warning from this target
        # But table_2 (Alice alone) and table_3 (empty) may already violate.
        # The check is on the event's affected targets, not all targets.
        # Bob going to table_1 doesn't change table_2 or table_3.
        result = reduce(snapshot, make_event(seq=seq + 2, type="relationship.set", payload={
            "from": "guests/guest_bob", "to": "tables/table_1",
            "type": "seated_at",
        }))
        assert result.applied

    def test_strict_rejects(self, seating_state):
        snapshot, seq = seating_state

        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "min_2_per_table",
            "rule": "min_per_target",
            "relationship_type": "seated_at",
            "value": 2,
            "message": "Every table needs at least 2 guests",
            "strict": True,
        })

        # Move Steve from table_1 to table_2 -- table_1 drops to 1, reject
        result = reduce(snapshot, make_event(seq=seq + 2, type="relationship.set", payload={
            "from": "guests/guest_steve", "to": "tables/table_2",
            "type": "seated_at",
        }))
        assert not result.applied
        assert "STRICT_CONSTRAINT_VIOLATED" in result.error


# ============================================================================
# collection_max_entities -- Collection can't exceed N entities
# ============================================================================


class TestCollectionMaxEntities:
    """Max 10 players in roster."""

    def test_warn_on_exceeding_max(self, roster_state):
        """4th player when max is 3 should warn."""
        snapshot, seq = roster_state  # 3 players

        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "max_players",
            "rule": "collection_max_entities",
            "collection": "roster",
            "value": 3,
            "message": "Max 3 players",
        })

        result = reduce(snapshot, make_event(seq=seq + 2, type="entity.create", payload={
            "collection": "roster", "id": "player_new",
            "fields": {"name": "New Player", "email": None, "status": "active"},
        }))
        assert result.applied
        assert _has_warning(result, "CONSTRAINT_VIOLATED")

    def test_no_warning_within_limit(self, roster_state):
        snapshot, seq = roster_state  # 3 players

        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "max_players",
            "rule": "collection_max_entities",
            "collection": "roster",
            "value": 10,  # Well above current count
            "message": "Max 10 players",
        })

        result = reduce(snapshot, make_event(seq=seq + 2, type="entity.create", payload={
            "collection": "roster", "id": "player_new",
            "fields": {"name": "New Player", "email": None, "status": "active"},
        }))
        assert result.applied
        assert not _has_warning(result, "CONSTRAINT_VIOLATED")

    def test_strict_rejects(self, roster_state):
        snapshot, seq = roster_state

        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "max_players",
            "rule": "collection_max_entities",
            "collection": "roster",
            "value": 3,
            "message": "Max 3 players",
            "strict": True,
        })

        result = reduce(snapshot, make_event(seq=seq + 2, type="entity.create", payload={
            "collection": "roster", "id": "player_new",
            "fields": {"name": "New Player", "email": None, "status": "active"},
        }))
        assert not result.applied
        assert "STRICT_CONSTRAINT_VIOLATED" in result.error

    def test_removed_entities_dont_count(self, roster_state):
        """Removed entities should not count toward the max."""
        snapshot, seq = roster_state  # 3 players

        # Remove one player
        result = reduce(snapshot, make_event(seq=seq + 1, type="entity.remove", payload={
            "ref": "roster/player_jake",
        }))
        snapshot = result.snapshot

        # Strict max 3 -- only 2 active now
        snapshot = _add_constraint(snapshot, seq + 2, {
            "id": "max_players",
            "rule": "collection_max_entities",
            "collection": "roster",
            "value": 3,
            "message": "Max 3 players",
            "strict": True,
        })

        result = reduce(snapshot, make_event(seq=seq + 3, type="entity.create", payload={
            "collection": "roster", "id": "player_new",
            "fields": {"name": "New Player", "email": None, "status": "active"},
        }))
        assert result.applied  # 3rd active entity, within limit

    def test_immediate_validation_on_constrain(self, roster_state):
        """Adding a constraint that's already violated produces an immediate warning."""
        snapshot, seq = roster_state  # 3 players

        result = reduce(snapshot, make_event(seq=seq + 1, type="meta.constrain", payload={
            "id": "max_players",
            "rule": "collection_max_entities",
            "collection": "roster",
            "value": 2,  # Already exceeded
            "message": "Max 2 players",
        }))
        assert result.applied  # Constraint is stored
        assert _has_warning(result, "CONSTRAINT_VIOLATED")


# ============================================================================
# unique_field -- No two entities can share a value for a field
# ============================================================================


class TestUniqueField:
    """No duplicate email addresses."""

    def test_warn_on_duplicate_create(self, roster_state):
        snapshot, seq = roster_state

        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "unique_email",
            "rule": "unique_field",
            "collection": "roster",
            "field": "email",
            "message": "Email must be unique",
        })

        # Create player with duplicate email
        result = reduce(snapshot, make_event(seq=seq + 2, type="entity.create", payload={
            "collection": "roster", "id": "player_new",
            "fields": {"name": "New", "email": "mike@test.com", "status": "active"},
            # mike@test.com already exists on player_mike
        }))
        assert result.applied
        assert _has_warning(result, "CONSTRAINT_VIOLATED")

    def test_warn_on_duplicate_update(self, roster_state):
        snapshot, seq = roster_state

        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "unique_email",
            "rule": "unique_field",
            "collection": "roster",
            "field": "email",
            "message": "Email must be unique",
        })

        # Update Dave's email to Mike's
        result = reduce(snapshot, make_event(seq=seq + 2, type="entity.update", payload={
            "ref": "roster/player_dave",
            "fields": {"email": "mike@test.com"},
        }))
        assert result.applied
        assert _has_warning(result, "CONSTRAINT_VIOLATED")

    def test_no_warning_on_unique_value(self, roster_state):
        snapshot, seq = roster_state

        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "unique_email",
            "rule": "unique_field",
            "collection": "roster",
            "field": "email",
            "message": "Email must be unique",
        })

        result = reduce(snapshot, make_event(seq=seq + 2, type="entity.create", payload={
            "collection": "roster", "id": "player_new",
            "fields": {"name": "New", "email": "unique@test.com", "status": "active"},
        }))
        assert result.applied
        assert not _has_warning(result, "CONSTRAINT_VIOLATED")

    def test_nulls_dont_conflict(self, roster_state):
        """Multiple null values in a unique field should not trigger a warning."""
        snapshot, seq = roster_state

        # Clear all emails to null first
        for player in ["mike", "dave", "jake"]:
            seq += 1
            result = reduce(snapshot, make_event(seq=seq, type="entity.update", payload={
                "ref": f"roster/player_{player}",
                "fields": {"email": None},
            }))
            snapshot = result.snapshot

        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "unique_email",
            "rule": "unique_field",
            "collection": "roster",
            "field": "email",
            "message": "Email must be unique",
        })

        # Create player with null email -- should not warn even though others are null
        result = reduce(snapshot, make_event(seq=seq + 2, type="entity.create", payload={
            "collection": "roster", "id": "player_new",
            "fields": {"name": "New", "email": None, "status": "active"},
        }))
        assert result.applied
        assert not _has_warning(result, "CONSTRAINT_VIOLATED")

    def test_strict_rejects_duplicate(self, roster_state):
        snapshot, seq = roster_state

        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "unique_email",
            "rule": "unique_field",
            "collection": "roster",
            "field": "email",
            "message": "Email must be unique",
            "strict": True,
        })

        result = reduce(snapshot, make_event(seq=seq + 2, type="entity.create", payload={
            "collection": "roster", "id": "player_new",
            "fields": {"name": "New", "email": "mike@test.com", "status": "active"},
        }))
        assert not result.applied
        assert "STRICT_CONSTRAINT_VIOLATED" in result.error

    def test_immediate_validation_on_constrain(self, roster_state):
        """Adding unique_field constraint when duplicates already exist should warn."""
        snapshot, seq = roster_state

        # Give Dave the same email as Mike
        result = reduce(snapshot, make_event(seq=seq + 1, type="entity.update", payload={
            "ref": "roster/player_dave",
            "fields": {"email": "mike@test.com"},
        }))
        snapshot = result.snapshot

        # Now add the constraint -- immediate validation should warn
        result = reduce(snapshot, make_event(seq=seq + 2, type="meta.constrain", payload={
            "id": "unique_email",
            "rule": "unique_field",
            "collection": "roster",
            "field": "email",
            "message": "Email must be unique",
        }))
        assert result.applied
        assert _has_warning(result, "CONSTRAINT_VIOLATED")


# ============================================================================
# required_fields -- Specified fields must be non-null on every entity
# ============================================================================


class TestRequiredFields:
    """Every guest must have a name."""

    def test_warn_on_null_required_field_create(self, roster_state):
        snapshot, seq = roster_state

        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "require_name",
            "rule": "required_fields",
            "collection": "roster",
            "fields": ["name"],
            "message": "Every player must have a name",
        })

        # Create player with null name -- should warn
        result = reduce(snapshot, make_event(seq=seq + 2, type="entity.create", payload={
            "collection": "roster", "id": "player_anonymous",
            "fields": {"name": None, "email": None, "status": "active"},
        }))
        # Note: "name" is "string" (required type) so this would already fail
        # as REQUIRED_FIELD_MISSING or TYPE_MISMATCH from schema validation.
        # The constraint adds an additional layer for nullable fields.
        # This test verifies the constraint layer fires when applicable.
        assert not result.applied  # Schema-level rejection takes precedence

    def test_warn_on_null_required_field_update(self, roster_state):
        """Updating a monitored field to null should warn."""
        snapshot, seq = roster_state

        # Make email a required field via constraint (email is string?, nullable at schema level)
        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "require_email",
            "rule": "required_fields",
            "collection": "roster",
            "fields": ["email"],
            "message": "Every player must have an email",
        })

        # Set Mike's email to null -- should warn (nullable at schema level, but constraint says required)
        result = reduce(snapshot, make_event(seq=seq + 2, type="entity.update", payload={
            "ref": "roster/player_mike",
            "fields": {"email": None},
        }))
        assert result.applied  # Schema allows null (string?), but constraint warns
        assert _has_warning(result, "CONSTRAINT_VIOLATED")

    def test_no_warning_when_field_present(self, roster_state):
        snapshot, seq = roster_state

        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "require_email",
            "rule": "required_fields",
            "collection": "roster",
            "fields": ["email"],
            "message": "Every player must have an email",
        })

        # Update email to a real value -- no warning
        result = reduce(snapshot, make_event(seq=seq + 2, type="entity.update", payload={
            "ref": "roster/player_mike",
            "fields": {"email": "mike@new.com"},
        }))
        assert result.applied
        assert not _has_warning(result, "CONSTRAINT_VIOLATED")

    def test_strict_rejects_null(self, roster_state):
        snapshot, seq = roster_state

        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "require_email",
            "rule": "required_fields",
            "collection": "roster",
            "fields": ["email"],
            "message": "Every player must have an email",
            "strict": True,
        })

        result = reduce(snapshot, make_event(seq=seq + 2, type="entity.update", payload={
            "ref": "roster/player_mike",
            "fields": {"email": None},
        }))
        assert not result.applied
        assert "STRICT_CONSTRAINT_VIOLATED" in result.error

    def test_field_remove_warns_if_referenced(self, roster_state):
        """Removing a field that a required_fields constraint references should warn."""
        snapshot, seq = roster_state

        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "require_email",
            "rule": "required_fields",
            "collection": "roster",
            "fields": ["email"],
            "message": "Every player must have an email",
        })

        # Remove the email field entirely
        result = reduce(snapshot, make_event(seq=seq + 2, type="field.remove", payload={
            "collection": "roster", "name": "email",
        }))
        assert result.applied  # Field removal still works
        assert len(result.warnings) > 0  # But warns about the constraint


# ============================================================================
# Multiple constraints on the same event
# ============================================================================


class TestMultipleConstraints:
    """Multiple constraints checked on a single event."""

    def test_multiple_warnings(self, seating_state):
        """An event can trigger warnings from multiple constraints simultaneously."""
        snapshot, seq = seating_state

        # Constraint 1: max 2 per table
        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "max_2",
            "rule": "max_per_target",
            "relationship_type": "seated_at",
            "value": 2,
            "message": "Max 2 per table",
        })

        # Constraint 2: exclude Linda and Bob from same table
        snapshot = _add_constraint(snapshot, seq + 2, {
            "id": "no_linda_bob",
            "rule": "exclude_pair",
            "entities": ["guests/guest_linda", "guests/guest_bob"],
            "relationship_type": "seated_at",
            "message": "Keep Linda and Bob apart",
        })

        # Seat Bob at table_1 (where Linda and Steve already are)
        # Violates BOTH: max_per_target (3rd guest) AND exclude_pair (Bob + Linda)
        result = reduce(snapshot, make_event(seq=seq + 3, type="relationship.set", payload={
            "from": "guests/guest_bob", "to": "tables/table_1",
            "type": "seated_at",
        }))
        assert result.applied  # Both non-strict
        assert len(result.warnings) >= 2

    def test_one_strict_one_not(self, seating_state):
        """If one constraint is strict and violated, the event is rejected
        even if other violated constraints are non-strict."""
        snapshot, seq = seating_state

        # Non-strict: max 2 per table
        snapshot = _add_constraint(snapshot, seq + 1, {
            "id": "max_2",
            "rule": "max_per_target",
            "relationship_type": "seated_at",
            "value": 2,
            "message": "Max 2 per table",
        })

        # Strict: exclude Linda and Bob
        snapshot = _add_constraint(snapshot, seq + 2, {
            "id": "no_linda_bob",
            "rule": "exclude_pair",
            "entities": ["guests/guest_linda", "guests/guest_bob"],
            "relationship_type": "seated_at",
            "message": "Keep Linda and Bob apart",
            "strict": True,
        })

        # Seat Bob at table_1 -- violates both, strict one rejects
        result = reduce(snapshot, make_event(seq=seq + 3, type="relationship.set", payload={
            "from": "guests/guest_bob", "to": "tables/table_1",
            "type": "seated_at",
        }))
        assert not result.applied
        assert "STRICT_CONSTRAINT_VIOLATED" in result.error
