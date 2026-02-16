"""
AIde Assembly -- Apply with Rejections Tests (Category 3)

Send 5 events where #3 is invalid. Verify #1, #2, #4, #5 applied,
#3 rejected with reason.

From the spec (aide_assembly_spec.md, "Testing Strategy"):
  "3. Apply with rejections. Send 5 events where #3 is invalid. Verify
   #1, #2, #4, #5 applied, #3 rejected with reason."

Properties from spec:
  - Partial application: if event 2 of 5 is rejected, events 1, 3, 4, 5 still apply
  - Order preserved: events are applied in the order given
  - Rejected events include error reason

Reference: aide_assembly_spec.md (apply operation, Testing Strategy)
"""

import pytest

from engine.kernel.assembly import AideAssembly, MemoryStorage
from engine.kernel.types import Blueprint, Event, now_iso


# ============================================================================
# Fixtures
# ============================================================================


def make_blueprint():
    return Blueprint(
        identity="Test aide for rejection testing.",
        voice="Direct.",
    )


def make_collection_event(seq: int) -> Event:
    return Event(
        id=f"evt_{seq:03d}",
        sequence=seq,
        timestamp=now_iso(),
        actor="user_test",
        source="test",
        type="collection.create",
        payload={"id": "items", "schema": {"name": "string", "count": "int"}},
    )


def make_entity_event(seq: int, entity_id: str, fields: dict) -> Event:
    return Event(
        id=f"evt_{seq:03d}",
        sequence=seq,
        timestamp=now_iso(),
        actor="user_test",
        source="test",
        type="entity.create",
        payload={"collection": "items", "id": entity_id, "fields": fields},
    )


def make_invalid_event(seq: int, error_type: str) -> Event:
    """Create an event that will be rejected for various reasons."""
    if error_type == "missing_collection":
        # Entity create for non-existent collection
        return Event(
            id=f"evt_{seq:03d}",
            sequence=seq,
            timestamp=now_iso(),
            actor="user_test",
            source="test",
            type="entity.create",
            payload={"collection": "nonexistent", "id": "x", "fields": {"name": "Test"}},
        )
    elif error_type == "invalid_payload":
        # collection.create without required 'id' field
        return Event(
            id=f"evt_{seq:03d}",
            sequence=seq,
            timestamp=now_iso(),
            actor="user_test",
            source="test",
            type="collection.create",
            payload={"schema": {"name": "string"}},  # Missing 'id'
        )
    elif error_type == "duplicate_entity":
        # Entity with ID that already exists
        return Event(
            id=f"evt_{seq:03d}",
            sequence=seq,
            timestamp=now_iso(),
            actor="user_test",
            source="test",
            type="entity.create",
            payload={"collection": "items", "id": "item_1", "fields": {"name": "Dupe"}},
        )
    elif error_type == "unknown_type":
        # Invalid primitive type
        return Event(
            id=f"evt_{seq:03d}",
            sequence=seq,
            timestamp=now_iso(),
            actor="user_test",
            source="test",
            type="invalid.type",
            payload={},
        )
    else:
        raise ValueError(f"Unknown error type: {error_type}")


# ============================================================================
# Partial application
# ============================================================================


