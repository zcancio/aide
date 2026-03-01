"""
Anthropic streaming client.

Connects to Anthropic Messages API, streams response chunks.
Supports both text-only streaming and tool_use streaming.
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
        temperature: float | None = None,
    ) -> AsyncIterator[str | dict[str, Any]]:
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
            Without tools: Text chunks (str) as they arrive
            With tools: Event dicts with structure:
                - {"type": "text", "text": "..."} for text content
                - {"type": "tool_use", "id": "...", "name": "...", "input": {...}}
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

        # Add temperature if provided
        if temperature is not None:
            kwargs["temperature"] = temperature

        async with self.client.messages.stream(**kwargs) as stream:
            if tools is not None:
                # With tools: iterate over events to capture both text and tool_use
                async for event in stream:
                    print(f"[CLIENT] event.type={event.type}", flush=True)
                    if event.type == "text":
                        # Text delta event
                        yield {"type": "text", "text": event.text}
                    elif event.type == "content_block_stop":
                        # Content block finished - check if it's a tool_use
                        block = event.content_block
                        print(f"[CLIENT] content_block_stop block.type={getattr(block, 'type', 'unknown')}", flush=True)
                        if hasattr(block, "type") and block.type == "tool_use":
                            yield {
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": block.input,
                            }
            else:
                # Without tools: use text_stream for backward compatibility
                async for text in stream.text_stream:
                    yield text

            # After stream completes, extract usage stats
            final_message = await stream.get_final_message()
            if final_message:
                print(f"[CLIENT] final_message content blocks: {len(final_message.content)}", flush=True)
                for i, block in enumerate(final_message.content):
                    print(f"[CLIENT] block[{i}] type={getattr(block, 'type', 'unknown')}", flush=True)
                    if hasattr(block, "type") and block.type == "tool_use":
                        print(f"[CLIENT] block[{i}] name={block.name}", flush=True)
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
