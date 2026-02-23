"""API token repository."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from asyncpg import Connection

from backend.models.api_token import ApiToken, ApiTokenListItem


def generate_token() -> str:
    """Generate a new API token with aide_ prefix."""
    return f"aide_{secrets.token_hex(32)}"


def hash_token(token: str) -> str:
    """Hash a token using SHA-256."""
    return hashlib.sha256(token.encode()).hexdigest()


async def create_token(
    conn: Connection,
    user_id: UUID,
    name: str = "cli",
    scope: str = "cli",
    expiry_days: int = 90,
) -> tuple[str, ApiToken]:
    """Create a new API token. Returns (raw_token, token_record)."""
    raw_token = generate_token()
    token_hash = hash_token(raw_token)
    expires_at = datetime.now(UTC) + timedelta(days=expiry_days)

    row = await conn.fetchrow(
        """
        INSERT INTO api_tokens (user_id, token_hash, name, scope, expires_at)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, user_id, token_hash, name, scope, last_used_at, expires_at, revoked, created_at
        """,
        user_id,
        token_hash,
        name,
        scope,
        expires_at,
    )

    token = ApiToken(**dict(row))
    return raw_token, token


async def get_by_hash(conn: Connection, token_hash: str) -> ApiToken | None:
    """Get token by hash."""
    row = await conn.fetchrow(
        """
        SELECT id, user_id, token_hash, name, scope, last_used_at, expires_at, revoked, created_at
        FROM api_tokens
        WHERE token_hash = $1
        """,
        token_hash,
    )

    if not row:
        return None

    return ApiToken(**dict(row))


async def touch_last_used(conn: Connection, token_id: UUID) -> None:
    """Update last_used_at timestamp."""
    await conn.execute(
        """
        UPDATE api_tokens
        SET last_used_at = now()
        WHERE id = $1
        """,
        token_id,
    )


async def list_tokens(conn: Connection, user_id: UUID) -> list[ApiTokenListItem]:
    """List all tokens for a user (RLS enforced)."""
    rows = await conn.fetch(
        """
        SELECT id, name, scope, last_used_at, expires_at, revoked, created_at
        FROM api_tokens
        WHERE user_id = $1
        ORDER BY created_at DESC
        """,
        user_id,
    )

    return [ApiTokenListItem(**dict(row)) for row in rows]


async def revoke_token(conn: Connection, token_id: UUID, user_id: UUID) -> bool:
    """Revoke a token. Returns True if revoked, False if not found."""
    result = await conn.execute(
        """
        UPDATE api_tokens
        SET revoked = true
        WHERE id = $1 AND user_id = $2
        """,
        token_id,
        user_id,
    )

    # result is a string like "UPDATE 1" or "UPDATE 0"
    return result.endswith(" 1")
