"""Add telemetry table for LLM call and edit metrics.

Revision ID: 006
Revises: 005
Create Date: 2026-02-19
"""

from typing import Sequence, Union

from alembic import op


revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE telemetry (
            id              SERIAL PRIMARY KEY,
            ts              TIMESTAMPTZ DEFAULT NOW(),
            aide_id         UUID NOT NULL,
            user_id         UUID,
            event_type      TEXT NOT NULL,

            -- LLM call fields
            tier            TEXT,
            model           TEXT,
            prompt_ver      TEXT,
            ttfc_ms         INT,
            ttc_ms          INT,
            input_tokens    INT,
            output_tokens   INT,
            cache_read_tokens   INT,
            cache_write_tokens  INT,

            -- Reducer stats
            lines_emitted   INT,
            lines_accepted  INT,
            lines_rejected  INT,

            -- Escalation
            escalated       BOOLEAN DEFAULT FALSE,
            escalation_reason TEXT,

            -- Cost
            cost_usd        NUMERIC(10,6),

            -- Direct edit fields
            edit_latency_ms INT,

            -- Context
            message_id      UUID,
            error           TEXT,

            CONSTRAINT valid_event_type CHECK (
                event_type IN ('llm_call', 'direct_edit', 'undo', 'escalation')
            )
        );
    """)

    op.execute("CREATE INDEX idx_telemetry_aide_ts ON telemetry(aide_id, ts);")
    op.execute("CREATE INDEX idx_telemetry_tier_ts ON telemetry(tier, ts);")
    op.execute("CREATE INDEX idx_telemetry_user_ts ON telemetry(user_id, ts);")
    op.execute("CREATE INDEX idx_telemetry_event_type ON telemetry(event_type, ts);")

    # Telemetry is system-level — no RLS needed (users never query it directly)
    # Grant permissions so aide_app role can INSERT
    op.execute("GRANT ALL ON telemetry TO aide_app;")
    op.execute("GRANT USAGE, SELECT ON SEQUENCE telemetry_id_seq TO aide_app;")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS telemetry CASCADE;")
