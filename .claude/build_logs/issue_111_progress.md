# Build Log: Issue #111 - Add GET /api/aides/{id}/telemetry endpoint

**Issue**: (5 of 8) Add GET /api/aides/{id}/telemetry endpoint
**Date**: 2026-03-02
**Status**: ✅ COMPLETED

## Summary

Implemented a new API endpoint that returns telemetry data for an aide in eval-compatible format. The endpoint supports the flight recorder UI for replaying conversations.

## Changes Made

### 1. Backend Service Layer (`backend/services/telemetry.py`)

**Added function**: `get_aide_telemetry(user_id: UUID, aide_id: UUID) -> AideTelemetry | None`

- Fetches aide data using `AideRepo().get(user_id, aide_id)` with RLS enforcement
- Returns `None` if aide not found or user doesn't have access
- Retrieves turn telemetry using `telemetry_repo.get_turns_for_aide(user_id, aide_id)`
- Constructs `AideTelemetry` response with:
  - `aide_id`: string representation of UUID
  - `name`: aide title
  - `timestamp`: ISO 8601 timestamp (UTC)
  - `turns`: list of `TurnTelemetry` objects
  - `final_snapshot`: aide's current state (from `aide.state`)

**Imports added**:
- `from datetime import UTC, datetime`
- `from backend.models.telemetry import AideTelemetry`
- `from backend.repos.aide_repo import AideRepo`

### 2. API Routes Layer (`backend/routes/telemetry.py`) - NEW FILE

**Created new router**: `/api/aides` prefix with `telemetry` tag

**Endpoint**: `GET /api/aides/{aide_id}/telemetry`
- Requires authentication via `Depends(get_current_user)`
- Returns `AideTelemetry` model
- Returns 404 if aide not found or user doesn't have access
- Used by flight recorder UI to replay conversations

### 3. Main Application (`backend/main.py`)

**Changes**:
- Added import: `from backend.routes import telemetry as telemetry_routes`
- Registered router: `app.include_router(telemetry_routes.router)`
- Router registered between flight_recorder_routes and ws_routes

### 4. Tests (`backend/tests/test_telemetry_api.py`) - NEW FILE

**Created comprehensive test suite** with 7 test cases:

1. `test_get_telemetry_returns_404_for_missing_aide` - Returns 404 for non-existent aide
2. `test_get_telemetry_requires_auth` - Returns 401 without authentication
3. `test_get_telemetry_returns_aide_telemetry` - Returns 200 with complete telemetry data
4. `test_get_telemetry_respects_rls` - RLS enforcement (404 for other users)
5. `test_telemetry_matches_eval_format` - Validates response structure matches eval golden format
6. `test_telemetry_includes_final_snapshot` - Verifies final_snapshot contains aide state
7. `test_telemetry_turns_ordered_chronologically` - Ensures turns are ordered by turn number

**Test fixture**: `test_aide_with_turns`
- Creates aide with sample state (`{"entities": {"e1": {"_schema": "Task", "name": "Buy milk"}}}`)
- Inserts 2 turn telemetry records with realistic data
- Proper cleanup in teardown

**All tests**: ✅ PASSED (7/7)

## Verification

### Linting
```bash
ruff check backend/     # ✅ All checks passed!
ruff format --check backend/  # ✅ 84 files already formatted
```

### Tests
```bash
python3 -m pytest backend/tests/test_telemetry_api.py -v
# ✅ 7 passed, 6 warnings in 0.21s
```

## API Usage Example

```bash
# Get telemetry for an aide
curl -X GET "http://localhost:8000/api/aides/{aide_id}/telemetry" \
  -H "Cookie: session={jwt_token}"
```

**Response**:
```json
{
  "aide_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "My Aide",
  "timestamp": "2026-03-02T12:34:56.789Z",
  "turns": [
    {
      "turn": 1,
      "tier": "L3",
      "model": "sonnet",
      "message": "Add task",
      "tool_calls": [{"name": "entity.create", "input": {"id": "e1"}}],
      "text_blocks": ["Created task"],
      "usage": {
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read": 0,
        "cache_creation": 0
      },
      "ttfc_ms": 200,
      "ttc_ms": 1000
    }
  ],
  "final_snapshot": {
    "entities": {
      "e1": {"_schema": "Task", "name": "Buy milk"}
    }
  }
}
```

## RLS Security

- Endpoint uses `user_conn(user_id)` via `AideRepo().get()`
- RLS policies enforce user can only access their own aides
- Cross-user access returns 404 (not 403) to avoid information leakage
- Verified with `test_get_telemetry_respects_rls` test

## Design Notes

### Eval-Compatible Format
The response format matches the eval golden files structure:
- Top-level fields: `aide_id`, `name`, `timestamp`, `turns`, `final_snapshot`
- Optional fields: `scenario_id`, `pattern` (not currently used)
- Turn structure matches `TurnTelemetry` model from #108

### Service Layer Pattern
Followed existing patterns:
- Business logic in `backend/services/telemetry.py`
- Thin route handler in `backend/routes/telemetry.py`
- No SQL in routes or services (delegated to repos)
- RLS enforcement via user-scoped connections

### Separation from Flight Recorder
This endpoint is **separate** from existing flight recorder endpoints:
- Does NOT modify `/api/flight-recorder/*` routes
- Provides telemetry in eval format (not flight recorder JSONL format)
- Can be used by flight recorder UI or other consumers

## Dependencies

This implementation depends on:
- ✅ #108 (TurnTelemetry models) - merged
- ✅ #110 (telemetry repo methods) - merged

## Files Modified

- `backend/services/telemetry.py` - Added `get_aide_telemetry()` function
- `backend/main.py` - Registered telemetry router

## Files Created

- `backend/routes/telemetry.py` - New telemetry API routes
- `backend/tests/test_telemetry_api.py` - Comprehensive test suite

## Acceptance Criteria

- ✅ `get_aide_telemetry()` function in telemetry.py
- ✅ New route file `backend/routes/telemetry.py`
- ✅ Router registered in main.py
- ✅ Tests pass: `pytest backend/tests/test_telemetry_api.py -v`
- ✅ Existing flight recorder endpoints unchanged
- ✅ Linting passes (ruff check + format)
- ✅ RLS security verified

## Next Steps

This completes task 5/8 in the telemetry consolidation epic (#104). Next tasks:
- #112 (6/8) - Integrate TurnRecorder into streaming orchestrator
- #113 (7/8) - Add telemetry to L2 compiler
- #114 (8/8) - Update flight recorder uploader
