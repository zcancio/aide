"""Tests for TurnRecorder class."""

from uuid import uuid4

import pytest

from backend import db
from backend.repos import telemetry_repo
from backend.services.telemetry import TurnRecorder

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_turn_recorder_basic_flow(initialize_pool, test_user_id):
    """Test basic turn recorder flow."""
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

    recorder = TurnRecorder(aide_id, test_user_id)
    recorder.start_turn(turn_num=1, tier="L3", model="sonnet", message="hello")
    recorder.record_tool_call("mutate_entity", {"action": "create", "id": "x"})
    recorder.record_text_block("Done")
    recorder.mark_first_content()
    recorder.set_usage(input_tokens=1000, output_tokens=500)

    row_id = await recorder.finish()
    assert row_id is not None

    # Cleanup
    async with db.system_conn() as conn:
        await conn.execute("DELETE FROM aide_turn_telemetry WHERE id = $1", row_id)
        await conn.execute("DELETE FROM aides WHERE id = $1", aide_id)


async def test_turn_recorder_with_timestamps(initialize_pool, test_user_id):
    """Test turn recorder with timestamps."""
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

    recorder = TurnRecorder(aide_id, test_user_id)
    recorder.start_turn(turn_num=1, tier="L3", model="sonnet", message="hello")
    recorder.record_tool_call("mutate_entity", {"action": "create"}, timestamp_ms=100)
    recorder.record_text_block("Done", timestamp_ms=200)
    recorder.set_usage(input_tokens=1000, output_tokens=500, cache_read=300)

    row_id = await recorder.finish()

    # Verify stored data
    turns = await telemetry_repo.get_turns_for_aide(test_user_id, aide_id)
    assert len(turns) == 1
    assert turns[0].tool_calls[0]["timestamp_ms"] == 100
    assert turns[0].usage.cache_read == 300

    # Cleanup
    async with db.system_conn() as conn:
        await conn.execute("DELETE FROM aide_turn_telemetry WHERE id = $1", row_id)
        await conn.execute("DELETE FROM aides WHERE id = $1", aide_id)


async def test_turn_recorder_returns_none_without_usage(initialize_pool, test_user_id):
    """Test turn recorder returns None without usage."""
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

    recorder = TurnRecorder(aide_id, test_user_id)
    recorder.start_turn(turn_num=1, tier="L3", model="sonnet", message="hello")
    # Don't call set_usage()

    row_id = await recorder.finish()
    assert row_id is None

    # Cleanup
    async with db.system_conn() as conn:
        await conn.execute("DELETE FROM aides WHERE id = $1", aide_id)
