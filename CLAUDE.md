# AIde — Claude Code Instructions

**What is AIde?** A living object engine. Users describe what they're running — a league, a budget, a renovation — and AIde forms a living page. As things change, users tell AIde through text, images, or voice. The page stays current. The URL stays the same. Continuity, not creation.

**Domain:** toaide.com (landing + published pages at `/s/{slug}`), get.toaide.com (authenticated editor)
**Tagline:** "For what you're running."

---

## Hard Rules

These are non-negotiable. Every PR, every file, every function.

1. **Raw asyncpg only.** No ORM. No SQLAlchemy. Parameterized queries with `$1`, `$2` placeholders.
2. **NEVER use f-strings or `.format()` in SQL.** Zero exceptions. Grep the codebase to be sure.
3. **All database access goes through `backend/repos/`.** Route handlers never touch SQL directly.
4. **All user-scoped queries use `user_conn(user_id)` for RLS.** This sets `app.current_user_id` on the connection so Postgres RLS policies filter rows automatically.
5. **`system_conn()` is ONLY for background tasks and auth** (magic link verify, token cleanup, abuse detection). Never in route handlers that serve user data.
6. **All request/response models are Pydantic.** No raw dicts crossing route handler boundaries. Use `model_config = {"extra": "forbid"}` on all request models.
7. **Auth is magic links via Resend.** No Google OAuth. No OAuth at all. No Cloudflare Access.
8. **JWT in HTTP-only, Secure, SameSite=Lax cookie.** Never localStorage. 24-hour expiry.
9. **Published pages go to R2.** Never serve user-generated HTML from the app server directly.
10. **Migrations must be backward-compatible.** Old code is still serving traffic during migration. Add columns as nullable or with defaults. Never drop columns old code reads. Column renames take 3 deploys (add new → migrate data → drop old).

---

## Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Language | Python 3.12 | Type hints everywhere, async/await for all I/O |
| Framework | FastAPI | Pydantic v2 for all models |
| Database | Neon Postgres | RLS enabled, asyncpg driver, `sslmode=require` |
| DB Migrations | Alembic | Runs before app start: `alembic upgrade head && uvicorn ...` |
| File Storage | Cloudflare R2 | `aide-workspaces` (private), `aide-published` (public CDN) |
| Email | Resend | Magic link delivery. Free tier: 100/day, 3,000/month |
| Payments | Stripe | Checkout sessions, webhook handlers, $10/mo Pro tier |
| Compute | Railway | Git-push deploys from `main`, zero-downtime, auto-rollback |
| DNS/CDN | Cloudflare | SSL, WAF, CDN caching for published pages |
| CI | GitHub Actions | Lint (ruff) + test (pytest) + security (bandit) on every push |
| Monitoring | BetterStack (uptime), Sentry (errors) | Both free tier |

---

## Project Structure

