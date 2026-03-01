"""
Tier classifier for LLM routing.

Routes user messages to appropriate tier:
- L3 (Sonnet): Compiler - handles updates after schema exists
- L4 (Sonnet): Architect - handles first messages (schema synthesis) and queries
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from backend.config import settings

Tier = Literal["L3", "L4"]


@dataclass
class ClassificationResult:
    """Result of classifying a user message."""

    tier: Tier
    reason: str


# Model mapping - uses settings for configurable models
TIER_MODELS = {
    "L3": settings.L3_MODEL,
    "L4": settings.L3_MODEL,  # L4 uses same as L3 for now
}

# Cache TTLs (seconds)
TIER_CACHE_TTL = {
    "L3": 3600,  # 1 hour
    "L4": 3600,  # 1 hour
}


def classify(
    message: str,
    snapshot: dict[str, Any],
    has_schema: bool,
) -> ClassificationResult:
    """
    Classify message to appropriate tier.

    Args:
        message: User's message text
        snapshot: Current aide snapshot
        has_schema: Whether any entities exist in the snapshot

    Returns:
        ClassificationResult with tier and reason
    """
    message_lower = message.lower()

    # L4: No schema exists yet (first message) - Architect builds initial structure
    if not has_schema or not snapshot.get("entities"):
        return ClassificationResult(tier="L4", reason="no_schema")

    # L4: Questions and queries
    # Check for question indicators
    question_keywords = ["?", "how many", "do we have", "is there", "what is", "who", "when", "where"]
    has_question = any(q in message_lower for q in question_keywords)

    if has_question:
        # Check if it's a pure query vs mutation+query
        mutation_keywords = ["add", "update", "change", "set", "remove", "delete", "rsvp", "mark", "claim"]
        has_mutation = any(k in message_lower for k in mutation_keywords)

        if not has_mutation:
            return ClassificationResult(tier="L4", reason="pure_query")

    # L3: Structural changes (escalation candidates)
    structural_keywords = [
        "add a section",
        "new section",
        "create a new",
        "add table",
        "new category",
        "reorganize",
        "restructure",
        "add column",
        "add field",
        "track",
    ]
    if any(k in message_lower for k in structural_keywords):
        return ClassificationResult(tier="L3", reason="structural_change")

    # L3: Complex multi-part messages (questions with mutations)
    if has_question:
        return ClassificationResult(tier="L3", reason="complex_message")

    # L3: Multiple "and" conjunctions suggest multiple intents
    if message.count(" and ") >= 2:
        return ClassificationResult(tier="L3", reason="complex_message")

    # L3: Many commas suggests list of items
    if message.count(",") >= 3:
        return ClassificationResult(tier="L3", reason="complex_message")

    # L3: Default for all updates when schema exists
    return ClassificationResult(tier="L3", reason="simple_update")
