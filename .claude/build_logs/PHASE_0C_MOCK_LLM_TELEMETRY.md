# Phase 0c — Mock LLM + Telemetry

**Status:** ✅ Phase 0c Complete
**Date:** 2026-02-19
**Branch:** `claude/issue-30`

---

## Summary

Built infrastructure for deterministic testing and performance measurement:

1. **Mock LLM** (`engine/kernel/mock_llm.py`) — streams golden files line-by-line with configurable delay profiles. Enables fast, deterministic tests with no real API calls, and realistic UX timing simulation.

2. **Telemetry table + migration** (`alembic/versions/006_add_telemetry_table.py`) — captures LLM call metrics, reducer stats, cost, and escalation signals from every AI turn.

3. **Pydantic model + repo + service** — full telemetry stack with `TelemetryEvent`, `record_event()`, `get_aide_stats()`, `LLMCallTracker`, and `calculate_cost()`.

4. **LLM provider toggle** (`backend/services/llm_provider.py` + `USE_MOCK_LLM` in `backend/config.py`) — `get_llm()` returns MockLLM when `USE_MOCK_LLM=true`, real implementation in Phase 4.

---

## What Was Built

### New Files

| File | Description |
|------|-------------|
| `engine/kernel/mock_llm.py` | `MockLLM` class — streams golden `.jsonl` files with 4 delay profiles |
| `engine/kernel/tests/test_mock_llm.py` | 6 tests covering streaming, timing, error cases |
| `alembic/versions/006_add_telemetry_table.py` | Migration: `telemetry` table + 4 indexes |
| `backend/models/telemetry.py` | `TelemetryEvent` Pydantic model (`extra="forbid"`) |
| `backend/repos/telemetry_repo.py` | `record_event()` + `get_aide_stats()` using `system_conn()` |
| `backend/services/telemetry.py` | `LLMCallTracker` context class + `calculate_cost()` |
| `backend/services/llm_provider.py` | `get_llm()` factory with `USE_MOCK_LLM` toggle |
| `backend/tests/test_telemetry.py` | 10 tests: 3 DB, 4 tracker, 3 cost |

### Modified Files

| File | Change |
|------|--------|
| `backend/config.py` | Added `USE_MOCK_LLM: bool` setting |

---

## Delay Profiles

| Profile | Think Time | Per-Line | Use Case |
|---------|-----------|----------|----------|
| `instant` | 0ms | 0ms | Unit tests — fast, deterministic |
| `realistic_l2` | 300ms | 200ms | Simulates Haiku L2 response |
| `realistic_l3` | 1500ms | 150ms | Simulates Sonnet L3 first creation |
| `slow` | 3000ms | 500ms | Stress testing UX / interrupt handling |

---

## Database Schema

```sql
CREATE TABLE telemetry (
    id              SERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ DEFAULT NOW(),
    aide_id         UUID NOT NULL,
    user_id         UUID,
    event_type      TEXT NOT NULL,     -- llm_call / direct_edit / undo / escalation
    tier            TEXT,              -- L2 / L3 / L4
    model           TEXT,              -- haiku / sonnet / opus
    prompt_ver      TEXT,
    ttfc_ms         INT,               -- time to first content
    ttc_ms          INT,               -- time to complete
    input_tokens    INT,
    output_tokens   INT,
    cache_read_tokens   INT,
    cache_write_tokens  INT,
    lines_emitted   INT,
    lines_accepted  INT,
    lines_rejected  INT,
    escalated       BOOLEAN DEFAULT FALSE,
    escalation_reason TEXT,
    cost_usd        NUMERIC(10,6),
    edit_latency_ms INT,
    message_id      UUID,
    error           TEXT,
    CONSTRAINT valid_event_type CHECK (
        event_type IN ('llm_call', 'direct_edit', 'undo', 'escalation')
    )
);
-- Indexes: aide_id+ts, tier+ts, user_id+ts, event_type+ts
```

