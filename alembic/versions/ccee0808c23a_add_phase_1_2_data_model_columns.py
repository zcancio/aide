"""add_phase_1_2_data_model_columns

Revision ID: ccee0808c23a
Revises: e58cbd86aa04
Create Date: 2026-02-16 11:27:14.067064
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ccee0808c23a'
down_revision: Union[str, None] = 'e58cbd86aa04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add state and event_log columns to aides table
    # These are nullable because existing rows won't have these values initially
    op.execute("""
        ALTER TABLE aides
        ADD COLUMN state JSONB DEFAULT '{}'::jsonb,
        ADD COLUMN event_log JSONB DEFAULT '[]'::jsonb;
    """)

    # Add channel column to conversations table
    # Default to 'web' for existing conversations
    op.execute("""
        ALTER TABLE conversations
        ADD COLUMN channel TEXT DEFAULT 'web' CHECK (channel IN ('web', 'signal'));
    """)

    # Create signal_mappings table
    # Maps Signal phone numbers to aides for the Signal ear integration
    op.execute("""
        CREATE TABLE signal_mappings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            phone_number TEXT NOT NULL,
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            aide_id UUID REFERENCES aides(id) ON DELETE CASCADE,
            conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(phone_number)
        );
    """)

    # Create indexes for signal_mappings lookups
    op.execute("""
        CREATE INDEX idx_signal_mappings_phone ON signal_mappings(phone_number);
    """)
    op.execute("""
        CREATE INDEX idx_signal_mappings_user ON signal_mappings(user_id);
    """)
    op.execute("""
        CREATE INDEX idx_signal_mappings_aide ON signal_mappings(aide_id);
    """)

    # Enable RLS on signal_mappings
    op.execute("""
        ALTER TABLE signal_mappings ENABLE ROW LEVEL SECURITY;
        ALTER TABLE signal_mappings FORCE ROW LEVEL SECURITY;
    """)

    # RLS policy: users can only see their own signal mappings
    op.execute("""
        CREATE POLICY signal_mappings_all_own
        ON signal_mappings
        FOR ALL
        USING (
            CASE
                WHEN NULLIF(current_setting('app.user_id', true), '') IS NULL THEN true
                ELSE user_id = current_setting('app.user_id', true)::uuid
            END
        );
    """)

    # Grant permissions to aide_app role
    op.execute("GRANT ALL ON signal_mappings TO aide_app;")


def downgrade() -> None:
    # Drop signal_mappings table and its policies
    op.execute("DROP TABLE IF EXISTS signal_mappings CASCADE;")

    # Remove channel column from conversations
    op.execute("ALTER TABLE conversations DROP COLUMN IF EXISTS channel;")

    # Remove state and event_log columns from aides
    op.execute("ALTER TABLE aides DROP COLUMN IF EXISTS event_log;")
    op.execute("ALTER TABLE aides DROP COLUMN IF EXISTS state;")
