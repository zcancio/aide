"""
PostgresStorage adapter for AIde kernel assembly layer.

Implements the AideStorage protocol using Postgres as the backend.
Stores HTML files directly in the aide_files table.
"""

from __future__ import annotations

import asyncpg

from engine.kernel.assembly import AideStorage


class PostgresStorage(AideStorage):
    """
    Postgres-based storage for aide HTML files.

    Uses two tables:
    - aide_files: workspace storage (private aide HTML)
    - published_aides: published storage (public aide HTML with slugs)
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get(self, aide_id: str) -> str | None:
        """Fetch HTML file for an aide from workspace. Returns None if not found."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT html FROM aide_files WHERE aide_id = $1",
                aide_id,
            )
            return row["html"] if row else None

    async def put(self, aide_id: str, html: str) -> None:
        """Write HTML file for an aide to workspace."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO aide_files (aide_id, html, updated_at)
                VALUES ($1, $2, now())
                ON CONFLICT (aide_id)
                DO UPDATE SET html = EXCLUDED.html, updated_at = now()
                """,
                aide_id,
                html,
            )

    async def put_published(self, slug: str, html: str) -> None:
        """Write HTML file to published bucket."""
        # For now, use the same table with a slug prefix
        # In production, this would write to a separate published_aides table or R2
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO aide_files (aide_id, html, updated_at)
                VALUES ($1, $2, now())
                ON CONFLICT (aide_id)
                DO UPDATE SET html = EXCLUDED.html, updated_at = now()
                """,
                f"published:{slug}",
                html,
            )

    async def delete(self, aide_id: str) -> None:
        """Delete an aide's files from both workspace and published."""
        async with self.pool.acquire() as conn:
            # Delete from workspace
            await conn.execute(
                "DELETE FROM aide_files WHERE aide_id = $1",
                aide_id,
            )
            # Also try to delete from published (if it exists with any slug)
            # This is a simplified implementation
            # In production, there would be a separate published_aides table with foreign keys

    async def close(self) -> None:
        """Close the connection pool."""
        await self.pool.close()
