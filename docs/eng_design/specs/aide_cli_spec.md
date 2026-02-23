# AIde CLI Spec

**Status:** Design
**Phase:** Post-launch (developer tool)
**Date:** 2026-02-22

## Overview

A terminal REPL for talking to AIde. Runs in a dedicated tab. Another "ear" — same orchestrator, different input surface. Authenticates via device authorization flow (like Claude Code), then provides a persistent session for jotting ideas, updating aides, and managing pages without opening a browser.

## UX

```
$ aide login
→ Opening browser: get.toaide.com/cli/auth?code=Kx9mPq
  Waiting for authorization... ✓
  Authenticated as zach@toaide.com
  Token saved to ~/.aide/config.json

$ aide
aide > running a basketball league, 8 teams
  Next step: draft order.

aide > mike's team beat dave's 88-72
  Standings updated. Mike: 3-1. Dave: 2-2.

aide > /switch budget
  Switched to: Home Renovation Budget

aide > granite countertops came in at $4,200
  Countertops: $4,200. Total: $18,350 of $25,000.

aide > /list
  1. Basketball League        (last: 2 min ago)
  2. Home Renovation Budget   (last: just now)
  3. Sophie's Graduation      (last: 3 days ago)

aide > /page
  → Opening toaide.com/s/basketball-league

aide > /new
  New aide started. Say what you're running.

aide > /quit
```

---

## Device Authorization Flow

### Sequence

```
aide login
    │
    ├─► POST /api/cli/auth/start
    │   Body: { device_code: "Kx9mPq" }
    │   Response: { auth_url, device_code, expires_at }
    │
    ├─► Opens auth_url in default browser
    │
    ├─► Polls POST /api/cli/auth/poll every 2s
    │   Body: { device_code: "Kx9mPq" }
    │   Response: { status: "pending" } or { status: "approved", token: "..." }
    │
    │   ┌──────── Browser ────────┐
    │   │                         │
    │   │  User lands on auth page│
    │   │  If not logged in:      │
    │   │    → magic link flow    │
    │   │  If logged in:          │
    │   │    → "Authorize CLI?"   │
    │   │    → [Confirm]          │
    │   │                         │
    │   │  POST /api/cli/auth/confirm
    │   │  Body: { device_code }  │
    │   │  (session cookie auth)  │
    │   └─────────────────────────┘
    │
    └─► Poll returns approved + API token
        Save to ~/.aide/config.json
        Done.
```

### Why Not Just Paste a JWT?

JWTs expire in 24 hours. A CLI token should last 90 days and be independently revocable. The device flow also avoids exposing tokens in terminal history or clipboard.

---

## Data Model

### Table: `cli_auth_requests`

```sql
CREATE TABLE cli_auth_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_code TEXT NOT NULL UNIQUE,         -- 6-char alphanumeric
    user_id UUID REFERENCES users(id),        -- NULL until confirmed
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | expired
    api_token TEXT,                           -- set on approval
    expires_at TIMESTAMPTZ NOT NULL,          -- 10 min TTL for auth flow
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Cleanup: delete expired rows daily
-- Index: device_code (unique constraint covers it)
```

### Table: `api_tokens`

```sql
CREATE TABLE api_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    token_hash TEXT NOT NULL UNIQUE,          -- SHA-256 of token (never store raw)
    name TEXT NOT NULL DEFAULT 'cli',         -- human label
    scope TEXT NOT NULL DEFAULT 'cli',        -- cli | api (future)
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,          -- 90 days from creation
    revoked BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- RLS: users can only see/revoke their own tokens
ALTER TABLE api_tokens ENABLE ROW LEVEL SECURITY;
CREATE POLICY api_tokens_user_policy ON api_tokens
    USING (user_id = current_setting('app.current_user_id')::uuid);
```

**Token format:** `aide_` prefix + 32 random bytes hex = `aide_a1b2c3d4...` (69 chars). Stored as SHA-256 hash. The raw token is shown once at creation and never again.

---

## API Endpoints

### POST /api/cli/auth/start

Start a device authorization flow. Unauthenticated.

**Request:**
```json
{
  "device_code": "Kx9mPq"
}
```

**Response:** 200
```json
{
  "auth_url": "https://get.toaide.com/cli/auth?code=Kx9mPq",
  "device_code": "Kx9mPq",
  "expires_at": "2026-02-22T12:10:00Z"
}
```

**Rate limit:** 10 per IP per hour.

**Errors:**
- 429: Rate limited
- 409: Device code already in use (client should regenerate)

