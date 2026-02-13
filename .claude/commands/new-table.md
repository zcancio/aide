Add a new database table with proper RLS policies and the full data access layer.

## Steps

### 1. Alembic migration
Write the migration by hand in `alembic/versions/`. No autogenerate.

```python
def upgrade():
    op.execute("""
        CREATE TABLE {table_name} (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            -- your columns here --
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );

        -- RLS policy: users can only see their own rows
        ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;

        CREATE POLICY {table_name}_user_isolation ON {table_name}
            USING (user_id = current_setting('app.user_id')::uuid);

        -- Indexes
        CREATE INDEX idx_{table_name}_user_id ON {table_name}(user_id);
    """)
```

Every table with user data MUST have:
- `user_id UUID REFERENCES users(id) ON DELETE CASCADE`
- RLS enabled
- Policy using `current_setting('app.user_id')`
- Index on user_id

### 2. Pydantic models (backend/models/)
- Internal model: maps 1:1 to DB row
- Request model: what client sends, with validation, `extra = "forbid"`
- Response model: what API returns, excludes internal fields

### 3. Repository (backend/repos/)
- `_row_to_model()` function with explicit field mapping
- CRUD methods using `user_conn(user_id)`
- All SQL parameterized

### 4. Tests
- Test CRUD operations
- Test RLS: user A cannot access user B's rows (this is critical)

```python
async def test_rls_prevents_cross_user_access():
    # Create as user A
    item = await repo.create(user_a_id, ...)
    # Try to access as user B
    result = await repo.get(user_b_id, item.id)
    assert result is None  # RLS blocks access
```

### 5. Verify
- [ ] RLS policy exists and uses correct setting
- [ ] Migration is hand-written SQL
- [ ] All queries parameterized
- [ ] Cross-user test exists and passes
- [ ] Cascade delete works (delete user → deletes their rows)
