"""Tests for ConversationRepo with RLS cross-user isolation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.models.aide import CreateAideRequest
from backend.models.conversation import Message
from backend.repos.aide_repo import AideRepo
from backend.repos.conversation_repo import ConversationRepo

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_create_conversation(test_user_id):
    """Test creating a conversation."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()

    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))
    conversation = await conv_repo.create(test_user_id, aide.id, channel="web")

    assert conversation.aide_id == aide.id
    assert conversation.channel == "web"
    assert conversation.messages == []


async def test_get_conversation(test_user_id):
    """Test getting a conversation by ID."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()

    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))
    created = await conv_repo.create(test_user_id, aide.id)
    fetched = await conv_repo.get(test_user_id, created.id)

    assert fetched is not None
    assert fetched.id == created.id


async def test_rls_prevents_cross_user_conversation_access(test_user_id, second_user_id):
    """Verify that user B cannot see user A's conversations."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()

    # Create aide and conversation as user A
    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="User A"))
    conversation = await conv_repo.create(test_user_id, aide.id)

    # Try to access as user B
    result = await conv_repo.get(second_user_id, conversation.id)

    assert result is None  # RLS blocks access


async def test_append_message(test_user_id):
    """Test appending a message to a conversation."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()

    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))
    conversation = await conv_repo.create(test_user_id, aide.id)

    message = Message(
        role="user",
        content="Hello, world!",
        timestamp=datetime.now(UTC),
        metadata={},
    )

    await conv_repo.append_message(test_user_id, conversation.id, message)

    # Fetch and verify
    updated = await conv_repo.get(test_user_id, conversation.id)
    assert updated is not None
    assert len(updated.messages) == 1
    assert updated.messages[0].content == "Hello, world!"


async def test_rls_prevents_cross_user_message_append(test_user_id, second_user_id):
    """Verify that user B cannot append messages to user A's conversation."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()

    # Create aide and conversation as user A
    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="User A"))
    conversation = await conv_repo.create(test_user_id, aide.id)

    # Try to append message as user B
    message = Message(
        role="user",
        content="Unauthorized message",
        timestamp=datetime.now(UTC),
    )

    await conv_repo.append_message(second_user_id, conversation.id, message)

    # Verify message was NOT added (RLS blocked the update)
    original = await conv_repo.get(test_user_id, conversation.id)
    assert original is not None
    assert len(original.messages) == 0


async def test_get_for_aide(test_user_id):
    """Test getting the most recent conversation for an aide."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()

    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))

    # Create multiple conversations
    await conv_repo.create(test_user_id, aide.id)  # conv1 - older
    conv2 = await conv_repo.create(test_user_id, aide.id)  # conv2 - newer

    # Should return the most recent one
    result = await conv_repo.get_for_aide(test_user_id, aide.id)
    assert result is not None
    assert result.id == conv2.id


async def test_list_for_aide(test_user_id, second_user_id):
    """Test listing conversations only shows conversations for user's aides."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()

    # Create aide and conversations for user A
    aide_a = await aide_repo.create(test_user_id, CreateAideRequest(title="User A"))
    await conv_repo.create(test_user_id, aide_a.id)
    await conv_repo.create(test_user_id, aide_a.id)

    # Create aide and conversation for user B
    aide_b = await aide_repo.create(second_user_id, CreateAideRequest(title="User B"))
    await conv_repo.create(second_user_id, aide_b.id)

    # User A should only see their 2 conversations
    convs_a = await conv_repo.list_for_aide(test_user_id, aide_a.id)
    assert len(convs_a) == 2

    # User B should only see their 1 conversation
    convs_b = await conv_repo.list_for_aide(second_user_id, aide_b.id)
    assert len(convs_b) == 1

    # User A should not be able to list user B's conversations
    convs_a_trying_b = await conv_repo.list_for_aide(test_user_id, aide_b.id)
    assert len(convs_a_trying_b) == 0


async def test_delete_conversation(test_user_id):
    """Test deleting a conversation."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()

    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))
    conversation = await conv_repo.create(test_user_id, aide.id)

    deleted = await conv_repo.delete(test_user_id, conversation.id)
    assert deleted is True

    # Verify it's gone
    result = await conv_repo.get(test_user_id, conversation.id)
    assert result is None


async def test_rls_prevents_cross_user_conversation_delete(test_user_id, second_user_id):
    """Verify that user B cannot delete user A's conversation."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()

    # Create aide and conversation as user A
    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="User A"))
    conversation = await conv_repo.create(test_user_id, aide.id)

    # Try to delete as user B
    deleted = await conv_repo.delete(second_user_id, conversation.id)
    assert deleted is False  # RLS blocks delete

    # Verify original still exists
    original = await conv_repo.get(test_user_id, conversation.id)
    assert original is not None


async def test_clear_messages(test_user_id):
    """Test clearing all messages from a conversation."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()

    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))
    conversation = await conv_repo.create(test_user_id, aide.id)

    # Add some messages
    message1 = Message(role="user", content="Message 1", timestamp=datetime.now(UTC))
    message2 = Message(role="assistant", content="Message 2", timestamp=datetime.now(UTC))

    await conv_repo.append_message(test_user_id, conversation.id, message1)
    await conv_repo.append_message(test_user_id, conversation.id, message2)

    # Verify messages exist
    with_messages = await conv_repo.get(test_user_id, conversation.id)
    assert len(with_messages.messages) == 2

    # Clear messages
    await conv_repo.clear_messages(test_user_id, conversation.id)

    # Verify cleared
    cleared = await conv_repo.get(test_user_id, conversation.id)
    assert cleared is not None
    assert len(cleared.messages) == 0


async def test_signal_channel_conversation(test_user_id):
    """Test creating a Signal channel conversation."""
    aide_repo = AideRepo()
    conv_repo = ConversationRepo()

    aide = await aide_repo.create(test_user_id, CreateAideRequest(title="Test"))
    conversation = await conv_repo.create(test_user_id, aide.id, channel="signal")

    assert conversation.channel == "signal"
