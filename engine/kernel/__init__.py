"""
AIde Kernel

apply(snapshot, event) → ApplyResult (pure, deterministic)
"""

from engine.kernel.kernel import ApplyResult, apply, apply_all, empty_snapshot, replay

__all__ = [
    "apply",
    "apply_all",
    "empty_snapshot",
    "replay",
    "ApplyResult",
]
