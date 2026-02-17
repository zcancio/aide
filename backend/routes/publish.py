"""Publish routes — publish and unpublish aides."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse

from backend import config
from backend.auth import get_current_user
from backend.models.aide import AideResponse, PublishRequest, PublishResponse
from backend.models.user import User
from backend.repos.aide_repo import AideRepo
from backend.services.r2 import r2_service
from engine.kernel.renderer import render
from engine.kernel.types import Blueprint, RenderOptions

router = APIRouter(tags=["publish"])
aide_repo = AideRepo()


@router.get("/s/{slug}", response_class=HTMLResponse)
async def get_published_page(slug: str) -> HTMLResponse:
    """
    Serve a published aide page.

    In production, this is served directly from R2/CDN.
    This route exists for local development.
    """
    html_bytes = await r2_service.get_published(slug)
    if not html_bytes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found.")
    return HTMLResponse(content=html_bytes.decode("utf-8"))


@router.post("/api/aides/{aide_id}/publish", status_code=200)
async def publish_aide(
    aide_id: UUID,
    req: PublishRequest,
    user: User = Depends(get_current_user),
) -> PublishResponse:
    """
    Publish an aide at the given slug.

    Renders the current state to HTML, uploads to R2 public bucket,
    and marks the aide as published with the slug.
    """
    aide = await aide_repo.get(user.id, aide_id)
    if not aide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")

    # Render current state to HTML
    # Free tier pages include "Made with AIde" footer; pro tier pages do not
    footer_text = "Made with AIde" if user.tier == "free" else None
    blueprint = Blueprint(identity=aide.title)
    options = RenderOptions(footer=footer_text)
    html_content = render(aide.state, blueprint=blueprint, events=[], options=options)

    # Upload to public R2 bucket
    await r2_service.upload_published(req.slug, html_content)

    # Persist published status and slug in DB
    updated = await aide_repo.publish(user.id, aide_id, req.slug)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")

    public_url = f"{config.settings.PUBLIC_URL}/s/{req.slug}"
    return PublishResponse(slug=req.slug, url=public_url)


@router.post("/api/aides/{aide_id}/unpublish", status_code=200)
async def unpublish_aide(
    aide_id: UUID,
    user: User = Depends(get_current_user),
) -> AideResponse:
    """
    Unpublish an aide — set back to draft and clear slug.

    Does not delete the R2 object (page remains cached at CDN until TTL).
    """
    aide = await aide_repo.get(user.id, aide_id)
    if not aide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")

    updated = await aide_repo.unpublish(user.id, aide_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")

    return AideResponse.from_model(updated)
