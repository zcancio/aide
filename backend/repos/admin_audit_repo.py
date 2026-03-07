"""Repository for admin audit operations."""

from __future__ import annotations

from uuid import UUID

import asyncpg

from backend.db import system_conn
from backend.models.admin_audit import AdminAuditLog, AdminAuditLogResponse


def _row_to_audit_log(row: asyncpg.Record) -> AdminAuditLog:
    """Convert a database row to an AdminAuditLog model."""
    return AdminAuditLog(
        id=row["id"],
        admin_user_id=row["admin_user_id"],
        action=row["action"],
        target_user_id=row.get("target_user_id"),
        target_aide_id=row.get("target_aide_id"),
        reason=row["reason"],
        ip_address=row.get("ip_address"),
        created_at=row["created_at"],
    )


class AdminAuditRepo:
    """All admin audit log database operations."""

    async def log_breakglass_access(
        self,
        admin_user_id: UUID,
        action: str,
        reason: str,
        target_user_id: UUID | None = None,
        target_aide_id: UUID | None = None,
        ip_address: str | None = None,
    ) -> AdminAuditLog:
        """
        Log an admin breakglass action.

        Args:
            admin_user_id: UUID of the admin performing the action
            action: Description of the action (e.g., "view_aide", "view_user_data")
            reason: Justification for the breakglass access (minimum 10 characters)
            target_user_id: Optional UUID of the user being accessed
            target_aide_id: Optional UUID of the aide being accessed
            ip_address: Optional IP address of the admin

        Returns:
            Created AdminAuditLog entry
        """
        async with system_conn() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO admin_audit_log (
                    admin_user_id, action, target_user_id, target_aide_id, reason, ip_address
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                admin_user_id,
                action,
                target_user_id,
                target_aide_id,
                reason,
                ip_address,
            )
            if not row:
                raise RuntimeError("Failed to create audit log entry")
            return _row_to_audit_log(row)

    async def list_audit_logs(
        self,
        admin_user_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AdminAuditLogResponse]:
        """
        List admin audit logs (admin only).

        Args:
            admin_user_id: UUID of the admin requesting the logs
            limit: Maximum number of logs to return
            offset: Number of logs to skip

        Returns:
            List of AdminAuditLogResponse entries with enriched data
        """
        # Use system_conn to bypass RLS for joins, but verify admin status first
        async with system_conn() as conn:
            # Verify the requesting user is an admin
            is_admin = await conn.fetchval(
                "SELECT is_admin FROM users WHERE id = $1",
                admin_user_id,
            )
            if not is_admin:
                raise RuntimeError("User is not an admin")

            rows = await conn.fetch(
                """
                SELECT
                    aal.id,
                    aal.admin_user_id,
                    admin_user.email as admin_email,
                    aal.action,
                    aal.target_user_id,
                    target_user.email as target_user_email,
                    aal.target_aide_id,
                    aide.title as target_aide_title,
                    aal.reason,
                    aal.ip_address,
                    aal.created_at
                FROM admin_audit_log aal
                JOIN users admin_user ON aal.admin_user_id = admin_user.id
                LEFT JOIN users target_user ON aal.target_user_id = target_user.id
                LEFT JOIN aides aide ON aal.target_aide_id = aide.id
                ORDER BY aal.created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )
            return [
                AdminAuditLogResponse(
                    id=row["id"],
                    admin_user_id=row["admin_user_id"],
                    admin_email=row["admin_email"],
                    action=row["action"],
                    target_user_id=row.get("target_user_id"),
                    target_user_email=row.get("target_user_email"),
                    target_aide_id=row.get("target_aide_id"),
                    target_aide_title=row.get("target_aide_title"),
                    reason=row["reason"],
                    ip_address=row.get("ip_address"),
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    async def count_audit_logs(self, admin_user_id: UUID) -> int:
        """
        Count total audit log entries (admin only).

        Args:
            admin_user_id: UUID of the admin requesting the count

        Returns:
            Total number of audit log entries
        """
        async with system_conn() as conn:
            # Verify the requesting user is an admin
            is_admin = await conn.fetchval(
                "SELECT is_admin FROM users WHERE id = $1",
                admin_user_id,
            )
            if not is_admin:
                raise RuntimeError("User is not an admin")

            count = await conn.fetchval("SELECT COUNT(*) FROM admin_audit_log")
            return count or 0
