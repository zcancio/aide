"""Signal ear routes — webhook, link code generation, and mapping management."""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from backend import config
from backend.auth import get_current_user
from backend.middleware.rate_limit import rate_limiter
from backend.models.signal_link_code import CreateLinkCodeRequest, LinkCodeResponse
from backend.models.signal_mapping import CreateSignalMappingRequest, SignalMappingResponse
from backend.models.user import User
from backend.repos.aide_repo import AideRepo
from backend.repos.conversation_repo import ConversationRepo
from backend.repos.signal_link_code_repo import SignalLinkCodeRepo
from backend.repos.signal_mapping_repo import SignalMappingRepo
from backend.services.orchestrator import Orchestrator
from backend.services.signal_service import signal_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/signal", tags=["signal"])

aide_repo = AideRepo()
conv_repo = ConversationRepo()
link_code_repo = SignalLinkCodeRepo()
mapping_repo = SignalMappingRepo()
orchestrator = Orchestrator()

# Pattern for a valid 6-char uppercase hex link code
_LINK_CODE_RE = re.compile(r"^[A-F0-9]{6}$")

# Rate limit: 60 inbound Signal messages per phone number per hour
_SIGNAL_RATE_LIMIT = 60
_SIGNAL_RATE_WINDOW = 3600


def _verify_webhook_signature(body: bytes, signature: str) -> bool:
    """Verify HMAC-SHA256 webhook signature from signal-cli."""
    secret = config.settings.SIGNAL_WEBHOOK_SECRET
    if not secret:
        # Skip verification if no secret is configured (dev/test only)
        return True
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhook", status_code=200)
async def signal_webhook(request: Request) -> dict:
    """
    Receive inbound Signal messages from signal-cli-rest-api.

    Unauthenticated — verified by HMAC-SHA256 signature header.
    Handles two message types:
      - 6-char hex codes → link code flow (phone → aide linking)
      - Everything else → route to orchestrator (aide update)
    """
    body = await request.body()

    # Verify webhook signature
    signature = request.headers.get("X-Signal-Signature", "")
    if not _verify_webhook_signature(body, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from exc

    envelope = payload.get("envelope", {})
    phone_number: str = envelope.get("sourceNumber", "")
    data_message = envelope.get("dataMessage", {})
    message_text: str = (data_message.get("message") or "").strip()

    if not phone_number or not message_text:
        # Ignore receipts, typing indicators, and other non-message envelopes
        return {"status": "ignored"}

    # Per-phone rate limiting (60 messages/hour)
    rate_key = f"signal:{phone_number}"
    window_minutes = _SIGNAL_RATE_WINDOW // 60
    if not rate_limiter.check_rate_limit(rate_key, max_requests=_SIGNAL_RATE_LIMIT, window_minutes=window_minutes):
        try:
            await signal_service.send_message(
                phone_number,
                "Too many messages. Please wait before sending more.",
            )
        except Exception:
            logger.warning("Failed to send rate-limit reply to %s", phone_number)
        return {"status": "rate_limited"}

    # Link code flow: 6-char uppercase hex
    if _LINK_CODE_RE.match(message_text.upper()):
        return await _handle_link_code(phone_number, message_text.upper())

    # Aide update flow: look up mapping and route to orchestrator
    return await _handle_aide_update(phone_number, message_text)


async def _handle_link_code(phone_number: str, code: str) -> dict:
    """Process a link code sent via Signal."""
    link_code = await link_code_repo.get_by_code(code)

    if not link_code:
        try:
            await signal_service.send_message(
                phone_number,
                "Code invalid or expired. Generate a new one from the dashboard.",
            )
        except Exception:
            logger.warning("Failed to send invalid-code reply to %s", phone_number)
        return {"status": "invalid_code"}

    # Create the Signal → aide mapping
    req = CreateSignalMappingRequest(
        phone_number=phone_number,
        aide_id=link_code.aide_id,
    )
    try:
        conversation = await conv_repo.create(link_code.user_id, link_code.aide_id, channel="signal")
        await mapping_repo.create(link_code.user_id, req, conversation.id)
    except Exception:
        logger.exception("Failed to create signal mapping for %s", phone_number)
        try:
            await signal_service.send_message(
                phone_number,
                "Something went wrong. Try again.",
            )
        except Exception:
            logger.warning("Failed to send error reply to %s", phone_number)
        return {"status": "error"}

    # Mark code as used
    await link_code_repo.mark_used(link_code.id)

    try:
        await signal_service.send_message(
            phone_number,
            "Connected! You can now text updates to your aide.",
        )
    except Exception:
        logger.warning("Failed to send confirmation to %s", phone_number)

    return {"status": "linked"}


async def _handle_aide_update(phone_number: str, message: str) -> dict:
    """Route an inbound Signal message to the orchestrator."""
    mapping = await mapping_repo.get_by_phone(phone_number)

    if not mapping:
        try:
            await signal_service.send_message(
                phone_number,
                "Link your phone first via the dashboard.",
            )
        except Exception:
            logger.warning("Failed to send link-prompt reply to %s", phone_number)
        return {"status": "unknown_phone"}

    try:
        result = await orchestrator.process_message(
            user_id=mapping.user_id,
            aide_id=mapping.aide_id,
            message=message,
            source="signal",
        )
        response_text = result.get("response", "")
        if response_text:
            await signal_service.send_message(phone_number, response_text)
    except Exception:
        logger.exception("Orchestrator error for phone %s", phone_number)
        try:
            await signal_service.send_message(
                phone_number,
                "Something went wrong. Try again.",
            )
        except Exception:
            logger.warning("Failed to send orchestrator-error reply to %s", phone_number)
        return {"status": "error"}

    return {"status": "processed"}


@router.post("/link", status_code=201)
async def generate_link_code(
    req: CreateLinkCodeRequest,
    user: User = Depends(get_current_user),
) -> LinkCodeResponse:
    """
    Generate a 6-char link code for linking a Signal phone number to an aide.

    The user texts this code to the AIde Signal number to complete linking.
    Codes expire after 15 minutes and are single-use.
    """
    # Verify the aide belongs to the user
    aide = await aide_repo.get(user.id, req.aide_id)
    if not aide:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aide not found.",
        )

    link_code = await link_code_repo.create(user.id, req.aide_id)

    return LinkCodeResponse(
        code=link_code.code,
        aide_id=link_code.aide_id,
        expires_at=link_code.expires_at,
        signal_phone=config.settings.SIGNAL_PHONE_NUMBER,
    )


