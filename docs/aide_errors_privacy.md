# AIde — Error Logging & Data Privacy

Two separate concerns, one document.

---

## Part 1: Error & Bug Logging

### Sentry (Free Tier)

Sentry auto-captures every unhandled exception, gives you the full stack trace, the request that caused it, which user was affected, and breadcrumbs showing what happened before the crash. Free tier gives you 5K errors/month — more than enough until you're big.

#### Setup (5 minutes)

```bash
pip install sentry-sdk[fastapi]
```

```python
# backend/main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=os.environ["SENTRY_DSN"],
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,       # 10% of requests traced for performance
    profiles_sample_rate=0.1,      # 10% profiled
    environment=os.environ.get("ENVIRONMENT", "production"),
    release=os.environ.get("GIT_SHA", "unknown"),
    send_default_pii=False,        # IMPORTANT: don't send user PII to Sentry
)
```

**`send_default_pii=False`** is critical. This means Sentry gets the error + stack trace but NOT the user's email, IP, or request body. Errors are debuggable without leaking user data to a third party.

#### What Sentry Captures

| Data | Captured? | Notes |
|------|-----------|-------|
| Stack trace | ✅ | Full traceback with local variables |
| Request URL + method | ✅ | Which endpoint crashed |
| Request headers | ✅ (sanitized) | Auth headers stripped |
| Request body | ❌ | Disabled via `send_default_pii=False` |
| User email/IP | ❌ | Disabled — privacy first |
| User ID (anonymous) | ✅ | Set manually (see below) |
| Breadcrumbs | ✅ | DB queries, HTTP calls, logs before the crash |
| Release/commit SHA | ✅ | Know exactly which deploy caused it |

#### Attaching Anonymous User Context

```python
# backend/middleware/sentry_context.py
import sentry_sdk

def set_sentry_user(user_id: str | None):
    """Attach user context without PII. Just the UUID."""
    if user_id:
        sentry_sdk.set_user({"id": user_id})
    else:
        sentry_sdk.set_user(None)
```

Now when an error hits, Sentry shows "User abc-123-def had this error" — you can look up that UUID in your own database if needed, but Sentry never sees their email or name.

#### Slack Alerts on Errors

In Sentry dashboard: Settings → Integrations → Slack → Create alert rule:
- **When:** A new issue is created
- **Alert:** Post to #aide-errors channel
- **Include:** Error title, stack trace preview, link to Sentry

#### What You See

```
#aide-errors

🐛 New issue: ZeroDivisionError in /api/aide/{aide_id}/publish
   File "backend/routes/publish.py", line 47, in publish_aide
     ratio = total_turns / active_days
   ZeroDivisionError: division by zero
   
   User: abc-123-def | Release: sha-a1b2c3d
   → View in Sentry: https://sentry.io/...
```

You click, you see the full trace, the request, what happened before it. Fix it, deploy, done.

---

## Part 2: Database Privacy & Break-Glass Access

This is the harder problem. You want:
1. The app can only access data it needs for the current user
2. No developer (including you) can casually browse user data
3. If someone DOES access raw data, there's an immutable audit record
4. Emergency access exists but it's loud and traceable

### Architecture: Three Database Roles

```
┌─────────────────────────────────────────────────┐
│                    Neon Postgres                 │
│                                                  │
│  Role: aide_app (normal operations)              │
│  ├── Can SELECT/INSERT/UPDATE/DELETE             │
│  ├── RLS enforced: only sees current user's rows │
│  └── Cannot BYPASSRLS, cannot access audit_log   │
│                                                  │
│  Role: aide_readonly (analytics/debugging)       │
│  ├── Can SELECT only (no writes)                 │
│  ├── RLS enforced: only sees aggregate data      │
│  ├── Cannot see PII columns (email, name)        │
│  └── Every query logged to audit_log             │
│                                                  │
│  Role: aide_breakglass (emergency only)          │
│  ├── BYPASSRLS — sees everything                 │
│  ├── Time-limited credentials (1 hour expiry)    │
│  ├── Every query logged to audit_log             │
│  └── Slack alert fires on activation             │
└─────────────────────────────────────────────────┘
```

### Schema: Privacy by Design

