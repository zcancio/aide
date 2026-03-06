"""backfill_meta_title_from_page_props

Backfill meta.title from entities.page.props.title for existing aides.

Fixes issue where dashboard shows "Untitled" even when page has a title.

Revision ID: 37075647b036
Revises: 008
Create Date: 2026-03-06 09:54:52.016857
"""

from alembic import op

revision: str = "37075647b036"
down_revision: str | None = "008"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Backfill both meta.title in state AND the aides.title column
    # from entities.page.props.title where:
    # - state exists and is not null
    # - title is currently null/empty or "Untitled"
    # - entities.page.props.title exists and is not null/empty
    op.execute("""
        UPDATE aides
        SET
            state = jsonb_set(
                state,
                '{meta,title}',
                state->'entities'->'page'->'props'->'title'
            ),
            title = state->'entities'->'page'->'props'->>'title'
        WHERE state IS NOT NULL
          AND (title IS NULL OR title = '' OR title = 'Untitled')
          AND state->'entities'->'page'->'props'->>'title' IS NOT NULL
          AND state->'entities'->'page'->'props'->>'title' != ''
    """)


def downgrade() -> None:
    # No downgrade - we don't want to remove titles that were backfilled
    # and may have been manually edited since
    pass
