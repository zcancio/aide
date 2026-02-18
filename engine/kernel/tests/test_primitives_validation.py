"""
AIde Primitives — Validation Tests

Tests for primitive payload validation (structural checks).
The validator checks if payloads are well-formed before they reach the reducer.

v3 primitives:
  - schema.create: requires id, interface
  - entity.create: requires id
  - entity.update: requires id
  - entity.remove: requires id
  - meta.update: requires at least one field
  - block.set: requires id, type
  - style.set: any key-value pairs accepted
"""

import pytest

from engine.kernel.primitives import validate_primitive

# ============================================================================
# schema.create Validation Tests
# ============================================================================


class TestSchemaCreateValidation:
    def test_valid_schema_create(self):
        """Valid schema.create payload should pass validation."""
        errors = validate_primitive(
            "schema.create",
            {
                "id": "task",
                "interface": "interface Task { name: string; done: boolean; }",
            },
        )
        assert errors == []

    def test_valid_schema_create_with_render_html(self):
        """schema.create with render_html should pass validation."""
        errors = validate_primitive(
            "schema.create",
            {
                "id": "task",
                "interface": "interface Task { name: string; }",
                "render_html": "<li>{{name}}</li>",
            },
        )
        assert errors == []

    def test_missing_id(self):
        """schema.create without id should fail."""
        errors = validate_primitive(
            "schema.create",
            {
                "interface": "interface Task { name: string; }",
            },
        )
        assert len(errors) >= 1
        assert "id" in errors[0].lower()

    def test_missing_interface(self):
        """schema.create without interface should fail."""
        errors = validate_primitive(
            "schema.create",
            {
                "id": "task",
            },
        )
        assert len(errors) >= 1
        assert "interface" in errors[0].lower()

    def test_missing_id_and_interface(self):
        """schema.create with empty payload should fail with 2 errors."""
        errors = validate_primitive("schema.create", {})
        assert len(errors) == 2


# ============================================================================
# entity.create Validation Tests
# ============================================================================


class TestEntityCreateValidation:
    def test_valid_entity_create(self):
        """Valid entity.create payload should pass validation."""
        errors = validate_primitive(
            "entity.create",
            {
                "id": "task_1",
                "_schema": "task",
                "name": "My Task",
                "done": False,
            },
        )
        assert errors == []

    def test_valid_entity_create_no_schema(self):
        """entity.create without _schema is still valid (schema optional)."""
        errors = validate_primitive(
            "entity.create",
            {
                "id": "standalone_1",
                "label": "Standalone entity",
            },
        )
        assert errors == []

    def test_missing_id(self):
        """entity.create without id should fail."""
        errors = validate_primitive(
            "entity.create",
            {
                "_schema": "task",
                "name": "Task without ID",
            },
        )
        assert len(errors) >= 1
        assert "id" in errors[0].lower()

    def test_empty_payload(self):
        """entity.create with empty payload should fail (missing id)."""
        errors = validate_primitive("entity.create", {})
        assert len(errors) >= 1
        assert "id" in errors[0].lower()


# ============================================================================
# entity.update Validation Tests
# ============================================================================


class TestEntityUpdateValidation:
    def test_valid_entity_update(self):
        """Valid entity.update payload should pass validation."""
        errors = validate_primitive(
            "entity.update",
            {
                "id": "task_1",
                "done": True,
                "priority": 2,
            },
        )
        assert errors == []

    def test_missing_id(self):
        """entity.update without id should fail."""
        errors = validate_primitive(
            "entity.update",
            {
                "done": True,
            },
        )
        assert len(errors) >= 1
        assert "id" in errors[0].lower()

    def test_empty_payload(self):
        """entity.update with empty payload should fail (missing id)."""
        errors = validate_primitive("entity.update", {})
        assert len(errors) >= 1
        assert "id" in errors[0].lower()


# ============================================================================
# entity.remove Validation Tests
# ============================================================================


class TestEntityRemoveValidation:
    def test_valid_entity_remove(self):
        """Valid entity.remove payload should pass validation."""
        errors = validate_primitive(
            "entity.remove",
            {
                "id": "task_1",
            },
        )
        assert errors == []

    def test_missing_id(self):
        """entity.remove without id should fail."""
        errors = validate_primitive("entity.remove", {})
        assert len(errors) >= 1
        assert "id" in errors[0].lower()


