"""
Streaming orchestrator for real-time LLM pipeline.

Coordinates classification, prompt building, LLM streaming, and reduction
for WebSocket-based interactions.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from backend.services.anthropic_client import AnthropicClient
from backend.services.classifier import TIER_MODELS, classify
from backend.services.prompt_builder import build_messages, build_system_blocks
from backend.services.tool_defs import L4_TOOLS, TOOLS
from engine.kernel.reducer_v2 import reduce

logger = logging.getLogger(__name__)

# Pricing per million tokens (MTok) — input/output/cache_read/cache_write
PRICING = {
    "L2": (0.25, 1.25, 0.025, 0.3125),  # Haiku
    "L3": (3.0, 15.0, 0.30, 3.75),  # Sonnet
    "L4": (15.0, 75.0, 1.50, 18.75),  # Opus
}


def calculate_cost(tier: str, usage: dict[str, int]) -> float:
    """Calculate cost in USD for an LLM call."""
    price_in, price_out, price_cr, price_cw = PRICING[tier]
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cache_read = usage.get("cache_read_input_tokens", 0)
    cache_write = usage.get("cache_creation_input_tokens", 0)

    cost = (
        (input_tokens * price_in / 1e6)
        + (output_tokens * price_out / 1e6)
        + (cache_read * price_cr / 1e6)
        + (cache_write * price_cw / 1e6)
    )
    return cost


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
        has_schema = bool(self.snapshot.get("entities"))
        classification = classify(content, self.snapshot, has_schema)

        self.tier = classification.tier
        self.model = TIER_MODELS[self.tier]

        logger.info(
            "streaming_orchestrator: classified message aide_id=%s tier=%s reason=%s",
            self.aide_id,
            self.tier,
            classification.reason,
        )

        # Build system prompt blocks
        system_blocks = build_system_blocks(self.tier, self.snapshot)

        # Build messages array
        messages = build_messages(self.conversation, content)

        # Select tools based on tier
        tools = L4_TOOLS if self.tier == "L4" else TOOLS

        # Yield classification metadata
        yield {
            "type": "meta.classification",
            "tier": self.tier,
            "model": self.model,
            "reason": classification.reason,
        }

        # Timing trackers
        t_start = time.time()
        t_first_content: float | None = None

        # Stream from LLM and parse JSONL
        line_buffer = ""
        async for chunk in self.client.stream(
            messages=messages,
            system=system_blocks,
            model=self.model,
            tools=tools,
        ):
            # Record time to first content
            if t_first_content is None:
                t_first_content = time.time()

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

        # Stream complete — gather metrics
        t_complete = time.time()
        ttfc_ms = int((t_first_content - t_start) * 1000) if t_first_content else 0
        ttc_ms = int((t_complete - t_start) * 1000)

        # Get usage stats from client
        usage = await self.client.get_usage_stats()
        if usage is None:
            usage = {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            }

        # Compute cost
        cost_usd = calculate_cost(self.tier, usage)

        # Yield stream.end with metrics
        yield {
            "type": "stream.end",
            "usage": {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "cache_read": usage.get("cache_read_input_tokens", 0),
                "cache_write": usage.get("cache_creation_input_tokens", 0),
            },
            "ttfc_ms": ttfc_ms,
            "ttc_ms": ttc_ms,
            "cost_usd": cost_usd,
        }
