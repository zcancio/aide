# Prompt System Integration Spec

## Overview

Integrate the eval-validated prompt architecture (`evals/scripts/`) into production (`backend/`). The new system uses a shared prefix + tier-specific instructions pattern with Anthropic cache optimization, a rule-based tier classifier, and dynamic calendar context.

## Current State (Production)

```
backend/
├── prompts/
│   ├── l2_system.md          # L2 instructions (~80 lines)
│   ├── l3_system.md          # L3 instructions
│   ├── l4_system.md          # L4 instructions
│   └── primitive_schemas.md   # Event schemas
├── services/
│   ├── prompt_builder.py     # Builds flat string prompts
│   ├── anthropic_client.py   # Streams from Anthropic API
│   └── llm_provider.py       # Factory for mock/real LLM
```

**Issues with current system:**
- No shared prefix (duplicated content across tiers)
- No cache optimization (wastes tokens on each call)
- No calendar context (model guesses dates)
- No tier classifier (hardcoded routing)
- Flat strings instead of content blocks

## Target State (Eval-Validated)

```
backend/
├── prompts/
│   ├── shared_prefix.md      # Voice, format, primitives, entity tree (~200 lines)
│   ├── l2_tier.md            # L2-specific rules (~180 lines)
│   ├── l3_tier.md            # L3-specific rules (~160 lines)
│   └── l4_tier.md            # L4-specific rules (~110 lines)
├── services/
│   ├── prompt_builder.py     # Content blocks with cache control
│   ├── tier_classifier.py    # Rule-based L2/L3/L4 routing
│   ├── anthropic_client.py   # Updated for content blocks
│   └── llm_provider.py       # Unchanged
```

## Architecture

### System Prompt Structure

```
┌─────────────────────────────┐
│  shared_prefix.md           │  cache_control: ephemeral
│  (~2,500 tokens)            │  — shared across L2/L3/L4
│                             │
│  - Voice rules              │
│  - Output format (JSONL)    │
│  - Primitives reference     │
│  - Entity tree structure    │
│  - Message classification   │
├─────────────────────────────┤
│  l{N}_tier.md               │  cache_control: ephemeral
│  (~500-800 tokens)          │  — tier-specific
│                             │
│  - Tier role & rules        │
│  - Escalation triggers      │
│  - Examples                 │
├─────────────────────────────┤
│  Snapshot JSON              │  no cache (changes every turn)
│  (~100-500 tokens)          │
└─────────────────────────────┘
```

### Cache Strategy

1. **Shared prefix** — Cached 1 hour, shared across L3+L4 (both Sonnet), saves ~2,500 tokens/call
2. **Tier block** — Cached 1 hour per tier, ~500-800 tokens
3. **Snapshot** — Never cached (changes every mutation)
4. **Conversation tail** — Cache breakpoint on last message, saves context tokens

### Template Variables

The shared prefix supports dynamic templates:
- `{{current_date}}` — "Tuesday, February 25, 2026"
- `{{calendar_context}}` — Week grid + Thursday references for schedule domains

---

## Implementation Plan

### Phase 1: Copy Prompts

Copy eval prompts to production:

```bash
cp evals/scripts/shared_prefix.md backend/prompts/
cp evals/scripts/l2_tier.md backend/prompts/
cp evals/scripts/l3_tier.md backend/prompts/
cp evals/scripts/l4_tier.md backend/prompts/
```

Remove old prompts after migration verified:
- `l2_system.md`
- `l3_system.md`
- `l4_system.md`
- `primitive_schemas.md` (content moved to shared_prefix)

### Phase 2: Update prompt_builder.py

Replace `backend/services/prompt_builder.py` with:

