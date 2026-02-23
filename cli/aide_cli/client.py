"""HTTP client for AIde API."""
from typing import Any

import httpx


class ApiClient:
    """HTTP client for AIde API."""

    def __init__(self, api_url: str, token: str | None = None):
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.client = httpx.Client(timeout=30.0)

    def _headers(self) -> dict:
        """Build request headers."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get(self, path: str) -> Any:
        """Make GET request."""
        url = f"{self.api_url}{path}"
        res = self.client.get(url, headers=self._headers())
        res.raise_for_status()
        return res.json()

    def post(self, path: str, data: dict) -> Any:
        """Make POST request."""
        url = f"{self.api_url}{path}"
        res = self.client.post(url, json=data, headers=self._headers())
        res.raise_for_status()
        return res.json()

    def close(self):
        """Close client."""
        self.client.close()
