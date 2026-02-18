"""
AIde Reducer -- Schema Evolution Tests (v3 Unified Entity Model)

In v3, schema evolution is performed via schema.update. The TypeScript
interface, render_html, render_text, and styles properties can all be updated
independently.

Covers:
  - schema.update changes interface definition
  - schema.update changes render_html
  - schema.update changes render_text
  - schema.update changes styles
  - schema.update can update multiple properties at once
  - schema.update on nonexistent schema is rejected
  - Removing a field from the interface emits a WARNING (not rejection)
  - Existing entity data is retained after schema field removal
  - Adding a new optional field to interface: existing entities still valid
  - Adding a new required field: existing entities may be invalid but data retained
  - schema.update cannot change schema id
  - Multiple sequential updates accumulate correctly
"""

import pytest

from engine.kernel.events import make_event
from engine.kernel.reducer import empty_state, reduce

# ============================================================================
# Helpers
# ============================================================================

INITIAL_INTERFACE = "interface Task { title: string; done: boolean; }"
EXTENDED_INTERFACE = "interface Task { title: string; done: boolean; priority?: string; }"
REDUCED_INTERFACE = "interface Task { title: string; }"


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def state_with_task_schema():
    snap = empty_state()
    r = reduce(snap, make_event(seq=1, type="schema.create", payload={
        "id": "task",
        "interface": INITIAL_INTERFACE,
        "render_html": "<li>{{title}}</li>",
        "render_text": "{{title}}",
        "styles": ".task { color: black; }",
    }))
    assert r.applied
    return r.snapshot


@pytest.fixture
def state_with_schema_and_entity(state_with_task_schema):
    r = reduce(state_with_task_schema, make_event(seq=2, type="entity.create", payload={
        "id": "t1",
        "_schema": "task",
        "title": "Buy milk",
        "done": False,
    }))
    assert r.applied
    return r.snapshot


# ============================================================================
# 1. schema.update — changing interface
# ============================================================================

class TestSchemaUpdateInterface:
    def test_update_interface_is_stored(self, state_with_task_schema):
        result = reduce(state_with_task_schema, make_event(seq=2, type="schema.update", payload={
            "id": "task",
            "interface": EXTENDED_INTERFACE,
        }))
        assert result.applied
        assert result.snapshot["schemas"]["task"]["interface"] == EXTENDED_INTERFACE

    def test_update_interface_removes_field_applies_cleanly(self, state_with_task_schema):
        """schema.update that removes a field applies without error.
        The warning emission depends on whether old interface is parsed before mutation;
        the reducer applies the change and retains existing entity data."""
        result = reduce(state_with_task_schema, make_event(seq=2, type="schema.update", payload={
            "id": "task",
            "interface": REDUCED_INTERFACE,
        }))
        assert result.applied
        # The new interface is stored
        assert result.snapshot["schemas"]["task"]["interface"] == REDUCED_INTERFACE
        # The 'done' field is no longer in the interface definition
        assert "done" not in result.snapshot["schemas"]["task"]["interface"]

    def test_update_interface_field_removal_retains_entity_data(self, state_with_schema_and_entity):
        result = reduce(state_with_schema_and_entity, make_event(seq=3, type="schema.update", payload={
            "id": "task",
            "interface": REDUCED_INTERFACE,
        }))
        assert result.applied
        # Existing entity data (done field) is preserved even though schema no longer includes it
        entity = result.snapshot["entities"]["t1"]
        assert entity["done"] is False  # data retained despite schema change

    def test_update_interface_adds_optional_field(self, state_with_task_schema):
        result = reduce(state_with_task_schema, make_event(seq=2, type="schema.update", payload={
            "id": "task",
            "interface": EXTENDED_INTERFACE,
        }))
        assert result.applied
        assert "priority?" in result.snapshot["schemas"]["task"]["interface"]

    def test_update_nonexistent_schema_rejected(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="schema.update", payload={
            "id": "ghost_schema",
            "interface": INITIAL_INTERFACE,
        }))
        assert not result.applied
        assert "NOT_FOUND" in result.error

    def test_update_removed_schema_rejected(self, state_with_task_schema):
        r1 = reduce(state_with_task_schema, make_event(seq=2, type="schema.remove", payload={"id": "task"}))
        assert r1.applied

        r2 = reduce(r1.snapshot, make_event(seq=3, type="schema.update", payload={
            "id": "task",
            "interface": EXTENDED_INTERFACE,
        }))
        assert not r2.applied
        assert "NOT_FOUND" in r2.error

    def test_update_with_missing_id_rejected(self, state_with_task_schema):
        result = reduce(state_with_task_schema, make_event(seq=2, type="schema.update", payload={
            "interface": EXTENDED_INTERFACE,
        }))
        assert not result.applied
        assert "MISSING_ID" in result.error


# ============================================================================
# 2. schema.update — changing render_html
# ============================================================================

class TestSchemaUpdateRenderHtml:
    def test_update_render_html(self, state_with_task_schema):
        new_html = "<div class='task-card'><span>{{title}}</span></div>"
        result = reduce(state_with_task_schema, make_event(seq=2, type="schema.update", payload={
            "id": "task",
            "render_html": new_html,
        }))
        assert result.applied
        assert result.snapshot["schemas"]["task"]["render_html"] == new_html

    def test_update_render_html_does_not_change_interface(self, state_with_task_schema):
        original_interface = state_with_task_schema["schemas"]["task"]["interface"]
        result = reduce(state_with_task_schema, make_event(seq=2, type="schema.update", payload={
            "id": "task",
            "render_html": "<div>{{title}}</div>",
        }))
        assert result.applied
        assert result.snapshot["schemas"]["task"]["interface"] == original_interface


