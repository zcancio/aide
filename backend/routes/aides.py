"""Aide CRUD routes — list, create, get, update, archive, delete."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse

from backend.auth import get_current_user
from backend.models.aide import (
    AideResponse,
    CreateAideRequest,
    HydrateResponse,
    SaveConversationRequest,
    SaveStateRequest,
    SaveStateResponse,
    UpdateAideRequest,
)
from backend.models.conversation import ConversationHistoryResponse, MessageResponse
from backend.models.user import User
from backend.repos.aide_repo import AideRepo
from backend.repos.conversation_repo import ConversationRepo
from backend.services.r2 import r2_service

router = APIRouter(prefix="/api/aides", tags=["aides"])
aide_repo = AideRepo()
conversation_repo = ConversationRepo()


@router.get("", status_code=200)
async def list_aides(user: User = Depends(get_current_user)) -> list[AideResponse]:
    """List all non-archived aides for the current user."""
    aides = await aide_repo.list_for_user(user.id)
    return [AideResponse.from_model(a) for a in aides]


@router.post("", status_code=201)
async def create_aide(
    req: CreateAideRequest,
    user: User = Depends(get_current_user),
) -> AideResponse:
    """Create a new aide."""
    aide = await aide_repo.create(user.id, req)
    return AideResponse.from_model(aide)


@router.get("/{aide_id}", status_code=200)
async def get_aide(
    aide_id: UUID,
    user: User = Depends(get_current_user),
) -> AideResponse:
    """Get a single aide by ID."""
    aide = await aide_repo.get(user.id, aide_id)
    if not aide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")
    return AideResponse.from_model(aide)


@router.get("/{aide_id}/hydrate", status_code=200)
async def hydrate_aide(
    aide_id: UUID,
    user: User = Depends(get_current_user),
) -> HydrateResponse:
    """
    Cold load hydration endpoint.

    Returns the complete state needed to initialize the editor client:
    - snapshot: current reduced state (already reduced, ready to render)
    - events: full event log (for audit trail + published embed)
    - blueprint: identity, voice, prompt metadata
    - messages: conversation history
    - snapshot_hash: checksum for reconciliation

    No replay is needed - the snapshot is the current state, persisted
    after each turn by the server.
    """
    from backend.utils.snapshot_hash import hash_snapshot

    # Verify user owns this aide
    aide = await aide_repo.get(user.id, aide_id)
    if not aide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")

    # Get conversation history
    conversation = await conversation_repo.get_for_aide(user.id, aide_id)
    messages = []
    if conversation:
        messages = [
            {"role": m.role, "content": m.content, "timestamp": m.timestamp.isoformat()}
            for m in conversation.messages
            if m.role in ("user", "assistant")
        ]

    # Build blueprint from aide metadata
    blueprint = {
        "identity": aide.title or "Untitled",
        "voice": "declarative",  # Default voice rules from CLAUDE.md
        "prompt": "",  # Could be extended with custom system prompts later
    }

    # Snapshot is already reduced and ready to render
    snapshot = aide.state or {}

    # Events from the event log
    events = aide.event_log or []

    # Compute snapshot hash for reconciliation
    snapshot_hash_value = hash_snapshot(snapshot)

    return HydrateResponse(
        snapshot=snapshot,
        events=events,
        blueprint=blueprint,
        messages=messages,
        snapshot_hash=snapshot_hash_value,
    )


@router.patch("/{aide_id}", status_code=200)
async def update_aide(
    aide_id: UUID,
    req: UpdateAideRequest,
    user: User = Depends(get_current_user),
) -> AideResponse:
    """Update an aide's title or slug."""
    aide = await aide_repo.update(user.id, aide_id, req)
    if not aide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")
    return AideResponse.from_model(aide)


@router.post("/{aide_id}/archive", status_code=200)
async def archive_aide(
    aide_id: UUID,
    user: User = Depends(get_current_user),
) -> AideResponse:
    """Archive an aide (soft delete)."""
    aide = await aide_repo.archive(user.id, aide_id)
    if not aide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")
    return AideResponse.from_model(aide)


