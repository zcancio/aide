"""
Authentication and authorization for AIde.

Magic link generation, JWT issuance, and session management.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Cookie, Header, HTTPException, status

from backend import config
from backend.db import system_conn
from backend.models.user import User
from backend.repos import api_token_repo
from backend.repos.user_repo import UserRepo

user_repo = UserRepo()


def create_jwt(user_id: UUID) -> str:
    """
    Create a JWT for a user session.

    Args:
        user_id: User UUID to encode in the token

    Returns:
        Signed JWT string
    """
    expires_at = datetime.now(UTC) + timedelta(hours=config.settings.JWT_EXPIRY_HOURS)
    payload = {
        "sub": str(user_id),
        "exp": expires_at,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, config.settings.JWT_SECRET, algorithm=config.settings.JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    """
    Decode and verify a JWT.

    Args:
        token: JWT string to decode

    Returns:
        Decoded payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, config.settings.JWT_SECRET, algorithms=[config.settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please sign in again.",
        ) from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token. Please sign in again.",
        ) from e


async def get_current_user_from_cookie(session: str) -> User:
    """
    Authenticate user via session cookie.

    Args:
        session: JWT from HTTP-only session cookie

    Returns:
        Current authenticated User

    Raises:
        HTTPException: If session is invalid or user not found
    """
    payload = decode_jwt(session)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token. Please sign in again.",
        )

    try:
        user_id = UUID(user_id_str)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token. Please sign in again.",
        ) from e

    user = await user_repo.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found. Please sign in again.",
        )

    return user


async def get_current_user_from_token(authorization: str) -> User:
    """
    Authenticate user via API token (CLI).

    Args:
        authorization: Bearer token header value

    Returns:
        Current authenticated User

    Raises:
        HTTPException: If token is invalid, revoked, or expired
    """
    if not authorization.startswith("Bearer aide_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format.",
        )

    raw_token = authorization.removeprefix("Bearer ")
    token_hash = api_token_repo.hash_token(raw_token)

    async with system_conn() as conn:
        token = await api_token_repo.get_by_hash(conn, token_hash)

        if not token or token.revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked token.",
            )

        if token.expires_at < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired.",
            )

        # Touch last_used_at
        await api_token_repo.touch_last_used(conn, token.id)

        # Get user
        user = await user_repo.get(token.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found.",
            )

        return user


async def get_current_user(
    session: Annotated[str | None, Cookie()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """
    FastAPI dependency to get the current authenticated user.

    Tries Bearer token first (CLI), then session cookie (browser).

    Args:
        session: JWT from HTTP-only session cookie
        authorization: Bearer token header

    Returns:
        Current authenticated User

    Raises:
        HTTPException: If authentication fails
    """
    # Try Bearer token first (CLI)
    if authorization and authorization.startswith("Bearer aide_"):
        return await get_current_user_from_token(authorization)

    # Fall back to session cookie (browser)
    if session:
        return await get_current_user_from_cookie(session)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Please sign in.",
    )
