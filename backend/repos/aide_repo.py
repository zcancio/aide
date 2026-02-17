"""Repository for aide operations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg

from backend.db import system_conn, user_conn
from backend.models.aide import Aide, CreateAideRequest, UpdateAideRequest


def _row_to_aide(row: asyncpg.Record) -> Aide:
    """Convert a database row to an Aide model."""
    return Aide(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        slug=row["slug"],
        status=row["status"],
        state=row["state"],
        event_log=row["event_log"],
        r2_prefix=row["r2_prefix"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class AideRepo:
    """All aide-related database operations."""

    async def create(self, user_id: UUID, req: CreateAideRequest) -> Aide:
        """
        Create a new aide for a user.

        Args:
            user_id: User UUID
            req: CreateAideRequest with aide details

        Returns:
            Newly created Aide
        """
        aide_id = uuid4()
        now = datetime.now(UTC)

        async with user_conn(user_id) as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO aides (id, user_id, title, r2_prefix, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $5)
                RETURNING *
                """,
                aide_id,
                user_id,
                req.title,
                f"aides/{aide_id}",
                now,
            )
            return _row_to_aide(row)

    async def get(self, user_id: UUID, aide_id: UUID) -> Aide | None:
        """
        Get an aide by ID. RLS ensures only the owner can access.

        Args:
            user_id: User UUID
            aide_id: Aide UUID

        Returns:
            Aide if found and owned by user, None otherwise
        """
        async with user_conn(user_id) as conn:
            row = await conn.fetchrow(
                "SELECT * FROM aides WHERE id = $1",
                aide_id,
            )
            return _row_to_aide(row) if row else None

    async def list_for_user(self, user_id: UUID) -> list[Aide]:
        """
        List all non-archived aides for a user.

        Args:
            user_id: User UUID

        Returns:
            List of Aide objects ordered by updated_at DESC
        """
        async with user_conn(user_id) as conn:
            rows = await conn.fetch("SELECT * FROM aides WHERE status != 'archived' ORDER BY updated_at DESC")
            return [_row_to_aide(row) for row in rows]

    async def update(self, user_id: UUID, aide_id: UUID, req: UpdateAideRequest) -> Aide | None:
        """
        Update an aide. RLS ensures only the owner can update.

        Args:
            user_id: User UUID
            aide_id: Aide UUID
            req: UpdateAideRequest with fields to update

        Returns:
            Updated Aide if found and owned by user, None otherwise
        """
        async with user_conn(user_id) as conn:
            # Build SET clause from non-None fields only
            updates = {}
            if req.title is not None:
                updates["title"] = req.title
            if req.slug is not None:
                updates["slug"] = req.slug

            if not updates:
                return await self.get(user_id, aide_id)

            set_clause = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(updates))
            values = list(updates.values())

            # S608/B608: False positive - set_clause only contains validated column names
            row = await conn.fetchrow(
                f"""
                UPDATE aides
                SET {set_clause}, updated_at = now()
                WHERE id = $1
                RETURNING *
                """,  # nosec B608
                aide_id,
                *values,
            )
            return _row_to_aide(row) if row else None

    async def delete(self, user_id: UUID, aide_id: UUID) -> bool:
        """
        Delete an aide. RLS ensures only the owner can delete.

        Args:
            user_id: User UUID
            aide_id: Aide UUID

        Returns:
            True if deleted, False if not found or not owned by user
        """
        async with user_conn(user_id) as conn:
            result = await conn.execute(
                "DELETE FROM aides WHERE id = $1",
                aide_id,
            )
            return result == "DELETE 1"

    async def archive(self, user_id: UUID, aide_id: UUID) -> Aide | None:
        """
        Archive an aide (soft delete).

        Args:
            user_id: User UUID
            aide_id: Aide UUID

        Returns:
            Updated Aide if found and owned by user, None otherwise
        """
        async with user_conn(user_id) as conn:
            row = await conn.fetchrow(
                """
                UPDATE aides
                SET status = 'archived', updated_at = now()
                WHERE id = $1
                RETURNING *
                """,
                aide_id,
            )
            return _row_to_aide(row) if row else None

    async def publish(self, user_id: UUID, aide_id: UUID, slug: str) -> Aide | None:
        """
        Publish an aide with a slug.

        Args:
            user_id: User UUID
            aide_id: Aide UUID
            slug: URL slug for published page

        Returns:
            Updated Aide if found and owned by user, None otherwise
        """
        async with user_conn(user_id) as conn:
            row = await conn.fetchrow(
                """
                UPDATE aides
                SET status = 'published', slug = $2, updated_at = now()
                WHERE id = $1
                RETURNING *
                """,
                aide_id,
                slug,
            )
            return _row_to_aide(row) if row else None

    async def unpublish(self, user_id: UUID, aide_id: UUID) -> Aide | None:
        """
        Unpublish an aide (set back to draft, clear slug).

        Args:
            user_id: User UUID
            aide_id: Aide UUID

        Returns:
            Updated Aide if found and owned by user, None otherwise
        """
        async with user_conn(user_id) as conn:
            row = await conn.fetchrow(
                """
                UPDATE aides
                SET status = 'draft', slug = NULL, updated_at = now()
                WHERE id = $1
                RETURNING *
                """,
                aide_id,
            )
            return _row_to_aide(row) if row else None

    async def get_by_slug(self, slug: str) -> Aide | None:
        """
        Get a published aide by slug. Public lookup - no user scoping needed.

        Args:
            slug: URL slug

        Returns:
            Aide if found and published, None otherwise
        """
        async with system_conn() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM aides WHERE slug = $1 AND status = 'published'",
                slug,
            )
            return _row_to_aide(row) if row else None

    async def count_for_user(self, user_id: UUID) -> int:
        """
        Count non-archived aides for a user.

        Args:
            user_id: User UUID

        Returns:
            Count of non-archived aides
        """
        async with user_conn(user_id) as conn:
            count = await conn.fetchval("SELECT count(*) FROM aides WHERE status != 'archived'")
            return count or 0

    async def update_state(
        self,
        user_id: UUID,
        aide_id: UUID,
        state: dict,
        event_log: list,
        title: str | None = None,
    ) -> Aide | None:
        """
        Update aide state and event log (for kernel operations).

        Args:
            user_id: User UUID
            aide_id: Aide UUID
            state: New state snapshot
            event_log: Updated event log
            title: Optional new title (from meta.update primitive)

        Returns:
            Updated Aide if found and owned by user, None otherwise
        """
        async with user_conn(user_id) as conn:
            if title:
                row = await conn.fetchrow(
                    """
                    UPDATE aides
                    SET state = $2, event_log = $3, title = $4, updated_at = now()
                    WHERE id = $1
                    RETURNING *
                    """,
                    aide_id,
                    state,
                    event_log,
                    title,
                )
            else:
                row = await conn.fetchrow(
                    """
                    UPDATE aides
                    SET state = $2, event_log = $3, updated_at = now()
                    WHERE id = $1
                    RETURNING *
                    """,
                    aide_id,
                    state,
                    event_log,
                )
            return _row_to_aide(row) if row else None