---

## Hard Rules Compliance

| Rule | Status |
|------|--------|
| Raw asyncpg only — no ORM | ✅ All SQL uses `asyncpg` parameterized queries |
| No f-strings or `.format()` in SQL | ✅ Verified — all `$1`, `$2` placeholders |
| SQL only in `backend/repos/` | ✅ `telemetry_repo.py` is the only SQL location |
| `system_conn()` for system-level ops | ✅ Telemetry is system-level (no user scope needed per spec) |
| Pydantic models with `extra="forbid"` | ✅ `TelemetryEvent` has `model_config = {"extra": "forbid"}` |
| No Google dependencies | ✅ None introduced |

---

## File Structure

```
engine/kernel/
├── mock_llm.py                     ← new
└── tests/
    └── test_mock_llm.py            ← new (6 tests)

backend/
├── config.py                       ← modified: USE_MOCK_LLM added
├── models/
│   └── telemetry.py                ← new
├── repos/
│   └── telemetry_repo.py           ← new
├── services/
│   ├── llm_provider.py             ← new
│   └── telemetry.py                ← new
└── tests/
    └── test_telemetry.py           ← new (10 tests)

alembic/versions/
└── 006_add_telemetry_table.py      ← new
```

---

## Verification

### Lint + Format
```
ruff check backend/ engine/kernel/mock_llm.py engine/kernel/tests/test_mock_llm.py
→ All checks passed!

ruff format --check backend/ engine/kernel/mock_llm.py engine/kernel/tests/test_mock_llm.py
→ 55 files already formatted
```

### MockLLM Tests (6 tests)
```
pytest engine/kernel/tests/test_mock_llm.py -v
→ 6 passed in 1.86s
```

### Telemetry Tests (10 tests)
```
pytest backend/tests/test_telemetry.py -v
→ 10 passed in 0.37s
```

### Alembic Migration
```
DATABASE_URL=postgresql://aide:test@localhost:5432/aide_test alembic upgrade head
→ Running upgrade 005 -> 006, Add telemetry table for LLM call and edit metrics.
```

### Pre-existing Failures (not introduced by this PR)
- 6 `test_db.py` RLS failures — pre-existing (verified by stashing changes)
- 9 `test_postgres_storage.py` event loop failures — pre-existing

---

## Test Coverage

| Component | Tests | Result |
|-----------|-------|--------|
| MockLLM | 6 | ✅ All pass |
| telemetry_repo | 3 | ✅ All pass |
| LLMCallTracker | 4 | ✅ All pass |
| calculate_cost | 3 | ✅ All pass |
| **Total** | **16** | **✅ 16/16** |

---

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| Mock LLM streams all 9 golden files correctly | ✅ All scenarios available via `list_scenarios()` |
| Delay profiles work (instant <200ms, l3 ≥1200ms) | ✅ Verified in timing tests |
| Telemetry migration runs cleanly | ✅ Migration 006 runs cleanly |
| Events recorded with all fields | ✅ `test_record_event_with_all_fields` |
| Stats aggregation returns correct aggregates | ✅ `test_get_aide_stats_aggregates` |
| Cost calculation matches Anthropic pricing | ✅ 3 cost tests pass |
| Mock/real toggle works via `USE_MOCK_LLM` env var | ✅ `get_llm()` returns `MockLLM` when set |

---

## Next Steps

- **Phase 1.5** Signal Ear — signal-cli-rest-api Docker container, webhook adapter, phone-number linking
- **Phase 1.7** Reliability — error handling, retry logic for L2/L3 failures, R2 upload retry
- Phase 0c infrastructure feeds directly into Phase 1 WebSocket handler:
  ```
  message → get_llm() → LLMCallTracker.start() → stream() → mark_first_content()
           → reducer → set_reducer_stats() → tracker.finish() → telemetry persisted
  ```
