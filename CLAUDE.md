# AIde — Claude Code Instructions

AIde is an AI-powered website builder where users describe what they're running and AIde structures it into a living page. Users interact through a conversational chat interface. Published pages are publicly accessible at toaide.com/{slug}.

## Architecture

- **Backend:** Python 3.12 / FastAPI / asyncpg / Pydantic v2
- **Database:** Neon Postgres with Row-Level Security (RLS)
- **File storage:** Cloudflare R2 (aide workspaces + published pages)
- **Email:** Resend (magic link auth, transactional)
- **Payments:** Stripe (Checkout + webhooks)
- **Compute:** Railway (auto-deploy from git, zero ops)
- **Networking:** Cloudflare DNS + CDN
- **AI Providers:** Anthropic, OpenAI, Gemini (user configurable)
- **Domains:** toaide.com (landing + published pages), get.toaide.com (authenticated editor)

## Documentation

Read these docs before implementing anything in the relevant area:

| Area | Doc |
|------|-----|
| Product requirements | docs/aide_prd.md |
| Launch phases & timeline | docs/aide_launch_plan.md |
| Data layer patterns | docs/aide_data_access.md |
| Security requirements | docs/aide_security_checklist.md |
| Infrastructure & deploy | docs/aide_infrastructure.md |
| CI/CD pipeline | docs/aide_cicd.md |
| Monitoring & abuse detection | docs/aide_monitoring.md |
| Error handling & privacy | docs/aide_errors_privacy.md |
| AI system prompt & voice | docs/aide_system_prompt.md |
| Visual design system | docs/aide_design_system.md |
| DevOps options | docs/aide_devops_options.md |

## Hard Rules

These are non-negotiable. Violating any of these is a bug.

### Database Access
- **NEVER use an ORM.** Raw asyncpg with parameterized queries only.
- **NEVER use f-strings, .format(), or string concatenation in SQL.** Always `$1`, `$2` placeholders via asyncpg.
- **ALL database access goes through the repos/ layer.** Route handlers never import asyncpg or write SQL.
- **ALL user-scoped queries use `user_conn(user_id)`** which sets the RLS context. Postgres enforces row-level access.
- **`system_conn()` is ONLY for:** background tasks (abuse checks, cleanup), auth (magic link verify, user creation), and operations that span multiple users. Never in a route handler that returns user data.
- **Every query uses RETURNING \* and maps to a Pydantic model.** No raw dicts flowing through the app.

### Authentication
- **Auth is magic links via Resend. No Google OAuth. No OAuth at all. No social login.**
- Magic link tokens: `secrets.token_hex(32)`, 15-minute expiry, single-use.
- Sessions: HTTP-only, Secure, SameSite=Lax cookie with signed JWT (24-hour expiry).
- Rate limits: 5 magic links per email per hour, 20 per IP per hour.

### API Design
- **ALL request bodies validated via Pydantic models** with `model_config = {"extra": "forbid"}`.
- **ALL response bodies are Pydantic models.** Never return raw dicts or database rows.
- **Three model shapes per entity:** internal model (maps to DB row), request model (client sends, has validation), response model (API returns, excludes internal fields).
- Route handlers are thin: authenticate → call repo → return response model. No business logic beyond simple gate checks.

### Security
- **Published aide pages go to R2.** Never serve user-generated HTML from the app server's process.
- **Stripe webhook signature must be verified** on every webhook. No exceptions.
- **Sentry: `send_default_pii=False`.** Only anonymous UUID, never email/name/IP.
- **No secrets in code, Docker build args, or git.** All secrets in `/etc/aide/.env` or GitHub Actions secrets.

### Code Style
- Type hints on all function signatures.
- `async`/`await` for all I/O operations.
- Use `from __future__ import annotations` in all files.
- Tests use `pytest` + `pytest-asyncio`.
- Linting: `ruff check` must pass with zero warnings.
- Formatting: `ruff format`.

## File Structure

```
backend/
├── main.py                  # FastAPI app, lifespan (pool init, background tasks), Sentry init
├── db.py                    # Connection pool, user_conn(), system_conn()
├── auth.py                  # Magic link send/verify, JWT issue/validate, get_current_user dependency
├── models/                  # Pydantic models ONLY. No imports from db, repos, or routes.
│   ├── user.py
│   ├── aide.py
│   ├── conversation.py
│   └── published.py
├── repos/                   # SQL lives here and ONLY here. Imports from models/ and db.
│   ├── base.py              # log_mutation decorator
│   ├── user_repo.py
│   ├── aide_repo.py
│   ├── conversation_repo.py
│   └── publish_repo.py
├── routes/                  # Thin HTTP handlers. Imports from repos/ and models/. Never writes SQL.
│   ├── aides.py
│   ├── conversations.py
│   ├── publish.py
│   ├── auth_routes.py
│   └── admin.py
├── services/                # External integrations. No SQL, no HTTP handling.
│   ├── ai_provider.py
│   ├── r2.py
│   └── stripe_service.py
└── middleware/
    ├── usage.py             # Turn tracking, abuse detection
    └── sentry_context.py
```

**Dependency flow is one direction:** routes → repos → db, routes → services. No cycles. Models are imported by everything but import nothing from the app.

## Patterns to Follow

### Creating a new endpoint
1. Define Pydantic request/response models in `backend/models/`
2. Add repo method with parameterized SQL in `backend/repos/`
3. Add thin route handler in `backend/routes/` using `Depends(get_current_user)`
4. All queries through `user_conn(user_id)`
5. Register route in `backend/main.py`

### Adding a new table
1. Write Alembic migration by hand (no autogenerate). Static SQL in `op.execute()`.
2. Add RLS policy: `CREATE POLICY ... USING (user_id = current_setting('app.user_id')::uuid)`
3. Create Pydantic model in `backend/models/`
4. Create repo in `backend/repos/` with `_row_to_model()` converter
5. Add RLS cross-user test in test suite

### Modifying auth
1. Read docs/aide_security_checklist.md Authentication section first
2. Magic links only. No OAuth, no social login, no passwords.
3. Rate limiting is mandatory on send and verify endpoints.
4. Tokens must be single-use and time-limited.

## What NOT to Do

- Don't install SQLAlchemy, Tortoise, Peewee, or any ORM.
- Don't use `localStorage` for auth tokens. HTTP-only cookies only.
- Don't expose `user_id`, `stripe_customer_id`, `r2_prefix`, or internal fields in API responses.
- Don't use Google services for anything (auth, analytics, email, fonts CDN).
- Don't add dependencies without checking if asyncpg/Pydantic/stdlib already handles it.
- Don't write SQL outside of `backend/repos/`.
- Don't use `pool.acquire()` directly. Always `user_conn()` or `system_conn()`.
