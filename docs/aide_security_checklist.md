# AIde — Security Checklist

Everything that needs to be true before real users touch this.

---

## Authentication (Magic Links)

- [ ] Magic link tokens are cryptographically random (32 bytes, `secrets.token_hex(32)`)
- [ ] Tokens expire after 15 minutes
- [ ] Tokens are single-use (marked `used = true` after verification, checked before issuing JWT)
- [ ] Expired/used tokens cleaned up by background task
- [ ] JWT signed with strong secret (256-bit minimum), HS256 or RS256
- [ ] JWT stored in HTTP-only, Secure, SameSite=Lax cookie (not localStorage)
- [ ] JWT expiry: 24 hours (short-lived)
- [ ] Refresh flow: user requests new magic link (no long-lived refresh tokens)
- [ ] Logout clears cookie server-side (set expired cookie)
- [ ] Rate limit magic link sends: 5 per email per hour, 20 per IP per hour
- [ ] Rate limit verify endpoint: 10 attempts per IP per minute (prevents token brute force)
- [ ] Email validation: Pydantic `EmailStr` before sending (reject garbage input)
- [ ] Magic link URL uses HTTPS only (`https://editor.toaide.com/auth/verify?token=...`)
- [ ] Email sending via Resend (no Google dependency)

---

## Authorization

- [ ] Every route handler uses `Depends(get_current_user)` — no anonymous access to API
- [ ] Every database call uses `user_conn(user_id)` with RLS active
- [ ] RLS policies on all tables: `users`, `aides`, `conversations`
- [ ] RLS test: verify user A cannot access user B's data (automated test)
- [ ] RLS test: verify user A cannot update/delete user B's data (automated test)
- [ ] `system_conn()` is only used in background tasks, never in route handlers
- [ ] Admin endpoints (`/stats`, `/health`) require admin check, not just authentication
- [ ] Published page serving (`toaide.com/{slug}`) does not expose user IDs or internal data

---

## SQL Injection

- [ ] Every query uses parameterized placeholders (`$1`, `$2`) via asyncpg
- [ ] Zero f-string or `.format()` usage in any SQL query (grep the codebase)
- [ ] Dynamic column names come from hardcoded Pydantic field names, never user input
- [ ] Alembic migrations use `op.execute()` with static SQL, not user-derived values
- [ ] CI check: `ruff` or custom lint rule flags string interpolation near SQL keywords

---

## Input Validation

- [ ] All request bodies validated via Pydantic models before any processing
- [ ] String fields have `max_length` constraints
- [ ] Slug field: `pattern=r"^[a-z0-9-]+$"`, max 100 chars
- [ ] Title field: max 200 chars
- [ ] Email validated via Pydantic `EmailStr`
- [ ] UUID fields validated as proper UUIDs (Pydantic does this automatically)
- [ ] JSONB `messages` field: validate via `Message` model before storing
- [ ] File uploads (if any): validate MIME type, max size, scan for malicious content
- [ ] Reject unexpected fields in request bodies (Pydantic `model_config = {"extra": "forbid"}`)

---

## XSS (Cross-Site Scripting)

- [ ] Published aide pages served in sandboxed iframe or separate origin
- [ ] `Content-Security-Policy` header on editor domain
- [ ] User-generated HTML (aide content) stored in R2, served from separate domain/subdomain
- [ ] Editor UI does not render raw user HTML inline — always iframe
- [ ] API responses set `Content-Type: application/json` (not `text/html`)
- [ ] No `innerHTML` or `dangerouslySetInnerHTML` with unsanitized user input in editor UI

---

## CSRF (Cross-Site Request Forgery)

- [ ] JWT in HTTP-only cookie with `SameSite=Lax` (blocks cross-origin POST)
- [ ] Magic link verify endpoint is GET (idempotent) — token is single-use so replay is harmless
- [ ] Mutating API endpoints (POST/PATCH/DELETE) verify `Origin` or `Referer` header matches allowed domains
- [ ] WebSocket connections validate the JWT cookie on handshake

---

## Rate Limiting

