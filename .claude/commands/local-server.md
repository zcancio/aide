# Local Server

Manage the local Docker development environment.

## Usage

When the user runs `/local-server`, check what they want:
- **start** or no argument: Start the server (backend + frontend)
- **stop**: Stop the server
- **restart**: Restart the server
- **logs**: Show backend logs
- **reset**: Full reset (delete database and restart)

## Commands

### Start
```bash
docker compose up -d
```

Wait for healthy status:
```bash
docker compose ps
```

Verify backend:
```bash
curl -s http://localhost:8000/health
```

### Stop
```bash
docker compose down
```

### Restart
```bash
docker compose restart backend frontend
```

### Logs
Backend logs:
```bash
docker compose logs -f backend
```

Frontend logs:
```bash
docker compose logs -f frontend
```

### Reset (wipes database)
```bash
docker compose down -v
docker compose up -d
```

## Notes
- **SPA (React)**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **Database**: localhost:5432
- **Dev login**: http://localhost:8000/auth/dev-login

All services run in Docker. The SPA proxies API/auth/ws calls to the backend.