```
aide/
├── .github/
│   └── workflows/
│       └── ci.yml                  # lint + test (backend + kernel) + security scan
├── .claude/
│   ├── README.md
│   └── commands/                   # Claude Code slash commands
│       ├── audit-architecture.md
│       ├── implement-phase.md
│       ├── new-endpoint.md
│       ├── new-table.md
│       ├── pre-commit.md
│       └── security-review.md
├── railway.toml                    # deploy config
├── CLAUDE.md                       # ← you are here
├── run_tests.sh                    # test runner with env var setup
├── pyproject.toml                  # ruff + pytest config
├── requirements.txt
├── requirements-dev.txt
├── alembic.ini                     # Alembic config (points to alembic/)
├── .gitignore
├── backend/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app, lifespan, background cleanup
│   ├── config.py                   # Settings from env vars (all secrets here)
│   ├── auth.py                     # JWT create/decode, get_current_user dependency
│   ├── db.py                       # Connection pool, user_conn(), system_conn()
│   ├── models/                     # Pydantic models only — no app imports
│   │   ├── __init__.py
│   │   ├── user.py                 # User, UserPublic
│   │   ├── auth.py                 # MagicLink, SendMagicLinkRequest/Response
│   │   ├── aide.py                 # Aide, CreateAideRequest, AideResponse
│   │   ├── conversation.py         # Conversation, Message
│   │   └── published.py            # PublishedVersion
│   ├── repos/                      # All SQL lives here — parameterized queries only
│   │   ├── __init__.py
│   │   ├── base.py                 # log_mutation decorator
│   │   ├── user_repo.py            # User CRUD, tier management
│   │   ├── magic_link_repo.py      # Magic link CRUD, rate limit queries
│   │   ├── aide_repo.py            # Aide CRUD
│   │   ├── conversation_repo.py    # Conversation/message storage
│   │   └── publish_repo.py         # Published version tracking
│   ├── routes/                     # Thin HTTP handlers — no SQL, no business logic
│   │   ├── __init__.py
│   │   ├── auth_routes.py          # /auth/send, /auth/verify, /auth/me, /auth/logout
│   │   ├── aides.py                # Aide CRUD endpoints
│   │   ├── conversations.py        # WebSocket chat
│   │   ├── publish.py              # Publish/unpublish
│   │   └── admin.py                # /health, /stats
│   ├── services/                   # External integrations — no SQL, no HTTP handling
│   │   ├── __init__.py
│   │   ├── ai_provider.py          # LLM abstraction (Anthropic, OpenAI, Gemini)
│   │   ├── email.py                # Resend magic link delivery
│   │   ├── r2.py                   # Cloudflare R2 file operations
│   │   └── stripe_service.py       # Stripe webhook handling
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── rate_limit.py           # In-memory rate limiter (Redis later)
│   │   ├── usage.py                # Turn tracking, abuse detection
│   │   └── sentry_context.py       # Anonymous user context for Sentry
│   └── tests/
│       ├── README.md               # Test setup instructions
│       ├── conftest.py             # Fixtures: test DB, test user
│       ├── test_db.py              # Pool init, RLS, cross-user isolation
│       └── test_auth.py            # JWT, magic links, rate limits, full auth flow
├── engine/
│   ├── kernel/                     # Modular Python kernel (pure functions)
│   │   ├── __init__.py
│   │   ├── reducer.py              # reduce(snapshot, event) → ReduceResult
│   │   ├── renderer.py             # render(snapshot, blueprint, events) → HTML
│   │   ├── primitives.py           # Schema definitions, field types
│   │   ├── validator.py            # Event payload validation
│   │   ├── types.py                # Shared types: Event, Blueprint, ReduceResult, etc.
│   │   └── tests/
│   │       ├── conftest.py
│   │       ├── tests_reducer/      # 5 suites: happy path, rejections, cardinality, determinism, round-trip
│   │       │   ├── test_reducer_happy_path.py
│   │       │   ├── test_reducer_rejections.py
│   │       │   ├── test_reducer_cardinality.py
│   │       │   ├── test_reducer_determinism.py
│   │       │   └── test_reducer_round_trip.py
│   │       ├── tests_renderer/     # 11 categories per renderer spec
│   │       │   ├── test_renderer_file_structure.py
│   │       │   ├── test_renderer_sort_filter_group.py
│   │       │   └── ...
│   │       └── tests_assembly/     # 10 categories per assembly spec
│   │           ├── test_assembly_load_save.py
│   │           ├── test_assembly_apply.py
│   │           ├── test_assembly_integrity.py
│   │           └── ...
│   └── builds/                     # Single-file builds for distribution (hosted on R2)
│       ├── engine.py               # Python single-file kernel
│       ├── engine.js               # JS single-file kernel
│       └── engine.ts               # TS single-file kernel
├── skills/
│   └── aide-builder/
│       ├── SKILL.md                # Claude Code skill — fetches latest engine
│       ├── evals/
│       └── examples/
├── scripts/
│   └── setup-runner.sh             # Self-hosted GitHub Actions runner setup
├── frontend/
│   └── index.html                  # Editor UI (full-viewport preview + chat overlay)
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_initial_schema.py   # users, magic_links, aides, conversations, published_versions, audit_log
│       ├── 002_force_rls.py        # Enable RLS on all tables
│       ├── 003_add_insert_policies.py
│       └── 004_fix_rls_policies.py
└── docs/
    ├── aide_security_checklist.md
    ├── prds/                       # Product requirements
    │   ├── aide_prd.md
    │   └── aide_editor_prd.md
    ├── eng_design/                 # Engineering design docs
    │   ├── aide_architecture.md
    │   └── specs/
    │       ├── aide_reducer_spec.md
    │       ├── aide_renderer_spec.md
    │       ├── aide_assembly_spec.md
    │       ├── aide_primitive_schemas_spec.md
    │       ├── aide_system_prompt_spec.md
    │       ├── aide_ui_design_system_spec.md
    │       └── api_auth_spec.md
    ├── infrastructure/             # Infra, deploy, data access
    │   ├── aide_infrastructure.md
    │   ├── aide_cicd.md
    │   ├── aide_data_access.md
    │   ├── aide_errors_privacy.md
    │   └── aide_monitoring.md
    ├── strategy/                   # Product strategy
    │   ├── aide_engine_distribution.md
    │   └── aide_living_objects.md
    └── tpm/                        # Launch tracking
        ├── aide_launch_plan.md
        ├── IMPLEMENTATION_SUMMARY.md
        └── PHASE0_COMPLETE.md
```

