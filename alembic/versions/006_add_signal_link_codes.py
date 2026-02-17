"""add_signal_link_codes

Revision ID: 006
Revises: ccee0808c23a
Create Date: 2026-02-17
"""

from typing import Sequence, Union

from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create signal_link_codes table
    # Stores temporary 6-char codes used to link a Signal phone number to an aide.
    # Codes expire after 15 minutes and are single-use.
    op.execute("""
        CREATE TABLE signal_link_codes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            code TEXT NOT NULL UNIQUE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            aide_id UUID NOT NULL REFERENCES aides(id) ON DELETE CASCADE,
            expires_at TIMESTAMPTZ NOT NULL,
            used BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    # Indexes for fast lookups
    op.execute("CREATE INDEX idx_signal_link_codes_code ON signal_link_codes(code);")
    op.execute("CREATE INDEX idx_signal_link_codes_user ON signal_link_codes(user_id);")
    op.execute("CREATE INDEX idx_signal_link_codes_expires ON signal_link_codes(expires_at);")

    # Enable RLS
    op.execute("ALTER TABLE signal_link_codes ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE signal_link_codes FORCE ROW LEVEL SECURITY;")

    # RLS policy: users can only see their own link codes
    # Uses get_app_user_id() from migration 005 to avoid UUID cast issues
    op.execute("""
        CREATE POLICY signal_link_codes_all_own
        ON signal_link_codes
        FOR ALL
        USING (get_app_user_id() IS NULL OR user_id = get_app_user_id());
    """)

    # Grant permissions to aide_app role
    op.execute("GRANT ALL ON signal_link_codes TO aide_app;")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS signal_link_codes CASCADE;")
