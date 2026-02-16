"""
AIde Assembly -- Round-Trip Tests (Category 1)

Create -> apply 10 events -> save -> load -> verify snapshot matches.
The most important test category.

From the spec (aide_assembly_spec.md, "Testing Strategy"):
  "1. Round-trip. Create -> apply 10 events -> save -> load -> verify
   snapshot matches. The most important test."

This verifies:
  - Events are correctly applied to the snapshot
  - The full aide file (snapshot + events + blueprint + HTML) persists correctly
  - Parsing extracts identical data to what was saved
  - The assembly layer coordinates reducer + renderer + storage correctly

Reference: aide_assembly_spec.md (Operations, Testing Strategy)
"""

import pytest

from engine.kernel.assembly import AideAssembly, MemoryStorage
from engine.kernel.types import Blueprint, Event, now_iso

# ============================================================================
# Fixtures
# ============================================================================


def make_blueprint():
    return Blueprint(
        identity="A family grocery list. Tracks what we need to buy.",
        voice="No first person. Terse confirmations.",
        prompt="You are maintaining a shared grocery list.",
    )


def make_collection_create_event(seq: int, coll_id: str, schema: dict) -> Event:
    return Event(
        id=f"evt_{seq:03d}",
        sequence=seq,
        timestamp=now_iso(),
        actor="user_test",
        source="test",
        type="collection.create",
        payload={"id": coll_id, "schema": schema},
    )


def make_entity_create_event(seq: int, coll_id: str, entity_id: str, fields: dict) -> Event:
    return Event(
        id=f"evt_{seq:03d}",
        sequence=seq,
        timestamp=now_iso(),
        actor="user_test",
        source="test",
        type="entity.create",
        payload={"collection": coll_id, "id": entity_id, "fields": fields},
    )


def make_meta_update_event(seq: int, field: str, value: str) -> Event:
    return Event(
        id=f"evt_{seq:03d}",
        sequence=seq,
        timestamp=now_iso(),
        actor="user_test",
        source="test",
        type="meta.update",
        payload={field: value},  # meta.update takes key-value pairs directly
    )


def make_ten_events() -> list[Event]:
    """Create 10 events that build a simple grocery list."""
    return [
        # 1. Create collection
        make_collection_create_event(1, "groceries", {
            "name": "string",
            "quantity": "int",
            "urgent": "bool",
        }),
        # 2-9. Add 8 items
        make_entity_create_event(2, "groceries", "item_1", {"name": "Milk", "quantity": 2, "urgent": False}),
        make_entity_create_event(3, "groceries", "item_2", {"name": "Eggs", "quantity": 12, "urgent": True}),
        make_entity_create_event(4, "groceries", "item_3", {"name": "Bread", "quantity": 1, "urgent": False}),
        make_entity_create_event(5, "groceries", "item_4", {"name": "Butter", "quantity": 1, "urgent": False}),
        make_entity_create_event(6, "groceries", "item_5", {"name": "Cheese", "quantity": 1, "urgent": True}),
        make_entity_create_event(7, "groceries", "item_6", {"name": "Apples", "quantity": 6, "urgent": False}),
        make_entity_create_event(8, "groceries", "item_7", {"name": "Bananas", "quantity": 4, "urgent": False}),
        make_entity_create_event(9, "groceries", "item_8", {"name": "Chicken", "quantity": 2, "urgent": True}),
        # 10. Update title
        make_meta_update_event(10, "title", "Family Grocery List"),
    ]


# ============================================================================
# Round-trip: create -> apply -> save -> load
# ============================================================================


class TestBasicRoundTrip:
    """
    The fundamental round-trip test: create, apply events, save, load, verify.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_ten_events_round_trip(self, assembly, storage):
        """Create -> apply 10 events -> save -> load -> snapshot matches."""
        # 1. Create
        blueprint = make_blueprint()
        aide_file = await assembly.create(blueprint)
        original_id = aide_file.aide_id

        # 2. Apply 10 events
        events = make_ten_events()
        result = await assembly.apply(aide_file, events)

        assert len(result.applied) == 10
        assert len(result.rejected) == 0
        snapshot_before = result.aide_file.snapshot

        # 3. Save
        await assembly.save(result.aide_file)
        assert original_id in storage.workspace

        # 4. Load
        loaded = await assembly.load(original_id)

        # 5. Verify snapshot matches
        assert loaded.snapshot == snapshot_before
        assert loaded.aide_id == original_id
        assert len(loaded.events) == 10
        assert loaded.last_sequence == 10

    @pytest.mark.asyncio
    async def test_blueprint_preserved(self, assembly, storage):
        """Blueprint is preserved across save/load cycle."""
        blueprint = make_blueprint()
        aide_file = await assembly.create(blueprint)

        events = make_ten_events()
        await assembly.apply(aide_file, events)
        await assembly.save(aide_file)

        loaded = await assembly.load(aide_file.aide_id)

        assert loaded.blueprint.identity == blueprint.identity
        assert loaded.blueprint.voice == blueprint.voice
        assert loaded.blueprint.prompt == blueprint.prompt

    @pytest.mark.asyncio
    async def test_events_preserved(self, assembly, storage):
        """All events are preserved across save/load cycle."""
        blueprint = make_blueprint()
        aide_file = await assembly.create(blueprint)

        events = make_ten_events()
        await assembly.apply(aide_file, events)
        await assembly.save(aide_file)

        loaded = await assembly.load(aide_file.aide_id)

        assert len(loaded.events) == 10
        for i, event in enumerate(loaded.events):
            assert event.type == events[i].type
            assert event.sequence == events[i].sequence

    @pytest.mark.asyncio
    async def test_html_valid_after_round_trip(self, assembly, storage):
        """HTML is a valid document after save/load."""
        blueprint = make_blueprint()
        aide_file = await assembly.create(blueprint)

        events = make_ten_events()
        await assembly.apply(aide_file, events)
        await assembly.save(aide_file)

        loaded = await assembly.load(aide_file.aide_id)

        assert loaded.html.startswith("<!DOCTYPE html>")
        assert "<html" in loaded.html
        assert "</html>" in loaded.html
        assert loaded.size_bytes > 0


class TestSnapshotIntegrity:
    """
    Verify the snapshot data is fully preserved across round trips.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_collections_preserved(self, assembly, storage):
        """Collections are identical before and after round trip."""
        aide_file = await assembly.create(make_blueprint())
        events = make_ten_events()
        await assembly.apply(aide_file, events)
        await assembly.save(aide_file)

        loaded = await assembly.load(aide_file.aide_id)

        assert "groceries" in loaded.snapshot["collections"]
        coll = loaded.snapshot["collections"]["groceries"]
        assert coll["id"] == "groceries"
        assert "name" in coll["schema"]
        assert "quantity" in coll["schema"]
        assert "urgent" in coll["schema"]

    @pytest.mark.asyncio
    async def test_entities_preserved(self, assembly, storage):
        """All 8 entities are present after round trip."""
        aide_file = await assembly.create(make_blueprint())
        events = make_ten_events()
        await assembly.apply(aide_file, events)
        await assembly.save(aide_file)

        loaded = await assembly.load(aide_file.aide_id)

        entities = loaded.snapshot["collections"]["groceries"]["entities"]
        assert len(entities) == 8

        # Check specific entity
        milk = entities["item_1"]
        assert milk["name"] == "Milk"
        assert milk["quantity"] == 2
        assert milk["urgent"] is False

    @pytest.mark.asyncio
    async def test_meta_preserved(self, assembly, storage):
        """Meta fields (title) are preserved."""
        aide_file = await assembly.create(make_blueprint())
        events = make_ten_events()
        await assembly.apply(aide_file, events)
        await assembly.save(aide_file)

        loaded = await assembly.load(aide_file.aide_id)

        assert loaded.snapshot["meta"]["title"] == "Family Grocery List"


