Implement a new API endpoint following the patterns in docs/aide_data_access.md.

## Steps (in this order)

### 1. Models (backend/models/)
- Create request model with validation constraints (max_length, pattern, etc.)
- Create internal model that maps 1:1 to the database row
- Create response model that excludes internal fields (user_id, r2_prefix, stripe IDs, etc.)
- Add `model_config = {"extra": "forbid"}` on request models
- Add `@classmethod from_model()` on response models

### 2. Migration (if new table)
- Hand-write Alembic migration. No autogenerate.
- Use `op.execute()` with static SQL.
- Add RLS policy: `USING (user_id = current_setting('app.user_id')::uuid)`
- Add check constraints where appropriate.

### 3. Repository (backend/repos/)
- Create `_row_to_model()` function that explicitly maps every column
- Every method takes `user_id` as first parameter
- Use `user_conn(user_id)` for all user-scoped operations
- All SQL uses `$1`, `$2` parameterized placeholders
- Use `RETURNING *` on INSERT/UPDATE
- Return Pydantic models, never raw rows or dicts

### 4. Route handler (backend/routes/)
- Use `Depends(get_current_user)` for authentication
- Call repo method, convert to response model, return
- No SQL. No business logic beyond simple checks (tier limits, ownership).
- Return proper HTTP status codes (201 for create, 204 for delete, 404 for not found)

### 5. Wire up
- Import and include router in backend/main.py

## Verification
After implementing, verify:
- [ ] Request model rejects extra fields
- [ ] Response model excludes internal fields
- [ ] All SQL is parameterized (no f-strings)
- [ ] RLS prevents cross-user access
- [ ] Route handler is thin (< 15 lines)
