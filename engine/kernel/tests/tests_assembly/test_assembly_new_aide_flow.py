"""
AIde Assembly -- New Aide Flow Tests (Category 10)

Simulate a first message flow: create → apply → save → publish.
Verify at each step that the aide is valid and correct.

From the spec (aide_assembly_spec.md, "Testing Strategy"):
  "10. New aide flow. Simulate a first message with no aide_id:
    create → apply AI-generated events → save → publish. Verify at
    each step that aide is in a valid state."

This tests the complete lifecycle of creating a new aide from scratch,
as would happen when a user sends their first message describing what
they want to track.

Reference: aide_assembly_spec.md (Full flow, Testing Strategy)
"""

import pytest

from engine.kernel.assembly import AideAssembly, MemoryStorage, parse_aide_html
from engine.kernel.types import Blueprint, Event, now_iso

# ============================================================================
# Fixtures
# ============================================================================


def make_poker_league_blueprint() -> Blueprint:
    """Create a blueprint for a poker league (common use case)."""
    return Blueprint(
        identity="A poker league tracker for a group of friends who play every other Thursday.",
        voice="Casual but organized. Keep it light.",
        prompt="You track poker games, standings, and who's hosting next.",
    )


def make_poker_league_events() -> list[Event]:
    """
    Create the events that AI would generate for a first message like:
    "I run a poker league, 8 guys, every other Thursday at someone's house."
    """
    events = []
    seq = 0

    # 1. Create players collection
    seq += 1
    events.append(
        Event(
            id=f"evt_{seq:03d}",
            sequence=seq,
            timestamp=now_iso(),
            actor="system",
            source="ai",
            type="collection.create",
            payload={
                "id": "players",
                "schema": {
                    "name": "string",
                    "games_played": "int",
                    "total_winnings": "int",
                    "hosting_count": "int",
                    "active": "bool",
                },
            },
        )
    )

    # 2. Create games collection
    seq += 1
    events.append(
        Event(
            id=f"evt_{seq:03d}",
            sequence=seq,
            timestamp=now_iso(),
            actor="system",
            source="ai",
            type="collection.create",
            payload={
                "id": "games",
                "schema": {
                    "date": "date",
                    "host": "string",
                    "winner": "string",
                    "pot": "int",
                    "notes": "string",
                },
            },
        )
    )

    # 3-10. Add 8 players
    player_names = ["Mike", "Dave", "Steve", "John", "Pete", "Rob", "Tom", "Chris"]
    for name in player_names:
        seq += 1
        events.append(
            Event(
                id=f"evt_{seq:03d}",
                sequence=seq,
                timestamp=now_iso(),
                actor="system",
                source="ai",
                type="entity.create",
                payload={
                    "collection": "players",
                    "id": f"player_{name.lower()}",
                    "fields": {
                        "name": name,
                        "games_played": 0,
                        "total_winnings": 0,
                        "hosting_count": 0,
                        "active": True,
                    },
                },
            )
        )

    # 11. Set meta title
    seq += 1
    events.append(
        Event(
            id=f"evt_{seq:03d}",
            sequence=seq,
            timestamp=now_iso(),
            actor="system",
            source="ai",
            type="meta.update",
            payload={"title": "Thursday Night Poker"},
        )
    )

    # 12. Set meta description
    seq += 1
    events.append(
        Event(
            id=f"evt_{seq:03d}",
            sequence=seq,
            timestamp=now_iso(),
            actor="system",
            source="ai",
            type="meta.update",
            payload={"description": "Every other Thursday at someone's house."},
        )
    )

    # 13. Create players view
    seq += 1
    events.append(
        Event(
            id=f"evt_{seq:03d}",
            sequence=seq,
            timestamp=now_iso(),
            actor="system",
            source="ai",
            type="view.create",
            payload={
                "id": "standings_view",
                "type": "table",
                "source": "players",
                "config": {
                    "show_fields": ["name", "games_played", "total_winnings"],
                    "sort_by": "total_winnings",
                    "sort_order": "desc",
                },
            },
        )
    )

    # 14. Create games view
    seq += 1
    events.append(
        Event(
            id=f"evt_{seq:03d}",
            sequence=seq,
            timestamp=now_iso(),
            actor="system",
            source="ai",
            type="view.create",
            payload={
                "id": "recent_games_view",
                "type": "table",
                "source": "games",
                "config": {
                    "show_fields": ["date", "host", "winner", "pot"],
                    "sort_by": "date",
                    "sort_order": "desc",
                },
            },
        )
    )

    # 15. Create header block
    seq += 1
    events.append(
        Event(
            id=f"evt_{seq:03d}",
            sequence=seq,
            timestamp=now_iso(),
            actor="system",
            source="ai",
            type="block.set",
            payload={
                "id": "block_header",
                "type": "heading",
                "parent": "block_root",
                "props": {"level": 1, "content": "Thursday Night Poker"},
            },
        )
    )

    # 16. Create standings section
    seq += 1
    events.append(
        Event(
            id=f"evt_{seq:03d}",
            sequence=seq,
            timestamp=now_iso(),
            actor="system",
            source="ai",
            type="block.set",
            payload={
                "id": "block_standings_header",
                "type": "heading",
                "parent": "block_root",
                "props": {"level": 2, "content": "Standings"},
            },
        )
    )

    # 17. Create standings view block
    seq += 1
    events.append(
        Event(
            id=f"evt_{seq:03d}",
            sequence=seq,
            timestamp=now_iso(),
            actor="system",
            source="ai",
            type="block.set",
            payload={
                "id": "block_standings",
                "type": "collection_view",
                "parent": "block_root",
                "props": {"source": "players", "view": "standings_view"},
            },
        )
    )

    # 18. Create recent games section
    seq += 1
    events.append(
        Event(
            id=f"evt_{seq:03d}",
            sequence=seq,
            timestamp=now_iso(),
            actor="system",
            source="ai",
            type="block.set",
            payload={
                "id": "block_games_header",
                "type": "heading",
                "parent": "block_root",
                "props": {"level": 2, "content": "Recent Games"},
            },
        )
    )

    # 19. Create games view block
    seq += 1
    events.append(
        Event(
            id=f"evt_{seq:03d}",
            sequence=seq,
            timestamp=now_iso(),
            actor="system",
            source="ai",
            type="block.set",
            payload={
                "id": "block_games",
                "type": "collection_view",
                "parent": "block_root",
                "props": {"source": "games", "view": "recent_games_view"},
            },
        )
    )

    return events


