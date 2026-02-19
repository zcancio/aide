"""
LLM provider factory.

Returns MockLLM when USE_MOCK_LLM=true (tests / UX simulation)
or a real LLM implementation in production (Phase 4).
"""

from __future__ import annotations

from backend.config import settings
from engine.kernel.mock_llm import MockLLM


def get_llm() -> MockLLM:
    """
    Return the configured LLM implementation.

    - USE_MOCK_LLM=true  → MockLLM (deterministic, no API calls)
    - default            → MockLLM placeholder until Phase 4 real implementation

    Phase 4 will replace the else branch with AnthropicLLM().
    """
    if settings.USE_MOCK_LLM:
        return MockLLM()
    # Real LLM implementation lives in Phase 4.
    # For now, always return MockLLM so imports don't break.
    return MockLLM()
