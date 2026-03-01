"""
Prompt builder for LLM tiers.

Assembles system prompts with snapshot context for each tier.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(tier: str) -> str:
    """Load and assemble system prompt for tier, resolving shared prefix."""
    shared_path = PROMPTS_DIR / "shared_prefix.md"
    shared = shared_path.read_text()
    tier_path = PROMPTS_DIR / f"{tier.lower()}_system.md"
    tier_prompt = tier_path.read_text()
    return tier_prompt.replace("{{shared_prefix}}", shared)


def build_system_blocks(tier: str, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Build system prompt as separate blocks for caching.

    Returns list of content blocks:
    - Block 1: Static tier instructions (cached, survives across turns)
    - Block 2: Dynamic snapshot (not cached, changes every turn)
    """
    base = load_prompt(tier)
    today = datetime.now().strftime("%Y-%m-%d")
    base = base.replace("{{current_date}}", today)
    snapshot_json = json.dumps(snapshot, indent=2, sort_keys=True)

    return [
        {
            "type": "text",
            "text": base,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": f"\n## Current Snapshot\n```json\n{snapshot_json}\n```\n",
        },
    ]


def build_messages(conversation: list[dict[str, Any]], user_message: str) -> list[dict[str, Any]]:
    """Build messages array with conversation windowing.

    Windows to last 9 message blocks (~3 exchanges) to prevent
    unbounded history growth at full input price.
    """
    MAX_HISTORY_MESSAGES = 9
    if len(conversation) > MAX_HISTORY_MESSAGES:
        windowed = conversation[-MAX_HISTORY_MESSAGES:]
        # Ensure we start on a user message (API requirement)
        while windowed and windowed[0]["role"] != "user":
            windowed = windowed[1:]
        msgs = list(windowed)
    else:
        msgs = list(conversation)
    msgs.append({"role": "user", "content": user_message})
    return msgs


# ── Deprecated Functions (kept for backward compatibility) ───────────────────


def _load_prompt_old(name: str) -> str:
    """Load prompt from prompts directory (old method, no prefix resolution)."""
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text()


def build_l2_prompt(snapshot: dict[str, Any]) -> str:
    """
    Build L2 (Haiku) system prompt with snapshot context.

    L2 handles routine updates using existing schema.
    """
    base = _load_prompt_old("l2_system")
    primitives = _load_prompt_old("primitive_schemas")
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
    base = _load_prompt_old("l3_system")
    primitives = _load_prompt_old("primitive_schemas")
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
    base = _load_prompt_old("l4_system")
    snapshot_json = json.dumps(snapshot, indent=2)

    return f"""{base}

## Current Snapshot
```json
{snapshot_json}
```
"""
