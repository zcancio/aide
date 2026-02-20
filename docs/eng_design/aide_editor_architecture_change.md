# Architecture Change: Inline Preview (Kill the Iframe)

**Date:** 2026-02-20
**Status:** Approved
**Supersedes:** Editor PRD § "Preview Iframe" and § "State Flow"
**Affects:** `frontend/`, `backend/routes/`, `backend/services/`

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

This is the key UX improvement. On first turn (L3), the page builds live as primitives stream in. On subsequent turns (L2), it's fast enough to feel like a snap.

### SSE Protocol

```
POST /api/aide/{aide_id}/chat
Content-Type: application/json
Accept: text/event-stream

Request:  { "message": "poker league, 8 players, biweekly thursdays" }

Response (SSE stream):

event: token
data: {"text": "Setting up an 8-player poker league..."}

event: token
data: {"text": " with biweekly rotation."}

event: primitive
data: {"type": "meta.update", "payload": {"title": "Poker League"}, "sequence": 1, ...}

event: primitive
data: {"type": "collection.create", "payload": {"id": "roster", ...}, "sequence": 2, ...}

event: primitive
data: {"type": "entity.create", "payload": {"collection": "roster", ...}, "sequence": 3, ...}

...more primitives...

event: done
data: {"snapshot_hash": "abc123", "event_count": 24}
```

### Client-Side Handling

```javascript
const eventSource = new EventSource(...)  // or fetch + ReadableStream

eventSource.on('token', (data) => {
  // Append to streaming chat message
  appendToCurrentMessage(data.text)
})

eventSource.on('primitive', (data) => {
  const event = data  // already a valid primitive event
  const result = reduce(entityState, event)

  if (result.applied) {
    setEntityState(result.snapshot)
    setEvents(prev => [...prev, event])
    // React re-renders → previewHtml updates → DOM updates
    // User sees the page building in real-time
  } else {
    console.warn('Primitive rejected:', result.error)
    // Don't break — server will reconcile on done
  }
})

eventSource.on('done', (data) => {
  // Server has persisted everything.
  // Optionally verify snapshot_hash matches local state.
  // If mismatch: fetch canonical state from server and replace.
  setIsProcessing(false)
})
```

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

**Subsequent turns (L2, ~1.5-3 seconds):**
```
t=0s     User hits send. Message appears in chat.
t=0.8s   TTFT. Chat streams: "Mike out. Dave substituting."
t=1.2s   1-2 primitives arrive. Preview snaps to new state.
t=1.5s   Done.
```

The first turn feels like watching a page build itself — similar to Claude's artifact experience. Subsequent turns feel snappy — type, beat, result.

---

## Server Changes

### Endpoint: `POST /api/aide/{aide_id}/chat`

Currently returns `{ response_text, html, mutated }`. Change to SSE stream.

```python
@router.post("/api/aide/{aide_id}/chat")
async def chat(aide_id: str, body: ChatRequest, user=Depends(get_current_user)):
    async def event_stream():
        # 1. Load current state from DB
        aide = await aide_repo.get(aide_id, user.id)
        snapshot = aide.current_snapshot
        events = aide.event_log

        # 2. Call L2/L3 with streaming
        async for chunk in orchestrator.stream(
            message=body.message,
            snapshot=snapshot,
            events=events,
        ):
            if chunk.type == "token":
                yield sse_event("token", {"text": chunk.text})

            elif chunk.type == "primitive":
                # Validate + apply server-side (server stays authoritative)
                result = reduce(snapshot, chunk.event)
                if result.applied:
                    snapshot = result.snapshot
                    events.append(chunk.event)
                    yield sse_event("primitive", chunk.event)
                else:
                    yield sse_event("warning", {"error": result.error})

        # 3. Persist final state
        await aide_repo.update_state(aide_id, snapshot, events)

        # 4. If published, update R2 async
        if aide.status == "published":
            background_tasks.add_task(publish_to_r2, aide_id, snapshot, events)

        yield sse_event("done", {
            "snapshot_hash": hash_snapshot(snapshot),
            "event_count": len(events),
        })

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

Key: the server applies each primitive to its own copy of the snapshot as it streams. Both client and server process the same primitives in the same order. They arrive at the same state. The `snapshot_hash` on `done` is a checksum the client can verify.

### Orchestrator Changes

The orchestrator needs to stream primitives as the LLM generates them, not batch them at the end.

The L2/L3 prompt already asks for JSONL primitives. As the LLM streams tokens, parse complete JSON lines as they arrive:

```python
async def stream(self, message, snapshot, events):
    buffer = ""
    async for token in llm.stream(prompt):
        buffer += token

        # Try to extract complete JSONL primitives from buffer
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue

            parsed = try_parse_primitive(line)
            if parsed:
                yield StreamChunk(type="primitive", event=parsed)
            else:
                # It's response text
                yield StreamChunk(type="token", text=line)
