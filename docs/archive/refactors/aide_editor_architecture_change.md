# Architecture Change: Inline Preview (Kill the Iframe)

**Date:** 2026-02-20
**Status:** Implemented
**Supersedes:** Editor PRD § "Preview Iframe" and § "State Flow"
**Affects:** `frontend/`, `backend/routes/`, `backend/services/`

---

> **Implementation Note:** This architecture change has been implemented. The actual implementation uses **WebSocket** (`/ws/aide/{aide_id}`) instead of SSE, and state is stored in **PostgreSQL** (`aides.state` column) rather than R2. See `backend/routes/ws.py` and `frontend/src/hooks/useWebSocket.js` for the current implementation.

---

## Problem

The editor PRD specified a sandboxed `<iframe>` for the preview, with `srcdoc` updated per turn. This creates a dual-state problem: the editor wrapper needs `entityState` for routing and context, and the iframe has its own copy embedded in the rendered HTML. Keeping them aligned across turns — especially during streaming — is fragile and fundamentally broken.

Additionally, the iframe approach means the preview is frozen during the entire LLM call. On first-turn L3 calls (schema synthesis, 5-15 seconds), the user stares at a blank or stale page with no feedback. This is unacceptable UX.

---

## Decision

**Kill the iframe. The preview is a `<div>` inside the same React app.**

One app. One state. One render cycle. No `postMessage`. No sync. The engine (`reduce` + `render`) runs client-side.

This is the same pattern Claude.ai uses for artifacts — inline rendering in the same DOM, not an iframe.

---

## Why This Works (Security)

The iframe existed for sandboxing. But AIde's security boundary is NOT the iframe — it's the **primitive → reducer → renderer pipeline**. The AI never produces raw HTML. It produces structured primitives (`entity.create`, `block.set`, etc.), and the deterministic renderer converts those to HTML. There is nothing to sandbox against because the renderer is the sandbox.

Published pages on `toaide.com/s/{slug}` remain static HTML served from R2 on a separate origin. That's the real security boundary for end users.

---

## New Architecture

### State Ownership

```
Editor (single React app)
├── state:
│   ├── entityState: AideState        // THE single source of truth
│   ├── messages: Message[]           // conversation history
│   ├── aideId: string
│   └── isProcessing: boolean
├── engine.js (client-side)
│   ├── emptyState()
│   ├── reduce(snapshot, event) → ReduceResult
│   └── render(snapshot, blueprint, events) → HTML string
```

The editor owns `entityState`. There is exactly one copy. The preview div renders from it. The server persists it but does not need to send rendered HTML back.

### Component Structure

```jsx
function Editor({ aideId }) {
  const [entityState, setEntityState] = useState(emptyState())
  const [events, setEvents] = useState([])
  const [messages, setMessages] = useState([])
  const [blueprint, setBlueprint] = useState(null)

  // Preview is just rendered HTML from state
  const previewHtml = useMemo(
    () => render(entityState, blueprint, events),
    [entityState, blueprint, events]
  )

  return (
    <>
      <Header aideId={aideId} />
      <PreviewDiv html={previewHtml} />
      <ChatOverlay messages={messages} onSend={handleSend} />
    </>
  )
}

function PreviewDiv({ html }) {
  return (
    <div
      className="aide-preview"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}
```

### CSS Scoping

The preview div needs scoped CSS so aide styles don't leak into the editor chrome. Approach:

```css
.aide-preview {
  /* Contains the rendered aide page */
  all: initial;           /* Reset inherited styles */
  position: absolute;
  top: var(--header-height);
  bottom: 0;
  width: 100%;
  overflow-y: auto;
}

/* Aide's own styles (from renderer) are scoped inside .aide-preview */
.aide-preview .aide-page { ... }
```

The renderer already produces CSS scoped to `.aide-page`. We just need to ensure the editor's own styles (header, chat overlay) don't collide. Use a prefix convention: editor styles use `.editor-*`, aide styles use `.aide-*`.

---

## Streaming Primitives

This is the key UX improvement. On first turn (L4), the page builds live as primitives stream in. On subsequent turns (L3), it's fast enough to feel like a snap.

### WebSocket Protocol (Implemented)

> **Note:** The original spec proposed SSE. Implementation uses WebSocket for bidirectional communication.

```
WebSocket: /ws/aide/{aide_id}

Client → Server:
  { "type": "message", "content": "poker league, 8 players, biweekly thursdays", "message_id": "..." }

Server → Client:
  { "type": "stream.start", "message_id": "..." }
  { "type": "entity.create", "id": "page", "data": {...} }
  { "type": "entity.create", "id": "roster", "data": {...} }
  { "type": "voice", "text": "Poker league created. 8-player roster ready." }
  { "type": "stream.end", "message_id": "..." }
```

See [Streaming Pipeline](../eng_design/editing/core/core_streaming_pipeline.md) for the full WebSocket protocol.

