"""
Tests for AnthropicClient tool_use handling.

RED/GREEN TDD: These tests define the expected behavior for streaming
with tools enabled.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.anthropic_client import AnthropicClient


class MockContentBlock:
    """Mock content block from Anthropic API."""

    def __init__(self, block_type: str, **kwargs: Any):
        self.type = block_type
        for key, value in kwargs.items():
            setattr(self, key, value)


class MockEvent:
    """Mock streaming event."""

    def __init__(self, event_type: str, **kwargs: Any):
        self.type = event_type
        for key, value in kwargs.items():
            setattr(self, key, value)


class AsyncIteratorMock:
    """Async iterator that yields from a list."""

    def __init__(self, items: list[Any]):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item


class MockUsage:
    """Mock usage stats."""

    def __init__(self):
        self.input_tokens = 100
        self.output_tokens = 50
        self.cache_creation_input_tokens = 10
        self.cache_read_input_tokens = 20


class MockMessage:
    """Mock final message."""

    def __init__(self, content: list[MockContentBlock]):
        self.content = content
        self.usage = MockUsage()


@pytest.fixture
def client() -> AnthropicClient:
    """Create client with mock API key."""
    return AnthropicClient("test-api-key")


@pytest.fixture
def mock_tools() -> list[dict[str, Any]]:
    """Sample tool definitions."""
    return [
        {
            "name": "mutate_entity",
            "description": "Mutate an entity",
            "input_schema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "id": {"type": "string"},
                },
            },
        },
        {
            "name": "voice",
            "description": "Send voice message",
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                },
            },
        },
    ]


@pytest.mark.asyncio
async def test_stream_with_tools_yields_tool_use_events(
    client: AnthropicClient, mock_tools: list[dict[str, Any]]
) -> None:
    """When tools are passed, stream should yield tool_use events."""
    # Setup mock stream that yields a tool_use content block
    tool_block = MockContentBlock(
        "tool_use",
        id="tool_123",
        name="mutate_entity",
        input={"action": "create", "id": "player_mike"},
    )

    events = [
        MockEvent("content_block_stop", content_block=tool_block),
    ]

    mock_stream = AsyncIteratorMock(events)
    mock_stream.get_final_message = AsyncMock(return_value=MockMessage([tool_block]))

    with patch.object(client.client.messages, "stream") as mock_stream_method:
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_stream_method.return_value = mock_context

        results = []
        async for event in client.stream(
            messages=[{"role": "user", "content": "test"}],
            system="test system",
            tools=mock_tools,
        ):
            results.append(event)

        # Should yield a tool_use event
        assert len(results) == 1
        assert results[0]["type"] == "tool_use"
        assert results[0]["name"] == "mutate_entity"
        assert results[0]["input"] == {"action": "create", "id": "player_mike"}


@pytest.mark.asyncio
async def test_stream_with_tools_yields_text_events(client: AnthropicClient, mock_tools: list[dict[str, Any]]) -> None:
    """When tools are passed, text content should yield text events."""
    text_block = MockContentBlock("text", text="Hello world")

    events = [
        MockEvent("text", text="Hello ", snapshot="Hello "),
        MockEvent("text", text="world", snapshot="Hello world"),
        MockEvent("content_block_stop", content_block=text_block),
    ]

    mock_stream = AsyncIteratorMock(events)
    mock_stream.get_final_message = AsyncMock(return_value=MockMessage([text_block]))

    with patch.object(client.client.messages, "stream") as mock_stream_method:
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_stream_method.return_value = mock_context

        results = []
        async for event in client.stream(
            messages=[{"role": "user", "content": "test"}],
            system="test system",
            tools=mock_tools,
        ):
            results.append(event)

        # Should yield text events for each text delta
        text_events = [r for r in results if r["type"] == "text"]
        assert len(text_events) == 2
        assert text_events[0]["text"] == "Hello "
        assert text_events[1]["text"] == "world"


@pytest.mark.asyncio
async def test_stream_with_tools_interleaved_text_and_tool_use(
    client: AnthropicClient, mock_tools: list[dict[str, Any]]
) -> None:
    """Stream should handle interleaved text and tool_use blocks."""
    tool_block = MockContentBlock(
        "tool_use",
        id="tool_456",
        name="voice",
        input={"text": "Done."},
    )
    text_block = MockContentBlock("text", text="Processing")

    events = [
        # First some text
        MockEvent("text", text="Processing", snapshot="Processing"),
        MockEvent("content_block_stop", content_block=text_block),
        # Then a tool call
        MockEvent("content_block_stop", content_block=tool_block),
    ]

    mock_stream = AsyncIteratorMock(events)
    mock_stream.get_final_message = AsyncMock(return_value=MockMessage([text_block, tool_block]))

    with patch.object(client.client.messages, "stream") as mock_stream_method:
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_stream_method.return_value = mock_context

        results = []
        async for event in client.stream(
            messages=[{"role": "user", "content": "test"}],
            system="test system",
            tools=mock_tools,
        ):
            results.append(event)

        # Should have text event followed by tool_use event
        assert len(results) == 2
        assert results[0]["type"] == "text"
        assert results[0]["text"] == "Processing"
        assert results[1]["type"] == "tool_use"
        assert results[1]["name"] == "voice"


@pytest.mark.asyncio
async def test_stream_without_tools_yields_strings(client: AnthropicClient) -> None:
    """Without tools, stream should yield plain strings (backward compat)."""

    async def mock_text_stream():
        for chunk in ["Hello ", "world"]:
            yield chunk

    mock_stream = AsyncMock()
    mock_stream.text_stream = mock_text_stream()
    mock_stream.get_final_message = AsyncMock(return_value=MockMessage([MockContentBlock("text", text="Hello world")]))

    with patch.object(client.client.messages, "stream") as mock_stream_method:
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_stream_method.return_value = mock_context

        results = []
        async for chunk in client.stream(
            messages=[{"role": "user", "content": "test"}],
            system="test system",
            # No tools parameter
        ):
            results.append(chunk)

        # Should yield plain strings
        assert results == ["Hello ", "world"]


@pytest.mark.asyncio
async def test_stream_with_tools_captures_usage_stats(
    client: AnthropicClient, mock_tools: list[dict[str, Any]]
) -> None:
    """Usage stats should be captured when streaming with tools."""
    tool_block = MockContentBlock(
        "tool_use",
        id="tool_789",
        name="mutate_entity",
        input={"action": "update"},
    )

    events = [
        MockEvent("content_block_stop", content_block=tool_block),
    ]

    mock_stream = AsyncIteratorMock(events)
    mock_stream.get_final_message = AsyncMock(return_value=MockMessage([tool_block]))

    with patch.object(client.client.messages, "stream") as mock_stream_method:
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_stream_method.return_value = mock_context

        async for _ in client.stream(
            messages=[{"role": "user", "content": "test"}],
            system="test system",
            tools=mock_tools,
        ):
            pass

        usage = await client.get_usage_stats()
        assert usage is not None
        assert usage["input_tokens"] == 100
        assert usage["output_tokens"] == 50
        assert usage["cache_creation_input_tokens"] == 10
        assert usage["cache_read_input_tokens"] == 20
