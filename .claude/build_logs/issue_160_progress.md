# Build Log: Issue #160 - Flight Recorder Export

## Summary
Added a flight recorder export feature that allows downloading full aide telemetry as a shareable JSON file for review and debugging.

## Implementation

### Backend Changes

#### 1. New API Endpoint: `/api/aides/{aide_id}/telemetry/export`
- **File**: `backend/routes/telemetry.py`
- **Method**: GET
- **Auth**: Requires authenticated user via JWT cookie
- **RLS**: Enforced - users can only export their own aides
- **Response**: JSON file with `Content-Disposition: attachment` header
- **Format**: Uses existing `AideTelemetry` Pydantic model (eval-compatible)

**Implementation Details**:
```python
@router.get("/{aide_id}/telemetry/export")
async def export_telemetry(
    aide_id: UUID,
    user: User = Depends(get_current_user),
) -> Response:
    """Export full telemetry as downloadable JSON file."""
    telemetry = await get_aide_telemetry(user.id, aide_id)
    if not telemetry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aide not found.",
        )

    filename = f"aide-telemetry-{aide_id}-{telemetry.timestamp[:10]}.json"
    return Response(
        content=telemetry.model_dump_json(indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

**Key Features**:
- Reuses existing `get_aide_telemetry()` service function
- No code duplication - shares logic with the existing GET `/api/aides/{aide_id}/telemetry` endpoint
- Automatic filename generation with aide_id and date
- Returns formatted JSON (indented) for readability

### Frontend Changes

#### 2. Export Button in Flight Recorder UI
- **File**: `frontend/flight-recorder.html`
- **Location**: Top toolbar, next to existing "Export Turn" button
- **Button**: "Export All" - downloads full telemetry for all turns
- **Style**: Blue background (#1e40af) with bold font to distinguish from turn export

**Implementation Details**:
```javascript
<button
  onClick={async () => {
    const res = await fetch(`/api/aides/${aideId}/telemetry/export`, { credentials: 'include' });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const contentDisposition = res.headers.get('content-disposition');
    const filenameMatch = contentDisposition?.match(/filename="(.+)"/);
    a.download = filenameMatch ? filenameMatch[1] : `aide-telemetry-${aideId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }}
  style={{
    background: "#1e40af",
    border: "1px solid #3b82f6",
    color: "#93c5fd",
    cursor: "pointer",
    fontSize: 11,
    padding: "4px 10px",
    borderRadius: 4,
    fontWeight: 600,
  }}
  title="Download full telemetry for all turns"
>
  Export All
</button>
```

**Key Features**:
- Extracts filename from Content-Disposition header
- Fallback filename if header parsing fails
- Proper blob handling with URL cleanup
- No loading state needed (browser handles download)

### Testing

#### 3. Comprehensive Test Suite
- **File**: `backend/tests/test_telemetry_api.py`
- **New Tests**: 5 tests covering all edge cases

**Tests Added**:
1. `test_export_telemetry_headers` - Verifies response headers (content-type, content-disposition)
2. `test_export_telemetry_format` - Validates AideTelemetry JSON structure
3. `test_export_telemetry_rls` - Ensures RLS isolation (404 for other user's aide)
4. `test_export_telemetry_not_found` - 404 for non-existent aide
5. `test_export_telemetry_unauthenticated` - 401 for unauthenticated requests

**New Fixture**:
- `test_aide` - Minimal aide fixture without turns (for basic tests)
- Reused existing `test_aide_with_turns` fixture for full telemetry tests

**Test Results**:
```
backend/tests/test_telemetry_api.py::test_export_telemetry_headers PASSED
backend/tests/test_telemetry_api.py::test_export_telemetry_format PASSED
backend/tests/test_telemetry_api.py::test_export_telemetry_rls PASSED
backend/tests/test_telemetry_api.py::test_export_telemetry_not_found PASSED
backend/tests/test_telemetry_api.py::test_export_telemetry_unauthenticated PASSED
```

All 12 telemetry API tests pass (7 existing + 5 new).

## TDD Approach Followed

### Phase 1: RED
- Wrote 5 failing tests in `test_telemetry_api.py`
- Tests initially hit 404 (endpoint didn't exist)
- Confirmed proper test failures

### Phase 2: GREEN
- Implemented `/api/aides/{aide_id}/telemetry/export` endpoint
- All 5 tests passed
- Fixed one test assertion (content-type header format)

### Phase 3: REFACTOR
- Reviewed for code duplication - none found (endpoint is minimal, reuses existing service)
- Ran full test suite - all tests pass
- Ran linting - all checks pass

## Export Format

The export uses the existing `AideTelemetry` Pydantic model, which is eval-compatible:

```json
{
  "aide_id": "uuid",
  "name": "Aide Title",
  "scenario_id": null,
  "pattern": null,
  "timestamp": "2026-03-05T12:00:00Z",
  "turns": [
    {
      "turn": 1,
      "tier": "L3",
      "model": "sonnet",
      "message": "User message...",
      "tool_calls": [...],
      "text_blocks": [...],
      "system_prompt": "...",
      "usage": {"input_tokens": 1200, "output_tokens": 450, ...},
      "ttfc_ms": 1250,
      "ttc_ms": 4500,
      "validation": null
    }
  ],
  "final_snapshot": {...}
}
```

## Privacy & Security

- **RLS Enforcement**: Users can only export their own aides (enforced via `get_aide_telemetry(user.id, aide_id)`)
- **Authentication**: JWT cookie required (via `get_current_user` dependency)
- **No Additional PII Scrubbing**: Same privacy posture as existing telemetry endpoint
- **Full Content**: Exported files contain complete message content and tool call inputs

## Files Modified

1. `backend/routes/telemetry.py` - Added export endpoint
2. `backend/tests/test_telemetry_api.py` - Added 5 tests + fixture
3. `backend/tests/test_telemetry.py` - Removed placeholder comment
4. `frontend/flight-recorder.html` - Added "Export All" button

## Quality Checks

✅ All tests pass (12/12 in test_telemetry_api.py)
✅ Ruff linting passed (no issues)
✅ Ruff formatting passed (all files formatted)
✅ RLS enforced (cross-user test passes)
✅ Authentication required (401 test passes)
✅ No code duplication (reuses existing service)

## Out of Scope

The following were explicitly descoped per the issue:
- Bulk export (multiple aides)
- Partial export (date range filter)
- R2 archival storage
- Loading states (browser handles download)

## Usage

1. Navigate to flight recorder: `/flight-recorder?aide_id={aide_id}`
2. Click "Export All" button in top toolbar
3. Browser downloads JSON file: `aide-telemetry-{aide_id}-{date}.json`
4. Use exported file for:
   - Quality analysis
   - Debugging production issues
   - Archival before aide deletion
   - Offline eval comparisons

## Notes

- Endpoint is minimal (8 lines) and follows existing patterns
- Frontend button is visually distinct (blue, bold) from turn export
- Filename includes date for easy organization
- Format is eval-compatible (can be used with eval tooling)
