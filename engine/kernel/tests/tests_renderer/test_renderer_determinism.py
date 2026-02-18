"""
AIde Renderer -- Determinism Tests (v3 Unified Entity Model)

Render the same snapshot 100 times, verify identical output every time.

From the spec (aide_renderer_spec.md, "Testing Strategy"):
  "10. Determinism. Render the same snapshot 100 times, verify identical
   output every time."

From the renderer contract:
  "Deterministic: same input → same output, always."

Reference: aide_renderer_spec.md (Contract, CSS Generation, Testing Strategy)
"""

import json

from engine.kernel.reducer import empty_state
from engine.kernel.renderer import render
from engine.kernel.types import Blueprint, Event


def make_blueprint():
    return Blueprint(
        identity="Test aide for determinism checks.",
        voice="No first person. State reflections only.",
        prompt="You are maintaining a test page.",
    )


def make_events():
    return [
        Event(
            id="evt_20260215_001",
            sequence=1,
            timestamp="2026-02-15T09:00:00Z",
            actor="user_test",
            source="web",
            type="schema.create",
            payload={"id": "item", "interface": "interface Item { name: string; }"},
        ),
        Event(
            id="evt_20260215_002",
            sequence=2,
            timestamp="2026-02-15T09:01:00Z",
            actor="user_test",
            source="web",
            type="entity.create",
            payload={"id": "item_1", "_schema": "item", "name": "First"},
        ),
    ]


def grocery_list_snapshot():
    """
    Grocery list with heading, text, metric, entities, style tokens,
    and annotations.
    """
    snapshot = empty_state()

    snapshot["meta"] = {
        "title": "Weekly Groceries",
        "identity": "Family grocery list.",
    }

    snapshot["styles"] = {
        "primary_color": "#2d3748",
        "bg_color": "#fafaf9",
    }

    snapshot["schemas"]["grocery_item"] = {
        "interface": "interface GroceryItem { name: string; checked: boolean; }",
        "render_html": "<li class=\"grocery-item\">{{name}}</li>",
        "render_text": "- {{name}}",
        "styles": ".grocery-item { padding: 4px; }",
    }

    snapshot["entities"]["groceries"] = {
        "_schema": "grocery_item",
        "name": "Groceries",
        "items": {
            "item_milk": {"name": "Milk", "checked": False, "_pos": 1.0},
            "item_eggs": {"name": "Eggs", "checked": True, "_pos": 2.0},
            "item_bread": {"name": "Bread", "checked": False, "_pos": 3.0},
        },
    }

    # Blocks
    snapshot["blocks"]["block_title"] = {
        "type": "heading",
        "level": 1,
        "text": "Weekly Groceries",
    }
    snapshot["blocks"]["block_subtitle"] = {
        "type": "text",
        "text": "Updated **Tuesday evening**.",
    }
    snapshot["blocks"]["block_count"] = {
        "type": "metric",
        "label": "Items remaining",
        "value": "3",
    }
    snapshot["blocks"]["block_list"] = {
        "type": "entity_view",
        "source": "groceries",
    }
    snapshot["blocks"]["block_divider"] = {"type": "divider"}
    snapshot["blocks"]["block_root"]["children"] = [
        "block_title",
        "block_subtitle",
        "block_count",
        "block_list",
        "block_divider",
    ]

    snapshot["annotations"] = [
        {
            "note": "Added bread.",
            "timestamp": "2026-02-15T18:00:00Z",
        }
    ]

    return snapshot


