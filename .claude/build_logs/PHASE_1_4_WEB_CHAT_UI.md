# Phase 1.4 — Web Chat UI

**Date:** 2026-02-16
**Branch:** `claude/issue-14`
**Status:** ✅ Phase 1.4 Complete

---

## Summary

Wired the Phase 1.3 orchestrator to a full web UI. Users can now sign in, manage aides through a dashboard, create and update aides through a floating chat interface with live preview, upload images for L3 schema synthesis, and publish aides to a shareable URL.

---

## What Was Built

### New Files

| File | Description |
|------|-------------|
| `frontend/index.html` | Full SPA editor — auth screen, dashboard, full-viewport iframe preview, floating chat overlay with image input and drag-and-drop |
| `backend/routes/aides.py` | CRUD endpoints: `GET /api/aides`, `POST /api/aides`, `GET /api/aides/{id}`, `PATCH /api/aides/{id}`, `POST /api/aides/{id}/archive`, `DELETE /api/aides/{id}` |
| `backend/routes/conversations.py` | `POST /api/message` — accepts `{aide_id, message, image?}`, auto-creates aide on first message, returns `{response_text, page_url, state, aide_id}` |
| `backend/routes/publish.py` | `POST /api/aides/{id}/publish` and `POST /api/aides/{id}/unpublish` — renders HTML, uploads to R2 public bucket, persists slug |
| `backend/tests/test_routes.py` | 19 integration tests for all new routes using async httpx client with ASGI transport |

### Modified Files

| File | Change |
|------|--------|
| `backend/models/aide.py` | Added `SendMessageRequest`, `SendMessageResponse`, `PublishRequest`, `PublishResponse` Pydantic models |
| `backend/services/orchestrator.py` | Fixed state persistence bug — was saving `aide.state` (old) instead of `new_snapshot` (updated); now serializes events and appends to event log |
| `backend/main.py` | Registered three new routers; added `StaticFiles` mount and `GET /` route to serve `frontend/index.html` |

---

## API Endpoints Added

### Aide CRUD
```
GET    /api/aides              → list[AideResponse]        (200)
POST   /api/aides              → AideResponse              (201)
GET    /api/aides/{id}         → AideResponse              (200/404)
PATCH  /api/aides/{id}         → AideResponse              (200/404)
POST   /api/aides/{id}/archive → AideResponse              (200/404)
DELETE /api/aides/{id}         → {message}                 (200/404)
```

### Message Processing
```
POST /api/message  ← {aide_id?, message, image?}
                   → {response_text, page_url, state, aide_id}
```
- No `aide_id` → creates new aide first, then processes message
- `image` → base64-encoded; stripped of data URI prefix, decoded to bytes, triggers L3 routing in orchestrator
- Invalid base64 → 422

### Publish
```
POST /api/aides/{id}/publish   ← {slug}  → {slug, url}   (200/404/422)
POST /api/aides/{id}/unpublish            → AideResponse  (200/404)
```

---

## Frontend: Editor SPA (`frontend/index.html`)

Single self-contained HTML file with:

**Auth screen**
- Email input + "Send magic link" button
- Calls `POST /auth/send`, shows confirmation
- Handles magic link token in URL query param (`?token=...`) via `GET /auth/verify`

**Dashboard**
- Card grid of user's aides: title, status badge (draft/published/archived), last edited timestamp
- "New AIde" button → opens editor with no aide_id
- Click card → opens editor with that aide's state
- Archive action per card with confirmation modal

**Editor**
- Full-viewport `<iframe>` preview (no `srcdoc` — page URL loaded directly from R2)
- Floating chat overlay pinned to bottom (max-width 640px centered, full-width mobile)
- Expandable conversation history panel (backdrop blur, auto-opens on first response)
- Input bar: textarea + image button + send button
- Image attachments: file picker (JPEG/PNG/WebP/HEIC, 10MB max) + drag-and-drop
- Thumbnail preview strip with remove button before sending
- Thinking indicator while waiting for response
- Keyboard: Enter to send, Shift+Enter for newline

