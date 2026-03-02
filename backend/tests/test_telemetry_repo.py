"""
Tests for turn telemetry repository methods.

Tests:
  test_insert_turn_creates_row
  test_get_turns_returns_chronological
  test_get_turns_respects_rls
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend import db
from backend.models.telemetry import TokenUsage, TurnTelemetry
from backend.repos import telemetry_repo

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_insert_turn_creates_row(initialize_pool, test_user_id) -> None:
    """insert_turn() creates a row and returns its UUID."""
    # Create a test aide
    aide_id = uuid4()
    async with db.system_conn() as conn:
        await conn.execute(
            "INSERT INTO aides (id, user_id, title, r2_prefix) VALUES ($1, $2, $3, $4)",
            aide_id,
            test_user_id,
            "Test Aide",
            f"test-{aide_id}",
        )

    turn = TurnTelemetry(
        turn=1,
        tier="L3",
        model="sonnet",
        message="hello",
        tool_calls=[{"name": "mutate_entity", "input": {"action": "create"}}],
        text_blocks=["response"],
        usage=TokenUsage(input_tokens=100, output_tokens=50),
        ttfc_ms=200,
        ttc_ms=1000,
    )

    row_id = await telemetry_repo.insert_turn(test_user_id, aide_id, turn)
    assert row_id is not None

    # Verify the row exists
    async with db.user_conn(test_user_id) as conn:
        row = await conn.fetchrow("SELECT * FROM aide_turn_telemetry WHERE id = $1", row_id)
    assert row is not None
    assert row["turn_num"] == 1
    assert row["tier"] == "L3"
    assert row["model"] == "sonnet"
    assert row["message"] == "hello"

    # Cleanup
    async with db.system_conn() as conn:
        await conn.execute("DELETE FROM aide_turn_telemetry WHERE id = $1", row_id)
        await conn.execute("DELETE FROM aides WHERE id = $1", aide_id)


async def test_get_turns_returns_chronological(initialize_pool, test_user_id) -> None:
    """get_turns_for_aide() returns turns ordered by turn number."""
    # Create a test aide
    aide_id = uuid4()
    async with db.system_conn() as conn:
        await conn.execute(
            "INSERT INTO aides (id, user_id, title, r2_prefix) VALUES ($1, $2, $3, $4)",
            aide_id,
            test_user_id,
            "Test Aide",
            f"test-{aide_id}",
        )

    # Insert turns out of order
    row_ids = []
    for i in [3, 1, 2]:
        turn = TurnTelemetry(
            turn=i,
            tier="L3",
            model="sonnet",
            message=f"msg{i}",
            tool_calls=[],
            text_blocks=[],
            usage=TokenUsage(input_tokens=100, output_tokens=50),
            ttfc_ms=200,
            ttc_ms=1000,
        )
        row_id = await telemetry_repo.insert_turn(test_user_id, aide_id, turn)
        row_ids.append(row_id)

    turns = await telemetry_repo.get_turns_for_aide(test_user_id, aide_id)
    assert [t.turn for t in turns] == [1, 2, 3]
    assert [t.message for t in turns] == ["msg1", "msg2", "msg3"]

    # Cleanup
    async with db.system_conn() as conn:
        await conn.execute("DELETE FROM aide_turn_telemetry WHERE id = ANY($1::uuid[])", row_ids)
        await conn.execute("DELETE FROM aides WHERE id = $1", aide_id)


async def test_get_turns_respects_rls(initialize_pool, test_user_id, second_user_id) -> None:
    """get_turns_for_aide() enforces RLS - other users get empty list."""
    # Create a test aide for first user
    aide_id = uuid4()
    async with db.system_conn() as conn:
        await conn.execute(
            "INSERT INTO aides (id, user_id, title, r2_prefix) VALUES ($1, $2, $3, $4)",
            aide_id,
            test_user_id,
            "Test Aide",
            f"test-{aide_id}",
        )

    turn = TurnTelemetry(
        turn=1,
        tier="L3",
        model="sonnet",
        message="hello",
        tool_calls=[],
        text_blocks=[],
        usage=TokenUsage(input_tokens=100, output_tokens=50),
        ttfc_ms=200,
        ttc_ms=1000,
    )
    row_id = await telemetry_repo.insert_turn(test_user_id, aide_id, turn)

    # Other user should get empty list
    turns = await telemetry_repo.get_turns_for_aide(second_user_id, aide_id)
    assert turns == []

    # Original user should see the turn
    turns = await telemetry_repo.get_turns_for_aide(test_user_id, aide_id)
    assert len(turns) == 1
    assert turns[0].turn == 1

    # Cleanup
    async with db.system_conn() as conn:
        await conn.execute("DELETE FROM aide_turn_telemetry WHERE id = $1", row_id)
        await conn.execute("DELETE FROM aides WHERE id = $1", aide_id)
