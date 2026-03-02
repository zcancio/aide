# Issue 83: Remove unused llm_provider.py

## Summary
Removed `backend/services/llm_provider.py` which was a 30-line factory function that was never imported anywhere in the codebase.

## Verification Steps Completed

### 1. Confirmed File Was Unused (Red)
```bash
grep -r "llm_provider" backend/ --include="*.py" | grep -v "llm_provider.py"
# Result: No matches found

grep -r "get_llm" backend/ --include="*.py" | grep -v "llm_provider.py"
# Result: No matches found
```

### 2. Checked __init__.py
- File was NOT exported from `backend/services/__init__.py`
- No additional cleanup needed

## Implementation

### Files Deleted
- `backend/services/llm_provider.py` (30 lines)

### Files Modified
- None (file was not exported)

## Testing Results

### Lint & Format
```bash
ruff check backend/ && ruff format --check backend/
```
✅ All checks passed!
✅ 85 files already formatted

### Backend Tests
```bash
python3 -m pytest backend/tests/ -v
```
✅ 266 passed
❌ 4 failed (pre-existing SPA serving failures, unrelated to this change)

The 4 failures are in `test_spa_serving.py` and are unrelated to removing `llm_provider.py`:
- `test_root_returns_spa`
- `test_catch_all_returns_spa`
- `test_nested_route_returns_spa`
- `test_assets_served`

These failures are due to missing `frontend/dist/spa.html` file, which is a separate issue.

## Impact Analysis

The removed file contained:
- `get_llm()` factory function that returned either `MockLLM` or `AnthropicClient`
- Based on `USE_MOCK_LLM` and `ANTHROPIC_API_KEY` settings
- Was never imported or used anywhere in the codebase

The backend uses `anthropic_client.py` directly instead of going through this factory.

## Conclusion

✅ File successfully removed
✅ No imports to clean up
✅ All lints pass
✅ Backend tests pass (except pre-existing SPA failures)
✅ No regressions introduced
