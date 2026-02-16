"""add aide_files table for kernel storage

Revision ID: e58cbd86aa04
Revises: 004
Create Date: 2026-02-16 10:26:00.906317
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e58cbd86aa04'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create aide_files table for kernel storage
    # Stores the full HTML content of each aide for the kernel layer
    # This is separate from the aides table which is for the app layer
    op.execute("""
        CREATE TABLE aide_files (
            aide_id UUID PRIMARY KEY,
            html TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
    """)

    # Create index on updated_at for cleanup queries
    op.execute("""
        CREATE INDEX idx_aide_files_updated ON aide_files(updated_at);
    """)

    # No RLS on aide_files - this is a kernel-level table
    # The kernel doesn't run with user context, it just stores/retrieves HTML


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aide_files CASCADE;")
