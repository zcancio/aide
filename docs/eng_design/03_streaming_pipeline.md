# 03: Streaming Pipeline

> **Prerequisites:** [01 Data Model](01_data_model.md) · [02 JSONL Schema](02_jsonl_schema.md)
> **Next:** [04 Display Components](04_display_components.md) (what the client does with each delta)

---

## End-to-End Flow

```
User sends message
  → Classifier picks tier (L2/L3/L4)        [<10ms, see 05]
  → LLM streams JSONL
  → Server buffers until newline
  → Server parses JSON line
  → Reducer applies it
    → accepted: push delta to client via WebSocket
    → rejected: skip, log, continue
  → Client patches entity graph in React state
  → React re-renders affected components
  → User sees page update progressively
```

---

## Server-Side Parsing

The parser is simple: buffer bytes until `\n`, attempt `JSON.parse()`, fire through reducer, push delta.

```
LLM stream → buffer until \n → JSON.parse()
  → expand abbreviated fields (t→type, p→props, etc.)
  → wrap in event envelope (sequence, timestamp, actor, source)
  → reducer(snapshot, event)
    → applied: save to event log, push delta to client
    → rejected: log rejection, skip, check consecutive failure count
  → if 3+ consecutive rejections: cancel stream, escalate to next tier
```

**Batch handling:** When `batch.start` is received, the server accumulates deltas in a buffer instead of pushing them. On `batch.end`, all buffered deltas are pushed as one atomic update. Safety valve: 30-second timeout forces flush.

---

## Streaming Rules

These rules ensure every intermediate state during streaming is renderable.

### Emission Order (enforced by system prompt)

1. `meta.set` first (title, identity)
2. Root page entity
3. Section entities (direct children of page)
4. Items within sections
5. Relationships (both endpoints must exist)
6. Style overrides
7. Voice lines interleaved after milestones (~every 8-10 entity lines for L3)
8. Final voice line last

### Invariants

1. **Parents before children.** The reducer rejects `entity.create` if `parent` doesn't exist. This is the only hard ordering constraint.
2. **Empty containers are valid.** A `table` with zero children renders with a placeholder. The user sees structure scaffolding in, then items populating.
3. **Display hints on creation.** The parent needs its `display` hint when created so the compiler knows how to render incoming children.
4. **Relationships after both endpoints.** `rel.set` requires both entities to exist.
5. **Batches for restructuring.** Wrap `entity.move` sequences in `batch.start`/`batch.end`. Normal top-down creation doesn't need batching.

### Graceful Degradation

If the LLM violates emission order (e.g., forgets batch signals during a restructure), the server renders each line as it arrives. The user may see entities briefly jump around. Not broken, just not smooth. Batch signals are an optimization, not a correctness requirement.

---

## WebSocket Protocol

The client connects to `/ws/aide/{aide_id}` on page load.

**Server → Client messages:**

| Type | Payload | Client Action |
|------|---------|--------------|
| `delta` | Entity graph patch (one or more operations) | Patch React state store |
| `voice` | `{ text: string }` | Display in chat panel |
| `query_response` | `{ text: string, message_id: string }` | Display L4 answer in chat |
| `error` | `{ message: string, entities_applied: number }` | Show error banner |
| `status` | `{ state: "streaming" \| "complete" \| "interrupted" }` | Toggle typing indicator, enable input |

**Client → Server messages:**

| Type | Payload | Server Action |
|------|---------|--------------|
| `message` | `{ text: string }` | Route through classifier → LLM |
| `direct_edit` | `{ t: "entity.update", ref, p }` | Apply through reducer |
| `interrupt` | `{}` | Cancel LLM stream |
| `undo` | `{}` | Replay events minus last batch |
| `redo` | `{}` | Replay undone batch |

---

## Prompt Caching Strategy

Anthropic's prompt caching is **per-model** — a Haiku cache and a Sonnet cache are completely separate. This means we have three independent cache pools, one per tier.

