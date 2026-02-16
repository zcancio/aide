"""
AIde Assembly -- Parse/Assemble Tests (Category 2)

Render an HTML file, parse it back, verify all extracted data matches
the original inputs.

From the spec (aide_assembly_spec.md, "Testing Strategy"):
  "2. Parse <-> assemble. Render an HTML file, parse it back, verify all
   extracted data matches the original inputs."

This verifies:
  - HTML rendering embeds JSON correctly
  - HTML parsing extracts JSON correctly
  - Blueprint, snapshot, and events survive the render/parse cycle
  - Parser is tolerant of optional sections

Reference: aide_assembly_spec.md (Parsing, Testing Strategy)
"""

import json

import pytest

from engine.kernel.assembly import AideAssembly, MemoryStorage, parse_aide_html
from engine.kernel.reducer import empty_state
from engine.kernel.renderer import render
from engine.kernel.types import Blueprint, Event, now_iso

# ============================================================================
# Fixtures
# ============================================================================


def make_blueprint():
    return Blueprint(
        identity="Test aide for parsing verification.",
        voice="Clear, direct language.",
        prompt="You are a test aide.",
    )


def make_events():
    return [
        Event(
            id="evt_001",
            sequence=1,
            timestamp="2026-02-15T10:00:00Z",
            actor="user_test",
            source="test",
            type="collection.create",
            payload={"id": "items", "schema": {"name": "string"}},
        ),
        Event(
            id="evt_002",
            sequence=2,
            timestamp="2026-02-15T10:01:00Z",
            actor="user_test",
            source="test",
            type="entity.create",
            payload={"collection": "items", "id": "item_1", "fields": {"name": "First"}},
        ),
    ]


def make_populated_snapshot():
    """Create a snapshot with collections, entities, blocks, and views."""
    snapshot = empty_state()
    snapshot["meta"] = {"title": "Parse Test Aide", "identity": "Testing parser."}
    snapshot["styles"] = {"primary_color": "#3b82f6", "density": "comfortable"}
    snapshot["collections"] = {
        "tasks": {
            "id": "tasks",
            "name": "Tasks",
            "schema": {"name": "string", "done": "bool", "priority": "int"},
            "entities": {
                "t1": {"name": "Write tests", "done": False, "priority": 1, "_removed": False},
                "t2": {"name": "Review code", "done": True, "priority": 2, "_removed": False},
            },
        },
    }
    snapshot["views"] = {
        "tasks_view": {
            "id": "tasks_view",
            "type": "list",
            "source": "tasks",
            "config": {"show_fields": ["name", "done"]},
        },
    }
    snapshot["blocks"] = {
        "block_root": {"type": "root", "children": ["block_h1", "block_tasks"]},
        "block_h1": {
            "type": "heading",
            "parent": "block_root",
            "props": {"level": 1, "content": "Parse Test"},
        },
        "block_tasks": {
            "type": "collection_view",
            "parent": "block_root",
            "props": {"source": "tasks", "view": "tasks_view"},
        },
    }
    return snapshot


# ============================================================================
# Parse <- Render: Round-trip parsing tests
# ============================================================================


class TestParseRenderedHTML:
    """
    Verify parsing extracts correct data from rendered HTML.
    """

    def test_parse_extracts_blueprint(self):
        """Blueprint is extracted correctly from rendered HTML."""
        blueprint = make_blueprint()
        snapshot = empty_state()
        html = render(snapshot, blueprint)

        parsed = parse_aide_html(html)

        assert parsed.blueprint is not None
        assert parsed.blueprint.identity == blueprint.identity
        assert parsed.blueprint.voice == blueprint.voice
        assert parsed.blueprint.prompt == blueprint.prompt

    def test_parse_extracts_snapshot(self):
        """Snapshot is extracted correctly from rendered HTML."""
        blueprint = make_blueprint()
        snapshot = make_populated_snapshot()
        html = render(snapshot, blueprint)

        parsed = parse_aide_html(html)

        assert parsed.snapshot is not None
        assert parsed.snapshot["meta"]["title"] == "Parse Test Aide"
        assert "tasks" in parsed.snapshot["collections"]

    def test_parse_extracts_events(self):
        """Events are extracted correctly from rendered HTML."""
        blueprint = make_blueprint()
        snapshot = empty_state()
        events = make_events()
        html = render(snapshot, blueprint, events)

        parsed = parse_aide_html(html)

        assert len(parsed.events) == 2
        assert parsed.events[0].type == "collection.create"
        assert parsed.events[1].type == "entity.create"
        assert parsed.events[0].sequence == 1
        assert parsed.events[1].sequence == 2

    def test_parse_no_errors(self):
        """Valid HTML produces no parse errors."""
        blueprint = make_blueprint()
        snapshot = make_populated_snapshot()
        events = make_events()
        html = render(snapshot, blueprint, events)

        parsed = parse_aide_html(html)

        assert parsed.parse_errors == []


