"""Fix RLS policies UUID cast issue in subqueries.

PostgreSQL's query planner evaluates UUID casts in RLS policy subqueries
even when CASE WHEN short-circuits. This causes errors when app.user_id
is empty.

Solution: Create a get_app_user_id() function that safely handles
NULL/empty values, and use it in all RLS policies.

Revision ID: 005
Revises: ccee0808c23a
Create Date: 2026-02-16
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "005"
down_revision = "ccee0808c23a"
branch_labels = None
depends_on = None


def upgrade():
    # Create a function to safely get the app user ID
    # This avoids the UUID cast error when app.user_id is empty
    op.execute("""
        CREATE OR REPLACE FUNCTION get_app_user_id() RETURNS uuid AS $$
        DECLARE
            val text;
        BEGIN
            val := current_setting('app.user_id', true);
            IF val IS NULL OR val = '' THEN
                RETURN NULL;
            END IF;
            RETURN val::uuid;
        END;
        $$ LANGUAGE plpgsql STABLE;
    """)

    # Update all RLS policies to use the function instead of direct casting
    # This prevents PostgreSQL from evaluating the UUID cast during query planning

    # Users table
    op.execute("DROP POLICY IF EXISTS users_select_own ON users")
    op.execute("DROP POLICY IF EXISTS users_update_own ON users")
    op.execute("DROP POLICY IF EXISTS users_delete_own ON users")

    op.execute("""
        CREATE POLICY users_select_own ON users
        FOR SELECT
        USING (get_app_user_id() IS NULL OR id = get_app_user_id());
    """)

    op.execute("""
        CREATE POLICY users_update_own ON users
        FOR UPDATE
        USING (get_app_user_id() IS NULL OR id = get_app_user_id());
    """)

    op.execute("""
        CREATE POLICY users_delete_own ON users
        FOR DELETE
        USING (get_app_user_id() IS NULL OR id = get_app_user_id());
    """)

    # Aides table
    op.execute("DROP POLICY IF EXISTS aides_all_own ON aides")
    op.execute("""
        CREATE POLICY aides_all_own ON aides
        FOR ALL
        USING (get_app_user_id() IS NULL OR user_id = get_app_user_id());
    """)

    # Conversations table (this was the problematic one with subquery)
    op.execute("DROP POLICY IF EXISTS conversations_all_own ON conversations")
    op.execute("""
        CREATE POLICY conversations_all_own ON conversations
        FOR ALL
        USING (
            get_app_user_id() IS NULL OR
            aide_id IN (SELECT id FROM aides WHERE user_id = get_app_user_id())
        );
    """)

    # Signal mappings table
    op.execute("DROP POLICY IF EXISTS signal_mappings_all_own ON signal_mappings")
    op.execute("""
        CREATE POLICY signal_mappings_all_own ON signal_mappings
        FOR ALL
        USING (get_app_user_id() IS NULL OR user_id = get_app_user_id());
    """)

    # Published versions table
    op.execute("DROP POLICY IF EXISTS published_versions_all_own ON published_versions")
    op.execute("""
        CREATE POLICY published_versions_all_own ON published_versions
        FOR ALL
        USING (
            get_app_user_id() IS NULL OR
            aide_id IN (SELECT id FROM aides WHERE user_id = get_app_user_id())
        );
    """)

    # Audit log table
    op.execute("DROP POLICY IF EXISTS audit_log_select_own ON audit_log")
    op.execute("""
        CREATE POLICY audit_log_select_own ON audit_log
        FOR SELECT
        USING (get_app_user_id() IS NULL OR user_id = get_app_user_id());
    """)


def downgrade():
    # Restore CASE-based policies (the old approach that had issues)

    # Users table
    op.execute("DROP POLICY IF EXISTS users_select_own ON users")
    op.execute("DROP POLICY IF EXISTS users_update_own ON users")
    op.execute("DROP POLICY IF EXISTS users_delete_own ON users")

    op.execute("""
        CREATE POLICY users_select_own ON users FOR SELECT
        USING (
            CASE
                WHEN NULLIF(current_setting('app.user_id', true), '') IS NULL THEN true
                ELSE id = current_setting('app.user_id', true)::uuid
            END
        );
    """)

    op.execute("""
        CREATE POLICY users_update_own ON users FOR UPDATE
        USING (
            CASE
                WHEN NULLIF(current_setting('app.user_id', true), '') IS NULL THEN true
                ELSE id = current_setting('app.user_id', true)::uuid
            END
        );
    """)

    op.execute("""
        CREATE POLICY users_delete_own ON users FOR DELETE
        USING (
            CASE
                WHEN NULLIF(current_setting('app.user_id', true), '') IS NULL THEN true
                ELSE id = current_setting('app.user_id', true)::uuid
            END
        );
    """)

    # Aides table
    op.execute("DROP POLICY IF EXISTS aides_all_own ON aides")
    op.execute("""
        CREATE POLICY aides_all_own ON aides FOR ALL
        USING (
            CASE
                WHEN NULLIF(current_setting('app.user_id', true), '') IS NULL THEN true
                ELSE user_id = current_setting('app.user_id', true)::uuid
            END
        );
    """)

    # Conversations table
    op.execute("DROP POLICY IF EXISTS conversations_all_own ON conversations")
    op.execute("""
        CREATE POLICY conversations_all_own ON conversations FOR ALL
        USING (
            CASE
                WHEN NULLIF(current_setting('app.user_id', true), '') IS NULL THEN true
                ELSE aide_id IN (
                    SELECT id FROM aides WHERE user_id = current_setting('app.user_id', true)::uuid
                )
            END
        );
    """)

    # Signal mappings table
    op.execute("DROP POLICY IF EXISTS signal_mappings_all_own ON signal_mappings")
    op.execute("""
        CREATE POLICY signal_mappings_all_own ON signal_mappings FOR ALL
        USING (
            CASE
                WHEN NULLIF(current_setting('app.user_id', true), '') IS NULL THEN true
                ELSE user_id = current_setting('app.user_id', true)::uuid
            END
        );
    """)

    # Published versions table
    op.execute("DROP POLICY IF EXISTS published_versions_all_own ON published_versions")
    op.execute("""
        CREATE POLICY published_versions_all_own ON published_versions FOR ALL
        USING (
            CASE
                WHEN NULLIF(current_setting('app.user_id', true), '') IS NULL THEN true
                ELSE aide_id IN (
                    SELECT id FROM aides WHERE user_id = current_setting('app.user_id', true)::uuid
                )
            END
        );
    """)

    # Audit log table
    op.execute("DROP POLICY IF EXISTS audit_log_select_own ON audit_log")
    op.execute("""
        CREATE POLICY audit_log_select_own ON audit_log FOR SELECT
        USING (
            CASE
                WHEN NULLIF(current_setting('app.user_id', true), '') IS NULL THEN true
                ELSE user_id = current_setting('app.user_id', true)::uuid
            END
        );
    """)

    # Drop the function
    op.execute("DROP FUNCTION IF EXISTS get_app_user_id()")
