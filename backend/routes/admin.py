"""Admin routes for breakglass access and audit logging."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.auth import get_current_admin
from backend.models.admin_audit import (
    AdminAuditLogResponse,
    AdminUserListItem,
    AdminUserListResponse,
    AideSearchRequest,
    AideSearchResult,
    BreakglassAccessRequest,
    SystemStatsResponse,
)
from backend.models.aide import Aide
from backend.models.telemetry import AideTelemetry
from backend.models.user import User
from backend.repos.admin_audit_repo import AdminAuditRepo
from backend.repos.aide_repo import AideRepo
from backend.repos.user_repo import UserRepo
from backend.services.telemetry import get_aide_telemetry_system

router = APIRouter(prefix="/api/admin", tags=["admin"])
admin_audit_repo = AdminAuditRepo()
aide_repo = AideRepo()
user_repo = UserRepo()


@router.post("/breakglass/aide/{aide_id}")
async def breakglass_view_aide(
    aide_id: UUID,
    req: BreakglassAccessRequest,
    request: Request,
    admin: Annotated[User, Depends(get_current_admin)],
) -> Aide:
    """
    Admin breakglass access to view any aide by ID.

    Requires admin privileges. All access is logged to admin_audit_log.

    Args:
        aide_id: UUID of the aide to access (must match request body)
        req: BreakglassAccessRequest with reason for access
        request: FastAPI request object for IP address
        admin: Current admin user (from dependency)

    Returns:
        The requested Aide

    Raises:
        HTTPException: If aide_id mismatch or aide not found
    """
    if aide_id != req.aide_id:
        raise HTTPException(
            status_code=400,
            detail="aide_id in URL must match aide_id in request body",
        )

    # Fetch the aide using system connection to bypass RLS
    aide = await aide_repo.get_by_id_system(aide_id)
    if not aide:
        raise HTTPException(status_code=404, detail="Aide not found")

    # Log the breakglass access
    client_ip = request.client.host if request.client else None
    await admin_audit_repo.log_breakglass_access(
        admin_user_id=admin.id,
        action="breakglass_view_aide",
        reason=req.reason,
        target_user_id=aide.user_id,
        target_aide_id=aide.id,
        ip_address=client_ip,
    )

    return aide


@router.post("/breakglass/aide/{aide_id}/telemetry")
async def breakglass_view_aide_telemetry(
    aide_id: UUID,
    req: BreakglassAccessRequest,
    request: Request,
    admin: Annotated[User, Depends(get_current_admin)],
) -> AideTelemetry:
    """
    Admin breakglass access to view telemetry for any aide.

    Requires admin privileges. All access is logged to admin_audit_log.
    Returns telemetry in flight-recorder compatible format.

    Args:
        aide_id: UUID of the aide to access (must match request body)
        req: BreakglassAccessRequest with reason for access
        request: FastAPI request object for IP address
        admin: Current admin user (from dependency)

    Returns:
        AideTelemetry for flight-recorder

    Raises:
        HTTPException: If aide_id mismatch or aide not found
    """
    if aide_id != req.aide_id:
        raise HTTPException(
            status_code=400,
            detail="aide_id in URL must match aide_id in request body",
        )

    # Fetch telemetry using system connection to bypass RLS
    telemetry = await get_aide_telemetry_system(aide_id)
    if not telemetry:
        raise HTTPException(status_code=404, detail="Aide not found")

    # Get aide for audit log (need user_id)
    aide = await aide_repo.get_by_id_system(aide_id)

    # Log the breakglass access
    client_ip = request.client.host if request.client else None
    await admin_audit_repo.log_breakglass_access(
        admin_user_id=admin.id,
        action="breakglass_view_aide_telemetry",
        reason=req.reason,
        target_user_id=aide.user_id if aide else None,
        target_aide_id=aide_id,
        ip_address=client_ip,
    )

    return telemetry


@router.get("/audit-logs")
async def list_audit_logs(
    admin: Annotated[User, Depends(get_current_admin)],
    limit: int = 100,
    offset: int = 0,
) -> list[AdminAuditLogResponse]:
    """
    List admin audit logs.

    Requires admin privileges.

    Args:
        admin: Current admin user (from dependency)
        limit: Maximum number of logs to return (default 100, max 1000)
        offset: Number of logs to skip (default 0)

    Returns:
        List of AdminAuditLogResponse entries

    Raises:
        HTTPException: If limit exceeds maximum
    """
    if limit > 1000:
        raise HTTPException(status_code=400, detail="Maximum limit is 1000")

    return await admin_audit_repo.list_audit_logs(
        limit=limit,
        offset=offset,
    )


@router.get("/audit-logs/count")
async def count_audit_logs(
    admin: Annotated[User, Depends(get_current_admin)],
) -> dict[str, int]:
    """
    Get total count of audit logs.

    Requires admin privileges.

    Args:
        admin: Current admin user (from dependency)

    Returns:
        Dictionary with total count
    """
    count = await admin_audit_repo.count_audit_logs()
    return {"count": count}


@router.get("/users")
async def list_users(
    admin: Annotated[User, Depends(get_current_admin)],
    limit: int = 100,
    offset: int = 0,
) -> AdminUserListResponse:
    """
    List all users in the system.

    Requires admin privileges.

    Args:
        admin: Current admin user (from dependency)
        limit: Maximum number of users to return (default 100, max 1000)
        offset: Number of users to skip (default 0)

    Returns:
        AdminUserListResponse with users and total count

    Raises:
        HTTPException: If limit exceeds maximum
    """
    if limit > 1000:
        raise HTTPException(status_code=400, detail="Maximum limit is 1000")

    users, total = await user_repo.list_all(limit=limit, offset=offset)

    return AdminUserListResponse(
        users=[AdminUserListItem(**u) for u in users],
        total=total,
    )


@router.get("/stats")
async def get_system_stats(
    admin: Annotated[User, Depends(get_current_admin)],
) -> SystemStatsResponse:
    """
    Get system-wide statistics.

    Requires admin privileges.

    Args:
        admin: Current admin user (from dependency)

    Returns:
        SystemStatsResponse with totals and breakdowns
    """
    users_by_tier = await user_repo.count_by_tier()
    total_users = sum(users_by_tier.values())

    aides_by_status = await aide_repo.count_by_status()
    total_aides = sum(aides_by_status.values())

    total_audit_logs = await admin_audit_repo.count_audit_logs()

    return SystemStatsResponse(
        total_users=total_users,
        total_aides=total_aides,
        total_audit_logs=total_audit_logs,
        users_by_tier=users_by_tier,
        aides_by_status=aides_by_status,
    )


@router.post("/search/aides")
async def search_aides(
    req: AideSearchRequest,
    admin: Annotated[User, Depends(get_current_admin)],
) -> list[AideSearchResult]:
    """
    Search for aides by ID, user email, or user ID.

    Requires admin privileges. Does NOT log breakglass access -
    use /breakglass/aide/{aide_id} to actually view aide content.

    Args:
        req: Search criteria (aide_id OR user_email OR user_id)
        admin: Current admin user (from dependency)

    Returns:
        List of matching aides with owner info

    Raises:
        HTTPException: If no search criteria provided
    """
    if not req.aide_id and not req.user_email and not req.user_id:
        raise HTTPException(
            status_code=400,
            detail="Either aide_id, user_email, or user_id must be provided",
        )

    results = []

    if req.aide_id:
        aide = await aide_repo.get_by_id_system(req.aide_id)
        if aide:
            owner = await user_repo.get_by_id_system(aide.user_id)
            results.append(
                AideSearchResult(
                    id=aide.id,
                    title=aide.title,
                    status=aide.status,
                    owner_email=owner.email if owner else "unknown",
                    owner_id=aide.user_id,
                    created_at=aide.created_at,
                    updated_at=aide.updated_at,
                )
            )

    if req.user_email:
        aides = await aide_repo.search_by_user_email(req.user_email)
        for a in aides:
            results.append(AideSearchResult(**a))

    if req.user_id:
        aides = await aide_repo.search_by_user_id(req.user_id)
        for a in aides:
            results.append(AideSearchResult(**a))

    return results