class TestBlueprintRoundTrip:
    """
    Verify all blueprint fields survive render/parse cycle.
    """

    def test_identity_preserved(self):
        """Blueprint identity string is preserved exactly."""
        bp = Blueprint(
            identity="A complex identity with \"quotes\" and 'apostrophes'.",
            voice="Voice with special chars: <>&",
        )
        html = render(empty_state(), bp)
        parsed = parse_aide_html(html)

        assert parsed.blueprint.identity == bp.identity

    def test_voice_preserved(self):
        """Blueprint voice string is preserved exactly."""
        bp = Blueprint(
            identity="Test",
            voice="No first person. Use we/us. Formal tone.",
        )
        html = render(empty_state(), bp)
        parsed = parse_aide_html(html)

        assert parsed.blueprint.voice == bp.voice

    def test_prompt_preserved(self):
        """Blueprint prompt string is preserved exactly."""
        bp = Blueprint(
            identity="Test",
            prompt="A detailed prompt with\nmultiple lines\nand various content.",
        )
        html = render(empty_state(), bp)
        parsed = parse_aide_html(html)

        assert parsed.blueprint.prompt == bp.prompt


class TestSnapshotRoundTrip:
    """
    Verify all snapshot sections survive render/parse cycle.
    """

    def test_meta_preserved(self):
        """Meta section is preserved exactly."""
        snapshot = empty_state()
        snapshot["meta"] = {
            "title": "My Aide Title",
            "identity": "An identity description.",
        }
        html = render(snapshot, make_blueprint())
        parsed = parse_aide_html(html)

        assert parsed.snapshot["meta"]["title"] == "My Aide Title"
        assert parsed.snapshot["meta"]["identity"] == "An identity description."

    def test_styles_preserved(self):
        """Styles section is preserved exactly."""
        snapshot = empty_state()
        snapshot["styles"] = {
            "primary_color": "#ff5500",
            "bg_color": "#fafafa",
            "density": "compact",
        }
        html = render(snapshot, make_blueprint())
        parsed = parse_aide_html(html)

        assert parsed.snapshot["styles"]["primary_color"] == "#ff5500"
        assert parsed.snapshot["styles"]["bg_color"] == "#fafafa"
        assert parsed.snapshot["styles"]["density"] == "compact"

    def test_collections_preserved(self):
        """Collections and their entities are preserved."""
        snapshot = make_populated_snapshot()
        html = render(snapshot, make_blueprint())
        parsed = parse_aide_html(html)

        assert "tasks" in parsed.snapshot["collections"]
        coll = parsed.snapshot["collections"]["tasks"]
        assert coll["name"] == "Tasks"
        assert "t1" in coll["entities"]
        assert coll["entities"]["t1"]["name"] == "Write tests"

    def test_views_preserved(self):
        """Views and their config are preserved."""
        snapshot = make_populated_snapshot()
        html = render(snapshot, make_blueprint())
        parsed = parse_aide_html(html)

        assert "tasks_view" in parsed.snapshot["views"]
        view = parsed.snapshot["views"]["tasks_view"]
        assert view["type"] == "list"
        assert view["source"] == "tasks"

    def test_blocks_preserved(self):
        """Block tree is preserved."""
        snapshot = make_populated_snapshot()
        html = render(snapshot, make_blueprint())
        parsed = parse_aide_html(html)

        assert "block_root" in parsed.snapshot["blocks"]
        assert "block_h1" in parsed.snapshot["blocks"]
        assert "block_tasks" in parsed.snapshot["blocks"]


