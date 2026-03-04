# Build Log: Issue #150 - Eval uses production kernel

**Date:** 2026-03-03
**Issue:** #150 (2/4) eval: use production kernel
**Status:** ✅ Completed

## Summary

Replaced the ~80-line inline reducer in `evals/scripts/eval_multiturn.py` with calls to the production kernel (`engine/kernel/kernel.py`). This ensures evals apply events through the same code path as the production app, eliminating drift between eval behavior and production behavior.

## Changes Made

### 1. Created Test Suite (TDD RED)
**File:** `evals/scripts/test_kernel_unification.py`
- Added `test_eval_apply_matches_kernel()` - Verifies eval and kernel produce identical entity state
- Added `test_eval_apply_handles_multiple_events()` - Tests sequence of events (create, create, update)
- Added `test_eval_apply_skips_signals()` - Confirms signals (voice, escalate) don't break state application
- Added `test_eval_apply_l4_readonly()` - Validates L4 tier doesn't mutate snapshot

### 2. Replaced apply_output_to_snapshot (TDD GREEN)
**File:** `evals/scripts/eval_multiturn.py`

**Before:**
- ~80 lines of inline reducer logic
- Manual handling of entity.create, entity.update, entity.remove, entity.move
- Custom relationship handling (rel.set, rel.remove)
- Meta operations (meta.set, meta.update)
- Orphan detection logic

**After:**
- 18 lines using production kernel
- Import from `engine.kernel.kernel import apply`
- Loop through parsed events
- Skip signals (voice, escalate, clarify, batch.start, batch.end)
- Apply each event via `apply(working, event)`
- Accept result if `result.accepted`

**Code:**
```python
def apply_output_to_snapshot(snapshot: dict, output_text: str, tier: str) -> dict:
    """
    Apply LLM output through the production kernel.

    For L2/L3: parse JSONL and apply events through kernel.
    For L4: no state change (read-only).
    """
    if tier == "L4":
        return json.loads(json.dumps(snapshot))  # L4 is read-only

    parsed, _ = parse_jsonl(output_text)
    working = json.loads(json.dumps(snapshot))

    for event in parsed:
        # Skip signals - they don't mutate state
        if event.get("t") in ("voice", "escalate", "clarify", "batch.start", "batch.end"):
            continue

        result = apply(working, event)
        if result.accepted:
            working = result.snapshot

    return working
```

### 3. Code Quality Fixes
- Fixed import organization (ruff I001)
- Removed unused imports (date, timezone, timedelta, ScenarioScore, DIMENSION_WEIGHTS)
- Fixed line length issues (E501) by breaking long lines
- Fixed multiple statements on one line (E702) - semicolon after print statement
- Removed extraneous f-string prefixes (F541)
- Applied ruff format for consistent style

## Tests

### Unit Tests
```bash
python3 evals/scripts/test_kernel_unification.py
```
**Result:** ✅ All 4 tests passed

### Import Test
```bash
cd evals/scripts && python3 -c "from eval_multiturn import apply_output_to_snapshot; print('✓ Import successful')"
```
**Result:** ✅ Import successful

### Linting
```bash
ruff check evals/scripts/eval_multiturn.py evals/scripts/test_kernel_unification.py
ruff format --check evals/scripts/eval_multiturn.py evals/scripts/test_kernel_unification.py
```
**Result:** ✅ All checks passed

## Verification

The eval system now:
1. Uses the exact same kernel as production (`engine/kernel/kernel.py`)
2. Respects all kernel validation rules (ID validation, parent existence, cycle prevention, etc.)
3. Maintains identical state structure to production
4. Passes all existing tests

## Benefits

1. **No Drift:** Eval behavior matches production exactly
2. **Maintainability:** One source of truth for event application logic
3. **Correctness:** All kernel validation rules now apply in evals (previously only subset was enforced)
4. **Simplicity:** 80 lines → 18 lines
5. **Future-proof:** Any kernel improvements automatically flow to evals

## Files Modified

- `evals/scripts/eval_multiturn.py` - Replaced apply_output_to_snapshot with kernel calls
- `evals/scripts/test_kernel_unification.py` - New test suite (158 lines)

## Lines Changed

- **Deleted:** ~80 lines of inline reducer logic
- **Added:** 18 lines kernel integration + 158 lines tests
- **Net:** -62 lines in production code, +158 in tests

## Related Issues

- Depends on: #149 (prompts unified)
- Parent: #118 (eval improvements)
- Part of: 2/4 eval refactoring series
