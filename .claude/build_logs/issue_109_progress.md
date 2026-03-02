# Issue #109: Add aide_turn_telemetry table migration

## Summary
Created database migration to add `aide_turn_telemetry` table for flight recorder. This is part of the larger consolidation effort (#104) to unify flight recorder and telemetry services.

## Changes Made

### 1. Migration File: `alembic/versions/008_add_aide_turn_telemetry.py`
- **Revision**: 008
- **Revises**: 007
- **Purpose**: Store turn-level telemetry for flight recorder in unified format

#### Table Schema
```sql
CREATE TABLE aide_turn_telemetry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aide_id UUID NOT NULL REFERENCES aides(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    turn_num INT NOT NULL,
    tier TEXT NOT NULL,
    model TEXT NOT NULL,
    message TEXT NOT NULL,
    tool_calls JSONB NOT NULL DEFAULT '[]',
    text_blocks JSONB NOT NULL DEFAULT '[]',
    system_prompt TEXT,
    usage JSONB NOT NULL,
    ttfc_ms INT NOT NULL,
    ttc_ms INT NOT NULL,
    validation JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT unique_aide_turn UNIQUE (aide_id, turn_num)
);
```

#### Indexes
- `idx_turn_telemetry_aide` on `aide_id` - for querying all turns of an aide
- `idx_turn_telemetry_user` on `user_id` - for user-scoped queries

#### Row-Level Security (RLS)
- Enabled RLS on table
- Policy: `aide_turn_telemetry_user` allows users to see only their own data
- Pattern matches existing RLS policies from migration 007
- Uses `CASE` expression to handle NULL `app.user_id` setting

#### Permissions
- Granted `SELECT, INSERT` to `aide_app` role
- No UPDATE/DELETE permissions (append-only telemetry)

## Validation Performed

### 1. Migration Tests
```bash
✓ alembic upgrade head     # Applied migration 008
✓ alembic downgrade -1     # Rolled back to 007
✓ alembic upgrade head     # Re-applied migration 008
```

All migration operations completed successfully.

### 2. Code Quality
```bash
✓ ruff check backend/      # All checks passed
✓ ruff format --check backend/  # 80 files already formatted
```

### 3. Backend Tests
```bash
✓ 26 RLS and telemetry tests passed
  - 6 aide RLS tests
  - 3 conversation RLS tests
  - 2 DB RLS tests
  - 2 route RLS tests
  - 2 signal mapping RLS tests
  - 11 telemetry tests (including new TurnTelemetry model tests)
```

## Design Notes

### Matches TurnTelemetry Model
The table schema directly maps to the `TurnTelemetry` Pydantic model from `backend/models/telemetry.py`:
- `turn` → `turn_num` (INT)
- `tier`, `model`, `message` → TEXT fields
- `tool_calls`, `text_blocks`, `validation` → JSONB fields
- `usage` → JSONB (stores TokenUsage model)
- `ttfc_ms`, `ttc_ms` → INT fields
- `system_prompt` → TEXT (nullable)

### Unique Constraint
The `CONSTRAINT unique_aide_turn UNIQUE (aide_id, turn_num)` ensures:
- Each turn number is unique per aide
- No duplicate turn data
- Prevents race conditions on concurrent writes

### Foreign Key Cascade
`ON DELETE CASCADE` on `aide_id` ensures:
- When an aide is deleted, all its turn telemetry is automatically cleaned up
- No orphaned telemetry records

### Append-Only Design
- Only granted `SELECT, INSERT` permissions
- No UPDATE or DELETE
- Telemetry is immutable once recorded
- Matches flight recorder design pattern

## Dependencies

### Completed
- ✓ #108: TurnTelemetry models added to `backend/models/telemetry.py`

### Blocked By This
Next issues can now proceed:
- #110: Add TurnTelemetryRepo for data access layer
- Later: Update streaming pipeline to record turn telemetry

## Acceptance Criteria Status

- [x] Migration file created
- [x] `alembic upgrade head` succeeds
- [x] Table has RLS policy
- [x] Downgrade works cleanly
- [x] Lint checks pass
- [x] Tests pass with non-superuser (aide_app) to verify RLS

## Notes

### RLS Policy Pattern
Used the newer RLS pattern from migration 007 that handles NULL `app.user_id`:
```sql
CASE
    WHEN NULLIF(current_setting('app.user_id', true), '') IS NULL THEN true
    ELSE user_id = current_setting('app.user_id', true)::uuid
END
```

This is more robust than the older pattern in migration 005.

### No System-Level Access
Unlike the original `telemetry` table (migration 006), this table has RLS enabled. This is correct because:
- Turn telemetry is user-scoped (each aide belongs to a user)
- Users may want to query their own turn data via API
- RLS protects against cross-user data leaks

### JSONB Usage
Chose JSONB over separate columns for:
- `tool_calls`: Variable structure, can be empty array
- `text_blocks`: Mixed dict/string types
- `usage`: Nested TokenUsage structure
- `validation`: Optional, variable structure

This matches the existing telemetry table pattern and provides flexibility for schema evolution.

## Build Time
- Migration creation: ~5 minutes
- Testing: ~2 minutes
- Documentation: ~3 minutes
- **Total**: ~10 minutes
