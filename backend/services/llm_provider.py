"""
LLM provider factory.

Returns MockLLM when USE_MOCK_LLM=true (tests / UX simulation)
or a real LLM implementation when ANTHROPIC_API_KEY is available (Phase 4).
"""

from __future__ import annotations

from backend.config import settings
from backend.services.anthropic_client import AnthropicClient
from engine.kernel.mock_llm import MockLLM


def get_llm() -> MockLLM | AnthropicClient:
    """
    Return the configured LLM implementation.

    - USE_MOCK_LLM=true              → MockLLM (deterministic, no API calls)
    - ANTHROPIC_API_KEY available    → AnthropicClient (real streaming)
    - default                        → MockLLM (fallback)
    """
    if settings.USE_MOCK_LLM:
        return MockLLM()

    if settings.ANTHROPIC_API_KEY:
        return AnthropicClient(api_key=settings.ANTHROPIC_API_KEY)

    # Fallback to mock if no API key configured
    return MockLLM()
