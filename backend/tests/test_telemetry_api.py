"""Tests for telemetry API endpoints."""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio

from backend import db
from backend.auth import create_jwt
from backend.models.telemetry import TokenUsage, TurnTelemetry
from backend.repos import telemetry_repo

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session")
async def test_aide_with_turns(initialize_pool, test_user_id):
    """Create a test aide with turn telemetry data."""
    aide_id = uuid4()
    async with db.system_conn() as conn:
        await conn.execute(
            "INSERT INTO aides (id, user_id, title, r2_prefix, state) VALUES ($1, $2, $3, $4, $5)",
            aide_id,
            test_user_id,
            "Test Aide with Turns",
            f"test-{aide_id}",
            {"entities": {"e1": {"_schema": "Task", "name": "Buy milk"}}},
        )

    # Insert some turns
    turn_ids = []
    for i in range(1, 3):
        turn = TurnTelemetry(
            turn=i,
            tier="L3",
            model="sonnet",
            message=f"message {i}",
            tool_calls=[{"name": "entity.create", "input": {"id": f"e{i}"}}],
            text_blocks=[f"response {i}"],
            usage=TokenUsage(input_tokens=100 * i, output_tokens=50 * i),
            ttfc_ms=200 * i,
            ttc_ms=1000 * i,
        )
        row_id = await telemetry_repo.insert_turn(test_user_id, aide_id, turn)
        turn_ids.append(row_id)

    class AideFixture:
        pass

    fixture = AideFixture()
    fixture.id = aide_id
    fixture.user_id = test_user_id
    fixture.turn_ids = turn_ids

    yield fixture

    # Cleanup
    async with db.system_conn() as conn:
        await conn.execute("DELETE FROM aide_turn_telemetry WHERE id = ANY($1::uuid[])", turn_ids)
        await conn.execute("DELETE FROM aides WHERE id = $1", aide_id)


