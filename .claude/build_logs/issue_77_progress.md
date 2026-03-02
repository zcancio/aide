# Issue 77 (Phase 2): Extract JS Modules - Build Log

## Summary

Successfully extracted reusable logic from `index.html` into importable ES modules in `frontend/src/lib/`. Followed TDD approach (RED → GREEN). All 40 tests passing.

## Files Created

### Test Files (RED Phase)
- `frontend/src/lib/__tests__/api.test.js` - 17 tests for API client
- `frontend/src/lib/__tests__/ws.test.js` - 12 tests for WebSocket client
- `frontend/src/lib/__tests__/entity-store.test.js` - 10 tests for entity store

### Implementation Files (GREEN Phase)
- `frontend/src/lib/api.js` - API client with fetch wrappers
- `frontend/src/lib/ws.js` - WebSocket client class
- `frontend/src/lib/entity-store.js` - Immutable entity state management

## Commits

1. **test: failing tests for lib modules (api, ws, entity-store)**
   - Commit: `19acca1`
   - All tests fail (modules don't exist yet)
   - RED phase complete

2. **feat: extract api, ws, entity-store modules (all tests green)**
   - Commit: `ccd533f`
   - All 40 tests passing
   - GREEN phase complete

## Test Results

```
Test Files  4 passed (4)
Tests       40 passed (40)
```

### Test Breakdown
- `api.test.js`: 17 tests (all ✓)
  - fetchAides, fetchAide, createAide, updateAide
  - archiveAide, deleteAide, sendMessage
  - publishAide, unpublishAide
  - sendMagicLink, verifyToken, fetchMe, logout
  - Error handling for 4xx/5xx responses
  - Credential inclusion verification

- `ws.test.js`: 12 tests (all ✓)
  - WebSocket connection and URL construction
  - Message routing (delta, meta, voice, status)
  - Snapshot buffering between start/end
  - Direct edit error handling
  - Send/disconnect functionality
  - Auto-reconnect with backoff

- `entity-store.test.js`: 10 tests (all ✓)
  - Store creation and reset
  - Entity create/update/remove
  - Root vs child entity handling
  - Meta updates
  - Immutability guarantees

## Architecture

### api.js
- Thin fetch wrappers
- Returns `{ data }` on success or `{ error }` on failure
- Never throws - all errors returned
- All requests include `credentials: 'same-origin'`

### ws.js
- `AideWS` class with callback registration
- Message routing to typed callbacks
- Snapshot buffering (collect deltas between start/end)
- Auto-reconnect with exponential backoff (1s → 30s max)

### entity-store.js
- Pure functions: `createStore()`, `applyDelta()`, `resetStore()`
- Immutable - returns new objects, never mutates
- Handles entity.create/update/remove and meta.update
- Root entity tracking (no parent or parent === 'root')

## Notes

- `index.html` NOT modified (code duplicated, not moved)
- No imports from new modules yet - that's Phase 3
- Tests use vitest with jsdom environment
- All functions match patterns from `index.html`
- WebSocket reconnect tested with fake timers

## Compliance

✓ No files modified outside `frontend/src/lib/`
✓ All tests pass before committing
✓ Followed TDD (RED → GREEN)
✓ No functionality removed from `index.html`
✓ Immutability maintained in entity-store
✓ Error handling tested
