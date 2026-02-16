"""Tests for SignalMappingRepo with RLS cross-user isolation."""

from __future__ import annotations

import asyncpg
import pytest

from backend.models.aide import CreateAideRequest
from backend.models.signal_mapping import CreateSignalMappingRequest
from backend.repos.aide_repo import AideRepo
from backend.repos.conversation_repo import ConversationRepo
from backend.repos.signal_mapping_repo import SignalMappingRepo

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_create_signal_mapping(test_user_id):
    """Test creating a Signal mapping."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()
    mapping_repo = SignalMappingRepo()

    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))
    conversation = await conv_repo.create(test_user_id, aide.id, channel="signal")

    req = CreateSignalMappingRequest(phone_number="+15551234567", aide_id=aide.id)
    mapping = await mapping_repo.create(test_user_id, req, conversation.id)

    assert mapping.phone_number == "+15551234567"
    assert mapping.user_id == test_user_id
    assert mapping.aide_id == aide.id
    assert mapping.conversation_id == conversation.id


async def test_get_by_phone(test_user_id):
    """Test getting a Signal mapping by phone number."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()
    mapping_repo = SignalMappingRepo()

    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))
    conversation = await conv_repo.create(test_user_id, aide.id, channel="signal")

    req = CreateSignalMappingRequest(phone_number="+15559876543", aide_id=aide.id)
    created = await mapping_repo.create(test_user_id, req, conversation.id)

    # System conn lookup (used by Signal ear)
    fetched = await mapping_repo.get_by_phone("+15559876543")

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.phone_number == "+15559876543"


async def test_get_signal_mapping(test_user_id):
    """Test getting a Signal mapping by ID."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()
    mapping_repo = SignalMappingRepo()

    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))
    conversation = await conv_repo.create(test_user_id, aide.id, channel="signal")

    req = CreateSignalMappingRequest(phone_number="+15551111111", aide_id=aide.id)
    created = await mapping_repo.create(test_user_id, req, conversation.id)

    fetched = await mapping_repo.get(test_user_id, created.id)

    assert fetched is not None
    assert fetched.id == created.id


async def test_rls_prevents_cross_user_signal_mapping_access(test_user_id, second_user_id):
    """Verify that user B cannot see user A's Signal mappings."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()
    mapping_repo = SignalMappingRepo()

    # Create aide, conversation, and mapping as user A
    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="User A"))
    conversation = await conv_repo.create(test_user_id, aide.id, channel="signal")

    req = CreateSignalMappingRequest(phone_number="+15552222222", aide_id=aide.id)
    mapping = await mapping_repo.create(test_user_id, req, conversation.id)

    # Try to access as user B
    result = await mapping_repo.get(second_user_id, mapping.id)

    assert result is None  # RLS blocks access


async def test_get_by_aide(test_user_id):
    """Test getting a Signal mapping by aide ID."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()
    mapping_repo = SignalMappingRepo()

    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))
    conversation = await conv_repo.create(test_user_id, aide.id, channel="signal")

    req = CreateSignalMappingRequest(phone_number="+15553333333", aide_id=aide.id)
    created = await mapping_repo.create(test_user_id, req, conversation.id)

    fetched = await mapping_repo.get_by_aide(test_user_id, aide.id)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.aide_id == aide.id


async def test_list_for_user(test_user_id, second_user_id):
    """Test listing Signal mappings only shows own mappings."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()
    mapping_repo = SignalMappingRepo()

    # Create mappings for user A
    aide_a1 = await aide_repo.create(test_user_id, CreateAideRequest(title="A1"))
    conv_a1 = await conv_repo.create(test_user_id, aide_a1.id, channel="signal")
    req_a1 = CreateSignalMappingRequest(phone_number="+15554444444", aide_id=aide_a1.id)
    await mapping_repo.create(test_user_id, req_a1, conv_a1.id)

    aide_a2 = await aide_repo.create(test_user_id, CreateAideRequest(title="A2"))
    conv_a2 = await conv_repo.create(test_user_id, aide_a2.id, channel="signal")
    req_a2 = CreateSignalMappingRequest(phone_number="+15555555555", aide_id=aide_a2.id)
    await mapping_repo.create(test_user_id, req_a2, conv_a2.id)

    # Create mapping for user B
    aide_b = await aide_repo.create(second_user_id, CreateAideRequest(title="B1"))
    conv_b = await conv_repo.create(second_user_id, aide_b.id, channel="signal")
    req_b = CreateSignalMappingRequest(phone_number="+15556666666", aide_id=aide_b.id)
    await mapping_repo.create(second_user_id, req_b, conv_b.id)

    # User A should only see their 2 mappings
    mappings_a = await mapping_repo.list_for_user(test_user_id)
    assert len(mappings_a) == 2
    assert all(m.user_id == test_user_id for m in mappings_a)

    # User B should only see their 1 mapping
    mappings_b = await mapping_repo.list_for_user(second_user_id)
    assert len(mappings_b) == 1
    assert mappings_b[0].user_id == second_user_id


