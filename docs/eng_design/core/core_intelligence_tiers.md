# 05: Intelligence Tiers

> **Prerequisites:** [Overview](../architecture_overview.md) · [Tool Calls](core_tool_calls.md) (for escalation signals)
> **Next:** [Prompts](core_prompts.md) (the actual system prompts for each tier)

---

## Two Models, Two Jobs

| Tier | Model | Job | When Used | Target Latency | ~Cost/Call |
|------|-------|-----|-----------|---------------|-----------|
| L4 | Opus | First turn + queries | First turn, escalations | <5s | ~$0.10-0.20 |
| L3 | Sonnet | Subsequent mutations | After first turn | <4s complete | ~$0.02-0.05 |

**L4 (Opus) — The Creator & Analyst.** Handles first turn (aide creation) and queries. "Plan my graduation party." "Who hasn't RSVPed?" Emits tool calls for mutations, text for query answers. First turn always routes here for best quality initial structure.

**L3 (Sonnet) — The Updater.** Handles subsequent mutations after the aide exists. "Add Aunt Linda." "Change date to May 22." Emits tool calls. Can escalate to L4 for queries or complex reasoning.

**Why Opus for first turn:** The initial structure defines the aide's shape. Getting it right matters more than speed. Users expect the first creation to take a moment. Subsequent updates need to feel snappy — that's where Sonnet shines.

---

## Routing: Two-Layer Safety Net

### Layer 1: Proactive Classifier

Server-side, rule-based, <10ms. Runs on every message before any LLM call.

**Route to L4 (Opus):**
- **First turn** (no entities exist yet) — always L4 for initial creation
- Message is a question (?, who, what, how many, do we, is there, which)
- Asks for analysis, comparison, recommendation
- Asks about completeness ("do we have enough", "what's missing", "are we ready")

**Route to L3 (Sonnet):**
- Subsequent turns with mutations: updates, additions, structural changes

**Confidence scoring:**
- High (>0.8) → route to classified tier
- Medium (0.5-0.8) → default to L4
- Low (<0.5) → default to L4

Principle: **never show wrong data.** When in doubt, use the smarter model. Latency is recoverable. Broken trust is not.

### Layer 2: LLM Self-Escalation

L3 can emit an escalation signal for queries or complex reasoning:

```json
{"type": "tool_use", "name": "escalate", "input": {"tier": "L4", "reason": "query", "extract": "do we have enough food?"}}
```

Server keeps mutations L3 already applied, sends the query to L4.

### Layer 3: Kernel Validation

Every tool call passes through the kernel. Catches: invalid entity references, type mismatches, constraint violations, structural errors.

If 3+ consecutive operations rejected → cancel stream → retry with more context.

**What the kernel doesn't catch:** Semantically wrong but structurally valid mutations (Linda added to table 3, user said table 5). That's what direct edit is for.

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

## Capability Boundaries

Every user request falls into one of three categories.

### Native — What aide Does Itself

Entity graph mutations, short text (one paragraph max, ~100 words), and queries over state. This is the tool call pipeline.

Examples:
- "Add Aunt Linda, she RSVPed yes" → entity mutation (L3)
- "Plan my graduation party" → schema synthesis (L4)
- "Write a short welcome message" → text entity, max ~100 words (L3)
- "Who hasn't RSVPed?" → query (L4)

### Skills — Bounded Actions Beyond Entity Mutations

Structured outputs through defined capabilities. Each skill is predictable and scoped.

**v1: No skills at launch.** The core entity graph is the product.

**v2 candidates:**
- Generate calendar invite (.ics from ceremony entity)
- Export guest list as CSV
- Draft reminder message for un-RSVPed guests
- Generate shareable summary for group text
- Print-friendly view

Skills are a natural **Pro tier differentiator.** Free gets the entity graph. Pro unlocks skills. More compelling than "more turns."

### Redirects — Things aide Hands Back

When the user requests something outside scope, aide acknowledges the request, suggests where to do it, and tells them how to bring the result back. The tone is helpful, not rejecting.

| User Says | aide Response |
|-----------|--------------|
| "Write a graduation speech for Sophie" | "That's better suited for Claude or Google Docs. Drop a link here and it'll show on the page." |
| "Generate a custom invitation graphic" | "Try Canva or an image generator for that. Paste the image URL here." |
| "Send an email to all guests" | "aide doesn't send emails. Copy the guest list to your email client. A reminder skill is coming soon." |

The redirect must never feel like a wall. The user asked a reasonable thing. aide isn't the right tool for that particular thing.

---

## Scoping Rules

### Image Handling

aide doesn't generate images but accepts URLs. An `image` display type with a `src` prop.

"Add Sophie's graduation photo" → "Drop a link or upload the photo and it'll be added to the page."

No file upload in v1. User pastes a URL. Image renders inline alongside structured data.

### Text Length Boundary

The system prompt enforces a ~100 word limit on `text` entity content. aide can write a welcome message, a short note, a paragraph of description. It cannot write essays, speeches, or long-form content.

This keeps aide positioned as a coordination tool, not a writing tool.

### Each Aide Is a Bounded Context

The entity graph lives inside a single aide. No cross-aide graph. Aides don't automatically link. `@another_aide` is an explicit, user-initiated bridge.

This keeps the graph small, the renderer tractable, and the mental model clear.

### No Spatial Primitives

Grid data (chess boards, Super Bowl squares) modeled as flat entities with coordinate fields (`row`, `col`) + `grid` display hint. State stays simple, renderer gets smarter.

### Display Hints, Not Layout Engines

~9 types in v1. Novel layouts = renderer upgrade, not schema change.

### Voice Reflections Decoupled

The tool call stream is purely structural. Voice is a separate `voice` tool call, optional. Simple updates often don't need one — the page change IS the response. For first creation, voice narrates progress every ~8-10 entity lines.

---

## Cost Profile

50-turn/week free tier with 95/5 distribution:

| Tier | Turns/Week | Cost/Turn | Weekly |
|------|-----------|-----------|--------|
| L3 (Sonnet) | 47 | $0.035 | $1.65 |
| L4 (Opus) | 3 | $0.15 | $0.45 |
| **Total** | | | **~$2.10** |

Monthly worst case: ~$8.40 per free user. Margin is healthy for $10/mo Pro subscribers.
