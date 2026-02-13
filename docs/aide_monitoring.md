# AIde — Monitoring

Three things to watch. Three solutions. $0/mo.

---

## 1. Is the Server Down?

**Tool:** BetterStack free tier
**Cost:** $0
**What it does:** Pings `https://editor.toaide.com/health` every 3 minutes. If it fails, texts/calls you.

Setup takes 2 minutes:
1. Sign up at betterstack.com
2. Add monitor → HTTPS → `https://editor.toaide.com/health`
3. Add your phone number as alert contact
4. Done

Free tier includes 10 monitors, SMS/call alerts, and a status page at `status.toaide.com` if you want one. That's all you need for uptime.

---

## 2. Is a User Abusing?

**Tool:** Built-in middleware that logs to a `usage_events` table and runs a check every 5 minutes.

### What counts as abuse

| Signal | Threshold | Action |
|--------|-----------|--------|
| Turns per hour | >20 (free) / >50 (pro) | Rate limit, Slack alert |
| Aide creation rate | >10 per hour | Rate limit, Slack alert |
| Published page content flagged | Safety scanner triggers | Unpublish, Slack alert |
| Burst API calls | >100 requests/min from one user | 429 response, Slack alert |

### Schema

```sql
CREATE TABLE usage_events (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID REFERENCES users(id),
    event_type  TEXT NOT NULL,  -- 'turn', 'aide_create', 'publish', 'request'
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_usage_user_time ON usage_events(user_id, created_at);
CREATE INDEX idx_usage_type_time ON usage_events(event_type, created_at);
```

### Middleware

```python
# backend/middleware/usage.py
from fastapi import Request
from datetime import datetime, timedelta
from backend.db import pool

async def track_request(request: Request, user_id: str | None):
    """Call this in your request pipeline. Lightweight — just an INSERT."""
    async with pool.connection() as conn:
        await conn.execute(
            "INSERT INTO usage_events (user_id, event_type, metadata) VALUES ($1, $2, $3)",
            user_id, "request", {"path": request.url.path}
        )

async def check_abuse(user_id: str, event_type: str, window_minutes: int, limit: int) -> bool:
    """Returns True if user exceeds the limit. Call before processing."""
    async with pool.connection() as conn:
        count = await conn.fetchval(
            """SELECT count(*) FROM usage_events
               WHERE user_id = $1 AND event_type = $2
               AND created_at > now() - interval '%s minutes'""" % window_minutes,
            user_id
        )
        return count >= limit
```

### Abuse Check Cron (every 5 minutes)

```python
# backend/tasks/abuse_check.py
import asyncio
import httpx

SLACK_WEBHOOK = os.environ["SLACK_WEBHOOK"]

CHECKS = [
    {
        "name": "High turn rate (free users)",
        "query": """
            SELECT u.email, count(*) as turns
            FROM usage_events e JOIN users u ON e.user_id = u.id
            WHERE e.event_type = 'turn'
            AND e.created_at > now() - interval '1 hour'
            AND u.tier = 'free'
            GROUP BY u.email
            HAVING count(*) > 20
        """,
    },
    {
        "name": "Mass aide creation",
        "query": """
            SELECT u.email, count(*) as aides
            FROM usage_events e JOIN users u ON e.user_id = u.id
            WHERE e.event_type = 'aide_create'
            AND e.created_at > now() - interval '1 hour'
            GROUP BY u.email
            HAVING count(*) > 10
        """,
    },
    {
        "name": "Request flooding",
        "query": """
            SELECT u.email, count(*) as requests
            FROM usage_events e JOIN users u ON e.user_id = u.id
            WHERE e.event_type = 'request'
            AND e.created_at > now() - interval '5 minutes'
            GROUP BY u.email
            HAVING count(*) > 500
        """,
    },
]

async def run_abuse_checks():
    async with pool.connection() as conn:
        for check in CHECKS:
            rows = await conn.fetch(check["query"])
            for row in rows:
                await alert_slack(f"🚨 {check['name']}: {row['email']} ({row[1]})")

async def alert_slack(message: str):
    async with httpx.AsyncClient() as client:
        await client.post(SLACK_WEBHOOK, json={"text": message})
```

Run this as a background task in FastAPI or a separate cron process.

---

## 3. Am I Getting a Traffic Spike?

**Tool:** A `/stats` endpoint + a 1-minute cron that checks thresholds and alerts Slack.

### Stats Endpoint

