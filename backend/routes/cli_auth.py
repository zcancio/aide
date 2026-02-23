"""CLI device authorization routes."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth import get_current_user
from backend.config import settings
from backend.db import system_conn
from backend.models.cli_auth import (
    ConfirmAuthRequest,
    ConfirmAuthResponse,
    PollAuthRequest,
    PollAuthResponse,
    StartAuthRequest,
    StartAuthResponse,
)
from backend.models.user import User
from backend.repos import api_token_repo, cli_auth_repo

router = APIRouter(prefix="/api/cli/auth", tags=["cli_auth"])


@router.post("/start")
async def start_auth(request: StartAuthRequest) -> StartAuthResponse:
    """
    Start a device authorization flow.

    Rate limited to 10 per IP per hour.
    """
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.CLI_AUTH_CODE_EXPIRY_MINUTES)

    async with system_conn() as conn:
        # Check if device code already exists
        existing = await cli_auth_repo.get_by_device_code(conn, request.device_code)
        if existing and existing.status == "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Device code already in use. Please regenerate.",
            )

        # Create auth request
        auth_request = await cli_auth_repo.create_request(conn, request.device_code, expires_at)

    auth_url = f"{settings.EDITOR_URL}/cli/auth?code={request.device_code}"

    return StartAuthResponse(
        auth_url=auth_url,
        device_code=auth_request.device_code,
        expires_at=auth_request.expires_at,
    )


@router.post("/poll")
async def poll_auth(request: PollAuthRequest) -> PollAuthResponse:
    """
    Poll for device authorization status.

    Rate limited to 30 per device_code per minute.
    """
    async with system_conn() as conn:
        auth_request = await cli_auth_repo.get_by_device_code(conn, request.device_code)

        if not auth_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Unknown device code.",
            )

        # Check expiry
        if auth_request.expires_at < datetime.now(UTC):
            if auth_request.status != "expired":
                await cli_auth_repo.mark_expired(conn, request.device_code)
            return PollAuthResponse(status="expired")

        # Return current status
        if auth_request.status == "approved":
            return PollAuthResponse(status="approved", token=auth_request.api_token)

        return PollAuthResponse(status="pending")


@router.post("/confirm")
async def confirm_auth(
    request: ConfirmAuthRequest,
    user: User = Depends(get_current_user),
) -> ConfirmAuthResponse:
    """
    Confirm device authorization (browser, requires session cookie).

    Creates an API token and approves the auth request.
    """
    async with system_conn() as conn:
        auth_request = await cli_auth_repo.get_by_device_code(conn, request.device_code)

        if not auth_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Unknown device code.",
            )

        # Check expiry
        if auth_request.expires_at < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device code expired.",
            )

        # Check if already approved
        if auth_request.status == "approved":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Device code already approved.",
            )

        # Create API token
        raw_token, token = await api_token_repo.create_token(
            conn,
            user.id,
            name="cli",
            scope="cli",
            expiry_days=settings.CLI_TOKEN_EXPIRY_DAYS,
        )

        # Approve auth request
        await cli_auth_repo.approve_request(conn, request.device_code, user.id, raw_token)

    return ConfirmAuthResponse(status="approved", email=user.email)
