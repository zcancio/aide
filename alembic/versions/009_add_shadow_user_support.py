"""add_shadow_user_support

Add support for shadow users (anonymous users tracked by browser fingerprint).
Shadow users have nullable email, fingerprint_id, is_shadow flag, and signed_up_at timestamp.

Revision ID: 009
Revises: 55f1f13d5aa9
Create Date: 2026-03-12
"""

from alembic import op

revision: str = "009"
down_revision: str | None = "55f1f13d5aa9"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Make email nullable for shadow users
    op.execute("""
        ALTER TABLE users ALTER COLUMN email DROP NOT NULL;
    """)

    # Add shadow user columns
    op.execute("""
        ALTER TABLE users
        ADD COLUMN fingerprint_id TEXT,
        ADD COLUMN is_shadow BOOLEAN DEFAULT false,
        ADD COLUMN signed_up_at TIMESTAMPTZ;
    """)

    # Backfill existing users with signed_up_at = created_at
    op.execute("""
        UPDATE users
        SET signed_up_at = created_at
        WHERE email IS NOT NULL;
    """)

    # Add unique constraint on fingerprint_id
    op.execute("""
        ALTER TABLE users
        ADD CONSTRAINT users_fingerprint_id_unique UNIQUE (fingerprint_id);
    """)

    # Index for fingerprint lookup
    op.execute("""
        CREATE INDEX idx_users_fingerprint
        ON users(fingerprint_id)
        WHERE fingerprint_id IS NOT NULL;
    """)

    # Index for cleanup job (finding old shadow users)
    op.execute("""
        CREATE INDEX idx_users_shadow_cleanup
        ON users(created_at)
        WHERE is_shadow = true;
    """)


def downgrade() -> None:
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_users_shadow_cleanup;")
    op.execute("DROP INDEX IF EXISTS idx_users_fingerprint;")

    # Drop unique constraint
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_fingerprint_id_unique;")

    # Drop columns
    op.execute("""
        ALTER TABLE users
        DROP COLUMN IF EXISTS signed_up_at,
        DROP COLUMN IF EXISTS is_shadow,
        DROP COLUMN IF EXISTS fingerprint_id;
    """)

    # Make email NOT NULL again
    op.execute("""
        ALTER TABLE users ALTER COLUMN email SET NOT NULL;
    """)
