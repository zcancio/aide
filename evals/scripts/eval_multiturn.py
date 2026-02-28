"""
AIde Multi-Turn Eval — v3

Runs realistic multi-turn scenarios against real Anthropic API using streaming
tool use. Tests the full conversational loop: vague kickoffs, incremental detail,
corrections, questions mid-build, and state reversals.

Scenarios from scenarios_multiturn.py — real users don't front-load context.

Usage:
    ANTHROPIC_API_KEY=sk-... python eval_multiturn.py
    ANTHROPIC_API_KEY=sk-... python eval_multiturn.py --scenario poker_realistic
    ANTHROPIC_API_KEY=sk-... python eval_multiturn.py --scenario flu_tracker --turn 4
    ANTHROPIC_API_KEY=sk-... python eval_multiturn.py --list

Output:
    eval_output/multiturn_YYYYMMDD_HHMMSS/
      ├── graduation_realistic.json
      ├── poker_realistic.json
      ├── ...
      └── report.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import anthropic

from scenarios_multiturn import MULTI_TURN_SCENARIOS, get_scenario

# ── Tool Definitions ────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "mutate_entity",
        "description": "Create, update, remove, or move an entity in the page tree.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "update", "remove", "move", "reorder"],
                },
                "id": {
                    "type": "string",
                    "description": "Entity ID (for create)",
                },
                "ref": {
                    "type": "string",
                    "description": "Entity ID (for update/remove/move)",
                },
                "parent": {
                    "type": "string",
                    "description": "'root' or parent entity ID",
                },
                "display": {
                    "type": "string",
                    "enum": [
                        "page", "section", "card", "list", "table",
                        "checklist", "grid", "metric", "text", "image",
                    ],
                },
                "props": {"type": "object"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "set_relationship",
        "description": "Set, remove, or constrain a relationship between entities.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["set", "remove", "constrain"],
                },
                "from": {"type": "string"},
                "to": {"type": "string"},
                "type": {"type": "string"},
                "cardinality": {
                    "type": "string",
                    "enum": ["one_to_one", "many_to_one", "many_to_many"],
                },
            },
            "required": ["action", "type"],
        },
    },
    {
        "name": "voice",
        "description": "Send a chat message to the user. You MUST call this tool in EVERY response — it is the ONLY way the user sees your reply. Without it, they see nothing. Call it after mutations to summarize, or alone for queries.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Short state reflection shown in chat. Max ~100 chars. No first person, no encouragement, no emojis.",
                },
            },
            "required": ["text"],
        },
    },
]

# ── Model Configuration ─────────────────────────────────────────────────────

MODELS = {
    "L4": "claude-opus-4-5-20251101",
    "L3": "claude-sonnet-4-5-20250929",
}

TEMPERATURE = {
    "L4": 0,   # deterministic for eval reproducibility
    "L3": 0,
}

# ── Configuration ────────────────────────────────────────────────────────────

OUTPUT_BASE = Path("eval_output")

def make_run_dir() -> Path:
    """Create a timestamped run directory."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_BASE / f"multiturn_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


# ── Prompt Loading ───────────────────────────────────────────────────────────

def load_prompt(tier: str) -> str:
    """Load and assemble system prompt for tier, resolving shared prefix."""
    prompt_dir = Path(__file__).parent

    # Load shared prefix
    shared_path = prompt_dir / "shared_prefix.md"
    shared = shared_path.read_text()

    # Load tier prompt
    tier_path = prompt_dir / f"{tier.lower()}_system.md"
    tier_prompt = tier_path.read_text()

    # Replace placeholder
    return tier_prompt.replace("{{shared_prefix}}", shared)


def build_system_prompt(tier: str, snapshot: dict[str, Any]) -> str:
    """Build system prompt with snapshot context."""
    base = load_prompt(tier)
    snapshot_json = json.dumps(snapshot, indent=2, sort_keys=True)
    return f"""{base}

## Current Snapshot
```json
{snapshot_json}
```
"""


# ── Reducer (minimal, for eval snapshot tracking) ────────────────────────────

def empty_snapshot() -> dict[str, Any]:
    return {
        "meta": {"title": None, "identity": None},
        "entities": {},
        "relationships": [],
        "_sequence": 0,
    }


