# Issue #74: Convert frontend/index.html to React SPA with Vite

**Build Log**
Started: 2026-03-01
Status: In Progress

---

## Overview

Converting the monolithic `frontend/index.html` (1,500+ lines of vanilla JS) to a React SPA using Vite. Following Red/Green TDD approach:
1. Write failing tests first (RED)
2. Implement components to make tests pass (GREEN)
3. Verify behavioral parity with current implementation

---

## Phase 0: RED — Scaffold and snapshot current behavior

### 0.1 Initialize Vite project ✅
- [ ] Create Vite project with React template
- [ ] Install dependencies
- [ ] Configure vite.config.js
- [ ] Configure vitest

### 0.2 Snapshot current index.html behavior
**Current screens/views:**
1. **Auth screen** — email input + magic link flow
2. **Dashboard** — aide grid, new aide button, empty state
3. **Editor** — header + preview + chat overlay

**API calls:**
- `GET /auth/me` — session check
- `POST /auth/send` — send magic link
- `GET /auth/verify?token=...` — verify magic link
- `POST /auth/logout` — logout
- `GET /api/aides` — list aides
- `GET /api/aides/{id}` — fetch aide
- `POST /api/aides` — create aide
- `PATCH /api/aides/{id}` — update aide
- `POST /api/aides/{id}/archive` — archive aide
- `DELETE /api/aides/{id}` — delete aide
- `POST /api/message` — send message
- `POST /api/aides/{id}/publish` — publish
- `POST /api/aides/{id}/unpublish` — unpublish

**WebSocket messages:**
- Sent: `{ type: "message", content, message_id }`
- Sent: `{ type: "direct_edit", entity_id, field, value }`
- Received: `entity.create`, `entity.update`, `entity.remove`
- Received: `voice`, `stream.start`, `stream.end`
- Received: `direct_edit.ack`, `direct_edit.error`

**Chat overlay states:**
- `hidden` — only pull-up handle visible
- `input` — input bar visible (default on load)
- `expanded` — input + message history (max 60% viewport)

### 0.3 Write failing tests for hooks
- [ ] useAuth.test.js
- [ ] useAide.test.js
- [ ] useWebSocket.test.js

### 0.4 Write failing tests for components
- [ ] Dashboard.test.jsx
- [ ] Editor.test.jsx
- [ ] EditorHeader.test.jsx
- [ ] Preview.test.jsx
- [ ] ChatOverlay.test.jsx
- [ ] ChatInput.test.jsx
- [ ] AuthScreen.test.jsx
- [ ] App.test.jsx

---

## Phase 1: GREEN — Build the foundation

### 1.1 Theme + CSS setup
- [ ] Create theme.css with CSS custom properties
- [ ] Create editor.css
- [ ] Create chat.css
- [ ] Create dashboard.css

### 1.2 API layer (src/api.js)
- [ ] Implement all API functions

### 1.3 WebSocket client (src/ws.js)
- [ ] Extract from current index.html
- [ ] Add auto-reconnect logic

### 1.4 Hooks
- [ ] useAuth
- [ ] useAide
- [ ] useWebSocket

---

## Phase 2: GREEN — Build the views

### 2.1 App + Router
- [ ] BrowserRouter setup
- [ ] Protected routes
- [ ] Auth redirect logic

### 2.2 Dashboard
- [ ] Aide grid
- [ ] Empty state
- [ ] Create/archive actions

### 2.3 Editor shell
- [ ] Layout
- [ ] WS connection
- [ ] State management

### 2.4 Preview
- [ ] dangerouslySetInnerHTML rendering
- [ ] Scroll preservation
- [ ] Inline editing
- [ ] Link interception

### 2.5 Chat overlay
- [ ] Three-state system (hidden/input/expanded)
- [ ] Auto-collapse logic
- [ ] Message history
- [ ] Image attachment

### 2.6 Editor header
- [ ] Dashboard link
- [ ] Inline title edit

### 2.7 Auth screen
- [ ] Magic link flow
- [ ] Token verification

---

## Phase 3: GREEN — Mobile + responsive

### 3.1 Mobile chat
- [ ] Bottom sheet behavior
- [ ] Touch gestures
- [ ] iOS safe area

### 3.2 Responsive breakpoints
- [ ] Desktop (≥1024px)
- [ ] Tablet (768-1023px)
- [ ] Mobile (<768px)

---

## Phase 4: Backend integration

### 4.1 Serve SPA from backend
- [ ] Build pipeline
- [ ] Catch-all route in FastAPI
- [ ] Static asset serving

### 4.2 Hydration endpoint
- [ ] GET /api/aides/{id}/hydrate

---

## Phase 5: Verify + cut over

### 5.1 Visual regression
- [ ] Screenshot comparison

### 5.2 Integration test checklist
- [ ] Auth flow
- [ ] Dashboard → editor
- [ ] Chat → preview updates
- [ ] Direct edit
- [ ] Browser back

### 5.3 Cut over
- [ ] Delete old index.html
- [ ] Update backend serving
- [ ] Update Railway build
- [ ] Update CI

---

## Files Created
(Will be updated as files are created)

## Files Modified
(Will be updated as files are modified)

## Tests Added
(Will be updated as tests are added)

## Issues Encountered
(Will be updated as issues arise)

---

**End of log**
