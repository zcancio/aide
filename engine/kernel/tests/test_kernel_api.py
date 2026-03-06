"""
TDD test for kernel API rename.

Tests the renamed kernel API: apply() instead of reduce().
"""

from engine.kernel import apply, empty_snapshot


class TestKernelAPI:
    """Tests for the renamed kernel API."""

    def test_apply_entity_create(self):
        """apply() creates an entity in the snapshot."""
        snap = empty_snapshot()
        event = {"t": "entity.create", "id": "test_entity", "p": {"name": "Test"}}
        result = apply(snap, event)
        assert result.accepted
        assert "test_entity" in result.snapshot["entities"]

    def test_apply_returns_reduce_result(self):
        """apply() returns a result with snapshot and accepted flag."""
        snap = empty_snapshot()
        event = {"t": "entity.create", "id": "item", "p": {}}
        result = apply(snap, event)
        assert hasattr(result, "snapshot")
        assert hasattr(result, "accepted")

    def test_empty_snapshot_still_works(self):
        """empty_snapshot() is unchanged."""
        snap = empty_snapshot()
        assert "entities" in snap
        assert "relationships" in snap
        assert "styles" in snap
        assert "meta" in snap