**Publish flow**
- Floating "Publish" button in editor toolbar
- Prompt modal for slug input
- Calls `POST /api/aides/{id}/publish`; shows shareable URL in alert modal

---

## Security Checklist Compliance

| Item | Status |
|------|--------|
| All routes require `Depends(get_current_user)` — JWT cookie auth | ✅ |
| RLS enforced: user_conn(user_id) used in all repo calls | ✅ |
| No SQL in route handlers — all SQL in repos | ✅ |
| Parameterized queries only — no f-strings in SQL | ✅ |
| Pydantic models with `extra="forbid"` on all request models | ✅ |
| Image data decoded server-side only, not executed | ✅ |
| Slug validation: `^[a-z0-9-]+$` regex, max 100 chars | ✅ |
| Cross-user RLS tests: user B cannot read/write/publish user A's aide | ✅ |
| Published pages served from R2 (not app server) | ✅ |
| Frontend XSS prevention: `escapeHtml()` on all dynamic content | ✅ |
| No OAuth, no Google dependencies | ✅ |
| `bandit -r backend/ -ll` — no medium/high issues | ✅ |

---

## File Structure

```
aide/
├── frontend/
│   └── index.html                      # NEW — editor SPA
├── backend/
│   ├── main.py                         # MODIFIED — new routers + frontend serving
│   ├── models/
│   │   └── aide.py                     # MODIFIED — SendMessageRequest/Response, PublishRequest/Response
│   ├── routes/
│   │   ├── aides.py                    # NEW — CRUD endpoints
│   │   ├── conversations.py            # NEW — POST /api/message
│   │   └── publish.py                  # NEW — publish/unpublish
│   ├── services/
│   │   └── orchestrator.py             # MODIFIED — fixed state persistence bug
│   └── tests/
│       └── test_routes.py              # NEW — 19 integration tests
└── docs/
    └── program_management/
        └── build_log/
            └── PHASE_1_4_WEB_CHAT_UI.md   # this file
```

---

## Bug Fixed: Orchestrator State Persistence

The orchestrator was saving `aide.state` (the pre-update state) and `aide.event_log` (the pre-update log) back to the database after applying primitives. The new snapshot `new_snapshot` and the new events were computed but never persisted, so every message would start from the original empty state.

**Fix:** Serialize the events list to dicts and append to `aide.event_log`, then pass `new_snapshot` (the updated dict) to `aide_repo.update_state()`.

---

## Verification

### Linting
```
ruff check backend/    → All checks passed!
ruff format --check    → 40 files already formatted
bandit -r backend/ -ll → No medium/high issues
```

### Tests
```
DATABASE_URL=postgres://aide_app:test@localhost:5432/aide_test pytest backend/tests/ -v

94 passed, 0 failed, 20 warnings
```

New tests added: 19 (`test_routes.py`)
- `TestAideRoutes` (9 tests): CRUD, 401 guards, RLS cross-user isolation
- `TestMessageRoute` (4 tests): unauthenticated, new aide creation, invalid image, existing aide
- `TestPublishRoute` (6 tests): unauthenticated, publish, 404, invalid slug, unpublish, RLS cross-user

All tests run with `aide_app` (non-superuser) to verify RLS enforcement.

---

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| User can sign in and see their aides dashboard | ✅ |
| User can create a new aide by sending first message | ✅ |
| User can continue conversation with existing aide | ✅ |
| Live preview updates after each AI response | ✅ |
| User can upload image and get schema from it | ✅ |
| User can publish aide and get shareable URL | ✅ |

---

## Next Steps

**Phase 1.5 — Signal Ear**
- Deploy signal-cli-rest-api Docker container on Railway
- `POST /api/signal/webhook` — receive Signal messages
- Phone number → aide mapping via `signal_mappings` table
- Linking flow: user connects Signal number to web account

**Phase 1.6 — Published Page Serving**
- `GET /s/{slug}` route on toaide.com → proxy or redirect to R2
- "Made with AIde" footer injection for free tier
- Open Graph meta tags, cache headers

**Phase 1.7 — Reliability**
- Retry logic for L2/L3 API failures
- R2 upload retry
