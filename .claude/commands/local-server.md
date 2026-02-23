# Local Server

Manage the local Docker development environment.

## Usage

When the user runs `/local-server`, check what they want:
- **start** or no argument: Start the server
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

Verify:
```bash
curl -s http://localhost:8000/health
```

### Stop
```bash
docker compose down
```

### Restart
```bash
docker compose restart backend
```

### Logs
```bash
docker compose logs -f backend
```

### Reset (wipes database)
```bash
docker compose down -v
docker compose up -d
```

## Notes
- Backend runs on http://localhost:8000
- Database runs on localhost:5432
- Frontend served at http://localhost:8000/
- Dev login at http://localhost:8000/auth/dev-login
