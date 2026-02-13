"""
Tests for authentication (magic links and JWT sessions).
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.auth import create_jwt, decode_jwt
from backend.db import system_conn
from backend.main import app
from backend.repos.magic_link_repo import MagicLinkRepo
from backend.repos.user_repo import UserRepo

pytestmark = pytest.mark.asyncio(loop_scope="session")

magic_link_repo = MagicLinkRepo()
user_repo = UserRepo()
client = TestClient(app)


class TestJWT:
    """Test JWT creation and validation."""

    def test_create_jwt(self):
        """Test creating a JWT token."""
        user_id = uuid4()
        token = create_jwt(user_id)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_jwt(self):
        """Test decoding a valid JWT token."""
        user_id = uuid4()
        token = create_jwt(user_id)

        payload = decode_jwt(token)

        assert payload["sub"] == str(user_id)
        assert "exp" in payload
        assert "iat" in payload

    def test_decode_expired_jwt(self):
        """Test decoding an expired JWT token raises exception."""
        import jwt

        user_id = uuid4()
        # Create token that expired 1 hour ago
        expires_at = datetime.now(UTC) - timedelta(hours=1)
        payload = {
            "sub": str(user_id),
            "exp": expires_at,
            "iat": datetime.now(UTC),
        }
        token = jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            decode_jwt(token)

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_decode_invalid_jwt(self):
        """Test decoding an invalid JWT raises exception."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            decode_jwt("invalid.token.here")

        assert exc_info.value.status_code == 401


class TestMagicLinkRepo:
    """Test magic link repository operations."""

    async def test_create_magic_link(self):
        """Test creating a magic link."""
        email = f"test-{uuid4()}@example.com"

        magic_link = await magic_link_repo.create(email)

        assert magic_link.email == email
        assert len(magic_link.token) == 64  # 32 bytes hex = 64 chars
        assert magic_link.used is False
        assert magic_link.expires_at > datetime.now(UTC)

    async def test_get_by_token(self):
        """Test getting a magic link by token."""
        email = f"test-{uuid4()}@example.com"
        created = await magic_link_repo.create(email)

        retrieved = await magic_link_repo.get_by_token(created.token)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.email == email
        assert retrieved.token == created.token

    async def test_get_by_invalid_token(self):
        """Test getting a magic link with invalid token returns None."""
        retrieved = await magic_link_repo.get_by_token("nonexistent-token")

        assert retrieved is None

    async def test_mark_used(self):
        """Test marking a magic link as used."""
        email = f"test-{uuid4()}@example.com"
        magic_link = await magic_link_repo.create(email)

        success = await magic_link_repo.mark_used(magic_link.token)
        assert success is True

        # Verify it's marked as used
        retrieved = await magic_link_repo.get_by_token(magic_link.token)
        assert retrieved.used is True

    async def test_count_recent_by_email(self):
        """Test counting recent magic links by email."""
        email = f"test-{uuid4()}@example.com"

        # Create 3 magic links
        await magic_link_repo.create(email)
        await magic_link_repo.create(email)
        await magic_link_repo.create(email)

        count = await magic_link_repo.count_recent_by_email(email, hours=1)
        assert count == 3

    async def test_cleanup_expired(self):
        """Test cleaning up expired magic links."""
        email = f"test-{uuid4()}@example.com"

        # Create a magic link
        magic_link = await magic_link_repo.create(email)

        # Mark it as used
        await magic_link_repo.mark_used(magic_link.token)

        # Set created_at to 2 hours ago so it gets cleaned up
        async with system_conn() as conn:
            await conn.execute(
                "UPDATE magic_links SET created_at = now() - interval '2 hours' WHERE id = $1",
                magic_link.id,
            )

        # Clean up
        deleted = await magic_link_repo.cleanup_expired(older_than_hours=1)
        assert deleted >= 1

        # Verify it's gone
        retrieved = await magic_link_repo.get_by_token(magic_link.token)
        assert retrieved is None


class TestUserRepo:
    """Test user repository operations."""

    async def test_create_user(self):
        """Test creating a new user."""
        email = f"test-{uuid4()}@example.com"

        user = await user_repo.create(email, name="Test User")

        assert user.email == email
        assert user.name == "Test User"
        assert user.tier == "free"
        assert user.turn_count == 0

        # Clean up
        async with system_conn() as conn:
            await conn.execute("DELETE FROM users WHERE id = $1", user.id)

    async def test_get_by_email(self):
        """Test getting a user by email."""
        email = f"test-{uuid4()}@example.com"
        created = await user_repo.create(email)

        retrieved = await user_repo.get_by_email(email)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.email == email

        # Clean up
        async with system_conn() as conn:
            await conn.execute("DELETE FROM users WHERE id = $1", created.id)

    async def test_get_by_email_not_found(self):
        """Test getting a user by email that doesn't exist."""
        retrieved = await user_repo.get_by_email("nonexistent@example.com")

        assert retrieved is None


