"""Tests for admin breakglass access and audit logging."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from backend.auth import create_jwt
from backend.db import system_conn
from backend.main import app
from backend.models.aide import CreateAideRequest
from backend.models.user import User
from backend.repos.admin_audit_repo import AdminAuditRepo
from backend.repos.aide_repo import AideRepo
from backend.repos.user_repo import UserRepo

pytestmark = pytest.mark.asyncio(loop_scope="session")

user_repo = UserRepo()
aide_repo = AideRepo()
admin_audit_repo = AdminAuditRepo()


@pytest_asyncio.fixture(loop_scope="session")
async def async_client():
    """Async HTTP client against the ASGI app."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest_asyncio.fixture
async def admin_user(initialize_pool) -> User:
    """Create an admin user for testing."""
    admin = await user_repo.create(email=f"admin-{uuid4()}@example.com")
    async with system_conn() as conn:
        await conn.execute("UPDATE users SET is_admin = true WHERE id = $1", admin.id)
    return await user_repo.get(admin.id)


class TestAdminBreakglass:
    """Test admin breakglass access functionality."""

    async def test_regular_user_cannot_access_admin_endpoints(self, initialize_pool, async_client):
        """Regular users should be denied access to admin endpoints."""
        # Create a regular user
        user = await user_repo.create(email=f"regular-{uuid4()}@example.com")
        jwt_token = create_jwt(user.id)

        # Create an aide
        aide = await aide_repo.create(user.id, CreateAideRequest(title="Test Aide"))

        # Try to use breakglass endpoint
        response = await async_client.post(
            f"/api/admin/breakglass/aide/{aide.id}",
            json={"aide_id": str(aide.id), "reason": "Testing regular user access"},
            cookies={"session": jwt_token},
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Admin access required."

        # Try to list audit logs
        response = await async_client.get("/api/admin/audit-logs", cookies={"session": jwt_token})
        assert response.status_code == 403
        assert response.json()["detail"] == "Admin access required."

    async def test_admin_can_access_any_aide(self, admin_user, async_client):
        """Admins should be able to access any aide via breakglass."""
        assert admin_user.is_admin is True

        # Create a regular user with an aide
        regular_user = await user_repo.create(email=f"user-{uuid4()}@example.com")
        aide = await aide_repo.create(regular_user.id, CreateAideRequest(title="Private Aide"))

        # Admin accesses the aide via breakglass
        admin_jwt = create_jwt(admin_user.id)

        response = await async_client.post(
            f"/api/admin/breakglass/aide/{aide.id}",
            json={
                "aide_id": str(aide.id),
                "reason": "Customer support request - investigating reported issue",
            },
            cookies={"session": admin_jwt},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(aide.id)
        assert data["title"] == "Private Aide"
        assert data["user_id"] == str(regular_user.id)

    async def test_breakglass_access_is_audited(self, admin_user, async_client):
        """All breakglass access should be logged to admin_audit_log."""
        # Create a regular user with an aide
        regular_user = await user_repo.create(email=f"user-{uuid4()}@example.com")
        aide = await aide_repo.create(regular_user.id, CreateAideRequest(title="Test Aide"))

        # Admin accesses the aide
        admin_jwt = create_jwt(admin_user.id)
        reason = "Investigating reported bug in aide rendering"

        response = await async_client.post(
            f"/api/admin/breakglass/aide/{aide.id}",
            json={"aide_id": str(aide.id), "reason": reason},
            cookies={"session": admin_jwt},
        )
        assert response.status_code == 200

        # Verify audit log entry was created
        audit_logs = await admin_audit_repo.list_audit_logs(limit=10)

        # Find the log entry for this access
        matching_logs = [log for log in audit_logs if log.target_aide_id == aide.id]
        assert len(matching_logs) >= 1

        log_entry = matching_logs[0]
        assert log_entry.admin_user_id == admin_user.id
        assert log_entry.action == "breakglass_view_aide"
        assert log_entry.target_user_id == regular_user.id
        assert log_entry.target_aide_id == aide.id
        assert log_entry.reason == reason

    async def test_breakglass_requires_valid_reason(self, admin_user, async_client):
        """Breakglass access should require a reason of minimum length."""
        # Create an aide
        regular_user = await user_repo.create(email=f"user-{uuid4()}@example.com")
        aide = await aide_repo.create(regular_user.id, CreateAideRequest(title="Test Aide"))

        admin_jwt = create_jwt(admin_user.id)

        # Try with reason that's too short
        response = await async_client.post(
            f"/api/admin/breakglass/aide/{aide.id}",
            json={"aide_id": str(aide.id), "reason": "short"},
            cookies={"session": admin_jwt},
        )

        assert response.status_code == 422  # Validation error

    async def test_breakglass_rejects_mismatched_aide_id(self, admin_user, async_client):
        """Breakglass endpoint should reject requests where URL aide_id != body aide_id."""
        # Create two aides
        regular_user = await user_repo.create(email=f"user-{uuid4()}@example.com")
        aide1 = await aide_repo.create(regular_user.id, CreateAideRequest(title="Aide 1"))
        aide2 = await aide_repo.create(regular_user.id, CreateAideRequest(title="Aide 2"))

        admin_jwt = create_jwt(admin_user.id)

        # Request with mismatched IDs
        response = await async_client.post(
            f"/api/admin/breakglass/aide/{aide1.id}",
            json={
                "aide_id": str(aide2.id),
                "reason": "Testing mismatched IDs for security",
            },
            cookies={"session": admin_jwt},
        )

        assert response.status_code == 400
        detail = response.json()["detail"].lower()
        assert "match" in detail and "aide_id" in detail

    async def test_breakglass_returns_404_for_nonexistent_aide(self, admin_user, async_client):
        """Breakglass should return 404 for non-existent aides."""
        admin_jwt = create_jwt(admin_user.id)

        # Try to access a non-existent aide
        fake_aide_id = uuid4()

        response = await async_client.post(
            f"/api/admin/breakglass/aide/{fake_aide_id}",
            json={
                "aide_id": str(fake_aide_id),
                "reason": "Testing non-existent aide access",
            },
            cookies={"session": admin_jwt},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_audit_log_count_endpoint(self, admin_user, async_client):
        """Admins should be able to get count of audit logs."""
        admin_jwt = create_jwt(admin_user.id)

        # Get initial count
        response = await async_client.get("/api/admin/audit-logs/count", cookies={"session": admin_jwt})

        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0
