"""
AIde Kernel — the pure engine.

Three components:
  primitives  — validation layer for the 25 declarative operations
  reducer     — (snapshot, event) → snapshot  (pure, deterministic)
  assembly    — coordinates reducer + react_preview + IO (R2, Postgres)

Query helpers (from renderer):
  apply_sort, apply_filter, resolve_view_entities, resolve_view_fields
"""

from engine.kernel.assembly import AideAssembly
from engine.kernel.primitives import validate_primitive
from engine.kernel.reducer import empty_state, reduce, replay
from engine.kernel.renderer import (
    apply_filter,
    apply_sort,
    resolve_view_entities,
    resolve_view_fields,
)

__all__ = [
    "validate_primitive",
    "reduce",
    "replay",
    "empty_state",
    "apply_sort",
    "apply_filter",
    "resolve_view_entities",
    "resolve_view_fields",
    "AideAssembly",
]
