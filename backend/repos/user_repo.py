"""Repository for user operations."""

from __future__ import annotations

from uuid import UUID

import asyncpg

from backend.db import system_conn, user_conn
from backend.models.user import User


def _row_to_user(row: asyncpg.Record) -> User:
    """Convert a database row to a User model."""
    return User(
        id=row["id"],
        email=row["email"],
        name=row["name"],
        tier=row["tier"],
        stripe_customer_id=row["stripe_customer_id"],
        stripe_sub_id=row["stripe_sub_id"],
        turn_count=row["turn_count"],
        turn_week_start=row["turn_week_start"],
        created_at=row["created_at"],
    )


class UserRepo:
    """All user-related database operations."""

    async def get_by_email(self, email: str) -> User | None:
        """
        Get a user by email address.
        Used during magic link verification. System conn because user context not yet established.

        Args:
            email: Email address to look up

        Returns:
            User if found, None otherwise
        """
        async with system_conn() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE email = $1",
                email,
            )
            return _row_to_user(row) if row else None

    async def create(self, email: str, name: str | None = None) -> User:
        """
        Create a new user during first magic link verification.

        Args:
            email: Email address for the new user
            name: Optional display name

        Returns:
            Newly created User
        """
        async with system_conn() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO users (email, name)
                VALUES ($1, $2)
                RETURNING *
                """,
                email,
                name,
            )
            return _row_to_user(row)

    async def get(self, user_id: UUID) -> User | None:
        """
        Get a user by ID.

        Args:
            user_id: User UUID

        Returns:
            User if found, None otherwise
        """
        async with user_conn(user_id) as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
            return _row_to_user(row) if row else None

    async def increment_turns(self, user_id: UUID) -> int:
        """
        Increment turn count for a user.

        Args:
            user_id: User UUID

        Returns:
            New turn count after increment
        """
        async with user_conn(user_id) as conn:
            new_count = await conn.fetchval(
                """
                UPDATE users SET turn_count = turn_count + 1
                WHERE id = $1
                RETURNING turn_count
                """,
                user_id,
            )
            return new_count or 0

    async def reset_turns_if_needed(self, user_id: UUID) -> None:
        """
        Reset weekly turn counter if 7 days have passed.

        Args:
            user_id: User UUID
        """
        async with user_conn(user_id) as conn:
            await conn.execute(
                """
                UPDATE users
                SET turn_count = 0, turn_week_start = now()
                WHERE id = $1
                AND turn_week_start < now() - interval '7 days'
                """,
                user_id,
            )

    async def upgrade_to_pro(self, user_id: UUID, stripe_customer_id: str, stripe_sub_id: str) -> None:
        """
        Upgrade a user to pro tier.

        Args:
            user_id: User UUID
            stripe_customer_id: Stripe customer ID
            stripe_sub_id: Stripe subscription ID
        """
        async with user_conn(user_id) as conn:
            await conn.execute(
                """
                UPDATE users
                SET tier = 'pro', stripe_customer_id = $2, stripe_sub_id = $3
                WHERE id = $1
                """,
                user_id,
                stripe_customer_id,
                stripe_sub_id,
            )

    async def downgrade_to_free(self, user_id: UUID) -> None:
        """
        Downgrade a user to free tier.

        Args:
            user_id: User UUID
        """
        async with user_conn(user_id) as conn:
            await conn.execute(
                """
                UPDATE users
                SET tier = 'free', stripe_sub_id = NULL
                WHERE id = $1
                """,
                user_id,
            )
