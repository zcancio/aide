# 03: Streaming Pipeline

> **Prerequisites:** [Data Model](core_data_model.md) · [Tool Calls](core_tool_calls.md)
> **Next:** [Display Components](core_display_components.md) (what the client does with each delta)

---

## End-to-End Flow

```
User sends message via WebSocket
  → Classifier picks tier (L3/L4)           [<10ms, see 05]
  → LLM streams tool calls
  → Server parses tool_use events
  → Converts to reducer events
  → Reducer applies event
    → accepted: update snapshot, push delta to client via WebSocket
    → rejected: skip, log, continue
  → Client patches entity graph in React state
  → React re-renders affected components
  → User sees page update progressively
```

**Implementation:** `backend/routes/ws.py`, `backend/services/streaming_orchestrator.py`

---

## Server-Side Processing

The orchestrator processes LLM tool calls and converts them to reducer events.

```
LLM stream → tool_use event → tool_use_to_reducer_event()
  → mutate_entity(action="create") → {"t": "entity.create", ...}
  → mutate_entity(action="update") → {"t": "entity.update", ...}
  → set_relationship(action="set") → {"t": "rel.set", ...}
  → voice(text="...") → {"t": "voice", ...}

For each reducer event:
  → reducer(snapshot, event)
    → applied: update snapshot, yield delta to WebSocket
    → rejected: log rejection, continue
```

**Escalation handling:** When L3 signals it needs structural help (via `needs_escalation()`), the orchestrator runs:
1. L4 creates structure with original snapshot
2. L3 retries with L4's updated snapshot
3. Results merged: L4 tool calls first, then L3

---

## Streaming Rules

These rules ensure every intermediate state during streaming is renderable.

### Emission Order (enforced by system prompt)

1. Page entity (root)
2. Section entities (direct children of page)
3. Items within sections
4. Relationships (both endpoints must exist)
5. Style overrides
6. Voice lines (via `voice` tool call)

### Invariants

1. **Parents before children.** The reducer rejects `entity.create` if `parent` doesn't exist. This is the only hard ordering constraint.
2. **Empty containers are valid.** A `table` with zero children renders with a placeholder. The user sees structure scaffolding in, then items populating.
3. **Display hints on creation.** The parent needs its `display` hint when created so the compiler knows how to render incoming children.
4. **Relationships after both endpoints.** `rel.set` requires both entities to exist.
5. **Voice is required.** Every response must include at least one `voice` tool call — without it, the user sees nothing in chat.

---

## WebSocket Protocol

The client connects to `/ws/aide/{aide_id}` on page load.

**Server → Client messages:**

| Type | Payload | Client Action |
|------|---------|--------------|
| `snapshot.start` | `{}` | Begin hydration mode |
| `entity.create` | `{ id, data }` | Add entity to state |
| `entity.update` | `{ id, data }` | Patch entity in state |
| `entity.remove` | `{ id }` | Mark entity removed |
| `meta.update` | `{ data }` | Update page metadata |
| `snapshot.end` | `{}` | End hydration mode |
| `stream.start` | `{ message_id }` | Show typing indicator |
| `voice` | `{ text }` | Display in chat panel |
| `stream.end` | `{ message_id }` | Hide typing indicator, enable input |
| `stream.error` | `{ error }` | Show error banner |
| `stream.interrupted` | `{ message_id }` | Stream was cancelled |
| `direct_edit.error` | `{ error }` | Direct edit failed |

**Client → Server messages:**

| Type | Payload | Server Action |
|------|---------|--------------|
| `message` | `{ content, message_id }` | Route through classifier → LLM |
| `direct_edit` | `{ entity_id, field, value }` | Apply entity.update through reducer |
| `interrupt` | `{}` | Cancel LLM stream |
| `set_profile` | `{ profile }` | Set mock LLM profile (dev only) |

---

## Prompt Caching Strategy

The system prompt is split into two blocks for Anthropic's prompt caching.

```
┌──────────────────────────────────────┐
│  Block 1: Static tier instructions   │  cache_control: { type: "ephemeral" }
│  (shared_prefix + tier instructions) │
│  ~2,200-2,800 tokens                 │
├──────────────────────────────────────┤
│  Block 2: Dynamic snapshot           │  no cache_control
│  (current state as JSON)             │
│  ~500-3,000 tokens                   │
└──────────────────────────────────────┘
```

**Implementation:** `backend/services/prompt_builder.py`

```python
def build_system_blocks(tier: str, snapshot: dict) -> list[dict]:
    return [
        {"type": "text", "text": base, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": f"## Current Snapshot\n```json\n{snapshot_json}\n```"},
    ]
```

**Caching behavior:**
- Block 1 (static) uses ephemeral caching — survives across turns within a session
- Block 2 (snapshot) has no cache control — changes every turn
- Anthropic's caching is per-model — Sonnet and Opus have separate caches

**Conversation windowing:** Messages are windowed via `build_messages()`:
- Maximum 9 messages (~3 exchanges) to prevent unbounded growth
- Always starts on a user message (API requirement)

---

## Storage (PostgreSQL)

State is stored in the `aides` table:

| Column | Type | Contents |
|--------|------|----------|
| `state` | JSONB | Current snapshot (entities, relationships, meta, styles) |
| `event_log` | JSONB | Append-only event history (for undo/replay) |
| `r2_prefix` | TEXT | Legacy field (R2 path prefix) |

**Conversation history** is stored in the `conversations` table:
- Messages as JSONB array of `{role, content, timestamp}`
- Loaded on WebSocket connection, persisted after each turn

**Published HTML** is stored in the `aide_files` table:
- Generated by server-side rendering on publish
- Served at `/s/{slug}` as static HTML

**Implementation:**
- `backend/repos/aide_repo.py` — aide CRUD, snapshot persistence
- `backend/repos/conversation_repo.py` — conversation history
- `backend/routes/ws.py` — `_load_snapshot()`, `_save_snapshot()`, `_load_conversation()`

---

## Rendering Timelines

### First Creation (L4 → L3)

| Time | What Arrives | What the User Sees |
|------|-------------|-------------------|
| 0ms | — | Typing indicator |
| ~300ms | First tool call → page entity | Page title appears |
| ~500ms | Section entities | Empty scaffolds appear |
| ~800ms | voice tool call | Chat shows "Page created." |
| ~1.5s | Child entities populate | Content fills in |
| ~2s | Final voice | "Add guests to get started." |

### L3 Update

| Time | What Happens |
|------|-------------|
| 0ms | User sends "Aunt Linda RSVPed yes" |
| ~500ms | First tool call → entity updated → row changes |
| ~1s | voice tool call → "Linda confirmed." |
| ~1.2s | Done |

### Direct Edit

| Time | What Happens |
|------|-------------|
| 0ms | User clicks "May 23" on ceremony card |
| 0ms | Inline input opens |
| — | User types "May 22", hits Enter |
| ~100ms | Client sends direct_edit to server |
| ~200ms | Server confirms, broadcasts delta. Card shows "May 22." |