---

## Database

### Schema (Neon Postgres)

Five core tables: `users`, `magic_links`, `aides`, `conversations`, `published_versions`.

### Three Database Roles

| Role | Purpose | RLS |
|------|---------|-----|
| `aide_app` | Application queries. Used in `user_conn()` and `system_conn()` | Cannot bypass RLS |
| `aide_readonly` | Monitoring, debugging. Masked PII view. No access to conversations | Cannot bypass RLS |
| `aide_breakglass` | Emergency access. `NOLOGIN` by default. 1-hour expiry. Slack alert on activation | Can bypass RLS |

### Connection Patterns

```python
# User-scoped query (route handlers) — RLS filters to this user's data
async with user_conn(user_id) as conn:
    aide = await conn.fetchrow("SELECT * FROM aides WHERE id = $1", aide_id)

# System query (background tasks, auth only) — no RLS filtering
async with system_conn() as conn:
    token = await conn.fetchrow("SELECT * FROM magic_links WHERE token = $1", token)
```

---

## Authentication

Magic links via Resend. ~50 lines of auth code total.

### Flow
1. `POST /auth/send` — validate email, generate `secrets.token_hex(32)`, store in `magic_links`, send via Resend
2. User clicks link → `GET /auth/verify?token=abc123`
3. Verify: token exists, not expired (15 min), not used → mark used → create/find user → issue JWT cookie
4. JWT: HTTP-only, Secure, SameSite=Lax, 24-hour expiry, HS256
5. Logout: set expired cookie

### Rate Limits
- Magic link send: 5 per email/hour, 20 per IP/hour
- Verify endpoint: 10 attempts per IP/minute
- API endpoints: 100 requests/minute per user
- WebSocket: 5 concurrent per user

---

## AI Voice

AIde is infrastructure, not a character. The AI must conform to these rules:

- **No first person.** Never "I updated..." — use state reflections: "Budget: $1,350."
- **No encouragement.** No "Great!", "Nice!", "Let's do this!"
- **No emojis.** Never.
- **No self-narration.** No "I'm going to...", "Let me..."
- **No filler.** No "Here's what I found...", "Sure thing..."
- **Mutations are declarative and final.** "Next game: Mike's on snacks."
- **State over action.** Show how things stand, not what was done.
- **Silence is valid.** Not every action needs a response.

---

## Kernel Architecture

AIde uses an event-sourced kernel with pure functions. AI handles fuzzy (intent compilation), code handles precise (state management and rendering).