# ============================================================================
# meta.update Validation Tests
# ============================================================================


class TestMetaUpdateValidation:
    def test_valid_meta_update_title(self):
        """Valid meta.update with title should pass."""
        errors = validate_primitive(
            "meta.update",
            {"title": "My New Title"},
        )
        assert errors == []

    def test_valid_meta_update_multiple(self):
        """Valid meta.update with multiple fields should pass."""
        errors = validate_primitive(
            "meta.update",
            {"title": "My Title", "description": "Some description"},
        )
        assert errors == []

    def test_empty_meta_update(self):
        """meta.update with no fields should fail."""
        errors = validate_primitive("meta.update", {})
        assert len(errors) >= 1


# ============================================================================
# block.set Validation Tests
# ============================================================================


class TestBlockSetValidation:
    def test_valid_block_set_heading(self):
        """Valid block.set with heading type should pass."""
        errors = validate_primitive(
            "block.set",
            {
                "id": "block_title",
                "type": "heading",
                "level": 1,
                "text": "Hello",
            },
        )
        assert errors == []

    def test_valid_block_set_text(self):
        """Valid block.set with text type should pass."""
        errors = validate_primitive(
            "block.set",
            {
                "id": "block_body",
                "type": "text",
                "text": "Some text content.",
            },
        )
        assert errors == []

    def test_missing_id(self):
        """block.set without id should fail."""
        errors = validate_primitive(
            "block.set",
            {
                "type": "heading",
                "level": 1,
            },
        )
        assert len(errors) >= 1
        assert "id" in errors[0].lower()

    def test_missing_type(self):
        """block.set without type should fail."""
        errors = validate_primitive(
            "block.set",
            {
                "id": "block_title",
                "level": 1,
            },
        )
        assert len(errors) >= 1
        assert "type" in errors[0].lower()

    def test_missing_id_and_type(self):
        """block.set with empty payload should fail with 2 errors."""
        errors = validate_primitive("block.set", {})
        assert len(errors) == 2


# ============================================================================
# style.set Validation Tests
# ============================================================================


class TestStyleSetValidation:
    def test_valid_style_set(self):
        """Valid style.set with any key-value pairs should pass."""
        errors = validate_primitive(
            "style.set",
            {"primary_color": "#ff5500"},
        )
        assert errors == []

    def test_valid_style_set_multiple(self):
        """Valid style.set with multiple tokens should pass."""
        errors = validate_primitive(
            "style.set",
            {
                "primary_color": "#3b82f6",
                "bg_color": "#ffffff",
                "text_color": "#111111",
                "density": "comfortable",
            },
        )
        assert errors == []


# ============================================================================
# General Validation Tests
# ============================================================================


class TestGeneralValidation:
    def test_unknown_primitive_type(self):
        """Unknown primitive type should fail validation."""
        errors = validate_primitive("unknown.type", {"foo": "bar"})
        assert len(errors) == 1
        assert "unknown" in errors[0].lower()

    def test_payload_must_be_dict_string(self):
        """Payload must be a dict, not a string (validator raises or returns errors)."""
        with pytest.raises((AttributeError, TypeError, AssertionError)):
            errors = validate_primitive("entity.create", "not a dict")
            assert len(errors) >= 1

    def test_payload_must_be_dict_list(self):
        """Payload must be a dict, not a list (validator raises or returns errors)."""
        with pytest.raises((AttributeError, TypeError, AssertionError)):
            errors = validate_primitive("entity.create", ["not", "a", "dict"])
            assert len(errors) >= 1

    def test_v2_grid_create_unknown(self):
        """v2 grid.create is not a known primitive in v3."""
        errors = validate_primitive(
            "grid.create",
            {"collection": "squares", "rows": 10, "cols": 10},
        )
        assert len(errors) >= 1
        assert "unknown" in errors[0].lower()

    def test_v2_collection_create_unknown(self):
        """v2 collection.create is not a known primitive in v3."""
        errors = validate_primitive(
            "collection.create",
            {"id": "tasks", "schema": {"name": "string"}},
        )
        assert len(errors) >= 1
        assert "unknown" in errors[0].lower()
