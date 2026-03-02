"""
Tests for SPA serving with catch-all routing.

The backend should serve the Vite-built SPA for all frontend routes
while preserving API, auth, ws, and health endpoints.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.fixture
async def client():
    """Create test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


class TestSPAServing:
    """Tests for SPA serving."""

    async def test_root_returns_spa(self, client: AsyncClient):
        """GET / returns 200 with HTML containing <div id="root">."""
        response = await client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert '<div id="root">' in response.text

    async def test_catch_all_returns_spa(self, client: AsyncClient):
        """GET /a/some-aide-id returns 200 with same HTML (catch-all for client-side routing)."""
        response = await client.get("/a/some-aide-id")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert '<div id="root">' in response.text

    async def test_nested_route_returns_spa(self, client: AsyncClient):
        """GET /a/some-aide-id/edit returns SPA (deeply nested routes)."""
        response = await client.get("/a/some-aide-id/edit")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert '<div id="root">' in response.text


class TestAPIRoutesNotCaught:
    """Tests that API routes are not caught by the SPA catch-all."""

    async def test_health_still_works(self, client: AsyncClient):
        """GET /health still returns {"status": "ok"}."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    async def test_api_routes_still_work(self, client: AsyncClient):
        """GET /api/aides returns JSON (API routes not caught by catch-all)."""
        # This will return 401 since we're not authenticated, but it should be JSON
        response = await client.get("/api/aides")
        assert response.status_code == 401
        assert "application/json" in response.headers["content-type"]

    async def test_auth_routes_still_work(self, client: AsyncClient):
        """GET /auth/me returns JSON."""
        response = await client.get("/auth/me")
        assert response.status_code == 401
        assert "application/json" in response.headers["content-type"]


class TestStaticAssets:
    """Tests for static asset serving."""

    async def test_assets_served(self, client: AsyncClient):
        """GET /assets/* returns static files from Vite build."""
        # This test will only pass after `npm run build` creates dist/assets/
        # For now, we test that the route exists and returns appropriate response
        response = await client.get("/assets/nonexistent.js")
        # Should return 404, not the SPA HTML
        assert response.status_code == 404


class TestSpecialPages:
    """Tests for special pages that are not part of the SPA."""

    async def test_flight_recorder_page(self, client: AsyncClient):
        """GET /flight-recorder returns the flight recorder HTML."""
        response = await client.get("/flight-recorder")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    async def test_cli_auth_page(self, client: AsyncClient):
        """GET /cli/auth returns the CLI auth HTML."""
        response = await client.get("/cli/auth")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
