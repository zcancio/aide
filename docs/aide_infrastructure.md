# AIde — Infrastructure Plan

**Goal:** Deploy and run AIde with zero ops work. Push a branch, it deploys.
**Constraint:** Keep it cheap. ~$6/mo at launch, scales with usage.

---

## Architecture

```
                         Cloudflare
                    ┌──────────────────┐
                    │  DNS + CDN + WAF │
                    │  toaide.com      │
                    │  get.toaide.com│
                    └────────┬─────────┘
                             │
                             │  HTTPS
                             │
                    ┌────────▼─────────┐
                    │     Railway      │
                    │    (compute)     │
                    │                  │
                    │  FastAPI app     │
                    │  auto-scaled     │
                    │  zero-downtime   │
                    │  deploy          │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │                             │
       ┌──────▼───────┐           ┌────────▼────────┐
       │    Neon       │           │  Cloudflare R2  │
       │  Postgres     │           │  aide files     │
       │  us-east-1    │           │  published pages│
       │  (managed)    │           │  (global CDN)   │
       └──────────────┘           └─────────────────┘
```

---

## Why This Stack

| Decision | Rationale |
|----------|-----------|
| **Railway** | Git-push deploys, auto-scaling, zero-downtime, rollbacks. $5-20/mo. Zero ops. |
| **Neon Postgres** | Managed, scale-to-zero, free tier, PITR, RLS support. $0 at launch. |
| **Cloudflare R2** | Zero egress fees. Published pages served via CDN. Free tier = 10GB. |
| **Cloudflare DNS** | CDN caching for published pages, DNS management, WAF. |

---

## Compute: Railway

### Why Railway

- **Git-push = deployed.** Push to `main`, Railway builds and deploys automatically.
- **Zero-downtime deploys.** New instance starts, health check passes, traffic swaps. Built-in.
- **Instant rollbacks.** One click in dashboard or `railway rollback` in CLI.
- **Preview environments.** Every PR gets its own URL for testing.
- **No servers to manage.** No SSH, no systemd, no Docker config, no firewall rules, no fail2ban.
- **Logs, metrics, alerts** built into the dashboard.

### Configuration

Railway detects Python automatically via `requirements.txt`. Configure via `railway.toml`:

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

That `startCommand` is the key line: **migrations run automatically before every deploy.** If migrations fail, the deploy fails, old version keeps serving. If they succeed, the app starts, health check passes, traffic swaps.

### Environment Variables

Set in Railway dashboard (Settings → Variables). Injected at runtime, never in code or build.

```
DATABASE_URL=postgres://user:pass@ep-xxx.us-east-1.aws.neon.tech/aidedb?sslmode=require
R2_ENDPOINT=https://ACCOUNT.r2.cloudflarestorage.com
R2_ACCESS_KEY=xxx
R2_SECRET_KEY=xxx
RESEND_API_KEY=xxx
STRIPE_SECRET_KEY=xxx
STRIPE_WEBHOOK_SECRET=xxx
SLACK_WEBHOOK=xxx
JWT_SECRET=xxx
```

### Deploy Flow

```
Push to main
     │
     ▼
Railway detects change
     │
     ▼
Nixpacks builds (installs Python deps, ~1-2 min)
     │
     ▼
Start command runs:
  1. alembic upgrade head (migrations)
  2. uvicorn starts on $PORT
     │
     ▼
Health check passes (/health returns 200)
     │
     ▼
Traffic swaps to new instance (zero downtime)
Old instance drains and stops
     │
     ▼
Done. ~3 minutes total.
```

### Deploying a Specific Branch

```bash
# Railway CLI
railway up --service aide            # deploy current branch

# Or in the dashboard:
# Settings → Source → change branch → Save → Railway redeploys
```

### Rollback

```bash
# Railway CLI
railway rollback --service aide

# Or in dashboard: Deployments → previous deploy → Rollback
```

Every deploy is saved. Rollback takes ~30 seconds.

---

## Database: Neon Postgres

### Why Neon

- **Scale-to-zero:** No traffic at 3am = no compute cost.
- **Free tier:** 100 CU-hours/mo, 0.5GB storage. Enough for months.
- **Point-in-time recovery:** Restore to any second. No pg_dump crons.
- **Branching:** Clone your prod database for testing in seconds.
- **Connection pooling:** Built-in.
- **RLS support:** Row-Level Security works natively. Critical for AIde's data access model.

### Tiers

| Tier | Cost | When |
|------|------|------|
| **Free** | $0/mo | Launch through ~500 users |
| **Launch** | $19/mo | >0.5GB storage or 7-day PITR. ~500-5,000 users. |
| **Scale** | $69/mo | HA, SLA, private networking. 5,000+ users. |

