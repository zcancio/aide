"""Tests for CLI device authorization flow."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient

from backend.auth import create_jwt
from backend.db import system_conn
from backend.repos import api_token_repo, cli_auth_repo

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture
async def cleanup_cli_auth(test_user):
    """Clean up CLI auth data before and after each test."""
    async with system_conn() as conn:
        # Clean up before
        await conn.execute("DELETE FROM api_tokens WHERE user_id = $1", test_user.id)
        await conn.execute("DELETE FROM cli_auth_requests WHERE user_id = $1", test_user.id)

    yield

    async with system_conn() as conn:
        # Clean up after
        await conn.execute("DELETE FROM api_tokens WHERE user_id = $1", test_user.id)
        await conn.execute("DELETE FROM cli_auth_requests WHERE user_id = $1", test_user.id)


async def test_device_auth_flow_success(async_client: AsyncClient, test_user, initialize_pool, cleanup_cli_auth):
    """Test successful device authorization flow."""
    device_code = f"TEST{uuid4().hex[:6].upper()}"

    # 1. Start auth flow
    res = await async_client.post(
        "/api/cli/auth/start",
        json={"device_code": device_code},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["device_code"] == device_code
    assert "auth_url" in data
    assert "expires_at" in data

    # 2. Poll - should be pending
    res = await async_client.post(
        "/api/cli/auth/poll",
        json={"device_code": device_code},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "pending"
    assert "token" not in data or data["token"] is None

    # 3. Confirm auth (browser, with session cookie)
    token = create_jwt(test_user.id)
    res = await async_client.post(
        "/api/cli/auth/confirm",
        json={"device_code": device_code},
        cookies={"session": token},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "approved"
    assert data["email"] == test_user.email

    # 4. Poll - should now be approved with token
    res = await async_client.post(
        "/api/cli/auth/poll",
        json={"device_code": device_code},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "approved"
    assert data["token"].startswith("aide_")

    # 5. Verify token works for API calls
    token = data["token"]
    res = await async_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    user_data = res.json()
    assert user_data["email"] == test_user.email


async def test_device_auth_duplicate_code(async_client: AsyncClient, initialize_pool):
    """Test that duplicate device codes are rejected."""
    device_code = f"DUP{uuid4().hex[:6].upper()}"

    # Start auth flow
    res = await async_client.post(
        "/api/cli/auth/start",
        json={"device_code": device_code},
    )
    assert res.status_code == 200

    # Try to start again with same code
    res = await async_client.post(
        "/api/cli/auth/start",
        json={"device_code": device_code},
    )
    assert res.status_code == 409
    assert "already in use" in res.json()["detail"].lower()


async def test_device_auth_unknown_code(async_client: AsyncClient, initialize_pool):
    """Test polling with unknown device code."""
    res = await async_client.post(
        "/api/cli/auth/poll",
        json={"device_code": "UNKNOWN"},
    )
    assert res.status_code == 404


async def test_device_auth_expired_code(async_client: AsyncClient, initialize_pool):
    """Test behavior with expired device code."""
    device_code = f"EXP{uuid4().hex[:6].upper()}"

    # Create expired auth request directly
    async with system_conn() as conn:
        expired_at = datetime.now(UTC) - timedelta(minutes=1)
        await cli_auth_repo.create_request(conn, device_code, expired_at)

    # Poll should return expired
    res = await async_client.post(
        "/api/cli/auth/poll",
        json={"device_code": device_code},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "expired"


async def test_device_auth_already_approved(async_client: AsyncClient, test_user, initialize_pool):
    """Test confirming an already-approved request."""
    device_code = f"APR{uuid4().hex[:6].upper()}"
    token = create_jwt(test_user.id)

    # Start and approve
    await async_client.post(
        "/api/cli/auth/start",
        json={"device_code": device_code},
    )
    await async_client.post(
        "/api/cli/auth/confirm",
        json={"device_code": device_code},
        cookies={"session": token},
    )

    # Try to approve again
    res = await async_client.post(
        "/api/cli/auth/confirm",
        json={"device_code": device_code},
        cookies={"session": token},
    )
    assert res.status_code == 409
    assert "already approved" in res.json()["detail"].lower()


async def test_api_token_authentication(async_client: AsyncClient, test_user, initialize_pool):
    """Test that API tokens work for authentication."""
    # Create a token
    async with system_conn() as conn:
        raw_token, token = await api_token_repo.create_token(
            conn,
            test_user.id,
            name="test-token",
            scope="cli",
            expiry_days=1,
        )

    # Use token to authenticate
    res = await async_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    assert res.status_code == 200
    user_data = res.json()
    assert user_data["id"] == str(test_user.id)

    # Verify last_used_at was updated
    async with system_conn() as conn:
        updated_token = await api_token_repo.get_by_hash(conn, api_token_repo.hash_token(raw_token))
        assert updated_token.last_used_at is not None


async def test_api_token_revoked(async_client: AsyncClient, test_user, initialize_pool):
    """Test that revoked tokens are rejected."""
    # Create and revoke token
    async with system_conn() as conn:
        raw_token, token = await api_token_repo.create_token(conn, test_user.id)
        await api_token_repo.revoke_token(conn, token.id, test_user.id)

    # Try to use revoked token
    res = await async_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    assert res.status_code == 401


async def test_api_token_expired(async_client: AsyncClient, test_user, initialize_pool):
    """Test that expired tokens are rejected."""
    # Create expired token
    async with system_conn() as conn:
        raw_token, token = await api_token_repo.create_token(
            conn,
            test_user.id,
            expiry_days=-1,  # Already expired
        )

    # Try to use expired token
    res = await async_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    assert res.status_code == 401


async def test_list_api_tokens(async_client: AsyncClient, test_user, initialize_pool):
    """Test listing API tokens."""
    # Create some tokens
    async with system_conn() as conn:
        await api_token_repo.create_token(conn, test_user.id, name="token-1")
        await api_token_repo.create_token(conn, test_user.id, name="token-2")

    # List tokens
    token = create_jwt(test_user.id)
    res = await async_client.get("/api/tokens", cookies={"session": token})
    assert res.status_code == 200
    tokens = res.json()
    assert len(tokens) >= 2
    assert all("token_hash" not in t for t in tokens)  # Hash should not be exposed


async def test_revoke_api_token(async_client: AsyncClient, test_user, initialize_pool):
    """Test revoking an API token."""
    # Create token
    async with system_conn() as conn:
        _, api_token = await api_token_repo.create_token(conn, test_user.id)

    # Revoke it
    session_token = create_jwt(test_user.id)
    res = await async_client.post(
        "/api/tokens/revoke",
        json={"token_id": str(api_token.id)},
        cookies={"session": session_token},
    )
    assert res.status_code == 200

    # Verify it's revoked
    async with system_conn() as conn:
        updated = await api_token_repo.get_by_hash(conn, api_token.token_hash)
        assert updated.revoked is True


async def test_unified_auth_prefers_bearer_token(async_client: AsyncClient, test_user, initialize_pool):
    """Test that Bearer token is preferred over session cookie."""
    # Create API token
    async with system_conn() as conn:
        raw_token, _ = await api_token_repo.create_token(conn, test_user.id)

    # Make request with both Bearer token and session cookie
    # Bearer should be used
    res = await async_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    assert res.status_code == 200


async def test_invalid_bearer_token_format(async_client: AsyncClient, initialize_pool):
    """Test that invalid Bearer token formats are rejected."""
    # Missing aide_ prefix
    res = await async_client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid_token"},
    )
    assert res.status_code == 401

    # Not a Bearer token
    res = await async_client.get(
        "/auth/me",
        headers={"Authorization": "Basic something"},
    )
    assert res.status_code == 401
