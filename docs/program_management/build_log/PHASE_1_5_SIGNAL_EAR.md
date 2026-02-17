# Phase 1.5: Signal Ear Implementation

## Overview

Implemented the Signal Ear integration, enabling users to update their AIde pages via Signal messages. Users link their phone number to an aide using a one-time 6-char code, then text updates directly.

## What Was Built

### A. Link Code Infrastructure

**Migration** (`alembic/versions/006_add_signal_link_codes.py`)
- New `signal_link_codes` table: `id`, `code`, `user_id`, `aide_id`, `expires_at`, `used`, `created_at`
- Indexed on `code` (fast lookup), `user_id`, and `expires_at` (cleanup)
- RLS enabled + forced; policy uses `get_app_user_id()` from migration 005
- Chained from migration 005 (not ccee0808c23a)

**Models** (`backend/models/signal_link_code.py`)
- `SignalLinkCode` — core model, 1:1 with table
- `CreateLinkCodeRequest` — `aide_id` only, `extra="forbid"`
- `LinkCodeResponse` — `code`, `aide_id`, `expires_at`, `signal_phone`

**Repo** (`backend/repos/signal_link_code_repo.py`)
- `create(user_id, aide_id)` — generates unique 6-char hex code (5 collision retries), 15-min TTL, `user_conn`
- `get_by_code(code)` — fetches active (not expired, not used) codes, `system_conn` (webhook caller)
- `mark_used(code_id)` — marks code consumed, `system_conn`
- `cleanup_expired()` — removes expired + used codes, returns delete count

### B. Signal Service Layer

**Config additions** (`backend/config.py`)
```python
SIGNAL_CLI_URL: str          # Default: "http://signal-cli:8080"
SIGNAL_PHONE_NUMBER: str     # AIde's Signal number in E.164
SIGNAL_WEBHOOK_SECRET: str   # HMAC-SHA256 webhook verification key
```

**Service** (`backend/services/signal_service.py`)
- `send_message(recipient, message, attachments?)` — POSTs to `/v2/send`
- `health_check()` — GETs `/v1/health`, returns bool
- Uses `httpx.AsyncClient` with 10s/5s timeouts
- Module-level `signal_service` singleton

### C. Signal Routes (`backend/routes/signal.py`)

| Endpoint | Auth | Description |
|----------|------|-------------|
| `POST /api/signal/webhook` | None (HMAC) | Receive inbound Signal messages |
| `POST /api/signal/link` | JWT cookie | Generate link code for an aide |
| `GET /api/signal/mappings` | JWT cookie | List user's Signal-linked aides |
| `GET /api/signal/mappings/{aide_id}` | JWT cookie | Check if aide is linked |
| `DELETE /api/signal/mappings/{aide_id}` | JWT cookie | Unlink Signal from aide |
| `GET /api/signal/phone` | None | Get AIde's Signal number |

**Webhook flow:**
1. Verify HMAC-SHA256 signature (`X-Signal-Signature` header); skip if `SIGNAL_WEBHOOK_SECRET` unset (dev)
2. Extract `envelope.sourceNumber` + `dataMessage.message`
3. Per-phone rate limit: 60 messages/hour via in-memory `RateLimiter`
4. If message matches `^[A-F0-9]{6}$` → link code flow
5. Else → lookup `signal_mappings` by phone → `orchestrator.process_message(source="signal")`
6. Reply via `signal_service.send_message()`

**Link code flow** (webhook handler):
- `get_by_code()` — validate active
- `conv_repo.create(channel="signal")` + `mapping_repo.create()` — persist mapping
- `mark_used()` — single-use enforcement
- Reply: "Connected! You can now text updates to your aide."

### D. main.py Updates

- Imports `SignalLinkCodeRepo` and `signal_routes`
- `cleanup_task` now also calls `signal_link_code_repo.cleanup_expired()` every 60s
- `app.include_router(signal_routes.router)` registered after publish_routes

### E. Existing Infrastructure (Unchanged)

- `signal_mappings` table and RLS — already in migration ccee0808c23a
- `SignalMappingRepo` — all CRUD already implemented
- `orchestrator.process_message(source="signal")` — already supported

## Tests

### `test_signal_link_code_repo.py` (8 tests)
- Create, get-by-code (active/expired/invalid), mark-used, cleanup
- RLS cross-user isolation: user B cannot read user A's codes
- Single-use enforcement

### `test_signal_service.py` (6 tests)
- `send_message` success, with attachments, HTTP error propagation
- `health_check` success, connection failure, non-200 response

### `test_signal_webhook.py` (6 tests)
- Link code flow creates mapping + marks used + sends confirmation
- Invalid link code sends error reply
- Unknown phone sends link-prompt
- Known phone routes to orchestrator
- Orchestrator error sends fallback reply
- RLS isolation: user B cannot see user A's aide (ownership check at route layer)

**Total: 20 new tests, 139 passing (full suite)**

## Quality Checks

- `ruff check backend/` — all checks passed
- `ruff format --check backend/` — 52 files already formatted
- `bandit -r backend/ -ll` — no medium/high severity issues
- Migration applied cleanly: `alembic upgrade 006`

## Railway Deployment Notes

The design doc describes adding signal-cli as a second Railway service:

```yaml
image: bbernhard/signal-cli-rest-api:latest
port: 8080
env:
  MODE: json-rpc
  AUTO_RECEIVE_SCHEDULE: "*/5 * * * *"
  CALLBACK_URL: "${EDITOR_URL}/api/signal/webhook"
volumes:
  /home/.local/share/signal-cli: signal-data
```

Phone number registration is a one-time manual step (exec into container, `signal-cli register + verify`). Not automated — requires Twilio number (~$1/month for SMS capability).

## Security

- Webhook: HMAC-SHA256 verification (configurable, skipped in dev when `SIGNAL_WEBHOOK_SECRET` is empty)
- Rate limiting: 60 messages/phone/hour via in-memory `RateLimiter`
- Link codes: 6 hex chars, 15-min TTL, single-use, unique constraint
- RLS: all tables protected; webhook uses `system_conn` only for phone lookup
- No user PII logged (phone numbers appear only in warning logs for send failures)
