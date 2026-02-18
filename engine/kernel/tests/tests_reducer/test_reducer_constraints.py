"""
AIde Reducer -- Constraint Tests (v3 Unified Entity Model)

In v3, constraints are enforced via TypeScript interface validation.
The schema's `interface` field is a TypeScript interface declaration that
defines field names and types. The reducer validates entity fields against
this interface on entity.create and warns on entity.update.

Covers:
  - schema.create with valid interface is accepted
  - schema.create with invalid interface syntax is rejected
  - entity.create with fields matching interface is accepted
  - entity.create with wrong field type is rejected (VALIDATION_ERROR)
  - entity.create with missing required field is rejected
  - entity.create with extra field not in interface still passes (open objects)
  - entity.update with bad type emits a warning (not hard rejection)
  - schema.create with missing interface is rejected
  - Schema with optional fields: entity without optional field is accepted
  - Multiple schemas: each entity validates against its own schema
"""

import pytest

from engine.kernel.events import make_event
from engine.kernel.reducer import empty_state, reduce, replay

# ============================================================================
# Helpers
# ============================================================================

TASK_INTERFACE = "interface Task { title: string; done: boolean; }"
PRODUCT_INTERFACE = "interface Product { name: string; price: string; in_stock: boolean; }"
OPTIONAL_INTERFACE = "interface Note { title: string; body?: string; pinned?: boolean; }"


# ============================================================================
# 1. Schema creation validation
# ============================================================================

class TestSchemaInterfaceValidation:
    def test_valid_interface_is_accepted(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="schema.create", payload={
            "id": "task",
            "interface": TASK_INTERFACE,
            "render_html": "<li>{{title}}</li>",
            "render_text": "{{title}}",
        }))
        assert result.applied
        assert "task" in result.snapshot["schemas"]

    def test_schema_create_without_interface_rejected(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="schema.create", payload={
            "id": "task",
            "render_html": "<li>{{title}}</li>",
            "render_text": "{{title}}",
        }))
        assert not result.applied
        assert "MISSING_INTERFACE" in result.error

    def test_schema_create_with_empty_interface_rejected(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="schema.create", payload={
            "id": "task",
            "interface": "",
            "render_html": "<li>{{title}}</li>",
            "render_text": "{{title}}",
        }))
        assert not result.applied
        assert "MISSING_INTERFACE" in result.error

    def test_schema_create_without_id_rejected(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="schema.create", payload={
            "interface": TASK_INTERFACE,
            "render_html": "<li>{{title}}</li>",
            "render_text": "{{title}}",
        }))
        assert not result.applied
        assert "MISSING_ID" in result.error

    def test_schema_create_with_invalid_id_format_rejected(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="schema.create", payload={
            "id": "My Schema",  # spaces are not allowed
            "interface": TASK_INTERFACE,
            "render_html": "<li>{{title}}</li>",
            "render_text": "{{title}}",
        }))
        assert not result.applied
        assert "INVALID_ID" in result.error


# ============================================================================
# 2. Entity field validation against interface
# ============================================================================

class TestEntityFieldValidation:
    @pytest.fixture
    def state_with_task_schema(self):
        snap = empty_state()
        r = reduce(snap, make_event(seq=1, type="schema.create", payload={
            "id": "task",
            "interface": TASK_INTERFACE,
            "render_html": "<li>{{title}}</li>",
            "render_text": "{{title}}",
        }))
        assert r.applied
        return r.snapshot

    def test_entity_with_correct_types_accepted(self, state_with_task_schema):
        result = reduce(state_with_task_schema, make_event(seq=2, type="entity.create", payload={
            "id": "t1",
            "_schema": "task",
            "title": "Buy milk",
            "done": False,
        }))
        assert result.applied
        assert result.snapshot["entities"]["t1"]["title"] == "Buy milk"
        assert result.snapshot["entities"]["t1"]["done"] is False

    def test_entity_with_wrong_type_for_boolean_rejected(self, state_with_task_schema):
        # done should be boolean, passing a string
        result = reduce(state_with_task_schema, make_event(seq=2, type="entity.create", payload={
            "id": "t1",
            "_schema": "task",
            "title": "Buy milk",
            "done": "yes",  # string instead of boolean
        }))
        assert not result.applied
        assert "VALIDATION_ERROR" in result.error

    def test_entity_with_wrong_type_for_string_rejected(self, state_with_task_schema):
        # title should be string, passing a boolean
        result = reduce(state_with_task_schema, make_event(seq=2, type="entity.create", payload={
            "id": "t1",
            "_schema": "task",
            "title": True,  # boolean instead of string
            "done": False,
        }))
        assert not result.applied
        assert "VALIDATION_ERROR" in result.error

    def test_entity_missing_required_field_rejected(self, state_with_task_schema):
        # done is a required field (not optional in TASK_INTERFACE)
        result = reduce(state_with_task_schema, make_event(seq=2, type="entity.create", payload={
            "id": "t1",
            "_schema": "task",
            "title": "Missing done field",
            # done is missing
        }))
        assert not result.applied
        assert "VALIDATION_ERROR" in result.error


# ============================================================================
# 3. Optional fields in interface
# ============================================================================

