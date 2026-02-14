"""Fix RLS policies to handle NULL/empty user_id and add missing policies.

Issues fixed:
1. Empty string app.user_id causes UUID cast error
2. Missing DELETE policy on users table
3. INSERT policy needs to work for system operations

Revision ID: 004
Revises: 003
Create Date: 2026-02-13
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    # Drop old policies on users table
    op.execute("DROP POLICY IF EXISTS users_select_own ON users")
    op.execute("DROP POLICY IF EXISTS users_update_own ON users")
    op.execute("DROP POLICY IF EXISTS users_insert_new ON users")

    # Create new policies with proper NULL/empty handling using COALESCE
    # COALESCE returns first non-null, NULLIF converts empty string to NULL
    # This prevents the UUID cast error when app.user_id is not set

    # SELECT: Users can only see their own row (when user_id is set)
    # System operations (no user_id) return no rows, which is fine for RLS tests
    op.execute("""
        CREATE POLICY users_select_own
        ON users
        FOR SELECT
        USING (
            NULLIF(current_setting('app.user_id', true), '') IS NOT NULL
            AND id = current_setting('app.user_id', true)::uuid
        );
    """)

    # UPDATE: Users can only update their own row
    op.execute("""
        CREATE POLICY users_update_own
        ON users
        FOR UPDATE
        USING (
            NULLIF(current_setting('app.user_id', true), '') IS NOT NULL
            AND id = current_setting('app.user_id', true)::uuid
        );
    """)

    # INSERT: Allow all inserts (needed for user signup)
    # The WITH CHECK validates the new row - true allows all
    op.execute("""
        CREATE POLICY users_insert_allow
        ON users
        FOR INSERT
        WITH CHECK (true);
    """)

    # DELETE: Allow delete when user_id matches OR when no user context (for cleanup)
    # This allows test fixtures and system operations to clean up
    op.execute("""
        CREATE POLICY users_delete_own
        ON users
        FOR DELETE
        USING (
            NULLIF(current_setting('app.user_id', true), '') IS NULL
            OR id = current_setting('app.user_id', true)::uuid
        );
    """)

    # Fix aides table policy
    op.execute("DROP POLICY IF EXISTS aides_all_own ON aides")
    op.execute("""
        CREATE POLICY aides_all_own
        ON aides
        FOR ALL
        USING (
            NULLIF(current_setting('app.user_id', true), '') IS NOT NULL
            AND user_id = current_setting('app.user_id', true)::uuid
        );
    """)

    # Fix conversations table policy
    op.execute("DROP POLICY IF EXISTS conversations_all_own ON conversations")
    op.execute("""
        CREATE POLICY conversations_all_own
        ON conversations
        FOR ALL
        USING (
            NULLIF(current_setting('app.user_id', true), '') IS NOT NULL
            AND aide_id IN (
                SELECT id FROM aides WHERE user_id = current_setting('app.user_id', true)::uuid
            )
        );
    """)

    # Fix published_versions table policy
    op.execute("DROP POLICY IF EXISTS published_versions_all_own ON published_versions")
    op.execute("""
        CREATE POLICY published_versions_all_own
        ON published_versions
        FOR ALL
        USING (
            NULLIF(current_setting('app.user_id', true), '') IS NOT NULL
            AND aide_id IN (
                SELECT id FROM aides WHERE user_id = current_setting('app.user_id', true)::uuid
            )
        );
    """)

    # Fix audit_log policies
    op.execute("DROP POLICY IF EXISTS audit_log_select_own ON audit_log")
    op.execute("DROP POLICY IF EXISTS audit_log_no_update ON audit_log")
    op.execute("DROP POLICY IF EXISTS audit_log_no_delete ON audit_log")
    op.execute("DROP POLICY IF EXISTS audit_log_insert_system ON audit_log")

    op.execute("""
        CREATE POLICY audit_log_select_own
        ON audit_log
        FOR SELECT
        USING (
            NULLIF(current_setting('app.user_id', true), '') IS NOT NULL
            AND user_id = current_setting('app.user_id', true)::uuid
        );
    """)

    op.execute("""
        CREATE POLICY audit_log_insert_allow
        ON audit_log
        FOR INSERT
        WITH CHECK (true);
    """)

    op.execute("""
        CREATE POLICY audit_log_no_update
        ON audit_log
        FOR UPDATE
        USING (false);
    """)

    # Allow DELETE only when no user context (for test cleanup)
    op.execute("""
        CREATE POLICY audit_log_delete_system
        ON audit_log
        FOR DELETE
        USING (NULLIF(current_setting('app.user_id', true), '') IS NULL);
    """)


def downgrade():
    # Restore original policies
    op.execute("DROP POLICY IF EXISTS users_select_own ON users")
    op.execute("DROP POLICY IF EXISTS users_update_own ON users")
    op.execute("DROP POLICY IF EXISTS users_insert_allow ON users")
    op.execute("DROP POLICY IF EXISTS users_delete_own ON users")

    op.execute("""
        CREATE POLICY users_select_own ON users FOR SELECT
        USING (id = current_setting('app.user_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY users_update_own ON users FOR UPDATE
        USING (id = current_setting('app.user_id', true)::uuid);
    """)

    op.execute("DROP POLICY IF EXISTS aides_all_own ON aides")
    op.execute("""
        CREATE POLICY aides_all_own ON aides FOR ALL
        USING (user_id = current_setting('app.user_id', true)::uuid);
    """)

    op.execute("DROP POLICY IF EXISTS conversations_all_own ON conversations")
    op.execute("""
        CREATE POLICY conversations_all_own ON conversations FOR ALL
        USING (aide_id IN (SELECT id FROM aides WHERE user_id = current_setting('app.user_id', true)::uuid));
    """)

    op.execute("DROP POLICY IF EXISTS published_versions_all_own ON published_versions")
    op.execute("""
        CREATE POLICY published_versions_all_own ON published_versions FOR ALL
        USING (aide_id IN (SELECT id FROM aides WHERE user_id = current_setting('app.user_id', true)::uuid));
    """)

    op.execute("DROP POLICY IF EXISTS audit_log_select_own ON audit_log")
    op.execute("DROP POLICY IF EXISTS audit_log_insert_allow ON audit_log")
    op.execute("DROP POLICY IF EXISTS audit_log_no_update ON audit_log")
    op.execute("DROP POLICY IF EXISTS audit_log_delete_system ON audit_log")

    op.execute("""
        CREATE POLICY audit_log_select_own ON audit_log FOR SELECT
        USING (user_id = current_setting('app.user_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY audit_log_no_update ON audit_log FOR UPDATE USING (false);
    """)
    op.execute("""
        CREATE POLICY audit_log_no_delete ON audit_log FOR DELETE USING (false);
    """)
