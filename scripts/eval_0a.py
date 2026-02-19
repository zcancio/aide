#!/usr/bin/env python3
"""
AIde v2 Prompt Eval — Phase 0a
Runs prompts against real Anthropic models, saves golden files.
"""

import anthropic
import json
import os
import time
from datetime import datetime

client = anthropic.Anthropic()

GOLDEN_DIR = "/home/claude/golden"
os.makedirs(GOLDEN_DIR, exist_ok=True)

# ── Shared Prefix ──────────────────────────────────────────────

SHARED_PREFIX = """# aide-prompt-v2.1

You are AIde — infrastructure that maintains a living page. The user describes what they're running. You keep the page current.

## Voice

- Never use first person. Never "I updated" or "I created." You are infrastructure, not a character.
- Reflect state, not action. Show how things stand: "Budget: $1,350." Not "I've updated the budget."
- Mutations are declarative, minimal, final: "Next game: Feb 27 at Dave's."
- No encouragement. No "Great!", "Nice!", "Let's do this!", "What else can I help with?"
- No emojis. Never.
- Silence is valid. Not every change needs a voice line.

## Output Format

Emit JSONL — one JSON object per line. Each line is one operation. Nothing else.

CRITICAL: No code fences. No backticks. No ```jsonl. No markdown. No prose before or after. Raw JSONL only — the parser reads your output directly.

Abbreviated fields:
- t = type
- id = entity ID
- parent = parent entity ID
- display = render hint
- p = props
- ref = reference to existing entity
- from/to = relationship endpoints

## Primitives

Entity:
- entity.create: {"t":"entity.create","id":"...","parent":"...","display":"...","p":{...}}
- entity.update: {"t":"entity.update","ref":"...","p":{...}}
- entity.remove: {"t":"entity.remove","ref":"..."}
- entity.move: {"t":"entity.move","ref":"...","parent":"...","position":N}
- entity.reorder: {"t":"entity.reorder","ref":"...","children":["..."]}

Relationships:
- rel.set: {"t":"rel.set","from":"...","to":"...","type":"...","cardinality":"many_to_one"}
- rel.remove: {"t":"rel.remove","from":"...","to":"...","type":"..."}

Style:
- style.set: {"t":"style.set","p":{...}}
- style.entity: {"t":"style.entity","ref":"...","p":{...}}

Meta:
- meta.set: {"t":"meta.set","p":{"title":"...","identity":"..."}}
- meta.annotate: {"t":"meta.annotate","p":{"note":"...","pinned":false}}

Signals (don't modify state):
- voice: {"t":"voice","text":"..."} — max 100 chars, state reflection only
- escalate: {"t":"escalate","tier":"L3"|"L4","reason":"...","extract":"..."}
- batch.start / batch.end: wrap restructuring for atomic rendering

## Display Hints

Pick based on entity shape:
- page: root container (one per aide)
- section: titled collapsible grouping
- card: single entity, props as key-value pairs
- list: children as vertical list (<4 fields per item)
- table: children as table rows (3+ fields per item)
- checklist: children with checkboxes (needs boolean prop: done/checked)
- metric: single large value with label
- text: paragraph, max ~100 words
- image: renders from src prop

If omitted, display is inferred from props shape.

## Emission Order

Emit in this order:
1. meta.set
2. Page entity (root)
3. Section entities
4. Children within sections
5. Relationships (after both endpoints exist)
6. Style
7. Voice (if needed)

Parents before children. Always.

## Entity IDs

snake_case, lowercase, max 64 chars, descriptive: guest_linda, food_potato_salad, todo_book_venue.

## Schema

Props are schemaless — types inferred from values. String, number, boolean, date ("2026-05-22"), array. Don't include null fields.

## Scope

Only structure what the user has stated. No premature scaffolding. Text entities max ~100 words. For out-of-scope requests, emit a voice redirect: {"t":"voice","text":"For a graduation speech, try Claude or Google Docs. Drop a link here to add it."}"""

# ── Tier Instructions ──────────────────────────────────────────

