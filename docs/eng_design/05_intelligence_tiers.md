# 05: Intelligence Tiers

> **Prerequisites:** [00 Overview](00_overview.md) · [02 JSONL Schema](02_jsonl_schema.md) (for escalation signals)
> **Next:** [06 Prompts](06_prompts.md) (the actual system prompts for each tier)

---

## Three Models, Three Jobs

| Tier | Model | Job | % of Turns | Target Latency | ~Cost/Call |
|------|-------|-----|-----------|---------------|-----------|
| L2 | Haiku | Routine mutations | ~85% | <1.5s | ~$0.001 |
| L3 | Sonnet | Schema synthesis | ~10% | <4s complete | ~$0.02-0.05 |
| L4 | Opus | Queries & reasoning | ~5% | <5s | ~$0.10-0.20 |

**L2 (Haiku) — The Compiler.** Clear intent, obvious primitive. "Add Aunt Linda." "Mark potato salad as claimed." "Change date to May 22." Emits JSONL. Speed is everything.

**L3 (Sonnet) — The Architect.** First creation, new sections, structural refactors. "Plan my graduation party." "Add a travel logistics section." Infers entity shapes, picks display hints. Emits JSONL.

**L4 (Opus) — The Analyst.** Queries that reason over the entity graph. "Who hasn't RSVPed?" "Do we have enough food?" Reads full snapshot, produces text answer in chat. Does **not** emit JSONL — no page mutations, just answers.

**Why Opus for queries:** The graduation parent asks "who hasn't RSVPed" and will call those people. A wrong answer has real consequences. The extra latency is invisible — the user is in "thinking mode" when asking questions, not "doing mode."

---

## Routing: Three-Layer Safety Net

### Layer 1: Proactive Classifier

Server-side, rule-based, <10ms. Runs on every message before any LLM call.

**Route to L4 (Opus):**
- Message is a question (?, who, what, how many, do we, is there, which)
- Asks for analysis, comparison, recommendation
- Asks about completeness ("do we have enough", "what's missing", "are we ready")

**Route to L3 (Sonnet):**
- No entities exist yet (first message)
- Requests new structural elements ("add a section", "create a", "set up")
- Entity graph has spatial/indexed structures AND message references position
- Complex conditional logic ("if... then...")
- Image input present
- References entity types that don't exist in the current graph

**Route to L2 (Haiku):**
- Everything else.

**Confidence scoring:**
- High (>0.8) → route to classified tier
- Medium (0.5-0.8) → default to L3
- Low (<0.5) → default to L3

Principle: **never show wrong data.** When in doubt, use the smarter model. Latency is recoverable. Broken trust is not.

### Layer 2: LLM Self-Escalation

L2 can emit an escalation signal mid-stream:

```json
{"t":"escalate","tier":"L3","reason":"unknown_entity_shape","extract":"add a seating chart with 5 tables"}
```

Server keeps mutations L2 already applied, sends the rest to L3. Escalation reasons: `unknown_entity_shape`, `ambiguous_intent`, `complex_conditional`, `structural_change`.

### Layer 3: Reducer Validation

Every JSONL line passes through the reducer. Catches: invalid entity references, type mismatches, constraint violations, structural errors.

If 3+ consecutive lines rejected → cancel stream → escalate entire message to next tier.

**What the reducer doesn't catch:** Semantically wrong but structurally valid mutations (Linda added to table 3, user said table 5). That's what the proactive classifier and direct edit are for.

---

## Multi-Intent Messages

Users don't speak in single intents:

> "Aunt Linda RSVPed yes, she's bringing potato salad, Uncle Steve is driving her, and do we have enough food for everyone?"

Three mutations and a query. The model handles what it can and escalates the rest:

```jsonl
{"t":"entity.update","ref":"guest_linda","p":{"rsvp":"yes"}}
{"t":"entity.create","id":"food_potato_salad","parent":"food","p":{"item":"Potato Salad","who":"Aunt Linda"}}
{"t":"rel.set","from":"guest_steve","to":"guest_linda","type":"driving"}
{"t":"escalate","tier":"L4","reason":"query","extract":"do we have enough food for everyone?"}
```

**What the user sees:** Page updates fast (mutations, <1s). Query answer appears in chat a few seconds later (L4 async).

**Mixed mutation tiers:** If any part of the message requires schema synthesis, route the whole thing to L3. L3 can handle simple mutations too. One L3 call > L2 failure + L3 retry.

**Ordering guarantee:** Mutations applied in JSONL order. Escalated queries run against post-mutation snapshot.

---

## Known Model Weaknesses

Haiku patterns proactively routed to a higher tier:

| Pattern | Example | Route To |
|---------|---------|----------|
| Positional indexing | "the third item", "row 2 col 3" | L3 |
| Spatial reasoning | "swap table 3 and table 5" | L3 |
| Arithmetic over entities | "what's the total budget?" | L4 |
| Negation queries | "who has NOT RSVPed?" | L4 |
| Conditional bulk updates | "everyone arriving Friday gets..." | L3 |
| Cross-reference reasoning | "bringing food but hasn't RSVPed?" | L4 |

This table grows as the eval suite finds new patterns.

---

## The Full Message Lifecycle

```
1. User sends message

2. Proactive classifier (<10ms)
   → inspects message text + entity graph shape
   → assigns tier with confidence score

3. LLM call (selected tier)
   → streams JSONL to server
   → each line: parse → reduce → push delta to client
   → escalation lines: queue for async dispatch
   → rejected lines: skip, escalate if 3+ consecutive

4. Stream complete
   → mutations saved to R2
   → escalated intents dispatched to higher tier

5. User sees
   → page updates progressively (fast)
   → query answers in chat (async)
   → direct edit available on all fields (instant)
```

---

## Cost Profile

50-turn/week free tier with 85/10/5 distribution:

| Tier | Turns/Week | Cost/Turn | Weekly |
|------|-----------|-----------|--------|
| L2 (Haiku) | 42 | $0.001 | $0.042 |
| L3 (Sonnet) | 5 | $0.035 | $0.175 |
| L4 (Opus) | 3 | $0.15 | $0.450 |
| **Total** | | | **~$0.67** |

Monthly worst case: ~$2.68 per free user. Margin is healthy for $10/mo Pro subscribers.