```python
"""
Prompt builder for LLM tiers (v3.1).

Assembles system prompts from shared prefix + tier instructions + context.
Uses Anthropic cache_control for token efficiency.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
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
    prefix = _load("shared_prefix").replace(
        "{{current_date}}", today.strftime("%A, %B %d, %Y")
    ).replace(
        "{{calendar_context}}", _build_calendar_context(today)
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
    blocks = build_system_blocks("L2", snapshot)
    return "\n\n".join(b["text"] for b in blocks)

def build_l3_prompt(snapshot: dict[str, Any]) -> str:
    blocks = build_system_blocks("L3", snapshot)
    return "\n\n".join(b["text"] for b in blocks)

def build_l4_prompt(snapshot: dict[str, Any]) -> str:
    blocks = build_system_blocks("L4", snapshot)
    return "\n\n".join(b["text"] for b in blocks)
```

### Phase 3: Add Tier Classifier

Create `backend/services/tier_classifier.py`:

```python
"""
Rule-based tier classifier.

Routes user messages to L2/L3/L4 based on intent detection.
Validated against 63 multi-turn scenarios with 100% accuracy.
"""

from __future__ import annotations

import re
from typing import Any


def classify_tier(message: str, snapshot: dict[str, Any] | None) -> str:
    """
    Classify which tier should handle a user message.

    Decision tree:
    1. Structural keywords (create, track, reorganize) → L3
    2. Questions (?, query starters, analysis requests) → L4
    3. No entities exist → L3 (first turn)
    4. Budget/quotes/tasks introduction (empty tables) → L3
    5. Multi-item creation (3+ comma items) → L3
    6. Default → L2 (routine mutations)

    Args:
        message: User's message text
        snapshot: Current entity state (or None if empty)

    Returns:
        "L2", "L3", or "L4"
    """
    msg_lower = message.lower().strip()
    entities = snapshot.get("entities", {}) if snapshot else {}
    entity_ids_lower = [eid.lower() for eid in entities.keys()]

    # "add a new [thing]" — L3 only if table doesn't exist
    add_new_match = re.search(r'add a new (\w+)', msg_lower)
    if add_new_match:
        thing = add_new_match.group(1)
        thing_exists = any(
            thing in eid or thing.rstrip('s') in eid or thing + 's' in eid
            for eid in entity_ids_lower
        )
        return "L2" if thing_exists else "L3"

    # Structural keywords → L3
    structural = [
        "add a section", "set up a", "create a", "make a",
        "we should track", "we should do", "gotta do",
        "redoing", "reorganize", "group the", "split the", "separate the"
    ]
    if any(kw in msg_lower for kw in structural):
        return "L3"

    # Questions → L4
    if "?" in msg_lower:
        return "L4"

    query_starts = [
        "how many", "who", "what's left", "what do we", "how much",
        "is there", "is the", "is it", "are the", "are they",
        "do we", "does it", "does the", "where are we", "show me", "give me"
    ]
    if any(msg_lower.startswith(q) for q in query_starts):
        return "L4"

    query_phrases = [
        "breakdown", "looking like", "status update",
        "where do we stand", "how are we", "what's the total",
        "run the numbers", "full picture"
    ]
    if any(qp in msg_lower for qp in query_phrases):
        return "L4"

    # No entities → L3 (first turn)
    if not entities:
        return "L3"

    # Helper: check if entity has children (not just skeleton)
    def has_children(prefix: str) -> bool:
        parent_ids = [eid for eid in entities.keys() if prefix in eid.lower()]
        if not parent_ids:
            return False
        return any(e.get("parent") in parent_ids for e in entities.values())

    # Domain-specific patterns → L3 if table empty
    if re.search(r'budget\s+(is|around|of|:)', msg_lower):
        if not has_children("budget"):
            return "L3"

    if re.search(r'(\d+\s+)?quotes?\s+(for|from|:)', msg_lower) or \
       ("got" in msg_lower and "quote" in msg_lower):
        if not has_children("quote"):
            return "L3"

    contractor_pattern = r'(plumber|electrician|contractor|installer|painter|carpenter)'
    if re.search(contractor_pattern, msg_lower) and \
       re.search(r'(start|begin|come|schedule)', msg_lower):
        if not has_children("task"):
            return "L3"

    # Multi-item creation → L3 if intro pattern table empty
    segments = [s.strip() for s in msg_lower.split(",") if s.strip()]
    if len(segments) >= 3:
        has_numbers = sum(1 for s in segments if re.search(r'\d', s))
        intro_patterns = [
            "quotes", "chores", "tasks", "items", "players",
            "guests", "weekly", "daily", "monthly"
        ]
        matched_intro = next((ip for ip in intro_patterns if ip in msg_lower), None)

        if has_numbers >= 2 or matched_intro:
            if matched_intro:
                if not has_children(matched_intro):
                    return "L3"
            else:
                table_parents = [
                    e for e in entities.values()
                    if e.get("display") in ("table", "list", "checklist")
                ]
                if not table_parents:
                    return "L3"

    # Default → L2
    return "L2"
```