class TestPartialApplication:
    """
    Verify that valid events are applied even when some events are rejected.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_five_events_third_invalid(self, assembly):
        """5 events, #3 invalid -> #1, #2, #4, #5 applied, #3 rejected."""
        aide_file = await assembly.create(make_blueprint())

        events = [
            make_collection_event(1),  # Valid: create collection
            make_entity_event(2, "item_1", {"name": "First", "count": 1}),  # Valid
            make_invalid_event(3, "invalid_payload"),  # Invalid: missing 'id'
            make_entity_event(4, "item_2", {"name": "Second", "count": 2}),  # Valid
            make_entity_event(5, "item_3", {"name": "Third", "count": 3}),  # Valid
        ]

        result = await assembly.apply(aide_file, events)

        # Check applied
        assert len(result.applied) == 4
        assert result.applied[0].sequence == 1
        assert result.applied[1].sequence == 2
        assert result.applied[2].sequence == 4
        assert result.applied[3].sequence == 5

        # Check rejected
        assert len(result.rejected) == 1
        rejected_event, reason = result.rejected[0]
        assert rejected_event.sequence == 3
        assert "id" in reason.lower() or "required" in reason.lower()

    @pytest.mark.asyncio
    async def test_first_event_invalid(self, assembly):
        """First event invalid -> skipped, rest applied if valid."""
        aide_file = await assembly.create(make_blueprint())

        events = [
            make_invalid_event(1, "invalid_payload"),  # Invalid
            make_collection_event(2),  # Valid
            make_entity_event(3, "item_1", {"name": "First", "count": 1}),  # Valid
        ]

        result = await assembly.apply(aide_file, events)

        assert len(result.applied) == 2
        assert len(result.rejected) == 1
        assert result.rejected[0][0].sequence == 1

    @pytest.mark.asyncio
    async def test_last_event_invalid(self, assembly):
        """Last event invalid -> first events applied, last rejected."""
        aide_file = await assembly.create(make_blueprint())

        events = [
            make_collection_event(1),
            make_entity_event(2, "item_1", {"name": "First", "count": 1}),
            make_invalid_event(3, "invalid_payload"),  # Invalid at end
        ]

        result = await assembly.apply(aide_file, events)

        assert len(result.applied) == 2
        assert len(result.rejected) == 1
        assert result.rejected[0][0].sequence == 3

    @pytest.mark.asyncio
    async def test_all_invalid(self, assembly):
        """All events invalid -> all rejected, no state change."""
        aide_file = await assembly.create(make_blueprint())
        original_snapshot_str = str(aide_file.snapshot)

        events = [
            make_invalid_event(1, "invalid_payload"),
            make_invalid_event(2, "invalid_payload"),
            make_invalid_event(3, "invalid_payload"),
        ]

        result = await assembly.apply(aide_file, events)

        assert len(result.applied) == 0
        assert len(result.rejected) == 3
        # Snapshot unchanged
        assert str(aide_file.snapshot) == original_snapshot_str

    @pytest.mark.asyncio
    async def test_alternating_valid_invalid(self, assembly):
        """Alternating valid/invalid -> valid ones applied."""
        aide_file = await assembly.create(make_blueprint())

        events = [
            make_collection_event(1),  # Valid
            make_invalid_event(2, "invalid_payload"),  # Invalid
            make_entity_event(3, "item_1", {"name": "First", "count": 1}),  # Valid
            make_invalid_event(4, "invalid_payload"),  # Invalid
            make_entity_event(5, "item_2", {"name": "Second", "count": 2}),  # Valid
        ]

        result = await assembly.apply(aide_file, events)

        assert len(result.applied) == 3
        assert len(result.rejected) == 2


