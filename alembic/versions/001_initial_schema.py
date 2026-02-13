"""Initial schema with all tables and RLS policies.

Revision ID: 001
Revises:
Create Date: 2026-02-13
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create users table
    op.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            tier TEXT DEFAULT 'free' CHECK (tier IN ('free', 'pro')),
            stripe_customer_id TEXT,
            stripe_sub_id TEXT,
            turn_count INTEGER DEFAULT 0,
            turn_week_start TIMESTAMPTZ DEFAULT now(),
            created_at TIMESTAMPTZ DEFAULT now()
        );
    """)

    # RLS policy for users table
    op.execute("""
        ALTER TABLE users ENABLE ROW LEVEL SECURITY;
    """)

    op.execute("""
        CREATE POLICY users_select_own
        ON users
        FOR SELECT
        USING (id = current_setting('app.user_id', true)::uuid);
    """)

    op.execute("""
        CREATE POLICY users_update_own
        ON users
        FOR UPDATE
        USING (id = current_setting('app.user_id', true)::uuid);
    """)

    # Create magic_links table
    op.execute("""
        CREATE TABLE magic_links (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            used BOOLEAN DEFAULT false,
            created_at TIMESTAMPTZ DEFAULT now()
        );
    """)

    op.execute("""
        CREATE INDEX idx_magic_links_token ON magic_links(token);
    """)

    op.execute("""
        CREATE INDEX idx_magic_links_email ON magic_links(email);
    """)

    # No RLS on magic_links - system table, accessed via system_conn only

    # Create aides table
    op.execute("""
        CREATE TABLE aides (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            title TEXT DEFAULT 'Untitled',
            slug TEXT UNIQUE,
            status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
            r2_prefix TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
    """)

    op.execute("""
        CREATE INDEX idx_aides_user ON aides(user_id);
    """)

    op.execute("""
        CREATE INDEX idx_aides_slug ON aides(slug);
    """)

    # RLS policy for aides table
    op.execute("""
        ALTER TABLE aides ENABLE ROW LEVEL SECURITY;
    """)

    op.execute("""
        CREATE POLICY aides_all_own
        ON aides
        FOR ALL
        USING (user_id = current_setting('app.user_id', true)::uuid);
    """)

    # Create conversations table
    op.execute("""
        CREATE TABLE conversations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            aide_id UUID REFERENCES aides(id) ON DELETE CASCADE,
            messages JSONB DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
    """)

    op.execute("""
        CREATE INDEX idx_conversations_aide ON conversations(aide_id);
    """)

    # RLS policy for conversations table
    # Conversations belong to users via aides, so we need to check the aide's user_id
    op.execute("""
        ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
    """)

    op.execute("""
        CREATE POLICY conversations_all_own
        ON conversations
        FOR ALL
        USING (
            aide_id IN (
                SELECT id FROM aides WHERE user_id = current_setting('app.user_id', true)::uuid
            )
        );
    """)

    # Create published_versions table
    op.execute("""
        CREATE TABLE published_versions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            aide_id UUID REFERENCES aides(id) ON DELETE CASCADE,
            version INTEGER NOT NULL,
            r2_key TEXT NOT NULL,
            notes TEXT,
            size_bytes INTEGER,
            published_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(aide_id, version)
        );
    """)

    op.execute("""
        CREATE INDEX idx_versions_aide ON published_versions(aide_id);
    """)

    # RLS policy for published_versions table
    op.execute("""
        ALTER TABLE published_versions ENABLE ROW LEVEL SECURITY;
    """)

    op.execute("""
        CREATE POLICY published_versions_all_own
        ON published_versions
        FOR ALL
        USING (
            aide_id IN (
                SELECT id FROM aides WHERE user_id = current_setting('app.user_id', true)::uuid
            )
        );
    """)

    # Create audit_log table (append-only)
    op.execute("""
        CREATE TABLE audit_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id UUID,
            details JSONB,
            ip_address TEXT,
            created_at TIMESTAMPTZ DEFAULT now()
        );
    """)

    op.execute("""
        CREATE INDEX idx_audit_log_user ON audit_log(user_id);
    """)

    op.execute("""
        CREATE INDEX idx_audit_log_created ON audit_log(created_at);
    """)

    # RLS policy for audit_log (select only, insert via system_conn)
    op.execute("""
        ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
    """)

    op.execute("""
        CREATE POLICY audit_log_select_own
        ON audit_log
        FOR SELECT
        USING (user_id = current_setting('app.user_id', true)::uuid);
    """)

    # Prevent updates and deletes on audit_log
    op.execute("""
        CREATE POLICY audit_log_no_update
        ON audit_log
        FOR UPDATE
        USING (false);
    """)

    op.execute("""
        CREATE POLICY audit_log_no_delete
        ON audit_log
        FOR DELETE
        USING (false);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS audit_log CASCADE")
    op.execute("DROP TABLE IF EXISTS published_versions CASCADE")
    op.execute("DROP TABLE IF EXISTS conversations CASCADE")
    op.execute("DROP TABLE IF EXISTS aides CASCADE")
    op.execute("DROP TABLE IF EXISTS magic_links CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
