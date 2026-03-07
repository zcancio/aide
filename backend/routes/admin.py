"""Admin routes for breakglass access and audit logging."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.auth import get_current_admin
from backend.db import system_conn
from backend.models.admin_audit import (
    AdminAuditLogResponse,
    BreakglassAccessRequest,
)
from backend.models.aide import Aide
from backend.models.user import User
from backend.repos.admin_audit_repo import AdminAuditRepo
from backend.repos.aide_repo import _row_to_aide

router = APIRouter(prefix="/api/admin", tags=["admin"])
admin_audit_repo = AdminAuditRepo()


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

    # Fetch the aide using system_conn to bypass RLS
    async with system_conn() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM aides WHERE id = $1",
            aide_id,
        )

        if not row:
            raise HTTPException(status_code=404, detail="Aide not found")

        aide = _row_to_aide(row)

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
        admin_user_id=admin.id,
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
    count = await admin_audit_repo.count_audit_logs(admin_user_id=admin.id)
    return {"count": count}
