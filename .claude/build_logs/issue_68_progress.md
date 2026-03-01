# Build Log: Issue #68 - Two-Pass Escalation (L3→L4→L3)

**Date:** 2026-02-28
**Issue:** Implement new architecture v3.0 (PR 2 of 3) - L3→L4→L3 Two-Pass Escalation
**Status:** ✅ COMPLETE

## Summary

Implemented a two-pass escalation system where L3 (Sonnet) can detect when it needs help from L4 (Opus), trigger an L4 pass to handle structural work or complex queries, and then retry with the updated snapshot.

## Implementation Overview

This PR implements the two-pass escalation pattern from the eval system (`evals/scripts/eval_multiturn.py`) into the production streaming orchestrator.

### Key Design Decisions

1. **Both L3 and L4 get full TOOLS** (`mutate_entity`, `set_relationship`, `voice`)
   - L4 needs mutation tools for first-message schema synthesis and escalation handling
   - Query-only behavior for L4 is enforced by the system prompt, not by tool restriction

2. **Temperature = 0 for both L3 and L4** for deterministic responses

3. **Escalation Detection**
   - **Signal 1:** L3 voice text contains phrases like "needs a new section", "needs structural", "escalat"
   - **Signal 2:** L3 creates structural containers (page/section/table/grid) — that's L4's job

4. **L4 sees original snapshot**, not the L3-mutated one (L3's mutations are discarded on escalation)

5. **L3 pass 2 sees L4's updated snapshot** (this is the point — L4 creates structure, L3 fills it in)

## Files Changed

### New Files (3)

1. **`backend/services/escalation.py`** (54 lines)
   - `needs_escalation(result)` — detects when L3 needs L4 help
   - Checks voice text for escalation phrases
   - Checks tool_calls for structural entity creation

2. **`backend/tests/test_escalation.py`** (117 lines)
   - 15 tests covering voice signal detection and structural creation detection
   - Tests case-insensitive matching, string vs dict text_blocks
   - Tests that card creation and updates don't trigger escalation

3. **`backend/tests/test_two_pass.py`** (275 lines)
   - 9 tests covering the full two-pass orchestration flow
   - Tests normal L3 (no escalation), voice escalation, structural creation escalation
   - Tests snapshot handling, usage aggregation, timing, meta events, tier labels

### Modified Files (1)

4. **`backend/services/streaming_orchestrator.py`** (~400 lines total, ~250 lines changed)
   - Added `_run_tier()` method to encapsulate single LLM call with result collection
   - Refactored `process_message()` to use `_run_tier()` and implement two-pass logic
   - Escalation flow: L3 → detect → L4 with original snapshot → L3 retry with L4 snapshot
   - Merges results: L4 tool_calls first, then L3
   - Aggregates usage (sums all three passes: initial L3 + L4 + retry L3)
   - TTFC from L4 pass (first visible), TTC spans all passes
   - Yields `meta.escalation` event when escalation occurs
   - Tier label shows `"L3->L4->L3"` in `stream.end`

## Test Results

### Step 1: Escalation Detection (RED → GREEN)

```bash
# RED: 15 tests fail (module doesn't exist)
pytest backend/tests/test_escalation.py -v
# ModuleNotFoundError: No module named 'backend.services.escalation'

# GREEN: Created escalation.py
pytest backend/tests/test_escalation.py -v
# ✅ 15 passed in 0.09s
```

### Step 2: Two-Pass Orchestration (RED → GREEN)

```bash
# RED: 9 tests fail (AttributeError: no _run_tier)
pytest backend/tests/test_two_pass.py -v
# AttributeError: ... does not have the attribute '_run_tier'

# GREEN: Updated streaming_orchestrator.py
pytest backend/tests/test_two_pass.py -v
# ✅ 9 passed in 0.27s (after fixing one test case)
```

### All Backend Tests (No Regressions)

```bash
pytest backend/tests/ -v
# ✅ 261 passed, 37 warnings in 33.98s
# Including our new 24 tests (15 escalation + 9 two-pass)
```

## Code Quality

### Linting

```bash
ruff check backend/
# ✅ All checks passed!

ruff format --check backend/
# ✅ 85 files already formatted
```

## Architecture Notes

### Two-Pass Flow

```
User message
    ↓
Classify → L3
    ↓
Run L3 (pass 1)
    ↓
needs_escalation?
    ├─ NO → Done (normal flow)
    └─ YES → Escalation flow:
         ↓
         1. Yield meta.escalation event
         2. Run L4 with original snapshot (temperature=0)
         3. Run L3 with L4's snapshot (pass 2, temperature=0)
         4. Merge results (L4 tool_calls + L3 tool_calls)
         5. Aggregate usage (all 3 passes)
         6. TTFC from L4, TTC spans all
         7. Tier label: "L3->L4->L3"
```

### Usage Aggregation (Example)

```
Initial L3 pass:  500 input,  100 output, 4590 cache_read
L4 pass:          800 input,   60 output, 5491 cache_read
L3 pass 2:        500 input,  100 output, 4590 cache_read
─────────────────────────────────────────────────────────
Total:           1800 input,  260 output, 14671 cache_read
```

### Timing Aggregation (Example)

```
Initial L3 pass:  TTFC=350ms, TTC=980ms   (discarded on escalation)
L4 pass:          TTFC=600ms, TTC=1500ms
L3 pass 2:        TTFC=300ms, TTC=900ms
─────────────────────────────────────────────────────────
Final:            TTFC=600ms (from L4), TTC=3380ms (980+1500+900)
```

## Edge Cases Handled

1. **Empty snapshot routes to L4 directly** (classifier logic) — no escalation needed
2. **Voice + tool_calls** — voice signal triggers escalation even if tool_calls present
3. **String vs dict text_blocks** — handles both formats
4. **Case-insensitive** — escalation phrases detected regardless of case
5. **Normal L3 work** — card creation, entity updates don't trigger escalation

## Dependencies

- **Requires PR 1:** Two-Block Prompt Architecture + Instrumentation
  - `build_system_blocks()` from `backend/services/prompt_builder.py`
  - `TOOLS` from `backend/services/tool_defs.py`
  - `calculate_cost()` in `streaming_orchestrator.py`

## Next Steps (PR 3)

This completes the two-pass escalation system. The next PR should focus on:
- Integration testing with real LLM calls
- Performance benchmarks (latency impact of two-pass)
- Escalation rate monitoring (what % of L3 calls escalate?)

## Checklist

- [x] Write `backend/tests/test_escalation.py` → 15 tests
- [x] Create `backend/services/escalation.py` → all tests pass
- [x] Write `backend/tests/test_two_pass.py` → 9 tests
- [x] Update `backend/services/streaming_orchestrator.py` → all tests pass
- [x] All existing tests pass (261 total, no regressions)
- [x] ruff check passes
- [x] ruff format passes
- [x] Build log written

---

**Build completed successfully at 2026-02-28**
