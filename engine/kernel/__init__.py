"""
AIde Kernel — the pure engine.

Components:
  primitives  — validation layer for declarative operations
  reducer_v2  — (snapshot, event) → ReduceResult (pure, deterministic, flat entity model)
  react_preview — React component rendering
"""

from engine.kernel.primitives import validate_primitive
from engine.kernel.reducer_v2 import empty_snapshot, reduce

__all__ = [
    "validate_primitive",
    "empty_snapshot",
    "reduce",
]