class TestAuthRoutes:
    """Test authentication route handlers."""

    async def test_send_magic_link(self):
        """Test sending a magic link (without actually sending email)."""
        # Mock the email service to avoid sending real emails in tests
        import backend.routes.auth_routes as auth_routes_module

        original_send = auth_routes_module.send_magic_link
        email_sent = []

        async def mock_send(email: str, token: str):
            email_sent.append((email, token))

        auth_routes_module.send_magic_link = mock_send

        try:
            email = f"test-{uuid4()}@example.com"
            response = client.post("/auth/send", json={"email": email})

            assert response.status_code == 200
            assert "Magic link sent" in response.json()["message"]
            assert len(email_sent) == 1
            assert email_sent[0][0] == email.lower()
        finally:
            auth_routes_module.send_magic_link = original_send

    async def test_send_magic_link_rate_limit(self):
        """Test magic link rate limiting by email."""
        import backend.routes.auth_routes as auth_routes_module

        original_send = auth_routes_module.send_magic_link

        async def mock_send(email: str, token: str):
            pass

        auth_routes_module.send_magic_link = mock_send

        try:
            email = f"test-{uuid4()}@example.com"

            # Send 5 magic links (the limit)
            for _ in range(config.MAGIC_LINK_RATE_LIMIT_PER_EMAIL):
                await magic_link_repo.create(email)

            # 6th should be rate limited
            response = client.post("/auth/send", json={"email": email})
            assert response.status_code == 429
            assert "Too many requests" in response.json()["detail"]
        finally:
            auth_routes_module.send_magic_link = original_send

    async def test_verify_magic_link_new_user(self):
        """Test verifying a magic link for a new user."""
        email = f"test-{uuid4()}@example.com"
        magic_link = await magic_link_repo.create(email)

        response = client.get(f"/auth/verify?token={magic_link.token}")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == email
        assert data["tier"] == "free"

        # Should have session cookie
        assert "session" in response.cookies

        # Clean up
        user = await user_repo.get_by_email(email)
        if user:
            async with system_conn() as conn:
                await conn.execute("DELETE FROM users WHERE id = $1", user.id)

    async def test_verify_magic_link_existing_user(self):
        """Test verifying a magic link for an existing user."""
        email = f"test-{uuid4()}@example.com"
        existing_user = await user_repo.create(email, name="Existing User")

        magic_link = await magic_link_repo.create(email)

        response = client.get(f"/auth/verify?token={magic_link.token}")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == email
        assert data["name"] == "Existing User"
        assert str(existing_user.id) == data["id"]

        # Clean up
        async with system_conn() as conn:
            await conn.execute("DELETE FROM users WHERE id = $1", existing_user.id)

    async def test_verify_invalid_token(self):
        """Test verifying an invalid token."""
        response = client.get("/auth/verify?token=invalid-token-here")

        assert response.status_code == 401
        assert "Invalid magic link" in response.json()["detail"]

    async def test_verify_used_token(self):
        """Test verifying a token that was already used."""
        email = f"test-{uuid4()}@example.com"
        magic_link = await magic_link_repo.create(email)

        # Mark as used
        await magic_link_repo.mark_used(magic_link.token)

        response = client.get(f"/auth/verify?token={magic_link.token}")

        assert response.status_code == 401
        assert "already been used" in response.json()["detail"]

    async def test_verify_expired_token(self):
        """Test verifying an expired token."""
        email = f"test-{uuid4()}@example.com"

        # Create expired token manually
        token = secrets.token_hex(32)
        expires_at = datetime.now(UTC) - timedelta(minutes=1)  # Expired 1 minute ago

        async with system_conn() as conn:
            await conn.execute(
                """
                INSERT INTO magic_links (email, token, expires_at)
                VALUES ($1, $2, $3)
                """,
                email,
                token,
                expires_at,
            )

        response = client.get(f"/auth/verify?token={token}")

        assert response.status_code == 401
        assert "expired" in response.json()["detail"]

    async def test_get_me_authenticated(self, test_user_id):
        """Test /auth/me endpoint with valid session."""
        token = create_jwt(test_user_id)

        response = client.get("/auth/me", cookies={"session": token})

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_user_id)

    async def test_get_me_unauthenticated(self):
        """Test /auth/me endpoint without session."""
        response = client.get("/auth/me")

        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]

    async def test_logout(self):
        """Test logout endpoint."""
        response = client.post("/auth/logout")

        assert response.status_code == 200
        assert "Logged out" in response.json()["message"]

        # Session cookie should be cleared (max_age=0)
        assert "session" in response.cookies
        # The cookie should be set to empty or have max_age=0
