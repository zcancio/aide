"""
AIde Assembly -- Apply with Rejections Tests (Category 3) — v3 Primitives

Send 5 events where #3 is invalid. Verify #1, #2, #4, #5 applied, #3 rejected.

v3 changes:
  - schema.create replaces collection.create
  - entity.create uses path-based id (no 'collection' field)
  - Snapshot has 'entities' not 'collections'

Reference: aide_assembly_spec.md (apply operation, Testing Strategy)
"""

import pytest

from engine.kernel.assembly import AideAssembly, MemoryStorage
from engine.kernel.types import Blueprint, Event, now_iso


def make_blueprint():
    return Blueprint(identity="Test aide for rejection testing.", voice="Direct.")


def make_schema_event(seq: int) -> Event:
    """v3: schema.create instead of collection.create."""
    return Event(
        id=f"evt_{seq:03d}",
        sequence=seq,
        timestamp=now_iso(),
        actor="user_test",
        source="test",
        type="schema.create",
        payload={
            "id": "item",
            "interface": "interface Item { name: string; count: number; }",
            "render_html": "<li>{{name}} ({{count}})</li>",
        },
    )


def make_entity_event(seq: int, entity_id: str, fields: dict) -> Event:
    """v3: entity.create with path-based id."""
    payload = {"id": entity_id, "_schema": "item"}
    payload.update(fields)
    return Event(
        id=f"evt_{seq:03d}",
        sequence=seq,
        timestamp=now_iso(),
        actor="user_test",
        source="test",
        type="entity.create",
        payload=payload,
    )


def make_invalid_event(seq: int, error_type: str) -> Event:
    """Create an event that will be rejected."""
    if error_type == "missing_schema":
        # Entity create for non-existent schema
        return Event(
            id=f"evt_{seq:03d}",
            sequence=seq,
            timestamp=now_iso(),
            actor="user_test",
            source="test",
            type="entity.create",
            payload={"id": "x", "_schema": "nonexistent", "name": "Test"},
        )
    elif error_type == "invalid_payload":
        # schema.create without required 'id' field
        return Event(
            id=f"evt_{seq:03d}",
            sequence=seq,
            timestamp=now_iso(),
            actor="user_test",
            source="test",
            type="schema.create",
            payload={"interface": "interface Foo { name: string; }"},  # Missing 'id'
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
            payload={"id": "item_1", "_schema": "item", "name": "Dupe"},
        )
    elif error_type == "unknown_type":
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


