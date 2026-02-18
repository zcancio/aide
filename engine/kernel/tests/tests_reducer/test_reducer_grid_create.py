"""
AIde Reducer -- Grid Create Tests (v3 Unified Entity Model)

In v3, grids are expressed through the `_shape` field on entity child
collections. A grid is a collection of cells where `_shape` describes
the layout dimensions (e.g., [8, 8] for a chessboard, [10, 10] for
football squares, [5, 7] for a custom grid).

There is no separate grid.create primitive — grids are just entities
with a `_shape` annotation on their child collections.

Covers:
  - entity.create with _shape in a nested collection
  - _shape is preserved through round-trip
  - Grid cells can be addressed by row/col identifier
  - Grid entity can be updated (add cells)
  - Multiple grids in the same snapshot
  - _shape on child collection vs _shape on the entity itself
  - Grid cell path addressing works
"""

import json

import pytest

from engine.kernel.events import make_event
from engine.kernel.reducer import empty_state, reduce

# ============================================================================
# Helpers
# ============================================================================


def snap_json(snap):
    return json.dumps(snap, sort_keys=True)


CHESSBOARD_INTERFACE = (
    "interface ChessCell { piece?: string; color: string; occupied: boolean; }"
)


# ============================================================================
# 1. entity.create with _shape in child collection
# ============================================================================

class TestGridCreateWithShape:
    def test_create_entity_with_shape_annotation(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "chessboard",
            "name": "Chess Board",
            "cells": {
                "_shape": [8, 8],
            },
        }))
        assert result.applied
        entity = result.snapshot["entities"]["chessboard"]
        assert entity["cells"]["_shape"] == [8, 8]

    def test_create_grid_with_initial_cells(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "ttt_board",
            "name": "Tic-Tac-Toe",
            "cells": {
                "_shape": [3, 3],
                "r0_c0": {"value": "X", "row": 0, "col": 0},
                "r0_c1": {"value": "", "row": 0, "col": 1},
                "r0_c2": {"value": "O", "row": 0, "col": 2},
            },
        }))
        assert result.applied
        cells = result.snapshot["entities"]["ttt_board"]["cells"]
        assert cells["_shape"] == [3, 3]
        assert cells["r0_c0"]["value"] == "X"
        assert cells["r0_c2"]["value"] == "O"

    def test_shape_survives_json_round_trip(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "football_squares",
            "name": "Super Bowl Squares",
            "cells": {
                "_shape": [10, 10],
            },
        }))
        assert result.applied
        rt = json.loads(json.dumps(result.snapshot, sort_keys=True))
        assert rt["entities"]["football_squares"]["cells"]["_shape"] == [10, 10]

    def test_custom_grid_shape(self):
        snap = empty_state()
        result = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "bingo_card",
            "name": "Bingo Card",
            "cells": {
                "_shape": [5, 5],
            },
        }))
        assert result.applied
        assert result.snapshot["entities"]["bingo_card"]["cells"]["_shape"] == [5, 5]


# ============================================================================
# 2. Grid cells addressed by row/col identifier
# ============================================================================

class TestGridCellAddressing:
    @pytest.fixture
    def state_with_grid(self):
        snap = empty_state()
        r = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "grid",
            "name": "My Grid",
            "cells": {
                "_shape": [3, 3],
            },
        }))
        assert r.applied
        return r.snapshot

    def test_update_grid_to_add_cells(self, state_with_grid):
        result = reduce(state_with_grid, make_event(seq=2, type="entity.update", payload={
            "id": "grid",
            "cells": {
                "r0_c0": {"value": "A", "row": 0, "col": 0},
                "r1_c1": {"value": "B", "row": 1, "col": 1},
                "r2_c2": {"value": "C", "row": 2, "col": 2},
            },
        }))
        assert result.applied
        cells = result.snapshot["entities"]["grid"]["cells"]
        assert cells["r0_c0"]["value"] == "A"
        assert cells["r1_c1"]["value"] == "B"
        assert cells["r2_c2"]["value"] == "C"
        # Shape preserved
        assert cells["_shape"] == [3, 3]

    def test_overwrite_cell_value(self, state_with_grid):
        r1 = reduce(state_with_grid, make_event(seq=2, type="entity.update", payload={
            "id": "grid",
            "cells": {
                "r0_c0": {"value": "X"},
            },
        }))
        r2 = reduce(r1.snapshot, make_event(seq=3, type="entity.update", payload={
            "id": "grid",
            "cells": {
                "r0_c0": {"value": "O"},
            },
        }))
        assert r2.applied
        assert r2.snapshot["entities"]["grid"]["cells"]["r0_c0"]["value"] == "O"

    def test_path_based_child_create_in_grid(self, state_with_grid):
        """Create a grid cell via path addressing."""
        result = reduce(state_with_grid, make_event(seq=2, type="entity.create", payload={
            "id": "grid/cells/r0_c0",
            "value": "X",
            "row": 0,
            "col": 0,
        }))
        assert result.applied
        cells = result.snapshot["entities"]["grid"]["cells"]
        assert cells["r0_c0"]["value"] == "X"


