"""
AIde Kernel

apply(snapshot, event) → ApplyResult (pure, deterministic)
"""

from engine.kernel.kernel import apply, apply_all, empty_snapshot, replay, ApplyResult

__all__ = [
    "apply",
    "apply_all",
    "empty_snapshot",
    "replay",
    "ApplyResult",
]
