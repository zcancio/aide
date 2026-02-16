"""Authentication routes for magic link auth."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from backend import config
from backend.auth import create_jwt, get_current_user
from backend.middleware.rate_limit import rate_limiter
from backend.models.auth import (
    LogoutResponse,
    SendMagicLinkRequest,
    SendMagicLinkResponse,
)
from backend.models.user import User, UserPublic
from backend.repos.magic_link_repo import MagicLinkRepo
from backend.repos.user_repo import UserRepo
from backend.services.email import send_magic_link

router = APIRouter(prefix="/auth", tags=["auth"])
magic_link_repo = MagicLinkRepo()
user_repo = UserRepo()


@router.post("/send", status_code=200)
async def send_magic_link_endpoint(
    req: SendMagicLinkRequest,
    request: Request,
) -> SendMagicLinkResponse:
    """
    Send a magic link to the user's email.

    Rate limits:
    - 5 per email per hour
    - 20 per IP per hour
    """
    email = req.email.lower()  # Normalize email to lowercase

    # Get client IP address
    client_ip = request.client.host if request.client else "unknown"

    # Rate limit: 5 per email per hour
    email_rate_limit_ok = await magic_link_repo.count_recent_by_email(email, hours=1)
    if email_rate_limit_ok >= config.settings.MAGIC_LINK_RATE_LIMIT_PER_EMAIL:
        max_links = config.settings.MAGIC_LINK_RATE_LIMIT_PER_EMAIL
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Maximum {max_links} magic links per hour.",
            headers={"Retry-After": "3600"},
        )

    # Rate limit: 20 per IP per hour (in-memory)
    if not rate_limiter.check_rate_limit(
        f"ip:{client_ip}",
        max_requests=config.settings.MAGIC_LINK_RATE_LIMIT_PER_IP,
        window_minutes=60,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests from this IP. Maximum {config.settings.MAGIC_LINK_RATE_LIMIT_PER_IP} per hour.",
            headers={"Retry-After": "3600"},
        )

    # Create magic link
    magic_link = await magic_link_repo.create(email)

    # Send email via Resend
    try:
        await send_magic_link(email, magic_link.token)
    except Exception as e:
        # Log error but don't expose details to client
        # In production, this would go to Sentry
        print(f"Failed to send magic link email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send email. Please try again.",
        ) from e

    return SendMagicLinkResponse()


@router.get("/verify", status_code=200)
async def verify_magic_link_endpoint(
    token: str,
    request: Request,
    response: Response,
) -> UserPublic:
    """
    Verify a magic link token and create a session.

    Rate limit: 10 attempts per IP per minute (prevents token brute force).
    """
    # Get client IP address
    client_ip = request.client.host if request.client else "unknown"

    # Rate limit: 10 per IP per minute
    if not rate_limiter.check_rate_limit(
        f"verify:{client_ip}",
        max_requests=10,
        window_minutes=1,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many verification attempts. Please wait a moment.",
            headers={"Retry-After": "60"},
        )

    # Get magic link
    magic_link = await magic_link_repo.get_by_token(token)
    if not magic_link:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid magic link. Please request a new one.",
        )

    # Check if already used
    if magic_link.used:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This magic link has already been used. Please request a new one.",
        )

    # Check if expired
    if magic_link.expires_at < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This magic link has expired. Please request a new one.",
        )

    # Mark as used
    await magic_link_repo.mark_used(token)

    # Get or create user
    user = await user_repo.get_by_email(magic_link.email)
    if not user:
        # First time user - create account
        user = await user_repo.create(magic_link.email)

    # Create JWT
    jwt_token = create_jwt(user.id)

    # Set HTTP-only cookie
    response.set_cookie(
        key="session",
        value=jwt_token,
        httponly=True,
        secure=True,  # HTTPS only
        samesite="lax",
        max_age=config.settings.JWT_EXPIRY_HOURS * 3600,
        path="/",
    )

    return UserPublic.from_user(user)


@router.get("/me", status_code=200)
async def get_current_user_endpoint(
    user: User = Depends(get_current_user),
) -> UserPublic:
    """
    Get the current authenticated user.

    Requires valid session cookie.
    """
    return UserPublic.from_user(user)


@router.post("/logout", status_code=200)
async def logout_endpoint(response: Response) -> LogoutResponse:
    """
    Logout the current user.

    Clears the session cookie.
    """
    # Clear cookie by setting it to expired
    response.set_cookie(
        key="session",
        value="",
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=0,  # Expire immediately
        path="/",
    )

    return LogoutResponse()