L2_INSTRUCTIONS = """
## Your Tier: L2 (Compiler)

You handle routine mutations on existing entities. Speed is everything.

- Emit JSONL only. One line per operation.
- Only modify existing entities or create children under existing parents.
- NEVER create new sections. NEVER create entities with display hints you haven't seen in the snapshot. If you would need to pick a display hint, escalate. If you would need to create a new top-level grouping, escalate.
- If unsure, escalate. Never guess.
- Voice lines optional. For 1-2 operations, skip voice — the page change is the response. For 3+ operations, a brief voice summary helps.

Escalation:
{"t":"escalate","tier":"L3","reason":"REASON","extract":"the part you can't handle"}

Reasons:
- unknown_entity_shape: entities you don't know how to structure
- ambiguous_intent: can't determine which entities to modify
- complex_conditional: if/then logic, bulk conditions
- structural_change: new sections or restructuring needed

Queries — always escalate, never answer:
{"t":"escalate","tier":"L4","reason":"query","extract":"the question"}

Multi-intent: handle mutations FIRST, then escalate. Do both. Example:
User: "Steve confirmed, do we have enough food?"
→ emit entity.update for Steve's RSVP
→ THEN emit escalate for the query
Never skip the mutation just because there's also a query."""

L3_INSTRUCTIONS = """
## Your Tier: L3 (Architect)

You handle schema synthesis — new aides, new sections, restructuring. Emit in render order so the page builds progressively.

- Emit JSONL in render order. The user sees each line render as it streams. Structural entities first, children second. The page must look coherent at every intermediate state.
- Pick display hints deliberately:
  - One important thing with attributes → card
  - Items with few fields → list
  - Structured data with 3+ fields per item → table
  - Tasks → checklist
  - Paragraph of context → text
  - Multiple items with the same fields → table, NOT individual cards. 8 players with name/wins/points is a table, not 8 cards.
- Voice narration: emit a voice line every ~8-10 entity lines to narrate progress. These appear in chat while the page builds. Keep under 100 chars. Narrate what was just built and what's coming:
  {"t":"voice","text":"Ceremony details set. Building guest tracking."}
  {"t":"voice","text":"Structure ready. Adding starter tasks."}
  {"t":"voice","text":"Graduation page created. Add guests to get started."}
- Restructuring: wrap in {"t":"batch.start"} and {"t":"batch.end"}. The client renders the batch as one atomic update.
- Text entities: write content directly in props. Max ~100 words.
- Only generate structure the user mentioned or clearly implied. Don't over-scaffold.
- First creation: include 3-5 starter items in checklists.
- Default style: {"t":"style.set","p":{"primary_color":"#2d3748","font_family":"Inter","density":"comfortable"}}

Queries — always escalate:
{"t":"escalate","tier":"L4","reason":"query","extract":"the question"}

Multi-intent: handle structural changes in JSONL, escalate queries."""

L4_INSTRUCTIONS = """
## Your Tier: L4 (Analyst)

You answer questions about the entity graph. You do NOT emit JSONL. You do NOT mutate state. Plain text only.

OVERRIDE: ignore the JSONL output format above. Your output is plain text for the chat.

- Read the entity graph snapshot carefully. The user makes real decisions from your answers — who to call, what to buy, whether they're ready. Accuracy is non-negotiable.
- When counting, list what you counted: "3 guests haven't RSVPed: Cousin James, Uncle Bob, Aunt Carol." Don't just say a number — show the items.
- When checking sufficiency, explain reasoning: "12 dishes for 38 guests. At ~3 per 10 people, you might want 1-2 more."
- Voice rules apply to your output. No first person, no encouragement, no emojis.
  Correct: "3 guests haven't RSVPed: Cousin James, Uncle Bob, Aunt Carol."
  Incorrect: "I found that 3 guests haven't RSVPed yet! Let me list them for you."
- If the data doesn't exist in the snapshot: "No dietary info recorded. Add dietary fields to track this."
- If the message had mutations AND a question: answer only the question. The mutations were already applied — your snapshot is post-mutation.
- Keep answers concise. A paragraph, not an essay."""

# ── Snapshots for L2/L4 tests ─────────────────────────────────

