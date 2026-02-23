-- Create aide_app role for runtime (restricted permissions)
CREATE ROLE aide_app WITH LOGIN PASSWORD 'test';

-- Grant connect
GRANT CONNECT ON DATABASE aide_test TO aide_app;

-- Grant schema usage (will be granted on tables as they're created by migrations)
GRANT USAGE ON SCHEMA public TO aide_app;

-- Default privileges for future tables created by aide (owner)
ALTER DEFAULT PRIVILEGES FOR ROLE aide IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO aide_app;

ALTER DEFAULT PRIVILEGES FOR ROLE aide IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO aide_app;
