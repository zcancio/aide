"""
AIde Assembly -- Compaction Tests (Category 7)

Create an aide with 600 events, compact to 50, verify snapshot unchanged,
event count is 50, HTML is smaller.

From the spec (aide_assembly_spec.md, "Testing Strategy"):
  "7. Compaction. Create an aide with 600 events, compact to 50, verify
   snapshot unchanged, event count is 50, HTML is smaller."

What compaction does:
  - Keeps the most recent N events
  - Snapshot already reflects all events, so old events are redundant
  - Re-renders HTML with reduced event log
  - Reduces file size

Reference: aide_assembly_spec.md (Event Log Compaction, Testing Strategy)
"""

import json

import pytest

from engine.kernel.assembly import AideAssembly, MemoryStorage
from engine.kernel.types import Blueprint, Event, now_iso

# ============================================================================
# Fixtures
# ============================================================================


def make_blueprint():
    return Blueprint(
        identity="A test aide for compaction.",
        voice="Minimal.",
    )


def make_many_events(count: int) -> list[Event]:
    """Generate a specified number of v3 events."""
    events = [
        Event(
            id="evt_001",
            sequence=1,
            timestamp=now_iso(),
            actor="user_test",
            source="test",
            type="schema.create",
            payload={
                "id": "item",
                "interface": "interface Item { name: string; index: number; }",
                "render_html": "<li>{{name}}</li>",
            },
        ),
    ]

    for i in range(2, count + 1):
        events.append(
            Event(
                id=f"evt_{i:03d}",
                sequence=i,
                timestamp=now_iso(),
                actor="user_test",
                source="test",
                type="entity.create",
                payload={
                    "id": f"item_{i}",
                    "_schema": "item",
                    "name": f"Item number {i}",
                    "index": i,
                },
            )
        )

    return events


# ============================================================================
# Basic compaction
# ============================================================================


class TestCompactionBasic:
    """
    Verify basic compaction behavior.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_compact_reduces_event_count(self, assembly):
        """Compaction reduces event count to keep_recent."""
        aide_file = await assembly.create(make_blueprint())
        events = make_many_events(600)
        await assembly.apply(aide_file, events)

        assert len(aide_file.events) == 600

        compacted = await assembly.compact(aide_file, keep_recent=50)

        assert len(compacted.events) == 50

    @pytest.mark.asyncio
    async def test_compact_keeps_recent_events(self, assembly):
        """Compaction keeps the MOST RECENT events, not oldest."""
        aide_file = await assembly.create(make_blueprint())
        events = make_many_events(100)
        await assembly.apply(aide_file, events)

        compacted = await assembly.compact(aide_file, keep_recent=10)

        # Should have events 91-100 (the last 10)
        sequences = [e.sequence for e in compacted.events]
        assert sequences == list(range(91, 101))

    @pytest.mark.asyncio
    async def test_compact_preserves_snapshot(self, assembly):
        """Compaction does not change the snapshot."""
        aide_file = await assembly.create(make_blueprint())
        events = make_many_events(100)
        await assembly.apply(aide_file, events)

        snapshot_before = json.dumps(aide_file.snapshot, sort_keys=True)

        await assembly.compact(aide_file, keep_recent=10)

        snapshot_after = json.dumps(aide_file.snapshot, sort_keys=True)

        assert snapshot_before == snapshot_after


class TestCompactionSizeReduction:
    """
    Verify compaction reduces HTML file size.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_compact_reduces_size(self, assembly):
        """Compaction reduces size_bytes."""
        aide_file = await assembly.create(make_blueprint())
        events = make_many_events(600)
        await assembly.apply(aide_file, events)

        size_before = aide_file.size_bytes

        await assembly.compact(aide_file, keep_recent=50)

        size_after = aide_file.size_bytes

        assert size_after < size_before

    @pytest.mark.asyncio
    async def test_compact_reduces_html_length(self, assembly):
        """Compaction reduces HTML string length."""
        aide_file = await assembly.create(make_blueprint())
        events = make_many_events(600)
        await assembly.apply(aide_file, events)

        html_len_before = len(aide_file.html)

        await assembly.compact(aide_file, keep_recent=50)

        html_len_after = len(aide_file.html)

        assert html_len_after < html_len_before


