# Magic Link Authentication Implementation Summary

## Overview

Implemented Phase 0.2 of the AIde launch plan: complete magic link authentication system with no Google/OAuth dependencies.

## What Was Built

### 1. Data Models (`backend/models/`)
- **user.py**: `User` (internal) and `UserPublic` (API response) models
- **auth.py**: Magic link request/response models with strict validation

### 2. Repositories (`backend/repos/`)
- **magic_link_repo.py**:
  - Create cryptographically random tokens (32 bytes hex = 64 chars)
  - Validate and mark tokens as used
  - Rate limiting query support (5 per email per hour)
  - Background cleanup of expired tokens

- **user_repo.py**:
  - Get/create users by email (for magic link verification)
  - User CRUD with RLS support
  - Turn counter management (for future rate limiting)
  - Stripe tier upgrades/downgrades

### 3. Authentication (`backend/auth.py`)
- **JWT Functions**:
  - `create_jwt()`: Issues 24-hour session tokens
  - `decode_jwt()`: Validates and extracts user ID

- **FastAPI Dependency**:
  - `get_current_user()`: Reads HTTP-only session cookie, validates JWT, returns User

### 4. API Routes (`backend/routes/auth_routes.py`)

#### POST /auth/send
- Validates email
- Rate limits: 5/email/hour, 20/IP/hour
- Generates magic link token
- Sends branded email via Resend
- Returns generic success message (doesn't leak if email exists)

#### GET /auth/verify?token=...
- Validates token exists, not used, not expired
- Rate limit: 10/IP/minute (prevents brute force)
- Marks token as used
- Creates user if first time, or finds existing user
- Issues JWT in HTTP-only, Secure, SameSite=Lax cookie
- Returns UserPublic

#### GET /auth/me
- Requires valid session cookie
- Returns current user info

#### POST /auth/logout
- Clears session cookie
- Returns success message

### 5. Email Service (`backend/services/email.py`)
- Sends magic link emails via Resend
- Branded HTML + plain text templates
- Clean, professional design
- 15-minute expiry displayed to user

### 6. Rate Limiting (`backend/middleware/rate_limit.py`)
- In-memory rate limiter for Phase 0
- Tracks requests by key (email or IP) within time windows
- Auto-cleanup of old entries
- Ready to swap for Redis in production

### 7. Application Lifecycle (`backend/main.py`)
- FastAPI lifespan context manager
- Initializes database pool on startup
- Starts background cleanup task (runs every 60 seconds)
- Gracefully shuts down on termination
- Registers auth routes

### 8. Background Tasks
- Cleans up expired/used magic links older than 1 hour
- Cleans up old rate limit entries older than 2 hours
- Runs continuously every 60 seconds

### 9. Comprehensive Tests (`backend/tests/test_auth.py`)
- JWT creation and validation (including expiry)
- Magic link CRUD operations
- Rate limiting (email and IP)
- Full auth flow: send → verify → session → logout
- Edge cases: expired tokens, used tokens, invalid tokens
- RLS verification (users can't access other users' data)

## Security Checklist Compliance

✅ **Authentication**
- [x] Magic link tokens are cryptographically random (32 bytes, `secrets.token_hex(32)`)
- [x] Tokens expire after 15 minutes
- [x] Tokens are single-use (marked used, checked before JWT issuance)
- [x] Background cleanup of expired/used tokens
- [x] JWT signed with HS256, 24-hour expiry
- [x] JWT in HTTP-only, Secure, SameSite=Lax cookie
- [x] Rate limit: 5 per email per hour, 20 per IP per hour
- [x] Rate limit verify: 10 per IP per minute
- [x] Email validation via Pydantic EmailStr
- [x] Magic link URL uses HTTPS only
- [x] Email via Resend (no Google dependency)

✅ **Input Validation**
- [x] All requests validated via Pydantic with `extra="forbid"`
- [x] Email validated as EmailStr
- [x] Token validated as 64-char string
- [x] No SQL injection (all queries use `$1`, `$2` parameterization)

✅ **Code Quality**
- [x] Ruff lint: zero warnings
- [x] Ruff format: all files formatted
- [x] Type hints on all functions
- [x] Async/await for all I/O
- [x] No f-strings or .format() in SQL queries
- [x] No ORM (raw asyncpg)

## File Structure

```
backend/
├── auth.py                    # JWT + get_current_user dependency
├── main.py                    # FastAPI app + lifespan + cleanup task
├── models/
│   ├── user.py                # User, UserPublic
│   └── auth.py                # MagicLink, request/response models
├── repos/
│   ├── magic_link_repo.py     # Magic link CRUD + rate limit queries
│   └── user_repo.py           # User CRUD
├── routes/
│   └── auth_routes.py         # /auth/send, /verify, /me, /logout
├── services/
│   └── email.py               # Resend integration
├── middleware/
│   └── rate_limit.py          # In-memory rate limiter
└── tests/
    ├── test_auth.py           # Comprehensive auth tests
    └── README.md              # Test setup instructions
```

## How to Use

### 1. Set Environment Variables

```bash
export DATABASE_URL="postgresql://user:pass@host:5432/aide"
export JWT_SECRET="your-256-bit-secret-key"
export RESEND_API_KEY="re_xxx"
```

### 2. Run Migrations

```bash
alembic upgrade head
```

### 3. Start the Server

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 4. Test the Flow

**Request magic link:**
```bash
curl -X POST http://localhost:8000/auth/send \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'
```

**Check email, click link (or use token):**
```bash
curl -X GET "http://localhost:8000/auth/verify?token=abc123..." \
  -c cookies.txt
```

**Access protected endpoint:**
```bash
curl -X GET http://localhost:8000/auth/me \
  -b cookies.txt
```

**Logout:**
```bash
curl -X POST http://localhost:8000/auth/logout \
  -b cookies.txt
```

## What's NOT Included

- ❌ Google OAuth (explicitly removed per requirements)
- ❌ Social login (not needed)
- ❌ Passwords (magic links only)
- ❌ Redis rate limiting (in-memory is fine for Phase 0)
- ❌ Email templates in a separate file (inline for simplicity)

## Next Steps (Phase 1+)

1. Multi-aide management (Phase 1.1)
2. Turn counting and limits (Phase 2.1)
3. Stripe integration (Phase 3.1)
4. Landing page (Phase 4.1)

## Testing

Tests require a PostgreSQL database. See `backend/tests/README.md` for setup instructions.

```bash
./run_tests.sh backend/tests/test_auth.py -v
```

## Deployment Notes

- Railway will run migrations automatically via `railway.toml` start command
- Background cleanup task starts automatically with the app
- Rate limiter is in-memory (OK for single-instance deployments)
- For multi-instance, swap rate limiter for Redis or Railway's built-in rate limiting

## Estimated Code Size

- ~800 lines of production code (models, repos, routes, services, middleware)
- ~400 lines of tests
- ~50 lines of auth code (as predicted in the launch plan)
- Zero dependencies on Google services

**Total: Phase 0.2 complete. ✅**
