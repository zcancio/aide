"""Flight recorder — captures all data for one AI turn."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass
class LLMCallRecord:
    """Record of a single LLM call (production or shadow)."""

    call_id: str
    shadow: bool
    model: str
    tier: str  # "L2" or "L3"
    prompt: str
    response: str
    usage: dict[str, int]
    latency_ms: int
    error: str | None = None


@dataclass
class TurnRecord:
    """Complete record for one AI turn."""

    turn_id: str
    aide_id: str
    user_id: str
    timestamp: str
    source: str
    user_message: str
    snapshot_before: dict[str, Any]
    snapshot_after: dict[str, Any]
    llm_calls: list[LLMCallRecord]
    primitives_emitted: list[dict[str, Any]]
    primitives_applied: int
    response_text: str
    total_latency_ms: int
    error: str | None = None  # Turn-level error (AI failure, grid resolution, etc.)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSONL storage."""
        return {
            "turn_id": self.turn_id,
            "aide_id": self.aide_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "user_message": self.user_message,
            "snapshot_before": self.snapshot_before,
            "snapshot_after": self.snapshot_after,
            "llm_calls": [
                {
                    "call_id": c.call_id,
                    "shadow": c.shadow,
                    "model": c.model,
                    "tier": c.tier,
                    "prompt": c.prompt,
                    "response": c.response,
                    "usage": c.usage,
                    "latency_ms": c.latency_ms,
                    "error": c.error,
                }
                for c in self.llm_calls
            ],
            "primitives_emitted": self.primitives_emitted,
            "primitives_applied": self.primitives_applied,
            "response_text": self.response_text,
            "total_latency_ms": self.total_latency_ms,
            "error": self.error,
        }


class FlightRecorder:
    """
    Captures all data for one AI turn.

    Usage:
        recorder = FlightRecorder()
        recorder.start_turn(turn_id, aide_id, user_id, source, message, snapshot_before)
        recorder.record_llm_call(...)
        record = recorder.end_turn(snapshot_after, primitives_emitted, primitives_applied, response_text)
    """

    def __init__(self) -> None:
        """Initialize recorder (one instance per turn)."""
        self._turn_id: str = ""
        self._aide_id: str = ""
        self._user_id: str = ""
        self._timestamp: str = ""
        self._source: str = ""
        self._user_message: str = ""
        self._snapshot_before: dict[str, Any] = {}
        self._llm_calls: list[LLMCallRecord] = []
        self._start_time: float = 0.0

    def start_turn(
        self,
        turn_id: str,
        aide_id: str,
        user_id: str,
        source: str,
        user_message: str,
        snapshot_before: dict[str, Any],
    ) -> None:
        """
        Begin recording a turn.

        Args:
            turn_id: Unique ID for this turn
            aide_id: Aide UUID
            user_id: User UUID
            source: Message source ("web", "signal")
            user_message: Raw user message text
            snapshot_before: Snapshot state before any mutations
        """
        self._turn_id = turn_id
        self._aide_id = aide_id
        self._user_id = user_id
        self._timestamp = datetime.now(UTC).isoformat()
        self._source = source
        self._user_message = user_message
        self._snapshot_before = snapshot_before
        self._llm_calls = []
        self._start_time = time.monotonic()

    def record_llm_call(
        self,
        shadow: bool,
        model: str,
        tier: str,
        prompt: str,
        response: str,
        usage: dict[str, int],
        latency_ms: int,
        error: str | None = None,
    ) -> None:
        """
        Record the result of one LLM call.

        Args:
            shadow: True if this is a shadow call (not applied to state)
            model: Model name used
            tier: "L2" or "L3"
            prompt: User-facing prompt content sent to model
            response: Raw model response text
            usage: Token usage dict with input_tokens and output_tokens
            latency_ms: Elapsed milliseconds for the call
            error: Error message if call failed, None on success
        """
        self._llm_calls.append(
            LLMCallRecord(
                call_id=f"call_{uuid.uuid4().hex[:8]}",
                shadow=shadow,
                model=model,
                tier=tier,
                prompt=prompt,
                response=response,
                usage=usage,
                latency_ms=latency_ms,
                error=error,
            )
        )

    def end_turn(
        self,
        snapshot_after: dict[str, Any],
        primitives_emitted: list[dict[str, Any]],
        primitives_applied: int,
        response_text: str,
        error: str | None = None,
    ) -> TurnRecord:
        """
        Finalize the turn and produce a TurnRecord.

        Args:
            snapshot_after: Snapshot state after mutations
            primitives_emitted: All primitives returned by LLM
            primitives_applied: Count of primitives that passed reducer
            response_text: Response text shown to user
            error: Turn-level error message if the turn failed

        Returns:
            Complete TurnRecord ready for upload
        """
        total_latency_ms = int((time.monotonic() - self._start_time) * 1000)

        return TurnRecord(
            turn_id=self._turn_id,
            aide_id=self._aide_id,
            user_id=self._user_id,
            timestamp=self._timestamp,
            source=self._source,
            user_message=self._user_message,
            snapshot_before=self._snapshot_before,
            snapshot_after=snapshot_after,
            llm_calls=list(self._llm_calls),
            primitives_emitted=primitives_emitted,
            primitives_applied=primitives_applied,
            response_text=response_text,
            total_latency_ms=total_latency_ms,
            error=error,
        )