### Schema

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE NOT NULL,
    name            TEXT,
    tier            TEXT DEFAULT 'free' CHECK (tier IN ('free', 'pro')),
    stripe_customer_id TEXT,
    stripe_sub_id   TEXT,
    turn_count      INTEGER DEFAULT 0,
    turn_week_start TIMESTAMPTZ DEFAULT now(),
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE magic_links (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL,
    token           TEXT UNIQUE NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL,
    used            BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_magic_links_token ON magic_links(token);
CREATE INDEX idx_magic_links_email ON magic_links(email);

CREATE TABLE aides (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    title           TEXT DEFAULT 'Untitled',
    slug            TEXT UNIQUE,
    status          TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
    r2_prefix       TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aide_id         UUID REFERENCES aides(id) ON DELETE CASCADE,
    messages        JSONB DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE published_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aide_id         UUID REFERENCES aides(id) ON DELETE CASCADE,
    version         INTEGER NOT NULL,
    r2_key          TEXT NOT NULL,
    notes           TEXT,
    size_bytes      INTEGER,
    published_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE(aide_id, version)
);

CREATE INDEX idx_aides_user ON aides(user_id);
CREATE INDEX idx_aides_slug ON aides(slug);
CREATE INDEX idx_conversations_aide ON conversations(aide_id);
CREATE INDEX idx_versions_aide ON published_versions(aide_id);
```

---

## File Storage: Cloudflare R2

Aide files and published snapshots live in R2. App stays stateless.

### Buckets

| Bucket | Purpose | Access |
|--------|---------|--------|
| `aide-workspaces` | Active aide files being edited | Private (app only) |
| `aide-published` | Published page snapshots | Public (via R2 custom domain) |

### Published Page Serving

```
User visits toaide.com/my-page
  → Cloudflare edge cache (hit? serve immediately)
  → R2 bucket: aide-published/{slug}/index.html
  → Cached at edge for subsequent visitors
```

Zero load on Railway for published page views.

---

## Backup Strategy (All Managed, Zero Ops)

| Layer | What | Who handles it | RPO |
|-------|------|----------------|-----|
| **Neon PITR** | Database | Neon (automatic) | ~1 second |
| **R2 durability** | Files | Cloudflare (11 9's) | 0 |
| **Railway deploy history** | App code | Railway (every deploy saved) | 0 |

No backup scripts. No cron jobs. No snapshots to manage.

---

## Scaling

| Stage | Users | Railway | DB | Monthly Cost |
|-------|-------|---------|-----|-------------|
| Launch | 0-500 | Hobby ($5) | Neon Free | ~$6 |
| Growing | 500-2,000 | Pro ($20 + usage) | Neon Launch $19 | ~$45 |
| Scaling | 2,000-10,000 | Pro (auto-scales) | Neon Launch $19 | ~$60 |
| Big | 10,000-50,000 | Pro (multiple instances) | Neon Scale $69 | ~$120 |

---

## Monitoring

### Built-in (Railway)
- Deploy logs, build logs, runtime logs
- CPU/memory/network metrics
- Deploy notifications
- Automatic restart on crash

### Add-ons ($0)
- **BetterStack** free tier: ping `/health` every 3 min, SMS/call on failure
- **Sentry** free tier: error tracking, `send_default_pii=False`
- **Built-in abuse detection:** background loop checking thresholds (see docs/aide_monitoring.md)
- **Slack webhooks:** abuse alerts, traffic spikes, break-glass access

---

## Security

### What Railway Handles
- TLS termination (automatic)
- DDoS protection
- Network isolation between services
- Encrypted environment variables
- No SSH access (no server to SSH into)
- Build isolation (each build is fresh)

### What You Handle
- Application security (see docs/aide_security_checklist.md)
- Secrets in Railway env vars (never in code)
- Cloudflare WAF rules for published pages

---

## Cost Summary

| Item | Monthly Cost |
|------|-------------|
| Railway Hobby plan | ~$5 |
| Neon Postgres (free tier) | $0 |
| Cloudflare R2 (free tier) | $0 |
| Cloudflare (free plan) | $0 |
| BetterStack (free tier) | $0 |
| Sentry (free tier) | $0 |
| Domain (toaide.com) | ~$0.87 |
| **Total at launch** | **~$6/mo** |

---

## Setup Checklist

### Railway
- [ ] Create Railway project
- [ ] Connect GitHub repo
- [ ] Set deploy branch to `main`
- [ ] Add `railway.toml` to repo
- [ ] Set all environment variables
- [ ] Add custom domains (toaide.com, get.toaide.com)
- [ ] Verify: push to main → builds → deploys → health check passes

### Database
- [ ] Create Neon project (free tier, us-east-1)
- [ ] Run initial schema migration
- [ ] Save connection string to Railway env vars

### Storage
- [ ] Create R2 buckets (aide-workspaces, aide-published)
- [ ] Generate R2 API keys
- [ ] Save R2 credentials to Railway env vars
- [ ] Configure R2 custom domain for published pages

### DNS
- [ ] Cloudflare DNS: toaide.com → Railway
- [ ] Cloudflare DNS: get.toaide.com → Railway
- [ ] R2 custom domain for published pages
- [ ] Verify SSL on all endpoints

### Monitoring
- [ ] BetterStack uptime monitor
- [ ] Sentry error tracking
- [ ] Slack webhook for alerts

### Verify
- [ ] Full flow: magic link → create aide → edit → publish → view
- [ ] Rollback: click rollback → previous version serves
