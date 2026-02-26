"""
Streaming orchestrator for real-time LLM pipeline.

Coordinates classification, prompt building, LLM streaming, and reduction
for WebSocket-based interactions.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from backend.services.anthropic_client import AnthropicClient
from backend.services.classifier import TIER_MODELS
from backend.services.prompt_builder import build_messages, build_system_blocks
from backend.services.tier_classifier import classify_tier
from engine.kernel.reducer_v2 import reduce

logger = logging.getLogger(__name__)


class StreamingOrchestrator:
    """Orchestrates streaming message processing through LLM pipeline."""

    def __init__(
        self,
        aide_id: str,
        snapshot: dict[str, Any],
        conversation: list[dict[str, Any]],
        api_key: str,
    ):
        """
        Initialize streaming orchestrator.

        Args:
            aide_id: Aide identifier
            snapshot: Current snapshot state (v2 format)
            conversation: Conversation history
            api_key: Anthropic API key
        """
        self.aide_id = aide_id
        self.snapshot = snapshot
        self.conversation = conversation
        self.client = AnthropicClient(api_key)
        self.tier: str | None = None
        self.model: str | None = None

    async def process_message(
        self,
        content: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Process user message and yield streaming results.

        Args:
            content: User message text

        Yields:
            Dictionaries containing events, deltas, or metadata
        """
        # Classify message to determine tier
        self.tier = classify_tier(content, self.snapshot)
        self.model = TIER_MODELS[self.tier]

        logger.info(
            "streaming_orchestrator: classified message aide_id=%s tier=%s",
            self.aide_id,
            self.tier,
        )

        # Build system prompt with content blocks (includes cache control)
        system_blocks = build_system_blocks(self.tier, self.snapshot)

        # Build messages array
        messages = build_messages(self.conversation, content)

        # Yield classification metadata
        yield {
            "type": "meta.classification",
            "tier": self.tier,
            "model": self.model,
        }

        # Stream from LLM and parse JSONL
        line_buffer = ""
        async for chunk in self.client.stream(
            messages=messages,
            system=system_blocks,
            model=self.model,
        ):
            line_buffer += chunk

            # Process complete lines
            while "\n" in line_buffer:
                line, line_buffer = line_buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue

                # Try to parse as JSON event
                try:
                    event = json.loads(line)
                    event_type = event.get("t", "")

                    # Pass through voice events
                    if event_type == "voice":
                        yield {"type": "voice", "text": event.get("text", "")}
                        continue

                    # Pass through batch signals
                    if event_type in ("batch.start", "batch.end"):
                        yield {"type": event_type}
                        continue

                    # Apply event to snapshot through reducer
                    result = reduce(self.snapshot, event)

                    if result.accepted:
                        self.snapshot = result.snapshot

                        # Yield the event for downstream processing
                        yield {"type": "event", "event": event, "snapshot": self.snapshot}
                    else:
                        logger.debug(
                            "streaming_orchestrator: reducer rejected event type=%s reason=%s",
                            event_type,
                            result.reason,
                        )
                        # Yield rejection for telemetry
                        yield {
                            "type": "rejection",
                            "event": event,
                            "reason": result.reason,
                        }

                except json.JSONDecodeError:
                    # Not a valid JSON line - could be part of response text
                    logger.debug("streaming_orchestrator: skipping non-JSON line: %r", line[:100])
                    continue

        # Process any remaining buffer content
        if line_buffer.strip():
            try:
                event = json.loads(line_buffer)
                result = reduce(self.snapshot, event)
                if result.accepted:
                    self.snapshot = result.snapshot
                    yield {"type": "event", "event": event, "snapshot": self.snapshot}
            except json.JSONDecodeError:
                logger.debug("streaming_orchestrator: skipping incomplete line in buffer")
