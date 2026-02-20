"""Tests for the cold load hydration endpoint."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio

from backend.auth import create_jwt
from backend.main import app
from backend.models.aide import CreateAideRequest
from backend.repos.aide_repo import AideRepo
from backend.repos.conversation_repo import ConversationRepo
from backend.utils.snapshot_hash import hash_snapshot

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session")
async def async_client():
    """Async HTTP client against the ASGI app."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


aide_repo = AideRepo()
conversation_repo = ConversationRepo()


async def test_hydrate_endpoint_returns_complete_state(async_client, test_user_id, initialize_pool):
    """Test that the hydrate endpoint returns all necessary state for cold load."""
    # Create an aide with some state
    req = CreateAideRequest(title="Test Aide")
    aide = await aide_repo.create(test_user_id, req)

    # Add some state to the aide
    snapshot = {
        "entities": {
            "e1": {"_schema": "person", "name": "Alice"},
            "e2": {"_schema": "person", "name": "Bob"},
        },
        "meta": {"title": "Test Aide"},
    }
    event_log = [
        {
            "id": "evt_1",
            "sequence": 0,
            "timestamp": "2026-02-20T12:00:00Z",
            "actor": str(test_user_id),
            "source": "web",
            "type": "entity.create",
            "payload": {"id": "e1", "fields": {"name": "Alice"}},
        }
    ]
    await aide_repo.update_state(test_user_id, aide.id, snapshot, event_log, title="Test Aide")

    # Create a conversation with some messages
    conversation = await conversation_repo.create(test_user_id, aide.id, channel="web")
    from datetime import UTC, datetime

    from backend.models.conversation import Message

    await conversation_repo.append_message(
        test_user_id,
        conversation.id,
        Message(role="user", content="Create two people", timestamp=datetime.now(UTC)),
    )
    await conversation_repo.append_message(
        test_user_id,
        conversation.id,
        Message(role="assistant", content="Created Alice and Bob", timestamp=datetime.now(UTC)),
    )

    # Make request to hydrate endpoint
    token = create_jwt(test_user_id)
    response = await async_client.get(
        f"/api/aides/{aide.id}/hydrate",
        cookies={"session": token},
    )

    assert response.status_code == 200
    data = response.json()

    # Verify all required fields are present
    assert "snapshot" in data
    assert "events" in data
    assert "blueprint" in data
    assert "messages" in data
    assert "snapshot_hash" in data

    # Verify snapshot content
    assert data["snapshot"]["entities"]["e1"]["name"] == "Alice"
    assert data["snapshot"]["entities"]["e2"]["name"] == "Bob"
    assert data["snapshot"]["meta"]["title"] == "Test Aide"

    # Verify events
    assert len(data["events"]) == 1
    assert data["events"][0]["type"] == "entity.create"

    # Verify blueprint
    assert data["blueprint"]["identity"] == "Test Aide"
    assert data["blueprint"]["voice"] == "declarative"

    # Verify messages
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"] == "Create two people"
    assert data["messages"][1]["role"] == "assistant"
    assert data["messages"][1]["content"] == "Created Alice and Bob"

    # Verify snapshot hash
    expected_hash = hash_snapshot(snapshot)
    assert data["snapshot_hash"] == expected_hash


async def test_hydrate_endpoint_empty_aide(async_client, test_user_id, initialize_pool):
    """Test hydrate endpoint with a new aide that has no state yet."""
    # Create an empty aide
    req = CreateAideRequest(title="Empty Aide")
    aide = await aide_repo.create(test_user_id, req)

    # Make request to hydrate endpoint
    token = create_jwt(test_user_id)
    response = await async_client.get(
        f"/api/aides/{aide.id}/hydrate",
        cookies={"session": token},
    )

    assert response.status_code == 200
    data = response.json()

    # Verify empty state
    assert data["snapshot"] == {}
    assert data["events"] == []
    assert data["messages"] == []
    assert data["blueprint"]["identity"] == "Empty Aide"
    assert data["snapshot_hash"] == hash_snapshot({})


async def test_hydrate_endpoint_unauthenticated(async_client, test_user_id, initialize_pool):
    """Test that unauthenticated requests are rejected."""
    # Create an aide
    req = CreateAideRequest(title="Test Aide")
    aide = await aide_repo.create(test_user_id, req)

    # Make request without auth
    response = await async_client.get(f"/api/aides/{aide.id}/hydrate")

    assert response.status_code == 401


async def test_hydrate_endpoint_not_found(async_client, test_user_id, initialize_pool):
    """Test that requesting a non-existent aide returns 404."""
    token = create_jwt(test_user_id)
    response = await async_client.get(
        "/api/aides/00000000-0000-0000-0000-000000000000/hydrate",
        cookies={"session": token},
    )

    assert response.status_code == 404


async def test_hydrate_endpoint_cross_user_access(async_client, test_user_id, second_user_id, initialize_pool):
    """Test that RLS prevents cross-user access to hydrate endpoint."""
    # User 1 creates an aide
    req = CreateAideRequest(title="User 1 Aide")
    aide = await aide_repo.create(test_user_id, req)

    # User 2 tries to hydrate user 1's aide
    token = create_jwt(second_user_id)
    response = await async_client.get(
        f"/api/aides/{aide.id}/hydrate",
        cookies={"session": token},
    )

    assert response.status_code == 404
