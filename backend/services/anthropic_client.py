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

    async def stream(
        self,
        messages: list[dict[str, Any]],
        system: str | list[dict[str, Any]],
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
        cache_ttl: int | None = None,
    ) -> AsyncIterator[str]:
        """
        Stream response from Anthropic API.

        Args:
            messages: Messages array for the conversation
            system: System prompt (string or content blocks with cache_control)
            model: Model identifier
            max_tokens: Maximum tokens to generate
            cache_ttl: Optional cache TTL (deprecated - use content blocks directly)

        Yields:
            Text chunks as they arrive from the API
        """
        # Support both old string format and new content blocks
        system_content: str | list[dict[str, Any]] = system
        if isinstance(system, str) and cache_ttl:
            # Legacy path: convert string to content blocks
            system_content = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]

        async with self.client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system_content,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def get_usage_stats(self) -> dict[str, int] | None:
        """
        Get usage statistics from the most recent API call.

        Returns:
            Dictionary with token counts or None if not available
        """
        # This would be populated after a stream completes
        # For now, return None - usage tracking will be enhanced in future
        return None
