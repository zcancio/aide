# Build Log: Issue #112 - Add TurnRecorder Class to Telemetry Service

**Date:** 2026-03-02
**Issue:** (4 of 8) Add TurnRecorder class to telemetry service
**Status:** ✅ Complete

## Summary

Added `TurnRecorder` class to `backend/services/telemetry.py` for capturing turn telemetry data during streaming. This class runs in parallel with the existing `LLMCallTracker` and records data in eval-compatible format.

## Changes Made

### 1. Updated `backend/services/telemetry.py`

**Imports Added:**
- Added `TokenUsage` and `TurnTelemetry` to imports from `backend.models.telemetry`

**New Class Added:**
- `TurnRecorder` class with the following methods:
  - `__init__(aide_id, user_id)` - Initialize recorder
  - `start_turn(turn_num, tier, model, message)` - Begin turn recording
  - `record_tool_call(name, input, timestamp_ms=None)` - Record tool calls
  - `record_text_block(text, timestamp_ms=None)` - Record text blocks
  - `set_system_prompt(prompt)` - Set system prompt
  - `mark_first_content()` - Mark time-to-first-content
  - `set_usage(input_tokens, output_tokens, cache_read=0, cache_creation=0)` - Set token usage
  - `set_validation(passed, issues=None)` - Set validation result
  - `finish()` - Finalize and persist turn data (returns UUID or None)

**Key Features:**
- Tracks timing with `time.perf_counter()` for TTFC and TTC
- Supports optional timestamps on tool calls and text blocks
- Returns `None` from `finish()` if usage not set (prevents incomplete data)
- Automatically sets TTFC = TTC if TTFC not marked

**Existing Code:**
- `LLMCallTracker` class unchanged
- All existing functionality preserved

### 2. Created `backend/tests/test_turn_recorder.py`

**Tests Created:**
1. `test_turn_recorder_basic_flow` - Tests basic recording flow with all core methods
2. `test_turn_recorder_with_timestamps` - Tests optional timestamps on tool calls and text blocks, verifies persistence
3. `test_turn_recorder_returns_none_without_usage` - Tests that finish() returns None when usage not set

**Test Pattern:**
- Uses `pytestmark = pytest.mark.asyncio(loop_scope="session")`
- Creates test aides inline (no fixture)
- Properly cleans up test data in all cases
- Uses `test_user_id` fixture from conftest.py

## Verification

### Linting
```bash
ruff check backend/
ruff format --check backend/
```
**Result:** ✅ All checks passed

### Tests
```bash
python3 -m pytest backend/tests/test_turn_recorder.py -v
```
**Result:** ✅ 3/3 tests passed

### Test Output
```
backend/tests/test_turn_recorder.py::test_turn_recorder_basic_flow PASSED [ 33%]
backend/tests/test_turn_recorder.py::test_turn_recorder_with_timestamps PASSED [ 66%]
backend/tests/test_turn_recorder_returns_none_without_usage PASSED [100%]
```

## Dependencies

This implementation depends on:
- ✅ #108 (TurnTelemetry models) - Models imported successfully
- ✅ #110 (telemetry repo methods) - `insert_turn()` and `get_turns_for_aide()` used successfully

## Integration Points

The `TurnRecorder` class:
- Uses `telemetry_repo.insert_turn()` to persist data
- Creates `TurnTelemetry` objects with `TokenUsage`
- Stores data in `aide_turn_telemetry` table with RLS enforcement
- Compatible with eval golden file format

## Files Modified

- `backend/services/telemetry.py` - Added TurnRecorder class (133 lines added)
- `backend/tests/test_turn_recorder.py` - Created test file (96 lines)

## Next Steps

This implementation is ready for:
- Integration into streaming pipeline
- Use alongside existing FlightRecorder (parallel operation)
- Future consolidation when FlightRecorder is replaced

## Notes

- TurnRecorder does NOT replace FlightRecorder yet - runs in parallel
- All tests follow existing patterns from test_telemetry_repo.py
- Proper cleanup ensures no test data leakage
- RLS enforcement verified through repo layer
