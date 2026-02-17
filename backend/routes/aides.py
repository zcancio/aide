"""Aide CRUD routes — list, create, get, update, archive, delete."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse

from backend.auth import get_current_user
from backend.models.aide import AideResponse, CreateAideRequest, UpdateAideRequest
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
