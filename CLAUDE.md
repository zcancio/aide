# AIde — Claude Code Guardrails

**Tagline:** "For what you're living."

You are working in a 130k+ line codebase. You CANNOT hold the full system in context. Act accordingly.

---

## Prime Directive

**Touch only what you're told to touch.** If the user says "fix the bug in `l2_compiler.py`", you modify `l2_compiler.py` and nothing else. If a fix requires changes in other files, STOP and explain what else needs to change. Let the user decide.

---

## Absolute Rules (violating any of these = broken build)

1. **Never modify files you weren't asked to modify.** If you think a change is needed elsewhere, say so. Don't do it.
2. **Never re-implement something that already exists.** Before writing a new function, grep the codebase: `grep -r "function_name" backend/ engine/`. If it exists, use it.
3. **Never change function signatures in repos/ or services/ without explicit approval.** Other files depend on them. Changing a signature is a multi-file change — flag it.
4. **Raw asyncpg only. No ORM. No SQLAlchemy.** Parameterized queries with `$1`, `$2`. NEVER f-strings or `.format()` in SQL.
5. **All SQL lives in `backend/repos/`.** Routes never touch SQL. Services never touch SQL.
6. **All user-scoped queries use `user_conn(user_id)` for RLS.** `system_conn()` is ONLY for background tasks and auth flows.
7. **All request/response models are Pydantic** with `model_config = {"extra": "forbid"}` on request models.
8. **No new dependencies without explicit approval.** Don't add imports for packages not in requirements.txt.

---

## Boundaries — Know Your Zones

### Backend Layers (changes must stay within ONE layer unless approved)

```
routes/          → HTTP handlers. Thin. No SQL, no business logic.
                   Calls services/ and repos/. Uses Depends(get_current_user).

services/        → Business logic + external integrations. No SQL, no HTTP.
                   Calls repos/ for data. Calls external APIs.

repos/           → Data access. All SQL here. Returns Pydantic models or dicts.
                   Never imported by routes/ directly for mutations without service layer.

models/          → Pydantic models only. No app imports. No logic.

middleware/      → Request-scoped concerns (rate limiting, usage, sentry).
```

**If a change requires crossing layers, STOP and say:** "This fix needs changes in [X] and [Y]. Here's what I'd change in each. Want me to proceed?"

### Engine (DO NOT touch without explicit instruction)

```
engine/kernel/   → Pure functions. Deterministic. reducer.py, renderer.py, primitives.py, validator.py
                   These have extensive test suites. Any change here requires running ALL kernel tests.
```

The kernel is the most sensitive code in the project. Never modify it as a side effect of another task.

### Frontend

```
frontend/        → Two HTML files. Changes here are separate from backend work.
```

---

## File-Specific Warnings

| File | Danger Level | Why |
|------|-------------|-----|
| `backend/db.py` | 🔴 CRITICAL | Connection pool, RLS. Touch = break everything. |
| `backend/auth.py` | 🔴 CRITICAL | JWT + auth. Security-sensitive. |
| `backend/main.py` | 🟡 CAUTION | App startup, route registration. Only add routes here. |
| `engine/kernel/reducer.py` | 🔴 CRITICAL | Core state machine. Pure, deterministic, heavily tested. |
| `engine/kernel/renderer.py` | 🔴 CRITICAL | HTML generation. Pure, deterministic, heavily tested. |
| `engine/kernel/types.py` | 🟡 CAUTION | Shared types — changes cascade everywhere. |
| `alembic/versions/*` | 🟡 CAUTION | Migrations must be backward-compatible. See migration rules below. |

---

## Before You Write Code

### Before ANY change:
1. Read the file(s) you're about to modify
2. Grep for related usages: `grep -r "function_or_class_name" backend/ engine/`
3. Check if what you're building already exists somewhere
4. If the change touches more than 2 files, pause and outline the plan first

### Before modifying a function:
1. Check who calls it: `grep -r "function_name" backend/ engine/`
2. If it's called from multiple places, DO NOT change the signature
3. If you must change behavior, consider adding a new function instead

### Before adding a new file:
1. Check if the functionality belongs in an existing file
2. Follow the existing naming convention in that directory
3. Add appropriate `__init__.py` exports if needed

---

## Testing Rules

- After ANY change to `engine/kernel/`, run: `pytest engine/kernel/tests/ -v`
- After ANY change to `backend/repos/` or `backend/routes/`, run: `pytest backend/tests/ -v`
- After ANY change to auth or RLS: run the cross-user isolation tests specifically
- Run `ruff check` and `ruff format --check` before considering a task done
- If tests fail, FIX YOUR CHANGE. Don't modify tests to pass unless explicitly asked.

