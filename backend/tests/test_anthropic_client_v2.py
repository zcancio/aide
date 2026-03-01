from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.anthropic_client import AnthropicClient


@pytest.mark.asyncio
async def test_accepts_list_system_prompt():
    """Client should accept list[dict] for system and pass it through."""
    client = AnthropicClient("fake-key")
    blocks = [
        {"type": "text", "text": "static", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "dynamic"},
    ]
    with patch.object(client.client.messages, "stream") as mock:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.text_stream = AsyncMock(return_value=iter([]))
        mock_ctx.__aiter__ = AsyncMock(return_value=iter([]))
        mock.return_value = mock_ctx
        try:
            async for _ in client.stream([], blocks, "claude-sonnet-4-5-20250929"):
                pass
        except Exception:  # noqa: S110
            pass
        # Verify system was passed as-is (list), not re-wrapped
        call_kwargs = mock.call_args.kwargs
        assert isinstance(call_kwargs["system"], list)
        assert len(call_kwargs["system"]) == 2
        assert call_kwargs["system"][0]["cache_control"]["type"] == "ephemeral"


@pytest.mark.asyncio
async def test_string_system_still_works():
    """Backward compat: string system prompts should still work."""
    client = AnthropicClient("fake-key")
    with patch.object(client.client.messages, "stream") as mock:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.text_stream = AsyncMock(return_value=iter([]))
        mock_ctx.__aiter__ = AsyncMock(return_value=iter([]))
        # Mock get_final_message to return a message with usage
        final_msg = MagicMock()
        final_msg.usage.input_tokens = 100
        final_msg.usage.output_tokens = 50
        final_msg.usage.cache_creation_input_tokens = 0
        final_msg.usage.cache_read_input_tokens = 0
        mock_ctx.get_final_message = AsyncMock(return_value=final_msg)
        mock.return_value = mock_ctx
        try:
            async for _ in client.stream([], "plain string", "model"):
                pass
        except Exception:  # noqa: S110
            pass
        call_kwargs = mock.call_args.kwargs
        # String without cache_ttl should be passed through as-is
        assert call_kwargs["system"] == "plain string"


@pytest.mark.asyncio
async def test_tools_forwarded():
    """Tool definitions should be passed through to the API call."""
    client = AnthropicClient("fake-key")
    tools = [{"name": "voice", "input_schema": {"type": "object", "properties": {}}}]
    with patch.object(client.client.messages, "stream") as mock:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.text_stream = AsyncMock(return_value=iter([]))
        mock_ctx.__aiter__ = AsyncMock(return_value=iter([]))
        mock.return_value = mock_ctx
        try:
            async for _ in client.stream([], "sys", "model", tools=tools):
                pass
        except Exception:  # noqa: S110
            pass
        assert mock.call_args.kwargs.get("tools") == tools