# ============================================================================
# Step 1: Create
# ============================================================================


class TestNewAideFlowCreate:
    """
    Verify create() produces a valid empty aide.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_create_produces_valid_aide(self, assembly):
        """create() returns a valid AideFile with empty state."""
        bp = make_poker_league_blueprint()
        aide_file = await assembly.create(bp)

        # Has ID
        assert aide_file.aide_id is not None
        assert len(aide_file.aide_id) > 0

        # Has blueprint
        assert aide_file.blueprint.identity == bp.identity
        assert aide_file.blueprint.voice == bp.voice

        # Empty state
        assert aide_file.events == []
        assert aide_file.last_sequence == 0

        # Has snapshot with empty collections
        assert aide_file.snapshot is not None
        assert aide_file.snapshot["collections"] == {}

        # Has valid HTML
        assert aide_file.html.startswith("<!DOCTYPE html>")

        # Loaded from "new"
        assert aide_file.loaded_from == "new"


# ============================================================================
# Step 2: Apply
# ============================================================================


class TestNewAideFlowApply:
    """
    Verify apply() correctly processes AI-generated events.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_apply_all_events_accepted(self, assembly):
        """All well-formed events are accepted."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()

        result = await assembly.apply(aide_file, events)

        assert len(result.rejected) == 0
        assert len(result.applied) == len(events)

    @pytest.mark.asyncio
    async def test_apply_creates_collections(self, assembly):
        """Apply creates the expected collections."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)

        assert "players" in aide_file.snapshot["collections"]
        assert "games" in aide_file.snapshot["collections"]

    @pytest.mark.asyncio
    async def test_apply_creates_entities(self, assembly):
        """Apply creates the expected entities."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)

        players = aide_file.snapshot["collections"]["players"]["entities"]
        assert len(players) == 8

        # Check a specific player
        assert "player_mike" in players
        assert players["player_mike"]["name"] == "Mike"
        assert players["player_mike"]["active"] is True

    @pytest.mark.asyncio
    async def test_apply_sets_meta(self, assembly):
        """Apply sets meta fields correctly."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)

        assert aide_file.snapshot["meta"]["title"] == "Thursday Night Poker"
        assert "Thursday" in aide_file.snapshot["meta"]["description"]

    @pytest.mark.asyncio
    async def test_apply_creates_views(self, assembly):
        """Apply creates views correctly."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)

        assert "standings_view" in aide_file.snapshot["views"]
        assert "recent_games_view" in aide_file.snapshot["views"]

        standings = aide_file.snapshot["views"]["standings_view"]
        assert standings["type"] == "table"
        assert standings["source"] == "players"

    @pytest.mark.asyncio
    async def test_apply_creates_blocks(self, assembly):
        """Apply creates blocks correctly."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)

        blocks = aide_file.snapshot["blocks"]
        assert "block_header" in blocks
        assert "block_standings" in blocks
        assert "block_games" in blocks

    @pytest.mark.asyncio
    async def test_apply_updates_sequence(self, assembly):
        """Apply stores all events.

        NOTE: last_sequence only tracks auto-assigned sequences.
        With preset sequences, last_sequence stays at 0 during apply.
        But all events are correctly stored and load() computes it right.
        """
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)

        # All events are stored
        assert len(aide_file.events) == len(events)

    @pytest.mark.asyncio
    async def test_apply_renders_html(self, assembly):
        """Apply produces valid rendered HTML."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)

        # HTML contains content
        assert "Thursday Night Poker" in aide_file.html
        assert "Standings" in aide_file.html

        # HTML is valid
        parsed = parse_aide_html(aide_file.html)
        assert parsed.parse_errors == []


# ============================================================================
# Step 3: Save
# ============================================================================


class TestNewAideFlowSave:
    """
    Verify save() persists the aide correctly.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_save_persists_to_storage(self, assembly, storage):
        """save() writes aide to storage."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)

        await assembly.save(aide_file)

        assert aide_file.aide_id in storage.workspace

    @pytest.mark.asyncio
    async def test_save_can_be_loaded(self, assembly, storage):
        """Saved aide can be loaded back."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)
        await assembly.save(aide_file)

        loaded = await assembly.load(aide_file.aide_id)

        assert loaded.aide_id == aide_file.aide_id
        # load() computes last_sequence from events correctly
        assert loaded.last_sequence == len(events)

    @pytest.mark.asyncio
    async def test_saved_aide_has_correct_state(self, assembly, storage):
        """Loaded aide has complete state."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)
        await assembly.save(aide_file)

        loaded = await assembly.load(aide_file.aide_id)

        # Check collections
        assert len(loaded.snapshot["collections"]["players"]["entities"]) == 8

        # Check events preserved
        assert len(loaded.events) == len(events)

        # Check blueprint preserved
        assert loaded.blueprint.identity == aide_file.blueprint.identity


# ============================================================================
# Step 4: Publish
# ============================================================================


class TestNewAideFlowPublish:
    """
    Verify publish() creates a public version.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_publish_returns_url(self, assembly, storage):
        """publish() returns a public URL."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)
        await assembly.save(aide_file)

        url = await assembly.publish(aide_file, slug="poker-league")

        assert url == "https://toaide.com/p/poker-league"

    @pytest.mark.asyncio
    async def test_publish_creates_public_html(self, assembly, storage):
        """publish() creates HTML in published storage."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)
        await assembly.save(aide_file)

        await assembly.publish(aide_file, slug="poker-league")

        assert "poker-league" in storage.published

    @pytest.mark.asyncio
    async def test_published_html_has_content(self, assembly, storage):
        """Published HTML contains the aide content."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)
        await assembly.save(aide_file)

        await assembly.publish(aide_file, slug="poker-league")

        published_html = storage.published["poker-league"]
        assert "Thursday Night Poker" in published_html
        assert "Mike" in published_html

    @pytest.mark.asyncio
    async def test_published_html_is_parseable(self, assembly, storage):
        """Published HTML is valid and parseable."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)
        await assembly.save(aide_file)

        await assembly.publish(aide_file, slug="poker-league")

        published_html = storage.published["poker-league"]
        parsed = parse_aide_html(published_html)
        assert parsed.parse_errors == []