def apply_tool_call(snapshot: dict[str, Any], tool_name: str, params: dict) -> dict[str, Any]:
    """Apply a single tool call to the snapshot. Minimal reducer for eval tracking."""
    seq = snapshot["_sequence"] + 1
    snapshot["_sequence"] = seq

    if tool_name == "mutate_entity":
        action = params.get("action")
        if action == "create":
            eid = params.get("id", f"entity_{seq}")
            snapshot["entities"][eid] = {
                "id": eid,
                "parent": params.get("parent", "root"),
                "display": params.get("display"),
                "props": params.get("props", {}),
                "_removed": False,
                "_created_seq": seq,
                "_updated_seq": seq,
            }
        elif action == "update":
            ref = params.get("ref", "")
            if ref in snapshot["entities"]:
                entity = snapshot["entities"][ref]
                entity["props"].update(params.get("props", {}))
                if params.get("display"):
                    entity["display"] = params["display"]
                entity["_updated_seq"] = seq
        elif action == "remove":
            ref = params.get("ref", "")
            if ref in snapshot["entities"]:
                snapshot["entities"][ref]["_removed"] = True
                snapshot["entities"][ref]["_updated_seq"] = seq
        elif action == "move":
            ref = params.get("ref", "")
            if ref in snapshot["entities"] and "parent" in params:
                snapshot["entities"][ref]["parent"] = params["parent"]
                snapshot["entities"][ref]["_updated_seq"] = seq

    elif tool_name == "set_relationship":
        action = params.get("action")
        if action == "set":
            snapshot["relationships"].append({
                "from": params.get("from", ""),
                "to": params.get("to", ""),
                "type": params.get("type", ""),
                "cardinality": params.get("cardinality", "many_to_one"),
            })
        elif action == "remove":
            snapshot["relationships"] = [
                r for r in snapshot["relationships"]
                if not (r["from"] == params.get("from") and r["to"] == params.get("to") and r["type"] == params.get("type"))
            ]

    return snapshot


# ── Tier Selection ───────────────────────────────────────────────────────────

def pick_tier(turn_spec: dict, turn_index: int, snapshot: dict) -> str:
    """
    Pick the tier to run this turn at.
    
    Uses expected_tier from the spec. In production this would be the
    classifier — here we trust the scenario author's routing decision.
    """
    return turn_spec["expected_tier"]


# ── Tool Call Extraction from Streaming ──────────────────────────────────────

