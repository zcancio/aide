"""
AIde Assembly -- Fork Tests (Category 5)

Create an aide with 20 events, fork it, verify the fork has the same
snapshot but empty events and a new aide_id.

From the spec (aide_assembly_spec.md, "Testing Strategy"):
  "5. Fork. Create an aide with 20 events, fork it, verify the fork has
   the same snapshot but empty events and a new aide_id."

What carries over: schema, entities, blocks, views, styles, blueprint
What doesn't: events, annotations, sequence metadata, user identity

Reference: aide_assembly_spec.md (fork operation, Testing Strategy)
"""

import pytest

from engine.kernel.assembly import AideAssembly, MemoryStorage
from engine.kernel.types import Blueprint, Event, now_iso

# ============================================================================
# Fixtures
# ============================================================================


def make_blueprint():
    return Blueprint(
        identity="A poker league tracker.",
        voice="Casual but accurate.",
        prompt="You track a poker league.",
    )


def make_twenty_events() -> list[Event]:
    """Create 20 events that build a small aide."""
    events = []
    seq = 0

    # 1. Create collection
    seq += 1
    events.append(Event(
        id=f"evt_{seq:03d}",
        sequence=seq,
        timestamp=now_iso(),
        actor="user_test",
        source="test",
        type="collection.create",
        payload={"id": "players", "schema": {"name": "string", "wins": "int", "active": "bool"}},
    ))

    # 2-11. Add 10 players
    for i in range(10):
        seq += 1
        events.append(Event(
            id=f"evt_{seq:03d}",
            sequence=seq,
            timestamp=now_iso(),
            actor="user_test",
            source="test",
            type="entity.create",
            payload={
                "collection": "players",
                "id": f"player_{i+1}",
                "fields": {"name": f"Player {i+1}", "wins": i, "active": True},
            },
        ))

    # 12-16. Update some players
    for i in range(5):
        seq += 1
        events.append(Event(
            id=f"evt_{seq:03d}",
            sequence=seq,
            timestamp=now_iso(),
            actor="user_test",
            source="test",
            type="field.update",
            payload={
                "collection": "players",
                "entity": f"player_{i+1}",
                "field": "wins",
                "value": (i + 1) * 10,
            },
        ))

    # 17. Update title
    seq += 1
    events.append(Event(
        id=f"evt_{seq:03d}",
        sequence=seq,
        timestamp=now_iso(),
        actor="user_test",
        source="test",
        type="meta.update",
        payload={"title": "Thursday Night Poker"},
    ))

    # 18. Create view
    seq += 1
    events.append(Event(
        id=f"evt_{seq:03d}",
        sequence=seq,
        timestamp=now_iso(),
        actor="user_test",
        source="test",
        type="view.create",
        payload={
            "id": "players_view",
            "type": "table",
            "source": "players",
            "config": {"show_fields": ["name", "wins", "active"]},
        },
    ))

    # 19. Create heading block
    seq += 1
    events.append(Event(
        id=f"evt_{seq:03d}",
        sequence=seq,
        timestamp=now_iso(),
        actor="user_test",
        source="test",
        type="block.set",
        payload={
            "id": "block_title",
            "type": "heading",
            "parent": "block_root",
            "props": {"level": 1, "content": "Thursday Night Poker"},
        },
    ))

    # 20. Create collection view block
    seq += 1
    events.append(Event(
        id=f"evt_{seq:03d}",
        sequence=seq,
        timestamp=now_iso(),
        actor="user_test",
        source="test",
        type="block.set",
        payload={
            "id": "block_players",
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "players", "view": "players_view"},
        },
    ))

    assert len(events) == 20
    return events


# ============================================================================
# Fork basic behavior
# ============================================================================