### Client-Side Handling (Implemented)

**Implementation:** `frontend/src/hooks/useWebSocket.js`

```javascript
// useWebSocket hook handles connection lifecycle
const { send, sendDirectEdit } = useWebSocket(aideId, {
  onDelta: handleDelta,      // entity.create, entity.update, entity.remove
  onSnapshot: handleSnapshot, // snapshot.start/end for hydration
  onVoice: handleVoice,      // voice messages for chat
});

// Send user message
send({ type: 'message', content: userInput });

// Direct edit (no LLM)
sendDirectEdit(entityId, field, value);
```

The reducer runs server-side. The client receives already-validated deltas via WebSocket and patches its local store.

### What the User Sees

**First turn (L3, ~5-15 seconds):**
```
t=0s     User hits send. Message appears in chat.
         Preview shows empty state / "This page is empty."
t=1s     TTFT. Chat starts streaming: "Setting up an 8-player..."
t=1.5s   First primitives arrive. Collections appear.
         Preview shows empty table structures.
t=2-4s   Entity primitives stream in.
         Preview fills with player names, schedule rows.
t=4-8s   Block, view, style primitives arrive.
         Layout takes shape. Styles apply. Page "builds itself."
t=8-15s  Done. Final state. Page is complete.
```

**Subsequent turns (L3, ~1.5-3 seconds):**
```
t=0s     User hits send. Message appears in chat.
t=0.8s   TTFT. Chat streams: "Mike out. Dave substituting."
t=1.2s   1-2 primitives arrive. Preview snaps to new state.
t=1.5s   Done.
```

The first turn feels like watching a page build itself — similar to Claude's artifact experience. Subsequent turns feel snappy — type, beat, result.

---

## Server Changes (Implemented)

### WebSocket Endpoint: `/ws/aide/{aide_id}`

**Implementation:** `backend/routes/ws.py`

The WebSocket handler:
1. Loads snapshot and conversation from PostgreSQL on connect
2. Hydrates client with existing entities via `snapshot.start`/`snapshot.end`
3. Processes messages through `StreamingOrchestrator`
4. Broadcasts deltas as they're applied
5. Persists state after each turn

```python
@router.websocket("/ws/aide/{aide_id}")
async def aide_websocket(websocket: WebSocket, aide_id: str):
    await websocket.accept()

    # Load existing state
    snapshot = await _load_snapshot(user_id, aide_id)
    conversation = await _load_conversation(user_id, aide_id)

    # Hydrate client with existing entities
    await websocket.send_text(json.dumps({"type": "snapshot.start"}))
    for entity_id, entity_data in entities.items():
        await websocket.send_text(json.dumps({
            "type": "entity.create", "id": entity_id, "data": entity_data
        }))
    await websocket.send_text(json.dumps({"type": "snapshot.end"}))

    # Message loop
    while True:
        msg = await websocket.receive_json()
        if msg["type"] == "message":
            # Process through orchestrator
            async for result in orchestrator.process_message(content):
                # Broadcast deltas to client
                ...
        elif msg["type"] == "direct_edit":
            # Apply through reducer, broadcast delta
            ...
```

### Orchestrator

**Implementation:** `backend/services/streaming_orchestrator.py`

The orchestrator processes LLM tool calls (`mutate_entity`, `set_relationship`, `voice`) and converts them to reducer events. See [Streaming Pipeline](../eng_design/editing/core/core_streaming_pipeline.md) for details.

---

## Cold Load (Refresh, Returning, Deep Link)

When the user refreshes the page, returns to an aide from the dashboard, or opens a direct link — the editor has no state in memory. It needs to hydrate from the server.

### Hydration Approaches (Two paths)

**1. REST Hydrate Endpoint** (exists but not primary)

```
GET /api/aides/{aide_id}/hydrate
→ {
    snapshot: AideState,       // current state (already reduced, ready to render)
    events: Event[],           // full event log (for audit trail + published embed)
    blueprint: Blueprint,      // identity, voice, prompt
    messages: Message[],       // conversation history
    snapshot_hash: string,     // checksum for reconciliation
  }
```

**2. WebSocket Hydration** (primary, implemented)

When the WebSocket connects, the server sends existing state via `snapshot.start`/`snapshot.end`:

```
Client connects to /ws/aide/{aide_id}
  → Server sends: { type: "snapshot.start" }
  → Server sends: { type: "entity.create", id: "page", data: {...} }
  → Server sends: { type: "entity.create", id: "roster", data: {...} }
  → ...all entities...
  → Server sends: { type: "meta.update", data: {...} }
  → Server sends: { type: "snapshot.end" }
```

### Client Implementation

**Implementation:** `frontend/src/components/Editor.jsx`, `frontend/src/hooks/useAide.js`

