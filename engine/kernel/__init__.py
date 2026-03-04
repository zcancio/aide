"""
AIde Kernel — the pure reducer.

reduce(snapshot, event) → ReduceResult (pure, deterministic)
"""

from engine.kernel.reducer import empty_snapshot, reduce

__all__ = [
    "empty_snapshot",
    "reduce",
]