# ============================================================================
# 3. Multiple grids in same snapshot
# ============================================================================

class TestMultipleGrids:
    def test_two_grids_independent(self):
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "grid_8x8",
            "name": "Chessboard",
            "cells": {"_shape": [8, 8]},
        }))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="entity.create", payload={
            "id": "grid_10x10",
            "name": "Football Squares",
            "cells": {"_shape": [10, 10]},
        }))
        assert r2.applied

        entities = r2.snapshot["entities"]
        assert entities["grid_8x8"]["cells"]["_shape"] == [8, 8]
        assert entities["grid_10x10"]["cells"]["_shape"] == [10, 10]

    def test_update_one_grid_does_not_affect_other(self):
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "grid_a",
            "name": "Grid A",
            "cells": {"_shape": [3, 3]},
        }))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="entity.create", payload={
            "id": "grid_b",
            "name": "Grid B",
            "cells": {"_shape": [4, 4]},
        }))
        r3 = reduce(r2.snapshot, make_event(seq=3, type="entity.update", payload={
            "id": "grid_a",
            "cells": {"r0_c0": {"value": "X"}},
        }))
        assert r3.applied

        # grid_b is unaffected
        assert r3.snapshot["entities"]["grid_b"]["cells"]["_shape"] == [4, 4]
        assert "r0_c0" not in r3.snapshot["entities"]["grid_b"]["cells"]


# ============================================================================
# 4. Schema-backed grid
# ============================================================================

class TestSchemaBackedGrid:
    def test_grid_with_schema(self):
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="schema.create", payload={
            "id": "chess_cell",
            "interface": CHESSBOARD_INTERFACE,
            "render_html": "<div class='cell {{color}}'>{{piece}}</div>",
            "render_text": "{{piece}}",
        }))
        assert r1.applied

        r2 = reduce(r1.snapshot, make_event(seq=2, type="entity.create", payload={
            "id": "board",
            "name": "Chess Board",
            "cells": {
                "_shape": [8, 8],
                "r0_c0": {
                    "_schema": "chess_cell",
                    "piece": "rook",
                    "color": "dark",
                    "occupied": True,
                },
            },
        }))
        assert r2.applied

        cell = r2.snapshot["entities"]["board"]["cells"]["r0_c0"]
        assert cell["piece"] == "rook"
        assert cell["color"] == "dark"
        assert cell["occupied"] is True
        assert r2.snapshot["entities"]["board"]["cells"]["_shape"] == [8, 8]


# ============================================================================
# 5. Grid entity removal
# ============================================================================

class TestGridEntityRemoval:
    def test_removing_grid_entity_marks_removed(self):
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "my_grid",
            "name": "My Grid",
            "cells": {
                "_shape": [5, 5],
                "r0_c0": {"value": "A"},
            },
        }))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="entity.remove", payload={"id": "my_grid"}))
        assert r2.applied
        assert r2.snapshot["entities"]["my_grid"]["_removed"] is True


# ============================================================================
# 6. _shape on top-level entity vs on child collection
# ============================================================================

class TestShapeOnEntity:
    def test_shape_on_entity_via_update(self):
        """_shape can be set via entity.update on the entity itself."""
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "layout_grid",
            "name": "Layout Grid",
        }))
        assert r1.applied

        r2 = reduce(r1.snapshot, make_event(seq=2, type="entity.update", payload={
            "id": "layout_grid",
            "_shape": [4, 6],
        }))
        assert r2.applied
        assert r2.snapshot["entities"]["layout_grid"]["_shape"] == [4, 6]

    def test_shape_on_entity_update(self):
        snap = empty_state()
        r1 = reduce(snap, make_event(seq=1, type="entity.create", payload={
            "id": "layout_grid",
            "name": "Layout Grid",
        }))
        r2 = reduce(r1.snapshot, make_event(seq=2, type="entity.update", payload={
            "id": "layout_grid",
            "_shape": [3, 3],
        }))
        assert r2.applied
        assert r2.snapshot["entities"]["layout_grid"]["_shape"] == [3, 3]
