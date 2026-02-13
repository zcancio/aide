# AIde

**For what you're running.**

AIde is a conversational web page editor. Describe what you're running — a league, a budget, a renovation — and AIde forms a living page. As things change, tell AIde. The page stays current. The URL stays the same.

## Stack

- **Backend:** Python 3.12 / FastAPI / asyncpg
- **Database:** Neon Postgres (RLS)
- **Storage:** Cloudflare R2
- **Compute:** Railway
- **Auth:** Magic links via Resend
- **Payments:** Stripe

## Development

```bash
pip install -r requirements.txt -r requirements-dev.txt
ruff check backend/
pytest backend/tests/
```

## Deploy

Push to `main`. Railway handles the rest.

## Docs

Architecture decisions, security requirements, and implementation guides are in `docs/`. Claude Code reads these automatically via `CLAUDE.md`.
