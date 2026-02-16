"""
Database connection pool and RLS-scoped connection managers.

All database access goes through user_conn() or system_conn().
Never use pool.acquire() directly outside this module.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from uuid import UUID

import asyncpg

from backend import config

pool: asyncpg.Pool | None = None


async def init_pool() -> None:
    """
    Initialize the connection pool.
    Called once at application startup.
    """
    global pool
    pool = await asyncpg.create_pool(
        dsn=config.DATABASE_URL,
        min_size=2,
        max_size=20,
        command_timeout=60,
        init=_init_connection,
    )


async def close_pool() -> None:
    """
    Close the connection pool.
    Called at application shutdown.
    """
    global pool
    if pool is not None:
        await pool.close()
        pool = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    """
    Initialize each new connection.
    Sets up type codecs for UUID and JSON handling.
    """
    await conn.set_type_codec(
        "uuid",
        encoder=str,
        decoder=lambda x: UUID(x),
        schema="pg_catalog",
    )
    # JSONB codec - decode to Python dict/list
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    await conn.set_type_codec(
        "json",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


@asynccontextmanager
async def user_conn(user_id: str | UUID):
    """
    Acquire a database connection scoped to a specific user via RLS.

    Every query through this connection can only see/modify rows
    belonging to this user. Enforced by Postgres RLS policies.

    Usage:
        async with user_conn(user_id) as conn:
            row = await conn.fetchrow("SELECT * FROM aides WHERE id = $1", aide_id)

    Args:
        user_id: UUID of the user to scope the connection to

    Yields:
        asyncpg.Connection with RLS context set
    """
    if pool is None:
        raise RuntimeError("Database pool not initialized. Call init_pool() first.")

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Set RLS context. All policies reference current_setting('app.user_id')
            await conn.execute(
                "SELECT set_config('app.user_id', $1, true)",
                str(user_id),
            )
            yield conn


@asynccontextmanager
async def system_conn():
    """
    Acquire a database connection without user scoping.

    For system operations only:
    - Migrations (alembic)
    - Background tasks (abuse checks, cleanup)
    - Auth operations (magic link verification, user creation)
    - Operations that span multiple users

    WARNING: Should be rare. If you're using this in a route handler
    that returns user data, you're probably doing it wrong.

    Usage:
        async with system_conn() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email)

    Yields:
        asyncpg.Connection without RLS scoping
    """
    if pool is None:
        raise RuntimeError("Database pool not initialized. Call init_pool() first.")

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Explicitly reset RLS context to empty string.
            # RLS policies use CASE WHEN NULLIF(current_setting('app.user_id', true), '') IS NULL
            # to bypass for system operations. Using LOCAL (true) ensures it's cleaned up.
            await conn.execute("SELECT set_config('app.user_id', '', true)")
            yield conn
