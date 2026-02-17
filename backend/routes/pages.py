"""Public page serving — GET /s/{slug} serves published aide HTML."""

from __future__ import annotations

import hashlib

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from backend.services.r2 import r2_service

router = APIRouter(tags=["pages"])

# Cache-Control TTL: 5 minutes for stale-while-revalidate, 1 hour shared cache
_CACHE_CONTROL = "public, max-age=300, s-maxage=3600, stale-while-revalidate=86400"


@router.get("/s/{slug}", response_class=HTMLResponse)
async def serve_published_page(slug: str) -> Response:
    """
    Serve a published aide page by slug.

    Fetches HTML from R2 public bucket. Returns 404 if the slug does not
    exist or the page has been unpublished.

    Cache headers:
    - Cache-Control: public, 5-min browser TTL, 1-hour CDN TTL, 24h stale-while-revalidate
    - ETag: MD5 of the HTML content for conditional requests
    """
    html_bytes = await r2_service.get_published(slug)

    if html_bytes is None:
        return HTMLResponse(
            content="<html><body><h1>404 — Page not found</h1></body></html>",
            status_code=404,
        )

    etag = f'"{hashlib.md5(html_bytes, usedforsecurity=False).hexdigest()}"'

    return Response(
        content=html_bytes,
        media_type="text/html; charset=utf-8",
        headers={
            "Cache-Control": _CACHE_CONTROL,
            "ETag": etag,
            "X-Content-Type-Options": "nosniff",
        },
    )
