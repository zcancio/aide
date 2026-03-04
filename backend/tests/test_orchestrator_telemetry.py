"""Tests for TurnRecorder integration in StreamingOrchestrator."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from backend.models.aide import CreateAideRequest
from backend.repos import telemetry_repo
from backend.repos.aide_repo import AideRepo
from backend.services.streaming_orchestrator import StreamingOrchestrator
from engine.kernel import empty_snapshot

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_orchestrator_records_turn_telemetry(test_user_id, initialize_pool):
    """Verify TurnRecorder captures turn telemetry during streaming."""
    aide_repo = AideRepo()
    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))

    orch = StreamingOrchestrator(
        aide_id=str(aide.id),
        snapshot=empty_snapshot(),
        conversation=[],
        api_key="fake",
        user_id=test_user_id,
        turn_num=1,
    )

    with patch.object(orch, "client") as mock_client:
        # Mock stream to yield tool use
        async def mock_stream(*args, **kwargs):
            await asyncio.sleep(0.001)  # Small delay to ensure ttfc_ms > 0
            yield {"type": "tool_use", "id": "t1", "name": "mutate_entity", "input": {"action": "create", "id": "x"}}

        mock_client.stream = mock_stream
        mock_client.get_usage_stats = AsyncMock(
            return_value={
                "input_tokens": 500,
                "output_tokens": 120,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            }
        )

        with patch("backend.services.streaming_orchestrator.classify") as mock_classify:
            mock_classify.return_value = MagicMock(tier="L3", reason="test")

            # Process message through orchestrator
            async for _ in orch.process_message("Create a todo list"):
                pass

            # Allow async task to complete
            await asyncio.sleep(0.2)

    # Verify telemetry was recorded
    turns = await telemetry_repo.get_turns_for_aide(test_user_id, aide.id)
    assert len(turns) == 1
    assert turns[0].message == "Create a todo list"
    assert turns[0].tier == "L3"
    assert turns[0].ttfc_ms > 0
    assert turns[0].ttc_ms > 0
    assert turns[0].usage.input_tokens == 500
    assert turns[0].usage.output_tokens == 120


async def test_orchestrator_captures_tool_calls(test_user_id, initialize_pool):
    """Verify tool calls are captured in turn telemetry."""
    aide_repo = AideRepo()
    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))

    orch = StreamingOrchestrator(
        aide_id=str(aide.id),
        snapshot=empty_snapshot(),
        conversation=[],
        api_key="fake",
        user_id=test_user_id,
        turn_num=2,
    )

    with patch.object(orch, "client") as mock_client:
        # Mock stream with multiple tool calls
        async def mock_stream(*args, **kwargs):
            yield {
                "type": "tool_use",
                "id": "t1",
                "name": "mutate_entity",
                "input": {"action": "create", "id": "task1", "display": "block"},
            }
            yield {
                "type": "tool_use",
                "id": "t2",
                "name": "mutate_entity",
                "input": {"action": "update", "ref": "task1", "p": {"title": "Buy milk"}},
            }

        mock_client.stream = mock_stream
        mock_client.get_usage_stats = AsyncMock(
            return_value={
                "input_tokens": 1000,
                "output_tokens": 250,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 100,
            }
        )

        with patch("backend.services.streaming_orchestrator.classify") as mock_classify:
            mock_classify.return_value = MagicMock(tier="L3", reason="test")

            async for _ in orch.process_message("Add a task"):
                pass

            await asyncio.sleep(0.2)

    turns = await telemetry_repo.get_turns_for_aide(test_user_id, aide.id)
    assert len(turns) == 1
    assert len(turns[0].tool_calls) == 2
    assert turns[0].tool_calls[0]["name"] == "mutate_entity"
    assert turns[0].tool_calls[0]["input"]["action"] == "create"
    assert turns[0].tool_calls[1]["name"] == "mutate_entity"
    assert turns[0].tool_calls[1]["input"]["action"] == "update"
    assert turns[0].usage.cache_read == 100


async def test_orchestrator_captures_text_blocks(test_user_id, initialize_pool):
    """Verify text blocks are captured in turn telemetry."""
    aide_repo = AideRepo()
    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))

    orch = StreamingOrchestrator(
        aide_id=str(aide.id),
        snapshot=empty_snapshot(),
        conversation=[],
        api_key="fake",
        user_id=test_user_id,
        turn_num=1,
    )

    with patch.object(orch, "client") as mock_client:
        # Mock stream with text
        async def mock_stream(*args, **kwargs):
            yield {"type": "text", "text": "Creating your task list"}
            yield {
                "type": "tool_use",
                "id": "t1",
                "name": "mutate_entity",
                "input": {"action": "create", "id": "x"},
            }

        mock_client.stream = mock_stream
        mock_client.get_usage_stats = AsyncMock(
            return_value={
                "input_tokens": 200,
                "output_tokens": 50,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            }
        )

        with patch("backend.services.streaming_orchestrator.classify") as mock_classify:
            mock_classify.return_value = MagicMock(tier="L3", reason="test")

            async for _ in orch.process_message("test"):
                pass

            await asyncio.sleep(0.2)

    turns = await telemetry_repo.get_turns_for_aide(test_user_id, aide.id)
    assert len(turns) == 1
    # Text blocks should be captured
    assert len(turns[0].text_blocks) > 0
    # At least one text block should contain our text
    text_found = any(
        "Creating your task list" in (block if isinstance(block, str) else block.get("text", ""))
        for block in turns[0].text_blocks
    )
    assert text_found


async def test_orchestrator_without_user_id_skips_telemetry(initialize_pool):
    """Verify telemetry is skipped when user_id is None."""
    aide_id = uuid4()

    orch = StreamingOrchestrator(
        aide_id=str(aide_id),
        snapshot=empty_snapshot(),
        conversation=[],
        api_key="fake",
        user_id=None,  # No user_id
        turn_num=1,
    )

    with patch.object(orch, "client") as mock_client:

        async def mock_stream(*args, **kwargs):
            yield {"type": "tool_use", "id": "t1", "name": "voice", "input": {"text": "hi"}}

        mock_client.stream = mock_stream
        mock_client.get_usage_stats = AsyncMock(
            return_value={
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            }
        )

        with patch("backend.services.streaming_orchestrator.classify") as mock_classify:
            mock_classify.return_value = MagicMock(tier="L3", reason="test")

            # Should not raise any errors
            async for _ in orch.process_message("test"):
                pass

            await asyncio.sleep(0.2)

    # No telemetry should be recorded (can't query without user_id)
    # This test just verifies no errors are raised
