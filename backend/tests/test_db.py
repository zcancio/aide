"""
Tests for database connection pool and RLS scoping.

NOTE: These tests require a running PostgreSQL database with the DATABASE_URL environment variable set.
Run `alembic upgrade head` before running these tests.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend import db


@pytest.mark.asyncio
async def test_pool_initialization():
    """Test that the database pool is initialized correctly."""
    assert db.pool is not None
    assert db.pool.get_size() > 0


@pytest.mark.asyncio
async def test_system_conn_works():
    """Test that system_conn can execute queries."""
    async with db.system_conn() as conn:
        result = await conn.fetchval("SELECT 1")
        assert result == 1


@pytest.mark.asyncio
async def test_user_conn_sets_rls_context(test_user_id):
    """Test that user_conn sets the RLS context correctly."""
    async with db.user_conn(test_user_id) as conn:
        # Check that the RLS context is set
        user_id_from_setting = await conn.fetchval("SELECT current_setting('app.user_id', true)")
        assert user_id_from_setting == str(test_user_id)


@pytest.mark.asyncio
async def test_user_can_read_own_data(test_user_id):
    """Test that a user can read their own user record via RLS."""
    async with db.user_conn(test_user_id) as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1",
            test_user_id,
        )
        assert row is not None
        assert row["id"] == test_user_id
        assert row["email"] == f"test-{test_user_id}@example.com"


@pytest.mark.asyncio
async def test_user_cannot_read_other_user_data(test_user_id, second_user_id):
    """Test that RLS prevents reading another user's data."""
    # User A tries to read User B's data
    async with db.user_conn(test_user_id) as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1",
            second_user_id,
        )
        # RLS should prevent this - row should be None
        assert row is None


@pytest.mark.asyncio
async def test_user_can_create_aide(test_user_id):
    """Test that a user can create an aide through user_conn."""
    aide_id = uuid4()

    async with db.user_conn(test_user_id) as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO aides (id, user_id, title, r2_prefix)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            aide_id,
            test_user_id,
            "My Test Aide",
            f"aides/{aide_id}",
        )

        assert row is not None
        assert row["id"] == aide_id
        assert row["user_id"] == test_user_id
        assert row["title"] == "My Test Aide"

        # Cleanup
        await conn.execute("DELETE FROM aides WHERE id = $1", aide_id)


@pytest.mark.asyncio
async def test_user_can_list_own_aides_only(test_user_id, second_user_id):
    """Test that user_conn only returns the user's own aides."""
    # Create aide for user A
    aide_a_id = uuid4()
    async with db.user_conn(test_user_id) as conn:
        await conn.execute(
            """
            INSERT INTO aides (id, user_id, title, r2_prefix)
            VALUES ($1, $2, $3, $4)
            """,
            aide_a_id,
            test_user_id,
            "Aide A",
            f"aides/{aide_a_id}",
        )

    # Create aide for user B
    aide_b_id = uuid4()
    async with db.user_conn(second_user_id) as conn:
        await conn.execute(
            """
            INSERT INTO aides (id, user_id, title, r2_prefix)
            VALUES ($1, $2, $3, $4)
            """,
            aide_b_id,
            second_user_id,
            "Aide B",
            f"aides/{aide_b_id}",
        )

    # User A lists aides - should only see their own
    async with db.user_conn(test_user_id) as conn:
        rows = await conn.fetch("SELECT * FROM aides")
        aide_ids = [row["id"] for row in rows]

        assert aide_a_id in aide_ids
        assert aide_b_id not in aide_ids

    # User B lists aides - should only see their own
    async with db.user_conn(second_user_id) as conn:
        rows = await conn.fetch("SELECT * FROM aides")
        aide_ids = [row["id"] for row in rows]

        assert aide_b_id in aide_ids
        assert aide_a_id not in aide_ids

    # Cleanup
    async with db.user_conn(test_user_id) as conn:
        await conn.execute("DELETE FROM aides WHERE id = $1", aide_a_id)
    async with db.user_conn(second_user_id) as conn:
        await conn.execute("DELETE FROM aides WHERE id = $1", aide_b_id)


