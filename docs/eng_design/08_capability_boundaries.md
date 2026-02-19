# 08: Capability Boundaries

> **Prerequisites:** [00 Overview](00_overview.md)
> **Related:** [06 Prompts](06_prompts.md) (boundaries enforced in system prompts)

---

## Three Buckets

Every user request falls into one of three categories.

### Native — What AIde Does Itself

Entity graph mutations, short text (one paragraph max, ~100 words), and queries over state. This is the JSONL pipeline.

Examples:
- "Add Aunt Linda, she RSVPed yes" → entity mutation (L2)
- "Plan my graduation party" → schema synthesis (L3)
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

### Redirects — Things AIde Hands Back

When the user requests something outside scope, AIde acknowledges the request, suggests where to do it, and tells them how to bring the result back. The tone is helpful, not rejecting.

| User Says | AIde Response |
|-----------|--------------|
| "Write a graduation speech for Sophie" | "That's better suited for Claude or Google Docs. Drop a link here and it'll show on the page." |
| "Generate a custom invitation graphic" | "Try Canva or an image generator for that. Paste the image URL here." |
| "Send an email to all guests" | "AIde doesn't send emails. Copy the guest list to your email client. A reminder skill is coming soon." |

The redirect must never feel like a wall. The user asked a reasonable thing. AIde isn't the right tool for that particular thing.

---

## Image Handling

AIde doesn't generate images but accepts URLs. An `image` display type with a `src` prop.

"Add Sophie's graduation photo" → "Drop a link or upload the photo and it'll be added to the page."

No file upload in v1. User pastes a URL. Image renders inline alongside structured data.

---

## Text Length Boundary

The system prompt enforces a ~100 word limit on `text` entity content. AIde can write a welcome message, a short note, a paragraph of description. It cannot write essays, speeches, or long-form content.

This keeps AIde positioned as a coordination tool, not a writing tool.

---

## Scoping Rules

### Each Aide Is a Bounded Context

The entity graph lives inside a single aide. No cross-aide graph. Aides don't automatically link. `@another_aide` is an explicit, user-initiated bridge.

This keeps the graph small, the renderer tractable, and the mental model clear.

### No Spatial Primitives

Grid data (chess boards, Super Bowl squares) modeled as flat entities with coordinate fields (`row`, `col`) + `grid` display hint. State stays simple, renderer gets smarter.

### Display Hints, Not Layout Engines

~9 types in v1. Novel layouts = renderer upgrade, not schema change.

### Voice Reflections Decoupled

The JSONL stream is purely structural. Voice is a separate `voice` signal line, optional. Most L2 updates don't need one — the page change IS the response. For L3 creation, voice narrates progress every ~8-10 lines.
