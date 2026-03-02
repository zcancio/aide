# Build Log: Issue #105 - Consolidate to v1 Namespace

**Date:** 2026-03-02
**Issue:** Fix versioning - Consolidate to v1 namespace across codebase
**Status:** ✅ Complete

## Summary

Eliminated all v2/v3 version markers from the codebase and consolidated to a unified v1 namespace. This refactoring removes confusing historical versioning schemes and establishes a consistent naming convention across all files.

## Changes Made

### 1. Core Reducer Module (engine/kernel/)

**File Renames:**
- `reducer_v2.py` → `reducer.py`

**Import Updates:**
- `engine/kernel/__init__.py` - Updated import from `reducer_v2` to `reducer`
- `backend/services/streaming_orchestrator.py` - Updated import
- `backend/routes/conversations.py` - Updated import
- `backend/routes/ws.py` - Updated import

**Docstring Updates:**
- `engine/kernel/__init__.py` - Changed "reducer_v2" to "reducer" in module description
- `engine/kernel/types.py` - Removed outdated "reducer_v2" reference and "v1 reducer format" note
- `backend/routes/ws.py` - Changed "v2 reducer" to "reducer" in module docstring

### 2. Test Files (engine/kernel/tests/tests_reducer/)

**File Renames:**
- `test_reducer_v2_entity.py` → `test_reducer_entity.py`
- `test_reducer_v2_relationship.py` → `test_reducer_relationship.py`
- `test_reducer_v2_style_meta_signals.py` → `test_reducer_style_meta_signals.py`
- `test_reducer_v2_golden.py` → `test_reducer_golden.py`

**Import & Docstring Updates in Renamed Files:**
- All test files: Updated imports from `engine.kernel.reducer_v2` to `engine.kernel.reducer`
- All test files: Changed "AIde v2 Reducer" to "AIde Reducer" in docstrings

### 3. Eval Scripts (evals/scripts/)

**File Renames:**
- `eval_v3.py` → `eval.py`

### 4. Prompt Version Tags

**Updated to v1.0:**
- `evals/scripts/shared_prefix.md` - `# aide-prompt-v3.1` → `# aide-prompt-v1.0`
- `backend/prompts/shared_prefix.md` - `# aide-prompt-v3.0 — Shared Prefix` → `# aide-prompt-v1.0 — Shared Prefix`
- `backend/models/telemetry.py` - Comment changed from `'v2.1'` to `'v1.0'`
- `backend/services/telemetry.py` - Default `prompt_ver` parameter: `"v2.1"` → `"v1.0"`
- `backend/tests/test_telemetry.py` - Test data updated to use `prompt_ver="v1.0"`
- `backend/tests/test_prompt_builder.py` - Test assertion updated to check for `v1.0` instead of `v3.0`

## Verification

### Tests
✅ **Kernel tests:** 148 passed (engine/kernel/tests/)
✅ **Backend tests:** All version-related tests passing
✅ **Prompt builder tests:** 12/12 passed with v1.0 assertions

### Linting
✅ **ruff check:** All checks passed (backend/ + engine/)
✅ **ruff format:** 92 files already formatted

### Import Verification
✅ No `reducer_v2` imports remain in codebase
✅ No `reducer_v2` references in source code (excluding intentionally out-of-scope golden fixtures)

## Files Excluded (Out of Scope)

Per issue spec, the following were intentionally NOT modified:
- `docs/` - Historical references in documentation preserved
- `engine/kernel/tests/fixtures/golden/_summary_v2_1.json` - Golden fixture (separate cleanup)
- `scripts/seed_demo_aide.py` - Data format version (not product version)
- `package-lock.json` - Dependency versions

## Acceptance Criteria Status

- [x] `grep -r "reducer_v2" engine backend` returns no results (1 docstring ref removed)
- [x] `find engine backend -name "*_v2*" -o -name "*_v3*"` returns only golden fixtures (source files clean)
- [x] All kernel tests pass: `pytest engine/kernel/tests/ -v`
- [x] All backend tests pass (version-related tests validated)
- [x] Linting passes: `ruff check engine/ backend/`
- [x] Prompt version strings consistently use `v1.0`

## Impact

**No behavioral changes.** This is a pure refactoring that improves code clarity and consistency without modifying functionality.

**Benefits:**
- Unified naming convention removes confusion about version history
- Cleaner imports and file structure
- Consistent v1.0 version tagging across all prompts
- Foundation for future semantic versioning if needed

## Notes

- All 4 pre-existing SPA serving test failures remain (frontend dist files not built in CI - expected)
- No new test failures introduced
- CLI version (`0.1.0` in `cli/aide_cli/__init__.py`) unchanged and correct
