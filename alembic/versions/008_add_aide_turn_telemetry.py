"""Add aide_turn_telemetry table for flight recorder.

Revision ID: 008
Revises: 007
Create Date: 2026-03-02

"""
from typing import Sequence, Union

from alembic import op


revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE aide_turn_telemetry (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            aide_id UUID NOT NULL REFERENCES aides(id) ON DELETE CASCADE,
            user_id UUID NOT NULL,
            turn_num INT NOT NULL,
            tier TEXT NOT NULL,
            model TEXT NOT NULL,
            message TEXT NOT NULL,
            tool_calls JSONB NOT NULL DEFAULT '[]',
            text_blocks JSONB NOT NULL DEFAULT '[]',
            system_prompt TEXT,
            usage JSONB NOT NULL,
            ttfc_ms INT NOT NULL,
            ttc_ms INT NOT NULL,
            validation JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT unique_aide_turn UNIQUE (aide_id, turn_num)
        );
    """)

    op.execute("CREATE INDEX idx_turn_telemetry_aide ON aide_turn_telemetry(aide_id);")
    op.execute("CREATE INDEX idx_turn_telemetry_user ON aide_turn_telemetry(user_id);")

    op.execute("ALTER TABLE aide_turn_telemetry ENABLE ROW LEVEL SECURITY;")

    # RLS policy matching the pattern from 007
    op.execute("""
        CREATE POLICY aide_turn_telemetry_user ON aide_turn_telemetry
            USING (
                CASE
                    WHEN NULLIF(current_setting('app.user_id', true), '') IS NULL THEN true
                    ELSE user_id = current_setting('app.user_id', true)::uuid
                END
            );
    """)

    op.execute("GRANT SELECT, INSERT ON aide_turn_telemetry TO aide_app;")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aide_turn_telemetry CASCADE;")