- [ ] Magic link send: 5 per email per hour, 20 per IP per hour
- [ ] Magic link verify: 10 attempts per IP per minute
- [ ] API endpoints: 100 requests/minute per user
- [ ] AI turn processing: 50 turns/week per free user (enforced server-side)
- [ ] Aide creation: 10 per hour per user
- [ ] Published page requests: 1000/minute per IP (Cloudflare handles this)
- [ ] WebSocket connections: 5 concurrent per user
- [ ] Rate limit responses return `429 Too Many Requests` with `Retry-After` header

---

## Data Privacy

- [ ] RLS active on all user-data tables
- [ ] Three database roles: `aide_app`, `aide_readonly`, `aide_breakglass`
- [ ] `aide_app` cannot bypass RLS
- [ ] `aide_readonly` uses masked view for PII (email shows as `***@domain.com`)
- [ ] `aide_readonly` cannot access `conversations` table
- [ ] `aide_breakglass` is `NOLOGIN` by default
- [ ] Break-glass activation requires justification string
- [ ] Break-glass credentials expire in 1 hour (`VALID UNTIL`)
- [ ] Break-glass activation fires Slack alert
- [ ] Break-glass deactivation fires Slack alert
- [ ] `audit_log` table: INSERT only, no UPDATE/DELETE policies
- [ ] Sentry initialized with `send_default_pii=False`
- [ ] Sentry receives user UUID only, never email/name/IP
- [ ] Stripe customer IDs and subscription IDs never exposed in API responses
- [ ] Conversation content (user messages) never logged to Sentry or application logs
- [ ] R2 workspace bucket is private (not publicly accessible)
- [ ] R2 published bucket only serves published aides, not draft content

---

## Secrets Management

- [ ] All secrets stored in Railway environment variables, never in code or git
- [ ] `.gitignore` includes `.env`, `*.pem`, `*.key`
- [ ] No secrets in build args or build output (Railway injects at runtime only)
- [ ] GitHub Actions secrets for Slack webhook (CI notifications)
- [ ] Rotate JWT secret on any suspected compromise
- [ ] Rotate database passwords quarterly (Neon makes this easy)
- [ ] Stripe webhook secret validates all incoming webhook payloads
- [ ] R2 API keys: separate keys for app (read/write workspaces) and public (read-only published)
- [ ] Resend API key stored in Railway env vars, never in code

---

## Transport Security