def run_turn(
    tier: str,
    snapshot: dict[str, Any],
    messages: list[dict],
    user_message: str,
) -> dict[str, Any]:
    """
    Run one turn against the Anthropic API with streaming tool use.

    Returns dict with:
        tool_calls: list of {name, input}
        text_blocks: list of text strings (voice output)
        snapshot: updated snapshot after applying tool calls
        usage: token usage
        ttfc_ms: time to first content
        ttc_ms: total time
    """
    system = build_system_prompt(tier, snapshot)
    model = MODELS[tier]
    temperature = TEMPERATURE[tier]

    # Build messages
    msgs = list(messages)
    msgs.append({"role": "user", "content": user_message})

    start = time.time()
    first_content_time = None
    tool_calls = []       # mutations only (for validation/snapshot)
    text_blocks = []      # voice output (text blocks + voice tool calls)
    all_raw_tools = []    # ALL tool calls incl. voice (for conversation history)

    with client.messages.stream(
        model=model,
        max_tokens=8192,
        temperature=temperature,
        system=system,
        messages=msgs,
        tools=TOOLS,
    ) as stream:
        current_tool = None
        current_text = ""

        for event in stream:
            if first_content_time is None and event.type in (
                "content_block_start", "content_block_delta",
            ):
                first_content_time = time.time()

            if event.type == "content_block_start":
                if event.content_block.type == "tool_use":
                    current_tool = {
                        "name": event.content_block.name,
                        "id": event.content_block.id,
                        "input_json": "",
                    }
                elif event.content_block.type == "text":
                    current_text = ""

            elif event.type == "content_block_delta":
                if hasattr(event.delta, "partial_json") and current_tool:
                    current_tool["input_json"] += event.delta.partial_json
                elif hasattr(event.delta, "text"):
                    current_text += event.delta.text

            elif event.type == "content_block_stop":
                if current_tool:
                    try:
                        params = json.loads(current_tool["input_json"])
                    except json.JSONDecodeError:
                        params = {}
                    ts = int((time.time() - start) * 1000)
                    # Voice tool → text block, not a mutation
                    if current_tool["name"] == "voice":
                        all_raw_tools.append({
                            "name": "voice",
                            "id": current_tool["id"],
                            "input": params,
                        })
                        voice_text = params.get("text", "")
                        if voice_text.strip():
                            text_blocks.append({
                                "text": voice_text.strip(),
                                "timestamp_ms": ts,
                            })
                    else:
                        all_raw_tools.append({
                            "name": current_tool["name"],
                            "id": current_tool["id"],
                            "input": params,
                        })
                        tool_calls.append({
                            "name": current_tool["name"],
                            "input": params,
                            "timestamp_ms": ts,
                        })
                        # Apply to snapshot
                        snapshot = apply_tool_call(snapshot, current_tool["name"], params)
                    current_tool = None
                elif current_text.strip():
                    ts = int((time.time() - start) * 1000)
                    text_blocks.append({
                        "text": current_text.strip(),
                        "timestamp_ms": ts,
                    })
                    current_text = ""

    end = time.time()
    msg = stream.get_final_message()

    ttfc_ms = int((first_content_time - start) * 1000) if first_content_time else -1
    ttc_ms = int((end - start) * 1000)

    # ── Forced voice continuation ──
    # If model emitted mutations but no voice, force a continuation call
    # with tool_choice to guarantee voice output.
    has_voice = any(t["name"] == "voice" for t in all_raw_tools)
    if not has_voice and tool_calls:
        print(f"    ⚠ No voice — forcing continuation...")
        # Build continuation messages: original + assistant response + tool results
        cont_msgs = list(msgs)

        # Add assistant's tool-use response
        assistant_content = []
        for raw_tool in all_raw_tools:
            assistant_content.append({
                "type": "tool_use",
                "id": raw_tool["id"],
                "name": raw_tool["name"],
                "input": raw_tool["input"],
            })
        cont_msgs.append({"role": "assistant", "content": assistant_content})

        # Add tool results (API requires a result for each tool_use)
        tool_results = []
        for raw_tool in all_raw_tools:
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": raw_tool["id"],
                "content": "ok",
            })
        cont_msgs.append({"role": "user", "content": tool_results})

        # Force voice call
        voice_start = time.time()
        with client.messages.stream(
            model=model,
            max_tokens=256,
            temperature=temperature,
            system=system,
            messages=cont_msgs,
            tools=TOOLS,
            tool_choice={"type": "tool", "name": "voice"},
        ) as voice_stream:
            voice_tool = None
            for event in voice_stream:
                if event.type == "content_block_start":
                    if event.content_block.type == "tool_use":
                        voice_tool = {"name": event.content_block.name, "id": event.content_block.id, "input_json": ""}
                elif event.type == "content_block_delta":
                    if hasattr(event.delta, "partial_json") and voice_tool:
                        voice_tool["input_json"] += event.delta.partial_json
                elif event.type == "content_block_stop":
                    if voice_tool:
                        try:
                            params = json.loads(voice_tool["input_json"])
                        except json.JSONDecodeError:
                            params = {}
                        ts = int((time.time() - start) * 1000)
                        voice_text = params.get("text", "")
                        if voice_text.strip():
                            text_blocks.append({"text": voice_text.strip(), "timestamp_ms": ts, "_forced": True})
                        all_raw_tools.append({"name": "voice", "id": voice_tool["id"], "input": params})
                        voice_tool = None

        voice_end = time.time()
        ttc_ms = int((voice_end - start) * 1000)  # extend TTC to include voice
        voice_msg = voice_stream.get_final_message()
        print(f"    ✓ Voice forced in {int((voice_end - voice_start)*1000)}ms")

    # Deduplicate text blocks (model may emit same text as both text block and voice tool)
    seen = set()
    deduped = []
    for tb in text_blocks:
        key = tb["text"]
        if key not in seen:
            seen.add(key)
            deduped.append(tb)
    text_blocks = deduped

    # Voice fallback — if model didn't call voice, synthesize from mutations
    if not text_blocks and tool_calls:
        creates = [tc for tc in tool_calls if tc["input"].get("action") == "create"]
        updates = [tc for tc in tool_calls if tc["input"].get("action") == "update"]
        rels = [tc for tc in tool_calls if tc["name"] == "set_relationship"]
        parts = []
        # Find page title if created
        page = next((tc for tc in creates if tc["input"].get("display") == "page"), None)
        if page:
            title = page["input"].get("props", {}).get("title", "Page")
            parts.append(f"{title} — page created.")
        else:
            if creates:
                parts.append(f"{len(creates)} entities created.")
            if updates:
                parts.append(f"{len(updates)} updated.")
            if rels:
                parts.append(f"{len(rels)} relationships set.")
        fallback_text = " ".join(parts) if parts else "Done."
        text_blocks.append({
            "text": fallback_text,
            "timestamp_ms": ttc_ms,
            "_synthetic": True,
        })
        print(f"    ⚠ Voice fallback: \"{fallback_text}\"")

    return {
        "tool_calls": tool_calls,
        "text_blocks": text_blocks,
        "all_raw_tools": all_raw_tools,
        "snapshot": snapshot,
        "system_prompt": system,
        "usage": {
            "input_tokens": msg.usage.input_tokens,
            "output_tokens": msg.usage.output_tokens,
            "cache_read": getattr(msg.usage, "cache_read_input_tokens", 0),
        },
        "ttfc_ms": ttfc_ms,
        "ttc_ms": ttc_ms,
    }


