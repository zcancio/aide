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


def _get_prompts_dir(version: str | None = None) -> Path:
    """Get prompts directory for specified version.

    Args:
        version: Version string (e.g., "v1", "v2"). If None, uses "current" symlink.

    Returns:
        Path to prompts directory for the version.

    Raises:
        FileNotFoundError: If specified version directory doesn't exist.
    """
    if version:
        versioned_dir = PROMPTS_DIR / version
        if not versioned_dir.exists():
            raise FileNotFoundError(f"Prompt version '{version}' not found at {versioned_dir}")
        return versioned_dir

    # Default: use "current" symlink
    current = PROMPTS_DIR / "current"
    if current.is_symlink() or current.is_dir():
        return current

    # Fallback for non-versioned setup (backward compatibility)
    return PROMPTS_DIR


def load_prompt(tier: str, version: str | None = None) -> str:
    """Load and assemble system prompt for tier, resolving shared prefix.

    L2 tier is deprecated and uses L3 prompts.

    Args:
        tier: Tier name (L2, L3, L4)
        version: Optional version string (e.g., "v1", "v2")

    Returns:
        Assembled prompt with shared prefix resolved.
    """
    prompts_dir = _get_prompts_dir(version)
    shared_path = prompts_dir / "shared_prefix.md"
    shared = shared_path.read_text()
    # L2 deprecated - use L3 prompts
    effective_tier = "l3" if tier.lower() == "l2" else tier.lower()
    tier_path = prompts_dir / f"{effective_tier}_system.md"
    tier_prompt = tier_path.read_text()
    return tier_prompt.replace("{{shared_prefix}}", shared)


def build_system_blocks(tier: str, snapshot: dict[str, Any], version: str | None = None) -> list[dict[str, Any]]:
    """Build system prompt as separate blocks for caching.

    Args:
        tier: Tier name (L2, L3, L4)
        snapshot: Current snapshot dictionary
        version: Optional prompt version (e.g., "v1", "v2")

    Returns list of content blocks:
    - Block 1: Static tier instructions (cached, survives across turns)
    - Block 2: Dynamic snapshot (not cached, changes every turn)
    """
    base = load_prompt(tier, version=version)
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


def _load_prompt_old(name: str, version: str | None = None) -> str:
    """Load prompt from prompts directory (old method, no prefix resolution)."""
    prompts_dir = _get_prompts_dir(version)
    path = prompts_dir / f"{name}.md"
    return path.read_text()


def build_l2_prompt(snapshot: dict[str, Any]) -> str:
    """
    Build L2 (Haiku) system prompt with snapshot context.

    L2 handles routine updates using existing schema.

    DEPRECATED: Use build_system_blocks("l3", snapshot) instead.
    L2 tier was consolidated into L3.
    """
    base = load_prompt("l3")
    snapshot_json = json.dumps(snapshot, indent=2)

    return f"""{base}

## Current Snapshot
```json
{snapshot_json}
```
"""


def build_l3_prompt(snapshot: dict[str, Any]) -> str:
    """
    Build L3 (Sonnet) system prompt with snapshot context.

    L3 handles schema synthesis and complex mutations.

    DEPRECATED: Use build_system_blocks("l3", snapshot) instead.
    Primitives are now inline in shared prefix.
    """
    base = load_prompt("l3")
    snapshot_json = json.dumps(snapshot, indent=2)

    return f"""{base}

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
