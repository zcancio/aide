"""Add INSERT policies for system operations.

System operations (user creation, audit logging) need to be able to insert
without having app.user_id set. This adds permissive INSERT policies.

Revision ID: 003
Revises: 002
Create Date: 2026-02-13
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    # Users table: allow INSERT for new user creation (signup)
    # The user_id won't be set yet during creation
    op.execute("""
        CREATE POLICY users_insert_new
        ON users
        FOR INSERT
        WITH CHECK (true);
    """)

    # Audit log: allow INSERT for system logging
    op.execute("""
        CREATE POLICY audit_log_insert_system
        ON audit_log
        FOR INSERT
        WITH CHECK (true);
    """)


def downgrade():
    op.execute("DROP POLICY IF EXISTS users_insert_new ON users")
    op.execute("DROP POLICY IF EXISTS audit_log_insert_system ON audit_log")
