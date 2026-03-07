"""Admin audit models for breakglass access tracking."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AdminAuditLog(BaseModel):
    """Admin audit log entry. Tracks all admin breakglass actions."""

    id: UUID
    admin_user_id: UUID
    action: str
    target_user_id: UUID | None = None
    target_aide_id: UUID | None = None
    reason: str
    ip_address: str | None = None
    created_at: datetime


class BreakglassAccessRequest(BaseModel):
    """Request model for admin breakglass access to an aide."""

    model_config = {"extra": "forbid"}

    aide_id: UUID
    reason: str = Field(min_length=10, max_length=500)


class AdminAuditLogResponse(BaseModel):
    """Response model for admin audit log entries."""

    id: UUID
    admin_user_id: UUID
    admin_email: str
    action: str
    target_user_id: UUID | None = None
    target_user_email: str | None = None
    target_aide_id: UUID | None = None
    target_aide_title: str | None = None
    reason: str
    ip_address: str | None = None
    created_at: datetime