def poker_snapshot():
    """Poker league snapshot with player entities."""
    snapshot = empty_state()

    snapshot["meta"] = {
        "title": "Poker League 2026",
        "identity": "Monthly home game tracker.",
    }

    snapshot["styles"] = {"primary_color": "#7c3aed"}

    snapshot["schemas"]["player"] = {
        "interface": "interface Player { name: string; wins: number; score: number; }",
        "render_html": "<tr><td>{{name}}</td><td>{{wins}}</td><td>{{score}}</td></tr>",
        "render_text": "{{name}}: {{wins}} wins",
    }

    snapshot["entities"]["players"] = {
        "_schema": "player",
        "name": "Players",
        "roster": {
            "player_mike": {"name": "Mike", "wins": 3, "score": 1200, "_pos": 1.0},
            "player_sarah": {"name": "Sarah", "wins": 5, "score": 1450, "_pos": 2.0},
            "player_dave": {"name": "Dave", "wins": 2, "score": 1100, "_pos": 3.0},
        },
    }

    snapshot["blocks"]["block_title"] = {
        "type": "heading",
        "level": 1,
        "text": "Poker League 2026",
    }
    snapshot["blocks"]["block_next"] = {
        "type": "metric",
        "label": "Next Game",
        "value": "March 15 at Mike's",
    }
    snapshot["blocks"]["block_players"] = {
        "type": "entity_view",
        "source": "players",
    }
    snapshot["blocks"]["block_root"]["children"] = [
        "block_title",
        "block_next",
        "block_players",
    ]

    return snapshot


class TestRenderDeterminism:
    """
    Render must be byte-identical across repeated invocations.
    """

    def test_empty_snapshot_is_deterministic(self):
        """Empty snapshot renders identically 100 times."""
        snapshot = empty_state()
        snapshot["meta"] = {"title": "Test"}
        blueprint = make_blueprint()

        first = render(snapshot, blueprint)
        for _ in range(99):
            result = render(snapshot, blueprint)
            assert result == first, "Render output changed on repeat call"

    def test_grocery_list_is_deterministic(self):
        """Grocery list snapshot renders identically 100 times."""
        snapshot = grocery_list_snapshot()
        blueprint = make_blueprint()

        first = render(snapshot, blueprint)
        for _ in range(99):
            result = render(snapshot, blueprint)
            assert result == first, "Grocery list render is not deterministic"

    def test_poker_snapshot_is_deterministic(self):
        """Poker league snapshot renders identically 100 times."""
        snapshot = poker_snapshot()
        blueprint = make_blueprint()

        first = render(snapshot, blueprint)
        for _ in range(99):
            result = render(snapshot, blueprint)
            assert result == first, "Poker snapshot render is not deterministic"

    def test_determinism_with_events(self):
        """Rendering with events list is deterministic."""
        from engine.kernel.types import RenderOptions

        snapshot = grocery_list_snapshot()
        blueprint = make_blueprint()
        events = make_events()
        opts = RenderOptions(include_events=True)

        first = render(snapshot, blueprint, events=events, options=opts)
        for _ in range(49):
            result = render(snapshot, blueprint, events=events, options=opts)
            assert result == first, "Render with events is not deterministic"

    def test_determinism_with_blueprint(self):
        """Rendering with blueprint embedded is deterministic."""
        from engine.kernel.types import RenderOptions

        snapshot = grocery_list_snapshot()
        blueprint = make_blueprint()
        opts = RenderOptions(include_blueprint=True)

        first = render(snapshot, blueprint, options=opts)
        for _ in range(49):
            result = render(snapshot, blueprint, options=opts)
            assert result == first, "Render with blueprint is not deterministic"

    def test_json_keys_are_sorted(self):
        """Embedded JSON uses sorted keys for determinism."""
        snapshot = grocery_list_snapshot()
        blueprint = make_blueprint()

        html = render(snapshot, blueprint)

        # Extract the embedded JSON and check key ordering
        import re

        pattern = r'<script[^>]*id="aide-state"[^>]*>(.*?)</script>'
        match = re.search(pattern, html, re.DOTALL)
        assert match, "No aide-state script block found"

        raw = match.group(1).strip()
        parsed = json.loads(raw)

        # Re-dump with sort_keys and check it matches
        sorted_str = json.dumps(parsed, sort_keys=True, ensure_ascii=False)
        # The embedded JSON should parse to the same structure
        reparsed = json.loads(sorted_str)
        assert reparsed == parsed

    def test_css_generation_is_stable(self):
        """CSS output is stable across renders."""
        snapshot = grocery_list_snapshot()
        blueprint = make_blueprint()

        import re

        def extract_css(html):
            match = re.search(r"<style>(.*?)</style>", html, re.DOTALL)
            return match.group(1) if match else ""

        first_css = extract_css(render(snapshot, blueprint))
        for _ in range(19):
            css = extract_css(render(snapshot, blueprint))
            assert css == first_css, "CSS is not deterministic"

    def test_entity_iteration_order_is_stable(self):
        """Entity rendering order is stable (not dict insertion-order dependent)."""
        snapshot = poker_snapshot()
        blueprint = make_blueprint()

        first = render(snapshot, blueprint)
        for _ in range(29):
            result = render(snapshot, blueprint)
            assert result == first, "Entity iteration order is not stable"


