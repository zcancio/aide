# AIde Editor Architecture Change: Kill the iframe

**Author:** Claude (implementing GitHub issue #43)
**Date:** 2026-02-20
**Status:** In Implementation
**Supersedes:** aide_editor_prd.md iframe approach

---

## Summary

Replace the sandboxed `<iframe>` preview with an inline `<div>` in the same React app. Stream primitives via Server-Sent Events (SSE) for real-time page building during LLM calls.

---

## Problem

The current iframe-based architecture creates fundamental issues:

### 1. Dual-State Sync Problem
- Editor state (React app) and preview state (iframe srcdoc) are separate
- `postMessage` coordination is fragile and error-prone
- State can drift between editor and preview
- Updates require full iframe reload

### 2. Poor UX During LLM Calls
- Preview is frozen during LLM processing (5-15s on L3 Sonnet)
- No visual feedback that work is happening
- User sees stale state while waiting
- No incremental progress indication

### 3. Complexity
- Sandbox coordination via `postMessage`
- CSP management across iframe boundary
- Scroll position preservation hacks
- Link interception complexity

---

## Solution

**Single React app, single state, single render cycle.**

### Architecture

```
┌─────────────────────────────────────────────────────┐
│  React App (get.toaide.com/aide/:id)                │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │  <PreviewDiv>                                │   │
│  │    - Renders snapshot via engine.render()   │   │
│  │    - Client-side reducer/renderer           │   │
│  │    - CSS-scoped (.aide-preview wrapper)     │   │
│  │    - Updates incrementally during stream    │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │  <ChatOverlay>                               │   │
│  │    - Floating input bar                      │   │
│  │    - Expandable history                      │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
         ↕ SSE connection
┌─────────────────────────────────────────────────────┐
│  FastAPI Backend                                     │
│  GET /sse/aide/:id?token=xxx                        │
│    → Streams primitives as LLM generates them       │
│    → Event types: token, primitive, done, error     │
└─────────────────────────────────────────────────────┘
```

### Flow

1. **User sends message** → WebSocket or POST to backend
2. **Backend starts LLM call** → Opens SSE stream to client
3. **LLM generates primitives** → Backend streams each primitive via SSE
4. **Client receives primitive** → Apply via `reduce()`, render via `render()`
5. **Preview updates incrementally** → Page "builds itself" in real-time
6. **LLM finishes** → SSE sends `done` event with final snapshot hash
7. **Client reconciles** → Verify hash matches, save final state

---

## Component Details

### 1. Engine Client Bundle

**File:** `engine/builds/engine.esm.js`

- ESM bundle of TypeScript engine (reducer + renderer)
- Exports: `reduce()`, `render()`, `empty_snapshot()`
- No dependencies, tree-shakeable
- Served from R2 CDN: `https://aide-published.com/engine/v3/engine.esm.js`

**Build:**
```bash
cd engine
tsc --project tsconfig.json --outDir builds/esm --module esnext
# Produces: builds/esm/reducer.js, builds/esm/renderer.js, builds/esm/index.js
```

### 2. PreviewDiv Component

**File:** `frontend/components/PreviewDiv.tsx`

```tsx
interface PreviewDivProps {
  snapshot: Snapshot;
  className?: string;
}

function PreviewDiv({ snapshot, className }: PreviewDivProps) {
  const htmlContent = render(snapshot);

  return (
    <div
      className={`aide-preview ${className}`}
      dangerouslySetInnerHTML={{ __html: htmlContent }}
    />
  );
}
```

**Responsibilities:**
- Render snapshot to HTML via `engine.render()`
- Apply CSS scoping wrapper
- Preserve scroll position on update (via `useEffect` + `scrollY` ref)
- Intercept links to open in new tab

### 3. CSS Scoping

**File:** `frontend/styles/preview-isolation.css`

```css
/* Scope all aide-generated styles to .aide-preview */
.aide-preview {
  /* Reset to prevent parent styles from leaking in */
  all: initial;
  display: block;

  /* Allow aide styles to work normally inside */
  * {
    all: revert;
  }
}

/* Ensure links don't navigate inside SPA */
.aide-preview a {
  cursor: pointer;
}
```

### 4. SSE Endpoint

**File:** `backend/routes/sse.py`

```python
@router.get("/sse/aide/{aide_id}")
async def stream_primitives(
    aide_id: UUID,
    user: User = Depends(get_current_user)
):
    """
    Stream primitives as LLM generates them.

    Event types:
    - token: LLM text tokens (for chat display)
    - primitive: Structural primitive event (for preview updates)
    - done: Final snapshot hash + event count
    - error: Error message
    """
    async def event_generator():
        try:
            orchestrator = StreamingOrchestrator(aide_id, user.id)

            async for event in orchestrator.stream():
                if event["type"] == "token":
                    yield f"event: token\ndata: {json.dumps(event)}\n\n"
                elif event["type"] == "primitive":
                    yield f"event: primitive\ndata: {json.dumps(event)}\n\n"
                elif event["type"] == "done":
                    yield f"event: done\ndata: {json.dumps(event)}\n\n"

        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
```

### 5. Client SSE Handler

**File:** `frontend/hooks/useSSE.ts`

```typescript
interface SSEState {
  snapshot: Snapshot;
  tokens: string[];
  error: string | null;
  done: boolean;
}

function useSSE(aideId: string) {
  const [state, setState] = useState<SSEState>({
    snapshot: empty_snapshot(),
    tokens: [],
    error: null,
    done: false,
  });

  useEffect(() => {
    const es = new EventSource(`/sse/aide/${aideId}`);

    es.addEventListener('token', (e) => {
      const { text } = JSON.parse(e.data);
      setState(prev => ({
        ...prev,
        tokens: [...prev.tokens, text]
      }));
    });

    es.addEventListener('primitive', (e) => {
      const primitive = JSON.parse(e.data);
      setState(prev => ({
        ...prev,
        snapshot: reduce(prev.snapshot, primitive)
      }));
    });

    es.addEventListener('done', (e) => {
      const { hash, event_count } = JSON.parse(e.data);
      // TODO: Verify hash matches client-side computed hash
      setState(prev => ({ ...prev, done: true }));
      es.close();
    });

    es.addEventListener('error', (e) => {
      const { error } = JSON.parse(e.data);
      setState(prev => ({ ...prev, error }));
      es.close();
    });

    return () => es.close();
  }, [aideId]);

  return state;
}
```

### 6. Snapshot Reconciliation

After `done` event, verify client-side snapshot matches server:

```typescript
function verifySnapshot(clientSnapshot: Snapshot, serverHash: string): boolean {
  const clientHash = hashSnapshot(clientSnapshot);
  if (clientHash !== serverHash) {
    console.error('Snapshot mismatch! Reloading from server...');
    // Fetch canonical snapshot from server
    return false;
  }
  return true;
}

function hashSnapshot(snapshot: Snapshot): string {
  // Simple JSON hash for now (could use xxhash later)
  return btoa(JSON.stringify(snapshot));
}
```

---

## Migration Steps

### Phase 1: Infrastructure (this PR)
- [x] Create this document
- [ ] Bundle engine.js for client (ESM build)
- [ ] Build `<PreviewDiv>` component
- [ ] Add CSS scoping
- [ ] Build SSE endpoint
- [ ] Build client-side SSE handler
- [ ] Add reconciliation logic

### Phase 2: Integration
- [ ] Update `StreamingOrchestrator` to emit primitives line-by-line
- [ ] Replace iframe with `<PreviewDiv>` in editor route
- [ ] Add scroll preservation logic
- [ ] Test CSS isolation

### Phase 3: Cleanup
- [ ] Remove all iframe-related code
- [ ] Remove `postMessage` coordination
- [ ] Remove CSP iframe rules
- [ ] Update tests

---

## Open Questions

### 1. Scroll Preservation
**Options:**
- A) Save/restore `scrollY` in `useEffect` (simple, can flicker)
- B) Surgical DOM updates (complex, pixel-perfect)
- C) Render to virtual DOM, diff, patch (React reconciliation)

