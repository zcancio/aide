"""Conversation routes — send messages, view history."""

from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth import get_current_user
from backend.models.aide import CreateAideRequest, SendMessageRequest, SendMessageResponse
from backend.models.user import User
from backend.repos.aide_repo import AideRepo
from backend.services.orchestrator import orchestrator

router = APIRouter(prefix="/api", tags=["conversations"])
aide_repo = AideRepo()


@router.post("/message", status_code=200)
async def send_message(
    req: SendMessageRequest,
    user: User = Depends(get_current_user),
) -> SendMessageResponse:
    """
    Send a message to an aide.

    If aide_id is omitted, a new aide is created from the first message.
    Returns the assistant response, rendered page URL, and updated state.
    """
    aide_id = req.aide_id

    # Create a new aide if no aide_id provided
    if aide_id is None:
        create_req = CreateAideRequest(title="Untitled")
        aide = await aide_repo.create(user.id, create_req)
        aide_id = aide.id

    # Decode image if provided
    image_data: bytes | None = None
    if req.image:
        try:
            # Strip data URI prefix if present (e.g. "data:image/png;base64,...")
            raw = req.image
            if "," in raw:
                raw = raw.split(",", 1)[1]
            image_data = base64.b64decode(raw)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid image data. Must be base64-encoded.",
            ) from exc

    result = await orchestrator.process_message(
        user_id=user.id,
        aide_id=aide_id,
        message=req.message,
        source="web",
        image_data=image_data,
    )

    # Fetch updated aide to get current state
    aide = await aide_repo.get(user.id, aide_id)
    if not aide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")

    return SendMessageResponse(
        response_text=result["response"],
        page_url=result["html_url"],
        state=aide.state,
        aide_id=aide_id,
    )
