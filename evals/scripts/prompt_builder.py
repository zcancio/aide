"""
Prompt builder for LLM tiers (v3.1).

Assembles system prompts from shared prefix + tier instructions + context.

Architecture (Anthropic cache_control):

    SYSTEM PROMPT (three content blocks):
    ┌─────────────────────────┐
    │  shared_prefix.md       │  cache_control: ephemeral (1h)
    │  (~2,500 tokens)        │  — shared across tiers on same model
    ├─────────────────────────┤
    │  l{N}_tier.md           │  cache_control: ephemeral (1h)
    │  (~500-800 tokens)      │  — tier-specific, cached separately
    ├─────────────────────────┤
    │  Snapshot (entityState)  │  no cache — changes every mutation
    └─────────────────────────┘

    MESSAGES ARRAY:
    ┌─────────────────────────┐
    │  Conversation tail       │  cache_control: ephemeral on last tail msg
    │  (previous turns)        │  — stable across rapid-fire messages
    ├─────────────────────────┤
    │  Current user message    │  no cache — new every call
    └─────────────────────────┘

Cache strategy:
- Shared prefix is the big win (~2,500 tokens, shared across L3+L4 on Sonnet)
- Tier block is small but still benefits from caching across turns
- Snapshot is small and changes constantly — not worth caching
- Conversation tail is stable between consecutive messages within
  a session — cache breakpoint on the last tail message means
  only the new user message is uncached input

Code fence handling:
- Sonnet tends to wrap JSONL output in ```jsonl fences despite prompt
  instructions. The server should strip these in post-processing.
- Prefilling the assistant response (e.g. with "{") does NOT work for
  JSONL — it causes multi-line pretty-printed JSON and wrapper objects.
  Only use prefill for single-object JSON responses, not streaming JSONL.
- L4 outputs plain text and doesn't have this issue.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone, timedelta
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


def _shared_prefix() -> str:
    """Load the shared prefix (identical across all tiers)."""
    return _load("shared_prefix")


def build_system_blocks(tier: str, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Build system prompt as content blocks for Anthropic API.

    Returns three blocks:
    1. Shared prefix (cached — same across all tiers on the same model)
    2. Tier instructions (cached — different per tier)
    3. Snapshot (uncached — changes every mutation)

    Cache architecture:
      Anthropic caches match from the start of the prompt. By giving the
      shared prefix its own cache breakpoint, L3 and L4 (both Sonnet)
      share the ~2,500 token prefix cache. Only the tier block differs.

    Args:
        tier: "L2", "L3", or "L4"
        snapshot: Current entityState

    Returns:
        List of content blocks for system parameter.
    """
    pacific = timezone(timedelta(hours=-8))
    today = datetime.now(pacific).date()

    # Build calendar context so the model doesn't have to do date arithmetic
    cal_lines = []
    # This week (Mon-Sun containing today)
    mon = today - timedelta(days=today.weekday())  # Monday of this week
    week = []
    for i in range(7):
        d = mon + timedelta(days=i)
        marker = " (today)" if d == today else ""
        week.append(f"{d.strftime('%a %b %d')}{marker}")
    cal_lines.append("This week: " + " | ".join(week))
    # Key relative dates
    # Find last/this/next for common day references
    days_since_thu = (today.weekday() - 3) % 7
    last_thu = today - timedelta(days=days_since_thu) if days_since_thu > 0 else today - timedelta(days=7)
    this_thu = last_thu + timedelta(days=7)
    cal_lines.append(f"Last Thursday = {last_thu.strftime('%b %d')}. This Thursday = {this_thu.strftime('%b %d')}. Two weeks from last Thursday = {(last_thu + timedelta(days=14)).strftime('%b %d')}.")
    calendar_context = "\n".join(cal_lines)

    prefix = _shared_prefix().replace(
        "{{current_date}}", today.strftime("%A, %B %d, %Y")
    ).replace(
        "{{calendar_context}}", calendar_context
    )
    tier_file = {"L2": "l2_tier", "L3": "l3_tier", "L4": "l4_tier"}[tier]
    tier_text = _load(tier_file)
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


# --- Convenience wrappers (flat string, for tests/mocks) ---


def build_l2_prompt(snapshot: dict[str, Any]) -> str:
    """Build L2 system prompt as flat string (for tests/mock mode)."""
    blocks = build_system_blocks("L2", snapshot)
    return "\n\n".join(b["text"] for b in blocks)


def build_l3_prompt(snapshot: dict[str, Any]) -> str:
    """Build L3 system prompt as flat string (for tests/mock mode)."""
    blocks = build_system_blocks("L3", snapshot)
    return "\n\n".join(b["text"] for b in blocks)


def build_l4_prompt(snapshot: dict[str, Any]) -> str:
    """Build L4 system prompt as flat string (for tests/mock mode)."""
    blocks = build_system_blocks("L4", snapshot)
    return "\n\n".join(b["text"] for b in blocks)


def build_messages(
    conversation: list[dict[str, Any]],
    user_message: str,
    tail_size: int = 5,
) -> list[dict[str, Any]]:
    """
    Build messages array for API call.

    Includes recent conversation tail plus current message.
    Previous L2/L3 (mutation) responses are summarized to save tokens.
    Previous L4 (query) responses are included in full.
    Cache breakpoint is set on the last tail message so the
    conversation prefix is cached across rapid-fire messages.

    Args:
        conversation: Full conversation history.
        user_message: Current user message.
        tail_size: Number of recent turns to include (default 5).

    Returns:
        Messages array formatted for Anthropic API.
    """
    messages = []
    tail = conversation[-tail_size:]

    for i, turn in enumerate(tail):
        role = turn.get("role", "user")
        content = turn.get("content", "")

        # Summarize mutation responses (they were JSONL, not useful as context)
        if role == "assistant" and turn.get("type") == "mutation":
            op_count = turn.get("operation_count", 0)
            if op_count > 0:
                content = f"[{op_count} operations applied]"
            else:
                content = "[response sent]"

        msg: dict[str, Any] = {"role": role, "content": content}

        # Cache breakpoint on the last tail message
        # (everything before this is identical between consecutive calls)
        if i == len(tail) - 1:
            msg["content"] = [
                {
                    "type": "text",
                    "text": content,
                    "cache_control": {"type": "ephemeral"},
                }
            ]

        messages.append(msg)

    # Current user message — always uncached
    messages.append({"role": "user", "content": user_message})
    return messages