**Decision:** Start with (A), optimize to (C) if flicker is noticeable.

### 2. Renderer Fragment Mode
Should `render()` emit full HTML document or just body content?

**Full document:**
```html
<!DOCTYPE html>
<html><head>...</head><body>...</body></html>
```

**Fragment mode:**
```html
<div class="aide-root">...</div>
```

**Decision:** Fragment mode for inline preview. Full document for published pages. Add `fragmentMode: boolean` option to `render()`.

### 3. Link Handling
How to prevent links from navigating the SPA?

**Options:**
- A) `target="_blank"` on all `<a>` tags (server-side in renderer)
- B) Click intercept in `<PreviewDiv>` (client-side event listener)
- C) Both (defense in depth)

**Decision:** (C) — renderer adds `target="_blank"`, component intercepts as backup.

---

## Benefits

### UX
- Real-time preview updates during LLM calls
- Visual feedback that work is happening
- Smoother, more responsive editing experience
- No frozen preview state

### Technical
- Single state, single source of truth
- No `postMessage` complexity
- Simpler CSP (no iframe sandbox)
- Client-side reducer enables offline editing (future)

### Performance
- No iframe reload overhead
- Incremental updates (only changed parts re-render)
- Streaming reduces perceived latency
- Smaller payloads (primitives vs full HTML)