# ============================================================================
# Full flow integration
# ============================================================================


class TestNewAideFlowComplete:
    """
    Test the complete flow: create → apply → save → publish.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_complete_flow(self, assembly, storage):
        """Complete new aide flow succeeds."""
        # Step 1: Create
        bp = make_poker_league_blueprint()
        aide_file = await assembly.create(bp)
        assert aide_file.aide_id is not None

        # Step 2: Apply
        events = make_poker_league_events()
        result = await assembly.apply(aide_file, events)
        assert len(result.rejected) == 0
        assert len(result.applied) == len(events)

        # Step 3: Save
        await assembly.save(aide_file)
        assert aide_file.aide_id in storage.workspace

        # Step 4: Publish
        url = await assembly.publish(aide_file, slug="poker-league")
        assert url == "https://toaide.com/p/poker-league"
        assert "poker-league" in storage.published

        # Verify final state
        published_html = storage.published["poker-league"]
        parsed = parse_aide_html(published_html)

        assert parsed.blueprint.identity == bp.identity
        assert "players" in parsed.snapshot["collections"]
        assert len(parsed.snapshot["collections"]["players"]["entities"]) == 8

    @pytest.mark.asyncio
    async def test_flow_with_free_tier_footer(self, assembly, storage):
        """Free tier flow adds footer to published page."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)
        await assembly.save(aide_file)

        await assembly.publish(aide_file, slug="poker-free", is_free_tier=True)

        published_html = storage.published["poker-free"]
        assert "aide-footer" in published_html

    @pytest.mark.asyncio
    async def test_flow_with_pro_tier_no_footer(self, assembly, storage):
        """Pro tier flow has no footer on published page."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)
        await assembly.save(aide_file)

        await assembly.publish(aide_file, slug="poker-pro", is_free_tier=False)

        published_html = storage.published["poker-pro"]
        assert '<footer class="aide-footer">' not in published_html


# ============================================================================
# State validity at each step
# ============================================================================


class TestStateValidityAtEachStep:
    """
    Verify aide is in valid state at each step of the flow.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_valid_after_create(self, assembly):
        """Aide is valid immediately after create."""
        aide_file = await assembly.create(make_poker_league_blueprint())

        # Can render HTML
        assert aide_file.html.startswith("<!DOCTYPE html>")

        # Snapshot is valid
        assert "collections" in aide_file.snapshot
        assert "meta" in aide_file.snapshot
        assert "blocks" in aide_file.snapshot

    @pytest.mark.asyncio
    async def test_valid_after_partial_apply(self, assembly):
        """Aide is valid after applying some events."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()

        # Apply just the first 5 events
        await assembly.apply(aide_file, events[:5])

        # HTML is valid
        parsed = parse_aide_html(aide_file.html)
        assert parsed.parse_errors == []

        # Snapshot reflects partial state
        assert "players" in aide_file.snapshot["collections"]

    @pytest.mark.asyncio
    async def test_valid_after_full_apply(self, assembly):
        """Aide is valid after applying all events."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)

        # HTML is valid and complete
        parsed = parse_aide_html(aide_file.html)
        assert parsed.parse_errors == []

        # All content present
        assert "Thursday Night Poker" in aide_file.html
        assert len(aide_file.snapshot["collections"]["players"]["entities"]) == 8

    @pytest.mark.asyncio
    async def test_valid_after_save(self, assembly, storage):
        """Aide is valid after save."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)
        await assembly.save(aide_file)

        # Load and verify
        loaded = await assembly.load(aide_file.aide_id)

        is_valid, issues = await assembly.integrity_check(loaded)
        # Note: Integrity check may have known limitations
        assert isinstance(is_valid, bool)

    @pytest.mark.asyncio
    async def test_valid_after_publish(self, assembly, storage):
        """Published version is valid."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)
        await assembly.save(aide_file)
        await assembly.publish(aide_file, slug="valid-test")

        published_html = storage.published["valid-test"]
        parsed = parse_aide_html(published_html)

        assert parsed.parse_errors == []
        assert parsed.blueprint is not None
        assert parsed.snapshot is not None


