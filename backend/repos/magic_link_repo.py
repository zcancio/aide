"""Repository for magic link operations."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import asyncpg

from backend import config
from backend.db import system_conn
from backend.models.auth import MagicLink


def _row_to_magic_link(row: asyncpg.Record) -> MagicLink:
    """Convert a database row to a MagicLink model."""
    return MagicLink(
        id=row["id"],
        email=row["email"],
        token=row["token"],
        expires_at=row["expires_at"],
        used=row["used"],
        created_at=row["created_at"],
    )


class MagicLinkRepo:
    """All magic link-related database operations."""

    async def create(self, email: str) -> MagicLink:
        """
        Create a new magic link token.

        Args:
            email: Email address to send the magic link to

        Returns:
            MagicLink model with token and expiry
        """
        token = secrets.token_hex(32)  # 64 character hex string
        expires_at = datetime.now(UTC) + timedelta(minutes=config.settings.MAGIC_LINK_EXPIRY_MINUTES)

        async with system_conn() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO magic_links (email, token, expires_at)
                VALUES ($1, $2, $3)
                RETURNING *
                """,
                email,
                token,
                expires_at,
            )
            return _row_to_magic_link(row)

    async def get_by_token(self, token: str) -> MagicLink | None:
        """
        Get a magic link by token.

        Args:
            token: Magic link token

        Returns:
            MagicLink if found, None otherwise
        """
        async with system_conn() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM magic_links WHERE token = $1",
                token,
            )
            return _row_to_magic_link(row) if row else None

    async def mark_used(self, token: str) -> bool:
        """
        Mark a magic link token as used.

        Args:
            token: Magic link token to mark as used

        Returns:
            True if token was marked, False if token not found
        """
        async with system_conn() as conn:
            result = await conn.execute(
                "UPDATE magic_links SET used = true WHERE token = $1",
                token,
            )
            return result == "UPDATE 1"

    async def count_recent_by_email(self, email: str, hours: int = 1) -> int:
        """
        Count recent magic links sent to an email address.

        Args:
            email: Email address to check
            hours: Number of hours to look back (default 1)

        Returns:
            Number of magic links sent in the time period
        """
        async with system_conn() as conn:
            count = await conn.fetchval(
                """
                SELECT count(*)
                FROM magic_links
                WHERE email = $1
                AND created_at > now() - interval '1 hour' * $2
                """,
                email,
                hours,
            )
            return count or 0

    async def count_recent_by_ip(self, ip_address: str, hours: int = 1) -> int:
        """
        Count recent magic links sent from an IP address.

        Note: This requires storing IP addresses with magic links.
        For Phase 0, we'll track this in-memory via middleware.
        This method is a placeholder for future implementation.

        Args:
            ip_address: IP address to check
            hours: Number of hours to look back (default 1)

        Returns:
            Number of magic links sent from this IP in the time period
        """
        # TODO: Add ip_address column to magic_links table in future migration
        # For now, IP-based rate limiting will be handled in-memory via middleware
        return 0

    async def cleanup_expired(self, older_than_hours: int = 1) -> int:
        """
        Delete expired and used magic links older than specified hours.

        Args:
            older_than_hours: Delete tokens older than this many hours (default 1)

        Returns:
            Number of records deleted
        """
        async with system_conn() as conn:
            result = await conn.execute(
                """
                DELETE FROM magic_links
                WHERE created_at < now() - interval '1 hour' * $1
                AND (used = true OR expires_at < now())
                """,
                older_than_hours,
            )
            # Result format is "DELETE N" where N is the count
            return int(result.split()[-1]) if result else 0
