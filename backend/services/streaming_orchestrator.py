"""
Streaming orchestrator for real-time LLM pipeline.

Coordinates classification, prompt building, LLM streaming, and reduction
for WebSocket-based interactions.
"""

from __future__ import annotations

import copy
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from backend.services.anthropic_client import AnthropicClient
from backend.services.classifier import TIER_MODELS, classify
from backend.services.escalation import needs_escalation
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

    async def _run_tier(
        self,
        tier: str,
        snapshot: dict[str, Any],
        messages: list[dict[str, Any]],
        user_message: str,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """
        Run a single LLM call for a tier and collect results.

        Both L3 and L4 receive the full TOOLS set.

        Args:
            tier: Tier to run (L3 or L4)
            snapshot: Current snapshot state
            messages: Conversation messages
            user_message: Current user message
            temperature: Optional temperature override (default 0 for both tiers)

        Returns:
            {
                "text_blocks": [{"text": "..."}],
                "tool_calls": [{"name": "mutate_entity", "input": {...}}],
                "all_raw_tools": [...],  # includes voice for conversation history
                "usage": {"input_tokens": ..., "output_tokens": ..., "cache_read": ..., "cache_creation": ...},
                "ttfc_ms": ...,
                "ttc_ms": ...,
                "snapshot": {...},  # snapshot after applying this tier's mutations
            }
        """
        # Get model for tier
        model = TIER_MODELS[tier]

        # Build system prompt blocks
        system_blocks = build_system_blocks(tier, snapshot)

        # Both tiers get full tool set (query-only enforced by prompt)
        tools = TOOLS

        # Use temperature 0 by default for deterministic responses
        if temperature is None:
            temperature = 0

        # Timing trackers
        t_start = time.time()
        t_first_content: float | None = None

        # Result accumulators
        text_blocks: list[dict[str, Any] | str] = []
        tool_calls: list[dict[str, Any]] = []
        all_raw_tools: list[dict[str, Any]] = []

        # Working snapshot for this tier
        working_snapshot = copy.deepcopy(snapshot)

        # Stream from LLM
        async for stream_event in self.client.stream(
            messages=messages,
            system=system_blocks,
            model=model,
            tools=tools,
            temperature=temperature,
        ):
            # Record time to first content
            if t_first_content is None:
                t_first_content = time.time()

            # Handle tool_use events
            if isinstance(stream_event, dict) and stream_event.get("type") == "tool_use":
                tool_name = stream_event.get("name", "")
                tool_input = stream_event.get("input", {})

                # Store raw tool call
                all_raw_tools.append(
                    {
                        "id": stream_event.get("id", ""),
                        "name": tool_name,
                        "input": tool_input,
                    }
                )

                # Convert tool call to reducer event
                event = tool_use_to_reducer_event(tool_name, tool_input)
                if event is None:
                    continue

                event_type = event.get("t", "")

                # Handle voice events (don't reduce, just collect)
                if event_type == "voice":
                    text_blocks.append({"text": event.get("text", "")})
                    continue

                # Apply event to working snapshot through reducer
                result = reduce(working_snapshot, event)

                if result.accepted:
                    working_snapshot = result.snapshot
                    tool_calls.append({"name": tool_name, "input": tool_input})

            # Handle text events - text between tool calls is voice output
            elif isinstance(stream_event, dict) and stream_event.get("type") == "text":
                text = stream_event.get("text", "")
                if text.strip():
                    text_blocks.append({"text": text})

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

        return {
            "text_blocks": text_blocks,
            "tool_calls": tool_calls,
            "all_raw_tools": all_raw_tools,
            "usage": {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "cache_read": usage.get("cache_read_input_tokens", 0),
                "cache_creation": usage.get("cache_creation_input_tokens", 0),
            },
            "ttfc_ms": ttfc_ms,
            "ttc_ms": ttc_ms,
            "snapshot": working_snapshot,
        }

    async def process_message(
        self,
        content: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Process user message and yield streaming results.

        Implements L3 → L4 → L3 two-pass escalation when L3 signals it needs help.

        Args:
            content: User message text

        Yields:
            Dictionaries containing events, deltas, or metadata
        """
        # Classify message to determine tier
        has_schema = bool(self.snapshot.get("entities"))
        classification = classify(content, self.snapshot, has_schema)

        tier = classification.tier
        self.tier = tier
        self.model = TIER_MODELS[tier]

        logger.info(
            "streaming_orchestrator: classified message aide_id=%s tier=%s reason=%s",
            self.aide_id,
            tier,
            classification.reason,
        )

        # Build messages array
        messages = build_messages(self.conversation, content)

        # Yield classification metadata
        yield {
            "type": "meta.classification",
            "tier": tier,
            "model": self.model,
            "reason": classification.reason,
        }

        # Save original snapshot for potential escalation
        original_snapshot = copy.deepcopy(self.snapshot)

        # Run initial tier
        result = await self._run_tier(tier, self.snapshot, messages, content)

        # Check for escalation (only for L3)
        if tier == "L3" and needs_escalation(result):
            # Yield escalation metadata
            yield {
                "type": "meta.escalation",
                "from_tier": "L3",
                "to_tier": "L4",
                "reason": "L3 signaled structural work or complex query",
            }

            # Pass 1: L4 creates structure with original snapshot, temperature 0
            l4_result = await self._run_tier("L4", original_snapshot, messages, content, temperature=0)
            l4_snapshot = l4_result["snapshot"]

            # Pass 2: L3 retries with L4's snapshot
            l3_result = await self._run_tier("L3", l4_snapshot, messages, content, temperature=0)

            # Merge results: L4 tool_calls first, then L3
            result = {
                "text_blocks": l4_result["text_blocks"] + l3_result["text_blocks"],
                "tool_calls": l4_result["tool_calls"] + l3_result["tool_calls"],
                "all_raw_tools": l4_result["all_raw_tools"] + l3_result["all_raw_tools"],
                "usage": {
                    "input_tokens": (
                        result["usage"]["input_tokens"]
                        + l4_result["usage"]["input_tokens"]
                        + l3_result["usage"]["input_tokens"]
                    ),
                    "output_tokens": (
                        result["usage"]["output_tokens"]
                        + l4_result["usage"]["output_tokens"]
                        + l3_result["usage"]["output_tokens"]
                    ),
                    "cache_read": (
                        result["usage"]["cache_read"]
                        + l4_result["usage"]["cache_read"]
                        + l3_result["usage"]["cache_read"]
                    ),
                    "cache_creation": (
                        result["usage"]["cache_creation"]
                        + l4_result["usage"]["cache_creation"]
                        + l3_result["usage"]["cache_creation"]
                    ),
                },
                "ttfc_ms": l4_result["ttfc_ms"],  # TTFC from first visible pass (L4)
                "ttc_ms": result["ttc_ms"] + l4_result["ttc_ms"] + l3_result["ttc_ms"],  # Sum all passes
                "snapshot": l3_result["snapshot"],  # Final snapshot from L3 pass 2
            }

            # Update tier label for stream.end
            tier = "L3->L4->L3"

            # Update instance snapshot
            self.snapshot = result["snapshot"]
        else:
            # No escalation - update snapshot from result
            self.snapshot = result["snapshot"]

        # Yield tool_calls as events
        for tc in result["tool_calls"]:
            # Convert tool call to reducer event for yielding
            event = tool_use_to_reducer_event(tc["name"], tc["input"])
            if event and event.get("t") != "voice":
                yield {"type": "event", "event": event, "snapshot": self.snapshot}

        # Yield text_blocks as voice
        for tb in result["text_blocks"]:
            text = tb["text"] if isinstance(tb, dict) else tb
            if text.strip():
                yield {"type": "voice", "text": text}

        # Fallback: if no voice was sent, generate a default message
        mutation_count = len(result["tool_calls"])
        has_voice = any((tb["text"] if isinstance(tb, dict) else tb).strip() for tb in result["text_blocks"])
        if not has_voice and mutation_count > 0:
            fallback_text = f"{mutation_count} update{'s' if mutation_count != 1 else ''} applied."
            yield {"type": "voice", "text": fallback_text}

        # Compute cost
        cost_usd = calculate_cost("L3" if tier == "L3->L4->L3" else tier, result["usage"])

        # Yield stream.end with metrics
        yield {
            "type": "stream.end",
            "tier": tier,
            "usage": result["usage"],
            "ttfc_ms": result["ttfc_ms"],
            "ttc_ms": result["ttc_ms"],
            "cost_usd": cost_usd,
        }
