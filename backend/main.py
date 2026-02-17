"""
AIde FastAPI application.

Entry point for the API server.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import db
from backend.middleware.rate_limit import rate_limiter
from backend.repos.magic_link_repo import MagicLinkRepo
from backend.routes import aides as aide_routes
from backend.routes import auth_routes
from backend.routes import conversations as conversation_routes
from backend.routes import flight_recorder as flight_recorder_routes
from backend.routes import pages as pages_routes
from backend.routes import publish as publish_routes
from backend.services.flight_recorder_uploader import flight_recorder_uploader


# Background task for cleanup
async def cleanup_task():
    """
    Background task to clean up expired magic links and old rate limit entries.

    Runs every 60 seconds.
    """
    magic_link_repo = MagicLinkRepo()

    while True:
        try:
            # Clean up expired/used magic links older than 1 hour
            deleted_count = await magic_link_repo.cleanup_expired(older_than_hours=1)
            if deleted_count > 0:
                print(f"Cleaned up {deleted_count} expired magic links")

            # Clean up old rate limit entries
            rate_limiter.cleanup_old_entries(max_age_hours=2)

        except Exception as e:
            print(f"Error in cleanup task: {e}")

        # Wait 60 seconds before next cleanup
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.

    Handles startup and shutdown logic:
    - Initialize database pool
    - Start background cleanup task
    - Close database pool on shutdown
    """
    # Startup
    await db.init_pool()
    print("Database pool initialized")

    # Start background cleanup task
    cleanup_task_handle = asyncio.create_task(cleanup_task())
    print("Background cleanup task started")

    # Start flight recorder uploader background task
    flight_uploader_handle = asyncio.create_task(flight_recorder_uploader.run())
    print("Flight recorder uploader started")

    yield

    # Shutdown
    cleanup_task_handle.cancel()
    try:
        await cleanup_task_handle
    except asyncio.CancelledError:
        print("Background cleanup task stopped")

    # Flush remaining flight records before shutdown
    flight_uploader_handle.cancel()
    try:
        await flight_uploader_handle
    except asyncio.CancelledError:
        pass
    await flight_recorder_uploader.flush()
    print("Flight recorder uploader stopped")

    await db.close_pool()
    print("Database pool closed")


app = FastAPI(
    title="AIde",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

# Register routes
app.include_router(auth_routes.router)
app.include_router(aide_routes.router)
app.include_router(conversation_routes.router)
app.include_router(publish_routes.router)
app.include_router(pages_routes.router)
app.include_router(flight_recorder_routes.router)


@app.get("/health")
async def health():
    """Health check endpoint for uptime monitoring."""
    return {"status": "ok"}


# Serve frontend — must be after all API routes
_FRONTEND = Path(__file__).parent.parent / "frontend"

if _FRONTEND.is_dir():
    app.mount("/static", StaticFiles(directory=str(_FRONTEND)), name="static")

    @app.get("/")
    async def serve_index():
        """Serve the editor SPA."""
        return FileResponse(str(_FRONTEND / "index.html"))

    @app.get("/flight-recorder")
    async def serve_flight_recorder():
        """Serve the flight recorder replay page."""
        return FileResponse(str(_FRONTEND / "flight-recorder.html"))
