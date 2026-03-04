# Phase 1: Vertical Slice Build Log

**Date:** 2026-02-19
**Status:** ✅ Phase 1 Vertical Slice Complete

---

## Summary

Implemented the complete end-to-end pipeline: user types a message → server receives via WebSocket → MockLLM streams a golden file → server parses each JSONL line → v2 reducer applies to snapshot → server pushes entity deltas to client via WebSocket → client patches entity store → FallbackDisplay renders entities on screen.

---

## What Was Built

### Backend

| File | Description |
|------|-------------|
| `backend/services/jsonl_parser.py` | **New.** Streaming JSONL parser. Buffers partial chunks, emits complete parsed lines. Expands abbreviated keys (`t→type`, `p→payload`) for use with higher-level consumers. |
| `backend/routes/ws.py` | **New.** WebSocket endpoint at `/ws/aide/{aide_id}`. Accepts client connections, receives `{type:"message",content,message_id}` messages, streams MockLLM golden files through the v2 reducer, emits `EntityDelta`, `VoiceDelta`, and `StreamStatus` messages. |
| `backend/main.py` | **Modified.** Registered `ws_routes.router` so the WebSocket endpoint is live. |

### Tests

| File | Tests | Description |
|------|-------|-------------|
| `backend/tests/test_jsonl_parser.py` | 22 | Covers single-line parsing, partial buffering, malformed line skipping, abbreviation expansion, and flush behavior. |
| `backend/tests/test_ws.py` | 12 | Integration tests for the WebSocket endpoint — connection acceptance, stream.start/end protocol, entity.create delta delivery, voice delta delivery, auto message_id generation, malformed client JSON handling, scenario routing. |

### Frontend

| File | Change |
|------|--------|
| `frontend/index.html` | **Modified.** Added entity store (vanilla JS), FallbackDisplay HTML renderer, WebSocket client class. The chat's `sendMessage` now tries WebSocket first (streaming entity deltas live) and falls back to HTTP. Entity deltas update the preview frame in real-time as they arrive. |

---

## Architecture Notes

### Key Design Decision: v2 Reducer Format
The golden files use the v2 compact format (`t` for type, `p` for props, `id`, `parent`, `display` at top level). The `reducer_v2.reduce()` function expects events in this raw format (it reads `event.get("t")`). The WS endpoint passes raw parsed JSONL objects directly to the reducer — no abbreviation expansion needed for the reducer path.

The `JSONLParser` still expands abbreviations (for higher-level consumers that need the full key names), but `ws.py` bypasses it and parses JSONL lines directly with `json.loads()`.

### WebSocket Protocol
```
Client → Server: {"type":"message","content":"...","message_id":"<uuid>"}
Server → Client: {"type":"stream.start","message_id":"..."}
Server → Client: {"type":"entity.create","id":"...","data":{...}}  (0..N)
Server → Client: {"type":"voice","text":"..."}                      (0..N)
Server → Client: {"type":"stream.end","message_id":"..."}
```

### Frontend Entity Store
The entity store is a plain JS object on the `window` scope (no framework dependency). It holds `entities: {}` and `rootIds: []`. `applyDelta()` handles create/update/remove. `getChildren(parentId)` returns child IDs. On `stream.start`, the store is reset for a fresh message.

### Scenario Routing
The WS server picks a golden file based on message content keywords. Unknown content defaults to `create_graduation`. Available scenarios: `create_graduation`, `create_poker`, `create_inspo`, `create_football_squares`, `create_group_trip`, `update_simple`.

---

## File Structure (New/Modified)

```
backend/
├── routes/
│   └── ws.py                    # NEW — WebSocket endpoint
├── services/
│   └── jsonl_parser.py          # NEW — JSONL stream parser
├── tests/
│   ├── test_jsonl_parser.py     # NEW — 22 tests
│   └── test_ws.py               # NEW — 12 tests
└── main.py                      # MODIFIED — added ws_routes

frontend/
└── index.html                   # MODIFIED — entity store, WS client, FallbackDisplay
```

---

## Security Checklist Compliance

- **No SQL in routes.** `ws.py` contains zero SQL — it's pure in-memory state.
- **No f-strings in SQL.** Not applicable (no SQL in this phase).
- **Pydantic models.** WebSocket messages are parsed via `json.loads` + plain dict access; no user input reaches SQL. Input is bounded (JSONL line ≤200 chars logged, otherwise silently skipped).
- **Auth.** WebSocket endpoint intentionally unauthenticated for Phase 1 (MockLLM, no DB state mutations from WS). Production will add JWT-from-cookie auth before Phase 2.
- **No XSS.** FallbackDisplay uses `escapeHtml()` on all entity values before inserting into `srcdoc`.
- **No eval.** Zero use of `eval`, `innerHTML` with unescaped data, or `Function()`.

---

## Verification

### Lint
```
ruff check backend/   → All checks passed!
ruff format --check   → 57 files already formatted
```

### Tests
```
backend/tests/test_jsonl_parser.py   22 passed
backend/tests/test_ws.py             12 passed
engine/kernel/tests/                 1065 passed, 4 skipped
  (9 pre-existing postgres_storage event-loop failures, unrelated)
```

---

## Checkpoint Criteria Status

| Criterion | Status |
|-----------|--------|
| WebSocket endpoint accepts connections and receives messages | ✅ |
| JSONL parser correctly buffers and expands abbreviations | ✅ |
| WS server streams MockLLM → v2 reducer → entity deltas | ✅ |
| Frontend store receives and applies deltas | ✅ |
| FallbackDisplay renders entity tree as key-value pairs | ✅ |
| Voice deltas delivered to chat history | ✅ |
| Malformed input handled gracefully | ✅ |
| All new tests pass | ✅ |

---

## Measurements (MockLLM instant profile)

| Metric | Result |
|--------|--------|
| ttfc (mock, instant) | <5ms (first entity delta) |
| ttc (mock, instant) | <50ms (full graduation scenario) |
| WebSocket latency | <5ms round-trip (TestClient) |

---

## Next Steps

- **Phase 1.2:** Authentication on WebSocket (JWT from cookie via query param or subprotocol)
- **Phase 1.3:** Wire real LLM (L2/L3 orchestrator) to WebSocket instead of MockLLM
- **Phase 1.4:** Persist WS-delivered state to DB; reconnect from saved snapshot
- **Phase 2:** Rate limiting (50 turns/week free), turn counting per user
- **Phase 3:** Stripe payments, Pro tier

---

**✅ Phase 1 Vertical Slice Complete — 2026-02-19**
