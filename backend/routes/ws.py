"""
WebSocket endpoint for real-time aide interaction.

Accepts connections at /ws/aide/{aide_id}, streams deltas back to the client
as the MockLLM processes each JSONL line through the v2 reducer.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.models.telemetry import TelemetryEvent
from backend.repos import telemetry_repo
from engine.kernel.mock_llm import MockLLM
from engine.kernel.reducer_v2 import empty_snapshot, reduce

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# Types that the client cares about as entity mutations
_ENTITY_TYPES = {"entity.create", "entity.update", "entity.remove"}

# Types that carry voice text to display in the chat
_VOICE_TYPES = {"voice"}


def _make_delta(event_type: str, entity_id: str | None, snapshot: dict) -> dict[str, Any]:
    """Build an EntityDelta payload for the given event."""
    if event_type == "entity.remove":
        return {"type": "entity.remove", "id": entity_id, "data": None}

    if entity_id and entity_id in snapshot.get("entities", {}):
        entity_data = snapshot["entities"][entity_id]
        return {"type": event_type, "id": entity_id, "data": entity_data}

    # Fallback: send the event type with no data (client will ignore gracefully)
    return {"type": event_type, "id": entity_id, "data": None}


async def _handle_direct_edit(
    websocket: WebSocket,
    aide_id: str,
    snapshot: dict[str, Any],
    msg: dict[str, Any],
) -> dict[str, Any]:
    """
    Handle a direct_edit message from the client.

    Protocol:
      Client sends: {"type": "direct_edit", "entity_id": "...", "field": "...", "value": "..."}
      Server applies entity.update through reducer and broadcasts delta.

    Returns the (possibly updated) snapshot.
    """
    start_ms = time.monotonic()

    entity_id: str | None = msg.get("entity_id")
    field: str | None = msg.get("field")
    value = msg.get("value")

    if not entity_id or not field:
        logger.warning("ws: direct_edit missing entity_id or field")
        await websocket.send_text(
            json.dumps({"type": "direct_edit.error", "error": "entity_id and field are required"})
        )
        return snapshot

    # Validate entity exists in current snapshot
    if entity_id not in snapshot.get("entities", {}):
        logger.warning("ws: direct_edit entity_id not found: %s", entity_id)
        await websocket.send_text(json.dumps({"type": "direct_edit.error", "error": f"Entity '{entity_id}' not found"}))
        return snapshot

    # Build entity.update event (v2 format: short keys; uses "ref" not "id")
    event: dict[str, Any] = {"t": "entity.update", "ref": entity_id, "p": {field: value}}

    result = reduce(snapshot, event)

    if not result.accepted:
        logger.warning(
            "ws: direct_edit reducer rejected: entity=%s field=%s reason=%s",
            entity_id,
            field,
            result.reason,
        )
        await websocket.send_text(
            json.dumps({"type": "direct_edit.error", "error": result.reason or "Reducer rejected edit"})
        )
        return snapshot

    snapshot = result.snapshot
    latency_ms = int((time.monotonic() - start_ms) * 1000)

    # Broadcast the delta back to the client
    delta = _make_delta("entity.update", entity_id, snapshot)
    await websocket.send_text(json.dumps(delta))

    logger.info(
        "ws: direct_edit applied aide_id=%s entity_id=%s field=%s latency=%dms",
        aide_id,
        entity_id,
        field,
        latency_ms,
    )

    # Record telemetry (best-effort — don't fail the edit if telemetry fails)
    try:
        # aide_id may be 'new' for unauthenticated Phase 1 sessions; skip telemetry
        import re

        _UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
        if _UUID_RE.match(aide_id):
            import uuid as _uuid

            event_record = TelemetryEvent(
                aide_id=_uuid.UUID(aide_id),
                event_type="direct_edit",
                edit_latency_ms=latency_ms,
            )
            await telemetry_repo.record_event(event_record)
    except Exception:
        logger.debug("ws: telemetry record failed (non-fatal)", exc_info=True)

    return snapshot


@router.websocket("/ws/aide/{aide_id}")
async def aide_websocket(websocket: WebSocket, aide_id: str) -> None:
    """
    Stream aide deltas to the client over WebSocket.

    Protocol:
      Client → Server:  {"type": "message", "content": "...", "message_id": "<uuid>"}
                        {"type": "interrupt"}
                        {"type": "set_profile", "profile": "realistic_l3"}
      Server → Client:  EntityDelta | VoiceDelta | StreamStatus

    For Phase 1, uses MockLLM with the "create_graduation" golden file.
    Authentication is intentionally skipped for Phase 1 (local dev only).
    """
    await websocket.accept()
    logger.info("WebSocket accepted: aide_id=%s", aide_id)

    # Per-connection state — start with an empty v2 snapshot
    snapshot: dict[str, Any] = empty_snapshot()
    mock_llm = MockLLM()
    current_profile = "realistic_l3"
    interrupt_requested = False
    current_message_id: str | None = None

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("ws: malformed message from client: %r", raw[:200])
                continue

            msg_type = msg.get("type")

            # ── interrupt ────────────────────────────────────────────
            if msg_type == "interrupt":
                interrupt_requested = True
                if current_message_id:
                    await websocket.send_text(
                        json.dumps({"type": "stream.interrupted", "message_id": current_message_id})
                    )
                    logger.info("ws: interrupt requested for message_id=%s", current_message_id)
                continue

            # ── set_profile ──────────────────────────────────────────
            if msg_type == "set_profile":
                profile = msg.get("profile", "realistic_l3")
                if profile in {"instant", "realistic_l2", "realistic_l3", "realistic_l4", "slow"}:
                    current_profile = profile
                    logger.info("ws: profile set to %s", current_profile)
                continue

            # ── direct_edit ──────────────────────────────────────────
            if msg_type == "direct_edit":
                snapshot = await _handle_direct_edit(websocket, aide_id, snapshot, msg)
                continue

            if msg_type != "message":
                continue

            content: str = msg.get("content", "")
            message_id: str = msg.get("message_id") or f"msg_{uuid.uuid4().hex[:8]}"
            current_message_id = message_id
            interrupt_requested = False

            # --- stream.start ---
            await websocket.send_text(json.dumps({"type": "stream.start", "message_id": message_id}))

            ttfc: float | None = None
            start_time = time.monotonic()

            # Buffer for partial lines
            line_buffer = ""
            # Batch buffering state
            in_batch = False
            batch_buffer: list[dict[str, Any]] = []

            # Pick scenario based on content (Phase 1: static golden files)
            scenario = _pick_scenario(content)

            try:
                async for line in mock_llm.stream(scenario, profile=current_profile):
                    # Check for interrupt request
                    if interrupt_requested:
                        logger.info("ws: stream interrupted message_id=%s", message_id)
                        break
                    # The mock LLM already yields one complete JSONL line per iteration.
                    # Parse the raw line and pass it directly to the v2 reducer
                    # (which expects the short-hand keys: t, p, id, parent, display).
                    line_buffer += line + "\n"
                    while "\n" in line_buffer:
                        raw_line, line_buffer = line_buffer.split("\n", 1)
                        raw_line = raw_line.strip()
                        if not raw_line:
                            continue
                        try:
                            event: dict[str, Any] = json.loads(raw_line)
                        except json.JSONDecodeError:
                            logger.warning("ws: malformed JSONL line: %r", raw_line[:200])
                            continue

                        # v2 reducer uses "t" for event type
                        event_type: str = event.get("t", "")

                        # Handle batch signals
                        if event_type == "batch.start":
                            in_batch = True
                            batch_buffer = []
                            continue

                        if event_type == "batch.end":
                            in_batch = False
                            # Apply all buffered events at once
                            for buffered_event in batch_buffer:
                                buffered_type = buffered_event.get("t", "")
                                result = reduce(snapshot, buffered_event)
                                if result.accepted:
                                    snapshot = result.snapshot
                                    if ttfc is None:
                                        ttfc = (time.monotonic() - start_time) * 1000
                                    if buffered_type in _ENTITY_TYPES:
                                        entity_id = buffered_event.get("id")
                                        delta = _make_delta(buffered_type, entity_id, snapshot)
                                        await websocket.send_text(json.dumps(delta))
                            batch_buffer = []
                            continue

                        if event_type in _VOICE_TYPES:
                            voice_text: str = event.get("text", "")
                            if voice_text:
                                await websocket.send_text(json.dumps({"type": "voice", "text": voice_text}))
                            continue

                        if event_type not in _ENTITY_TYPES and not event_type.startswith(
                            ("meta.", "style.", "collection.", "field.", "block.", "view.", "relationship.", "rel.")
                        ):
                            continue

                        # Buffer events during batch mode
                        if in_batch:
                            batch_buffer.append(event)
                            continue

                        # Apply to snapshot via v2 reducer (raw event, not expanded)
                        result = reduce(snapshot, event)

                        if result.accepted:
                            snapshot = result.snapshot

                            if ttfc is None:
                                ttfc = (time.monotonic() - start_time) * 1000

                            if event_type in _ENTITY_TYPES:
                                entity_id = event.get("id")
                                delta = _make_delta(event_type, entity_id, snapshot)
                                await websocket.send_text(json.dumps(delta))
                        else:
                            logger.debug(
                                "ws: reducer rejected %s (reason=%s)",
                                event_type,
                                result.reason,
                            )

            except FileNotFoundError:
                logger.error("ws: golden file not found for scenario=%s", scenario)
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "stream.error",
                            "message_id": message_id,
                            "error": f"Scenario '{scenario}' not found.",
                        }
                    )
                )
                continue

            ttc = (time.monotonic() - start_time) * 1000
            logger.info(
                "ws: turn complete aide_id=%s message_id=%s ttfc=%.0fms ttc=%.0fms interrupted=%s",
                aide_id,
                message_id,
                ttfc or 0,
                ttc,
                interrupt_requested,
            )

            # --- stream.end ---
            if not interrupt_requested:
                await websocket.send_text(json.dumps({"type": "stream.end", "message_id": message_id}))
            current_message_id = None

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: aide_id=%s", aide_id)


def _pick_scenario(content: str) -> str:
    """
    Choose a golden file scenario based on message content.

    Phase 1: simple keyword matching against available scenarios.
    """
    content_lower = content.lower()

    if any(kw in content_lower for kw in ("graduation", "party", "sophie")):
        return "create_graduation"
    if any(kw in content_lower for kw in ("poker", "card", "chips")):
        return "create_poker"
    if any(kw in content_lower for kw in ("inspo", "inspiration", "mood")):
        return "create_inspo"
    if any(kw in content_lower for kw in ("football", "squares", "grid", "pool")):
        return "create_football_squares"
    if any(kw in content_lower for kw in ("trip", "travel", "group")):
        return "create_group_trip"
    if any(kw in content_lower for kw in ("update", "add", "guest")):
        return "update_simple"

    # Default: graduation party demo
    return "create_graduation"
