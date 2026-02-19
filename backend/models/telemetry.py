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
    prompt_ver: str | None = None  # 'v2.1'
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
