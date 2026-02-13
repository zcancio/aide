"""Authentication models for magic links and session management."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class MagicLink(BaseModel):
    """Core magic link model. Represents a row in the magic_links table."""

    id: UUID
    email: EmailStr
    token: str
    expires_at: datetime
    used: bool
    created_at: datetime


class SendMagicLinkRequest(BaseModel):
    """Request to send a magic link."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class SendMagicLinkResponse(BaseModel):
    """Response after sending a magic link."""

    message: str = "Magic link sent. Check your email."


class VerifyMagicLinkRequest(BaseModel):
    """Request to verify a magic link token."""

    model_config = ConfigDict(extra="forbid")

    token: str = Field(..., min_length=64, max_length=64)


class LogoutResponse(BaseModel):
    """Response after logout."""

    message: str = "Logged out successfully"
