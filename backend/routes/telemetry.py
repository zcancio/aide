"""Telemetry API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth import get_current_user
from backend.models.telemetry import AideTelemetry
from backend.models.user import User
from backend.services.telemetry import get_aide_telemetry

router = APIRouter(prefix="/api/aides", tags=["telemetry"])


@router.get("/{aide_id}/telemetry")
async def get_telemetry(
    aide_id: UUID,
    user: User = Depends(get_current_user),
) -> AideTelemetry:
    """
    Get full telemetry for an aide in eval-compatible format.

    Used by the flight recorder UI to replay conversations.
    """
    telemetry = await get_aide_telemetry(user.id, aide_id)
    if not telemetry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aide not found.",
        )
    return telemetry
