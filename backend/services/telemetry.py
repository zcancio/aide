"""
Telemetry service — tracks LLM call metrics and cost.

Usage:
    tracker = LLMCallTracker(aide_id=..., user_id=..., tier="L2", model="haiku")
    tracker.start()
    # stream tokens...
    tracker.mark_first_content()
    tracker.set_tokens(input_tokens=500, output_tokens=120)
    tracker.set_reducer_stats(emitted=5, accepted=4, rejected=1)
    await tracker.finish()   # persists to telemetry table
"""

from __future__ import annotations

import time
from decimal import Decimal
from uuid import UUID

from backend.models.telemetry import TelemetryEvent, TokenUsage, TurnTelemetry
from backend.repos import telemetry_repo

# ---------------------------------------------------------------------------
# Pricing (per 1M tokens, as of 2026)
# ---------------------------------------------------------------------------

_PRICING: dict[str, dict[str, float]] = {
    "haiku": {"input": 0.25, "output": 1.25, "cache_read": 0.03},
    "sonnet": {"input": 3.00, "output": 15.00, "cache_read": 0.30},
    "opus": {"input": 15.00, "output": 75.00, "cache_read": 1.50},
}


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
) -> Decimal:
    """
    Calculate cost in USD based on model pricing.

    Cache-read tokens are billed at a lower rate; they are subtracted
    from the regular input token count.
    """
    prices = _PRICING.get(model, _PRICING["sonnet"])

    regular_input = max(0, input_tokens - cache_read_tokens)

    cost = (
        (regular_input / 1_000_000) * prices["input"]
        + (cache_read_tokens / 1_000_000) * prices["cache_read"]
        + (output_tokens / 1_000_000) * prices["output"]
    )

    return Decimal(str(round(cost, 6)))


# ---------------------------------------------------------------------------
# LLMCallTracker
# ---------------------------------------------------------------------------


class LLMCallTracker:
    """Context manager for tracking LLM call metrics."""

    def __init__(
        self,
        aide_id: UUID,
        user_id: UUID | None,
        tier: str,
        model: str,
        prompt_ver: str = "v1.0",
        message_id: UUID | None = None,
    ) -> None:
        self.event = TelemetryEvent(
            aide_id=aide_id,
            user_id=user_id,
            event_type="llm_call",
            tier=tier,
            model=model,
            prompt_ver=prompt_ver,
            message_id=message_id,
        )
        self._start_time: float | None = None
        self._first_content_time: float | None = None

    def start(self) -> None:
        """Record the call start time."""
        self._start_time = time.perf_counter()

    def mark_first_content(self) -> None:
        """Record time-to-first-content (call once on first streamed token)."""
        if self._first_content_time is None and self._start_time is not None:
            self._first_content_time = time.perf_counter()
            self.event.ttfc_ms = int((self._first_content_time - self._start_time) * 1000)

    def set_tokens(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_read: int = 0,
        cache_write: int = 0,
    ) -> None:
        """Set token counts and compute cost."""
        self.event.input_tokens = input_tokens
        self.event.output_tokens = output_tokens
        self.event.cache_read_tokens = cache_read
        self.event.cache_write_tokens = cache_write
        if self.event.model:
            self.event.cost_usd = calculate_cost(self.event.model, input_tokens, output_tokens, cache_read)

    def set_reducer_stats(self, emitted: int, accepted: int, rejected: int) -> None:
        """Record how many primitives were emitted / accepted / rejected."""
        self.event.lines_emitted = emitted
        self.event.lines_accepted = accepted
        self.event.lines_rejected = rejected

    def set_escalation(self, reason: str) -> None:
        """Mark this call as an escalation event."""
        self.event.escalated = True
        self.event.escalation_reason = reason

    def set_error(self, error: str) -> None:
        """Record an error string."""
        self.event.error = error

    async def finish(self) -> int:
        """Finalize timing and persist the event. Returns the row id."""
        if self._start_time is not None:
            self.event.ttc_ms = int((time.perf_counter() - self._start_time) * 1000)
        return await telemetry_repo.record_event(self.event)


