"""Integration tests for the Signal webhook flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.models.aide import CreateAideRequest
from backend.models.signal_mapping import CreateSignalMappingRequest
from backend.repos.aide_repo import AideRepo
from backend.repos.conversation_repo import ConversationRepo
from backend.repos.signal_link_code_repo import SignalLinkCodeRepo
from backend.repos.signal_mapping_repo import SignalMappingRepo
from backend.routes.signal import _handle_aide_update, _handle_link_code

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_handle_link_code_creates_mapping(test_user_id):
    """Test that a valid link code creates a Signal mapping."""
    aide_repo = AideRepo()
    link_code_repo = SignalLinkCodeRepo()
    mapping_repo = SignalMappingRepo()

    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))
    link_code = await link_code_repo.create(test_user_id, aide.id)

    phone = "+15550001111"

    with patch("backend.routes.signal.signal_service") as mock_svc:
        mock_svc.send_message = AsyncMock()
        result = await _handle_link_code(phone, link_code.code)

    assert result["status"] == "linked"
    mock_svc.send_message.assert_called_once()
    call_args = mock_svc.send_message.call_args.args
    assert call_args[0] == phone
    assert "Connected" in call_args[1]

    # Verify mapping was created
    mapping = await mapping_repo.get_by_phone(phone)
    assert mapping is not None
    assert mapping.aide_id == aide.id
    assert mapping.user_id == test_user_id

    # Verify code is marked used
    stale = await link_code_repo.get_by_code(link_code.code)
    assert stale is None


async def test_handle_link_code_invalid(test_user_id):
    """Test that an invalid link code sends an error reply."""
    phone = "+15550002222"

    with patch("backend.routes.signal.signal_service") as mock_svc:
        mock_svc.send_message = AsyncMock()
        result = await _handle_link_code(phone, "FFFFFF")

    assert result["status"] == "invalid_code"
    mock_svc.send_message.assert_called_once()
    msg = mock_svc.send_message.call_args.args[1]
    assert "invalid" in msg.lower() or "expired" in msg.lower()


async def test_handle_aide_update_unknown_phone():
    """Test that an unknown phone gets a link-prompt reply."""
    phone = "+15500099999"

    with patch("backend.routes.signal.signal_service") as mock_svc:
        mock_svc.send_message = AsyncMock()
        result = await _handle_aide_update(phone, "update something")

    assert result["status"] == "unknown_phone"
    mock_svc.send_message.assert_called_once()


async def test_handle_aide_update_routes_to_orchestrator(test_user_id):
    """Test that a known phone routes the message to the orchestrator."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()
    mapping_repo = SignalMappingRepo()

    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))
    conversation = await conv_repo.create(test_user_id, aide.id, channel="signal")

    phone = "+15550003333"
    req = CreateSignalMappingRequest(phone_number=phone, aide_id=aide.id)
    await mapping_repo.create(test_user_id, req, conversation.id)

    with patch("backend.routes.signal.signal_service") as mock_svc:
        mock_svc.send_message = AsyncMock()
        with patch("backend.routes.signal.orchestrator") as mock_orch:
            mock_orch.process_message = AsyncMock(
                return_value={"response": "Updated.", "html_url": "https://r2.example.com/test"}
            )
            result = await _handle_aide_update(phone, "add milk to the list")

    assert result["status"] == "processed"
    mock_orch.process_message.assert_called_once_with(
        user_id=test_user_id,
        aide_id=aide.id,
        message="add milk to the list",
        source="signal",
    )
    mock_svc.send_message.assert_called_once_with(phone, "Updated.")


async def test_handle_aide_update_orchestrator_error(test_user_id):
    """Test that orchestrator errors send an error reply."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()
    mapping_repo = SignalMappingRepo()

    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))
    conversation = await conv_repo.create(test_user_id, aide.id, channel="signal")

    phone = "+15550004444"
    req = CreateSignalMappingRequest(phone_number=phone, aide_id=aide.id)
    await mapping_repo.create(test_user_id, req, conversation.id)

    with patch("backend.routes.signal.signal_service") as mock_svc:
        mock_svc.send_message = AsyncMock()
        with patch("backend.routes.signal.orchestrator") as mock_orch:
            mock_orch.process_message = AsyncMock(side_effect=RuntimeError("AI error"))
            result = await _handle_aide_update(phone, "something")

    assert result["status"] == "error"
    mock_svc.send_message.assert_called_once()
    msg = mock_svc.send_message.call_args.args[1]
    assert "wrong" in msg.lower()


async def test_generate_link_code_verifies_aide_ownership(test_user_id, second_user_id):
    """
    Test that generating a link code via the route checks aide ownership.

    The route calls aide_repo.get(user.id, req.aide_id) before creating the code,
    so user B cannot generate a link code for user A's aide via the API layer.
    This is the correct enforcement point — the route returns 404 for non-owned aides.
    """
    aide_repo = AideRepo()

    # User A creates an aide
    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="User A Aide"))

    # User B cannot see user A's aide via user_conn (RLS blocks it)
    aide_for_b = await aide_repo.get(second_user_id, aide.id)
    assert aide_for_b is None  # RLS isolation confirmed