# ── Validation ───────────────────────────────────────────────────────────────

def validate_turn(turn_spec: dict, result: dict, snapshot: dict) -> dict[str, Any]:
    """
    Validate a turn result against the checks dict from scenarios_multiturn.
    
    Checks are intentionally fuzzy — we validate structural correctness, not
    exact entity names. The checks dict uses boolean flags and patterns.
    """
    issues = []
    warnings = []
    checks = turn_spec.get("checks", {})
    tc = result["tool_calls"]
    # text_blocks may be dicts with {text, timestamp_ms} or plain strings
    raw_tb = result["text_blocks"]
    tb = [b["text"] if isinstance(b, dict) else b for b in raw_tb]
    entities = snapshot.get("entities", {})
    active = {k: v for k, v in entities.items() if not v.get("_removed")}

    # ── Structural checks ──

    if checks.get("creates_page"):
        pages = [t for t in tc if t["name"] == "mutate_entity"
                 and t["input"].get("action") == "create"
                 and t["input"].get("display") == "page"]
        if not pages:
            issues.append("Expected page creation, got none")

    if checks.get("has_meta"):
        has_title = any(
            t["name"] == "mutate_entity" and t["input"].get("action") == "create"
            and t["input"].get("display") == "page" and t["input"].get("props", {}).get("title")
            for t in tc
        )
        if not has_title:
            issues.append("Expected page with title in props")

    if checks.get("not_over_scaffolded"):
        sections = [t for t in tc if t["name"] == "mutate_entity"
                    and t["input"].get("action") == "create"
                    and t["input"].get("display") in ("section", "table", "checklist", "list")]
        if len(sections) > 2:
            issues.append(f"Over-scaffolded: {len(sections)} sections from vague input")

    # ── Entity creation checks (pattern: creates_N_type) ──

    if checks.get("creates_guests"):
        guest_creates = [t for t in tc if t["name"] == "mutate_entity"
                        and t["input"].get("action") == "create"
                        and "guest" in str(t["input"]).lower()]
        if not guest_creates:
            issues.append("Expected guest entity creation")

    for key in checks:
        m = re.match(r"creates_(\d+)_(players|guests|items|chores|tasks|cards)", key)
        if m and checks[key]:
            expected_count = int(m.group(1))
            creates = [t for t in tc if t["name"] == "mutate_entity"
                      and t["input"].get("action") == "create"]
            if len(creates) < expected_count:
                issues.append(f"Expected ≥{expected_count} creates, got {len(creates)}")

    if checks.get("batch_creates"):
        creates = [t for t in tc if t["name"] == "mutate_entity"
                  and t["input"].get("action") == "create"]
        min_ents = checks.get("min_entities", 2)
        if len(creates) < min_ents:
            issues.append(f"Batch: expected ≥{min_ents} creates, got {len(creates)}")

    # Named item creation
    for key in ["creates_butter", "creates_chore", "creates_game", "creates_lisa",
                "potato_salad_entity"]:
        if checks.get(key):
            creates = [t for t in tc if t["name"] == "mutate_entity"
                      and t["input"].get("action") == "create"]
            if not creates:
                issues.append(f"Expected entity creation ({key})")

    # ── Update checks ──

    if checks.get("updates_existing"):
        updates = [t for t in tc if t["name"] == "mutate_entity"
                  and t["input"].get("action") == "update"]
        if not updates:
            issues.append("Expected entity update(s), got none")

    if checks.get("updates_details"):
        # Accept either update to existing entity OR create of new details entity
        any_mutation = [t for t in tc if t["name"] == "mutate_entity"
                       and t["input"].get("action") in ("update", "create")]
        if not any_mutation:
            issues.append("Expected details update or creation, got none")

    for key in ["marks_task_done", "marks_done"]:
        if checks.get(key):
            done = [t for t in tc if t["name"] == "mutate_entity"
                   and t["input"].get("action") == "update"
                   and (t["input"].get("props", {}).get("done") is True
                        or t["input"].get("props", {}).get("checked") is True)]
            if not done:
                issues.append("Expected task marked done/checked")

    if checks.get("checks_off_2"):
        done_count = sum(
            1 for t in tc if t["name"] == "mutate_entity"
            and t["input"].get("action") == "update"
            and (t["input"].get("props", {}).get("done") is True
                 or t["input"].get("props", {}).get("checked") is True)
        )
        if done_count < 2:
            issues.append(f"Expected 2 items checked off, got {done_count}")

    if checks.get("unchecks_eggs"):
        unchecks = [t for t in tc if t["name"] == "mutate_entity"
                   and t["input"].get("action") == "update"
                   and (t["input"].get("props", {}).get("done") is False
                        or t["input"].get("props", {}).get("checked") is False)]
        if not unchecks:
            issues.append("Expected item unchecked (state reversal)")

    if checks.get("appends_not_updates"):
        creates = [t for t in tc if t["name"] == "mutate_entity"
                  and t["input"].get("action") == "create"]
        if not creates:
            issues.append("Expected new entities (append), not updates")

    if checks.get("marks_done_or_removes"):
        done_or_rm = [t for t in tc if t["name"] == "mutate_entity"
                     and (t["input"].get("action") == "remove"
                          or (t["input"].get("action") == "update"
                              and (t["input"].get("props", {}).get("done") is True
                                   or t["input"].get("props", {}).get("checked") is True)))]
        if not done_or_rm:
            issues.append("Expected item marked done or removed")

    # Update-specific named checks — accept entity.update OR set_relationship
    for key in ["updates_chicken", "updates_mike_wins", "updates_game_result",
                "updates_maria", "updates_bob_or_drinks", "updates_james_confirmed",
                "updates_james_travel", "updates_dave_declined", "updates_jake",
                "updates_dates"]:
        if checks.get(key):
            # Extract the entity name hint from the check key (e.g., "updates_jake" → "jake")
            name_hint = key.replace("updates_", "").split("_")[0]
            updates = [t for t in tc if t["name"] == "mutate_entity"
                      and t["input"].get("action") == "update"]
            rels = [t for t in tc if t["name"] == "set_relationship"
                   and name_hint in json.dumps(t["input"]).lower()]
            if not updates and not rels:
                issues.append(f"Expected update or relationship ({key})")

    # ── Query / text checks ──

    if checks.get("plain_text"):
        if tc:
            issues.append(f"Expected text-only response (query), got {len(tc)} tool calls")

    if checks.get("no_mutations"):
        mutations = [t for t in tc if t["name"] == "mutate_entity"]
        if mutations:
            issues.append(f"Expected no mutations (query), got {len(mutations)}")

    if checks.get("answers_count"):
        all_text = " ".join(tb).lower()
        if not re.search(r"\d+", all_text):
            issues.append("Query response should contain a number")

    for key in ["trend_summary", "comprehensive_summary", "george_med_analysis",
                "george_peak", "lists_remaining", "answers_standings",
                "calculates_remaining"]:
        if checks.get(key):
            if not tb:
                issues.append(f"Expected text summary ({key})")

    # ── Clarification checks ──

    if checks.get("should_clarify"):
        all_text = " ".join(tb).lower()
        clarify_signals = ["which", "do you mean", "clarify", "which one", "?"]
        if not any(s in all_text for s in clarify_signals):
            issues.append("Expected clarification question, model guessed instead")

    if checks.get("resolves_clarify"):
        if not tc and "?" in " ".join(tb):
            issues.append("Expected resolution, got another question")

    # ── Relationship checks ──

    if checks.get("uses_rel_for_selection"):
        rels = [t for t in tc if t["name"] == "set_relationship"]
        if not rels:
            issues.append("Expected set_relationship for selection")

    if checks.get("sets_attending"):
        attending_rels = [t for t in tc if t["name"] == "set_relationship"
                        and t["input"].get("type") == "attending"]
        if not attending_rels:
            issues.append("Expected attending relationships for game participants")

    if checks.get("linked_to_linda"):
        # Bonus check — relationship or assigned prop
        rels = [t for t in tc if t["name"] == "set_relationship"]
        props_with_linda = [t for t in tc if "linda" in json.dumps(t["input"]).lower()]
        if not rels and not props_with_linda:
            pass  # Bonus, don't fail

    # ── Output content checks ──

    expect_in = checks.get("expect_in_output", [])
    if expect_in:
        all_output = json.dumps(tc) + " ".join(tb)
        for pattern in expect_in:
            alternatives = pattern.split("|")
            if not any(alt.lower() in all_output.lower() for alt in alternatives):
                issues.append(f"Expected '{pattern}' in output")

    if checks.get("names_correct"):
        all_output = json.dumps(tc).lower() + " ".join(tb).lower()
        for name in checks["names_correct"]:
            if name.lower() not in all_output:
                issues.append(f"Expected name '{name}' in output")

    # ── Section/structure creation ──

    for key in ["creates_food_section", "creates_food_items", "creates_budget_table",
                "creates_quote_table", "creates_todo_section", "creates_sections",
                "creates_roster", "adds_schedule_or_fields", "creates_budget_item",
                "adds_budget_items", "creates_tasks"]:
        if checks.get(key):
            any_creates = [t for t in tc if t["name"] == "mutate_entity"
                          and t["input"].get("action") == "create"]
            if not any_creates:
                issues.append(f"Expected entity creation ({key})")

    # ── Boolean checks that just need any tool output ──

    for key in ["has_date", "has_venue", "has_store_note", "compact",
                "assigns_all", "assigns_jamie", "unassigns_chore",
                "tasks_unchecked", "unassigned_items", "marks_prereq_done",
                "budget_ceiling_intact", "captures_note"]:
        if checks.get(key):
            pass  # These are intent checks — hard to validate automatically

    # ── Voice quality (always checked) ──

    # Every turn must produce at least one text block
    if not tb:
        issues.append("No voice output — user gets silence in chat")
    else:
        # Check if voice was synthetic (model didn't call voice tool at all)
        raw_tb = result["text_blocks"]
        if any(isinstance(b, dict) and b.get("_synthetic") for b in raw_tb):
            issues.append("Voice synthetic fallback — model produced no voice at all")
        elif any(isinstance(b, dict) and b.get("_forced") for b in raw_tb):
            # Forced via continuation — not a failure, just a note
            pass  # Don't flag as issue — the system handled it

    for text in tb:
        if len(text) > 200:
            issues.append(f"Voice too long ({len(text)}ch): {text[:60]}...")
        elif len(text) > 150:
            warnings.append(f"Voice long ({len(text)}ch): {text[:60]}...")
        if text.lower().startswith(("i ", "i'", "i've", "let me", "i'll")):
            issues.append(f"First person: {text[:60]}...")
        if any(e in text for e in ["🎉", "🎊", "✨", "👏", "🎶", "❤️", "😊"]):
            issues.append(f"Emoji in voice: {text[:60]}...")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "issues": issues,
    }