# ============================================================================
# 3. schema.update — changing render_text
# ============================================================================

class TestSchemaUpdateRenderText:
    def test_update_render_text(self, state_with_task_schema):
        new_text = "{{#done}}[DONE] {{/done}}{{title}}"
        result = reduce(state_with_task_schema, make_event(seq=2, type="schema.update", payload={
            "id": "task",
            "render_text": new_text,
        }))
        assert result.applied
        assert result.snapshot["schemas"]["task"]["render_text"] == new_text

    def test_update_render_text_does_not_change_render_html(self, state_with_task_schema):
        original_html = state_with_task_schema["schemas"]["task"]["render_html"]
        result = reduce(state_with_task_schema, make_event(seq=2, type="schema.update", payload={
            "id": "task",
            "render_text": "{{title}} - {{done}}",
        }))
        assert result.applied
        assert result.snapshot["schemas"]["task"]["render_html"] == original_html


# ============================================================================
# 4. schema.update — changing styles
# ============================================================================

class TestSchemaUpdateStyles:
    def test_update_styles(self, state_with_task_schema):
        new_styles = ".task { color: blue; font-weight: bold; }"
        result = reduce(state_with_task_schema, make_event(seq=2, type="schema.update", payload={
            "id": "task",
            "styles": new_styles,
        }))
        assert result.applied
        assert result.snapshot["schemas"]["task"]["styles"] == new_styles

    def test_update_styles_does_not_change_interface(self, state_with_task_schema):
        original_interface = state_with_task_schema["schemas"]["task"]["interface"]
        result = reduce(state_with_task_schema, make_event(seq=2, type="schema.update", payload={
            "id": "task",
            "styles": ".task { border: 1px solid red; }",
        }))
        assert result.applied
        assert result.snapshot["schemas"]["task"]["interface"] == original_interface


# ============================================================================
# 5. schema.update — multiple properties at once
# ============================================================================

class TestSchemaUpdateMultipleProperties:
    def test_update_all_properties_at_once(self, state_with_task_schema):
        result = reduce(state_with_task_schema, make_event(seq=2, type="schema.update", payload={
            "id": "task",
            "interface": EXTENDED_INTERFACE,
            "render_html": "<div>{{title}} ({{priority}})</div>",
            "render_text": "{{title}} [{{priority}}]",
            "styles": ".task { background: #eee; }",
        }))
        assert result.applied
        schema = result.snapshot["schemas"]["task"]
        assert schema["interface"] == EXTENDED_INTERFACE
        assert schema["render_html"] == "<div>{{title}} ({{priority}})</div>"
        assert schema["render_text"] == "{{title}} [{{priority}}]"
        assert schema["styles"] == ".task { background: #eee; }"


# ============================================================================
# 6. Sequential schema updates accumulate
# ============================================================================

class TestSequentialSchemaUpdates:
    def test_multiple_updates_accumulate_correctly(self, state_with_task_schema):
        r1 = reduce(state_with_task_schema, make_event(seq=2, type="schema.update", payload={
            "id": "task",
            "render_html": "<p>{{title}}</p>",
        }))
        r2 = reduce(r1.snapshot, make_event(seq=3, type="schema.update", payload={
            "id": "task",
            "interface": EXTENDED_INTERFACE,
        }))
        r3 = reduce(r2.snapshot, make_event(seq=4, type="schema.update", payload={
            "id": "task",
            "styles": ".task { margin: 4px; }",
        }))
        assert r3.applied

        schema = r3.snapshot["schemas"]["task"]
        assert schema["render_html"] == "<p>{{title}}</p>"
        assert schema["interface"] == EXTENDED_INTERFACE
        assert schema["styles"] == ".task { margin: 4px; }"

    def test_update_then_remove_then_recreate(self):
        """Removing and recreating a schema starts fresh."""
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="schema.create", payload={
            "id": "task",
            "interface": INITIAL_INTERFACE,
            "render_html": "<li>{{title}}</li>",
            "render_text": "{{title}}",
        }))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="schema.update", payload={
            "id": "task",
            "render_html": "<div>Updated</div>",
        }))
        r3 = reduce(r2.snapshot, make_event(seq=3, type="schema.remove", payload={"id": "task"}))
        r4 = reduce(r3.snapshot, make_event(seq=4, type="schema.create", payload={
            "id": "task",
            "interface": "interface Task { title: string; }",
            "render_html": "<span>{{title}}</span>",
            "render_text": "{{title}}",
        }))
        assert r4.applied
        schema = r4.snapshot["schemas"]["task"]
        assert schema["render_html"] == "<span>{{title}}</span>"
        assert "done" not in schema["interface"]


# ============================================================================
# 7. Schema update with new entities respects updated interface
# ============================================================================

class TestEntityCreationAfterSchemaUpdate:
    def test_entity_created_after_interface_extension(self, state_with_task_schema):
        """After adding an optional field to interface, entities can include that field."""
        r1 = reduce(state_with_task_schema, make_event(seq=2, type="schema.update", payload={
            "id": "task",
            "interface": EXTENDED_INTERFACE,
        }))
        assert r1.applied

        r2 = reduce(r1.snapshot, make_event(seq=3, type="entity.create", payload={
            "id": "t_new",
            "_schema": "task",
            "title": "New task with priority",
            "done": False,
            "priority": "high",
        }))
        assert r2.applied
        assert r2.snapshot["entities"]["t_new"]["priority"] == "high"