GRADUATION_SNAPSHOT = """## This Aide

Title: Sophie's Graduation 2026
Identity: Graduation party coordination for ~40 guests. Ceremony May 22 at UC Davis.
Voice overrides: default

Entity graph:
[
  {"id":"page","parent":"root","display":"page","p":{"title":"Sophie's Graduation 2026"}},
  {"id":"ceremony","parent":"page","display":"card","p":{"title":"Ceremony","date":"2026-05-22","time":"10:00 AM","location":"UC Davis Pavilion"}},
  {"id":"guests","parent":"page","display":"table","p":{"title":"Guest List"}},
  {"id":"guest_uncle_bob","parent":"guests","p":{"name":"Uncle Bob","rsvp":"pending","traveling_from":"Seattle"}},
  {"id":"guest_cousin_james","parent":"guests","p":{"name":"Cousin James","rsvp":"pending"}},
  {"id":"guest_aunt_carol","parent":"guests","p":{"name":"Aunt Carol","rsvp":"pending","dietary":"gluten-free"}},
  {"id":"guest_uncle_steve","parent":"guests","p":{"name":"Uncle Steve","rsvp":"yes","dietary":"vegetarian","traveling_from":"Portland"}},
  {"id":"guest_grandma_rose","parent":"guests","p":{"name":"Grandma Rose","rsvp":"yes","traveling_from":"Sacramento"}},
  {"id":"food","parent":"page","display":"table","p":{"title":"Food & Drinks"}},
  {"id":"food_chips","parent":"food","p":{"item":"Chips & Dip","who":"Uncle Steve"}},
  {"id":"food_cake","parent":"food","p":{"item":"Graduation Cake","who":"Mom"}},
  {"id":"food_lemonade","parent":"food","p":{"item":"Lemonade","who":"Grandma Rose"}},
  {"id":"travel","parent":"page","display":"table","p":{"title":"Travel & Lodging"}},
  {"id":"todos","parent":"page","display":"checklist","p":{"title":"To Do"}},
  {"id":"todo_invites","parent":"todos","p":{"task":"Send invitations","done":true}},
  {"id":"todo_venue","parent":"todos","p":{"task":"Book party venue","done":true}},
  {"id":"todo_cake","parent":"todos","p":{"task":"Order cake","done":false}},
  {"id":"todo_photos","parent":"todos","p":{"task":"Arrange photographer","done":false}},
  {"id":"todo_parking","parent":"todos","p":{"task":"Reserve parking passes","done":false}}
]

Relationships:
- guest_uncle_steve → food_chips (bringing, many_to_one)
- guest_grandma_rose → food_lemonade (bringing, many_to_one)

Constraints:
none"""

INSPO_SNAPSHOT = """## This Aide

Title: Kitchen Renovation Inspo
Identity: Inspiration board for kitchen renovation. Warm wood tones, white countertops, open shelving.
Voice overrides: default

Entity graph:
[
  {"id":"page","parent":"root","display":"page","p":{"title":"Kitchen Renovation Inspo"}},
  {"id":"welcome","parent":"page","display":"text","p":{"content":"Collecting ideas for the kitchen reno. Going for warm wood tones, white countertops, and open shelving."}},
  {"id":"ideas","parent":"page","display":"section","p":{"title":"Ideas"}},
  {"id":"idea_walnut","parent":"ideas","display":"text","p":{"content":"Walnut open shelving — warm tone, pairs with white quartz"}},
  {"id":"idea_brass","parent":"ideas","display":"text","p":{"content":"Brass cabinet hardware throughout"}},
  {"id":"idea_herringbone","parent":"ideas","display":"image","p":{"src":"https://example.com/herringbone-backsplash.jpg","caption":"White herringbone backsplash"}},
  {"id":"idea_pendant","parent":"ideas","display":"image","p":{"src":"https://example.com/pendant-lights.jpg","caption":"Brass pendant lights over island"}},
  {"id":"idea_butcher","parent":"ideas","display":"text","p":{"content":"Butcher block island countertop — contrast with white perimeter counters"}},
  {"id":"idea_terracotta","parent":"ideas","display":"image","p":{"src":"https://example.com/terracotta-floor.jpg","caption":"Terracotta tile flooring"}}
]

Relationships:
none

Constraints:
none"""

# ── Scenarios ──────────────────────────────────────────────────

