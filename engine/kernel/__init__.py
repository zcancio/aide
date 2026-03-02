"""
AIde Kernel — the pure engine.

Components:
  primitives  — validation layer for declarative operations
  reducer     — (snapshot, event) → ReduceResult (pure, deterministic, flat entity model)
"""

from engine.kernel.primitives import validate_primitive
from engine.kernel.reducer import empty_snapshot, reduce

__all__ = [
    "validate_primitive",
    "empty_snapshot",
    "reduce",
]
