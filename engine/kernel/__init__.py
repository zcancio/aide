"""
AIde Kernel — the pure engine.

Four components:
  primitives  — validation layer for the 25 declarative operations
  reducer     — (snapshot, event) → snapshot  (pure, deterministic)
  renderer    — (snapshot, blueprint) → HTML   (pure, deterministic)
  assembly    — coordinates reducer + renderer + IO (R2, Postgres)
"""

from engine.kernel.assembly import AideAssembly
from engine.kernel.primitives import validate_primitive
from engine.kernel.reducer import empty_state, reduce, replay
from engine.kernel.renderer import render

__all__ = [
    "validate_primitive",
    "reduce",
    "replay",
    "empty_state",
    "render",
    "AideAssembly",
]