class TestPartialApplication:
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
            make_schema_event(1),                                          # Valid
            make_entity_event(2, "item_1", {"name": "First", "count": 1}), # Valid
            make_invalid_event(3, "invalid_payload"),                       # Invalid
            make_entity_event(4, "item_2", {"name": "Second", "count": 2}),# Valid
            make_entity_event(5, "item_3", {"name": "Third", "count": 3}), # Valid
        ]

        result = await assembly.apply(aide_file, events)

        assert len(result.applied) == 4
        assert result.applied[0].sequence == 1
        assert result.applied[1].sequence == 2
        assert result.applied[2].sequence == 4
        assert result.applied[3].sequence == 5

        assert len(result.rejected) == 1
        rejected_event, reason = result.rejected[0]
        assert rejected_event.sequence == 3

    @pytest.mark.asyncio
    async def test_first_event_invalid(self, assembly):
        """First event invalid -> skipped, rest applied if valid."""
        aide_file = await assembly.create(make_blueprint())

        events = [
            make_invalid_event(1, "invalid_payload"),  # Invalid
            make_schema_event(2),                       # Valid
            make_entity_event(3, "item_1", {"name": "First", "count": 1}),
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
            make_schema_event(1),
            make_entity_event(2, "item_1", {"name": "First", "count": 1}),
            make_invalid_event(3, "invalid_payload"),
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
        assert str(aide_file.snapshot) == original_snapshot_str

    @pytest.mark.asyncio
    async def test_alternating_valid_invalid(self, assembly):
        """Alternating valid/invalid -> valid ones applied."""
        aide_file = await assembly.create(make_blueprint())

        events = [
            make_schema_event(1),                                          # Valid
            make_invalid_event(2, "invalid_payload"),                       # Invalid
            make_entity_event(3, "item_1", {"name": "First", "count": 1}), # Valid
            make_invalid_event(4, "invalid_payload"),                       # Invalid
            make_entity_event(5, "item_2", {"name": "Second", "count": 2}),# Valid
        ]

        result = await assembly.apply(aide_file, events)

        assert len(result.applied) == 3
        assert len(result.rejected) == 2


class TestRejectionReasons:
    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_missing_schema_reason(self, assembly):
        """Entity for non-existent schema has descriptive rejection reason."""
        aide_file = await assembly.create(make_blueprint())

        events = [make_invalid_event(1, "missing_schema")]
        result = await assembly.apply(aide_file, events)

        assert len(result.rejected) == 1
        _, reason = result.rejected[0]
        assert len(reason) > 0

    @pytest.mark.asyncio
    async def test_invalid_payload_reason(self, assembly):
        """Invalid payload has descriptive rejection reason."""
        aide_file = await assembly.create(make_blueprint())

        events = [make_invalid_event(1, "invalid_payload")]
        result = await assembly.apply(aide_file, events)

        assert len(result.rejected) == 1
        _, reason = result.rejected[0]
        assert len(reason) > 0

    @pytest.mark.asyncio
    async def test_duplicate_entity_reason(self, assembly):
        """Duplicate entity has descriptive rejection reason."""
        aide_file = await assembly.create(make_blueprint())

        events = [
            make_schema_event(1),
            make_entity_event(2, "item_1", {"name": "First", "count": 1}),
            make_invalid_event(3, "duplicate_entity"),  # Same ID as item_1
        ]
        result = await assembly.apply(aide_file, events)

        assert len(result.rejected) == 1
        _, reason = result.rejected[0]
        assert "exist" in reason.lower() or "duplicate" in reason.lower() or "already" in reason.lower()

    @pytest.mark.asyncio
    async def test_unknown_type_reason(self, assembly):
        """Unknown primitive type has descriptive rejection reason."""
        aide_file = await assembly.create(make_blueprint())

        events = [make_invalid_event(1, "unknown_type")]
        result = await assembly.apply(aide_file, events)

        assert len(result.rejected) == 1
        _, reason = result.rejected[0]
        assert len(reason) > 0


class TestOrderPreservation:
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

        events = [
            make_schema_event(1),
            make_entity_event(2, "item_1", {"name": "First", "count": 1}),
            make_entity_event(3, "item_2", {"name": "Second", "count": 2}),
        ]

        result = await assembly.apply(aide_file, events)

        assert len(result.applied) == 3
        assert result.applied[0].type == "schema.create"
        assert result.applied[1].type == "entity.create"
        assert result.applied[2].type == "entity.create"

    @pytest.mark.asyncio
    async def test_wrong_order_entity_before_schema(self, assembly):
        """Entity before schema -> entity rejected if schema required."""
        aide_file = await assembly.create(make_blueprint())

        # Wrong order: entity before schema (entity references nonexistent schema)
        events = [
            make_invalid_event(1, "missing_schema"),   # Will fail (schema not created)
            make_schema_event(2),                       # Schema created
            make_entity_event(3, "item_2", {"name": "Second", "count": 2}),  # Should work
        ]

        result = await assembly.apply(aide_file, events)

        # First entity rejected, schema applied, second entity applied
        assert len(result.applied) == 2
        assert len(result.rejected) == 1
        assert result.rejected[0][0].sequence == 1


class TestStateAfterRejections:
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
            make_schema_event(1),
            make_entity_event(2, "item_1", {"name": "First", "count": 1}),
            make_invalid_event(3, "invalid_payload"),  # Invalid
            make_entity_event(4, "item_2", {"name": "Second", "count": 2}),
        ]

        result = await assembly.apply(aide_file, events)

        # v3: entities at top level
        entities = result.aide_file.snapshot["entities"]
        assert "item_1" in entities
        assert "item_2" in entities

    @pytest.mark.asyncio
    async def test_html_reflects_valid_events(self, assembly):
        """Re-rendered HTML reflects only valid applied events."""
        aide_file = await assembly.create(make_blueprint())

        events = [
            make_schema_event(1),
            make_entity_event(2, "item_1", {"name": "ValidItem", "count": 1}),
            make_invalid_event(3, "invalid_payload"),
        ]

        result = await assembly.apply(aide_file, events)

        html = result.aide_file.html
        assert "ValidItem" in html or "aide+json" in html

    @pytest.mark.asyncio
    async def test_events_list_excludes_rejected(self, assembly):
        """aide_file.events only contains applied events, not rejected."""
        aide_file = await assembly.create(make_blueprint())
        assert len(aide_file.events) == 0

        events = [
            make_schema_event(1),
            make_invalid_event(2, "invalid_payload"),
            make_entity_event(3, "item_1", {"name": "First", "count": 1}),
        ]

        result = await assembly.apply(aide_file, events)

        # aide_file.events should have 2, not 3
        assert len(result.aide_file.events) == 2
        assert result.aide_file.events[0].sequence == 1
        assert result.aide_file.events[1].sequence == 3
