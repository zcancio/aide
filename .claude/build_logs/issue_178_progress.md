# Build Log: Issue #178 - Fix Turn Counts in Dashboard

## Issue Summary
Turn counts in the dashboard were showing 0 for all users, despite users having completed turns.

## Root Cause
The `TurnRecorder.finish()` method in `backend/services/telemetry.py` was persisting turn telemetry to the `aide_turn_telemetry` table but was not incrementing the user's `turn_count` field in the `users` table. The `UserRepo.increment_turns()` method existed but was never being called.

## Changes Made

### 1. Modified `backend/services/telemetry.py`
- Added import for `UserRepo` (line 24)
- Modified `TurnRecorder.finish()` method to:
  - Store the row_id from `insert_turn()` instead of returning it immediately
  - Instantiate `UserRepo` and call `increment_turns(user_id)` to update the user's turn count
  - Return the row_id after incrementing

**File:** `backend/services/telemetry.py:229-258`

```python
async def finish(self) -> UUID | None:
    """Finalize and persist the turn. Returns row ID or None if missing data."""
    if not self._usage:
        return None

    self._ttc_ms = int((time.perf_counter() - self._start_time) * 1000)
    if self._ttfc_ms is None:
        self._ttfc_ms = self._ttc_ms

    turn = TurnTelemetry(
        turn=self._turn_num,
        tier=self._tier,
        model=self._model,
        message=self._message,
        tool_calls=self._tool_calls,
        text_blocks=self._text_blocks,
        system_prompt=self._system_prompt,
        usage=self._usage,
        ttfc_ms=self._ttfc_ms,
        ttc_ms=self._ttc_ms,
        validation=self._validation,
    )

    row_id = await telemetry_repo.insert_turn(self._user_id, self._aide_id, turn)

    # Increment user's turn count
    user_repo = UserRepo()
    await user_repo.increment_turns(self._user_id)

    return row_id
```

### 2. Added Test Coverage
Added new test `test_turn_recorder_increments_user_turn_count()` in `backend/tests/test_turn_recorder.py` to verify that:
- User's `turn_count` is read before recording a turn
- After `TurnRecorder.finish()` is called, the `turn_count` is incremented by 1
- Test includes proper cleanup of test data

**File:** `backend/tests/test_turn_recorder.py:101-135`

## Testing

### Tests Run
1. `test_turn_recorder.py::test_turn_recorder_increments_user_turn_count` - PASSED
2. All turn recorder tests (4 tests) - PASSED
3. All orchestrator telemetry tests (4 tests) - PASSED
4. All user-related tests (30 tests) - PASSED

### Linting
- `ruff check backend/` - All checks passed
- `ruff format --check backend/` - All files formatted correctly

## Impact
- User turn counts will now properly increment each time a turn is completed
- Dashboard will show accurate turn counts for all users
- Weekly turn limit enforcement (for free tier) will work correctly
- No breaking changes to existing functionality
- All existing tests continue to pass

## Files Modified
1. `backend/services/telemetry.py` - Added UserRepo import and increment_turns call
2. `backend/tests/test_turn_recorder.py` - Added test for turn count increment

## Verification Steps
1. ✅ Run linting: `ruff check backend/ && ruff format --check backend/`
2. ✅ Run tests: `DATABASE_URL=postgres://aide_app:test@localhost:5432/aide_test pytest backend/tests/ -v`
3. ✅ All 4 turn recorder tests pass
4. ✅ All 30 user-related tests pass
5. ✅ All 4 orchestrator telemetry tests pass

## Status
✅ Complete - Ready for review
