# Phase 1.7: Reliability + Flight Recorder — Build Log

**Date:** 2026-02-17
**Branch:** claude/issue-20
**Status:** Complete

---

## What was built

### 1.7.1 Reliability (previously done)
- Error handling for invalid primitives — already in place via `validate_primitive` in L2/L3.
- Retry logic for L2/L3 calls — handled by `_call_l2`/`_call_l3` wrappers in orchestrator.
- R2 upload retry — implemented in `FlightRecorderUploader._upload_aide_batch` (1 retry, 2s delay).

### 1.7.2 Flight Recorder

**`docs/aide_flight_recorder_design.md`** (new)
- Design doc covering architecture, data format, storage layout, model configuration, error handling, privacy posture.

**`backend/services/flight_recorder.py`** (new)
- `LLMCallRecord` dataclass: one record per LLM call (production or shadow), captures model, tier (L2/L3), prompt, response, token usage, latency_ms, error.
- `TurnRecord` dataclass: complete turn snapshot — user message, snapshot before/after, all LLM calls, primitives emitted/applied, response text, total latency.
- `FlightRecorder` class: per-turn recorder. `start_turn()` → `record_llm_call()` (multiple times) → `end_turn()` → `TurnRecord`.

**`backend/services/flight_recorder_uploader.py`** (new)
- `FlightRecorderUploader`: background uploader. Bounded asyncio queue (10,000 records max).
- `enqueue()`: O(1), non-blocking. On overflow: drops oldest, logs warning.
- `run()`: background loop — drains queue, batches by `_BATCH_SIZE` (100) or `_FLUSH_INTERVAL_SECONDS` (60s).
- `flush()`: graceful shutdown — uploads all remaining records.
- `_upload_batch()`: groups by aide_id for separate JSONL files per aide.
- `_upload_aide_batch()`: retry once on R2 failure (2s delay). Serialization errors skip without raising.
- Storage key: `flight-logs/{aide_id}/{YYYY-MM-DD}/{batch_id}.jsonl` in the existing `aide-workspaces` R2 bucket.

### 1.7.3 Shadow LLM Calls

**`backend/config.py`** (updated)
- Added `L2_MODEL` (default: `claude-sonnet-4-20250514`) — production L2 (Sonnet for quality).
- Added `L3_MODEL` (default: `claude-opus-4-6`) — production L3 (Opus for schema synthesis + vision).
- Added `L2_SHADOW_MODEL` (default: `claude-3-5-haiku-20241022`) — shadow L2 (lower-tier for cost comparison).
- Added `L3_SHADOW_MODEL` (default: `claude-sonnet-4-20250514`) — shadow L3 (lower-tier for cost comparison).
- All four configurable via environment variables.

**`backend/services/orchestrator.py`** (refactored)
- `process_message()` now initializes a `FlightRecorder` at the start of each turn.
- `_call_l2()` / `_call_l3()`: wrappers that call production or shadow model, record result in flight recorder with timing, and return parsed result.
- `_call_l2_shadow()` / `_call_l3_shadow()`: thin wrappers that never raise — shadow failures are logged and recorded but never surface to users.
- Shadow calls run sequentially after production calls (same event loop, same turn, before reducer).
- At turn end: `recorder.end_turn()` → `TurnRecord` → `flight_recorder_uploader.enqueue()`.

**`backend/main.py`** (updated)
- Imports `flight_recorder_uploader`.
- Lifespan starts uploader as background task alongside cleanup task.
- Lifespan cancels uploader task on shutdown, then calls `flush()` to drain remaining records.

### Tests

**`backend/tests/test_flight_recorder.py`** (new, 15 tests)
- `TestFlightRecorder` (6 tests): start/end turn produces valid record, LLM calls captured, shadow+production both recorded, failed call with error, JSON serialization, latency measurement.
- `TestFlightRecorderUploader` (7 tests): enqueue non-blocking, queue overflow drops oldest, flush uploads all pending, batch grouped by aide, retry on failure, permanent failure dropped, serialization error skips.
- `TestOrchestratorFlightRecorderIntegration` (2 tests): process_message enqueues TurnRecord, shadow call failure doesn't fail production turn.

---

## Test results

```
22 passed in 5.02s
ruff check: all checks passed
ruff format --check: 45 files already formatted
```

---

## Design decisions

1. **Per-turn recorder, not singleton**: `FlightRecorder` is instantiated per `process_message()` call. No shared state between concurrent turns.

2. **Shadow calls sequential, not concurrent**: Easier to reason about, shadow never races with production. Adds latency but shadow latency is already acceptable (it's post-response in terms of user impact — user sees response after production call).

3. **Bounded queue, drop oldest**: 10,000 record buffer is generous. Dropping oldest favors recency — recent turns are more valuable for debugging.

4. **R2 workspace bucket reuse**: Flight logs live at `flight-logs/{aide_id}/...` in the existing private `aide-workspaces` bucket. No new bucket or credentials needed.

5. **Zero token usage for production calls**: `l2_compiler` and `l3_synthesizer` don't return token counts. Shadow calls (which call `ai_provider` directly) do return usage. Production usage tracking is a future improvement.

---

## Acceptance criteria checklist

- [x] Flight recorder captures all turn data as JSONL
- [x] Shadow calls recorded alongside production calls (not applied to state)
- [x] Background upload doesn't delay user responses
- [x] Upload failures do not delay or fail user responses (retry + drop)
- [x] Queue bounded at 10,000 records, drops oldest on overflow with warning
- [x] Background uploader starts with the app, stops cleanly on shutdown with flush
- [x] `ruff check` and `ruff format --check` pass
- [x] All new tests pass (15/15)
- [x] Existing orchestrator tests still pass (7/7)