# ---------------------------------------------------------------------------
# TurnRecorder
# ---------------------------------------------------------------------------


class TurnRecorder:
    """
    Records telemetry for a single turn in eval-compatible format.

    Usage:
        recorder = TurnRecorder(aide_id, user_id)
        recorder.start_turn(turn_num=1, tier="L3", model="sonnet", message="hello")

        # During streaming...
        recorder.record_tool_call("mutate_entity", {"action": "create", "id": "x"})
        recorder.record_text_block("Here's what I did")
        recorder.mark_first_content()

        # After streaming...
        recorder.set_usage(input_tokens=1000, output_tokens=500, cache_read=200)
        await recorder.finish()
    """

    def __init__(self, aide_id: UUID, user_id: UUID) -> None:
        self._aide_id = aide_id
        self._user_id = user_id
        self._turn_num: int = 0
        self._tier: str = ""
        self._model: str = ""
        self._message: str = ""
        self._tool_calls: list[dict] = []
        self._text_blocks: list[dict | str] = []
        self._system_prompt: str | None = None
        self._usage: TokenUsage | None = None
        self._start_time: float = 0.0
        self._ttfc_ms: int | None = None
        self._ttc_ms: int | None = None
        self._validation: dict | None = None

    def start_turn(self, turn_num: int, tier: str, model: str, message: str) -> None:
        """Initialize turn recording."""
        self._turn_num = turn_num
        self._tier = tier
        self._model = model
        self._message = message
        self._tool_calls = []
        self._text_blocks = []
        self._start_time = time.perf_counter()

    def record_tool_call(self, name: str, tool_input: dict, timestamp_ms: int | None = None) -> None:
        """Record a tool call (mutate_entity, set_relationship, etc)."""
        tc = {"name": name, "input": tool_input}
        if timestamp_ms is not None:
            tc["timestamp_ms"] = timestamp_ms
        self._tool_calls.append(tc)

    def record_text_block(self, text: str, timestamp_ms: int | None = None) -> None:
        """Record a text block from the response."""
        if timestamp_ms is not None:
            self._text_blocks.append({"text": text, "timestamp_ms": timestamp_ms})
        else:
            self._text_blocks.append(text)

    def set_system_prompt(self, prompt: str) -> None:
        """Set the system prompt used for this turn."""
        self._system_prompt = prompt

    def mark_first_content(self) -> None:
        """Mark time-to-first-content."""
        if self._ttfc_ms is None and self._start_time:
            self._ttfc_ms = int((time.perf_counter() - self._start_time) * 1000)

    def set_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_read: int = 0,
        cache_creation: int = 0,
    ) -> None:
        """Set token usage from API response."""
        self._usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read=cache_read,
            cache_creation=cache_creation,
        )

    def set_validation(self, passed: bool, issues: list[str] = None) -> None:
        """Set validation result."""
        self._validation = {"passed": passed, "issues": issues or []}

    async def finish(self) -> UUID | None:
        """Finalize and persist the turn. Returns row ID or None if missing data."""
        if not self._usage:
            return None

        self._ttc_ms = int((time.perf_counter() - self._start_time) * 1000)
        if self._ttfc_ms is None:
            self._ttfc_ms = self._ttc_ms

        turn = TurnTelemetry(
            turn=self._turn_num,
            tier=self._tier,
            model=self._model,
            message=self._message,
            tool_calls=self._tool_calls,
            text_blocks=self._text_blocks,
            system_prompt=self._system_prompt,
            usage=self._usage,
            ttfc_ms=self._ttfc_ms,
            ttc_ms=self._ttc_ms,
            validation=self._validation,
        )

        return await telemetry_repo.insert_turn(self._user_id, self._aide_id, turn)