@router.get("/mappings", status_code=200)
async def list_signal_mappings(
    user: User = Depends(get_current_user),
) -> list[SignalMappingResponse]:
    """List all Signal-linked aides for the current user."""
    mappings = await mapping_repo.list_for_user(user.id)
    return [SignalMappingResponse.from_model(m) for m in mappings]


@router.get("/mappings/{aide_id}", status_code=200)
async def get_signal_mapping(
    aide_id: UUID,
    user: User = Depends(get_current_user),
) -> dict:
    """
    Check whether an aide is linked to a Signal phone number.

    Returns { linked: true, phone_number: "...", aide_id: "..." }
    or      { linked: false, aide_id: "..." }
    """
    mapping = await mapping_repo.get_by_aide(user.id, aide_id)
    if mapping:
        return {
            "linked": True,
            "phone_number": mapping.phone_number,
            "aide_id": str(aide_id),
        }
    return {"linked": False, "aide_id": str(aide_id)}


@router.delete("/mappings/{aide_id}")
async def delete_signal_mapping(
    aide_id: UUID,
    user: User = Depends(get_current_user),
) -> Response:
    """Unlink Signal from an aide."""
    mapping = await mapping_repo.get_by_aide(user.id, aide_id)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal mapping not found.",
        )
    await mapping_repo.delete(user.id, mapping.id)
    return Response(status_code=204)


@router.get("/phone", status_code=200)
async def get_signal_phone() -> dict:
    """Get the AIde Signal phone number to display in the dashboard."""
    return {"phone_number": config.settings.SIGNAL_PHONE_NUMBER}
