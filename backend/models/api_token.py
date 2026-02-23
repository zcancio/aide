"""API token models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ApiToken(BaseModel):
    """API token stored in database."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    token_hash: str
    name: str
    scope: str
    last_used_at: datetime | None
    expires_at: datetime
    revoked: bool
    created_at: datetime


class ApiTokenListItem(BaseModel):
    """API token info for listing (no hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    scope: str
    last_used_at: datetime | None
    expires_at: datetime
    revoked: bool
    created_at: datetime


class RevokeTokenRequest(BaseModel):
    """Request to revoke a token."""

    model_config = ConfigDict(extra="forbid")

    token_id: UUID
