# Local Server

Start and manage the local development server using Docker.

## Quick Start

```bash
docker compose up -d
```

Wait a few seconds for migrations to run, then verify:
```bash
curl http://localhost:8000/health
```

## Commands

| Command | Description |
|---------|-------------|
| `docker compose up -d` | Start all services |
| `docker compose down` | Stop all services |
| `docker compose down -v` | Stop and delete database |
| `docker compose logs -f backend` | Stream backend logs |
| `docker compose restart backend` | Restart backend only |
| `docker compose up -d --build backend` | Rebuild and restart backend |

## Services

| Service | Port | Description |
|---------|------|-------------|
| backend | 8000 | FastAPI server |
| db | 5432 | PostgreSQL 16 |

## Database

- **Owner role**: `aide` (runs migrations)
- **App role**: `aide_app` (runtime, RLS enforced)

Access psql:
```bash
docker compose exec db psql -U aide -d aide_test
```

## Environment

The backend reads additional environment variables from `.env`:
- `R2_ENDPOINT`, `R2_ACCESS_KEY`, `R2_SECRET_KEY` - R2 storage
- `ANTHROPIC_API_KEY` - AI features

## Hot Reload

Backend code changes auto-reload. For dependency changes:
```bash
docker compose build backend
docker compose up -d backend
```

## Full Reset

```bash
docker compose down -v
docker compose up -d
```
