"""Signal mapping models for Signal ear integration."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SignalMapping(BaseModel):
    """Core signal mapping model. Maps Signal phone numbers to aides."""

    id: UUID
    phone_number: str
    user_id: UUID
    aide_id: UUID
    conversation_id: UUID
    created_at: datetime
    updated_at: datetime


class CreateSignalMappingRequest(BaseModel):
    """What the system sends to create a signal mapping."""

    model_config = {"extra": "forbid"}

    phone_number: str = Field(min_length=1, max_length=20)
    aide_id: UUID


class SignalMappingResponse(BaseModel):
    """What the API returns for signal mappings."""

    id: UUID
    phone_number: str
    aide_id: UUID
    created_at: datetime

    @classmethod
    def from_model(cls, mapping: SignalMapping) -> SignalMappingResponse:
        """Convert internal SignalMapping model to public API response."""
        return cls(
            id=mapping.id,
            phone_number=mapping.phone_number,
            aide_id=mapping.aide_id,
            created_at=mapping.created_at,
        )
