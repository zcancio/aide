"""AI provider abstraction for Anthropic and OpenAI models."""

from typing import Any

import anthropic
import openai

from backend.config import settings


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
    ) -> dict[str, Any]:
        """
        Call Claude API.

        Args:
            model: Model name (e.g., "claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022")
            system: System prompt
            messages: List of message dicts with "role" and "content"
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Dict with "content" (text) and "usage" (token counts)
        """
        response = await self.anthropic_client.messages.create(
            model=model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # Extract text content from response
        content_text = ""
        for block in response.content:
            if block.type == "text":
                content_text += block.text

        return {
            "content": content_text,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }

    async def call_gpt(
        self,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 1.0,
    ) -> dict[str, Any]:
        """
        Call OpenAI GPT API.

        Args:
            model: Model name (e.g., "gpt-4o", "gpt-4o-mini")
            system: System prompt
            messages: List of message dicts with "role" and "content"
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Dict with "content" (text) and "usage" (token counts)
        """
        # Prepend system message
        full_messages = [{"role": "system", "content": system}] + messages

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
