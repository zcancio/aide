"""add cli auth tables

Revision ID: 007
Revises: 006
Create Date: 2026-02-22

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    # Create cli_auth_requests table
    op.execute("""
        CREATE TABLE cli_auth_requests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            device_code TEXT NOT NULL UNIQUE,
            user_id UUID REFERENCES users(id),
            status TEXT NOT NULL DEFAULT 'pending',
            api_token TEXT,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    # Create api_tokens table
    op.execute("""
        CREATE TABLE api_tokens (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            token_hash TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL DEFAULT 'cli',
            scope TEXT NOT NULL DEFAULT 'cli',
            last_used_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ NOT NULL,
            revoked BOOLEAN DEFAULT false,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    # Enable RLS on api_tokens
    op.execute("ALTER TABLE api_tokens ENABLE ROW LEVEL SECURITY")

    # RLS policy: users can only see/revoke their own tokens
    op.execute("""
        CREATE POLICY api_tokens_user_policy ON api_tokens
            USING (user_id = current_setting('app.current_user_id')::uuid)
    """)

    # Grant permissions to aide_app
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON cli_auth_requests TO aide_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON api_tokens TO aide_app")


def downgrade():
    op.execute("DROP TABLE IF EXISTS api_tokens CASCADE")
    op.execute("DROP TABLE IF EXISTS cli_auth_requests CASCADE")