@router.delete("/{aide_id}", status_code=200)
async def delete_aide(
    aide_id: UUID,
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Permanently delete an aide."""
    deleted = await aide_repo.delete(user.id, aide_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")
    return {"message": "Aide deleted."}


@router.get("/{aide_id}/preview", status_code=200)
async def get_aide_preview(
    aide_id: UUID,
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Get rendered HTML preview for an aide (proxied from R2)."""
    # Verify user owns this aide
    aide = await aide_repo.get(user.id, aide_id)
    if not aide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")

    # Fetch HTML from R2
    # TODO: Race condition - if user refreshes before R2 upload completes,
    # R2 returns nothing but aide.state has content. Should fall back to
    # rendering from aide.state using render_react_preview() instead of
    # showing "Send a message" placeholder.
    html_content = await r2_service.get_html(str(aide_id))
    if not html_content:
        # Return placeholder if no HTML yet
        html_content = (
            '<!DOCTYPE html><html><body style="background:#f9f9f9;'
            "display:flex;align-items:center;justify-content:center;"
            'height:100vh;font-family:sans-serif;color:#aaa;font-size:14px;">'
            "Send a message to get started.</body></html>"
        )

    return HTMLResponse(content=html_content)


@router.get("/{aide_id}/state", status_code=200)
async def get_aide_state(
    aide_id: UUID,
    user: User = Depends(get_current_user),
) -> dict:
    """Get the aide's current state (entities, meta) for client-side hydration."""
    aide = await aide_repo.get(user.id, aide_id)
    if not aide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")

    state = aide.state or {}
    return {
        "entities": state.get("entities", {}),
        "meta": state.get("meta", {}),
    }


@router.get("/{aide_id}/history", status_code=200)
async def get_aide_history(
    aide_id: UUID,
    user: User = Depends(get_current_user),
) -> ConversationHistoryResponse:
    """Get conversation history for an aide."""
    # Verify user owns this aide
    aide = await aide_repo.get(user.id, aide_id)
    if not aide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")

    # Get conversation for this aide
    conversation = await conversation_repo.get_for_aide(user.id, aide_id)
    if not conversation:
        return ConversationHistoryResponse(messages=[])

    # Convert messages to response format (exclude system messages and metadata)
    messages = [
        MessageResponse(role=m.role, content=m.content)
        for m in conversation.messages
        if m.role in ("user", "assistant")
    ]

    return ConversationHistoryResponse(messages=messages)


@router.post("/{aide_id}/state", status_code=200)
async def save_aide_state(
    aide_id: UUID,
    req: SaveStateRequest,
    user: User = Depends(get_current_user),
) -> SaveStateResponse:
    """
    Save streamed state to database and R2.

    This endpoint persists the state that was streamed via WebSocket.
    No LLM call - just saves what the frontend already has.
    """
    from engine.kernel.react_preview import render_react_preview

    # Verify user owns this aide
    aide = await aide_repo.get(user.id, aide_id)
    if not aide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")

    # Build v2 snapshot from frontend state
    snapshot = {
        "entities": req.entities,
        "meta": req.meta,
        "relationships": [],
        "styles": {"global": {}, "entities": {}},
        "_sequence": 0,
    }

    # Update aide state in database
    title = req.meta.get("title") or aide.title
    await aide_repo.update_state(user.id, aide_id, snapshot, event_log=[], title=title)

    # Render HTML and upload to R2
    html_content = render_react_preview(snapshot, title=title)
    await r2_service.upload_html(str(aide_id), html_content)

    # Save conversation history if provided
    if req.message or req.response:
        from datetime import UTC, datetime

        from backend.models.conversation import Message

        # Get or create conversation for this aide
        conversation = await conversation_repo.get_for_aide(user.id, aide_id)
        if not conversation:
            conversation = await conversation_repo.create(user.id, aide_id, channel="web")

        now = datetime.now(UTC)

        # Append user message
        if req.message:
            await conversation_repo.append_message(
                user.id,
                conversation.id,
                Message(role="user", content=req.message, timestamp=now),
            )

        # Append assistant response
        if req.response:
            await conversation_repo.append_message(
                user.id,
                conversation.id,
                Message(role="assistant", content=req.response, timestamp=now),
            )

    return SaveStateResponse(preview_url=f"/api/aides/{aide_id}/preview")


@router.post("/{aide_id}/conversation", status_code=200)
async def save_conversation(
    aide_id: UUID,
    req: SaveConversationRequest,
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """
    Save conversation history only (no state update).

    Server handles state persistence in ws.py after stream.end.
    This endpoint only saves the user message and AI response.
    """
    from datetime import UTC, datetime

    from backend.models.conversation import Message

    # Verify user owns this aide
    aide = await aide_repo.get(user.id, aide_id)
    if not aide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")

    if not req.message and not req.response:
        return {"status": "ok"}

    # Get or create conversation for this aide
    conversation = await conversation_repo.get_for_aide(user.id, aide_id)
    if not conversation:
        conversation = await conversation_repo.create(user.id, aide_id, channel="web")

    now = datetime.now(UTC)

    # Append user message
    if req.message:
        await conversation_repo.append_message(
            user.id,
            conversation.id,
            Message(role="user", content=req.message, timestamp=now),
        )

    # Append assistant response
    if req.response:
        await conversation_repo.append_message(
            user.id,
            conversation.id,
            Message(role="assistant", content=req.response, timestamp=now),
        )

    return {"status": "ok"}