---

### POST /api/cli/auth/poll

Check if device authorization has been approved. Unauthenticated.

**Request:**
```json
{
  "device_code": "Kx9mPq"
}
```

**Response (pending):** 200
```json
{
  "status": "pending"
}
```

**Response (approved):** 200
```json
{
  "status": "approved",
  "token": "aide_a1b2c3d4e5f6..."
}
```

**Response (expired):** 200
```json
{
  "status": "expired"
}
```

**Rate limit:** 30 per device_code per minute (prevents aggressive polling). Client polls every 2 seconds.

**Errors:**
- 404: Unknown device code
- 429: Polling too fast

---

### POST /api/cli/auth/confirm

Approve a device authorization. **Requires session cookie** (browser-authenticated).

**Request:**
```json
{
  "device_code": "Kx9mPq"
}
```

**Response:** 200
```json
{
  "status": "approved",
  "email": "zach@toaide.com"
}
```

**Side effects:**
- Creates row in `api_tokens` (hashed)
- Updates `cli_auth_requests` with user_id, status=approved, api_token
- Token is returned via poll, not via this endpoint

**Errors:**
- 401: Not logged in (redirect to magic link flow first)
- 404: Unknown or expired device code
- 409: Already approved

---

### Browser Auth Page

**Route:** `GET /cli/auth?code={device_code}`

Served by the frontend (or a simple standalone HTML page).

**Flow:**
1. Page loads, checks for session cookie via `GET /auth/me`
2. If not authenticated → show "Sign in first" with magic link form. After sign-in, redirect back to this page.
3. If authenticated → show "Authorize CLI session?" with device code displayed, user email shown, and a **Confirm** button
4. On confirm → `POST /api/cli/auth/confirm`, show "✓ You can close this tab"

**Security:** Page displays the device code so user can verify it matches their terminal. Prevents phishing via substitute URLs.

---

## CLI Authentication for API Calls

Once authenticated, the CLI includes the token in all requests:

```
Authorization: Bearer aide_a1b2c3d4e5f6...
```

**Backend token resolution** (new auth dependency):

```python
async def get_current_user_from_token(
    authorization: str = Header(None),
) -> User:
    """Resolve API token to user. Used by CLI."""
    if not authorization or not authorization.startswith("Bearer aide_"):
        raise HTTPException(401)
    token = authorization.removeprefix("Bearer ")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    row = await api_token_repo.get_by_hash(token_hash)
    if not row or row.revoked or row.expires_at < now():
        raise HTTPException(401)
    await api_token_repo.touch_last_used(row.id)
    return await user_repo.get_by_id(row.user_id)
```

**Unified auth dependency** — existing routes need no changes:

```python
async def get_current_user(
    request: Request,
    authorization: str = Header(None),
) -> User:
    """Try session cookie first, then Bearer token."""
    if authorization and authorization.startswith("Bearer aide_"):
        return await get_current_user_from_token(authorization)
    return await get_current_user_from_cookie(request)
```

This means the CLI uses the same `POST /api/message` endpoint as the web UI. No new message routes needed.

---

## CLI Client

### Installation

```bash
pip install aide-cli
# or from repo:
pip install -e ./cli
```

Single entry point: `aide`

### Top-Level Help (`aide --help`)

```
Usage: aide [options] [command]

Commands:
  login           Authenticate via browser
  logout          Revoke token and clear config
  (none)          Enter REPL

Options:
  --api-url URL   Override API endpoint (default: https://get.toaide.com)
  --aide ID       Start REPL with specific aide
  -h, --help      Show this help
  -v, --version   Show version
```

```
$ aide login --help
Usage: aide login [options]

Authenticate this CLI session via browser.

Options:
  --api-url URL   Override API endpoint
  -h, --help      Show this help
```

| Command | Action |
|---------|--------|
| `aide login` | Device auth flow |
| `aide logout` | Delete local config + revoke token |
| `aide` | Enter REPL (default aide or last used) |
| `aide --aide <id>` | Enter REPL with specific aide |
| `aide --help` | Show top-level help |
| `aide --version` | Print version |

### REPL Commands (`/help`)

```
aide > /help

Commands:
  /list           Show your aides
  /switch <n>     Switch to a different aide
  /new            Start a new aide
  /page           Open published page in browser
  /info           Current aide details
  /history [n]    Show last n messages (default 10)
  /help           Show this help
  /quit           Exit (or Ctrl-D)

Everything else is sent as a message to the current aide.
```