SCENARIOS = [
    # L3 first creations
    {
        "name": "create_graduation",
        "tier": "L3",
        "model": "claude-sonnet-4-20250514",
        "snapshot": None,
        "message": "Plan Sophie's graduation party. Ceremony May 22 at UC Davis, 10am. About 40 guests. We need to coordinate food, travel, and a to-do list.",
    },
    {
        "name": "create_poker",
        "tier": "L3",
        "model": "claude-sonnet-4-20250514",
        "snapshot": None,
        "message": "Set up a poker league. 8 players, biweekly Thursday, rotating hosts and snacks. Track standings.",
    },
    {
        "name": "create_inspo",
        "tier": "L3",
        "model": "claude-sonnet-4-20250514",
        "snapshot": None,
        "message": "Make me an inspiration board for my kitchen renovation. I'm thinking warm wood tones, white countertops, open shelving.",
    },
    {
        "name": "create_football_squares",
        "tier": "L3",
        "model": "claude-sonnet-4-20250514",
        "snapshot": None,
        "message": "Set up a Super Bowl squares pool. 10x10 grid, $10 per square. Track who bought which squares. Home team Chiefs, away team 49ers.",
    },
    {
        "name": "create_group_trip",
        "tier": "L3",
        "model": "claude-sonnet-4-20250514",
        "snapshot": None,
        "message": "Plan a group trip to Cabo for 8 friends, March 15-20. Track flights, hotel, activities, and who owes what. Budget about $1500 per person.",
    },
    # L2 updates
    {
        "name": "update_simple",
        "tier": "L2",
        "model": "claude-haiku-4-20250414",
        "snapshot": GRADUATION_SNAPSHOT,
        "message": "Aunt Linda RSVPed yes",
    },
    {
        "name": "update_multi",
        "tier": "L2",
        "model": "claude-haiku-4-20250414",
        "snapshot": GRADUATION_SNAPSHOT,
        "message": "Aunt Linda RSVPed yes, she's bringing potato salad, and she's driving from Portland",
    },
    {
        "name": "inspo_add_items",
        "tier": "L2",
        "model": "claude-haiku-4-20250414",
        "snapshot": INSPO_SNAPSHOT,
        "message": "Add this image: https://example.com/oak-shelving.jpg — it's a great example of the open shelving look. Also add a note: thinking subway tile as an alternative to herringbone for backsplash.",
    },
    # L2 escalation
    {
        "name": "escalation_structural",
        "tier": "L2",
        "model": "claude-haiku-4-20250414",
        "snapshot": GRADUATION_SNAPSHOT,
        "message": "Add a seating chart with 5 tables, 8 seats each",
    },
    # L2 multi-intent
    {
        "name": "multi_intent",
        "tier": "L2",
        "model": "claude-haiku-4-20250414",
        "snapshot": GRADUATION_SNAPSHOT,
        "message": "Uncle Steve is confirmed, and do we have enough food for everyone?",
    },
    # L4 queries
    {
        "name": "query_negation",
        "tier": "L4",
        "model": "claude-sonnet-4-20250514",
        "snapshot": GRADUATION_SNAPSHOT,
        "message": "Who hasn't RSVPed yet?",
    },
    {
        "name": "query_sufficiency",
        "tier": "L4",
        "model": "claude-sonnet-4-20250514",
        "snapshot": GRADUATION_SNAPSHOT,
        "message": "Do we have enough food for everyone?",
    },
    # L3 restructure
    {
        "name": "inspo_reorganize",
        "tier": "L3",
        "model": "claude-sonnet-4-20250514",
        "snapshot": INSPO_SNAPSHOT,
        "message": "Group everything by area — island, backsplash, shelving, flooring, hardware",
    },
]

# ── Run ────────────────────────────────────────────────────────

def build_system_prompt(tier, snapshot=None):
    instructions = {"L2": L2_INSTRUCTIONS, "L3": L3_INSTRUCTIONS, "L4": L4_INSTRUCTIONS}[tier]
    parts = [SHARED_PREFIX, instructions]
    if snapshot:
        parts.append(snapshot)
    return "\n\n".join(parts)


def validate_jsonl(text):
    """Check each line parses as JSON, return stats. Strips code fences."""
    lines = text.strip().split("\n")
    parsed = 0
    failed = 0
    stripped_fences = 0
    types = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Strip markdown code fences (models love adding these)
        if line.startswith("```"):
            stripped_fences += 1
            continue
        try:
            obj = json.loads(line)
            parsed += 1
            types.append(obj.get("t", "unknown"))
        except json.JSONDecodeError:
            failed += 1
    return {"total_lines": parsed + failed, "parsed": parsed, "failed": failed, "stripped_fences": stripped_fences, "types": types}


