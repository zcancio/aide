"""
AIde Streaming Orchestrator — v3

Coordinates classification → prompt building → streaming tool use → reduction.

Changes from v2:
  - Streaming tool use instead of JSONL parsing
  - Voice is text blocks interleaved with tool calls (not a JSONL signal)
  - L4 for first messages, L3 for everything after
  - Tool calls buffered via input_json_delta, applied on content_block_stop
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

import anthropic

from classifier import ClassificationResult, classify
from prompt_builder import TOOLS, build_messages, build_system_prompt

logger = logging.getLogger(__name__)


class StreamingOrchestrator:
    """
    Process a user message through the full pipeline:
    1. Classify → L4 or L3
    2. Build system prompt with snapshot
    3. Stream tool calls from LLM
    4. Apply each completed tool call to reducer
    5. Yield deltas for client
    """

    def __init__(
        self,
        aide_id: str,
        snapshot: dict[str, Any],
        conversation: list[dict[str, Any]],
        api_key: str,
    ):
        self.aide_id = aide_id
        self.snapshot = snapshot
        self.conversation = conversation
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def process_message(
        self,
        user_message: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Process a message and yield streaming results.

        Yields events:
          - {"type": "meta.classification", "tier": ..., "model": ..., "reason": ...}
          - {"type": "voice", "text": ...}           # text block from model
          - {"type": "tool_call", "name": ..., "input": ...}  # completed tool call
          - {"type": "entity.create", "id": ..., "data": ...} # reducer delta
          - {"type": "entity.update", "id": ..., "data": ...} # reducer delta
          - {"type": "entity.remove", "id": ...}              # reducer delta
          - {"type": "relationship.set", ...}                  # reducer delta
          - {"type": "error", "message": ...}                  # on failure
        """
        # 1. Classify
        classification = classify(user_message, self.snapshot)
        yield {
            "type": "meta.classification",
            "tier": classification.tier,
            "model": classification.model,
            "reason": classification.reason,
        }

        # 2. Build prompt and messages
        system = build_system_prompt(classification.tier, self.snapshot)
        messages = build_messages(self.conversation, user_message)

        # 3. Stream with tool use
        try:
            async with self.client.messages.stream(
                model=classification.model,
                max_tokens=8192,
                temperature=classification.temperature,
                system=system,
                messages=messages,
                tools=TOOLS,
            ) as stream:
                current_tool = None
                current_text = ""

                async for event in stream:
                    # Content block start
                    if event.type == "content_block_start":
                        if event.content_block.type == "tool_use":
                            current_tool = {
                                "name": event.content_block.name,
                                "id": event.content_block.id,
                                "input_json": "",
                            }
                        elif event.content_block.type == "text":
                            current_text = ""

                    # Content block delta
                    elif event.type == "content_block_delta":
                        if hasattr(event.delta, "partial_json") and current_tool:
                            current_tool["input_json"] += event.delta.partial_json
                        elif hasattr(event.delta, "text"):
                            current_text += event.delta.text

                    # Content block stop — this is where we apply
                    elif event.type == "content_block_stop":
                        if current_tool:
                            # Parse completed tool call
                            try:
                                params = json.loads(current_tool["input_json"])
                            except json.JSONDecodeError:
                                logger.warning(
                                    "Failed to parse tool call JSON: %s",
                                    current_tool["input_json"][:200],
                                )
                                yield {
                                    "type": "error",
                                    "message": f"Malformed tool call: {current_tool['name']}",
                                }
                                current_tool = None
                                continue

                            # Yield raw tool call for logging
                            yield {
                                "type": "tool_call",
                                "name": current_tool["name"],
                                "input": params,
                            }

                            # Decompose and apply to reducer
                            async for delta in self._apply_tool_call(
                                current_tool["name"], params
                            ):
                                yield delta

                            current_tool = None

                        elif current_text.strip():
                            # Voice output
                            yield {
                                "type": "voice",
                                "text": current_text.strip(),
                            }
                            current_text = ""

        except anthropic.APIError as e:
            logger.error("Anthropic API error: %s", e)
            yield {"type": "error", "message": f"API error: {e}"}

    async def _apply_tool_call(
        self,
        tool_name: str,
        params: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Apply a tool call to the snapshot and yield reducer deltas.

        This is where tool calls get decomposed into reducer events
        and applied to the snapshot.
        """
        if tool_name == "mutate_entity":
            action = params.get("action")
            seq = self.snapshot.get("_sequence", 0) + 1
            self.snapshot["_sequence"] = seq

            if action == "create":
                eid = params.get("id", f"entity_{seq}")
                entity = {
                    "id": eid,
                    "parent": params.get("parent", "root"),
                    "display": params.get("display"),
                    "props": params.get("props", {}),
                    "_removed": False,
                    "_created_seq": seq,
                    "_updated_seq": seq,
                }
                self.snapshot.setdefault("entities", {})[eid] = entity
                yield {
                    "type": "entity.create",
                    "id": eid,
                    "data": entity,
                }

            elif action == "update":
                ref = params.get("ref", "")
                if ref in self.snapshot.get("entities", {}):
                    entity = self.snapshot["entities"][ref]
                    entity["props"].update(params.get("props", {}))
                    if params.get("display"):
                        entity["display"] = params["display"]
                    entity["_updated_seq"] = seq
                    yield {
                        "type": "entity.update",
                        "id": ref,
                        "data": entity,
                    }
                else:
                    logger.warning("Entity not found for update: %s", ref)

            elif action == "remove":
                ref = params.get("ref", "")
                if ref in self.snapshot.get("entities", {}):
                    self.snapshot["entities"][ref]["_removed"] = True
                    self.snapshot["entities"][ref]["_updated_seq"] = seq
                    yield {"type": "entity.remove", "id": ref}

            elif action == "move":
                ref = params.get("ref", "")
                new_parent = params.get("parent")
                if ref in self.snapshot.get("entities", {}) and new_parent:
                    self.snapshot["entities"][ref]["parent"] = new_parent
                    self.snapshot["entities"][ref]["_updated_seq"] = seq
                    yield {
                        "type": "entity.update",
                        "id": ref,
                        "data": self.snapshot["entities"][ref],
                    }

        elif tool_name == "set_relationship":
            action = params.get("action")
            if action == "set":
                rel = {
                    "from": params.get("from", ""),
                    "to": params.get("to", ""),
                    "type": params.get("type", ""),
                    "cardinality": params.get("cardinality", "many_to_one"),
                }
                self.snapshot.setdefault("relationships", []).append(rel)
                yield {"type": "relationship.set", **rel}

            elif action == "remove":
                rels = self.snapshot.get("relationships", [])
                self.snapshot["relationships"] = [
                    r for r in rels
                    if not (
                        r["from"] == params.get("from")
                        and r["to"] == params.get("to")
                        and r["type"] == params.get("type")
                    )
                ]
                yield {
                    "type": "relationship.remove",
                    "from": params.get("from"),
                    "to": params.get("to"),
                    "rel_type": params.get("type"),
                }
