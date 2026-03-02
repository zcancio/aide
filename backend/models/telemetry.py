"""Pydantic models for telemetry events."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class TelemetryEvent(BaseModel):
    """A single telemetry event capturing metrics for an LLM call, edit, or undo."""

    aide_id: UUID
    user_id: UUID | None = None
    event_type: str  # 'llm_call', 'direct_edit', 'undo', 'escalation'

    # LLM call fields
    tier: str | None = None  # 'L2', 'L3', 'L4'
    model: str | None = None  # 'haiku', 'sonnet', 'opus'
    prompt_ver: str | None = None  # 'v1.0'
    ttfc_ms: int | None = None  # time to first content (ms)
    ttc_ms: int | None = None  # time to complete (ms)
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None

    # Reducer stats
    lines_emitted: int | None = None
    lines_accepted: int | None = None
    lines_rejected: int | None = None

    # Escalation
    escalated: bool = False
    escalation_reason: str | None = None

    # Cost
    cost_usd: Decimal | None = None

    # Direct edit fields
    edit_latency_ms: int | None = None

    # Context
    message_id: UUID | None = None
    error: str | None = None

    model_config = {"extra": "forbid"}


class TokenUsage(BaseModel):
    """Token usage with cache metrics."""

    input_tokens: int
    output_tokens: int
    cache_read: int = 0
    cache_creation: int = 0

    def cost(self, tier: str) -> float:
        """Calculate cost in dollars."""
        rates = {
            "L4": {"in": 5, "out": 25, "cache_read": 0.5, "cache_write": 6.25},
            "L3": {"in": 3, "out": 15, "cache_read": 0.3, "cache_write": 3.75},
        }
        r = rates.get(tier.split("->")[0], rates["L3"])
        return (
            self.input_tokens * r["in"] / 1e6
            + self.output_tokens * r["out"] / 1e6
            + self.cache_read * r["cache_read"] / 1e6
            + self.cache_creation * r["cache_write"] / 1e6
        )

    model_config = {"extra": "forbid"}


class TurnTelemetry(BaseModel):
    """Single turn - matches eval golden format."""

    turn: int
    tier: str
    model: str
    message: str
    tool_calls: list[dict]
    text_blocks: list[dict | str]
    system_prompt: str | None = None
    usage: TokenUsage
    ttfc_ms: int
    ttc_ms: int
    validation: dict | None = None

    model_config = {"extra": "forbid"}


class AideTelemetry(BaseModel):
    """Full telemetry for an aide - matches eval golden files."""

    aide_id: str
    name: str
    scenario_id: str | None = None
    pattern: str | None = None
    timestamp: str
    turns: list[TurnTelemetry]
    final_snapshot: dict | None = None

    model_config = {"extra": "forbid"}
