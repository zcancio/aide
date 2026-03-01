"""
Escalation detection for L3 → L4 routing.

Detects when L3 (Sonnet) produces output that signals it needs L4 (Opus):
1. Voice text contains escalation phrases
2. L3 created structural containers (page/section/table/grid) — that's L4's job
"""

from __future__ import annotations

from typing import Any

# Phrases in L3 voice output that signal escalation need
ESCALATION_PHRASES = [
    "needs a new section",
    "new section structure",
    "needs structural",
    "escalat",
]

# Display types that only L4 should create (structural containers)
STRUCTURAL_DISPLAYS = {"page", "section", "table", "grid"}


def needs_escalation(result: dict[str, Any]) -> bool:
    """
    Check if L3 result signals that L4 escalation is needed.

    Args:
        result: L3 output with text_blocks and tool_calls

    Returns:
        True if escalation to L4 is needed
    """
    # Signal 1: Voice text contains escalation phrases
    text_blocks = result.get("text_blocks", [])
    all_voice = " ".join(b["text"] if isinstance(b, dict) else b for b in text_blocks).lower()
    if any(phrase in all_voice for phrase in ESCALATION_PHRASES):
        return True

    # Signal 2: L3 created structural containers
    tool_calls = result.get("tool_calls", [])
    for tc in tool_calls:
        if tc.get("name") != "mutate_entity":
            continue
        inp = tc.get("input", {})
        if inp.get("action") == "create" and inp.get("display") in STRUCTURAL_DISPLAYS:
            return True

    return False
