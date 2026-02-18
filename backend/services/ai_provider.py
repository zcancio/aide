"""AI provider abstraction for Anthropic and OpenAI models."""

import asyncio
import time
from typing import Any

import anthropic
import openai

from backend.config import settings

# Transient error types that warrant a retry
_RETRYABLE_ANTHROPIC = (
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
)
_RETRYABLE_OPENAI = (
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.InternalServerError,
)


class AIProvider:
    """Unified interface for AI providers (Anthropic, OpenAI)."""

    def __init__(self) -> None:
        """Initialize AI clients with API keys from settings."""
        self.anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.openai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def call_claude(
        self,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 1.0,
        max_retries: int = 1,
    ) -> dict[str, Any]:
        """
        Call Claude API with streaming and timing telemetry.

        Args:
            model: Model name (e.g., "claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022")
            system: System prompt
            messages: List of message dicts with "role" and "content"
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            max_retries: Number of retries on transient failures (default 1)

        Returns:
            Dict with:
            - content: Generated text
            - usage: Token counts (input_tokens, output_tokens)
            - timing: Timing telemetry (request_ms, ttft_ms, total_ms)

        Raises:
            anthropic.APIError: If all retries exhausted
        """
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                request_sent_at = time.perf_counter()
                first_token_at: float | None = None
                content_text = ""
                input_tokens = 0
                output_tokens = 0

                # Use prompt caching for system prompt (5 min cache)
                system_with_cache = [
                    {
                        "type": "text",
                        "text": system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]

                cache_read_tokens = 0
                cache_creation_tokens = 0

                async with self.anthropic_client.messages.stream(
                    model=model,
                    system=system_with_cache,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                ) as stream:
                    async for event in stream:
                        if event.type == "content_block_delta":
                            if first_token_at is None:
                                first_token_at = time.perf_counter()
                            if hasattr(event.delta, "text"):
                                content_text += event.delta.text
                        elif event.type == "message_delta":
                            if hasattr(event.usage, "output_tokens"):
                                output_tokens = event.usage.output_tokens
                        elif event.type == "message_start":
                            if hasattr(event.message, "usage"):
                                usage = event.message.usage
                                input_tokens = usage.input_tokens
                                cache_read_tokens = getattr(usage, "cache_read_input_tokens", 0) or 0
                                cache_creation_tokens = getattr(usage, "cache_creation_input_tokens", 0) or 0

                last_token_at = time.perf_counter()

                # Calculate timing metrics
                total_ms = int((last_token_at - request_sent_at) * 1000)
                ttft_ms = int((first_token_at - request_sent_at) * 1000) if first_token_at else total_ms

                # Log cache stats
                if cache_read_tokens > 0:
                    print(f"Cache HIT: {cache_read_tokens} tokens read from cache, TTFT={ttft_ms}ms")
                elif cache_creation_tokens > 0:
                    print(f"Cache MISS: {cache_creation_tokens} tokens cached, TTFT={ttft_ms}ms")
                else:
                    print(f"No cache: TTFT={ttft_ms}ms")

                return {
                    "content": content_text,
                    "usage": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "cache_read_tokens": cache_read_tokens,
                        "cache_creation_tokens": cache_creation_tokens,
                    },
                    "timing": {
                        "ttft_ms": ttft_ms,
                        "total_ms": total_ms,
                    },
                }
            except _RETRYABLE_ANTHROPIC as e:
                last_error = e
                if attempt < max_retries:
                    wait_time = 2**attempt  # Exponential backoff: 1s, 2s, 4s...
                    print(f"Claude API error (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"Claude API error, retries exhausted: {e}")

        # All retries failed
        raise last_error  # type: ignore[misc]

    async def call_gpt(
        self,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 1.0,
        max_retries: int = 1,
    ) -> dict[str, Any]:
        """
        Call OpenAI GPT API with retry on transient failures.

        Args:
            model: Model name (e.g., "gpt-4o", "gpt-4o-mini")
            system: System prompt
            messages: List of message dicts with "role" and "content"
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            max_retries: Number of retries on transient failures (default 1)

        Returns:
            Dict with "content" (text) and "usage" (token counts)

        Raises:
            openai.APIError: If all retries exhausted
        """
        # Prepend system message
        full_messages = [{"role": "system", "content": system}] + messages
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                response = await self.openai_client.chat.completions.create(
                    model=model,
                    messages=full_messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

                return {
                    "content": response.choices[0].message.content or "",
                    "usage": {
                        "input_tokens": response.usage.prompt_tokens,
                        "output_tokens": response.usage.completion_tokens,
                    },
                }
            except _RETRYABLE_OPENAI as e:
                last_error = e
                if attempt < max_retries:
                    wait_time = 2**attempt
                    print(f"OpenAI API error (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"OpenAI API error, retries exhausted: {e}")

        raise last_error  # type: ignore[misc]

    async def transcribe_audio(self, audio_data: bytes, filename: str = "audio.webm") -> str:
        """
        Transcribe audio using OpenAI Whisper.

        Args:
            audio_data: Raw audio bytes
            filename: Filename hint for audio format

        Returns:
            Transcribed text
        """
        # Create a file-like object from bytes
        from io import BytesIO

        audio_file = BytesIO(audio_data)
        audio_file.name = filename

        response = await self.openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )

        return response.text


# Singleton instance
ai_provider = AIProvider()