```sql
-- ============================================================
-- ROLES
-- ============================================================

-- App role: used by the FastAPI application
CREATE ROLE aide_app LOGIN PASSWORD '...';

-- Readonly role: for analytics queries, debugging
CREATE ROLE aide_readonly LOGIN PASSWORD '...';

-- Break-glass role: emergency full access
-- NOLOGIN by default — credentials created on demand
CREATE ROLE aide_breakglass NOLOGIN BYPASSRLS;

-- ============================================================
-- TABLES
-- ============================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE NOT NULL,      -- PII
    name            TEXT,                       -- PII
    picture         TEXT,                       -- PII
    tier            TEXT DEFAULT 'free',
    stripe_customer_id TEXT,                    -- Sensitive
    stripe_sub_id   TEXT,                       -- Sensitive
    turn_count      INTEGER DEFAULT 0,
    turn_week_start TIMESTAMPTZ DEFAULT now(),
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE aides (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    title           TEXT DEFAULT 'Untitled',
    slug            TEXT UNIQUE,
    status          TEXT DEFAULT 'draft',
    r2_prefix       TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aide_id         UUID REFERENCES aides(id) ON DELETE CASCADE,
    messages        JSONB DEFAULT '[]'::jsonb,  -- User content — most sensitive
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- AUDIT LOG (append-only, immutable)
-- ============================================================

CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ DEFAULT now() NOT NULL,
    db_role         TEXT NOT NULL DEFAULT current_user,
    action          TEXT NOT NULL,              -- 'breakglass_activate', 'query', 'export', etc.
    target_table    TEXT,
    target_user_id  UUID,                      -- whose data was accessed
    query_text      TEXT,                      -- the actual SQL (for break-glass)
    ip_address      INET,
    justification   TEXT,                      -- why (required for break-glass)
    metadata        JSONB DEFAULT '{}'
);

-- Nobody can UPDATE or DELETE audit log entries
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY audit_insert_only ON audit_log
    FOR INSERT
    WITH CHECK (true);

CREATE POLICY audit_select_admin ON audit_log
    FOR SELECT
    USING (current_user IN ('aide_breakglass', 'aide_readonly'));

-- No UPDATE or DELETE policies = immutable

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE aides ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

-- App role: can only see the current user's data
-- The app sets current_setting('app.user_id') on each request
CREATE POLICY users_app_policy ON users
    FOR ALL TO aide_app
    USING (id::text = current_setting('app.user_id', true));

CREATE POLICY aides_app_policy ON aides
    FOR ALL TO aide_app
    USING (user_id::text = current_setting('app.user_id', true));

CREATE POLICY conversations_app_policy ON conversations
    FOR ALL TO aide_app
    USING (aide_id IN (
        SELECT id FROM aides WHERE user_id::text = current_setting('app.user_id', true)
    ));

-- Readonly role: aggregate access only, no PII
CREATE POLICY users_readonly_policy ON users
    FOR SELECT TO aide_readonly
    USING (true);  -- Can see rows but PII columns are masked (see view below)

CREATE POLICY aides_readonly_policy ON aides
    FOR SELECT TO aide_readonly
    USING (true);

-- Readonly CANNOT see conversations at all
-- (no policy = no access when RLS is enabled)

-- Break-glass: BYPASSRLS — sees everything, but every action is logged

-- ============================================================
-- MASKED VIEW FOR READONLY
-- ============================================================

CREATE VIEW users_safe AS
SELECT
    id,
    '***' || right(email, length(email) - position('@' in email) + 1) AS email_domain,
    tier,
    turn_count,
    turn_week_start,
    created_at
FROM users;

GRANT SELECT ON users_safe TO aide_readonly;

-- Readonly should use users_safe, not users directly
-- Even if they query users, RLS allows it but PII columns are there
-- The view is the intended interface

-- ============================================================
-- PERMISSIONS
-- ============================================================

-- App role permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON users, aides, conversations, usage_events TO aide_app;
GRANT INSERT ON audit_log TO aide_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO aide_app;

-- Readonly permissions
GRANT SELECT ON users_safe, aides, usage_events TO aide_readonly;
GRANT SELECT, INSERT ON audit_log TO aide_readonly;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO aide_readonly;

-- Break-glass gets everything (but NOLOGIN by default)
GRANT ALL ON ALL TABLES IN SCHEMA public TO aide_breakglass;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO aide_breakglass;
```