class TestEventsRoundTrip:
    """
    Verify all event fields survive render/parse cycle.
    """

    def test_event_ids_preserved(self):
        """Event IDs are preserved exactly."""
        events = make_events()
        html = render(empty_state(), make_blueprint(), events)
        parsed = parse_aide_html(html)

        assert parsed.events[0].id == "evt_001"
        assert parsed.events[1].id == "evt_002"

    def test_event_types_preserved(self):
        """Event types are preserved exactly."""
        events = make_events()
        html = render(empty_state(), make_blueprint(), events)
        parsed = parse_aide_html(html)

        assert parsed.events[0].type == "collection.create"
        assert parsed.events[1].type == "entity.create"

    def test_event_payloads_preserved(self):
        """Event payloads are preserved exactly."""
        events = make_events()
        html = render(empty_state(), make_blueprint(), events)
        parsed = parse_aide_html(html)

        assert parsed.events[0].payload["id"] == "items"
        assert parsed.events[1].payload["fields"]["name"] == "First"

    def test_event_timestamps_preserved(self):
        """Event timestamps are preserved exactly."""
        events = make_events()
        html = render(empty_state(), make_blueprint(), events)
        parsed = parse_aide_html(html)

        assert parsed.events[0].timestamp == "2026-02-15T10:00:00Z"
        assert parsed.events[1].timestamp == "2026-02-15T10:01:00Z"


class TestParserTolerance:
    """
    Verify parser is tolerant of missing optional sections.
    """

    def test_missing_events_ok(self):
        """HTML without events section parses without error."""
        from engine.kernel.renderer import RenderOptions

        options = RenderOptions(include_events=False)
        html = render(empty_state(), make_blueprint(), events=None, options=options)
        parsed = parse_aide_html(html)

        assert parsed.events == []
        assert parsed.parse_errors == []

    def test_missing_blueprint_ok(self):
        """HTML without blueprint section parses without error."""
        from engine.kernel.renderer import RenderOptions

        options = RenderOptions(include_blueprint=False)
        html = render(empty_state(), make_blueprint(), options=options)
        parsed = parse_aide_html(html)

        assert parsed.blueprint is None
        assert parsed.parse_errors == []

    def test_snapshot_always_required(self):
        """Snapshot must always be present (required section)."""
        # Normal render always includes snapshot
        html = render(empty_state(), make_blueprint())
        parsed = parse_aide_html(html)

        assert parsed.snapshot is not None


class TestJSONIntegrity:
    """
    Verify JSON is deterministically formatted and can be re-parsed.
    """

    def test_json_sorted_keys(self):
        """Embedded JSON uses sorted keys for determinism."""
        snapshot = make_populated_snapshot()
        html = render(snapshot, make_blueprint())

        # Extract the raw JSON
        import re
        state_match = re.search(
            r'<script[^>]*id="aide-state"[^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )
        state_json = state_match.group(1).strip()

        # Parse and re-serialize with sorted keys, should match
        parsed = json.loads(state_json)
        reserialized = json.dumps(parsed, sort_keys=True)
        assert state_json == reserialized

    def test_multiple_parses_identical(self):
        """Parsing the same HTML multiple times yields identical results."""
        html = render(make_populated_snapshot(), make_blueprint(), make_events())

        parsed1 = parse_aide_html(html)
        parsed2 = parse_aide_html(html)

        assert json.dumps(parsed1.snapshot, sort_keys=True) == json.dumps(parsed2.snapshot, sort_keys=True)
        assert len(parsed1.events) == len(parsed2.events)


# ============================================================================
# Integration with Assembly class
# ============================================================================


class TestAssemblyParsing:
    """
    Verify Assembly.load uses parser correctly.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_load_parses_saved_file(self, assembly, storage):
        """Assembly.load correctly parses a previously saved file."""
        aide_file = await assembly.create(make_blueprint())
        events = make_events()
        await assembly.apply(aide_file, events)
        await assembly.save(aide_file)

        # Load and verify
        loaded = await assembly.load(aide_file.aide_id)

        assert loaded.blueprint.identity == make_blueprint().identity
        assert len(loaded.events) == 2

    @pytest.mark.asyncio
    async def test_parsed_snapshot_matches_applied(self, assembly, storage):
        """Parsed snapshot exactly matches what was applied."""
        aide_file = await assembly.create(make_blueprint())

        events = [
            Event(
                id="evt_001",
                sequence=1,
                timestamp=now_iso(),
                actor="test",
                source="test",
                type="collection.create",
                payload={"id": "stuff", "schema": {"name": "string"}},
            ),
        ]
        result = await assembly.apply(aide_file, events)
        await assembly.save(result.aide_file)

        loaded = await assembly.load(aide_file.aide_id)

        assert "stuff" in loaded.snapshot["collections"]
        assert loaded.snapshot["collections"]["stuff"]["schema"]["name"] == "string"
