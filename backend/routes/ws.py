"""
WebSocket endpoint for real-time aide interaction.

Accepts connections at /ws/aide/{aide_id}, streams deltas back to the client
as the LLM processes tool calls through the reducer.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.config import settings
from backend.models.conversation import Message
from backend.models.telemetry import TelemetryEvent
from backend.repos import telemetry_repo
from backend.repos.aide_repo import AideRepo
from backend.repos.conversation_repo import ConversationRepo
from backend.services.streaming_orchestrator import StreamingOrchestrator
from engine.kernel.reducer import empty_snapshot, reduce

logger = logging.getLogger(__name__)

# UUID regex for validation
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)

aide_repo = AideRepo()
conversation_repo = ConversationRepo()


def _get_user_id_from_websocket(websocket: WebSocket) -> UUID | None:
    """
    Extract user_id from WebSocket session cookie.

    Returns None if not authenticated (allows unauthenticated connections for dev).
    """
    cookies = websocket.cookies
    session = cookies.get("session")
    if not session:
        return None

    try:
        payload = jwt.decode(session, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str:
            return UUID(user_id_str)
    except (jwt.InvalidTokenError, ValueError):
        pass

    return None


async def _load_snapshot(user_id: UUID | None, aide_id: str) -> dict[str, Any]:
    """
    Load snapshot from database for the given aide.

    Returns empty_snapshot() if aide not found or user not authenticated.
    """
    if not user_id or not _UUID_RE.match(aide_id):
        return empty_snapshot()

    try:
        aide = await aide_repo.get(user_id, UUID(aide_id))
        if aide and aide.state:
            state = aide.state
            if isinstance(state, dict) and "entities" in state:
                logger.info("ws: loaded %d entities for aide_id=%s", len(state.get("entities", {})), aide_id)
                return state
    except Exception as e:
        logger.warning("ws: failed to load snapshot for aide_id=%s: %s", aide_id, e)

    return empty_snapshot()


async def _save_snapshot(user_id: UUID | None, aide_id: str, snapshot: dict[str, Any]) -> None:
    """
    Save snapshot to database for the given aide.
    """
    if not user_id or not _UUID_RE.match(aide_id):
        return

    try:
        aide_uuid = UUID(aide_id)
        title = snapshot.get("meta", {}).get("title")
        await aide_repo.update_state(user_id, aide_uuid, snapshot, event_log=[], title=title)
        logger.info("ws: saved %d entities for aide_id=%s", len(snapshot.get("entities", {})), aide_id)
    except Exception as e:
        logger.warning("ws: failed to save snapshot for aide_id=%s: %s", aide_id, e)


async def _load_conversation(user_id: UUID | None, aide_id: str) -> tuple[list[dict[str, str]], UUID | None, int]:
    """
    Load conversation history for the given aide.

    Returns:
        Tuple of (conversation_messages, conversation_id, turn_num)
        - conversation_messages: List of {"role": "...", "content": "..."} dicts
        - conversation_id: UUID of the conversation if exists, None otherwise
        - turn_num: Current turn number (based on user messages count + 1)
    """
    if not user_id or not _UUID_RE.match(aide_id):
        return [], None, 1

    try:
        aide_uuid = UUID(aide_id)
        conversation = await conversation_repo.get_for_aide(user_id, aide_uuid)
        if conversation:
            # Convert Message objects to dict format for orchestrator
            messages = [{"role": m.role, "content": m.content} for m in conversation.messages]
            # Turn number is count of user messages + 1
            turn_num = sum(1 for m in conversation.messages if m.role == "user") + 1
            logger.info(
                "ws: loaded %d messages for aide_id=%s, turn_num=%d",
                len(messages),
                aide_id,
                turn_num,
            )
            return messages, conversation.id, turn_num
    except Exception as e:
        logger.warning("ws: failed to load conversation for aide_id=%s: %s", aide_id, e)

    return [], None, 1


async def _save_conversation_messages(
    user_id: UUID | None,
    aide_id: str,
    conversation_id: UUID | None,
    user_message: str,
    assistant_response: str,
) -> None:
    """
    Save user message and assistant response to conversation.

    Creates a new conversation if one doesn't exist.
    """
    if not user_id or not _UUID_RE.match(aide_id):
        return

    try:
        aide_uuid = UUID(aide_id)
        now = datetime.now(UTC)

        # Get or create conversation
        if not conversation_id:
            conversation = await conversation_repo.create(user_id, aide_uuid, channel="web")
            conversation_id = conversation.id
            logger.info("ws: created conversation for aide_id=%s", aide_id)

        # Append user message
        if user_message:
            await conversation_repo.append_message(
                user_id,
                conversation_id,
                Message(role="user", content=user_message, timestamp=now),
            )

        # Append assistant response
        if assistant_response:
            await conversation_repo.append_message(
                user_id,
                conversation_id,
                Message(role="assistant", content=assistant_response, timestamp=now),
            )

        logger.info("ws: saved conversation messages for aide_id=%s", aide_id)
    except Exception as e:
        logger.warning("ws: failed to save conversation for aide_id=%s: %s", aide_id, e)


router = APIRouter(tags=["websocket"])

# Types that the client cares about as entity mutations
_ENTITY_TYPES = {"entity.create", "entity.update", "entity.remove"}

# Types that update page metadata
_META_TYPES = {"meta.update"}

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
    user_id: UUID | None,
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

    # Persist the updated snapshot
    await _save_snapshot(user_id, aide_id, snapshot)

    # Record telemetry (best-effort — don't fail the edit if telemetry fails)
    try:
        # aide_id may be 'new' for unauthenticated Phase 1 sessions; skip telemetry
        if _UUID_RE.match(aide_id):
            event_record = TelemetryEvent(
                aide_id=UUID(aide_id),
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

    Loads existing snapshot from database on connection.
    Persists updated snapshot after each stream.end.
    """
    await websocket.accept()
    logger.info("WebSocket accepted: aide_id=%s", aide_id)

    # Get user_id from session cookie for DB access
    user_id = _get_user_id_from_websocket(websocket)

    # Load existing snapshot from database (or start empty for new aides)
    snapshot: dict[str, Any] = await _load_snapshot(user_id, aide_id)

    # Send existing entities to client on connection (hydrate client state)
    entities = snapshot.get("entities", {})
    if entities:
        # Send snapshot.start to signal hydration beginning
        await websocket.send_text(json.dumps({"type": "snapshot.start"}))
        # Send each entity as entity.create, sorted by _created_seq
        sorted_entities = sorted(entities.items(), key=lambda x: x[1].get("_created_seq", 0))
        for entity_id, entity_data in sorted_entities:
            delta = {"type": "entity.create", "id": entity_id, "data": entity_data}
            await websocket.send_text(json.dumps(delta))
        # Send meta if present
        meta = snapshot.get("meta", {})
        if meta:
            await websocket.send_text(json.dumps({"type": "meta.update", "data": meta}))
        # Send snapshot.end to signal hydration complete
        await websocket.send_text(json.dumps({"type": "snapshot.end"}))
        logger.info("ws: hydrated %d entities for aide_id=%s", len(entities), aide_id)

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

            # ── direct_edit ──────────────────────────────────────────
            if msg_type == "direct_edit":
                snapshot = await _handle_direct_edit(websocket, user_id, aide_id, snapshot, msg)
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

            # Load conversation history
            conversation_history, conversation_id, turn_num = await _load_conversation(user_id, aide_id)

            # Collect voice text during streaming for conversation history
            voice_texts: list[str] = []

            # Check for API key - required for LLM streaming
            if not settings.ANTHROPIC_API_KEY:
                await websocket.send_text(
                    json.dumps({"type": "stream.error", "error": "API key not configured"})
                )
                await websocket.send_text(json.dumps({"type": "stream.end", "message_id": message_id}))
                continue

            try:
                orchestrator = StreamingOrchestrator(
                    aide_id=aide_id,
                    snapshot=snapshot,
                    conversation=conversation_history,
                    api_key=settings.ANTHROPIC_API_KEY,
                    user_id=user_id,
                    turn_num=turn_num,
                )

                async for result in orchestrator.process_message(content):
                    # Check for interrupt request
                    if interrupt_requested:
                        logger.info("ws: stream interrupted message_id=%s", message_id)
                        break

                    result_type = result.get("type")

                    # Classification metadata
                    if result_type == "meta.classification":
                        logger.info(
                            "ws: tier=%s model=%s reason=%s",
                            result.get("tier"),
                            result.get("model"),
                            result.get("reason"),
                        )
                        continue

                    # Voice events
                    if result_type == "voice":
                        voice_text = result.get("text", "")
                        voice_texts.append(voice_text)
                        await websocket.send_text(json.dumps({"type": "voice", "text": voice_text}))
                        continue

                    # Event processed
                    if result_type == "event":
                        event = result.get("event", {})
                        snapshot = result.get("snapshot", snapshot)
                        event_type = event.get("t", "")

                        if ttfc is None:
                            ttfc = (time.monotonic() - start_time) * 1000

                        if event_type in _ENTITY_TYPES:
                            entity_id = event.get("id") or event.get("ref")
                            delta = _make_delta(event_type, entity_id, snapshot)
                            await websocket.send_text(json.dumps(delta))
                        elif event_type in _META_TYPES:
                            # Send meta update to client
                            meta = snapshot.get("meta", {})
                            await websocket.send_text(json.dumps({"type": "meta.update", "data": meta}))
                        continue

                    # Rejection
                    if result_type == "rejection":
                        logger.debug("ws: event rejected reason=%s", result.get("reason"))
                        continue

            except Exception as e:
                # Log the error and send error message to client
                logger.error("ws: LLM streaming failed: %s", e)
                try:
                    error_msg = "Anthropic API is temporarily unavailable. Please try again."
                    await websocket.send_text(json.dumps({"type": "stream.error", "error": error_msg}))
                except RuntimeError:
                    pass
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
                # Persist snapshot to database and R2
                await _save_snapshot(user_id, aide_id, snapshot)

                # Save conversation history (user message + assistant response)
                assistant_response = " ".join(voice_texts) if voice_texts else ""
                await _save_conversation_messages(user_id, aide_id, conversation_id, content, assistant_response)

                await websocket.send_text(json.dumps({"type": "stream.end", "message_id": message_id}))
            current_message_id = None

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: aide_id=%s", aide_id)