@pytest.mark.asyncio
async def test_user_cannot_update_other_user_aide(test_user_id, second_user_id):
    """Test that RLS prevents updating another user's aide."""
    # User A creates an aide
    aide_id = uuid4()
    async with db.user_conn(test_user_id) as conn:
        await conn.execute(
            """
            INSERT INTO aides (id, user_id, title, r2_prefix)
            VALUES ($1, $2, $3, $4)
            """,
            aide_id,
            test_user_id,
            "Original Title",
            f"aides/{aide_id}",
        )

    # User B tries to update User A's aide
    async with db.user_conn(second_user_id) as conn:
        result = await conn.execute(
            """
            UPDATE aides
            SET title = $2
            WHERE id = $1
            """,
            aide_id,
            "Hacked Title",
        )
        # RLS should prevent this - no rows affected
        assert result == "UPDATE 0"

    # Verify the title wasn't changed
    async with db.user_conn(test_user_id) as conn:
        row = await conn.fetchrow("SELECT * FROM aides WHERE id = $1", aide_id)
        assert row["title"] == "Original Title"

        # Cleanup
        await conn.execute("DELETE FROM aides WHERE id = $1", aide_id)


@pytest.mark.asyncio
async def test_user_cannot_delete_other_user_aide(test_user_id, second_user_id):
    """Test that RLS prevents deleting another user's aide."""
    # User A creates an aide
    aide_id = uuid4()
    async with db.user_conn(test_user_id) as conn:
        await conn.execute(
            """
            INSERT INTO aides (id, user_id, title, r2_prefix)
            VALUES ($1, $2, $3, $4)
            """,
            aide_id,
            test_user_id,
            "Important Aide",
            f"aides/{aide_id}",
        )

    # User B tries to delete User A's aide
    async with db.user_conn(second_user_id) as conn:
        result = await conn.execute("DELETE FROM aides WHERE id = $1", aide_id)
        # RLS should prevent this - no rows affected
        assert result == "DELETE 0"

    # Verify the aide still exists
    async with db.user_conn(test_user_id) as conn:
        row = await conn.fetchrow("SELECT * FROM aides WHERE id = $1", aide_id)
        assert row is not None

        # Cleanup
        await conn.execute("DELETE FROM aides WHERE id = $1", aide_id)


@pytest.mark.asyncio
async def test_conversations_rls_via_aide(test_user_id, second_user_id):
    """Test that conversations are scoped via their parent aide's user_id."""
    # User A creates an aide and conversation
    aide_id = uuid4()
    conversation_id = uuid4()

    async with db.user_conn(test_user_id) as conn:
        await conn.execute(
            """
            INSERT INTO aides (id, user_id, title, r2_prefix)
            VALUES ($1, $2, $3, $4)
            """,
            aide_id,
            test_user_id,
            "Aide with Conversation",
            f"aides/{aide_id}",
        )

        await conn.execute(
            """
            INSERT INTO conversations (id, aide_id, messages)
            VALUES ($1, $2, $3)
            """,
            conversation_id,
            aide_id,
            '[{"role": "user", "content": "Hello"}]',
        )

    # User B tries to read User A's conversation
    async with db.user_conn(second_user_id) as conn:
        row = await conn.fetchrow(
            "SELECT * FROM conversations WHERE id = $1",
            conversation_id,
        )
        # RLS should prevent this - row should be None
        assert row is None

    # User A can read their own conversation
    async with db.user_conn(test_user_id) as conn:
        row = await conn.fetchrow(
            "SELECT * FROM conversations WHERE id = $1",
            conversation_id,
        )
        assert row is not None
        assert row["aide_id"] == aide_id

        # Cleanup
        await conn.execute("DELETE FROM aides WHERE id = $1", aide_id)


@pytest.mark.asyncio
async def test_audit_log_append_only(test_user_id):
    """Test that audit_log is append-only (no updates or deletes)."""
    # Insert an audit log entry via system_conn
    log_id = uuid4()
    async with db.system_conn() as conn:
        await conn.execute(
            """
            INSERT INTO audit_log (id, user_id, action, resource_type, resource_id)
            VALUES ($1, $2, $3, $4, $5)
            """,
            log_id,
            test_user_id,
            "test_action",
            "test_resource",
            uuid4(),
        )

    # User tries to update the log entry
    async with db.user_conn(test_user_id) as conn:
        result = await conn.execute(
            """
            UPDATE audit_log
            SET action = $2
            WHERE id = $1
            """,
            log_id,
            "modified_action",
        )
        # RLS policy should prevent this
        assert result == "UPDATE 0"

    # User tries to delete the log entry
    async with db.user_conn(test_user_id) as conn:
        result = await conn.execute(
            "DELETE FROM audit_log WHERE id = $1",
            log_id,
        )
        # RLS policy should prevent this
        assert result == "DELETE 0"

    # Verify the entry still exists with original data
    async with db.system_conn() as conn:
        row = await conn.fetchrow("SELECT * FROM audit_log WHERE id = $1", log_id)
        assert row is not None
        assert row["action"] == "test_action"

        # Cleanup (system can delete for test cleanup)
        await conn.execute("DELETE FROM audit_log WHERE id = $1", log_id)
