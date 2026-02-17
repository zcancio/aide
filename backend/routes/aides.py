"""Aide CRUD routes — list, create, get, update, archive, delete."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth import get_current_user
from backend.models.aide import AideResponse, CreateAideRequest, UpdateAideRequest
from backend.models.user import User
from backend.repos.aide_repo import AideRepo

router = APIRouter(prefix="/api/aides", tags=["aides"])
aide_repo = AideRepo()


@router.get("", status_code=200)
async def list_aides(user: User = Depends(get_current_user)) -> list[AideResponse]:
    """List all non-archived aides for the current user."""
    aides = await aide_repo.list_for_user(user.id)
    return [AideResponse.from_model(a) for a in aides]


@router.post("", status_code=201)
async def create_aide(
    req: CreateAideRequest,
    user: User = Depends(get_current_user),
) -> AideResponse:
    """Create a new aide."""
    aide = await aide_repo.create(user.id, req)
    return AideResponse.from_model(aide)


@router.get("/{aide_id}", status_code=200)
async def get_aide(
    aide_id: UUID,
    user: User = Depends(get_current_user),
) -> AideResponse:
    """Get a single aide by ID."""
    aide = await aide_repo.get(user.id, aide_id)
    if not aide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")
    return AideResponse.from_model(aide)


@router.patch("/{aide_id}", status_code=200)
async def update_aide(
    aide_id: UUID,
    req: UpdateAideRequest,
    user: User = Depends(get_current_user),
) -> AideResponse:
    """Update an aide's title or slug."""
    aide = await aide_repo.update(user.id, aide_id, req)
    if not aide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")
    return AideResponse.from_model(aide)


@router.post("/{aide_id}/archive", status_code=200)
async def archive_aide(
    aide_id: UUID,
    user: User = Depends(get_current_user),
) -> AideResponse:
    """Archive an aide (soft delete)."""
    aide = await aide_repo.archive(user.id, aide_id)
    if not aide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")
    return AideResponse.from_model(aide)


@router.delete("/{aide_id}", status_code=200)
async def delete_aide(
    aide_id: UUID,
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Permanently delete an aide."""
    deleted = await aide_repo.delete(user.id, aide_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")
    return {"message": "Aide deleted."}