# ── Main Runner ──────────────────────────────────────────────────────────────

def run_scenario(scenario: dict, run_dir: Path, max_turn: int | None = None) -> dict[str, Any]:
    """Run a full multi-turn scenario."""
    scenario_name = scenario["name"]

    print(f"\n{'=' * 70}")
    print(f"Scenario: {scenario_name}")
    print(f"  {scenario.get('description', '')[:80]}")
    print(f"  Turns: {len(scenario['turns'])}")
    print(f"{'=' * 70}")

    snapshot = empty_snapshot()
    messages: list[dict] = []
    turn_results = []

    for turn_index, turn_spec in enumerate(scenario["turns"]):
        turn_num = turn_index + 1
        if max_turn and turn_num > max_turn:
            break

        tier = pick_tier(turn_spec, turn_index, snapshot)
        message = turn_spec["message"]
        accept_tiers = turn_spec.get("accept_tiers", [tier])

        print(f"\n  Turn {turn_num} ({tier}): {message[:70]}{'...' if len(message) > 70 else ''}")

        result = run_turn(tier, snapshot, messages, message)

        # ── L3 → L4 escalation ──
        if tier == "L3":
            escalated = False

            # Signal 1: L3 says it needs escalation in voice text
            escalation_signals = ["needs a new section", "new section structure",
                                  "needs structural", "escalat"]
            all_voice = " ".join(
                b["text"] if isinstance(b, dict) else b for b in result["text_blocks"]
            ).lower()
            if any(sig in all_voice for sig in escalation_signals):
                print(f"    ↑ L3 voice-escalated → re-running as L4")
                escalated = True

            # Signal 2: L3 created structural containers (page/section/table/grid)
            # These are L4-only — L3 shouldn't create skeleton entities
            if not escalated:
                STRUCTURAL_DISPLAYS = {"page", "section", "table", "grid"}
                structural_creates = [
                    tc for tc in result["tool_calls"]
                    if tc["name"] == "mutate_entity"
                    and tc["input"].get("action") == "create"
                    and tc["input"].get("display") in STRUCTURAL_DISPLAYS
                ]
                if structural_creates:
                    ids = [tc["input"]["id"] for tc in structural_creates]
                    print(f"    ↑ L3 created structural entities {ids} → re-running as L4")
                    escalated = True

            if escalated:
                # Two-pass escalation:
                # 1. L4 creates structure (sees user message for context)
                print(f"    -> Pass 1: L4 creating structure...")
                l4_result = run_turn("L4", snapshot, messages, message)
                snapshot = l4_result["snapshot"]

                # 2. L3 retries with updated snapshot (structure now exists)
                print(f"    -> Pass 2: L3 retrying with structure...")
                l3_result = run_turn("L3", snapshot, messages, message)
                tier = "L3->L4->L3"

                # Merge: L4's tool_calls first, then L3's
                result = l3_result
                result["tool_calls"] = l4_result["tool_calls"] + l3_result["tool_calls"]
                result["text_blocks"] = l4_result["text_blocks"] + l3_result["text_blocks"]
                result["all_raw_tools"] = l4_result["all_raw_tools"] + l3_result["all_raw_tools"]
                # Usage: sum both passes
                result["usage"] = {
                    "input_tokens": l4_result["usage"]["input_tokens"] + l3_result["usage"]["input_tokens"],
                    "output_tokens": l4_result["usage"]["output_tokens"] + l3_result["usage"]["output_tokens"],
                    "cache_read": l4_result["usage"]["cache_read"] + l3_result["usage"]["cache_read"],
                }
                # Timing: TTFC from L4 pass 1, TTC spans both
                result["ttfc_ms"] = l4_result["ttfc_ms"]
                result["ttc_ms"] = l4_result["ttc_ms"] + l3_result["ttc_ms"]
                # System prompt from L4 (the structural pass)
                result["system_prompt"] = l4_result["system_prompt"]

        snapshot = result["snapshot"]

        # ── Update conversation history ──

        messages.append({"role": "user", "content": message})

        assistant_content = []
        tool_ids = []
        for text in result["text_blocks"]:
            t = text["text"] if isinstance(text, dict) else text
            assistant_content.append({"type": "text", "text": t})
        # Use all_raw_tools (includes voice) for conversation history —
        # API requires tool_result for every tool_use in the response
        for raw_tc in result["all_raw_tools"]:
            tool_ids.append(raw_tc["id"])
            assistant_content.append({
                "type": "tool_use",
                "id": raw_tc["id"],
                "name": raw_tc["name"],
                "input": raw_tc["input"],
            })
        if assistant_content:
            messages.append({"role": "assistant", "content": assistant_content})

            if tool_ids:
                tool_results = []
                for tool_id in tool_ids:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": "ok",
                    })
                messages.append({"role": "user", "content": tool_results})

        # ── Validate ──

        validation = validate_turn(turn_spec, result, snapshot)

        # Report
        tc_summary = {}
        for tc_item in result["tool_calls"]:
            tc_summary[tc_item["name"]] = tc_summary.get(tc_item["name"], 0) + 1

        print(f"    Tools: {tc_summary or '(text only)'}")
        print(f"    Text: {len(result['text_blocks'])} blocks")
        print(f"    TTFC: {result['ttfc_ms']}ms  TTC: {result['ttc_ms']}ms")
        print(f"    Tokens: {result['usage']['input_tokens']:,} in / {result['usage']['output_tokens']:,} out", end="")
        if result["usage"]["cache_read"]:
            pct = round(result["usage"]["cache_read"] / result["usage"]["input_tokens"] * 100)
            print(f"  (cache: {pct}%)")
        else:
            print()
        if result["text_blocks"]:
            for tb_item in result["text_blocks"][:2]:
                tb_text = tb_item["text"] if isinstance(tb_item, dict) else tb_item
                print(f"    Voice: \"{tb_text[:80]}\"")
        if not validation["passed"]:
            print(f"    ⚠ ISSUES ({len(validation['issues'])}):")
            for issue in validation["issues"]:
                print(f"      - {issue}")
        else:
            print(f"    ✓ Passed")
        if validation.get("warnings"):
            for warn in validation["warnings"]:
                print(f"    ⚡ {warn}")

        turn_results.append({
            "turn": turn_num,
            "tier": tier,
            "expected_tier": turn_spec["expected_tier"],
            "accept_tiers": accept_tiers,
            "message": message,
            "tool_calls": result["tool_calls"],
            "text_blocks": result["text_blocks"],
            "system_prompt": result["system_prompt"],
            "usage": result["usage"],
            "ttfc_ms": result["ttfc_ms"],
            "ttc_ms": result["ttc_ms"],
            "validation": validation,
            "checks": turn_spec.get("checks", {}),
            "notes": turn_spec.get("notes", ""),
        })

    # ── Save golden file ──

    golden = {
        "scenario_id": scenario_name,
        "name": scenario_name.replace("_", " ").title(),
        "description": scenario.get("description", ""),
        "timestamp": datetime.now().isoformat(),
        "turns": turn_results,
        "final_snapshot": snapshot,
    }
    golden_path = run_dir / f"{scenario_name}.json"
    with open(golden_path, "w") as f:
        json.dump(golden, f, indent=2, default=str)
    print(f"\n  → {golden_path}")

    # Summary stats
    total_tool_calls = sum(len(tr["tool_calls"]) for tr in turn_results)
    total_text = sum(len(tr["text_blocks"]) for tr in turn_results)
    total_issues = sum(len(tr["validation"]["issues"]) for tr in turn_results)
    all_passed = all(tr["validation"]["passed"] for tr in turn_results)
    entity_count = sum(1 for e in snapshot["entities"].values() if not e.get("_removed"))

    return {
        "scenario_id": scenario_name,
        "name": scenario_name.replace("_", " ").title(),
        "turns": len(turn_results),
        "total_tool_calls": total_tool_calls,
        "total_text_blocks": total_text,
        "total_issues": total_issues,
        "all_passed": all_passed,
        "entity_count": entity_count,
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AIde Multi-Turn Eval v3")
    parser.add_argument("--scenario", type=str, help="Run specific scenario by name")
    parser.add_argument("--turn", type=int, help="Run up to this turn number")
    parser.add_argument("--list", action="store_true", help="List available scenarios")
    args = parser.parse_args()

    if args.list:
        print("Available multi-turn scenarios:\n")
        for s in MULTI_TURN_SCENARIOS:
            turns = len(s["turns"])
            tiers = [t["expected_tier"] for t in s["turns"]]
            tier_counts = {t: tiers.count(t) for t in set(tiers)}
            tier_str = " ".join(f"{t}×{c}" for t, c in sorted(tier_counts.items()))
            print(f"  {s['name']:<25} {turns:>2} turns  [{tier_str}]")
            print(f"    {s.get('description', '')[:72]}")
        return

    scenarios = MULTI_TURN_SCENARIOS
    if args.scenario:
        s = get_scenario(args.scenario)
        if not s:
            print(f"Scenario '{args.scenario}' not found. Use --list to see options.")
            return
        scenarios = [s]

    total_turns = sum(len(s["turns"]) for s in scenarios)
    run_dir = make_run_dir()

    print(f"AIde Multi-Turn Eval — v3")
    print(f"  {len(scenarios)} scenarios, {total_turns} total turns")
    print(f"  Wire: mutate_entity / set_relationship streaming tool use")
    print(f"  Output: {run_dir}")
    print(f"  Started: {datetime.now().isoformat()}")

    results = []
    for scenario in scenarios:
        try:
            result = run_scenario(scenario, run_dir, max_turn=args.turn)
            results.append(result)
        except Exception as e:
            print(f"\n  ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "scenario_id": scenario["name"],
                "name": scenario["name"],
                "error": str(e),
            })

    # Summary table
    print(f"\n\n{'=' * 70}")
    print(f"SUMMARY")
    print(f"{'=' * 70}")
    print(f"{'Scenario':<25} {'Turns':>5} {'Tools':>6} {'Text':>5} {'Ents':>5} {'Issues':>6} {'Pass':>5}")
    print(f"{'-' * 25} {'-' * 5} {'-' * 6} {'-' * 5} {'-' * 5} {'-' * 6} {'-' * 5}")
    for r in results:
        if "error" in r:
            print(f"{r['name']:<25} ERROR: {r['error'][:40]}")
            continue
        status = "✓" if r["all_passed"] else "✗"
        print(
            f"{r['name']:<25} {r['turns']:>5} {r['total_tool_calls']:>6} "
            f"{r['total_text_blocks']:>5} {r['entity_count']:>5} "
            f"{r['total_issues']:>6} {status:>5}"
        )

    # Save report
    report = {
        "run_dir": str(run_dir),
        "timestamp": datetime.now().isoformat(),
        "scenarios_run": len(results),
        "results": results,
    }
    report_path = run_dir / "report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
