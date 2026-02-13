from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


def test_placeholder():
    """Remove this once real tests exist."""
    assert True


def test_health_endpoint():
    """Test that the /health endpoint returns {"status": "ok"}."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