```

This requires the LLM to emit primitives as JSONL lines in the response (one per line, parseable as they arrive). The system prompt should instruct the model to emit primitives first, then response text — or interleave them with clear delimiters.

---

## Cold Load (Refresh, Returning, Deep Link)

When the user refreshes the page, returns to an aide from the dashboard, or opens a direct link — the editor has no state in memory. It needs to hydrate from the server.

### Endpoint

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

### Client Hydration

```javascript
async function loadAide(aideId) {
  const res = await fetch(`/api/aides/${aideId}/hydrate`)
  const { snapshot, events, blueprint, messages, snapshot_hash } = await res.json()

  setEntityState(snapshot)       // NOT replayed — snapshot is already current
  setEvents(events)
  setBlueprint(blueprint)
  setMessages(messages)

  // Preview renders immediately from snapshot
  // render(snapshot, blueprint, events) → HTML → div
}
```

### Key Points

- **No replay on load.** The server persists the reduced snapshot after every turn. The client receives the current state directly — it does not replay the event log to reconstruct it. The events are carried for the audit trail and for embedding in published HTML, not for client-side reconstruction.
- **No HTML transfer.** The server does not send rendered HTML. The client renders locally from the snapshot using the same `render()` function used during streaming. This means the cold load path and the streaming path produce identical output — same engine, same function, same result.
- **Load time.** A typical aide's JSON payload (snapshot + events + messages) is 20-100KB. The client-side render is milliseconds. Total cold load: one network round-trip + a few ms of rendering. Fast.
- **New aide (no state yet).** When creating a new aide, there's no server state to load. The client starts with `emptyState()` and an empty event log. The first message creates everything via streamed primitives.

### Sequence

```
Cold load:
  t=0ms     GET /api/aides/{id}/hydrate
  t=200ms   JSON response arrives (snapshot + events + blueprint + messages + snapshot_hash)
  t=205ms   render(snapshot, blueprint, events) → HTML string
  t=210ms   DOM update. Preview visible. Chat history populated.
  t=210ms   Ready for input.

New aide:
  t=0ms     emptyState() + empty events + no blueprint
  t=0ms     render(emptyState()) → "This page is empty."
  t=0ms     Ready for input. Placeholder: "What are you running?"
```

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

- **Published pages** are still static HTML files on R2. `render()` still produces full standalone HTML with embedded `aide+json`, `aide-events+json`, and `aide-blueprint+json` blocks. Publishing runs server-side after state is persisted.
- **The chat overlay** spec is unchanged — floating input bar, expandable history, backdrop blur, auto-collapse.
- **Voice rules** are unchanged.
- **L2/L3 routing** is unchanged.
- **Server is still authoritative.** Client-side reduce is for real-time preview. Server persists. On mismatch, server wins.
- **Database schema** is unchanged. `aides` table stores snapshot + event log.

---

## What Changes

| Before (PRD) | After |
|---|---|
| Preview is a sandboxed `<iframe>` with `srcdoc` | Preview is a `<div>` with `dangerouslySetInnerHTML` |
| Server returns `{ html }` per turn | Server streams primitives via SSE |
| Engine runs server-side only | Engine runs on both client and server |
| Preview updates once on turn completion | Preview updates incrementally as primitives arrive |
| Editor holds no entityState | Editor holds entityState as single source of truth during session |
| No streaming | SSE streaming of tokens + primitives |

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
