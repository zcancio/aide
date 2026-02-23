# AIde — CI/CD Pipeline

**CI:** GitHub Actions (lint + test on every push)
**CD:** Railway (auto-deploys from `main`, runs migrations, zero downtime)
**Rollback:** One click in Railway dashboard

---

## How It Works

```
Developer pushes to any branch
         │
         ▼
┌─────────────────┐
│ CI: Lint + Test │  (GitHub Actions, ~2 min)
└────────┬────────┘
         │ pass
         │
         │── feature branch? → done (CI only)
         │
         │── main branch? ──┐
                            ▼
                   ┌──────────────────┐
                   │  Railway CD      │
                   │                  │
                   │  1. Build app    │  (~1-2 min)
                   │  2. Run alembic  │ 
                   │  3. Start app    │
                   │  4. Health check │
                   │  5. Swap traffic │
                   └────────┬─────────┘
                            │
                     Slack notification
```

That's it. No Docker config, no GHCR, no SSH, no deploy scripts, no blue/green orchestration. Railway handles all of it.

---

## CI: GitHub Actions (Every Push)

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: ['*']
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: aide
          POSTGRES_PASSWORD: test
          POSTGRES_DB: aide_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-dev.txt

      - name: Lint
        run: |
          ruff check backend/
          ruff format --check backend/

      - name: Security scan
        run: |
          pip install bandit
          bandit -r backend/ -ll

      - name: Run migrations
        env:
          DATABASE_URL: postgres://aide:test@localhost:5432/aide_test
        run: alembic upgrade head

      - name: Test
        env:
          DATABASE_URL: postgres://aide:test@localhost:5432/aide_test
          TESTING: "true"
        run: pytest backend/tests/ -v --tb=short
```

### What CI Catches

- **ruff check:** Linting, unused imports, code quality
- **ruff format:** Consistent formatting
- **bandit:** Python security issues (SQL injection patterns, hardcoded secrets, eval usage)
- **alembic upgrade head:** Migrations work on clean database
- **pytest:** Unit tests, integration tests, RLS cross-user tests

---

## CD: Railway (Push to Main)

Railway watches your GitHub repo. When `main` changes, it:

1. **Builds** using Nixpacks (detects Python, installs deps)
2. **Runs your start command:** `alembic upgrade head && uvicorn ...`
3. **Health checks** `/health`
4. **Swaps traffic** — zero downtime
5. **Drains old instance** — existing connections finish

Configuration is one file:

```toml
# railway.toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "DATABASE_URL=$DATABASE_URL_OWNER python -m alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port $PORT --workers 4"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 5
```

### Migration Safety

Migrations run before the app starts. If a migration fails:
- The start command fails
- Railway keeps the old instance running
- You see the error in Railway logs
- Fix the migration, push again

**Critical rule:** Migrations must be backward-compatible. The old code is still serving traffic while the new code runs migrations. This means:
- Add columns with defaults or as nullable — never add non-nullable columns without defaults
- Never rename columns in one step — add new, migrate data, drop old (3 deploys)
- Never drop columns that old code still reads

---

## Rollback

```bash
# CLI
railway rollback --service aide

# Dashboard: Deployments → click previous deploy → Rollback
```

Takes ~30 seconds. Redeploys the exact same build artifact.

---

## Deploying a Specific Branch

For testing or staging:

```bash
# Railway CLI — deploy current branch
railway up --service aide

# Dashboard: Settings → Source → change branch → Save
```

Railway also creates preview environments for PRs if you enable it.

---

## Slack Notifications

Railway has built-in deploy notifications. For custom alerts, add a small notification step:

```yaml
# .github/workflows/notify.yml
name: Deploy Notification

on:
  workflow_run:
    workflows: ["CI"]
    branches: [main]
    types: [completed]

jobs:
  notify:
    runs-on: ubuntu-latest
    if: ${{ github.event.workflow_run.conclusion == 'failure' }}
    steps:
      - name: Notify Slack on CI failure
        run: |
          curl -X POST "${{ secrets.SLACK_WEBHOOK }}" \
            -H 'Content-type: application/json' \
            -d '{"text":"❌ CI failed on main: ${{ github.event.workflow_run.html_url }}"}'
```

Railway handles deploy success/failure notifications natively.

---

## Dev Workflow

```bash
# Feature work
git checkout -b feature/magic-links
# ... code ...
git push origin feature/magic-links
# → CI runs lint + test + security scan (~2 min)

# Ready to ship
# Merge PR (or push to main directly)
git checkout main
git merge feature/magic-links
git push origin main
# → CI passes → Railway builds → migrations run → deploys → done
# → Total: ~3-4 minutes, zero manual steps
```

---

## Project Structure

```
aide/
├── .github/
│   └── workflows/
│       └── ci.yml                # lint + test + security scan (every push)
├── .claude/
│   ├── README.md
│   └── commands/                 # Claude Code slash commands
├── railway.toml                  # Railway deploy config
├── CLAUDE.md                     # Claude Code project instructions
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── tests/
│   │   ├── conftest.py
│   │   └── test_*.py
│   └── ...
├── frontend/
│   └── index.html
├── alembic/
│   ├── alembic.ini
│   └── versions/
├── docs/                         # Architecture docs (from Claude.ai)
│   ├── aide_prd.md
│   ├── aide_launch_plan.md
│   ├── aide_security_checklist.md
│   └── ...
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml                # ruff config
```

---

## What's Gone (Compared to Hetzner DIY)

| Before (Hetzner) | Now (Railway) |
|---|---|
| Dockerfile | Not needed (Nixpacks auto-detects) |
| .dockerignore | Not needed |
| GHCR image registry | Not needed |
| deploy.sh script | Not needed |
| Caddyfile | Not needed |
| Blue/green orchestration | Built into Railway |
| SSH keys for deploy | Not needed |
| systemd unit files | Not needed |
| Server hardening (UFW, fail2ban) | Not needed (no server) |
| Cloudflare Tunnel config | Not needed (Railway has custom domains) |
| Health check scripts | Not needed (Railway built-in) |
| Failover scripts | Not needed (Railway auto-restarts) |
| Docker login to GHCR | Not needed |
| Caddy install + config | Not needed |
| app-2 standby server | Not needed |

**Lines of deploy config:** ~400 lines of bash/yaml/Dockerfile → 10 lines of `railway.toml`

---

## Cost

| Item | Cost |
|------|------|
| GitHub Actions | $0 (free tier: 2,000 min/mo) |
| Railway | $5/mo Hobby (or $20/mo Pro) |
| **Total CI/CD cost** | **$5/mo** |

The $5/mo buys you: zero-downtime deploys, instant rollbacks, auto-scaling, preview environments, logs, metrics, and your weekends back.