### Components

| Component | What it does | Pure function? |
|-----------|-------------|----------------|
| **Reducer** | Applies primitive events to snapshot state | Yes — deterministic |
| **Renderer** | Converts snapshot → static HTML/CSS with embedded JSON | Yes — deterministic |
| **Assembly** | Combines rendered HTML + blueprint + events into self-contained file | Yes |
| **L2 (Haiku)** | Intent compiler: user message → primitive events (~90% of interactions) | No — LLM |
| **L3 (Sonnet)** | Schema synthesizer: creates/evolves collections, fields, MacroSpecs (~10%) | No — LLM |

### Primitives

All state mutations flow through declarative primitive events. No file I/O tools — the AI emits events, the reducer applies them, the renderer produces HTML.

Primitive families: `entity.*`, `collection.*`, `field.*`, `block.*`, `view.*`, `style.*`, `meta.*`, `relationship.*`

See `docs/eng_design/specs/aide_primitive_schemas_spec.md` and `docs/eng_design/specs/aide_reducer_spec.md` for full catalog.

---

## AI Routing (L2/L3 Escalation)

For users without their own API keys, AIde provides managed access via tiered intelligence:

- **L2 (Haiku-class)** — default for all messages. Compiles user intent into primitive events. ~$0.001/call.
- **L3 (Sonnet-class)** — escalation only. Triggers on: no schema exists, L2 returns escalation signal, image input, voice transcription with ambiguity, message complexity above threshold. ~$0.02–0.05/call.
- L3 synthesizes MacroSpecs that are persisted — L2 can invoke by name in future (system gets cheaper over time)
- BYOK users bypass managed routing entirely
- Server-side keys stored in env vars, never user-facing

---


## Tiers

| | Free | Pro ($10/mo) |
|---|---|---|
| AI turns | 50/week | Unlimited |
| Published pages | "Made with AIde" footer | No footer |
| Slugs | Random | Custom |
| BYOK | Always available | Always available |

---

## Editor

The editor is a full-viewport preview with a floating chat overlay. The page is primary — the chat floats at the bottom.

- **Preview:** sandboxed `<iframe>` fills the viewport. Refreshes per AI turn via `srcdoc`. Same HTML as published pages.
- **Chat overlay:** input bar pinned to bottom with expandable conversation history. Backdrop blur, auto-collapse after inactivity.
- **Same layout on all screen sizes.** No split-pane, no breakpoint-driven layout shifts. Desktop: chat overlay centered at max-width 640px. Mobile: full-width.
- **Three input modes:** text (typing), images (file picker + drag-and-drop), voice (speech-to-text).

See `docs/prds/aide_editor_prd.md` for full specification.

---

## Input Modes

### Text
Standard message input. Enter to send, Shift+Enter for newline.

### Images
- Accept: JPEG, PNG, WebP, HEIC (convert HEIC server-side)
- Max size: 10MB. Sent as base64 to AI provider.
- Images trigger L3 routing (vision-capable model).

### Voice (Speech-to-Text)
Two-tier approach — browser API default, server-side Whisper fallback:

- **Primary:** browser `SpeechRecognition` API. Free, real-time streaming into input field. Chrome + Safari.
- **Fallback:** `POST /api/transcribe` — accepts WebM/Opus audio, sends to OpenAI Whisper API (~$0.006/min), returns `{ text: "..." }`. Rate-limited same as AI turns.
- Transcribed text populates the input field for review before sending. Voice never auto-sends.

---

## Publishing

Published pages are static HTML/CSS/JS served from R2 via Cloudflare CDN:

```
User publishes → files uploaded to R2 (aide-published/{slug}/)
Visitor hits toaide.com/s/{slug} → Cloudflare edge cache → R2
```

Zero load on Railway for published page views. Published pages cannot execute server-side code, cannot set cookies on toaide.com.

---

## Deploy

