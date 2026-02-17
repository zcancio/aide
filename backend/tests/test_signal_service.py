"""Tests for SignalService with mocked HTTP."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.services.signal_service import SignalService

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_send_message_success():
    """Test that send_message POSTs to signal-cli and returns the response."""
    service = SignalService()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"timestamp": 1234567890}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await service.send_message("+15551234567", "Hello!")

    assert result == {"timestamp": 1234567890}
    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    assert "/v2/send" in call_kwargs.args[0]
    payload = call_kwargs.kwargs["json"]
    assert payload["recipients"] == ["+15551234567"]
    assert payload["message"] == "Hello!"


async def test_send_message_with_attachments():
    """Test that attachments are included in the payload."""
    service = SignalService()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        await service.send_message("+15551234567", "Photo", attachments=["base64data"])

    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["base64_attachments"] == ["base64data"]


async def test_send_message_raises_on_http_error():
    """Test that send_message propagates HTTP errors."""
    service = SignalService()

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Server Error", request=MagicMock(), response=MagicMock()
    )

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await service.send_message("+15551234567", "Hello!")


async def test_health_check_success():
    """Test health_check returns True when signal-cli responds 200."""
    service = SignalService()

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await service.health_check()

    assert result is True


async def test_health_check_failure():
    """Test health_check returns False when signal-cli is unreachable."""
    service = SignalService()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client_cls.return_value = mock_client

        result = await service.health_check()

    assert result is False


async def test_health_check_non_200():
    """Test health_check returns False for non-200 responses."""
    service = SignalService()

    mock_response = MagicMock()
    mock_response.status_code = 503

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await service.health_check()

    assert result is False
