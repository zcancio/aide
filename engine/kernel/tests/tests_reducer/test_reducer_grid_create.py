"""
AIde Reducer — grid.create Tests

Tests for the grid.create primitive which batch-creates rows × cols entities.
Used for Super Bowl squares, bingo cards, seating charts, etc.
"""

import pytest

from engine.kernel.events import make_event
from engine.kernel.reducer import empty_state, reduce


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def empty():
    """Fresh empty state."""
    return empty_state()


@pytest.fixture
def state_with_grid_collection(empty):
    """State with a squares collection that has row/col fields."""
    result = reduce(
        empty,
        make_event(
            seq=1,
            type="collection.create",
            payload={
                "id": "squares",
                "name": "Super Bowl Squares",
                "schema": {
                    "row": "int",
                    "col": "int",
                    "owner": "string?",
                },
            },
        ),
    )
    assert result.applied
    return result.snapshot


@pytest.fixture
def state_with_collection_missing_row_col(empty):
    """State with a collection that lacks row/col fields."""
    result = reduce(
        empty,
        make_event(
            seq=1,
            type="collection.create",
            payload={
                "id": "items",
                "name": "Items",
                "schema": {
                    "name": "string",
                    "price": "float?",
                },
            },
        ),
    )
    assert result.applied
    return result.snapshot


# ============================================================================
# Happy Path Tests
# ============================================================================


class TestGridCreateHappyPath:
    def test_creates_correct_number_of_entities(self, state_with_grid_collection):
        """grid.create should create rows × cols entities."""
        result = reduce(
            state_with_grid_collection,
            make_event(
                seq=2,
                type="grid.create",
                payload={
                    "collection": "squares",
                    "rows": 10,
                    "cols": 10,
                },
            ),
        )

        assert result.applied
        assert result.error is None

        entities = result.snapshot["collections"]["squares"]["entities"]
        # Filter out _removed entities
        active_entities = [e for e in entities.values() if not e.get("_removed")]
        assert len(active_entities) == 100

    def test_entities_have_correct_row_col_values(self, state_with_grid_collection):
        """Each entity should have correct row and col field values."""
        result = reduce(
            state_with_grid_collection,
            make_event(
                seq=2,
                type="grid.create",
                payload={
                    "collection": "squares",
                    "rows": 3,
                    "cols": 3,
                },
            ),
        )

        assert result.applied
        entities = result.snapshot["collections"]["squares"]["entities"]

        # Check specific cells
        assert entities["cell_0_0"]["row"] == 0
        assert entities["cell_0_0"]["col"] == 0
        assert entities["cell_1_2"]["row"] == 1
        assert entities["cell_1_2"]["col"] == 2
        assert entities["cell_2_2"]["row"] == 2
        assert entities["cell_2_2"]["col"] == 2

    def test_nullable_fields_default_to_null(self, state_with_grid_collection):
        """Nullable fields (like owner) should default to null."""
        result = reduce(
            state_with_grid_collection,
            make_event(
                seq=2,
                type="grid.create",
                payload={
                    "collection": "squares",
                    "rows": 2,
                    "cols": 2,
                },
            ),
        )

        assert result.applied
        entities = result.snapshot["collections"]["squares"]["entities"]

        for entity in entities.values():
            assert entity["owner"] is None

    def test_entities_have_system_fields(self, state_with_grid_collection):
        """Entities should have _removed and _created_seq fields."""
        result = reduce(
            state_with_grid_collection,
            make_event(
                seq=2,
                type="grid.create",
                payload={
                    "collection": "squares",
                    "rows": 2,
                    "cols": 2,
                },
            ),
        )

        assert result.applied
        entities = result.snapshot["collections"]["squares"]["entities"]

        for entity in entities.values():
            assert entity["_removed"] is False
            assert entity["_created_seq"] == 2

    def test_small_grid(self, state_with_grid_collection):
        """Test a small 2x3 grid."""
        result = reduce(
            state_with_grid_collection,
            make_event(
                seq=2,
                type="grid.create",
                payload={
                    "collection": "squares",
                    "rows": 2,
                    "cols": 3,
                },
            ),
        )

        assert result.applied
        entities = result.snapshot["collections"]["squares"]["entities"]
        assert len(entities) == 6

        # Verify all expected cells exist
        expected_ids = [
            "cell_0_0", "cell_0_1", "cell_0_2",
            "cell_1_0", "cell_1_1", "cell_1_2",
        ]
        for cell_id in expected_ids:
            assert cell_id in entities

    def test_with_defaults(self, state_with_grid_collection):
        """Test grid.create with default values for optional fields."""
        result = reduce(
            state_with_grid_collection,
            make_event(
                seq=2,
                type="grid.create",
                payload={
                    "collection": "squares",
                    "rows": 2,
                    "cols": 2,
                    "defaults": {"owner": "Unclaimed"},
                },
            ),
        )

        assert result.applied
        entities = result.snapshot["collections"]["squares"]["entities"]

        for entity in entities.values():
            assert entity["owner"] == "Unclaimed"


