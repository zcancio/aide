"""Repository for conversation operations."""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import asyncpg

from backend.db import user_conn
from backend.models.conversation import Conversation, Message


def _row_to_conversation(row: asyncpg.Record) -> Conversation:
    """Convert a database row to a Conversation model."""
    messages_raw = row["messages"]
    # JSONB comes back as a Python list from asyncpg
    if isinstance(messages_raw, str):
        messages_raw = json.loads(messages_raw)
    messages = [Message(**m) for m in messages_raw]

    return Conversation(
        id=row["id"],
        aide_id=row["aide_id"],
        channel=row["channel"],
        messages=messages,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class ConversationRepo:
    """All conversation-related database operations."""

    async def get_for_aide(self, user_id: UUID, aide_id: UUID) -> Conversation | None:
        """
        Get the most recent conversation for an aide.

        Args:
            user_id: User UUID
            aide_id: Aide UUID

        Returns:
            Most recent Conversation if found, None otherwise
        """
        async with user_conn(user_id) as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM conversations
                WHERE aide_id = $1
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                aide_id,
            )
            return _row_to_conversation(row) if row else None

    async def get(self, user_id: UUID, conversation_id: UUID) -> Conversation | None:
        """
        Get a conversation by ID. RLS ensures only owner can access.

        Args:
            user_id: User UUID
            conversation_id: Conversation UUID

        Returns:
            Conversation if found and user owns the aide, None otherwise
        """
        async with user_conn(user_id) as conn:
            row = await conn.fetchrow(
                "SELECT * FROM conversations WHERE id = $1",
                conversation_id,
            )
            return _row_to_conversation(row) if row else None

    async def create(self, user_id: UUID, aide_id: UUID, channel: str = "web") -> Conversation:
        """
        Create a new conversation for an aide.

        Args:
            user_id: User UUID
            aide_id: Aide UUID
            channel: Channel type (web or signal)

        Returns:
            Newly created Conversation
        """
        conversation_id = uuid4()

        async with user_conn(user_id) as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO conversations (id, aide_id, channel)
                VALUES ($1, $2, $3)
                RETURNING *
                """,
                conversation_id,
                aide_id,
                channel,
            )
            return _row_to_conversation(row)

    async def append_message(self, user_id: UUID, conversation_id: UUID, message: Message) -> None:
        """
        Append a message to a conversation.

        Args:
            user_id: User UUID
            conversation_id: Conversation UUID
            message: Message to append
        """
        async with user_conn(user_id) as conn:
            await conn.execute(
                """
                UPDATE conversations
                SET messages = messages || $2::jsonb,
                    updated_at = now()
                WHERE id = $1
                """,
                conversation_id,
                json.dumps([message.model_dump(mode="json")]),
            )

    async def list_for_aide(self, user_id: UUID, aide_id: UUID) -> list[Conversation]:
        """
        List all conversations for an aide.

        Args:
            user_id: User UUID
            aide_id: Aide UUID

        Returns:
            List of Conversation objects ordered by updated_at DESC
        """
        async with user_conn(user_id) as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM conversations
                WHERE aide_id = $1
                ORDER BY updated_at DESC
                """,
                aide_id,
            )
            return [_row_to_conversation(row) for row in rows]

    async def delete(self, user_id: UUID, conversation_id: UUID) -> bool:
        """
        Delete a conversation. RLS ensures only owner can delete.

        Args:
            user_id: User UUID
            conversation_id: Conversation UUID

        Returns:
            True if deleted, False if not found or not owned by user
        """
        async with user_conn(user_id) as conn:
            result = await conn.execute(
                "DELETE FROM conversations WHERE id = $1",
                conversation_id,
            )
            return result == "DELETE 1"

    async def clear_messages(self, user_id: UUID, conversation_id: UUID) -> None:
        """
        Clear all messages from a conversation.

        Args:
            user_id: User UUID
            conversation_id: Conversation UUID
        """
        async with user_conn(user_id) as conn:
            await conn.execute(
                """
                UPDATE conversations
                SET messages = '[]'::jsonb, updated_at = now()
                WHERE id = $1
                """,
                conversation_id,
            )