class TestForkBasic:
    """
    Verify fork produces a new aide with same state but different identity.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_fork_creates_new_id(self, assembly, storage):
        """Fork produces a new, different aide_id."""
        # Create and save original
        original = await assembly.create(make_blueprint())
        events = make_twenty_events()
        await assembly.apply(original, events)
        await assembly.save(original)

        # Fork
        forked = await assembly.fork(original.aide_id)

        assert forked.aide_id != original.aide_id
        assert len(forked.aide_id) > 0

    @pytest.mark.asyncio
    async def test_fork_clears_events(self, assembly, storage):
        """Forked aide has empty events list."""
        original = await assembly.create(make_blueprint())
        events = make_twenty_events()
        await assembly.apply(original, events)
        await assembly.save(original)

        forked = await assembly.fork(original.aide_id)

        assert len(forked.events) == 0

    @pytest.mark.asyncio
    async def test_fork_resets_sequence(self, assembly, storage):
        """Forked aide has last_sequence=0."""
        original = await assembly.create(make_blueprint())
        events = make_twenty_events()
        await assembly.apply(original, events)
        await assembly.save(original)

        forked = await assembly.fork(original.aide_id)

        assert forked.last_sequence == 0

    @pytest.mark.asyncio
    async def test_fork_loaded_from_new(self, assembly, storage):
        """Forked aide has loaded_from='new'."""
        original = await assembly.create(make_blueprint())
        events = make_twenty_events()
        await assembly.apply(original, events)
        await assembly.save(original)

        forked = await assembly.fork(original.aide_id)

        assert forked.loaded_from == "new"


class TestForkSnapshotPreservation:
    """
    Verify fork preserves the snapshot data.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_fork_preserves_collections(self, assembly, storage):
        """Forked aide has same collections."""
        original = await assembly.create(make_blueprint())
        events = make_twenty_events()
        await assembly.apply(original, events)
        await assembly.save(original)

        forked = await assembly.fork(original.aide_id)

        assert "players" in forked.snapshot["collections"]
        assert forked.snapshot["collections"]["players"]["schema"] == original.snapshot["collections"]["players"]["schema"]

    @pytest.mark.asyncio
    async def test_fork_preserves_entities(self, assembly, storage):
        """Forked aide has same entities."""
        original = await assembly.create(make_blueprint())
        events = make_twenty_events()
        await assembly.apply(original, events)
        await assembly.save(original)

        forked = await assembly.fork(original.aide_id)

        orig_entities = original.snapshot["collections"]["players"]["entities"]
        fork_entities = forked.snapshot["collections"]["players"]["entities"]

        assert len(fork_entities) == len(orig_entities)
        for eid in orig_entities:
            assert eid in fork_entities
            assert fork_entities[eid]["name"] == orig_entities[eid]["name"]
            assert fork_entities[eid]["wins"] == orig_entities[eid]["wins"]

    @pytest.mark.asyncio
    async def test_fork_preserves_views(self, assembly, storage):
        """Forked aide has same views."""
        original = await assembly.create(make_blueprint())
        events = make_twenty_events()
        await assembly.apply(original, events)
        await assembly.save(original)

        forked = await assembly.fork(original.aide_id)

        assert "players_view" in forked.snapshot["views"]
        assert forked.snapshot["views"]["players_view"]["type"] == "table"

    @pytest.mark.asyncio
    async def test_fork_preserves_blocks(self, assembly, storage):
        """Forked aide has same blocks."""
        original = await assembly.create(make_blueprint())
        events = make_twenty_events()
        await assembly.apply(original, events)
        await assembly.save(original)

        forked = await assembly.fork(original.aide_id)

        assert "block_title" in forked.snapshot["blocks"]
        assert "block_players" in forked.snapshot["blocks"]

    @pytest.mark.asyncio
    async def test_fork_preserves_styles(self, assembly, storage):
        """Forked aide has same styles."""
        original = await assembly.create(make_blueprint())
        events = make_twenty_events()

        # Add a style event (style.set takes key-value pairs directly)
        events.append(Event(
            id="evt_021",
            sequence=21,
            timestamp=now_iso(),
            actor="user_test",
            source="test",
            type="style.set",
            payload={"primary_color": "#ff5500"},
        ))

        await assembly.apply(original, events)
        await assembly.save(original)

        forked = await assembly.fork(original.aide_id)

        assert forked.snapshot["styles"]["primary_color"] == "#ff5500"