class TestMultipleRoundTrips:
    """
    Verify multiple save/load cycles don't corrupt data.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_five_round_trips(self, assembly, storage):
        """Five consecutive save/load cycles produce identical snapshots."""
        aide_file = await assembly.create(make_blueprint())
        events = make_ten_events()
        await assembly.apply(aide_file, events)

        import json

        first_snapshot = json.dumps(aide_file.snapshot, sort_keys=True)

        for _ in range(5):
            await assembly.save(aide_file)
            aide_file = await assembly.load(aide_file.aide_id)

        final_snapshot = json.dumps(aide_file.snapshot, sort_keys=True)
        assert first_snapshot == final_snapshot

    @pytest.mark.asyncio
    async def test_incremental_apply_round_trips(self, assembly, storage):
        """Apply events in batches with save/load between each."""
        aide_file = await assembly.create(make_blueprint())

        # First batch: create collection + 2 entities
        batch1 = make_ten_events()[:3]
        await assembly.apply(aide_file, batch1)
        await assembly.save(aide_file)

        # Load and apply second batch
        aide_file = await assembly.load(aide_file.aide_id)
        batch2 = make_ten_events()[3:6]
        # Clear sequences to let assembly assign new ones
        for e in batch2:
            e.sequence = 0
        await assembly.apply(aide_file, batch2)
        await assembly.save(aide_file)

        # Load and apply third batch
        aide_file = await assembly.load(aide_file.aide_id)
        batch3 = make_ten_events()[6:10]
        for e in batch3:
            e.sequence = 0
        await assembly.apply(aide_file, batch3)
        await assembly.save(aide_file)

        # Final load and verify
        final = await assembly.load(aide_file.aide_id)
        entities = final.snapshot["collections"]["groceries"]["entities"]
        assert len(entities) == 8
        assert final.snapshot["meta"]["title"] == "Family Grocery List"


class TestLastSequenceTracking:
    """
    Verify last_sequence is tracked correctly across operations.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_last_sequence_after_create(self, assembly):
        """New aide starts with last_sequence=0."""
        aide_file = await assembly.create(make_blueprint())
        assert aide_file.last_sequence == 0

    @pytest.mark.asyncio
    async def test_last_sequence_after_apply(self, assembly):
        """last_sequence tracks auto-assigned sequences.

        NOTE: Current implementation only tracks last_sequence for auto-assigned
        sequences (when event.sequence == 0). Events with preset sequences don't
        update last_sequence during apply - that's computed during load().
        """
        aide_file = await assembly.create(make_blueprint())

        # Use auto-assigned sequences (sequence=0)
        events = [
            Event(id="", sequence=0, timestamp=now_iso(), actor="test", source="test",
                  type="collection.create", payload={"id": "items", "schema": {"name": "string"}}),
        ]
        for i in range(9):
            events.append(Event(
                id="", sequence=0, timestamp=now_iso(), actor="test", source="test",
                type="entity.create",
                payload={"collection": "items", "id": f"item_{i}", "fields": {"name": f"Item {i}"}},
            ))

        await assembly.apply(aide_file, events)

        assert aide_file.last_sequence == 10

    @pytest.mark.asyncio
    async def test_last_sequence_after_load(self, assembly, storage):
        """last_sequence is restored from loaded events."""
        aide_file = await assembly.create(make_blueprint())
        events = make_ten_events()
        await assembly.apply(aide_file, events)
        await assembly.save(aide_file)

        loaded = await assembly.load(aide_file.aide_id)
        assert loaded.last_sequence == 10

    @pytest.mark.asyncio
    async def test_sequence_continuity(self, assembly, storage):
        """Sequences continue from where they left off after load."""
        aide_file = await assembly.create(make_blueprint())
        events = make_ten_events()[:5]
        await assembly.apply(aide_file, events)
        await assembly.save(aide_file)

        loaded = await assembly.load(aide_file.aide_id)

        # Apply more events without explicit sequences
        more_events = [
            Event(
                id="",
                sequence=0,  # Let assembly assign
                timestamp=now_iso(),
                actor="user_test",
                source="test",
                type="entity.create",
                payload={
                    "collection": "groceries",
                    "id": "item_new",
                    "fields": {"name": "Orange Juice", "quantity": 1, "urgent": False},
                },
            ),
        ]
        result = await assembly.apply(loaded, more_events)

        # New event should get sequence 6
        assert result.applied[0].sequence == 6
        assert loaded.last_sequence == 6
