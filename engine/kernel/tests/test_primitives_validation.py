"""
AIde Primitives — Validation Tests

Tests for primitive payload validation (structural checks).
The validator checks if payloads are well-formed before they reach the reducer.
"""

import pytest

from engine.kernel.primitives import validate_primitive


# ============================================================================
# grid.create Validation Tests
# ============================================================================


class TestGridCreateValidation:
    def test_valid_grid_create(self):
        """Valid grid.create payload should pass validation."""
        errors = validate_primitive(
            "grid.create",
            {
                "collection": "squares",
                "rows": 10,
                "cols": 10,
            },
        )
        assert errors == []

    def test_valid_grid_create_with_defaults(self):
        """grid.create with defaults should pass validation."""
        errors = validate_primitive(
            "grid.create",
            {
                "collection": "squares",
                "rows": 10,
                "cols": 10,
                "defaults": {"owner": "Unclaimed"},
            },
        )
        assert errors == []

    def test_missing_collection(self):
        """grid.create without collection should fail."""
        errors = validate_primitive(
            "grid.create",
            {
                "rows": 10,
                "cols": 10,
            },
        )
        assert len(errors) == 1
        assert "collection" in errors[0].lower()

    def test_invalid_collection_id(self):
        """grid.create with invalid collection ID should fail."""
        errors = validate_primitive(
            "grid.create",
            {
                "collection": "invalid id with spaces",
                "rows": 10,
                "cols": 10,
            },
        )
        assert len(errors) == 1
        assert "collection" in errors[0].lower()

    def test_missing_rows(self):
        """grid.create without rows should fail."""
        errors = validate_primitive(
            "grid.create",
            {
                "collection": "squares",
                "cols": 10,
            },
        )
        assert len(errors) == 1
        assert "rows" in errors[0].lower()

    def test_missing_cols(self):
        """grid.create without cols should fail."""
        errors = validate_primitive(
            "grid.create",
            {
                "collection": "squares",
                "rows": 10,
            },
        )
        assert len(errors) == 1
        assert "cols" in errors[0].lower()

    def test_invalid_rows_type(self):
        """grid.create with non-integer rows should fail."""
        errors = validate_primitive(
            "grid.create",
            {
                "collection": "squares",
                "rows": "10",
                "cols": 10,
            },
        )
        assert len(errors) >= 1
        assert "rows" in errors[0].lower()

    def test_invalid_cols_type(self):
        """grid.create with non-integer cols should fail."""
        errors = validate_primitive(
            "grid.create",
            {
                "collection": "squares",
                "rows": 10,
                "cols": "10",
            },
        )
        assert len(errors) >= 1
        assert "cols" in errors[0].lower()

    def test_zero_rows(self):
        """grid.create with zero rows should fail."""
        errors = validate_primitive(
            "grid.create",
            {
                "collection": "squares",
                "rows": 0,
                "cols": 10,
            },
        )
        assert len(errors) >= 1
        assert "rows" in errors[0].lower()

    def test_negative_rows(self):
        """grid.create with negative rows should fail."""
        errors = validate_primitive(
            "grid.create",
            {
                "collection": "squares",
                "rows": -1,
                "cols": 10,
            },
        )
        assert len(errors) >= 1
        assert "rows" in errors[0].lower()

    def test_zero_cols(self):
        """grid.create with zero cols should fail."""
        errors = validate_primitive(
            "grid.create",
            {
                "collection": "squares",
                "rows": 10,
                "cols": 0,
            },
        )
        assert len(errors) >= 1
        assert "cols" in errors[0].lower()

    def test_negative_cols(self):
        """grid.create with negative cols should fail."""
        errors = validate_primitive(
            "grid.create",
            {
                "collection": "squares",
                "rows": 10,
                "cols": -5,
            },
        )
        assert len(errors) >= 1
        assert "cols" in errors[0].lower()


# ============================================================================
# General Validation Tests
# ============================================================================


class TestGeneralValidation:
    def test_unknown_primitive_type(self):
        """Unknown primitive type should fail validation."""
        errors = validate_primitive("unknown.type", {"foo": "bar"})
        assert len(errors) == 1
        assert "unknown" in errors[0].lower()

    def test_payload_must_be_dict(self):
        """Payload must be a dict, not a list or string."""
        errors = validate_primitive("entity.create", "not a dict")
        assert len(errors) >= 1
        assert "object" in errors[0].lower()

        errors = validate_primitive("entity.create", ["not", "a", "dict"])
        assert len(errors) >= 1
        assert "object" in errors[0].lower()