| Command | Action |
|---------|--------|
| `/list` | Show user's aides with last activity |
| `/switch <n>` | Switch to a different aide |
| `/new` | Start a new aide |
| `/page` | Open published URL in browser |
| `/info` | Show current aide details (slug, created, turn count) |
| `/history [n]` | Show last n messages (default 10) |
| `/help` | Print REPL command reference |
| `/quit` or Ctrl-D | Exit |

Everything else is sent as a message to the current aide.

### Local Config

```json
// ~/.aide/config.json
{
  "token": "aide_a1b2c3d4e5f6...",
  "email": "zach@toaide.com",
  "default_aide_id": "550e8400-...",
  "api_url": "https://get.toaide.com"
}
```

### Dependencies

Minimal. Python 3.10+.

- `httpx` — HTTP client
- `readline` (stdlib) — input history, line editing
- No TUI framework. No rich. Raw `input()` + ANSI escape codes for minimal color.

### REPL Loop

```python
while True:
    line = input("aide > ").strip()
    if not line:
        continue
    if line.startswith("/"):
        handle_command(line)
        continue
    response = client.post("/api/message", json={
        "aide_id": current_aide_id,
        "message": line,
    })
    data = response.json()
    if not current_aide_id:
        current_aide_id = data["aide_id"]  # new aide created
    print(f"  {data['response_text']}")
```

---

## Token Management

### Dashboard UI (future, not blocking CLI)

Users can view and revoke CLI tokens from the web dashboard:

```
GET  /api/tokens         → list user's active tokens
DELETE /api/tokens/{id}  → revoke a token
```

### Token Lifecycle

| Event | Action |
|-------|--------|
| `aide login` | Create token (90-day expiry) |
| `aide logout` | Revoke token + delete local config |
| Token expires | CLI gets 401, prompts re-login |
| User revokes in dashboard | CLI gets 401, prompts re-login |
| 401 during REPL | Print "Session expired. Run `aide login`." and exit |

---

## Security

- **Token storage:** `~/.aide/config.json` with `0600` permissions (owner-only read/write)
- **Token hashing:** Raw token never stored server-side. SHA-256 hash only.
- **Token prefix:** `aide_` prefix allows secret scanners (GitHub, GitGuardian) to flag leaked tokens
- **Device code TTL:** 10 minutes. Expired codes cleaned up by background task.
- **Polling rate limit:** Prevents brute-force guessing of device codes
- **No token in URL:** Token transmitted only via Authorization header, never query params
- **Revocation:** Immediate. Token check hits DB on every request (cache later if needed)

---

## Rate Limiting

CLI users share the same per-user rate limits as web users:

| Limit | Value |
|-------|-------|
| API requests | 100/min per user |
| AI turns | 50/week (free) or unlimited (pro) |
| Aide creation | 10/hour per user |

The CLI `source` field is set to `"cli"` in orchestrator calls for telemetry segmentation.

---

## Files to Create

| File | Purpose |
|------|---------|
| `alembic/versions/XXX_add_cli_auth.py` | Migration: cli_auth_requests + api_tokens tables |
| `backend/models/api_token.py` | Pydantic models |
| `backend/models/cli_auth.py` | Pydantic request/response models |
| `backend/repos/api_token_repo.py` | Token CRUD (hashed storage) |
| `backend/repos/cli_auth_repo.py` | Device auth request CRUD |
| `backend/routes/cli_auth.py` | start, poll, confirm endpoints |
| `backend/routes/api_tokens.py` | list, revoke endpoints |
| `frontend/cli-auth.html` | Browser authorization page |
| `cli/` | CLI package root |
| `cli/aide_cli/__init__.py` | Package init |
| `cli/aide_cli/main.py` | Entry point, arg parsing |
| `cli/aide_cli/auth.py` | Device auth flow |
| `cli/aide_cli/repl.py` | REPL loop + commands |
| `cli/aide_cli/client.py` | HTTP client wrapper |
| `cli/aide_cli/config.py` | Config file read/write |
| `cli/pyproject.toml` | Package metadata, `aide` entry point |

## Files to Modify

| File | Changes |
|------|---------|
| `backend/auth.py` | Unified `get_current_user` — try cookie, then Bearer token |
| `backend/main.py` | Register cli_auth + api_tokens routers |
| `backend/config.py` | Add `CLI_TOKEN_EXPIRY_DAYS = 90` |

## Existing (No Changes)

- `backend/routes/conversations.py` — `POST /api/message` works as-is
- `backend/services/orchestrator.py` — already supports `source` parameter
- `backend/routes/aides.py` — list/CRUD works with Bearer auth once `get_current_user` is unified