class TestForkCleanup:
    """
    Verify fork clears sequence metadata and annotations.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_fork_clears_entity_sequence_metadata(self, assembly, storage):
        """Forked entities have no _created_seq, _updated_seq, _removed_seq."""
        original = await assembly.create(make_blueprint())
        events = make_twenty_events()
        await assembly.apply(original, events)
        await assembly.save(original)

        forked = await assembly.fork(original.aide_id)

        for entity in forked.snapshot["collections"]["players"]["entities"].values():
            assert "_created_seq" not in entity
            assert "_updated_seq" not in entity
            assert "_removed_seq" not in entity

    @pytest.mark.asyncio
    async def test_fork_clears_annotations(self, assembly, storage):
        """Forked aide has empty annotations."""
        original = await assembly.create(make_blueprint())
        events = make_twenty_events()
        await assembly.apply(original, events)
        await assembly.save(original)

        forked = await assembly.fork(original.aide_id)

        assert forked.snapshot["annotations"] == []

    @pytest.mark.asyncio
    async def test_fork_updates_title(self, assembly, storage):
        """Forked aide title is prefixed with 'Copy of'."""
        original = await assembly.create(make_blueprint())
        events = make_twenty_events()
        await assembly.apply(original, events)
        await assembly.save(original)

        forked = await assembly.fork(original.aide_id)

        assert forked.snapshot["meta"]["title"].startswith("Copy of")
        assert "Thursday Night Poker" in forked.snapshot["meta"]["title"]


class TestForkBlueprint:
    """
    Verify fork preserves the blueprint.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_fork_preserves_blueprint_identity(self, assembly, storage):
        """Forked aide has same blueprint identity."""
        bp = make_blueprint()
        original = await assembly.create(bp)
        events = make_twenty_events()
        await assembly.apply(original, events)
        await assembly.save(original)

        forked = await assembly.fork(original.aide_id)

        assert forked.blueprint.identity == bp.identity

    @pytest.mark.asyncio
    async def test_fork_preserves_blueprint_voice(self, assembly, storage):
        """Forked aide has same blueprint voice."""
        bp = make_blueprint()
        original = await assembly.create(bp)
        events = make_twenty_events()
        await assembly.apply(original, events)
        await assembly.save(original)

        forked = await assembly.fork(original.aide_id)

        assert forked.blueprint.voice == bp.voice

    @pytest.mark.asyncio
    async def test_fork_blueprint_is_deep_copy(self, assembly, storage):
        """Forked blueprint is independent of original."""
        bp = make_blueprint()
        original = await assembly.create(bp)
        events = make_twenty_events()
        await assembly.apply(original, events)
        await assembly.save(original)

        forked = await assembly.fork(original.aide_id)

        # Mutating forked blueprint shouldn't affect original
        # (Blueprint is a dataclass, so just verify they're equal but independent)
        assert forked.blueprint is not original.blueprint


class TestForkIndependence:
    """
    Verify forked aide is independent of original.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_fork_snapshot_is_deep_copy(self, assembly, storage):
        """Mutations to forked snapshot don't affect original."""
        original = await assembly.create(make_blueprint())
        events = make_twenty_events()
        await assembly.apply(original, events)
        await assembly.save(original)

        forked = await assembly.fork(original.aide_id)

        # Mutate forked snapshot
        forked.snapshot["collections"]["players"]["entities"]["player_1"]["wins"] = 9999

        # Reload original
        reloaded = await assembly.load(original.aide_id)

        # Original should be unchanged
        assert reloaded.snapshot["collections"]["players"]["entities"]["player_1"]["wins"] != 9999

    @pytest.mark.asyncio
    async def test_fork_can_be_saved_independently(self, assembly, storage):
        """Forked aide can be saved with its own ID."""
        original = await assembly.create(make_blueprint())
        events = make_twenty_events()
        await assembly.apply(original, events)
        await assembly.save(original)

        forked = await assembly.fork(original.aide_id)
        await assembly.save(forked)

        # Both should exist in storage
        assert original.aide_id in storage.workspace
        assert forked.aide_id in storage.workspace
        assert original.aide_id != forked.aide_id


class TestForkDoesNotSave:
    """
    Verify fork() does NOT automatically save the forked aide.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_fork_does_not_persist(self, assembly, storage):
        """fork() does not write forked aide to storage."""
        original = await assembly.create(make_blueprint())
        events = make_twenty_events()
        await assembly.apply(original, events)
        await assembly.save(original)

        forked = await assembly.fork(original.aide_id)

        # Forked aide should NOT be in storage yet
        assert forked.aide_id not in storage.workspace

        # Only original should be in storage
        assert len(storage.workspace) == 1
        assert original.aide_id in storage.workspace
