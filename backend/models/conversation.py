"""Conversation models for chat history."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Message(BaseModel):
    """A single message in a conversation."""

    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class Conversation(BaseModel):
    """Core conversation model. Represents a row in the conversations table."""

    id: UUID
    aide_id: UUID
    channel: Literal["web", "signal"] = "web"
    messages: list[Message] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ConversationResponse(BaseModel):
    """What the API returns for conversations."""

    id: UUID
    aide_id: UUID
    channel: str
    message_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, conversation: Conversation) -> ConversationResponse:
        """Convert internal Conversation model to public API response."""
        return cls(
            id=conversation.id,
            aide_id=conversation.aide_id,
            channel=conversation.channel,
            message_count=len(conversation.messages),
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )
