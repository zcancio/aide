"""
Anthropic streaming client.

Connects to Anthropic Messages API, streams response chunks.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import anthropic


class AnthropicClient:
    """Streams responses from Anthropic Messages API."""

    def __init__(self, api_key: str):
        """
        Initialize Anthropic client.

        Args:
            api_key: Anthropic API key
        """
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self._last_usage: dict[str, int] | None = None

    async def stream(
        self,
        messages: list[dict[str, Any]],
        system: str | list[dict[str, Any]],
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
        cache_ttl: int | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        """
        Stream response from Anthropic API.

        Args:
            messages: Messages array for the conversation
            system: System prompt (string or list of content blocks)
            model: Model identifier
            max_tokens: Maximum tokens to generate
            cache_ttl: Optional cache TTL in seconds (deprecated, kept for backward compat)
            tools: Optional tool definitions to pass to the API

        Yields:
            Text chunks as they arrive from the API
        """
        # Handle system prompt format
        system_content: str | list[dict[str, Any]]
        if isinstance(system, list):
            # Already in list format, pass through as-is
            system_content = system
        else:
            # String format: wrap in cache_control block if cache_ttl specified
            if cache_ttl:
                system_content = [
                    {
                        "type": "text",
                        "text": system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            else:
                system_content = system

        # Build API call kwargs
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_content,
            "messages": messages,
        }

        # Add tools if provided
        if tools is not None:
            kwargs["tools"] = tools

        async with self.client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

            # After stream completes, extract usage stats
            final_message = await stream.get_final_message()
            if final_message and hasattr(final_message, "usage"):
                self._last_usage = {
                    "input_tokens": final_message.usage.input_tokens,
                    "output_tokens": final_message.usage.output_tokens,
                    "cache_creation_input_tokens": getattr(final_message.usage, "cache_creation_input_tokens", 0),
                    "cache_read_input_tokens": getattr(final_message.usage, "cache_read_input_tokens", 0),
                }

    async def get_usage_stats(self) -> dict[str, int] | None:
        """
        Get usage statistics from the most recent API call.

        Returns:
            Dictionary with token counts or None if not available
        """
        return self._last_usage