### How the App Sets User Context

```python
# backend/db.py
from contextlib import asynccontextmanager
import asyncpg

pool: asyncpg.Pool = None

async def init_pool():
    global pool
    pool = await asyncpg.create_pool(
        dsn=os.environ["DATABASE_URL"],  # connects as aide_app
        min_size=2,
        max_size=10,
    )

@asynccontextmanager
async def user_db(user_id: str):
    """Get a connection scoped to a specific user via RLS."""
    async with pool.acquire() as conn:
        # Set the user context for RLS policies
        await conn.execute(
            "SELECT set_config('app.user_id', $1, true)",  # true = local to transaction
            user_id
        )
        yield conn
```

```python
# backend/routes/aides.py
@router.get("/api/aides")
async def list_aides(user = Depends(get_current_user)):
    async with user_db(str(user.id)) as conn:
        # RLS automatically filters to only this user's aides
        rows = await conn.fetch("SELECT * FROM aides ORDER BY updated_at DESC")
        return [dict(row) for row in rows]
```

Even if a bug causes the wrong user_id to be set, RLS means they can only see that user's data — not everyone's. The database enforces the boundary, not application code.

### Break-Glass Protocol

When you need emergency access to user data (debugging a critical bug, responding to a legal request, investigating abuse):

#### Step 1: Activate (automated script)

```bash
#!/bin/bash
# /opt/aide/breakglass.sh
# Usage: breakglass.sh "justification text here"

set -euo pipefail

JUSTIFICATION="$1"
EXPIRY="1 hour"
PASSWORD=$(openssl rand -base64 32)
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)

if [ -z "$JUSTIFICATION" ]; then
    echo "ERROR: Justification required."
    echo "Usage: breakglass.sh \"Investigating bug #123 for user complaint\""
    exit 1
fi

# 1. Enable login with temporary password (expires in 1 hour)
psql "$ADMIN_DATABASE_URL" << SQL
ALTER ROLE aide_breakglass LOGIN PASSWORD '$PASSWORD'
    VALID UNTIL '$(date -u -d "+$EXPIRY" +%Y-%m-%dT%H:%M:%SZ)';
SQL

# 2. Log activation to audit_log
psql "$ADMIN_DATABASE_URL" << SQL
INSERT INTO audit_log (db_role, action, justification, metadata)
VALUES ('aide_breakglass', 'breakglass_activate',
    '$JUSTIFICATION',
    '{"expires": "$(date -u -d "+$EXPIRY" +%Y-%m-%dT%H:%M:%SZ)", "activated_by": "$(whoami)@$(hostname)"}'
);
SQL

# 3. Alert Slack
curl -X POST "$SLACK_WEBHOOK" \
    -H 'Content-type: application/json' \
    -d "{
        \"text\": \"🔓 BREAK-GLASS ACTIVATED\nWho: $(whoami)\nWhen: $TIMESTAMP\nExpires: $EXPIRY\nJustification: $JUSTIFICATION\nAll queries will be logged.\"
    }"

# 4. Output connection string (don't log this)
echo ""
echo "========================================"
echo "  BREAK-GLASS SESSION ACTIVE"
echo "  Expires in: $EXPIRY"
echo "  ALL QUERIES ARE BEING LOGGED"
echo "========================================"
echo ""
echo "Connect with:"
echo "  psql \"postgres://aide_breakglass:${PASSWORD}@ep-xxx.us-east-1.aws.neon.tech/aidedb?sslmode=require\""
echo ""
echo "When done, run: breakglass-deactivate.sh"
```

#### Step 2: Use (with logging)

The break-glass role has `BYPASSRLS` so it can see all rows. But a trigger logs every query:

```sql
-- Log all break-glass queries via pg_stat_statements or a function wrapper
-- Since Neon supports pg_stat_statements, you can audit after the fact

-- Alternatively, create a helper function that logs and executes:
CREATE OR REPLACE FUNCTION breakglass_query(query_text TEXT, target_user UUID DEFAULT NULL)
RETURNS SETOF RECORD
LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    -- Log the query
    INSERT INTO audit_log (db_role, action, target_table, target_user_id, query_text)
    VALUES (current_user, 'breakglass_query', NULL, target_user, query_text);

    -- Execute it
    RETURN QUERY EXECUTE query_text;
END;
$$;
```

