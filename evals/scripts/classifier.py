"""
AIde Message Classifier — v3

Routing model:
  - First message (empty snapshot) → L4 (Opus)
  - Every subsequent message → L3 (Sonnet)
  - L2 (Haiku) shelved — not in routing path

That's the entire classifier.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Tier = Literal["L3", "L4"]


@dataclass
class ClassificationResult:
    tier: Tier
    model: str
    reason: str
    temperature: float


# Model mapping
TIER_MODELS = {
    "L4": "claude-opus-4-5-20251101",
    "L3": "claude-sonnet-4-5-20250929",
}

# Temperature per tier
TIER_TEMPERATURE = {
    "L4": 0.2,  # First message: slight exploration for schema synthesis
    "L3": 0,    # Compilation: deterministic
}

# Cache TTLs (seconds)
TIER_CACHE_TTL = {
    "L4": 3600,  # 1 hour (first messages are rare)
    "L3": 3600,  # 1 hour
}


def classify(message: str, snapshot: dict[str, Any]) -> ClassificationResult:
    """
    Classify message to appropriate tier.

    The entire routing logic:
      - If the aide has no entities → L4 (first message)
      - Otherwise → L3 (everything else)

    L3 self-escalates to L4 when it encounters schema evolution
    or structural changes it can't handle.
    """
    if not _has_entities(snapshot):
        return ClassificationResult(
            tier="L4",
            model=TIER_MODELS["L4"],
            reason="first_message",
            temperature=TIER_TEMPERATURE["L4"],
        )

    return ClassificationResult(
        tier="L3",
        model=TIER_MODELS["L3"],
        reason="subsequent_message",
        temperature=TIER_TEMPERATURE["L3"],
    )


def _has_entities(snapshot: dict[str, Any]) -> bool:
    """Check if the snapshot has any non-removed entities."""
    entities = snapshot.get("entities", {})
    return any(not e.get("_removed", False) for e in entities.values())
