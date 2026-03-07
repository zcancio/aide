"""add admin breakglass support

Revision ID: 24388223f9bc
Revises: 37075647b036
Create Date: 2026-03-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '24388223f9bc'
down_revision: Union[str, None] = '37075647b036'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_admin column to users table
    op.execute("""
        ALTER TABLE users
        ADD COLUMN is_admin BOOLEAN DEFAULT false NOT NULL;
    """)

    # Create admin_audit_log table for tracking admin breakglass access
    op.execute("""
        CREATE TABLE admin_audit_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            admin_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            action TEXT NOT NULL,
            target_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            target_aide_id UUID REFERENCES aides(id) ON DELETE SET NULL,
            reason TEXT NOT NULL,
            ip_address TEXT,
            created_at TIMESTAMPTZ DEFAULT now()
        );
    """)

    # Grant access to aide_app role
    op.execute("GRANT SELECT, INSERT ON admin_audit_log TO aide_app;")

    # Create indexes for efficient querying
    op.execute("""
        CREATE INDEX idx_admin_audit_log_admin_user ON admin_audit_log(admin_user_id);
    """)

    op.execute("""
        CREATE INDEX idx_admin_audit_log_target_user ON admin_audit_log(target_user_id);
    """)

    op.execute("""
        CREATE INDEX idx_admin_audit_log_created ON admin_audit_log(created_at);
    """)

    # No RLS on admin_audit_log - authorization is handled at the application layer
    # via get_current_admin() dependency and manual is_admin checks in the repo.
    # The table is append-only by design (no UPDATE/DELETE grants to aide_app).


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS admin_audit_log CASCADE;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_admin;")
