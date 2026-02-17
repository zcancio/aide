"""HTTP client for signal-cli-rest-api."""

from __future__ import annotations

import logging

import httpx

from backend import config

logger = logging.getLogger(__name__)


class SignalService:
    """HTTP client for signal-cli-rest-api.

    Communicates with the signal-cli-rest-api sidecar service to send
    Signal messages and check service health.
    """

    def __init__(self) -> None:
        self._base_url = config.settings.SIGNAL_CLI_URL
        self._phone = config.settings.SIGNAL_PHONE_NUMBER

    async def send_message(
        self,
        recipient: str,
        message: str,
        attachments: list[str] | None = None,
    ) -> dict:
        """
        Send a Signal message via signal-cli-rest-api.

        Args:
            recipient: Recipient phone number in E.164 format (e.g. "+15551234567")
            message: Text content to send
            attachments: Optional list of base64-encoded attachment data

        Returns:
            Response dict from signal-cli-rest-api

        Raises:
            httpx.HTTPError: If the signal-cli service is unreachable or returns an error
        """
        payload: dict = {
            "number": self._phone,
            "recipients": [recipient],
            "message": message,
        }
        if attachments:
            payload["base64_attachments"] = attachments

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self._base_url}/v2/send",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def health_check(self) -> bool:
        """
        Check whether signal-cli is healthy.

        Returns:
            True if signal-cli responds to /v1/health, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/v1/health")
                return response.status_code == 200
        except Exception:
            logger.warning("signal-cli health check failed")
            return False


signal_service = SignalService()
