"""Pydantic models for flight recorder replay API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class LLMCallSummary(BaseModel):
    """Summary of an LLM call for the replay UI."""

    call_id: str
    shadow: bool
    model: str
    tier: str  # "L2" or "L3"
    latency_ms: int
    prompt: str
    response: str
    usage: dict[str, int]
    error: str | None = None


class TurnSummary(BaseModel):
    """Turn metadata for the timeline (excludes large snapshot data)."""

    turn_id: str
    turn_index: int  # Sequential index for ordering
    timestamp: str
    source: str
    user_message: str
    response_text: str
    llm_calls: list[LLMCallSummary]
    primitives_emitted: list[dict[str, Any]]
    primitives_applied: int
    total_latency_ms: int
    error: str | None = None  # Turn-level error if failed


class FlightRecorderListResponse(BaseModel):
    """Response for listing all turns."""

    aide_id: str
    aide_title: str
    turns: list[TurnSummary]
