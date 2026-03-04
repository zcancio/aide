# Build Log: Issue #151 - Prompt Versioning

**Issue:** (3/4) eval: add prompt versioning
**Date:** 2026-03-03
**Status:** ✅ Complete

## Summary

Implemented versioned prompt structure to support A/B testing of candidate prompts against production baseline. Followed TDD approach as specified in the issue.

## Changes Made

### 1. Directory Restructure
Created versioned prompt directory structure:
```
backend/prompts/
├── v1/                     # Production prompts
│   ├── shared_prefix.md
│   ├── l3_system.md
│   └── l4_system.md
└── current -> v1          # Symlink to active version
```

**Files moved:**
- `backend/prompts/*.md` → `backend/prompts/v1/*.md`
- Created symlink: `backend/prompts/current` → `v1`

### 2. Backend Implementation

**File:** `backend/services/prompt_builder.py`

Added version support to prompt loading:
- `_get_prompts_dir(version: str | None = None)` - New helper function
  - Returns versioned directory path
  - Falls back to "current" symlink if no version specified
  - Raises FileNotFoundError for nonexistent versions

- Updated `load_prompt(tier: str, version: str | None = None)`
  - Added optional version parameter
  - Uses `_get_prompts_dir()` to resolve version path

- Updated `build_system_blocks(tier: str, snapshot: dict, version: str | None = None)`
  - Added optional version parameter
  - Passes version through to `load_prompt()`

- Updated deprecated `_load_prompt_old()` for backward compatibility

### 3. Test Suite

**File:** `backend/tests/test_prompt_versioning.py` (new)

Created comprehensive test coverage:
- `test_prompt_version_loading()` - Verifies version parameter works and current == v1
- `test_prompt_version_nonexistent()` - Ensures clear error for missing versions
- `test_prompt_version_all_tiers()` - Tests L2, L3, L4 tier support

### 4. Eval Script Updates

**File:** `evals/scripts/eval_multiturn.py`

Added `--prompt-version` CLI flag:
- Updated `run_turn()` - Added prompt_version parameter
- Updated `run_multiturn_scenario()` - Propagated prompt_version through pipeline
- Updated all `build_system_blocks()` calls to pass version parameter
- Updated cache warming, retry logic, and escalation flows
- Added CLI argument: `--prompt-version` (e.g., `--prompt-version v2`)
- Updated documentation with usage example

## TDD Flow (as specified)

### ✅ RED Phase
1. Wrote failing test in `test_prompt_versioning.py`
2. Ran tests: `pytest backend/tests/test_prompt_versioning.py` → **3 FAILED**
   - TypeError: build_system_blocks() got an unexpected keyword argument 'version'

### ✅ GREEN Phase
1. Created versioned directory structure (v1/ + current symlink)
2. Implemented `_get_prompts_dir()` helper
3. Added version parameter to `load_prompt()` and `build_system_blocks()`
4. Ran tests: `pytest backend/tests/test_prompt_versioning.py` → **3 PASSED**

### ✅ REFACTOR Phase
1. Added `--prompt-version` flag to eval_multiturn.py
2. Propagated version parameter through entire eval pipeline
3. Updated documentation

## Testing Results

### Unit Tests
```bash
$ pytest backend/tests/test_prompt_versioning.py -v
# 3/3 passed ✅

$ pytest backend/tests/test_prompt_builder.py -v
# 12/12 passed ✅

$ pytest backend/tests/test_*.py -k "prompt" -v
# 19/19 passed ✅
```

### Linting
```bash
$ ruff check backend/
# All checks passed! ✅

$ ruff format --check backend/
# 80 files already formatted ✅
```

## Usage Examples

### Use production prompts (default)
```bash
python evals/scripts/eval_multiturn.py --scenario graduation_realistic
```

### Test candidate v2 prompts
```bash
python evals/scripts/eval_multiturn.py --scenario graduation_realistic --prompt-version v2
```

### A/B comparison workflow
```bash
# Run baseline
python evals/scripts/eval_multiturn.py --save --output-dir ./eval_v1

# Run candidate
python evals/scripts/eval_multiturn.py --save --output-dir ./eval_v2 --prompt-version v2

# Compare results
diff eval_v1/report.json eval_v2/report.json
```

## Backward Compatibility

✅ All existing code continues to work without changes:
- Default behavior uses "current" symlink (points to v1)
- Optional version parameter preserves existing API
- Deprecated functions updated for consistency

## Files Modified

1. `backend/services/prompt_builder.py` - Core versioning logic
2. `evals/scripts/eval_multiturn.py` - CLI flag and propagation
3. `backend/tests/test_prompt_versioning.py` - New test file

## Files Created/Moved

1. Created: `backend/prompts/v1/` directory
2. Moved: All `.md` files to `v1/` subdirectory
3. Created: `backend/prompts/current` symlink → `v1`

## Next Steps

To create a candidate version for testing:
```bash
# Copy current version
cp -r backend/prompts/v1 backend/prompts/v2

# Edit candidate prompts
vim backend/prompts/v2/l3_system.md

# Test candidate
python evals/scripts/eval_multiturn.py --prompt-version v2
```

## Notes

- Symlink approach allows easy rollback (just update `current` link)
- Version structure supports multiple concurrent candidates (v2, v3, etc.)
- Tests verify FileNotFoundError for missing versions
- All eval pipeline stages properly propagate version parameter
- Cache warming, retries, and escalation all respect version setting