- [x] ~~All traffic through Cloudflare Tunnel~~ — Railway handles TLS + custom domains
- [ ] Cloudflare SSL mode: Full (Strict)
- [ ] Database connection: `sslmode=require` in connection string
- [ ] R2 access: HTTPS only (S3-compatible API)
- [x] ~~SSH: key-only, no passwords, no root login~~ — no SSH, no server
- [ ] HSTS header: `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- [ ] No mixed content (HTTP resources on HTTPS pages)

---

## Server Hardening

_Railway is a managed platform — no servers to harden. This section is handled by Railway:_

- [x] ~~No root SSH access~~ — no SSH at all, no server
- [x] ~~Password authentication disabled~~ — no server
- [x] ~~UFW firewall~~ — no server
- [x] ~~fail2ban~~ — no server
- [x] ~~Unattended security updates~~ — Railway handles runtime
- [x] ~~App runs as unprivileged user~~ — Railway isolates builds/runs
- [x] ~~Systemd hardening~~ — no systemd
- [x] ~~Docker daemon not exposed~~ — no Docker to manage

---

## Content Safety (Published Pages)

- [ ] Safety scanner runs on publish — check for phishing, malware, adult content
- [ ] "Made with AIde" footer on free tier pages (visible, not hidden)
- [ ] Report button or `abuse@toaide.com` email for flagging malicious pages
- [ ] Unpublish mechanism: admin can set aide status to `archived` without break-glass
- [ ] `robots.txt` on published pages (allow indexing)
- [ ] Published pages cannot execute server-side code (static HTML/CSS/JS only from R2)
- [ ] Published pages cannot set cookies on `toaide.com` (serve from `*.toaide.com` or R2 domain)
- [ ] Cloudflare WAF rules for common attack patterns on published page URLs

---

## Payments (Stripe)

- [ ] Stripe webhook signature verified on every webhook (`stripe.Webhook.construct_event()`)
- [ ] Webhook handler is idempotent (replaying the same event doesn't double-upgrade)
- [ ] `checkout.session.completed` → upgrade user to pro
- [ ] `customer.subscription.deleted` → downgrade user to free
- [ ] `invoice.payment_failed` → optional: notify user, grace period
- [ ] No credit card data ever touches your server (Stripe Checkout handles this)
- [ ] Stripe customer ID stored but never exposed in API responses
- [ ] Test webhook handlers with Stripe CLI before launch

---

## Monitoring & Alerting

- [ ] BetterStack uptime monitor on `editor.toaide.com/health` (every 3 min)
- [ ] Sentry error tracking with Slack alerts on new issues
- [ ] Abuse detection loop running every 60 seconds
- [ ] Traffic spike detection with configurable thresholds
- [ ] Slack alerts for: downtime, errors, abuse, traffic spikes, break-glass access, deploy success/failure
- [ ] Weekly backup verification script (Neon connectivity + R2 access)

---

## Deployment Safety

- [ ] CI runs lint + test + bandit security scan on every push
- [ ] Railway only auto-deploys from `main` branch
- [ ] Railway health check gates deploy (`/health` must return 200)
- [ ] Failed health check → new instance killed, old instance keeps serving
- [ ] Migrations run before app starts (`alembic upgrade head && uvicorn ...`)
- [ ] Migrations are backward-compatible (old code still serving during migration)
- [ ] Railway rollback tested: click rollback → previous version serves in ~30s
- [ ] Deploy notifications in Slack (via Railway built-in or GitHub Actions)
- [ ] No `DROP COLUMN` or `DROP TABLE` in migrations without a multi-step deprecation

---

## Legal / Compliance

- [ ] Privacy policy at `toaide.com/privacy` (what data you collect, how it's used, how to delete)
- [ ] Terms of service at `toaide.com/terms` (acceptable use, content policies)
- [ ] Cookie consent: only essential cookies (JWT session) — no tracking cookies, no banner needed
- [ ] GDPR: user can request data export and account deletion
- [ ] Account deletion: cascading delete (user → aides → conversations → published versions → R2 files)
- [ ] Data retention: usage_events cleaned up after 30 days
- [ ] Audit log retained indefinitely (required for accountability)
- [ ] No third-party analytics at launch (no Google Analytics, no Mixpanel)
- [ ] No Google infrastructure dependencies (auth via magic links, not OAuth)
- [ ] Sentry PII disabled (no user email/IP sent to third parties)

---

## Pre-Launch Final Check

- [ ] Run full test suite including RLS cross-user tests
- [ ] Run `ruff check` — zero warnings
- [ ] Grep codebase for hardcoded secrets, test credentials, TODO/FIXME
- [ ] Test signup → create aide → edit → publish → view → share → delete flow
- [ ] Test magic link flow: request → email arrives → click → authenticated → JWT cookie set
- [ ] Test magic link expiry: token older than 15 min is rejected
- [ ] Test magic link reuse: used token is rejected
- [ ] Test magic link rate limiting: 6th request in an hour for same email is rejected
- [ ] Test free tier limits (turn limit, aide limit)
- [ ] Test Stripe upgrade → verify pro features → cancel → verify downgrade
- [ ] Test break-glass procedure end to end
- [ ] Verify published pages load from R2 CDN (not from app server)
- [ ] Verify Cloudflare SSL is Full (Strict)
- [x] ~~Verify UFW is active on both servers~~ — no servers
- [x] ~~Verify fail2ban is active~~ — no servers
- [x] ~~Verify Hetzner snapshots are enabled~~ — Railway handles deploys
- [x] ~~Test failover: stop app-1, verify app-2 takes over~~ — Railway auto-restarts
- [ ] Test Railway rollback: click rollback → previous version serves
- [ ] Have someone else try to break it (friend, colleague, LLM)
