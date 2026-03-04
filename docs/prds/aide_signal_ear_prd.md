# AIde Signal Ear Design

**Status:** Design
**Phase:** 1.5
**Date:** 2024-02-17

## Overview

Signal Ear enables users to update their AIde pages via Signal messages. Users link their phone number to an aide, then text updates directly.

## Architecture

```
User texts Signal number
         │
         ▼
┌─────────────────────────────────────┐
│  signal-cli-rest-api (Railway)      │
│  - Receives Signal messages         │
│  - POSTs webhook to backend         │
└──────────────┬──────────────────────┘
               │ POST /api/signal/webhook
               ▼
┌─────────────────────────────────────┐
│  Signal Routes (backend)            │
│  ┌─────────────────┐                │
│  │ Webhook Handler │                │
│  └────────┬────────┘                │
│           │                         │
│  ┌────────▼────────┐                │
│  │ Lookup Mapping  │                │
│  │ (phone → aide)  │                │
│  └────────┬────────┘                │
│           │                         │
│  ┌────────▼────────┐                │
│  │  Orchestrator   │                │
│  │  source="signal"│                │
│  └────────┬────────┘                │
│           │                         │
│  ┌────────▼────────┐                │
│  │ Signal Service  │──► Send reply  │
│  └─────────────────┘                │
└─────────────────────────────────────┘
```

## Link Code Flow

```
1. User opens dashboard, clicks "Link Signal"
2. Backend generates 6-char code (e.g., "A7F3B2"), expires in 15 min
3. Dashboard shows: "Text A7F3B2 to +1-555-AIDE"
4. User texts the code
5. Webhook receives code, looks up pending link_code
6. Creates signal_mapping (phone → aide)
7. Responds: "Connected! You can now text updates."
```

## Data Model

### Tables

**signal_link_codes** (new)
```sql
CREATE TABLE signal_link_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT NOT NULL UNIQUE,           -- 6-char hex code
    user_id UUID REFERENCES users(id),
    aide_id UUID REFERENCES aides(id),
    expires_at TIMESTAMPTZ NOT NULL,     -- 15 min TTL
    used BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

**signal_mappings** (existing)
```sql
-- Already exists with:
-- phone_number, user_id, aide_id, conversation_id
```

### Pydantic Models

```python
# backend/models/signal_link_code.py

class SignalLinkCode(BaseModel):
    id: UUID
    code: str
    user_id: UUID
    aide_id: UUID
    expires_at: datetime
    used: bool

class CreateLinkCodeRequest(BaseModel):
    aide_id: UUID

class LinkCodeResponse(BaseModel):
    code: str
    aide_id: UUID
    expires_at: datetime
    signal_phone: str
```

## API Endpoints

### Webhook (Unauthenticated)

```
POST /api/signal/webhook
```
- Receives messages from signal-cli
- Verifies webhook signature
- Handles link codes or routes to orchestrator
- Rate limited: 60 messages/phone/hour

### Dashboard (Authenticated)

```
POST /api/signal/link
Body: { aide_id: UUID }
Response: { code, aide_id, expires_at, signal_phone }
```
Generate link code for an aide.

```
GET /api/signal/mappings
Response: [{ phone_number, aide_id, created_at }]
```
List user's Signal-linked aides.

```
GET /api/signal/mappings/{aide_id}
Response: { linked: bool, phone_number?, aide_id }
```
Check if aide is linked.

```
DELETE /api/signal/mappings/{aide_id}
```
Unlink Signal from aide.

```
GET /api/signal/phone
Response: { phone_number: "+1..." }
```
Get AIde's Signal number for display.

## Signal Service

```python
# backend/services/signal_service.py

class SignalService:
    """HTTP client for signal-cli-rest-api."""

    async def send_message(
        self,
        recipient: str,      # Phone in E.164
        message: str,
        attachments: list[str] | None = None,
    ) -> dict:
        """Send via POST /v2/send"""

    async def health_check(self) -> bool:
        """Check signal-cli is healthy"""
```

## Configuration

```python
# backend/config.py

SIGNAL_CLI_URL: str = "http://signal-cli:8080"
SIGNAL_PHONE_NUMBER: str = "+1XXXXXXXXXX"
SIGNAL_WEBHOOK_SECRET: str = "..."  # For signature verification
```

## Railway Deployment

### Service: signal-cli

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

### Phone Number Setup (One-time)

1. Get SMS-capable number from Twilio (~$1/month)
2. Exec into signal-cli container
3. `signal-cli -u +1XXXXXXXXXX register`
4. Verify with SMS: `signal-cli -u +1XXXXXXXXXX verify CODE`

## Files to Create

| File | Purpose |
|------|---------|
| `alembic/versions/XXX_add_signal_link_codes.py` | Migration |
| `backend/models/signal_link_code.py` | Pydantic models |
| `backend/repos/signal_link_code_repo.py` | Link code CRUD |
| `backend/services/signal_service.py` | HTTP client |
| `backend/routes/signal.py` | All Signal endpoints |
| `backend/tests/test_signal_*.py` | Tests |

## Files to Modify

| File | Changes |
|------|---------|
| `backend/config.py` | Add Signal config vars |
| `backend/main.py` | Register routes, cleanup task |

## Existing (No Changes)

- `backend/models/signal_mapping.py` — Already complete
- `backend/repos/signal_mapping_repo.py` — Already complete
- `backend/services/orchestrator.py` — Already supports source="signal"

## Webhook Message Flow

```python
# Incoming message structure from signal-cli
{
    "envelope": {
        "sourceNumber": "+15551234567",
        "dataMessage": {
            "message": "add milk to the list",
            "attachments": [...]
        }
    }
}

# Processing flow
1. Verify webhook signature
2. Extract phone + message
3. Rate limit check (60/hour/phone)
4. If message matches /^[A-F0-9]{6}$/: handle_link_code()
5. Else: lookup signal_mapping by phone
   - If not found: "Link your phone first"
   - If found: orchestrator.process_message(source="signal")
6. Send response back via signal_service.send_message()
```

## Security

- Webhook signature verification (HMAC-SHA256)
- Rate limiting per phone number
- Link codes: 15-min TTL, single-use, 6 hex chars
- RLS on all tables (system_conn for webhook only)

## Error Handling

| Scenario | Response |
|----------|----------|
| Unknown phone | "Link your phone first via dashboard" |
| Invalid/expired code | "Code invalid or expired, generate new one" |
| Rate limited | "Too many messages, please wait" |
| Orchestrator error | "Something went wrong, try again" |
| signal-cli down | Log error, no response sent |

## Testing Plan

1. **Unit tests**: Link code repo, signal service (mocked HTTP)
2. **Integration tests**: Webhook flow, link flow, mappings CRUD
3. **RLS tests**: Cross-user isolation
4. **E2E**: Local signal-cli + backend, full link + message flow
