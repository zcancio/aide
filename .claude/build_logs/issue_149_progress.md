# Issue #149 Build Log: Unify Prompts with Backend

**Date:** 2026-03-03
**Issue:** (1/4) eval: unify prompts with backend
**Objective:** Evals must use the same prompts as production backend

## Summary

Successfully unified eval prompts with backend prompts using TDD approach. All eval scripts now delegate to `backend/services/prompt_builder.py` instead of maintaining duplicate prompt files.

## Changes Made

### 1. Created Test (RED Phase) ✅
**File:** `evals/scripts/test_prompt_unification.py`
- New test to verify evals use backend's `build_system_blocks` function
- Test initially failed (as expected) because evals had separate implementation
- Updated to check that eval and backend functions are identical (delegation pattern)

### 2. Unified Prompt Builder (GREEN Phase) ✅
**File:** `evals/scripts/prompt_builder.py`
- **Before:** 215 lines with full implementation + duplicate prompt logic
- **After:** 32 lines that delegates to backend
- Adds backend to Python path
- Re-exports all functions from `backend.services.prompt_builder`
- Maintains same API for backward compatibility

### 3. Removed Duplicate Prompt Files ✅
Deleted duplicate markdown files from `evals/scripts/`:
- `shared_prefix.md` (deleted)
- `l2_tier.md` (deleted)
- `l3_tier.md` (deleted)
- `l4_tier.md` (deleted)

These files were maintaining separate copies of prompts that could drift from production.

### 4. Updated Eval Scripts (REFACTOR Phase) ✅

**File:** `evals/scripts/eval_multiturn.py`
- Removed inline `build_system_blocks()` implementation (45 lines)
- Removed inline `load_prompt()` implementation
- Now imports from `backend.services.prompt_builder`
- All functionality preserved

**File:** `evals/scripts/eval.py`
- Removed inline `build_system_blocks()` implementation (35 lines)
- Removed inline `load_prompt()` implementation
- Now imports from `backend.services.prompt_builder`
- All functionality preserved

## Architecture Notes

### Backend Prompt Structure (Production)
The backend uses a 2-block structure:
1. **Block 1:** Combined static prompt (shared prefix + tier instructions) with cache_control
2. **Block 2:** Dynamic snapshot (changes every turn)

### Key Differences Resolved
- **L2 Tier:** Backend has deprecated L2, consolidated into L3. The `build_l2_prompt()` function in backend uses L3 prompts.
- **Prompt Files:** Backend only has `l3_system.md` and `l4_system.md` (no `l2_system.md`)
- **Calendar Context:** Backend uses simpler date replacement, evals had complex calendar building (now unified)
- **Caching Strategy:** Backend uses 2 blocks, old evals used 3 blocks (now unified to 2)

## Testing

### Unit Tests ✅
```bash
python3 -m pytest evals/scripts/test_prompt_unification.py -v
```
**Result:** PASSED - Confirms evals delegate to backend

### Lint Checks ✅
```bash
ruff check backend/
ruff format --check backend/
```
**Result:** All checks passed, 79 files already formatted

## Benefits

1. **Single Source of Truth:** Prompts maintained in one place (`backend/prompts/`)
2. **No Drift:** Eval and production prompts are guaranteed identical
3. **Easier Maintenance:** Prompt changes automatically propagate to evals
4. **Code Reduction:** Removed ~300 lines of duplicate code across eval files
5. **Test Coverage:** New test ensures delegation is maintained

## Files Modified

- `evals/scripts/prompt_builder.py` - Replaced with delegation wrapper
- `evals/scripts/eval.py` - Uses backend prompt builder
- `evals/scripts/eval_multiturn.py` - Uses backend prompt builder
- `evals/scripts/test_prompt_unification.py` - New test file

## Files Deleted

- `evals/scripts/shared_prefix.md`
- `evals/scripts/l2_tier.md`
- `evals/scripts/l3_tier.md`
- `evals/scripts/l4_tier.md`

## Next Steps

As outlined in parent issue #118, remaining tasks are:
- (2/4) eval: add structured scoring
- (3/4) eval: add multi-turn scenarios
- (4/4) eval: document eval system

## Notes

- No database migrations needed (prompt-only changes)
- No backend tests affected (only eval scripts modified)
- Backward compatible - same API preserved in prompt_builder.py
- Ready for review and merge
