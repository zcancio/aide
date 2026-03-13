"""backfill_user_turn_counts

Backfill users.turn_count from aide_turn_telemetry records.

Fixes issue where turn counts show 0 for users who have existing turns
recorded in telemetry (before increment_turns was called in TurnRecorder.finish).

Revision ID: 55f1f13d5aa9
Revises: 24388223f9bc
Create Date: 2026-03-12
"""

from alembic import op

revision: str = "55f1f13d5aa9"
down_revision: str | None = "24388223f9bc"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Update users.turn_count to match actual count from aide_turn_telemetry
    op.execute("""
        UPDATE users u
        SET turn_count = (
            SELECT COUNT(*)
            FROM aide_turn_telemetry t
            WHERE t.user_id = u.id
        )
        WHERE EXISTS (
            SELECT 1 FROM aide_turn_telemetry t WHERE t.user_id = u.id
        )
    """)


def downgrade() -> None:
    # No downgrade - we don't want to reset turn counts
    # as new turns may have been recorded since the backfill
    pass