async def test_delete_signal_mapping(test_user_id):
    """Test deleting a Signal mapping."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()
    mapping_repo = SignalMappingRepo()

    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))
    conversation = await conv_repo.create(test_user_id, aide.id, channel="signal")

    req = CreateSignalMappingRequest(phone_number="+15557777777", aide_id=aide.id)
    mapping = await mapping_repo.create(test_user_id, req, conversation.id)

    deleted = await mapping_repo.delete(test_user_id, mapping.id)
    assert deleted is True

    # Verify it's gone
    result = await mapping_repo.get(test_user_id, mapping.id)
    assert result is None


async def test_rls_prevents_cross_user_signal_mapping_delete(test_user_id, second_user_id):
    """Verify that user B cannot delete user A's Signal mapping."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()
    mapping_repo = SignalMappingRepo()

    # Create aide, conversation, and mapping as user A
    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="User A"))
    conversation = await conv_repo.create(test_user_id, aide.id, channel="signal")

    req = CreateSignalMappingRequest(phone_number="+15558888888", aide_id=aide.id)
    mapping = await mapping_repo.create(test_user_id, req, conversation.id)

    # Try to delete as user B
    deleted = await mapping_repo.delete(second_user_id, mapping.id)
    assert deleted is False  # RLS blocks delete

    # Verify original still exists
    original = await mapping_repo.get(test_user_id, mapping.id)
    assert original is not None


async def test_delete_by_phone(test_user_id):
    """Test deleting a Signal mapping by phone number (system operation)."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()
    mapping_repo = SignalMappingRepo()

    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))
    conversation = await conv_repo.create(test_user_id, aide.id, channel="signal")

    req = CreateSignalMappingRequest(phone_number="+15559999999", aide_id=aide.id)
    await mapping_repo.create(test_user_id, req, conversation.id)

    # Delete by phone (system conn)
    deleted = await mapping_repo.delete_by_phone("+15559999999")
    assert deleted is True

    # Verify it's gone
    result = await mapping_repo.get_by_phone("+15559999999")
    assert result is None


async def test_update_conversation(test_user_id):
    """Test updating the conversation_id for a Signal mapping."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()
    mapping_repo = SignalMappingRepo()

    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))
    conversation1 = await conv_repo.create(test_user_id, aide.id, channel="signal")
    conversation2 = await conv_repo.create(test_user_id, aide.id, channel="signal")

    req = CreateSignalMappingRequest(phone_number="+15550000000", aide_id=aide.id)
    mapping = await mapping_repo.create(test_user_id, req, conversation1.id)

    # Update to conversation2
    updated = await mapping_repo.update_conversation(test_user_id, mapping.id, conversation2.id)

    assert updated is not None
    assert updated.conversation_id == conversation2.id


async def test_unique_phone_number_constraint(test_user_id):
    """Test that phone numbers must be unique across all users."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()
    mapping_repo = SignalMappingRepo()

    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))
    conversation = await conv_repo.create(test_user_id, aide.id, channel="signal")

    phone = "+15551231234"
    req1 = CreateSignalMappingRequest(phone_number=phone, aide_id=aide.id)
    await mapping_repo.create(test_user_id, req1, conversation.id)

    # Try to create another mapping with the same phone number
    aide2 = await aide_repo.create(test_user_id, CreateAideRequest(title="Test2"))
    conversation2 = await conv_repo.create(test_user_id, aide2.id, channel="signal")
    req2 = CreateSignalMappingRequest(phone_number=phone, aide_id=aide2.id)

    with pytest.raises(asyncpg.UniqueViolationError):
        await mapping_repo.create(test_user_id, req2, conversation2.id)