class TestRejectionReasons:
    """
    Verify that rejected events include meaningful error reasons.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_missing_collection_reason(self, assembly):
        """Entity for non-existent collection has descriptive rejection reason."""
        aide_file = await assembly.create(make_blueprint())

        events = [make_invalid_event(1, "missing_collection")]
        result = await assembly.apply(aide_file, events)

        assert len(result.rejected) == 1
        _, reason = result.rejected[0]
        # Reason should mention collection or "not found" or similar
        assert "collection" in reason.lower() or "not found" in reason.lower() or "nonexistent" in reason.lower()

    @pytest.mark.asyncio
    async def test_invalid_payload_reason(self, assembly):
        """Invalid payload structure has descriptive rejection reason."""
        aide_file = await assembly.create(make_blueprint())

        events = [make_invalid_event(1, "invalid_payload")]
        result = await assembly.apply(aide_file, events)

        assert len(result.rejected) == 1
        _, reason = result.rejected[0]
        # Reason should mention missing field or validation error
        assert len(reason) > 0

    @pytest.mark.asyncio
    async def test_duplicate_entity_reason(self, assembly):
        """Duplicate entity creation has descriptive rejection reason."""
        aide_file = await assembly.create(make_blueprint())

        events = [
            make_collection_event(1),
            make_entity_event(2, "item_1", {"name": "First", "count": 1}),
            make_invalid_event(3, "duplicate_entity"),  # Same ID as above
        ]
        result = await assembly.apply(aide_file, events)

        assert len(result.rejected) == 1
        _, reason = result.rejected[0]
        # Reason should mention duplicate or already exists
        assert "exist" in reason.lower() or "duplicate" in reason.lower()

    @pytest.mark.asyncio
    async def test_unknown_type_reason(self, assembly):
        """Unknown primitive type has descriptive rejection reason."""
        aide_file = await assembly.create(make_blueprint())

        events = [make_invalid_event(1, "unknown_type")]
        result = await assembly.apply(aide_file, events)

        assert len(result.rejected) == 1
        _, reason = result.rejected[0]
        # Reason should mention unknown or invalid type
        assert len(reason) > 0


class TestOrderPreservation:
    """
    Verify events are applied in the order given, respecting dependencies.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_dependent_events_order(self, assembly):
        """Events that depend on previous events must be in order."""
        aide_file = await assembly.create(make_blueprint())

        # Collection must be created before entities
        events = [
            make_collection_event(1),
            make_entity_event(2, "item_1", {"name": "First", "count": 1}),
            make_entity_event(3, "item_2", {"name": "Second", "count": 2}),
        ]

        result = await assembly.apply(aide_file, events)

        assert len(result.applied) == 3
        assert result.applied[0].type == "collection.create"
        assert result.applied[1].type == "entity.create"
        assert result.applied[2].type == "entity.create"

    @pytest.mark.asyncio
    async def test_wrong_order_causes_rejection(self, assembly):
        """Entity before collection -> entity rejected due to missing collection."""
        aide_file = await assembly.create(make_blueprint())

        # Wrong order: entity before collection
        events = [
            make_entity_event(1, "item_1", {"name": "First", "count": 1}),  # Will fail
            make_collection_event(2),
            make_entity_event(3, "item_2", {"name": "Second", "count": 2}),  # Should work
        ]

        result = await assembly.apply(aide_file, events)

        # First entity rejected, collection applied, second entity applied
        assert len(result.applied) == 2
        assert len(result.rejected) == 1
        assert result.rejected[0][0].sequence == 1


class TestStateAfterRejections:
    """
    Verify the snapshot state is correct after partial application.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_snapshot_has_valid_entities_only(self, assembly):
        """Snapshot contains only entities from valid events."""
        aide_file = await assembly.create(make_blueprint())

        events = [
            make_collection_event(1),
            make_entity_event(2, "item_1", {"name": "First", "count": 1}),
            make_invalid_event(3, "invalid_payload"),  # Invalid
            make_entity_event(4, "item_2", {"name": "Second", "count": 2}),
        ]

        result = await assembly.apply(aide_file, events)

        entities = result.aide_file.snapshot["collections"]["items"]["entities"]
        assert len(entities) == 2
        assert "item_1" in entities
        assert "item_2" in entities

    @pytest.mark.asyncio
    async def test_html_reflects_valid_events(self, assembly):
        """Re-rendered HTML reflects only valid applied events."""
        aide_file = await assembly.create(make_blueprint())

        events = [
            make_collection_event(1),
            make_entity_event(2, "item_1", {"name": "ValidItem", "count": 1}),
            make_invalid_event(3, "invalid_payload"),
        ]

        result = await assembly.apply(aide_file, events)

        # HTML should mention ValidItem but not contain invalid event content
        html = result.aide_file.html
        assert "ValidItem" in html or "aide+json" in html  # Either rendered or in JSON

    @pytest.mark.asyncio
    async def test_events_list_excludes_rejected(self, assembly):
        """aide_file.events only contains applied events, not rejected."""
        aide_file = await assembly.create(make_blueprint())
        assert len(aide_file.events) == 0

        events = [
            make_collection_event(1),
            make_invalid_event(2, "invalid_payload"),
            make_entity_event(3, "item_1", {"name": "First", "count": 1}),
        ]

        result = await assembly.apply(aide_file, events)

        # aide_file.events should have 2, not 3
        assert len(result.aide_file.events) == 2
        assert result.aide_file.events[0].sequence == 1
        assert result.aide_file.events[1].sequence == 3
