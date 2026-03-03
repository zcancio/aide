# 05: Intelligence Tiers

> **Prerequisites:** [00 Overview](00_overview.md) · [02 Tool Calls](02_tool_calls.md) (for escalation signals)
> **Next:** [06 Prompts](06_prompts.md) (the actual system prompts for each tier)

---

## Two Models, Two Jobs

| Tier | Model | Job | % of Turns | Target Latency | ~Cost/Call |
|------|-------|-----|-----------|---------------|-----------|
| L3 | Sonnet | Mutations + creation | ~95% | <4s complete | ~$0.02-0.05 |
| L4 | Opus | Queries & reasoning | ~5% | <5s | ~$0.10-0.20 |

**L3 (Sonnet) — The Architect.** Handles all mutations: first creation, new sections, structural refactors, and routine updates. "Plan my graduation party." "Add Aunt Linda." "Change date to May 22." Emits tool calls. Handles both creation and updates.

**L4 (Opus) — The Analyst.** Queries that reason over the entity graph. "Who hasn't RSVPed?" "Do we have enough food?" Reads full snapshot, produces text answer in chat. Does **not** emit tool calls — no page mutations, just answers.

**Why Opus for queries:** The graduation parent asks "who hasn't RSVPed" and will call those people. A wrong answer has real consequences. The extra latency is invisible — the user is in "thinking mode" when asking questions, not "doing mode."

---

## Routing: Two-Layer Safety Net

### Layer 1: Proactive Classifier

Server-side, rule-based, <10ms. Runs on every message before any LLM call.

**Route to L4 (Opus):**
- Message is a question (?, who, what, how many, do we, is there, which)
- Asks for analysis, comparison, recommendation
- Asks about completeness ("do we have enough", "what's missing", "are we ready")

**Route to L3 (Sonnet):**
- Everything else: creation, mutations, updates, structural changes

**Confidence scoring:**
- High (>0.8) → route to classified tier
- Medium (0.5-0.8) → default to L3
- Low (<0.5) → default to L3

Principle: **never show wrong data.** When in doubt, use the smarter model. Latency is recoverable. Broken trust is not.

### Layer 2: LLM Self-Escalation

L3 can emit an escalation signal for queries:

```json
{"type": "tool_use", "name": "escalate", "input": {"tier": "L4", "reason": "query", "extract": "do we have enough food?"}}
```

Server keeps mutations L3 already applied, sends the query to L4.

### Layer 3: Reducer Validation

Every tool call passes through the reducer. Catches: invalid entity references, type mismatches, constraint violations, structural errors.

If 3+ consecutive operations rejected → cancel stream → retry with more context.

**What the reducer doesn't catch:** Semantically wrong but structurally valid mutations (Linda added to table 3, user said table 5). That's what direct edit is for.

---

## Multi-Intent Messages

Users don't speak in single intents:

> "Aunt Linda RSVPed yes, she's bringing potato salad, Uncle Steve is driving her, and do we have enough food for everyone?"

Three mutations and a query. L3 handles what it can and escalates the rest:

```
[mutate_entity tool call: update guest_linda with rsvp=yes]
[mutate_entity tool call: create food_potato_salad under food]
[set_relationship tool call: guest_steve driving guest_linda]
[escalate tool call: tier=L4, query about food]
```

**What the user sees:** Page updates fast (mutations, <2s). Query answer appears in chat a few seconds later (L4 async).

**Ordering guarantee:** Mutations applied in order. Escalated queries run against post-mutation snapshot.

---

## Known Model Weaknesses

Patterns proactively routed to L4:

| Pattern | Example | Route To |
|---------|---------|----------|
| Arithmetic over entities | "what's the total budget?" | L4 |
| Negation queries | "who has NOT RSVPed?" | L4 |
| Cross-reference reasoning | "bringing food but hasn't RSVPed?" | L4 |
| Comparison questions | "who's contributing the most?" | L4 |

This table grows as the eval suite finds new patterns.

---

## The Full Message Lifecycle

```
1. User sends message

2. Proactive classifier (<10ms)
   → inspects message text + entity graph shape
   → assigns tier with confidence score

3. LLM call (selected tier)
   → streams tool calls to server
   → each tool call: reduce → push delta to client
   → escalation tool calls: queue for async dispatch
   → rejected operations: skip, retry if 3+ consecutive

4. Stream complete
   → mutations saved to PostgreSQL
   → escalated intents dispatched to L4

5. User sees
   → page updates progressively (fast)
   → query answers in chat (async)
   → direct edit available on all fields (instant)
```

---

## Cost Profile

50-turn/week free tier with 95/5 distribution:

| Tier | Turns/Week | Cost/Turn | Weekly |
|------|-----------|-----------|--------|
| L3 (Sonnet) | 47 | $0.035 | $1.65 |
| L4 (Opus) | 3 | $0.15 | $0.45 |
| **Total** | | | **~$2.10** |

Monthly worst case: ~$8.40 per free user. Margin is healthy for $10/mo Pro subscribers.