---

## Migration Rules

Alembic migrations must be backward-compatible (old code is still serving during deploy):
- Add columns as `nullable` or with `server_default`
- Never drop columns that old code reads
- Column renames = 3 deploys (add new → migrate data → drop old)
- Always test: `alembic upgrade head` then `alembic downgrade -1` then `alembic upgrade head`

---

## Existing Patterns — Follow These, Don't Invent New Ones

### New endpoint:
1. Pydantic models in `backend/models/`
2. Repo method in `backend/repos/` (parameterized SQL, `$1`/`$2`)
3. Thin route in `backend/routes/` using `Depends(get_current_user)`
4. Queries via `user_conn(user_id)`
5. Register in `backend/main.py`

### New table:
1. Alembic migration (nullable/defaults)
2. RLS policy: `USING (user_id = current_setting('app.current_user_id')::uuid)`
3. Grant to `aide_app`
4. Cross-user isolation test
5. Pydantic model, repo, route (following patterns above)

---

## What NOT to Build

These are explicitly descoped. Do not implement even if they seem like good ideas:
- Team tier / collaboration
- Custom domains for published pages
- Analytics dashboard
- PPTX export
- Real-time multi-user editing
- Template marketplace
- Conversation compression
- Mobile app

---

## When In Doubt

**Ask.** It is always better to pause and clarify than to make a 5-file change that introduces regressions. The user would rather answer a question than debug a cascade.

---

## Key Docs (read BEFORE implementing features)

### Architecture & Design (numbered series — read in order)
| Doc | Covers |
|-----|--------|
| `docs/eng_design/00_overview.md` | System overview |
| `docs/eng_design/01_data_model.md` | Data model |
| `docs/eng_design/02_jsonl_schema.md` | JSONL event schema |
| `docs/eng_design/03_streaming_pipeline.md` | Streaming pipeline |
| `docs/eng_design/04_display_components.md` | Display components |
| `docs/eng_design/05_intelligence_tiers.md` | L2/L3 AI routing |
| `docs/eng_design/06_prompts.md` | Prompt design |
| `docs/eng_design/07_edge_cases.md` | Edge cases |
| `docs/eng_design/08_capability_boundaries.md` | What the system can/can't do |
| `docs/eng_design/09_implementation_plan.md` | Implementation plan |

### Specs
| Doc | Covers |
|-----|--------|
| `docs/eng_design/specs/api_auth_spec.md` | Auth API spec |
| `docs/eng_design/specs/aide_ui_design_system_spec.md` | UI design system |
| `docs/eng_design/aide_editor_architecture_change.md` | Editor architecture changes |

### Product
| Doc | Covers |
|-----|--------|
| `docs/prds/aide_prd.md` | Product vision, user flows |
| `docs/prds/aide_editor_prd.md` | Editor layout, chat, preview |
| `docs/strategy/aide_living_objects.md` | Living object thesis |
| `docs/strategy/aide_engine_distribution.md` | Engine distribution |

### Infrastructure
| Doc | Covers |
|-----|--------|
| `docs/infrastructure/aide_data_access.md` | DB patterns, RLS, connections |
| `docs/infrastructure/aide_infrastructure.md` | Stack architecture, deploy |
| `docs/infrastructure/aide_cicd.md` | CI/CD pipeline |
| `docs/infrastructure/aide_errors_privacy.md` | Error handling, privacy |
| `docs/infrastructure/aide_monitoring.md` | Monitoring setup |

### Other
| Doc | Covers |
|-----|--------|
| `docs/aide_security_checklist.md` | Security requirements |
| `docs/aide_flight_recorder_design.md` | Flight recorder system |
| `docs/aide_signal_ear_design.md` | Signal ear design |

---

## Stack Reference

| Layer | Tech |
|-------|------|
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| Database | Neon Postgres, raw asyncpg, RLS |
| Migrations | Alembic |
| Storage | Cloudflare R2 |
| Email | Resend (magic links) |
| Payments | Stripe |
| Deploy | Railway (push to main) |
| CI | GitHub Actions (ruff + pytest + bandit) |
| Auth | Magic links → JWT in HTTP-only cookie, 24hr expiry |

---

## AI Voice (for any user-facing text)

- No first person ("I updated...")
- No encouragement ("Great!", "Nice!")
- No emojis
- No self-narration ("I'm going to...", "Let me...")
- Mutations are declarative: "Budget: $1,350."
- State over action. Silence is valid.