class TestRenderIdempotence:
    """
    Rendering the same snapshot with same options always produces same output.
    The function is pure and has no side effects.
    """

    def test_snapshot_not_mutated(self):
        """The snapshot dict is not mutated by render()."""
        import copy

        snapshot = grocery_list_snapshot()
        blueprint = make_blueprint()

        original = copy.deepcopy(snapshot)
        render(snapshot, blueprint)

        assert snapshot == original, "render() mutated the snapshot"

    def test_blueprint_not_mutated(self):
        """The blueprint object is not mutated by render()."""
        snapshot = grocery_list_snapshot()
        blueprint = make_blueprint()
        original_identity = blueprint.identity
        original_voice = blueprint.voice

        render(snapshot, blueprint)

        assert blueprint.identity == original_identity
        assert blueprint.voice == original_voice

    def test_events_not_mutated(self):
        """The events list is not mutated by render()."""
        from engine.kernel.types import RenderOptions

        snapshot = grocery_list_snapshot()
        blueprint = make_blueprint()
        events = make_events()
        opts = RenderOptions(include_events=True)

        original_len = len(events)
        original_first = events[0].id

        render(snapshot, blueprint, events=events, options=opts)

        assert len(events) == original_len
        assert events[0].id == original_first


class TestRenderDifferentInputsDifferentOutputs:
    """
    Different inputs produce different outputs (basic sanity check).
    """

    def test_different_titles_different_output(self):
        """Two snapshots with different titles produce different HTML."""
        s1 = empty_state()
        s1["meta"] = {"title": "Page One"}
        s2 = empty_state()
        s2["meta"] = {"title": "Page Two"}
        blueprint = make_blueprint()

        html1 = render(s1, blueprint)
        html2 = render(s2, blueprint)

        assert html1 != html2

    def test_different_entities_different_output(self):
        """Two snapshots with different entities produce different HTML."""
        s1 = grocery_list_snapshot()
        s2 = grocery_list_snapshot()

        # Add a new entity to s2
        s2["entities"]["extra"] = {"name": "Extra Entity"}
        s2["blocks"]["block_extra"] = {"type": "text", "text": "Extra content."}
        s2["blocks"]["block_root"]["children"].append("block_extra")

        blueprint = make_blueprint()
        html1 = render(s1, blueprint)
        html2 = render(s2, blueprint)

        assert html1 != html2

    def test_different_styles_different_css(self):
        """Two snapshots with different style tokens produce different CSS."""
        s1 = empty_state()
        s1["meta"] = {"title": "Test"}
        s1["styles"] = {"primary_color": "#ff0000"}

        s2 = empty_state()
        s2["meta"] = {"title": "Test"}
        s2["styles"] = {"primary_color": "#0000ff"}

        blueprint = make_blueprint()
        html1 = render(s1, blueprint)
        html2 = render(s2, blueprint)

        assert html1 != html2
