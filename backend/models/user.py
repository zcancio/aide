"""User models for authentication and authorization."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr


class User(BaseModel):
    """Core user model. Represents a row in the users table."""

    id: UUID
    email: EmailStr
    name: str | None = None
    tier: Literal["free", "pro"] = "free"
    stripe_customer_id: str | None = None
    stripe_sub_id: str | None = None
    turn_count: int = 0
    turn_week_start: datetime
    created_at: datetime


class UserPublic(BaseModel):
    """What the API returns. No Stripe IDs, no internal fields."""

    id: UUID
    email: EmailStr
    name: str | None
    tier: Literal["free", "pro"]
    turn_count: int
    turn_week_start: datetime
    created_at: datetime

    @classmethod
    def from_user(cls, user: User) -> UserPublic:
        """Convert internal User model to public API response."""
        return cls(
            id=user.id,
            email=user.email,
            name=user.name,
            tier=user.tier,
            turn_count=user.turn_count,
            turn_week_start=user.turn_week_start,
            created_at=user.created_at,
        )
