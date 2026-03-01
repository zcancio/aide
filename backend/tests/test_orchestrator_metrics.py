from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.streaming_orchestrator import StreamingOrchestrator


@pytest.fixture
def orch():
    return StreamingOrchestrator("test", {"entities": {}}, [], "fake")


@pytest.mark.asyncio
async def test_stream_end_includes_usage(orch):
    """stream.end event must include token counts."""
    with patch.object(orch, "client") as mock_client:
        # Mock the stream to yield no text and return usage stats
        async def mock_stream(*args, **kwargs):
            if False:
                yield

        mock_client.stream = mock_stream
        mock_client.get_usage_stats = AsyncMock(
            return_value={
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_input_tokens": 10,
                "cache_read_input_tokens": 20,
            }
        )

        with patch("backend.services.streaming_orchestrator.classify") as mock_classify:
            mock_classify.return_value = MagicMock(tier="L3", reason="test")
            events = [e async for e in orch.process_message("test")]

    end = [e for e in events if e.get("type") == "stream.end"]
    assert len(end) == 1
    usage = end[0]["usage"]
    assert "input_tokens" in usage
    assert "output_tokens" in usage
    assert "cache_read" in usage


@pytest.mark.asyncio
async def test_stream_end_includes_timings(orch):
    """stream.end event must include TTFC and TTC."""
    with patch.object(orch, "client") as mock_client:

        async def mock_stream(*args, **kwargs):
            if False:
                yield

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
            events = [e async for e in orch.process_message("test")]

    end = [e for e in events if e.get("type") == "stream.end"][0]
    assert "ttfc_ms" in end
    assert "ttc_ms" in end
    assert end["ttc_ms"] >= end["ttfc_ms"]


@pytest.mark.asyncio
async def test_stream_end_includes_cost(orch):
    """stream.end event must include computed cost in USD."""
    with patch.object(orch, "client") as mock_client:

        async def mock_stream(*args, **kwargs):
            if False:
                yield

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
            events = [e async for e in orch.process_message("test")]

    end = [e for e in events if e.get("type") == "stream.end"][0]
    assert "cost_usd" in end
    assert end["cost_usd"] >= 0