In practice, for a solo dev, the audit log entry from activation + the Slack alert + the 1-hour expiry is sufficient. You know when it was used and why.

#### Step 3: Deactivate

```bash
#!/bin/bash
# /opt/aide/breakglass-deactivate.sh

# Disable login immediately
psql "$ADMIN_DATABASE_URL" << SQL
ALTER ROLE aide_breakglass NOLOGIN;
SQL

# Log deactivation
psql "$ADMIN_DATABASE_URL" << SQL
INSERT INTO audit_log (db_role, action, justification)
VALUES ('aide_breakglass', 'breakglass_deactivate', 'Session ended');
SQL

# Alert Slack
curl -X POST "$SLACK_WEBHOOK" \
    -H 'Content-type: application/json' \
    -d '{"text": "🔒 Break-glass session DEACTIVATED. Audit log preserved."}'

echo "Break-glass access revoked."
```

#### Step 4: Auto-expiry

Even if you forget to deactivate, the `VALID UNTIL` on the role means the password expires in 1 hour. After that, nobody can log in as `aide_breakglass` until the script is run again.

### What the Audit Trail Looks Like

```sql
SELECT ts, db_role, action, target_user_id, justification
FROM audit_log
ORDER BY ts DESC
LIMIT 10;

ts                    | db_role          | action                | target_user_id | justification
─────────────────────┼──────────────────┼──────────────────────┼────────────────┼──────────────────────────────
2026-02-12 22:15:00  | aide_breakglass  | breakglass_deactivate |                | Session ended
2026-02-12 22:14:30  | aide_breakglass  | breakglass_query      | abc-123-def    | NULL
2026-02-12 22:12:00  | aide_breakglass  | breakglass_activate   |                | Bug #47: user reports missing aide
2026-02-12 21:00:00  | aide_app         | user_login            | abc-123-def    | NULL
2026-02-12 20:55:00  | aide_app         | aide_publish          | xyz-789-ghi    | NULL
```

Every break-glass activation is visible in the audit log forever. You can't delete it (no DELETE policy on audit_log). If you ever need to prove to a user, a lawyer, or yourself that data was accessed responsibly, the trail is there.

---

## Summary

### Error Logging

| What | How | Cost |
|------|-----|------|
| Crash/exception tracking | Sentry free tier | $0 |
| Stack traces + context | Sentry auto-capture | $0 |
| Slack alerts on errors | Sentry → Slack integration | $0 |
| Performance monitoring | Sentry traces (10% sample) | $0 |
| PII leaked to Sentry | None (`send_default_pii=False`) | — |

### Data Privacy

| What | How |
|------|-----|
| App can only see current user's data | Postgres RLS with `app.user_id` session variable |
| Developer can't casually browse PII | `aide_readonly` role sees masked view, no conversations |
| Emergency full access exists | `aide_breakglass` role with BYPASSRLS |
| Break-glass is time-limited | `VALID UNTIL` = 1 hour auto-expiry |
| Break-glass is loud | Slack alert on activate + deactivate |
| Break-glass is traceable | Immutable `audit_log` table (INSERT only, no UPDATE/DELETE) |
| Nobody can erase the audit trail | RLS on audit_log — no DELETE policy for anyone |
| Conversation content is protected | Only visible via RLS-scoped app queries or break-glass |

### The Trust Model

```
Normal operation:
  App → aide_app role → RLS scoped to current user → user sees only their data
  Developer → aide_readonly role → masked PII, no conversations
  
Emergency:
  Developer → runs breakglass.sh "reason" → Slack fires → 1-hour window
  → aide_breakglass role → full access → all queries logged
  → breakglass-deactivate.sh → access revoked → Slack fires
  
Audit:
  Anyone → SELECT * FROM audit_log → full history of every break-glass session
  Nobody → DELETE/UPDATE audit_log → immutable by design
```

This isn't "trust the developer." This is "verify the developer." Even when the developer is you.
