"""Tests for AideRepo with RLS cross-user isolation."""

from __future__ import annotations

import pytest

from backend.models.aide import CreateAideRequest, UpdateAideRequest
from backend.repos.aide_repo import AideRepo

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_create_aide(test_user_id):
    """Test creating an aide."""
    repo = AideRepo()
    req = CreateAideRequest(title="My Living Page")

    aide = await repo.create(test_user_id, req)

    assert aide.title == "My Living Page"
    assert aide.user_id == test_user_id
    assert aide.status == "draft"
    assert aide.state == {}
    assert aide.event_log == []
    assert aide.r2_prefix == f"aides/{aide.id}"


async def test_get_aide(test_user_id):
    """Test getting an aide by ID."""
    repo = AideRepo()
    req = CreateAideRequest(title="Test Aide")

    created = await repo.create(test_user_id, req)
    fetched = await repo.get(test_user_id, created.id)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.title == "Test Aide"


async def test_rls_prevents_cross_user_access(test_user_id, second_user_id):
    """Verify that user A cannot see user B's aides via RLS."""
    repo = AideRepo()

    # Create aide as user A
    aide = await repo.create(test_user_id, CreateAideRequest(title="Secret Page"))

    # Try to access as user B
    result = await repo.get(second_user_id, aide.id)

    assert result is None  # RLS blocks access


async def test_list_for_user(test_user_id, second_user_id):
    """Test listing aides only shows own aides."""
    repo = AideRepo()

    # Create aides for user A
    await repo.create(test_user_id, CreateAideRequest(title="User A - Page 1"))
    await repo.create(test_user_id, CreateAideRequest(title="User A - Page 2"))

    # Create aide for user B
    await repo.create(second_user_id, CreateAideRequest(title="User B - Page 1"))

    # User A should only see their 2 aides
    user_a_aides = await repo.list_for_user(test_user_id)
    assert len(user_a_aides) == 2
    assert all(a.user_id == test_user_id for a in user_a_aides)

    # User B should only see their 1 aide
    user_b_aides = await repo.list_for_user(second_user_id)
    assert len(user_b_aides) == 1
    assert user_b_aides[0].user_id == second_user_id


async def test_update_aide(test_user_id):
    """Test updating an aide."""
    repo = AideRepo()

    aide = await repo.create(test_user_id, CreateAideRequest(title="Original"))
    updated = await repo.update(test_user_id, aide.id, UpdateAideRequest(title="Updated Title"))

    assert updated is not None
    assert updated.title == "Updated Title"
    assert updated.id == aide.id


async def test_rls_prevents_cross_user_update(test_user_id, second_user_id):
    """Verify that user B cannot update user A's aide."""
    repo = AideRepo()

    # Create aide as user A
    aide = await repo.create(test_user_id, CreateAideRequest(title="User A's Aide"))

    # Try to update as user B
    result = await repo.update(second_user_id, aide.id, UpdateAideRequest(title="Hacked"))

    assert result is None  # RLS blocks update

    # Verify original is unchanged
    original = await repo.get(test_user_id, aide.id)
    assert original.title == "User A's Aide"


async def test_delete_aide(test_user_id):
    """Test deleting an aide."""
    repo = AideRepo()

    aide = await repo.create(test_user_id, CreateAideRequest(title="To Delete"))
    deleted = await repo.delete(test_user_id, aide.id)

    assert deleted is True

    # Verify it's gone
    result = await repo.get(test_user_id, aide.id)
    assert result is None


async def test_rls_prevents_cross_user_delete(test_user_id, second_user_id):
    """Verify that user B cannot delete user A's aide."""
    repo = AideRepo()

    # Create aide as user A
    aide = await repo.create(test_user_id, CreateAideRequest(title="Protected"))

    # Try to delete as user B
    deleted = await repo.delete(second_user_id, aide.id)

    assert deleted is False  # RLS blocks delete

    # Verify original still exists
    original = await repo.get(test_user_id, aide.id)
    assert original is not None


async def test_archive_aide(test_user_id):
    """Test archiving an aide."""
    repo = AideRepo()

    aide = await repo.create(test_user_id, CreateAideRequest(title="To Archive"))
    archived = await repo.archive(test_user_id, aide.id)

    assert archived is not None
    assert archived.status == "archived"

    # Archived aides should not appear in list
    aides = await repo.list_for_user(test_user_id)
    assert len(aides) == 0


async def test_publish_and_unpublish(test_user_id):
    """Test publishing and unpublishing an aide."""
    repo = AideRepo()

    aide = await repo.create(test_user_id, CreateAideRequest(title="To Publish"))

    # Publish with slug
    published = await repo.publish(test_user_id, aide.id, "my-page")
    assert published is not None
    assert published.status == "published"
    assert published.slug == "my-page"

    # Can retrieve by slug
    by_slug = await repo.get_by_slug("my-page")
    assert by_slug is not None
    assert by_slug.id == aide.id

    # Unpublish
    unpublished = await repo.unpublish(test_user_id, aide.id)
    assert unpublished is not None
    assert unpublished.status == "draft"
    assert unpublished.slug is None

    # Can no longer retrieve by slug
    by_slug_after = await repo.get_by_slug("my-page")
    assert by_slug_after is None


async def test_update_state(test_user_id):
    """Test updating aide state and event log."""
    repo = AideRepo()

    aide = await repo.create(test_user_id, CreateAideRequest(title="State Test"))

    state = {"collections": {"tasks": {"items": []}}}
    event_log = [{"type": "collection.create", "payload": {"name": "tasks"}}]

    updated = await repo.update_state(test_user_id, aide.id, state, event_log)

    assert updated is not None
    assert updated.state == state
    assert updated.event_log == event_log


async def test_count_for_user(test_user_id, second_user_id):
    """Test counting aides respects RLS."""
    repo = AideRepo()

    # Create 3 aides for user A
    await repo.create(test_user_id, CreateAideRequest(title="A1"))
    await repo.create(test_user_id, CreateAideRequest(title="A2"))
    aide_to_archive = await repo.create(test_user_id, CreateAideRequest(title="A3"))
    await repo.archive(test_user_id, aide_to_archive.id)

    # Create 1 aide for user B
    await repo.create(second_user_id, CreateAideRequest(title="B1"))

    # User A should see 2 (archived not counted)
    count_a = await repo.count_for_user(test_user_id)
    assert count_a == 2

    # User B should see 1
    count_b = await repo.count_for_user(second_user_id)
    assert count_b == 1