Push to `main` → Railway builds → `alembic upgrade head` → `uvicorn` starts → health check passes → traffic swaps. ~3 minutes, zero manual steps.

```toml
# railway.toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python -m alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port $PORT --workers 4"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 5
```

Rollback: `railway rollback --service aide` (~30 seconds).

---

## Code Patterns

### New Endpoint Checklist
1. Pydantic request/response models in `backend/models/`
2. Repo method with parameterized SQL in `backend/repos/`
3. Thin route handler in `backend/routes/` using `Depends(get_current_user)`
4. All queries via `user_conn(user_id)`
5. Register route in `backend/main.py`

### New Table Checklist
1. Alembic migration (nullable columns or with defaults)
2. RLS policy: `USING (user_id = current_setting('app.current_user_id')::uuid)`
3. Grant permissions to `aide_app` role
4. Add to masked view for `aide_readonly` if contains PII
5. Cross-user test: verify user A cannot access user B's data
6. Pydantic model in `backend/models/`
7. Repo in `backend/repos/`

### Testing
- `pytest-asyncio` for async tests
- CI spins up Postgres 16 service container
- RLS cross-user isolation tests are mandatory for any user-data table
- `ruff check` and `ruff format --check` must pass
- `bandit -r backend/ -ll` for security scanning

---

## What's NOT in v1

Explicitly descoped — do not build these:

- Team tier / collaboration
- Custom domains for published pages
- Analytics dashboard
- PPTX export
- Real-time multi-user collaboration
- Template marketplace with payments
- Conversation compression (build when someone hits context limits)
- Mobile app (web-responsive is enough)

---

## Key Docs

Read these before implementing features:

| Doc | What it covers |
|-----|---------------|
| `docs/prds/aide_prd.md` | Product vision, user flows, feature requirements |
| `docs/prds/aide_editor_prd.md` | Editor layout, chat overlay, preview, voice/image input |
| `docs/strategy/aide_living_objects.md` | Living object thesis, ears/brain/body model, channel architecture |
| `docs/strategy/aide_engine_distribution.md` | Engine distribution across Claude surfaces |
| `docs/tpm/aide_launch_plan.md` | 6-phase launch plan with Signal ear, task checklists |
| `docs/eng_design/aide_architecture.md` | Event-sourced kernel, data tiers, state flow |
| `docs/eng_design/specs/aide_reducer_spec.md` | Reducer pure function, primitive handlers, error codes |
| `docs/eng_design/specs/aide_renderer_spec.md` | HTML/CSS generation, block rendering, embedded JSON |
| `docs/eng_design/specs/aide_assembly_spec.md` | Assembly layer: load, save, apply, compact, publish |
| `docs/eng_design/specs/aide_primitive_schemas_spec.md` | Full primitive catalog with payload schemas |
| `docs/infrastructure/aide_infrastructure.md` | Stack architecture, deploy flow, scaling plan |
| `docs/infrastructure/aide_cicd.md` | CI/CD pipeline, migration safety, project structure |
| `docs/infrastructure/aide_data_access.md` | Database patterns, RLS, connection handling |
| `docs/aide_security_checklist.md` | Every security item that must be true before launch |

---

## Environment Variables

Set in Railway dashboard, never in code:

```
DATABASE_URL        # Neon Postgres connection string (?sslmode=require)
R2_ENDPOINT         # Cloudflare R2 S3-compatible endpoint
R2_ACCESS_KEY       # R2 API key (read/write for workspaces)
R2_SECRET_KEY       # R2 API secret
RESEND_API_KEY      # Transactional email
ANTHROPIC_API_KEY   # Managed AI routing (L2 Haiku, L3 Sonnet)
OPENAI_API_KEY      # Whisper speech-to-text fallback
STRIPE_SECRET_KEY   # Payments
STRIPE_WEBHOOK_SECRET # Webhook signature verification
SLACK_WEBHOOK       # Alerts (abuse, errors, deploy, break-glass)
JWT_SECRET          # 256-bit minimum, HS256
```