```javascript
// Editor loads aide metadata and conversation history via REST
useEffect(() => {
  api.fetchAide(aideId);              // GET /api/aides/{aide_id}
  api.fetchConversationHistory(aideId); // GET /api/aides/{aide_id}/history
}, [aideId]);

// WebSocket hydrates entity state on connect
const { entityStore, handleDelta, handleSnapshot } = useAide();
useWebSocket(aideId, {
  onDelta: handleDelta,
  onSnapshot: handleSnapshot,  // handles snapshot.start/end
  onVoice: handleVoice,
});
```

### Key Points

- **No replay on load.** The server persists the reduced snapshot after every turn. The client receives the current state directly — it does not replay the event log.
- **No HTML transfer.** The server does not send rendered HTML. The client renders locally from the entity store using `renderHtml()`.
- **Load time.** A typical aide's entities are sent as individual messages. Total cold load: WebSocket connect + entity messages + render. Fast.
- **New aide (no state yet).** The WebSocket connects with empty state. The first message creates everything via streamed deltas.

---

## Reconciliation

If the client and server diverge (network glitch, rejected primitive the client accepted, etc.):

1. On `done`, client computes `hash(entityState)` and compares to server's `snapshot_hash`
2. If they match: done, everything is consistent
3. If they don't match: client fetches canonical snapshot from `GET /api/aide/{aide_id}/state` and replaces local state

This should be rare. Both sides run the same `reduce()` function on the same primitives. But the safety net is there.

---

## Client-Side Engine Bundle

The engine is already built as `engine.js` (874 lines, ~25KB unminified). It exports:

- `emptyState()` → fresh AideState
- `reduce(snapshot, event)` → ReduceResult
- `replay(events)` → AideState
- `render(snapshot, blueprint, events)` → HTML string
- `parseAideHtml(html)` → { snapshot, blueprint, events }

For the editor, we need this as an ES module import (currently CommonJS). Either:
- Build an ESM version from `engine.ts`
- Use a bundler (vite/esbuild) that handles CJS→ESM
- Or just convert the exports: `export { emptyState, reduce, replay, render }`

The compact build (`engine.compact.js`) is also available if bundle size matters, but 25KB is fine.

---

## What Stays the Same

- **Published pages** are still static HTML files. Publishing runs server-side after state is persisted.
- **The chat overlay** spec is unchanged — floating input bar, expandable history, backdrop blur.
- **Voice rules** are unchanged.
- **L3/L4 routing** is unchanged.
- **Server is still authoritative.** The reducer runs server-side. Client receives validated deltas. On mismatch, server wins.
- **Database schema** is unchanged. `aides` table stores snapshot + event log in `state` and `event_log` JSONB columns.

---

## What Changes

| Before (PRD) | After (Implemented) |
|---|---|
| Preview is a sandboxed `<iframe>` with `srcdoc` | Preview is a `<div>` inside Shadow DOM |
| Server returns `{ html }` per turn | Server streams deltas via WebSocket |
| Engine runs server-side only | Reducer runs server-side, renderer runs client-side |
| Preview updates once on turn completion | Preview updates incrementally as deltas arrive |
| Editor holds no entityState | Editor holds entityStore as single source of truth during session |
| No streaming | WebSocket streaming of entity deltas + voice |

---

## Migration Steps

1. **Bundle engine.js for client** — ESM build from engine.ts, include in frontend bundle
2. **Build `<PreviewDiv>` component** — replaces iframe, renders from entityState via `render()`
3. **Add CSS scoping** — `.aide-preview` wrapper with style isolation
4. **Build SSE endpoint** — replace batch `/chat` endpoint with streaming version
5. **Build client-side SSE handler** — parse `token` and `primitive` events, update state incrementally
6. **Add reconciliation** — snapshot hash check on `done`
7. **Update orchestrator** — stream primitives as JSONL lines, parse incrementally
8. **Test scroll preservation** — preview div should maintain scroll position across re-renders (React key strategy or manual scroll save/restore)
9. **Test CSS isolation** — aide styles must not leak into editor chrome and vice versa
10. **Remove all iframe references** — clean up any `sandbox`, `srcdoc`, `postMessage` code

---

## Open Questions

1. **Scroll preservation on re-render.** When `dangerouslySetInnerHTML` changes, React replaces the DOM. This resets scroll position. We need either: (a) save/restore scroll position around updates, or (b) use a more surgical DOM update strategy (diff and patch instead of full replace). Option (a) is simpler for v1.

2. **Renderer output format.** Currently `render()` produces a full HTML document (`<!DOCTYPE html><html>...`). For inline preview, we only need the `<body>` content + `<style>` block. Consider adding a `RenderOptions.fragment` flag that emits just the inner content without the document wrapper, `<head>`, OG tags, etc.

3. **Link handling.** In an iframe, links naturally don't navigate the parent. In a div, clicking a link in the preview would navigate the editor away. Add `target="_blank"` to all links in rendered output, or add a click handler on `.aide-preview` that intercepts navigation.
