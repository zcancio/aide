"""
Pytest configuration and fixtures for AIde tests.
"""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest_asyncio

from backend import db

# Set test environment variables before importing config
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/aide_test")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only")
os.environ.setdefault("RESEND_API_KEY", "test-resend-key")
os.environ.setdefault("STRIPE_SECRET_KEY", "test-stripe-key")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "test-webhook-secret")


@pytest_asyncio.fixture(scope="session", autouse=True)
async def initialize_pool():
    """Initialize pool once for all tests."""
    await db.init_pool()
    yield
    await db.close_pool()


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Create event loop for the session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_user_id():
    """Create a test user and return their ID."""
    user_id = uuid4()
    user_email = f"test-{user_id}@example.com"

    async with db.system_conn() as conn:
        await conn.execute(
            "INSERT INTO users (id, email, name) VALUES ($1, $2, $3)",
            user_id,
            user_email,
            "Test User",
        )

    yield user_id

    async with db.system_conn() as conn:
        await conn.execute("DELETE FROM users WHERE id = $1", user_id)


@pytest_asyncio.fixture
async def second_user_id():
    """Create a second test user for cross-user RLS tests."""
    user_id = uuid4()
    user_email = f"test-{user_id}@example.com"

    async with db.system_conn() as conn:
        await conn.execute(
            "INSERT INTO users (id, email, name) VALUES ($1, $2, $3)",
            user_id,
            user_email,
            "Second Test User",
        )

    yield user_id

    async with db.system_conn() as conn:
        await conn.execute("DELETE FROM users WHERE id = $1", user_id)
