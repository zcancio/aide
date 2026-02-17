"""Signal link code models for the Signal ear linking flow."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SignalLinkCode(BaseModel):
    """Core signal link code model — maps 1:1 to signal_link_codes table."""

    id: UUID
    code: str
    user_id: UUID
    aide_id: UUID
    expires_at: datetime
    used: bool
    created_at: datetime


class CreateLinkCodeRequest(BaseModel):
    """Request body for generating a new link code."""

    model_config = {"extra": "forbid"}

    aide_id: UUID


class LinkCodeResponse(BaseModel):
    """Public response returned after generating a link code."""

    code: str
    aide_id: UUID
    expires_at: datetime
    signal_phone: str
