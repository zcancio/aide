"""
Authentication and authorization for AIde.

Magic link generation, JWT issuance, and session management.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Cookie, HTTPException, status

from backend import config
from backend.models.user import User
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


async def get_current_user(session: Annotated[str | None, Cookie()] = None) -> User:
    """
    FastAPI dependency to get the current authenticated user.

    Reads the session cookie, validates the JWT, and returns the user.

    Args:
        session: JWT from HTTP-only session cookie

    Returns:
        Current authenticated User

    Raises:
        HTTPException: If session is missing, invalid, or user not found
    """
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please sign in.",
        )

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
