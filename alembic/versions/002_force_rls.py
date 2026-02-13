"""Add FORCE ROW LEVEL SECURITY to all RLS-enabled tables.

This ensures RLS policies apply even when using superuser roles (like postgres).

Revision ID: 002
Revises: 001
Create Date: 2026-02-13
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    # Force RLS on all tables that have RLS enabled
    # This makes policies apply even to table owners and superusers
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aides FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE conversations FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE published_versions FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_log FORCE ROW LEVEL SECURITY")


def downgrade():
    # Remove FORCE RLS (RLS still enabled, just not forced for owners)
    op.execute("ALTER TABLE users NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aides NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE conversations NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE published_versions NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_log NO FORCE ROW LEVEL SECURITY")
