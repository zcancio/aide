"""
Prompt builder for LLM tiers.

Assembles system prompts with snapshot context for each tier.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load prompt from prompts directory."""
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text()


def build_l2_prompt(snapshot: dict[str, Any]) -> str:
    """
    Build L2 (Haiku) system prompt with snapshot context.

    L2 handles routine updates using existing schema.
    """
    base = load_prompt("l2_system")
    primitives = load_prompt("primitive_schemas")
    snapshot_json = json.dumps(snapshot, indent=2)

    return f"""{base}

## Primitive Schemas
{primitives}

## Current Snapshot
```json
{snapshot_json}
```
"""


def build_l3_prompt(snapshot: dict[str, Any]) -> str:
    """
    Build L3 (Sonnet) system prompt with snapshot context.

    L3 handles schema synthesis and complex mutations.
    """
    base = load_prompt("l3_system")
    primitives = load_prompt("primitive_schemas")
    snapshot_json = json.dumps(snapshot, indent=2)

    return f"""{base}

## Primitive Schemas
{primitives}

## Current Snapshot
```json
{snapshot_json}
```
"""


def build_l4_prompt(snapshot: dict[str, Any]) -> str:
    """
    Build L4 (Opus) system prompt with snapshot context.

    L4 handles queries requiring reasoning over the snapshot.
    """
    base = load_prompt("l4_system")
    snapshot_json = json.dumps(snapshot, indent=2)

    return f"""{base}

## Current Snapshot
```json
{snapshot_json}
```
"""


def build_messages(conversation: list[dict[str, Any]], user_message: str) -> list[dict[str, Any]]:
    """
    Build messages array for API call.

    Includes recent conversation tail (last 10 turns) plus current message.

    Args:
        conversation: Full conversation history
        user_message: Current user message

    Returns:
        Messages array formatted for Anthropic API
    """
    messages = []

    # Include recent conversation tail (last 10 turns)
    for turn in conversation[-10:]:
        messages.append({"role": turn["role"], "content": turn["content"]})

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    return messages