```python
# backend/routes/stats.py
from fastapi import APIRouter, Depends
from backend.auth import require_admin

router = APIRouter()

@router.get("/stats")
async def get_stats(admin=Depends(require_admin)):
    """Dashboard stats. Admin-only."""
    async with pool.connection() as conn:
        stats = {}

        # Active users (last hour)
        stats["active_users_1h"] = await conn.fetchval(
            "SELECT count(DISTINCT user_id) FROM usage_events WHERE created_at > now() - interval '1 hour'"
        )

        # Requests per minute (last 5 min avg)
        stats["rpm_5m"] = await conn.fetchval(
            "SELECT count(*) / 5.0 FROM usage_events WHERE event_type = 'request' AND created_at > now() - interval '5 minutes'"
        )

        # Turns today
        stats["turns_today"] = await conn.fetchval(
            "SELECT count(*) FROM usage_events WHERE event_type = 'turn' AND created_at > now() - interval '1 day'"
        )

        # Total users
        stats["total_users"] = await conn.fetchval("SELECT count(*) FROM users")

        # Total aides
        stats["total_aides"] = await conn.fetchval("SELECT count(*) FROM aides")

        # Pro users
        stats["pro_users"] = await conn.fetchval("SELECT count(*) FROM users WHERE tier = 'pro'")

        return stats
```

### Traffic Spike Alert

```python
# backend/tasks/traffic_check.py

# Baselines — update these as your traffic grows
THRESHOLDS = {
    "rpm_spike": 100,          # requests/min (adjust as baseline grows)
    "active_users_spike": 50,  # concurrent users in 1 hour
    "turns_spike": 500,        # turns in last hour
}

async def check_traffic():
    async with pool.connection() as conn:
        rpm = await conn.fetchval(
            "SELECT count(*) FROM usage_events WHERE event_type = 'request' AND created_at > now() - interval '1 minute'"
        )
        active = await conn.fetchval(
            "SELECT count(DISTINCT user_id) FROM usage_events WHERE created_at > now() - interval '1 hour'"
        )
        turns = await conn.fetchval(
            "SELECT count(*) FROM usage_events WHERE event_type = 'turn' AND created_at > now() - interval '1 hour'"
        )

        alerts = []
        if rpm > THRESHOLDS["rpm_spike"]:
            alerts.append(f"📈 RPM spike: {rpm}/min (threshold: {THRESHOLDS['rpm_spike']})")
        if active > THRESHOLDS["active_users_spike"]:
            alerts.append(f"📈 Active users spike: {active} in last hour")
        if turns > THRESHOLDS["turns_spike"]:
            alerts.append(f"📈 Turn spike: {turns} in last hour ($$$ alert)")

        for alert in alerts:
            await alert_slack(alert)
```

---

## Putting It Together

### Background Tasks in FastAPI

```python
# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncio

async def monitoring_loop():
    """Runs abuse + traffic checks every 60 seconds."""
    while True:
        try:
            await run_abuse_checks()
            await check_traffic()
        except Exception as e:
            print(f"Monitoring error: {e}")
        await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(monitoring_loop())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)
```

### Cleanup (daily, keep 30 days of events)

```sql
-- Run daily via a scheduled task or cron
DELETE FROM usage_events WHERE created_at < now() - interval '30 days';
```

---

## What Your Slack Channel Looks Like

```
✅ Normal day:
  (nothing — silence is golden)

🚨 Abuse:
  🚨 High turn rate (free users): sketchy@gmail.com (47 turns/hour)
  🚨 Request flooding: bot@spam.com (1,200 requests in 5 min)

📈 Traffic spike:
  📈 RPM spike: 340/min (threshold: 100)
  📈 Active users spike: 89 in last hour
  📈 Turn spike: 620 in last hour ($$$ alert)

⚠️ Server down (from BetterStack):
  ⚠️ editor.toaide.com is DOWN — checked at 2:34 PM EST
  + SMS/phone call to your number
```

---

## Summary

| What | How | Cost |
|------|-----|------|
| Server down | BetterStack free (external ping) | $0 |
| User abuse | `usage_events` table + 60s check loop | $0 |
| Traffic spike | Same check loop, threshold alerts | $0 |
| Visibility | `/stats` admin endpoint | $0 |
| Alerts | Slack webhook | $0 |
| Phone call on downtime | BetterStack free tier | $0 |
| **Total** | | **$0** |

No Datadog. No PagerDuty. No Grafana dashboards. A table, a loop, and a Slack channel. Upgrade to paid monitoring when you have the revenue to justify it.
