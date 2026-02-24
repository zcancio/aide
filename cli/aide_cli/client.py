"""HTTP client for AIde API."""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx


class ApiClient:
    """HTTP client for AIde API."""

    def __init__(self, api_url: str, token: str | None = None):
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.client = httpx.Client(timeout=30.0)
        self.async_client = None

    def _headers(self, accept: str = "application/json") -> dict:
        """Build request headers."""
        headers = {"Content-Type": "application/json", "Accept": accept}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get(self, path: str, params: dict | None = None) -> Any:
        """Make GET request."""
        url = f"{self.api_url}{path}"
        res = self.client.get(url, headers=self._headers(), params=params or {})
        res.raise_for_status()
        return res.json()

    def post(self, path: str, data: dict) -> Any:
        """Make POST request."""
        url = f"{self.api_url}{path}"
        res = self.client.post(url, json=data, headers=self._headers())
        res.raise_for_status()
        return res.json()

    def send_message(self, aide_id: str, message: str) -> dict:
        """
        Send message to aide (non-streaming).

        Returns {"response_text": "...", "page_url": "...", "state": {...}, "aide_id": "..."}
        """
        return self.post("/api/message", {"aide_id": aide_id, "message": message})

    async def stream_message(self, aide_id: str, message: str) -> AsyncIterator[tuple[str, dict]]:
        """
        Send message and stream response via SSE.

        Yields tuples of (event_type, data).
        """
        if not self.async_client:
            self.async_client = httpx.AsyncClient(timeout=60.0)

        url = f"{self.api_url}/api/aide/{aide_id}/chat"

        async with self.async_client.stream(
            "POST",
            url,
            json={"message": message},
            headers=self._headers(accept="text/event-stream"),
        ) as response:
            response.raise_for_status()

            event_type = None
            async for line in response.aiter_lines():
                line = line.strip()

                if not line:
                    continue

                if line.startswith("event: "):
                    event_type = line[7:]
                elif line.startswith("data: "):
                    if event_type:
                        data = json.loads(line[6:])
                        yield (event_type, data)

    def fetch_engine(self) -> bool:
        """
        Fetch engine.js from server and cache it locally.

        Returns True if fetch succeeded, False if offline/failed.
        """
        engine_path = Path.home() / ".aide" / "engine.js"
        engine_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            url = f"{self.api_url}/api/engine.js"
            # No auth required for engine.js
            res = httpx.get(url, timeout=10.0, follow_redirects=True)
            res.raise_for_status()

            # Validate response is JavaScript, not error JSON
            content = res.text
            if content.startswith("[{") or content.startswith('{"error'):
                raise ValueError("Server returned error instead of JavaScript")

            engine_path.write_text(content)
            return True

        except Exception as e:
            # If fetch fails, check if we have a cached version that looks valid
            if engine_path.exists():
                cached = engine_path.read_text()[:50]
                if not cached.startswith("[{") and not cached.startswith('{"error'):
                    print(f"  Warning: Could not fetch engine.js, using cached version ({e})")
                    return True
            print(f"  Error: Could not fetch engine.js and no valid cached version exists ({e})")
            return False

    def close(self):
        """Close client."""
        self.client.close()
        if self.async_client:
            asyncio.run(self.async_client.aclose())
