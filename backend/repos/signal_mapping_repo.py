"""Repository for Signal mapping operations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg

from backend.db import system_conn, user_conn
from backend.models.signal_mapping import CreateSignalMappingRequest, SignalMapping


def _row_to_signal_mapping(row: asyncpg.Record) -> SignalMapping:
    """Convert a database row to a SignalMapping model."""
    return SignalMapping(
        id=row["id"],
        phone_number=row["phone_number"],
        user_id=row["user_id"],
        aide_id=row["aide_id"],
        conversation_id=row["conversation_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SignalMappingRepo:
    """All signal mapping-related database operations."""

    async def create(
        self,
        user_id: UUID,
        req: CreateSignalMappingRequest,
        conversation_id: UUID,
    ) -> SignalMapping:
        """
        Create a new Signal mapping for an aide.

        Args:
            user_id: User UUID
            req: CreateSignalMappingRequest with phone number and aide_id
            conversation_id: Conversation UUID for Signal channel

        Returns:
            Newly created SignalMapping
        """
        mapping_id = uuid4()
        now = datetime.now(UTC)

        async with user_conn(user_id) as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO signal_mappings (
                    id, phone_number, user_id, aide_id, conversation_id, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $6)
                RETURNING *
                """,
                mapping_id,
                req.phone_number,
                user_id,
                req.aide_id,
                conversation_id,
                now,
            )
            return _row_to_signal_mapping(row)

    async def get_by_phone(self, phone_number: str) -> SignalMapping | None:
        """
        Get a Signal mapping by phone number. System conn for Signal ear.

        Args:
            phone_number: Phone number to look up

        Returns:
            SignalMapping if found, None otherwise
        """
        async with system_conn() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM signal_mappings WHERE phone_number = $1",
                phone_number,
            )
            return _row_to_signal_mapping(row) if row else None

    async def get(self, user_id: UUID, mapping_id: UUID) -> SignalMapping | None:
        """
        Get a Signal mapping by ID. RLS ensures only owner can access.

        Args:
            user_id: User UUID
            mapping_id: SignalMapping UUID

        Returns:
            SignalMapping if found and owned by user, None otherwise
        """
        async with user_conn(user_id) as conn:
            row = await conn.fetchrow(
                "SELECT * FROM signal_mappings WHERE id = $1",
                mapping_id,
            )
            return _row_to_signal_mapping(row) if row else None

    async def get_by_aide(self, user_id: UUID, aide_id: UUID) -> SignalMapping | None:
        """
        Get a Signal mapping by aide ID.

        Args:
            user_id: User UUID
            aide_id: Aide UUID

        Returns:
            SignalMapping if found and owned by user, None otherwise
        """
        async with user_conn(user_id) as conn:
            row = await conn.fetchrow(
                "SELECT * FROM signal_mappings WHERE aide_id = $1",
                aide_id,
            )
            return _row_to_signal_mapping(row) if row else None

    async def list_for_user(self, user_id: UUID) -> list[SignalMapping]:
        """
        List all Signal mappings for a user.

        Args:
            user_id: User UUID

        Returns:
            List of SignalMapping objects ordered by created_at DESC
        """
        async with user_conn(user_id) as conn:
            rows = await conn.fetch("SELECT * FROM signal_mappings ORDER BY created_at DESC")
            return [_row_to_signal_mapping(row) for row in rows]

    async def delete(self, user_id: UUID, mapping_id: UUID) -> bool:
        """
        Delete a Signal mapping. RLS ensures only owner can delete.

        Args:
            user_id: User UUID
            mapping_id: SignalMapping UUID

        Returns:
            True if deleted, False if not found or not owned by user
        """
        async with user_conn(user_id) as conn:
            result = await conn.execute(
                "DELETE FROM signal_mappings WHERE id = $1",
                mapping_id,
            )
            return result == "DELETE 1"

    async def delete_by_phone(self, phone_number: str) -> bool:
        """
        Delete a Signal mapping by phone number. System conn for Signal ear.

        Args:
            phone_number: Phone number

        Returns:
            True if deleted, False if not found
        """
        async with system_conn() as conn:
            result = await conn.execute(
                "DELETE FROM signal_mappings WHERE phone_number = $1",
                phone_number,
            )
            return result == "DELETE 1"

    async def update_conversation(self, user_id: UUID, mapping_id: UUID, conversation_id: UUID) -> SignalMapping | None:
        """
        Update the conversation_id for a Signal mapping.

        Args:
            user_id: User UUID
            mapping_id: SignalMapping UUID
            conversation_id: New conversation UUID

        Returns:
            Updated SignalMapping if found and owned by user, None otherwise
        """
        async with user_conn(user_id) as conn:
            row = await conn.fetchrow(
                """
                UPDATE signal_mappings
                SET conversation_id = $2, updated_at = now()
                WHERE id = $1
                RETURNING *
                """,
                mapping_id,
                conversation_id,
            )
            return _row_to_signal_mapping(row) if row else None
