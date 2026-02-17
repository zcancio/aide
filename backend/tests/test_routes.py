"""Integration tests for aides, conversations, and publish routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from backend.auth import create_jwt
from backend.main import app
from backend.models.aide import CreateAideRequest
from backend.repos.aide_repo import AideRepo

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session")
async def async_client():
    """Async HTTP client against the ASGI app."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


# ── aide CRUD routes ────────────────────────────────────────────────────────


class TestAideRoutes:
    """Tests for /api/aides endpoints."""

    async def test_list_aides_unauthenticated(self, async_client):
        """GET /api/aides without session → 401."""
        res = await async_client.get("/api/aides")
        assert res.status_code == 401

    async def test_list_aides_authenticated(self, async_client, test_user_id):
        """GET /api/aides with valid session → 200 list."""
        token = create_jwt(test_user_id)
        res = await async_client.get("/api/aides", cookies={"session": token})
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    async def test_create_aide(self, async_client, test_user_id):
        """POST /api/aides → 201 with new aide."""
        token = create_jwt(test_user_id)
        res = await async_client.post(
            "/api/aides",
            json={"title": "Route Test Aide"},
            cookies={"session": token},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["title"] == "Route Test Aide"
        assert data["status"] == "draft"

    async def test_create_aide_unauthenticated(self, async_client):
        """POST /api/aides without session → 401."""
        res = await async_client.post("/api/aides", json={"title": "x"})
        assert res.status_code == 401

    async def test_get_aide(self, async_client, test_user_id):
        """GET /api/aides/{id} → 200."""
        repo = AideRepo()
        aide = await repo.create(test_user_id, CreateAideRequest(title="Fetchable"))
        token = create_jwt(test_user_id)
        res = await async_client.get(f"/api/aides/{aide.id}", cookies={"session": token})
        assert res.status_code == 200
        assert res.json()["id"] == str(aide.id)

    async def test_get_aide_not_found(self, async_client, test_user_id):
        """GET /api/aides/{nonexistent} → 404."""
        token = create_jwt(test_user_id)
        res = await async_client.get(f"/api/aides/{uuid4()}", cookies={"session": token})
        assert res.status_code == 404

    async def test_archive_aide(self, async_client, test_user_id):
        """POST /api/aides/{id}/archive → 200, status=archived."""
        repo = AideRepo()
        aide = await repo.create(test_user_id, CreateAideRequest(title="To Archive"))
        token = create_jwt(test_user_id)
        res = await async_client.post(f"/api/aides/{aide.id}/archive", cookies={"session": token})
        assert res.status_code == 200
        assert res.json()["status"] == "archived"

    async def test_delete_aide(self, async_client, test_user_id):
        """DELETE /api/aides/{id} → 200."""
        repo = AideRepo()
        aide = await repo.create(test_user_id, CreateAideRequest(title="To Delete"))
        token = create_jwt(test_user_id)
        res = await async_client.delete(f"/api/aides/{aide.id}", cookies={"session": token})
        assert res.status_code == 200
        assert "deleted" in res.json()["message"].lower()

    async def test_rls_cross_user_get(self, async_client, test_user_id, second_user_id):
        """User B cannot access user A's aide via routes."""
        repo = AideRepo()
        aide = await repo.create(test_user_id, CreateAideRequest(title="User A Private"))
        token_b = create_jwt(second_user_id)
        res = await async_client.get(f"/api/aides/{aide.id}", cookies={"session": token_b})
        assert res.status_code == 404


# ── preview route ──────────────────────────────────────────────────────────


class TestPreviewRoute:
    """Tests for GET /api/aides/{id}/preview."""

    async def test_preview_unauthenticated(self, async_client):
        """GET /api/aides/{id}/preview without session → 401."""
        res = await async_client.get(f"/api/aides/{uuid4()}/preview")
        assert res.status_code == 401

    async def test_preview_not_found(self, async_client, test_user_id):
        """GET /api/aides/{nonexistent}/preview → 404."""
        token = create_jwt(test_user_id)
        res = await async_client.get(f"/api/aides/{uuid4()}/preview", cookies={"session": token})
        assert res.status_code == 404

    async def test_preview_returns_html(self, async_client, test_user_id):
        """GET /api/aides/{id}/preview → 200 with HTML content."""
        repo = AideRepo()
        aide = await repo.create(test_user_id, CreateAideRequest(title="Preview Test"))
        token = create_jwt(test_user_id)

        with patch(
            "backend.routes.aides.r2_service.get_html",
            new_callable=AsyncMock,
            return_value="<html><body>Preview content</body></html>",
        ):
            res = await async_client.get(
                f"/api/aides/{aide.id}/preview",
                cookies={"session": token},
            )

        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/html")
        assert "Preview content" in res.text

    async def test_preview_empty_returns_placeholder(self, async_client, test_user_id):
        """GET /api/aides/{id}/preview with no R2 content → placeholder HTML."""
        repo = AideRepo()
        aide = await repo.create(test_user_id, CreateAideRequest(title="Empty Preview"))
        token = create_jwt(test_user_id)

        with patch(
            "backend.routes.aides.r2_service.get_html",
            new_callable=AsyncMock,
            return_value=None,
        ):
            res = await async_client.get(
                f"/api/aides/{aide.id}/preview",
                cookies={"session": token},
            )

        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/html")
        # Should return placeholder HTML
        assert "<!DOCTYPE html>" in res.text

    async def test_rls_cross_user_preview(self, async_client, test_user_id, second_user_id):
        """User B cannot preview user A's aide."""
        repo = AideRepo()
        aide = await repo.create(test_user_id, CreateAideRequest(title="User A Preview"))
        token_b = create_jwt(second_user_id)
        res = await async_client.get(f"/api/aides/{aide.id}/preview", cookies={"session": token_b})
        assert res.status_code == 404


# ── message route ───────────────────────────────────────────────────────────


class TestMessageRoute:
    """Tests for POST /api/message."""

    async def test_message_unauthenticated(self, async_client):
        """POST /api/message without session → 401."""
        res = await async_client.post("/api/message", json={"message": "hello"})
        assert res.status_code == 401

    async def test_message_creates_aide_if_no_aide_id(self, async_client, test_user_id):
        """POST /api/message with no aide_id → creates new aide."""
        token = create_jwt(test_user_id)
        mock_result = {
            "response": "Tasks: none yet.",
            "html_url": "/api/aides/abc/preview",
            "primitives_count": 2,
        }
        with patch(
            "backend.routes.conversations.orchestrator.process_message",
            new_callable=AsyncMock,
        ) as mock_orch:
            mock_orch.return_value = mock_result
            res = await async_client.post(
                "/api/message",
                json={"message": "I'm running a grocery list"},
                cookies={"session": token},
            )

        assert res.status_code == 200
        data = res.json()
        assert data["response_text"] == "Tasks: none yet."
        assert data["aide_id"] is not None

    async def test_message_invalid_image_data(self, async_client, test_user_id):
        """POST /api/message with bad image → 422."""
        token = create_jwt(test_user_id)
        res = await async_client.post(
            "/api/message",
            json={"message": "describe this", "image": "not-valid-base64!!!"},
            cookies={"session": token},
        )
        assert res.status_code == 422

    async def test_message_with_existing_aide(self, async_client, test_user_id):
        """POST /api/message with aide_id → calls orchestrator with that aide."""
        repo = AideRepo()
        aide = await repo.create(test_user_id, CreateAideRequest(title="Existing"))
        token = create_jwt(test_user_id)

        mock_result = {
            "response": "State updated.",
            "html_url": "/api/aides/abc/preview",
            "primitives_count": 1,
        }
        with patch(
            "backend.routes.conversations.orchestrator.process_message",
            new_callable=AsyncMock,
        ) as mock_orch:
            mock_orch.return_value = mock_result
            res = await async_client.post(
                "/api/message",
                json={"message": "add milk", "aide_id": str(aide.id)},
                cookies={"session": token},
            )

        assert res.status_code == 200
        data = res.json()
        assert data["aide_id"] == str(aide.id)
        mock_orch.assert_called_once()


# ── publish route ───────────────────────────────────────────────────────────


class TestPublishRoute:
    """Tests for POST /api/aides/{id}/publish and /unpublish."""

    async def test_publish_unauthenticated(self, async_client):
        """Publish without session → 401."""
        res = await async_client.post(f"/api/aides/{uuid4()}/publish", json={"slug": "test"})
        assert res.status_code == 401

    async def test_publish_aide(self, async_client, test_user_id):
        """POST /api/aides/{id}/publish → 200 with url."""
        repo = AideRepo()
        aide = await repo.create(test_user_id, CreateAideRequest(title="To Publish"))
        token = create_jwt(test_user_id)

        with (
            patch(
                "backend.routes.publish.r2_service.upload_published",
                new_callable=AsyncMock,
                return_value="published-slug/index.html",
            ),
            patch("backend.routes.publish.render", return_value="<html>test</html>"),
        ):
            res = await async_client.post(
                f"/api/aides/{aide.id}/publish",
                json={"slug": "my-test-page"},
                cookies={"session": token},
            )

        assert res.status_code == 200
        data = res.json()
        assert data["slug"] == "my-test-page"
        assert "my-test-page" in data["url"]

    async def test_publish_aide_not_found(self, async_client, test_user_id):
        """Publish nonexistent aide → 404."""
        token = create_jwt(test_user_id)
        res = await async_client.post(
            f"/api/aides/{uuid4()}/publish",
            json={"slug": "ghost"},
            cookies={"session": token},
        )
        assert res.status_code == 404

    async def test_publish_invalid_slug(self, async_client, test_user_id):
        """Publish with invalid slug → 422."""
        token = create_jwt(test_user_id)
        res = await async_client.post(
            f"/api/aides/{uuid4()}/publish",
            json={"slug": "invalid slug!"},
            cookies={"session": token},
        )
        assert res.status_code == 422

    async def test_unpublish_aide(self, async_client, test_user_id):
        """POST /api/aides/{id}/unpublish → 200, status=draft."""
        repo = AideRepo()
        aide = await repo.create(test_user_id, CreateAideRequest(title="Published One"))
        await repo.publish(test_user_id, aide.id, f"unpublish-test-{aide.id}")
        token = create_jwt(test_user_id)

        res = await async_client.post(
            f"/api/aides/{aide.id}/unpublish",
            cookies={"session": token},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "draft"

    async def test_rls_cross_user_publish(self, async_client, test_user_id, second_user_id):
        """User B cannot publish user A's aide."""
        repo = AideRepo()
        aide = await repo.create(test_user_id, CreateAideRequest(title="User A Protected"))
        token_b = create_jwt(second_user_id)

        res = await async_client.post(
            f"/api/aides/{aide.id}/publish",
            json={"slug": "stolen-slug"},
            cookies={"session": token_b},
        )
        assert res.status_code == 404