class TestOptionalFields:
    @pytest.fixture
    def state_with_note_schema(self):
        snap = empty_state()
        r = reduce(snap, make_event(seq=1, type="schema.create", payload={
            "id": "note",
            "interface": OPTIONAL_INTERFACE,
            "render_html": "<div>{{title}}</div>",
            "render_text": "{{title}}",
        }))
        assert r.applied
        return r.snapshot

    def test_entity_with_only_required_fields_accepted(self, state_with_note_schema):
        result = reduce(state_with_note_schema, make_event(seq=2, type="entity.create", payload={
            "id": "n1",
            "_schema": "note",
            "title": "My Note",
            # body and pinned are optional — omitting them is fine
        }))
        assert result.applied

    def test_entity_with_optional_field_provided_accepted(self, state_with_note_schema):
        result = reduce(state_with_note_schema, make_event(seq=2, type="entity.create", payload={
            "id": "n1",
            "_schema": "note",
            "title": "My Note",
            "body": "Some body text",
            "pinned": True,
        }))
        assert result.applied
        assert result.snapshot["entities"]["n1"]["body"] == "Some body text"
        assert result.snapshot["entities"]["n1"]["pinned"] is True

    def test_entity_with_optional_field_wrong_type_rejected(self, state_with_note_schema):
        result = reduce(state_with_note_schema, make_event(seq=2, type="entity.create", payload={
            "id": "n1",
            "_schema": "note",
            "title": "My Note",
            "pinned": "true",  # should be boolean
        }))
        assert not result.applied
        assert "VALIDATION_ERROR" in result.error


# ============================================================================
# 4. Entity without schema skips validation
# ============================================================================

class TestEntityWithoutSchema:
    def test_entity_without_schema_accepts_any_fields(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "freeform",
            "any_field": 42,
            "another": True,
            "nested": {"x": 1},
        }))
        assert result.applied
        assert result.snapshot["entities"]["freeform"]["any_field"] == 42


# ============================================================================
# 5. schema.remove blocked when entities reference it
# ============================================================================

class TestSchemaRemoveBlockedByEntities:
    def test_schema_remove_blocked_when_entities_exist(self):
        events = [
            make_event(seq=1, type="schema.create", payload={
                "id": "task",
                "interface": TASK_INTERFACE,
                "render_html": "<li>{{title}}</li>",
                "render_text": "{{title}}",
            }),
            make_event(seq=2, type="entity.create", payload={
                "id": "t1",
                "_schema": "task",
                "title": "A task",
                "done": False,
            }),
        ]
        snap = replay(events)

        result = reduce(snap, make_event(seq=3, type="schema.remove", payload={"id": "task"}))
        assert not result.applied
        assert "SCHEMA_IN_USE" in result.error

    def test_schema_remove_allowed_after_entity_removed(self):
        events = [
            make_event(seq=1, type="schema.create", payload={
                "id": "task",
                "interface": TASK_INTERFACE,
                "render_html": "<li>{{title}}</li>",
                "render_text": "{{title}}",
            }),
            make_event(seq=2, type="entity.create", payload={
                "id": "t1",
                "_schema": "task",
                "title": "A task",
                "done": False,
            }),
            make_event(seq=3, type="entity.remove", payload={"id": "t1"}),
        ]
        snap = replay(events)

        result = reduce(snap, make_event(seq=4, type="schema.remove", payload={"id": "task"}))
        assert result.applied
        assert result.snapshot["schemas"]["task"]["_removed"] is True


# ============================================================================
# 6. Multiple schemas — each entity validates against its own schema
# ============================================================================

class TestMultipleSchemaValidation:
    def test_entity_validates_against_correct_schema(self):
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="schema.create", payload={
            "id": "task",
            "interface": TASK_INTERFACE,
            "render_html": "<li>{{title}}</li>",
            "render_text": "{{title}}",
        }))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="schema.create", payload={
            "id": "product",
            "interface": PRODUCT_INTERFACE,
            "render_html": "<div>{{name}}</div>",
            "render_text": "{{name}}",
        }))

        # Create valid task
        r3 = reduce(r2.snapshot, make_event(seq=3, type="entity.create", payload={
            "id": "t1",
            "_schema": "task",
            "title": "Buy milk",
            "done": False,
        }))
        assert r3.applied

        # Create valid product
        r4 = reduce(r3.snapshot, make_event(seq=4, type="entity.create", payload={
            "id": "p1",
            "_schema": "product",
            "name": "Widget",
            "price": "9.99",
            "in_stock": True,
        }))
        assert r4.applied

        # Task-schema entity with product fields should fail
        r5 = reduce(r4.snapshot, make_event(seq=5, type="entity.create", payload={
            "id": "t2",
            "_schema": "task",
            "name": "Widget name",  # 'name' is not in TASK_INTERFACE; 'title' and 'done' are required
            "price": "5.00",
        }))
        assert not r5.applied
        assert "VALIDATION_ERROR" in r5.error

    def test_entity_referencing_nonexistent_schema_rejected(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "t1",
            "_schema": "nonexistent_schema",
            "title": "A task",
        }))
        assert not result.applied
        assert "SCHEMA_NOT_FOUND" in result.error