```
           L2 (Haiku) cache        L3 (Sonnet) cache       L4 (Opus) cache
           85% of traffic          10% of traffic          5% of traffic

┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│ System prompt + L2   │  │ System prompt + L3   │  │ System prompt + L4   │
│ instructions         │  │ instructions         │  │ instructions         │
│ TTL: 5-min (free)    │  │ TTL: 1-hour (2x)    │  │ TTL: 1-hour (2x)    │
│ Hit rate: HIGH       │  │ Hit rate: MEDIUM     │  │ Hit rate: LOW        │
├──────────────────────┤  ├──────────────────────┤  ├──────────────────────┤
│ Aide snapshot        │  │ Aide snapshot        │  │ Aide snapshot        │
│ TTL: 5-min           │  │ TTL: 5-min           │  │ TTL: 5-min           │
├──────────────────────┤  ├──────────────────────┤  ├──────────────────────┤
│ Conversation tail    │  │ Conversation tail    │  │ Conversation tail    │
│ No cache             │  │ No cache             │  │ No cache             │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘
```

**Why different system prompt TTLs:**
- **L2 (Haiku):** 85% of traffic. 5-minute TTL is free (1.25x write, 0.1x read). With multiple active users, Haiku calls happen every few minutes — the cache stays warm naturally.
- **L3 (Sonnet):** 10% of traffic. Calls might be 10-20 minutes apart for a single user. 5-minute cache expires between calls. 1-hour TTL (2x write, 0.1x read) keeps it warm through gaps.
- **L4 (Opus):** 5% of traffic. Even less frequent. 1-hour TTL for the same reason. But caching matters least here — queries have short input and expensive output. The savings are minimal.

**Snapshot caching across tiers:** The aide snapshot changes every turn, but the prefix is stable (existing entities keep their position, new ones append). Even with 5-minute TTL, consecutive L2 calls within a session get snapshot cache hits. L3/L4 calls are less likely to hit the snapshot cache because they're infrequent.

**Key rules:**
- 1-hour TTL entries must appear before 5-minute TTL entries in the request.
- Maximum 4 cache breakpoints per request. We use 2 (after system prompt, after snapshot).
- Snapshot serialization must be deterministic and append-only to maximize prefix match.

**Cost impact on an active aide (L2 calls):**
- Full price: ~200 tokens (conversation tail + message)
- 0.1x price: ~4K tokens (system prompt + snapshot)
- Effective input cost: ~75% less than without caching

Conversation history is the enemy of caching — every message shifts the content. Keep the tail minimal (3-5 messages). The entity graph IS the memory.

---

## Storage (R2)

R2 stores three files per aide:

| File | Contents | Updated |
|------|----------|---------|
| `{aide_id}/events.jsonl` | Append-only event log with full event envelopes | Every mutation (append) |
| `{aide_id}/snapshot.json` | Materialized entity graph as JSON | Every mutation (overwrite) |
| `{aide_id}/published.html` | Static server-rendered HTML for public URL | On publish |

**events.jsonl** is the source of truth. Replaying it through the reducer produces any historical state. Used for undo, time travel, and debugging.

**snapshot.json** is derived state, cached for fast client load. When a client connects or reconnects, it gets the snapshot — not the full event log. Rebuilt after each mutation by the reducer.

**published.html** is the public-facing page at `toaide.com/s/{slug}`. Generated by server-side rendering the same React display components against the snapshot. Visitors see plain HTML — no React, no WebSocket, no account needed. Rebuilt when the user publishes (or auto-publishes on state change).

**During editing, HTML only exists client-side.** The React compiler renders the entity graph in the browser. No HTML is stored or transmitted during the editing session — only entity graph deltas over WebSocket.

---

## Rendering Timelines

### First Creation (L3, Sonnet)

| Time | What Arrives | What the User Sees |
|------|-------------|-------------------|
| 0ms | — | Typing indicator |
| ~300ms | meta.set + page entity | Page title appears |
| ~500ms | ceremony card | Card with date, time, location |
| ~600ms | voice: "Ceremony details set..." | Chat shows narration |
| ~800ms | section entities | Empty scaffolds appear |
| ~1.5s | voice: "Structure ready..." | Chat updates |
| ~2s | todo items populate | Checklist fills in |
| ~2.5s | style.set | Colors apply |
| ~3s | final voice line | "Add guests to get started." |

### L2 Update (Haiku)

| Time | What Happens |
|------|-------------|
| 0ms | User sends "Aunt Linda RSVPed yes" |
| ~400ms | First JSONL line → entity created → row appears |
| ~800ms | Relationship line → food link established |
| ~1s | Done |

### Direct Edit

| Time | What Happens |
|------|-------------|
| 0ms | User clicks "May 23" on ceremony card |
| 0ms | Inline input opens |
| — | User types "May 22", hits Enter |
| ~100ms | Client emits entity.update to server |
| ~200ms | Server confirms. Card shows "May 22." |
