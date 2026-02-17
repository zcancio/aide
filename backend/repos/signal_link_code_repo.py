"""Repository for Signal link code operations."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg

from backend.db import system_conn, user_conn
from backend.models.signal_link_code import SignalLinkCode

_LINK_CODE_EXPIRY_MINUTES = 15


def _generate_code() -> str:
    """Generate a 6-char uppercase hex code (e.g. 'A7F3B2')."""
    return secrets.token_hex(3).upper()


def _row_to_signal_link_code(row: asyncpg.Record) -> SignalLinkCode:
    """Convert a database row to a SignalLinkCode model."""
    return SignalLinkCode(
        id=row["id"],
        code=row["code"],
        user_id=row["user_id"],
        aide_id=row["aide_id"],
        expires_at=row["expires_at"],
        used=row["used"],
        created_at=row["created_at"],
    )


class SignalLinkCodeRepo:
    """All signal link code database operations."""

    async def create(self, user_id: UUID, aide_id: UUID) -> SignalLinkCode:
        """
        Generate and store a new link code for linking a Signal phone to an aide.

        Generates a unique 6-char hex code with 15-minute TTL.

        Args:
            user_id: User UUID
            aide_id: Aide UUID to link

        Returns:
            Newly created SignalLinkCode
        """
        code_id = uuid4()
        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=_LINK_CODE_EXPIRY_MINUTES)

        # Retry on the unlikely chance of a code collision
        for _ in range(5):
            code = _generate_code()
            try:
                async with user_conn(user_id) as conn:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO signal_link_codes (
                            id, code, user_id, aide_id, expires_at, used, created_at
                        )
                        VALUES ($1, $2, $3, $4, $5, false, $6)
                        RETURNING *
                        """,
                        code_id,
                        code,
                        user_id,
                        aide_id,
                        expires_at,
                        now,
                    )
                    return _row_to_signal_link_code(row)
            except asyncpg.UniqueViolationError:
                code_id = uuid4()
                continue

        raise RuntimeError("Failed to generate a unique link code after 5 attempts")

    async def get_by_code(self, code: str) -> SignalLinkCode | None:
        """
        Look up an active (not expired, not used) link code. Uses system_conn
        because the caller is the unauthenticated webhook handler.

        Args:
            code: 6-char hex code

        Returns:
            SignalLinkCode if found and active, None otherwise
        """
        now = datetime.now(UTC)
        async with system_conn() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM signal_link_codes
                WHERE code = $1
                  AND used = false
                  AND expires_at > $2
                """,
                code,
                now,
            )
            return _row_to_signal_link_code(row) if row else None

    async def mark_used(self, code_id: UUID) -> bool:
        """
        Mark a link code as used. Uses system_conn because this is called
        from the webhook handler after linking is complete.

        Args:
            code_id: UUID of the link code

        Returns:
            True if updated, False if not found
        """
        async with system_conn() as conn:
            result = await conn.execute(
                "UPDATE signal_link_codes SET used = true WHERE id = $1",
                code_id,
            )
            return result == "UPDATE 1"

    async def cleanup_expired(self) -> int:
        """
        Delete expired or used link codes. Safe to run from background task.

        Returns:
            Number of rows deleted
        """
        now = datetime.now(UTC)
        async with system_conn() as conn:
            result = await conn.execute(
                "DELETE FROM signal_link_codes WHERE expires_at < $1 OR used = true",
                now,
            )
            # asyncpg returns "DELETE N" string
            parts = result.split()
            return int(parts[1]) if len(parts) == 2 else 0