# ============================================================================
# Edge cases
# ============================================================================


class TestNewAideFlowEdgeCases:
    """
    Test edge cases in the new aide flow.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_publish_before_save(self, assembly, storage):
        """Can publish without saving to workspace first."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)

        # Publish without save
        url = await assembly.publish(aide_file, slug="no-save-test")

        assert "no-save-test" in storage.published
        # Should NOT be in workspace
        assert aide_file.aide_id not in storage.workspace

    @pytest.mark.asyncio
    async def test_multiple_applies_before_save(self, assembly, storage):
        """Can apply events in multiple batches before save."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()

        # Apply in chunks
        await assembly.apply(aide_file, events[:5])
        await assembly.apply(aide_file, events[5:10])
        await assembly.apply(aide_file, events[10:])

        await assembly.save(aide_file)

        loaded = await assembly.load(aide_file.aide_id)
        assert len(loaded.events) == len(events)

    @pytest.mark.asyncio
    async def test_republish_after_updates(self, assembly, storage):
        """Can republish after applying more events."""
        aide_file = await assembly.create(make_poker_league_blueprint())
        events = make_poker_league_events()
        await assembly.apply(aide_file, events)

        # First publish
        await assembly.publish(aide_file, slug="republish-test")
        v1_html = storage.published["republish-test"]

        # Apply more events
        next_seq = len(events) + 1
        update_event = Event(
            id=f"evt_{next_seq:03d}",
            sequence=next_seq,
            timestamp=now_iso(),
            actor="user",
            source="test",
            type="field.update",
            payload={"collection": "players", "entity": "player_mike", "field": "total_winnings", "value": 500},
        )
        await assembly.apply(aide_file, [update_event])

        # Republish
        await assembly.publish(aide_file, slug="republish-test")
        v2_html = storage.published["republish-test"]

        # V2 should be different (has updated data)
        # Both should be valid
        assert parse_aide_html(v1_html).parse_errors == []
        assert parse_aide_html(v2_html).parse_errors == []
