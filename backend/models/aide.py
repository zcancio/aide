"""Aide models for living object pages."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SendMessageRequest(BaseModel):
    """What the client sends to POST /api/message."""

    model_config = {"extra": "forbid"}

    aide_id: UUID | None = None
    message: str = Field(min_length=1, max_length=10000)
    image: str | None = None  # base64-encoded image data


class SendMessageResponse(BaseModel):
    """What the message endpoint returns."""

    response_text: str
    page_url: str
    state: dict[str, Any]
    aide_id: UUID


class SaveStateRequest(BaseModel):
    """What the client sends to persist streamed state (no LLM call)."""

    model_config = {"extra": "forbid"}

    entities: dict[str, Any]
    meta: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None  # Original user message for conversation history
    response: str | None = None  # AI response text for conversation history


class SaveStateResponse(BaseModel):
    """What the save state endpoint returns."""

    preview_url: str


class SaveConversationRequest(BaseModel):
    """What the client sends to save conversation history only (no state)."""

    model_config = {"extra": "forbid"}

    message: str | None = None  # Original user message
    response: str | None = None  # AI response text


class PublishRequest(BaseModel):
    """What the client sends to publish an aide."""

    model_config = {"extra": "forbid"}

    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")


class PublishResponse(BaseModel):
    """What the publish endpoint returns."""

    slug: str
    url: str


class Aide(BaseModel):
    """Core aide model. Represents a row in the aides table."""

    id: UUID
    user_id: UUID
    title: str = "Untitled"
    slug: str | None = None
    status: Literal["draft", "published", "archived"] = "draft"
    state: dict[str, Any] = Field(default_factory=dict)
    event_log: list[dict[str, Any]] = Field(default_factory=list)
    r2_prefix: str | None = None
    created_at: datetime
    updated_at: datetime


class CreateAideRequest(BaseModel):
    """What the client sends to create an aide."""

    model_config = {"extra": "forbid"}

    title: str = Field(default="Untitled", max_length=200)


class UpdateAideRequest(BaseModel):
    """What the client sends to update an aide. All fields optional."""

    model_config = {"extra": "forbid"}

    title: str | None = Field(default=None, max_length=200)
    slug: str | None = Field(default=None, max_length=100, pattern=r"^[a-z0-9-]+$")


class AideResponse(BaseModel):
    """What the API returns."""

    id: UUID
    title: str
    slug: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    snapshot: dict[str, Any] | None = None  # Included when include_snapshot=true (CLI usage)

    @classmethod
    def from_model(cls, aide: Aide) -> AideResponse:
        """Convert internal Aide model to public API response."""
        return cls(
            id=aide.id,
            title=aide.title,
            slug=aide.slug,
            status=aide.status,
            created_at=aide.created_at,
            updated_at=aide.updated_at,
        )


class HydrateResponse(BaseModel):
    """
    Cold load hydration response.

    Returns the complete state needed to initialize the editor:
    - snapshot: current reduced state (ready to render, no replay needed)
    - events: full event log (for audit trail + published embed)
    - blueprint: identity, voice, prompt
    - messages: conversation history
    - snapshot_hash: checksum for reconciliation
    """

    snapshot: dict[str, Any]
    events: list[dict[str, Any]]
    blueprint: dict[str, str]
    messages: list[dict[str, Any]]
    snapshot_hash: str