class TestCompactionNoOp:
    """
    Verify compaction is a no-op when not needed.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_compact_noop_when_under_threshold(self, assembly):
        """Compaction does nothing when events <= keep_recent."""
        aide_file = await assembly.create(make_blueprint())
        events = make_many_events(30)
        await assembly.apply(aide_file, events)

        events_before = len(aide_file.events)
        html_before = aide_file.html

        await assembly.compact(aide_file, keep_recent=50)

        assert len(aide_file.events) == events_before
        assert aide_file.html == html_before

    @pytest.mark.asyncio
    async def test_compact_noop_when_exactly_threshold(self, assembly):
        """Compaction does nothing when events == keep_recent."""
        aide_file = await assembly.create(make_blueprint())
        events = make_many_events(50)
        await assembly.apply(aide_file, events)

        events_before = len(aide_file.events)

        await assembly.compact(aide_file, keep_recent=50)

        assert len(aide_file.events) == events_before

    @pytest.mark.asyncio
    async def test_compact_empty_aide(self, assembly):
        """Compaction handles empty aide (no events)."""
        aide_file = await assembly.create(make_blueprint())

        # Should not raise
        await assembly.compact(aide_file, keep_recent=50)

        assert len(aide_file.events) == 0


class TestCompactionEntityPreservation:
    """
    Verify all entities are preserved after compaction.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_all_entities_preserved(self, assembly):
        """All entities remain in snapshot after compaction."""
        aide_file = await assembly.create(make_blueprint())
        events = make_many_events(600)  # Creates 599 entities
        await assembly.apply(aide_file, events)

        entities_before = len(aide_file.snapshot["entities"])

        await assembly.compact(aide_file, keep_recent=50)

        entities_after = len(aide_file.snapshot["entities"])

        assert entities_before == entities_after
        assert entities_after == 599  # 600 events - 1 schema.create

    @pytest.mark.asyncio
    async def test_entity_data_unchanged(self, assembly):
        """Entity field values are unchanged after compaction."""
        aide_file = await assembly.create(make_blueprint())
        events = make_many_events(100)
        await assembly.apply(aide_file, events)

        # Get specific entity before
        entity_50_before = aide_file.snapshot["entities"]["item_50"].copy()

        await assembly.compact(aide_file, keep_recent=10)

        entity_50_after = aide_file.snapshot["entities"]["item_50"]

        assert entity_50_after["name"] == entity_50_before["name"]
        assert entity_50_after["index"] == entity_50_before["index"]


class TestCompactionHTMLValidity:
    """
    Verify compacted HTML is still valid.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_compacted_html_valid(self, assembly):
        """Compacted HTML is valid and parseable."""
        from engine.kernel.assembly import parse_aide_html

        aide_file = await assembly.create(make_blueprint())
        events = make_many_events(100)
        await assembly.apply(aide_file, events)

        await assembly.compact(aide_file, keep_recent=20)

        parsed = parse_aide_html(aide_file.html)
        assert parsed.parse_errors == []

    @pytest.mark.asyncio
    async def test_compacted_html_has_correct_event_count(self, assembly):
        """Embedded events in compacted HTML matches keep_recent."""
        from engine.kernel.assembly import parse_aide_html

        aide_file = await assembly.create(make_blueprint())
        events = make_many_events(100)
        await assembly.apply(aide_file, events)

        await assembly.compact(aide_file, keep_recent=20)

        parsed = parse_aide_html(aide_file.html)
        assert len(parsed.events) == 20


class TestCompactionWithMixedEvents:
    """
    Verify compaction works with various event types.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_compact_with_updates_and_deletes(self, assembly):
        """Compaction handles updates and removes correctly."""
        aide_file = await assembly.create(make_blueprint())

        # Create schema and entities (v3)
        events = [
            Event(
                id="evt_001",
                sequence=1,
                timestamp=now_iso(),
                actor="test",
                source="test",
                type="schema.create",
                payload={"id": "item", "interface": "interface Item { name: string; }", "render_html": "<li>{{name}}</li>"},
            ),
            Event(
                id="evt_002",
                sequence=2,
                timestamp=now_iso(),
                actor="test",
                source="test",
                type="entity.create",
                payload={"id": "item_1", "_schema": "item", "name": "Original"},
            ),
        ]

        # Add many updates (entity.update uses ref and fields format)
        for i in range(3, 103):
            events.append(
                Event(
                    id=f"evt_{i:03d}",
                    sequence=i,
                    timestamp=now_iso(),
                    actor="test",
                    source="test",
                    type="entity.update",
                    payload={"id": "item_1", "name": f"Updated {i}"},
                )
            )

        await assembly.apply(aide_file, events)

        # Snapshot should have final update
        assert aide_file.snapshot["entities"]["item_1"]["name"] == "Updated 102"

        # Compact
        await assembly.compact(aide_file, keep_recent=10)

        # Snapshot still has final update
        assert aide_file.snapshot["entities"]["item_1"]["name"] == "Updated 102"
        assert len(aide_file.events) == 10


class TestCompactionRoundTrip:
    """
    Verify compacted aide can be saved and loaded correctly.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_compact_save_load(self, assembly, storage):
        """Compacted aide survives save/load cycle."""
        aide_file = await assembly.create(make_blueprint())
        events = make_many_events(100)
        await assembly.apply(aide_file, events)

        await assembly.compact(aide_file, keep_recent=20)
        await assembly.save(aide_file)

        loaded = await assembly.load(aide_file.aide_id)

        assert len(loaded.events) == 20
        # All entities still present
        assert len(loaded.snapshot["entities"]) == 99