async def test_get_telemetry_returns_404_for_missing_aide(async_client, test_user_id):
    """GET /api/aides/{id}/telemetry for missing aide → 404."""
    token = create_jwt(test_user_id)
    response = await async_client.get(
        f"/api/aides/{uuid4()}/telemetry",
        cookies={"session": token},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


async def test_get_telemetry_requires_auth(async_client, test_aide_with_turns):
    """GET /api/aides/{id}/telemetry without auth → 401."""
    response = await async_client.get(
        f"/api/aides/{test_aide_with_turns.id}/telemetry",
    )
    assert response.status_code == 401


async def test_get_telemetry_returns_aide_telemetry(async_client, test_user_id, test_aide_with_turns):
    """GET /api/aides/{id}/telemetry → 200 with telemetry data."""
    token = create_jwt(test_user_id)
    response = await async_client.get(
        f"/api/aides/{test_aide_with_turns.id}/telemetry",
        cookies={"session": token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["aide_id"] == str(test_aide_with_turns.id)
    assert data["name"] == "Test Aide with Turns"
    assert "timestamp" in data
    assert "turns" in data
    assert len(data["turns"]) == 2
    assert "final_snapshot" in data


async def test_get_telemetry_respects_rls(async_client, second_user_id, test_aide_with_turns):
    """GET /api/aides/{id}/telemetry by different user → 404."""
    token = create_jwt(second_user_id)
    response = await async_client.get(
        f"/api/aides/{test_aide_with_turns.id}/telemetry",
        cookies={"session": token},
    )
    assert response.status_code == 404


async def test_telemetry_matches_eval_format(async_client, test_user_id, test_aide_with_turns):
    """Verify telemetry response matches eval golden format."""
    token = create_jwt(test_user_id)
    response = await async_client.get(
        f"/api/aides/{test_aide_with_turns.id}/telemetry",
        cookies={"session": token},
    )
    data = response.json()

    # Verify eval golden format fields
    assert "aide_id" in data
    assert "name" in data
    assert "timestamp" in data
    assert "turns" in data

    if data["turns"]:
        turn = data["turns"][0]
        assert "turn" in turn
        assert "tier" in turn
        assert "model" in turn
        assert "message" in turn
        assert "tool_calls" in turn
        assert "text_blocks" in turn
        assert "usage" in turn
        assert "ttfc_ms" in turn
        assert "ttc_ms" in turn

        # Verify usage structure
        usage = turn["usage"]
        assert "input_tokens" in usage
        assert "output_tokens" in usage
        assert "cache_read" in usage
        assert "cache_creation" in usage


async def test_telemetry_includes_final_snapshot(async_client, test_user_id, test_aide_with_turns):
    """Verify final_snapshot contains the aide state."""
    token = create_jwt(test_user_id)
    response = await async_client.get(
        f"/api/aides/{test_aide_with_turns.id}/telemetry",
        cookies={"session": token},
    )
    data = response.json()

    assert "final_snapshot" in data
    assert data["final_snapshot"] is not None
    assert "entities" in data["final_snapshot"]
    assert "e1" in data["final_snapshot"]["entities"]


async def test_telemetry_turns_ordered_chronologically(async_client, test_user_id, test_aide_with_turns):
    """Verify turns are returned in chronological order."""
    token = create_jwt(test_user_id)
    response = await async_client.get(
        f"/api/aides/{test_aide_with_turns.id}/telemetry",
        cookies={"session": token},
    )
    data = response.json()

    turns = data["turns"]
    assert len(turns) == 2
    assert turns[0]["turn"] == 1
    assert turns[1]["turn"] == 2
    assert turns[0]["message"] == "message 1"
    assert turns[1]["message"] == "message 2"


# ===========================================================================
# Telemetry export endpoint tests
# ===========================================================================


@pytest_asyncio.fixture(loop_scope="session")
async def test_aide(initialize_pool, test_user_id):
    """Create a minimal test aide without turns."""
    aide_id = uuid4()
    async with db.system_conn() as conn:
        await conn.execute(
            "INSERT INTO aides (id, user_id, title, r2_prefix, state) VALUES ($1, $2, $3, $4, $5)",
            aide_id,
            test_user_id,
            "Minimal Test Aide",
            f"test-{aide_id}",
            {"entities": {}},
        )

    class AideFixture:
        pass

    fixture = AideFixture()
    fixture.id = aide_id
    fixture.user_id = test_user_id

    yield fixture

    # Cleanup
    async with db.system_conn() as conn:
        await conn.execute("DELETE FROM aides WHERE id = $1", aide_id)


async def test_export_telemetry_headers(async_client, test_user_id, test_aide):
    """Export endpoint returns JSON with attachment headers."""
    token = create_jwt(test_user_id)
    response = await async_client.get(
        f"/api/aides/{test_aide.id}/telemetry/export",
        cookies={"session": token},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert "attachment" in response.headers["content-disposition"]
    assert str(test_aide.id) in response.headers["content-disposition"]


async def test_export_telemetry_format(async_client, test_user_id, test_aide_with_turns):
    """Export returns valid AideTelemetry structure."""
    token = create_jwt(test_user_id)
    response = await async_client.get(
        f"/api/aides/{test_aide_with_turns.id}/telemetry/export",
        cookies={"session": token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "aide_id" in data
    assert "turns" in data
    assert isinstance(data["turns"], list)
    assert "name" in data
    assert "timestamp" in data


async def test_export_telemetry_rls(async_client, second_user_id, test_aide_with_turns):
    """User cannot export another user's aide telemetry."""
    token = create_jwt(second_user_id)
    response = await async_client.get(
        f"/api/aides/{test_aide_with_turns.id}/telemetry/export",
        cookies={"session": token},
    )
    assert response.status_code == 404


async def test_export_telemetry_not_found(async_client, test_user_id):
    """Export returns 404 for non-existent aide."""
    token = create_jwt(test_user_id)
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await async_client.get(
        f"/api/aides/{fake_id}/telemetry/export",
        cookies={"session": token},
    )
    assert response.status_code == 404


async def test_export_telemetry_unauthenticated(async_client, test_aide):
    """Export requires authentication."""
    response = await async_client.get(f"/api/aides/{test_aide.id}/telemetry/export")
    assert response.status_code == 401