---

## Testing Plan

### Unit Tests (CI — `pytest cli/`)

- Token hashing: raw → SHA-256 → lookup round-trip
- Device code generation: uniqueness, format, length
- Config file: read/write, `0600` permissions enforcement
- Command routing: `/list`, `/switch`, `/new` dispatch correctly
- Client wrapper: verifies correct endpoints called, Authorization header set

### Integration Tests (CI — `pytest backend/tests/test_cli_auth.py`)

- Full device auth flow: start → confirm → poll returns token
- Token auth: valid token → user resolved
- Token auth: expired token → 401
- Token auth: revoked token → 401
- Token auth: malformed token → 401
- Unified auth: cookie still works when Bearer absent
- Unified auth: Bearer takes precedence when both present
- Rate limiting on poll endpoint
- Device code expiry: confirm after 10 min → 404
- RLS: user A cannot see/revoke user B's tokens
- `POST /api/message` with Bearer token → aide created, response returned
- `source: "cli"` recorded in telemetry

```python
# Example: full device auth flow (no browser needed)
async def test_device_auth_full_flow(client, test_user_jwt):
    # 1. Start
    r = await client.post("/api/cli/auth/start",
        json={"device_code": "TEST01"})
    assert r.status_code == 200

    # 2. Poll — pending
    r = await client.post("/api/cli/auth/poll",
        json={"device_code": "TEST01"})
    assert r.json()["status"] == "pending"

    # 3. Confirm (simulates browser with session cookie)
    r = await client.post("/api/cli/auth/confirm",
        json={"device_code": "TEST01"},
        cookies={"session": test_user_jwt})
    assert r.json()["status"] == "approved"

    # 4. Poll — approved
    r = await client.post("/api/cli/auth/poll",
        json={"device_code": "TEST01"})
    assert r.json()["status"] == "approved"
    token = r.json()["token"]
    assert token.startswith("aide_")

    # 5. Use token on existing endpoint
    r = await client.get("/api/aides",
        headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
```

### Local Dev

CLI takes `--api-url` flag (or `AIDE_API_URL` env var) to override the default:

```bash
aide login --api-url http://localhost:8000
```

Browser opens `localhost:8000/cli/auth?code=Kx9mPq`. Local session cookie authorizes the confirm. Full flow works because browser and CLI hit the same backend.

### Staging

Points at staging URL — exercises the real Resend email path end-to-end:

```bash
aide login --api-url https://staging.toaide.com
```

Real magic link → real browser confirm → real token. Best end-to-end coverage of the full auth chain. Verify `source: "cli"` appears in telemetry to confirm CLI traffic is segmented from web.

### Smoke Test Script

```bash
#!/bin/bash
# scripts/test_cli_smoke.sh — quick validation against any environment
API_URL=${1:-http://localhost:8000}

echo "=== Token auth ==="
curl -sf -H "Authorization: Bearer $AIDE_TOKEN" \
  "$API_URL/api/aides" | jq '.[] | .title' || echo "FAIL: /api/aides"

echo "=== Message via token ==="
curl -sf -X POST -H "Authorization: Bearer $AIDE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "smoke test from cli"}' \
  "$API_URL/api/message" | jq '.response_text' || echo "FAIL: /api/message"

echo "=== Auth endpoints ==="
curl -sf -X POST -H "Content-Type: application/json" \
  -d '{"device_code": "SMOKE1"}' \
  "$API_URL/api/cli/auth/start" | jq '.auth_url' || echo "FAIL: /auth/start"

echo "Done."
```

### E2E (Manual — pre-launch checklist)

- `aide login` → browser opens → confirm → CLI authenticated
- Send message via CLI → aide state updates → published page reflects change
- `/list` shows aides, `/switch` changes context, `/page` opens browser
- `aide logout` → token revoked → subsequent requests return 401
- Re-run `aide login` → fresh token works
- Token expires (set short TTL in test) → CLI prints "Session expired" and exits

---

## What's Explicitly Not in v1

- **Streaming responses** — CLI prints full response after completion. Streaming adds complexity for marginal UX gain in a dev tool.
- **Image input** — Text only. Use the web UI for images.
- **Tab completion for aide names** — Nice-to-have, not blocking.
- **Multiple token management in CLI** — One token per machine. `aide logout && aide login` to switch accounts.
- **Offline mode** — Always requires network.
- **Shell integration** — No piping stdin/stdout. Interactive REPL only.
