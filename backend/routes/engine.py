"""Engine.js serving route."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api", tags=["engine"])


@router.get("/engine.js")
async def get_engine():
    """
    Serve current engine.js. No auth required.

    The CLI fetches this on startup to ensure it's always running
    the latest engine version.
    """
    # display.js contains both reducer (reduce, replay) and renderer (renderText, renderHtml)
    engine_path = Path(__file__).parent.parent.parent / "frontend" / "display.js"

    if not engine_path.exists():
        raise HTTPException(status_code=404, detail=f"Engine not found at {engine_path}")

    return FileResponse(
        str(engine_path),
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=300"},  # Cache for 5 minutes
    )
