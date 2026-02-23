"""CLI auth repository."""

from datetime import datetime
from uuid import UUID

from asyncpg import Connection

from backend.models.cli_auth import CliAuthRequest


async def create_request(
    conn: Connection,
    device_code: str,
    expires_at: datetime,
) -> CliAuthRequest:
    """Create a new CLI auth request."""
    row = await conn.fetchrow(
        """
        INSERT INTO cli_auth_requests (device_code, expires_at)
        VALUES ($1, $2)
        RETURNING id, device_code, user_id, status, api_token, expires_at, created_at
        """,
        device_code,
        expires_at,
    )

    return CliAuthRequest(**dict(row))


async def get_by_device_code(conn: Connection, device_code: str) -> CliAuthRequest | None:
    """Get auth request by device code."""
    row = await conn.fetchrow(
        """
        SELECT id, device_code, user_id, status, api_token, expires_at, created_at
        FROM cli_auth_requests
        WHERE device_code = $1
        """,
        device_code,
    )

    if not row:
        return None

    return CliAuthRequest(**dict(row))


async def approve_request(
    conn: Connection,
    device_code: str,
    user_id: UUID,
    api_token: str,
) -> CliAuthRequest | None:
    """Approve an auth request. Returns updated request or None if not found."""
    row = await conn.fetchrow(
        """
        UPDATE cli_auth_requests
        SET status = 'approved', user_id = $1, api_token = $2
        WHERE device_code = $3 AND status = 'pending'
        RETURNING id, device_code, user_id, status, api_token, expires_at, created_at
        """,
        user_id,
        api_token,
        device_code,
    )

    if not row:
        return None

    return CliAuthRequest(**dict(row))


async def mark_expired(conn: Connection, device_code: str) -> None:
    """Mark an auth request as expired."""
    await conn.execute(
        """
        UPDATE cli_auth_requests
        SET status = 'expired'
        WHERE device_code = $1
        """,
        device_code,
    )


async def delete_expired(conn: Connection, cutoff: datetime) -> int:
    """Delete expired auth requests older than cutoff. Returns count deleted."""
    result = await conn.execute(
        """
        DELETE FROM cli_auth_requests
        WHERE expires_at < $1
        """,
        cutoff,
    )

    # result is a string like "DELETE 5"
    return int(result.split()[-1])
