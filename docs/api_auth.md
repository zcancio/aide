# AIde Authentication API

## Endpoints

### POST /auth/send

Send a magic link to the user's email.

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response:** 200 OK
```json
{
  "message": "Magic link sent. Check your email."
}
```

**Rate Limits:**
- 5 requests per email per hour
- 20 requests per IP per hour

**Errors:**
- 429 Too Many Requests: Rate limit exceeded
- 422 Unprocessable Entity: Invalid email format
- 500 Internal Server Error: Email delivery failed

---

### GET /auth/verify?token={token}

Verify a magic link token and create a session.

**Query Parameters:**
- `token` (required): 64-character hex token from magic link email

**Response:** 200 OK
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "name": null,
  "tier": "free",
  "turn_count": 0,
  "turn_week_start": "2026-02-13T10:00:00Z",
  "created_at": "2026-02-13T10:00:00Z"
}
```

**Side Effects:**
- Sets `session` HTTP-only cookie with JWT (24-hour expiry)
- Marks magic link token as used
- Creates new user if first time signing in

**Rate Limits:**
- 10 attempts per IP per minute

**Errors:**
- 401 Unauthorized: Invalid, expired, or used token
- 429 Too Many Requests: Rate limit exceeded

---

### GET /auth/me

Get the current authenticated user.

**Headers:**
- Cookie: `session={jwt_token}` (set automatically by browser)

**Response:** 200 OK
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "name": "John Doe",
  "tier": "pro",
  "turn_count": 15,
  "turn_week_start": "2026-02-13T10:00:00Z",
  "created_at": "2026-02-10T08:30:00Z"
}
```

**Errors:**
- 401 Unauthorized: Missing or invalid session cookie

---

### POST /auth/logout

Logout the current user.

**Response:** 200 OK
```json
{
  "message": "Logged out successfully"
}
```

**Side Effects:**
- Clears `session` cookie

---

## Authentication Flow

1. **User requests magic link:**
   ```bash
   POST /auth/send
   {"email": "user@example.com"}
   ```

2. **User receives email** with link:
   ```
   https://editor.toaide.com/auth/verify?token=abc123...
   ```

3. **User clicks link** (or frontend calls verify endpoint):
   ```bash
   GET /auth/verify?token=abc123...
   ```

4. **Server responds** with user info and sets session cookie

5. **Frontend stores user info** and redirects to dashboard

6. **Subsequent requests** include session cookie automatically:
   ```bash
   GET /auth/me
   Cookie: session=eyJhbGc...
   ```

7. **User logs out:**
   ```bash
   POST /auth/logout
   ```

## Session Management

- **Session Duration:** 24 hours
- **Storage:** HTTP-only, Secure, SameSite=Lax cookie
- **Refresh:** User must request a new magic link after 24 hours
- **Logout:** Clears cookie immediately

## Security Features

✅ **Magic Link Tokens:**
- Cryptographically random (32 bytes = 64 hex chars)
- Single-use (marked as used after verification)
- 15-minute expiry
- Background cleanup of expired tokens

✅ **JWT Sessions:**
- HS256 signed with server secret
- 24-hour expiry
- HTTP-only cookie (not accessible via JavaScript)
- Secure flag (HTTPS only)
- SameSite=Lax (CSRF protection)

✅ **Rate Limiting:**
- Prevents email spam (5/hour per email)
- Prevents IP abuse (20/hour per IP for send)
- Prevents token brute force (10/minute per IP for verify)

✅ **No Password Storage:**
- Passwordless authentication only
- No password reset flows needed
- No password leak vulnerabilities

## Error Handling

All errors return JSON:

```json
{
  "detail": "Human-readable error message"
}
```

Rate limit errors include `Retry-After` header (seconds until limit resets).

## Testing

See `backend/tests/test_auth.py` for comprehensive test examples.