# ============================================================================
# Rejection Tests
# ============================================================================


class TestGridCreateRejections:
    def test_rejects_nonexistent_collection(self, empty):
        """grid.create should reject when collection doesn't exist."""
        result = reduce(
            empty,
            make_event(
                seq=1,
                type="grid.create",
                payload={
                    "collection": "nonexistent",
                    "rows": 10,
                    "cols": 10,
                },
            ),
        )

        assert not result.applied
        assert "COLLECTION_NOT_FOUND" in result.error

    def test_rejects_collection_without_row_field(self, state_with_collection_missing_row_col):
        """grid.create should reject when collection lacks row field."""
        result = reduce(
            state_with_collection_missing_row_col,
            make_event(
                seq=2,
                type="grid.create",
                payload={
                    "collection": "items",
                    "rows": 10,
                    "cols": 10,
                },
            ),
        )

        assert not result.applied
        assert "SCHEMA_MISMATCH" in result.error

    def test_rejects_removed_collection(self, state_with_grid_collection):
        """grid.create should reject when collection is removed."""
        # First remove the collection
        result = reduce(
            state_with_grid_collection,
            make_event(
                seq=2,
                type="collection.remove",
                payload={"id": "squares"},
            ),
        )
        snapshot = result.snapshot

        # Try to create grid in removed collection
        result = reduce(
            snapshot,
            make_event(
                seq=3,
                type="grid.create",
                payload={
                    "collection": "squares",
                    "rows": 10,
                    "cols": 10,
                },
            ),
        )

        assert not result.applied
        assert "COLLECTION_NOT_FOUND" in result.error or "COLLECTION_REMOVED" in result.error


# ============================================================================
# Edge Cases
# ============================================================================


class TestGridCreateEdgeCases:
    def test_single_cell_grid(self, state_with_grid_collection):
        """1x1 grid should create exactly one entity."""
        result = reduce(
            state_with_grid_collection,
            make_event(
                seq=2,
                type="grid.create",
                payload={
                    "collection": "squares",
                    "rows": 1,
                    "cols": 1,
                },
            ),
        )

        assert result.applied
        entities = result.snapshot["collections"]["squares"]["entities"]
        assert len(entities) == 1
        assert "cell_0_0" in entities
        assert entities["cell_0_0"]["row"] == 0
        assert entities["cell_0_0"]["col"] == 0

    def test_single_row_grid(self, state_with_grid_collection):
        """1xN grid (single row)."""
        result = reduce(
            state_with_grid_collection,
            make_event(
                seq=2,
                type="grid.create",
                payload={
                    "collection": "squares",
                    "rows": 1,
                    "cols": 5,
                },
            ),
        )

        assert result.applied
        entities = result.snapshot["collections"]["squares"]["entities"]
        assert len(entities) == 5

        for col in range(5):
            assert entities[f"cell_0_{col}"]["row"] == 0
            assert entities[f"cell_0_{col}"]["col"] == col

    def test_single_column_grid(self, state_with_grid_collection):
        """Nx1 grid (single column)."""
        result = reduce(
            state_with_grid_collection,
            make_event(
                seq=2,
                type="grid.create",
                payload={
                    "collection": "squares",
                    "rows": 5,
                    "cols": 1,
                },
            ),
        )

        assert result.applied
        entities = result.snapshot["collections"]["squares"]["entities"]
        assert len(entities) == 5

        for row in range(5):
            assert entities[f"cell_{row}_0"]["row"] == row
            assert entities[f"cell_{row}_0"]["col"] == 0
