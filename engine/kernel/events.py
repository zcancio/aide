"""
AIde Kernel — Event Construction

Factory functions for creating well-formed events.
Used by the orchestrator to wrap primitives before feeding them to the reducer,
and by tests to build events concisely.
"""

from __future__ import annotations

from typing import Any

from engine.kernel.types import Event, now_iso


def make_event(
    seq: int,
    type: str,
    payload: dict[str, Any],
    *,
    actor: str = "user_test",
    source: str = "web",
    intent: str | None = None,
    message: str | None = None,
    message_id: str | None = None,
    timestamp: str | None = None,
    event_id: str | None = None,
) -> Event:
    """
    Build a complete Event from minimal inputs.

    seq is required — it determines both the event ID and sequence number.
    Everything else has sensible defaults for testing.
    """
    ts = timestamp or now_iso()
    eid = event_id or f"evt_{ts[:10].replace('-', '')}_{seq:03d}"

    return Event(
        id=eid,
        sequence=seq,
        timestamp=ts,
        actor=actor,
        source=source,
        type=type,
        payload=payload,
        intent=intent,
        message=message,
        message_id=message_id,
    )


def assign_metadata(
    events: list[dict[str, Any]],
    *,
    start_sequence: int,
    actor: str,
    source: str,
    message: str | None = None,
    message_id: str | None = None,
) -> list[Event]:
    """
    Assign metadata to a batch of raw primitives (type + payload dicts)
    coming from the AI compiler. Returns fully formed Events.

    Used by the assembly layer's apply() method.
    """
    ts = now_iso()
    result: list[Event] = []

    for i, primitive in enumerate(events):
        seq = start_sequence + i
        result.append(
            Event(
                id=f"evt_{ts[:10].replace('-', '')}_{seq:03d}",
                sequence=seq,
                timestamp=ts,
                actor=actor,
                source=source,
                type=primitive["type"],
                payload=primitive["payload"],
                intent=primitive.get("intent"),
                message=message if i == 0 else None,  # attach message to first event only
                message_id=message_id if i == 0 else None,
            )
        )

    return result
