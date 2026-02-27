"""
AIde Prompt Builder — v3

Assembles system prompts with snapshot context for L4 and L3 tiers.
Tool definitions are passed separately via the API tools parameter.

Changes from v2:
  - No primitive schemas in prompt (tools are schema-enforced via API)
  - No L2 prompt (shelved)
  - L4 handles first messages (was L3)
  - L3 handles all subsequent messages (was L2 + L3)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Tool definitions — shared across tiers
TOOLS = [
    {
        "name": "mutate_entity",
        "description": "Create, update, or remove an entity",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "update", "remove", "move", "reorder"],
                },
                "id": {
                    "type": "string",
                    "description": "Entity ID (for create). snake_case, max 64 chars.",
                },
                "ref": {
                    "type": "string",
                    "description": "Entity ID (for update/remove/move).",
                },
                "parent": {
                    "type": "string",
                    "description": "'root' or parent entity ID.",
                },
                "display": {
                    "type": "string",
                    "enum": [
                        "page", "section", "card", "list", "table",
                        "checklist", "grid", "metric", "text", "image",
                    ],
                },
                "props": {
                    "type": "object",
                    "description": "Entity properties. Field names: snake_case, singular nouns.",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "set_relationship",
        "description": "Set, remove, or constrain a relationship between entities",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["set", "remove", "constrain"],
                },
                "from": {"type": "string", "description": "Source entity ID"},
                "to": {"type": "string", "description": "Target entity ID"},
                "type": {"type": "string", "description": "Relationship type name"},
                "cardinality": {
                    "type": "string",
                    "enum": ["one_to_one", "many_to_one", "many_to_many"],
                    "description": "Only needed on first use of this relationship type.",
                },
            },
            "required": ["action", "type"],
        },
    },
]


def load_prompt(name: str) -> str:
    """Load prompt markdown from prompts directory."""
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text()


def _assemble_tier_prompt(tier_name: str) -> str:
    """
    Assemble a tier prompt by injecting the shared prefix.

    Tier prompts contain {{shared_prefix}} placeholder which gets
    replaced with the shared prefix content.
    """
    shared = load_prompt("shared_prefix")
    tier = load_prompt(f"{tier_name}_system")
    return tier.replace("{{shared_prefix}}", shared)


def build_l4_prompt(snapshot: dict[str, Any]) -> str:
    """
    Build L4 (Opus) system prompt with snapshot context.

    L4 handles first messages (schema synthesis) and escalations.
    Tool definitions are NOT included in the prompt — they're passed
    via the API tools parameter for schema enforcement.
    """
    base = _assemble_tier_prompt("l4")
    snapshot_json = json.dumps(snapshot, indent=2, sort_keys=True)

    return f"""{base}

## Current Snapshot
```json
{snapshot_json}
```
"""


def build_l3_prompt(snapshot: dict[str, Any]) -> str:
    """
    Build L3 (Sonnet) system prompt with snapshot context.

    L3 handles all messages after the first.
    """
    base = _assemble_tier_prompt("l3")
    snapshot_json = json.dumps(snapshot, indent=2, sort_keys=True)

    return f"""{base}

## Current Snapshot
```json
{snapshot_json}
```
"""


def build_system_prompt(tier: str, snapshot: dict[str, Any]) -> str:
    """Build system prompt for the given tier."""
    if tier == "L4":
        return build_l4_prompt(snapshot)
    elif tier == "L3":
        return build_l3_prompt(snapshot)
    else:
        raise ValueError(f"Unknown tier: {tier}. Only L4 and L3 are active.")


def build_messages(
    conversation: list[dict[str, Any]],
    user_message: str,
) -> list[dict[str, Any]]:
    """
    Build messages array for API call.

    Includes recent conversation tail (last 10 turns) plus current message.
    Previous assistant responses are summarized to save tokens — tool calls
    become "[N mutations applied]" instead of full tool use blocks.
    """
    messages = []

    for turn in conversation[-10:]:
        role = turn["role"]
        content = turn["content"]

        if role == "assistant" and isinstance(content, list):
            # Summarize tool calls to save tokens
            text_parts = []
            tool_count = 0
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block["text"])
                    elif block.get("type") == "tool_use":
                        tool_count += 1
                elif isinstance(block, str):
                    text_parts.append(block)

            summary = ""
            if text_parts:
                summary = " ".join(text_parts)
            if tool_count:
                summary += f"\n[{tool_count} mutations applied]"
            messages.append({"role": "assistant", "content": summary.strip()})
        else:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_message})
    return messages