### Phase 4: Update anthropic_client.py

Update to accept content blocks for system prompt:

```python
async def stream(
    self,
    messages: list[dict[str, Any]],
    system: str | list[dict[str, Any]],  # Accept both formats
    model: str = "claude-sonnet-4-5-20250929",
    max_tokens: int = 4096,
) -> AsyncIterator[str]:
    """
    Stream response from Anthropic API.

    Args:
        messages: Messages array for the conversation
        system: System prompt (string or content blocks)
        model: Model identifier
        max_tokens: Maximum tokens to generate

    Yields:
        Text chunks as they arrive
    """
    async with self.client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=system,  # Pass through directly
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text
```

### Phase 5: Integration Point

Update the route/service that handles chat messages to use the classifier:

```python
from backend.services.tier_classifier import classify_tier
from backend.services.prompt_builder import build_system_blocks, build_messages

async def handle_message(user_message: str, snapshot: dict, conversation: list):
    # Classify tier
    tier = classify_tier(user_message, snapshot)

    # Build prompt with cache control
    system_blocks = build_system_blocks(tier, snapshot)
    messages = build_messages(conversation, user_message)

    # Select model based on tier
    model = {
        "L2": "claude-haiku-4-5-20251001",
        "L3": "claude-sonnet-4-5-20250929",
        "L4": "claude-sonnet-4-5-20250929",
    }[tier]

    # Stream response
    async for chunk in llm.stream(messages, system_blocks, model):
        yield chunk
```

---

## Migration Checklist

- [ ] Copy prompt files to `backend/prompts/`
- [ ] Update `prompt_builder.py` with content blocks
- [ ] Create `tier_classifier.py`
- [ ] Update `anthropic_client.py` to accept content blocks
- [ ] Update chat handler to use classifier
- [ ] Add tests for classifier (port from eval scenarios)
- [ ] Remove old prompt files
- [ ] Update any prompt references in tests

## Rollback Plan

If issues arise:
1. Revert prompt files to old versions
2. Revert `prompt_builder.py` to flat string version
3. Remove classifier, use hardcoded tier routing

## Validation

Run production with new prompts against eval scenarios:

```bash
cd evals/scripts
python eval_multiturn.py --save
```

Expected: 63/63 classifier accuracy, >0.95 avg score across all scenarios.

---

## Files Changed

| File | Action | Notes |
|------|--------|-------|
| `backend/prompts/shared_prefix.md` | Add | From `evals/scripts/` |
| `backend/prompts/l2_tier.md` | Add | From `evals/scripts/` |
| `backend/prompts/l3_tier.md` | Add | From `evals/scripts/` |
| `backend/prompts/l4_tier.md` | Add | From `evals/scripts/` |
| `backend/prompts/l2_system.md` | Remove | Replaced by above |
| `backend/prompts/l3_system.md` | Remove | Replaced by above |
| `backend/prompts/l4_system.md` | Remove | Replaced by above |
| `backend/prompts/primitive_schemas.md` | Remove | Moved to shared_prefix |
| `backend/services/prompt_builder.py` | Replace | Content blocks + cache |
| `backend/services/tier_classifier.py` | Add | New file |
| `backend/services/anthropic_client.py` | Update | Accept content blocks |
| `backend/tests/test_prompt_builder.py` | Update | Test new structure |
| `backend/tests/test_tier_classifier.py` | Add | Port eval scenarios |
