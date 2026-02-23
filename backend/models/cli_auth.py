"""CLI auth models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CliAuthRequest(BaseModel):
    """CLI auth request stored in database."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    device_code: str
    user_id: UUID | None
    status: str
    api_token: str | None
    expires_at: datetime
    created_at: datetime


class StartAuthRequest(BaseModel):
    """Request to start device auth flow."""

    model_config = ConfigDict(extra="forbid")

    device_code: str


class StartAuthResponse(BaseModel):
    """Response from starting device auth."""

    auth_url: str
    device_code: str
    expires_at: datetime


class PollAuthRequest(BaseModel):
    """Request to poll device auth status."""

    model_config = ConfigDict(extra="forbid")

    device_code: str


class PollAuthResponse(BaseModel):
    """Response from polling device auth."""

    status: str
    token: str | None = None


class ConfirmAuthRequest(BaseModel):
    """Request to confirm device auth (browser)."""

    model_config = ConfigDict(extra="forbid")

    device_code: str


class ConfirmAuthResponse(BaseModel):
    """Response from confirming device auth."""

    status: str
    email: str
