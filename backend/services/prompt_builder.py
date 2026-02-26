"""
Prompt builder for LLM tiers (v3.1).

Assembles system prompts from shared prefix + tier instructions + context.
Uses Anthropic cache_control for token efficiency.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Cache loaded prompts in memory (they don't change at runtime)
_cache: dict[str, str] = {}


def _load(name: str) -> str:
    """Load and cache a prompt file."""
    if name not in _cache:
        path = PROMPTS_DIR / f"{name}.md"
        _cache[name] = path.read_text()
    return _cache[name]


def _build_calendar_context(today: date) -> str:
    """Build calendar context for date-aware prompts."""
    cal_lines = []

    # This week (Mon-Sun)
    mon = today - timedelta(days=today.weekday())
    week = []
    for i in range(7):
        d = mon + timedelta(days=i)
        marker = " (today)" if d == today else ""
        week.append(f"{d.strftime('%a %b %d')}{marker}")
    cal_lines.append("This week: " + " | ".join(week))

    # Thursday references (common for recurring events)
    days_since_thu = (today.weekday() - 3) % 7
    last_thu = today - timedelta(days=days_since_thu) if days_since_thu > 0 else today - timedelta(days=7)
    this_thu = last_thu + timedelta(days=7)
    cal_lines.append(
        f"Last Thursday = {last_thu.strftime('%b %d')}. "
        f"This Thursday = {this_thu.strftime('%b %d')}. "
        f"Two weeks from last Thursday = {(last_thu + timedelta(days=14)).strftime('%b %d')}."
    )

    return "\n".join(cal_lines)


def build_system_blocks(
    tier: str,
    snapshot: dict[str, Any],
    user_timezone: str = "America/Los_Angeles",
) -> list[dict[str, Any]]:
    """
    Build system prompt as content blocks for Anthropic API.

    Returns three blocks with cache control for token efficiency:
    1. Shared prefix (cached — same across all tiers)
    2. Tier instructions (cached — different per tier)
    3. Snapshot (uncached — changes every mutation)

    Args:
        tier: "L2", "L3", or "L4"
        snapshot: Current entityState
        user_timezone: IANA timezone for date context

    Returns:
        List of content blocks for system parameter.
    """
    # Use user's timezone for date context
    tz = timezone(timedelta(hours=-8))  # Default to Pacific
    today = datetime.now(tz).date()

    # Build shared prefix with templates
    prefix = (
        _load("shared_prefix")
        .replace("{{current_date}}", today.strftime("%A, %B %d, %Y"))
        .replace("{{calendar_context}}", _build_calendar_context(today))
    )

    # Load tier-specific instructions
    tier_file = {"L2": "l2_tier", "L3": "l3_tier", "L4": "l4_tier"}[tier]
    tier_text = _load(tier_file)

    # Format snapshot
    snapshot_json = json.dumps(snapshot, indent=2)

    return [
        {
            "type": "text",
            "text": prefix,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": tier_text,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": f"## Current Snapshot\n```json\n{snapshot_json}\n```",
        },
    ]


def build_messages(
    conversation: list[dict[str, Any]],
    user_message: str,
    tail_size: int = 5,
) -> list[dict[str, Any]]:
    """
    Build messages array for API call.

    Includes recent conversation tail plus current message.
    Cache breakpoint on last tail message for token efficiency.

    Args:
        conversation: Full conversation history
        user_message: Current user message
        tail_size: Number of recent turns to include

    Returns:
        Messages array formatted for Anthropic API
    """
    messages = []
    tail = conversation[-tail_size:]

    for i, turn in enumerate(tail):
        role = turn.get("role", "user")
        content = turn.get("content", "")

        # Summarize mutation responses (JSONL not useful as context)
        if role == "assistant" and turn.get("type") == "mutation":
            op_count = turn.get("operation_count", 0)
            content = f"[{op_count} operations applied]" if op_count else "[response sent]"

        msg: dict[str, Any] = {"role": role, "content": content}

        # Cache breakpoint on last tail message
        if i == len(tail) - 1:
            msg["content"] = [
                {
                    "type": "text",
                    "text": content,
                    "cache_control": {"type": "ephemeral"},
                }
            ]

        messages.append(msg)

    messages.append({"role": "user", "content": user_message})
    return messages


# --- Convenience wrappers (flat string, for tests) ---


def build_l2_prompt(snapshot: dict[str, Any]) -> str:
    """Build L2 prompt as flat string (for backward compatibility)."""
    blocks = build_system_blocks("L2", snapshot)
    return "\n\n".join(b["text"] for b in blocks)


def build_l3_prompt(snapshot: dict[str, Any]) -> str:
    """Build L3 prompt as flat string (for backward compatibility)."""
    blocks = build_system_blocks("L3", snapshot)
    return "\n\n".join(b["text"] for b in blocks)


def build_l4_prompt(snapshot: dict[str, Any]) -> str:
    """Build L4 prompt as flat string (for backward compatibility)."""
    blocks = build_system_blocks("L4", snapshot)
    return "\n\n".join(b["text"] for b in blocks)
