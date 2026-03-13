"""Conversation routes — send messages, view history."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth import get_current_user
from backend.config import settings
from backend.models.aide import CreateAideRequest, SendMessageRequest, SendMessageResponse
from backend.models.user import User
from backend.repos.aide_repo import AideRepo
from backend.repos.user_repo import UserRepo
from backend.services.streaming_orchestrator import StreamingOrchestrator
from engine.kernel import empty_snapshot

router = APIRouter(prefix="/api", tags=["conversations"])
aide_repo = AideRepo()
user_repo = UserRepo()


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
    # Check shadow user turn limit
    if user.is_shadow:
        usage = await user_repo.get_shadow_turn_count(user.id)
        if usage and usage["limit_reached"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "TURN_LIMIT_REACHED",
                    "message": "Trial limit reached. Sign up to continue.",
                    "turn_count": usage["turn_count"],
                    "turn_limit": usage["turn_limit"],
                },
            )

    aide_id = req.aide_id

    # Create a new aide if no aide_id provided
    if aide_id is None:
        create_req = CreateAideRequest(title="Untitled")
        aide = await aide_repo.create(user.id, create_req)
        aide_id = aide.id

    # Load existing aide
    aide = await aide_repo.get(user.id, UUID(aide_id) if isinstance(aide_id, str) else aide_id)
    if not aide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")

    # Get snapshot (or empty if none)
    snapshot = aide.state if aide.state and isinstance(aide.state, dict) else empty_snapshot()

    # Check for API key
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Anthropic API key not configured.",
        )

    # Create streaming orchestrator
    orchestrator = StreamingOrchestrator(
        aide_id=str(aide_id),
        snapshot=snapshot,
        conversation=[],  # TODO: Load conversation history if needed
        api_key=settings.ANTHROPIC_API_KEY,
    )

    # Process message and collect results
    voice_texts: list[str] = []
    final_snapshot = snapshot

    async for result in orchestrator.process_message(req.message):
        result_type = result.get("type")

        if result_type == "voice":
            text = result.get("text", "")
            if text.strip():
                voice_texts.append(text)

        elif result_type == "event":
            final_snapshot = result.get("snapshot", final_snapshot)

        elif result_type == "stream.end":
            # Stream complete
            pass

    # Combine voice texts into response
    response_text = " ".join(voice_texts) if voice_texts else "Done."

    # Save updated state
    title = final_snapshot.get("meta", {}).get("title")
    await aide_repo.update_state(user.id, aide.id, final_snapshot, event_log=[], title=title)

    return SendMessageResponse(
        response_text=response_text,
        page_url=f"/api/aides/{aide_id}/preview",
        state=final_snapshot,
        aide_id=str(aide_id),
    )