---

## Risks

### 1. CSS Isolation
**Risk:** Parent styles leak into preview, preview styles leak out.
**Mitigation:** CSS scoping via `.aide-preview` wrapper + `all: initial` reset.

### 2. XSS
**Risk:** User-controlled content in inline HTML.
**Mitigation:** Renderer already escapes all user content. No `<script>` tags in preview.

### 3. Performance (Large Snapshots)
**Risk:** Re-rendering large snapshots (1000+ entities) on every primitive.
**Mitigation:** React memoization. If still slow, batch primitives into 100ms windows.

### 4. Browser Compatibility
**Risk:** Old browsers don't support `EventSource` (SSE).
**Mitigation:** Polyfill or fallback to polling (rare case, modern browsers widely support SSE).

---

## Testing

### Unit Tests
- `engine.render()` fragment mode
- `reduce()` determinism (snapshot hash stability)
- CSS scoping (styles don't leak)

### Integration Tests
- SSE stream sends primitives in order
- Client-side reducer applies primitives correctly
- Snapshot reconciliation detects mismatches

### E2E Tests
- User sends message → preview updates incrementally
- Scroll position preserved on update
- Links open in new tab
- Error handling (SSE disconnect)

---

## Future Enhancements

### 1. Optimistic Updates
Apply user input immediately (before LLM responds) for instant feedback.

### 2. Offline Editing
Client-side reducer enables full offline editing. Sync to server on reconnect.

### 3. Time-Travel Debugging
Replay event log to reconstruct any historical snapshot state.

### 4. Collaborative Editing
Multiple SSE streams merge primitives via CRDT or OT.

---

## References

- **SSE Spec:** https://html.spec.whatwg.org/multipage/server-sent-events.html
- **React dangerouslySetInnerHTML:** https://react.dev/reference/react-dom/components/common#dangerously-setting-the-inner-html
- **CSS `all: initial`:** https://developer.mozilla.org/en-US/docs/Web/CSS/all
- **EventSource polyfill:** https://github.com/Yaffle/EventSource

---

## Approval

- [ ] Technical review (engine determinism verified)
- [ ] UX review (scroll preservation acceptable)
- [ ] Security review (CSS isolation, XSS prevention)
- [ ] Performance benchmarks (1000 entity snapshot renders < 100ms)
