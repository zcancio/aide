# Issue #170: Magic Link Auth Redirect to Dashboard

## Summary
Fixed magic link authentication flow to perform server-side redirects instead of client-side redirects.

## Problem
Previously, the `/auth/verify` endpoint returned JSON with user data, and the frontend handled the redirect in JavaScript. This required the frontend to call the API and then navigate based on the response.

## Solution
Changed the `/auth/verify` endpoint to return HTTP 303 redirects directly:
- **On success**: Redirects to `/` (dashboard) with session cookie set
- **On failure**: Redirects to `/auth?error=<error_code>` with appropriate error code

## Changes Made

### Backend: `/backend/routes/auth_routes.py`
1. Added `RedirectResponse` import from FastAPI
2. Modified `verify_magic_link_endpoint`:
   - Changed status code from 200 to 302
   - Changed return type from `UserPublic` to `RedirectResponse`
   - Replaced all `HTTPException` raises with `RedirectResponse` to `/auth?error=...`
   - Success case now redirects to `/` with session cookie
   - Error codes: `too_many_attempts`, `invalid_link`, `link_used`, `link_expired`

### Frontend: `/frontend/src/components/AuthScreen.jsx`
1. Removed token verification logic from `useEffect`
2. Added error parameter handling from URL query string
3. Display appropriate error messages based on error codes from redirect

### Tests: `/backend/tests/test_auth.py`
Updated 5 tests to expect redirects instead of JSON responses:
1. `test_verify_magic_link_new_user` - Expects 303 redirect to `/`
2. `test_verify_magic_link_existing_user` - Expects 303 redirect to `/`
3. `test_verify_invalid_token` - Expects 303 redirect to `/auth?error=invalid_link`
4. `test_verify_used_token` - Expects 303 redirect to `/auth?error=link_used`
5. `test_verify_expired_token` - Expects 303 redirect to `/auth?error=link_expired`

## Error Codes
- `too_many_attempts`: Rate limit exceeded (10 attempts per IP per minute)
- `invalid_link`: Magic link token not found in database
- `link_used`: Magic link has already been used
- `link_expired`: Magic link has expired (default: 15 minutes)

## User Flow
1. User clicks magic link in email: `/auth/verify?token=<token>`
2. Server validates token and:
   - **Success**: Sets session cookie → 303 redirect to `/` → User sees dashboard
   - **Failure**: 303 redirect to `/auth?error=<code>` → User sees auth screen with error message

## Testing
- All 23 auth tests pass ✅
- All 244 backend tests pass ✅ (5 pre-existing SPA serving failures unrelated to this change)
- Linting: `ruff check backend/` ✅
- Formatting: `ruff format --check backend/` ✅

## Files Modified
- `backend/routes/auth_routes.py`
- `frontend/src/components/AuthScreen.jsx`
- `backend/tests/test_auth.py`

## Notes
- The `verifyToken` function in `useAuth.jsx` is kept for backward compatibility but is no longer actively used
- The change is transparent to the user - they still click a link and get redirected
- Server-side redirects are more secure and eliminate a round-trip through the frontend
