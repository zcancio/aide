Run pre-commit quality and security checks on the current changes.

## Checks (run in this order)

### 1. Lint & format
```bash
ruff check backend/
ruff format --check backend/
```
Fix any issues found.

### 2. SQL safety scan
Search for dangerous SQL patterns:
```bash
grep -rn "f\".*SELECT\|f\".*INSERT\|f\".*UPDATE\|f\".*DELETE\|\.format.*SELECT\|\.format.*INSERT" backend/
```
Any matches are **critical bugs**. All SQL must use asyncpg $1, $2 parameterized placeholders.

### 3. SQL location check
Verify SQL only exists in repos/ layer:
```bash
grep -rn "SELECT\|INSERT\|UPDATE\|DELETE\|CREATE TABLE" backend/ --include="*.py" | grep -v "repos/" | grep -v "alembic/" | grep -v "__pycache__" | grep -v ".pyc"
```
Any matches outside repos/ and alembic/ violate the data access layer architecture.

### 4. Secrets scan
```bash
grep -rn "sk_live\|sk_test\|re_\|RESEND_API_KEY\|JWT_SECRET\|password\s*=" backend/ --include="*.py" | grep -v ".env" | grep -v "os.environ\|getenv\|config\["
```
Flag any hardcoded secrets or API keys.

### 5. Google dependency check
```bash
grep -rn "google\|googleapis\|oauth\|GOOGLE_" backend/ --include="*.py" -i
```
AIde has zero Google dependencies. Any matches need removal.

### 6. Auth pattern check
Verify all route handlers use authentication:
```bash
grep -rn "def.*async.*(" backend/routes/ --include="*.py" | grep -v "get_current_user\|Depends\|__init__\|#"
```
Every route handler should have `Depends(get_current_user)` unless it's a public endpoint (magic link send/verify, published page serving, health check).

### 7. Type check (if mypy is installed)
```bash
mypy backend/ --ignore-missing-imports
```

## Output
Report results for each check. If all pass, confirm ready to commit. If any fail, list the exact files and lines that need fixing.
