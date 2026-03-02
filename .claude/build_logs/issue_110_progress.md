# Build Log: Issue #110 - Add telemetry repo methods for turn storage

**Issue:** (3 of 8) Add telemetry repo methods for turn storage
**Branch:** claude/issue-110
**Date:** 2026-03-02

## Summary

Added repository methods for inserting and querying turn telemetry records from the `aide_turn_telemetry` table with proper RLS enforcement.

## Changes Made

### 1. Updated `backend/repos/telemetry_repo.py`

Added imports:
- `json` module for JSON serialization
- `user_conn` from backend.db for RLS-scoped queries
- `TokenUsage, TurnTelemetry` from backend.models.telemetry

Added two new repository methods:

#### `insert_turn(user_id, aide_id, turn)`
- Inserts a turn telemetry record into `aide_turn_telemetry` table
- Uses `user_conn(user_id)` for RLS enforcement
- Serializes JSON fields (tool_calls, text_blocks, usage, validation)
- Returns the UUID of the created row

#### `get_turns_for_aide(user_id, aide_id)`
- Retrieves all turns for an aide, ordered by turn number
- Uses `user_conn(user_id)` for RLS enforcement
- Deserializes JSON fields back to Pydantic models
- Returns a list of `TurnTelemetry` objects

### 2. Created `backend/tests/test_telemetry_repo.py`

Added three comprehensive tests:

#### `test_insert_turn_creates_row`
- Verifies that `insert_turn()` creates a row and returns a valid UUID
- Confirms all fields are stored correctly in the database
- Tests with tool_calls and text_blocks

#### `test_get_turns_returns_chronological`
- Inserts 3 turns out of order (3, 1, 2)
- Verifies they are retrieved in chronological order (1, 2, 3)
- Confirms ordering by turn_num works correctly

#### `test_get_turns_respects_rls`
- Creates a turn for one user
- Attempts to retrieve it as a different user
- Verifies RLS policy blocks access (empty list returned)
- Confirms original user can still access their own data

## Testing

All tests pass:
```bash
$ python3 -m pytest backend/tests/test_telemetry_repo.py -v
============================= test session starts ==============================
backend/tests/test_telemetry_repo.py::test_insert_turn_creates_row PASSED [ 33%]
backend/tests/test_telemetry_repo.py::test_get_turns_returns_chronological PASSED [ 66%]
backend/tests/test_telemetry_repo.py::test_get_turns_respects_rls PASSED [100%]

============================== 3 passed in 0.14s ===============================
```

## Linting

All checks pass:
```bash
$ ruff check backend/ && ruff format --check backend/
All checks passed!
81 files already formatted
```

## Database Schema

The implementation uses the `aide_turn_telemetry` table created in migration `008_add_aide_turn_telemetry.py`:

- Columns: id, aide_id, user_id, turn_num, tier, model, message, tool_calls, text_blocks, system_prompt, usage, ttfc_ms, ttc_ms, validation, created_at
- RLS policy: Enforces user_id matches current_setting('app.user_id')
- Indexes: On aide_id and user_id for efficient queries
- Grants: aide_app role has SELECT, INSERT permissions

## Acceptance Criteria

- [x] `insert_turn()` added to telemetry_repo.py
- [x] `get_turns_for_aide()` added to telemetry_repo.py
- [x] Tests pass: `pytest backend/tests/test_telemetry_repo.py -v`
- [x] RLS enforced on queries
- [x] Lint checks pass
- [x] Format checks pass

## Notes

- Used `user_conn()` throughout for RLS enforcement (not `system_conn()`)
- JSON fields are properly serialized/deserialized using `json.dumps()` and `json.loads()`
- TokenUsage is reconstructed from JSON using `TokenUsage(**json.loads(...))`
- Tests create aide records with correct schema (title, r2_prefix) from migration 001
- All cleanup is done in tests to avoid leaving test data in the database
