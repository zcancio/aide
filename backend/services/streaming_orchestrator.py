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
from backend.services.tool_defs import TOOLS
from engine.kernel.reducer_v2 import reduce

logger = logging.getLogger(__name__)

# Pricing per million tokens (MTok) — input/output/cache_read/cache_write
PRICING = {
    "L3": (3.0, 15.0, 0.30, 3.75),  # Sonnet
    "L4": (3.0, 15.0, 0.30, 3.75),  # Sonnet (same model as L3)
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


def tool_use_to_reducer_event(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any] | None:
    """
    Convert a tool_use call to a reducer event.

    Maps:
      mutate_entity(action="create", ...) → {"t": "entity.create", ...}
      mutate_entity(action="update", ...) → {"t": "entity.update", ...}
      set_relationship(action="set", ...) → {"t": "rel.set", ...}
      voice(text="...") → {"t": "voice", "text": "..."}
    """
    if tool_name == "mutate_entity":
        action = tool_input.get("action", "")
        event: dict[str, Any] = {"t": f"entity.{action}"}

        # Map tool fields to reducer event fields
        if "id" in tool_input:
            event["id"] = tool_input["id"]
        if "ref" in tool_input:
            event["ref"] = tool_input["ref"]
        if "parent" in tool_input:
            event["parent"] = tool_input["parent"]
        if "display" in tool_input:
            event["display"] = tool_input["display"]

        # Handle props - also handle title directly for prompt compatibility
        props = tool_input.get("props", {})
        # Parse props if it's a JSON string
        if isinstance(props, str):
            try:
                props = json.loads(props)
            except json.JSONDecodeError:
                props = {}
        if "title" in tool_input:
            props["title"] = tool_input["title"]
        if props:
            event["p"] = props

        return event

    elif tool_name == "set_relationship":
        action = tool_input.get("action", "set")
        event = {"t": f"rel.{action}"}

        for key in ("from", "to", "type", "cardinality"):
            if key in tool_input:
                event[key] = tool_input[key]

        return event

    elif tool_name == "voice":
        return {"t": "voice", "text": tool_input.get("text", "")}

    else:
        logger.warning("streaming_orchestrator: unknown tool %s", tool_name)
        return None


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

        # Both tiers get full tool set (query-only enforced by prompt)
        tools = TOOLS

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

        # Track if voice was sent and mutation count for fallback
        voice_sent = False
        mutation_count = 0

        print(f"[ORCH] starting stream tier={self.tier} model={self.model}", flush=True)

        # Stream from LLM with tool support
        async for stream_event in self.client.stream(
            messages=messages,
            system=system_blocks,
            model=self.model,
            tools=tools,
        ):
            print(f"[ORCH] got event: {type(stream_event)} = {stream_event}", flush=True)
            # Record time to first content
            if t_first_content is None:
                t_first_content = time.time()

            # Handle tool_use events
            if isinstance(stream_event, dict) and stream_event.get("type") == "tool_use":
                tool_name = stream_event.get("name", "")
                tool_input = stream_event.get("input", {})
                print(f"[ORCH] processing tool_use: {tool_name}", flush=True)

                # Convert tool call to reducer event
                event = tool_use_to_reducer_event(tool_name, tool_input)
                if event is None:
                    print(f"[ORCH] tool_use_to_reducer_event returned None", flush=True)
                    continue

                event_type = event.get("t", "")
                print(f"[ORCH] converted to reducer event: {event_type}", flush=True)

                # Pass through voice events
                if event_type == "voice":
                    print(f"[ORCH] yielding voice: {event.get('text', '')[:50]}", flush=True)
                    voice_sent = True
                    yield {"type": "voice", "text": event.get("text", "")}
                    continue

                # Apply event to snapshot through reducer
                result = reduce(self.snapshot, event)
                print(f"[ORCH] reducer result: accepted={result.accepted} reason={result.reason}", flush=True)

                if result.accepted:
                    self.snapshot = result.snapshot
                    mutation_count += 1
                    yield {"type": "event", "event": event, "snapshot": self.snapshot}
                else:
                    logger.debug(
                        "streaming_orchestrator: reducer rejected event type=%s reason=%s",
                        event_type,
                        result.reason,
                    )
                    yield {
                        "type": "rejection",
                        "event": event,
                        "reason": result.reason,
                    }

            # Handle text events - text between tool calls is voice output
            elif isinstance(stream_event, dict) and stream_event.get("type") == "text":
                text = stream_event.get("text", "")
                print(f"[ORCH] got text event: {text[:50] if text else '(empty)'}", flush=True)
                if text.strip():
                    # Text output is the voice response shown in chat
                    voice_sent = True
                    yield {"type": "voice", "text": text}

        print(f"[ORCH] stream finished", flush=True)

        # Fallback: if no voice was sent, generate a default message
        if not voice_sent and mutation_count > 0:
            fallback_text = f"{mutation_count} update{'s' if mutation_count != 1 else ''} applied."
            print(f"[ORCH] no voice sent, using fallback: {fallback_text}", flush=True)
            yield {"type": "voice", "text": fallback_text}

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
