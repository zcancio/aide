Audit the codebase architecture against the documentation in docs/.

## Check each layer

### 1. File structure
Compare actual file structure against the structure defined in CLAUDE.md. Flag:
- Files in wrong directories (SQL outside repos/, business logic in routes/)
- Missing files that should exist per the architecture
- Extra files that don't fit the pattern

### 2. Dependency flow
Verify one-way dependency flow: routes → repos → db, routes → services.
- No circular imports
- models/ imports nothing from the app
- repos/ doesn't import from routes/
- routes/ doesn't import from db directly

### 3. Data access patterns
For every route handler, verify:
- Uses `Depends(get_current_user)`
- Calls a repo method (not raw SQL)
- Returns a Pydantic response model
- Is thin (< 15 lines, no business logic beyond gate checks)

For every repo method, verify:
- Uses `user_conn(user_id)` or `system_conn()` (with justification)
- All SQL parameterized
- Returns Pydantic models via `_row_to_model()`

### 4. Model consistency
For every entity (user, aide, conversation, etc.), verify three model shapes exist:
- Internal model (maps to DB)
- Request model (with validation)
- Response model (excludes internal fields)

### 5. Configuration
- All secrets via environment variables
- No hardcoded values that should be configurable

## Output
Summary table: area, status (✅/⚠️/❌), notes. Then a prioritized list of fixes needed.