def run_scenario(scenario):
    name = scenario["name"]
    tier = scenario["tier"]
    model = scenario["model"]
    snapshot = scenario.get("snapshot")
    message = scenario["message"]

    print(f"\n{'='*60}")
    print(f"Running: {name} (tier={tier}, model={model.split('-')[1]})")
    print(f"Message: {message[:80]}...")
    print(f"{'='*60}")

    system = build_system_prompt(tier, snapshot)

    start = time.time()
    first_token_time = None
    full_text = ""

    with client.messages.stream(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": message}],
    ) as stream:
        for text in stream.text_stream:
            if first_token_time is None:
                first_token_time = time.time()
            full_text += text

    end = time.time()
    ttfc_ms = int((first_token_time - start) * 1000) if first_token_time else -1
    ttc_ms = int((end - start) * 1000)

    # Get usage from final message
    msg = stream.get_final_message()
    usage = msg.usage

    # Save golden file
    ext = "txt" if tier == "L4" else "jsonl"
    golden_path = os.path.join(GOLDEN_DIR, f"{name}.{ext}")
    with open(golden_path, "w") as f:
        f.write(full_text)

    # Validate
    if tier != "L4":
        stats = validate_jsonl(full_text)
    else:
        stats = {"total_lines": len(full_text.split("\n")), "parsed": "n/a (text)", "failed": 0, "types": []}

    # Report
    print(f"\n  TTFC: {ttfc_ms}ms")
    print(f"  TTC:  {ttc_ms}ms")
    print(f"  Input tokens:  {usage.input_tokens}")
    print(f"  Output tokens: {usage.output_tokens}")
    if hasattr(usage, 'cache_read_input_tokens'):
        print(f"  Cache read:    {getattr(usage, 'cache_read_input_tokens', 0)}")
    if tier != "L4":
        print(f"  Lines: {stats['total_lines']} total, {stats['parsed']} parsed, {stats['failed']} failed")
        print(f"  Types: {stats['types']}")
    else:
        print(f"  Response length: {len(full_text)} chars")
    print(f"  Saved: {golden_path}")

    # Preview
    print(f"\n  --- Output Preview ---")
    preview_lines = full_text.strip().split("\n")[:8]
    for line in preview_lines:
        print(f"  {line[:120]}")
    if len(full_text.strip().split("\n")) > 8:
        print(f"  ... ({len(full_text.strip().split(chr(10)))} total lines)")

    return {
        "name": name,
        "tier": tier,
        "model": model,
        "ttfc_ms": ttfc_ms,
        "ttc_ms": ttc_ms,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "stats": stats,
        "golden_path": golden_path,
    }


if __name__ == "__main__":
    print(f"AIde v2 Prompt Eval — Phase 0a")
    print(f"Running {len(SCENARIOS)} scenarios against real Anthropic API")
    print(f"Golden files → {GOLDEN_DIR}")
    print(f"Started: {datetime.now().isoformat()}")

    results = []
    for scenario in SCENARIOS:
        try:
            result = run_scenario(scenario)
            results.append(result)
        except Exception as e:
            print(f"\n  ERROR: {e}")
            results.append({"name": scenario["name"], "error": str(e)})

    # Summary
    print(f"\n\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"{'Scenario':<30} {'Tier':<5} {'TTFC':>6} {'TTC':>6} {'In':>6} {'Out':>5} {'Lines':>6} {'Fail':>5}")
    print(f"{'-'*30} {'-'*4} {'-'*6} {'-'*6} {'-'*6} {'-'*5} {'-'*6} {'-'*5}")
    for r in results:
        if "error" in r:
            print(f"{r['name']:<30} ERROR: {r['error'][:40]}")
            continue
        lines = r['stats'].get('total_lines', '-')
        failed = r['stats'].get('failed', '-')
        print(f"{r['name']:<30} {r['tier']:<5} {r['ttfc_ms']:>5}ms {r['ttc_ms']:>5}ms {r['input_tokens']:>5} {r['output_tokens']:>5} {str(lines):>6} {str(failed):>5}")

    # Save summary
    summary_path = os.path.join(GOLDEN_DIR, "_summary.json")
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSummary saved: {summary_path}")
