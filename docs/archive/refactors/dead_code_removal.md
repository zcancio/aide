# Dead Code Removal — Engine Kernel v1 Cleanup

**Status:** Spec
**Date:** 2026-02-22

---

## Overview

The engine kernel contains legacy v1 code that is no longer used by the backend. The backend has fully migrated to:
- `reducer_v2.py` — flat entity hierarchy (no collections)
- `react_preview.py` — React component rendering
- `primitives.py` — validation (shared)

The v1 code (collections, views, blocks schema) remains in the codebase alongside 11 test files that test only v1 behavior. This spec defines the cleanup.

---

## Current State

### Files actively imported by backend

| File | Imports | Status |
|------|---------|--------|
| `reducer_v2.py` | `reduce`, `empty_snapshot` | ACTIVE |
| `react_preview.py` | `render_react_preview` | ACTIVE |
| `primitives.py` | `validate_primitive` | ACTIVE |
| `types.py` | `Event`, `ReduceResult` | ACTIVE (partial) |
| `mock_llm.py` | `MockLLM` | ACTIVE |
| `events.py` | (not imported) | ACTIVE (used by primitives) |

### Files NOT imported by backend (dead code)

| File | Lines | Purpose | Verdict |
|------|-------|---------|---------|
| `reducer.py` | ~400 | v1 reducer (collections/views/blocks) | DELETE |
| `renderer.py` | ~70 | v1 query helpers (apply_sort, resolve_view_entities) | DELETE |
| `assembly.py` | ~200 | v1 orchestration layer | DELETE |
| `postgres_storage.py` | ~100 | Unused storage adapter | DELETE |
| `smoke_test.py` | ~50 | Manual test script | DELETE |

### Generated bundles (engine/builds/)

| File | Lines | Status |
|------|-------|--------|
| `engine.py` | ~2800 | Not imported by backend | DELETE |
| `engine.js` | ~3500 | Not imported by frontend | DELETE |
| `engine.ts` | ~3500 | Not imported | DELETE |
| `engine.compact.js` | ~2000 | Not imported | DELETE |

### Tests using v1 reducer (11 files)

All in `engine/kernel/tests/tests_reducer/`:
- `test_reducer_cardinality.py`
- `test_reducer_cascade.py`
- `test_reducer_constraints.py`
- `test_reducer_grid_create.py`
- `test_reducer_happy_path.py`
- `test_reducer_rejections.py`
- `test_reducer_schema_evolution.py`
- `test_reducer_determinism.py`
- `test_reducer_idempotency.py`
- `test_reducer_round_trip.py`
- `test_reducer_walkthrough.py`

**Verdict:** DELETE — these test v1 code that no longer runs in production.

### Tests using v2 reducer (4 files) — KEEP

- `test_reducer_v2_entity.py`
- `test_reducer_v2_relationship.py`
- `test_reducer_v2_golden.py`
- `test_reducer_v2_style_meta_signals.py`

---

## types.py Cleanup

The `Snapshot` dataclass uses v1 schema:

```python
@dataclass
class Snapshot:
    collections: dict[str, Any]  # v1 — NOT USED
    views: dict[str, Any]        # v1 — NOT USED
    blocks: dict[str, Any]       # v1 — NOT USED
    relationships: list          # v1 format
    ...
```

The backend uses v2 snapshot shape from `reducer_v2.py`:

```python
{
    "meta": {...},
    "entities": {id: Entity},    # FLAT — v2
    "relationships": [...],
    "styles": {...},
    "_sequence": int,
}
```

**Action:** Either:
1. Delete the `Snapshot` dataclass (backend uses raw dicts)
2. Redefine `Snapshot` to match v2 schema

Recommendation: Delete it. The backend passes `dict[str, Any]` everywhere. Type hints using `Snapshot` in `types.py` are misleading since they describe v1.

### Types to KEEP

- `Event` — used by backend
- `ReduceResult` — used by reducer_v2
- `Warning` — used by reducer_v2
- ID/ref patterns and validation helpers — used by primitives
- `PRIMITIVE_TYPES` — used by primitives

### Types to DELETE (v1-only)

- `Snapshot` dataclass
- `Blueprint` — not used by backend
- `AideFile` — not used by backend
- `ApplyResult` — not used by backend
- `ParsedAide` — not used by backend
- `Escalation` — not used by backend (L2 uses inline dict)
- `BLOCK_TYPES` — v1 concept
- `VIEW_TYPES` — v1 concept

---

## __init__.py Cleanup

Current exports:

```python
from engine.kernel.assembly import AideAssembly        # DELETE
from engine.kernel.primitives import validate_primitive
from engine.kernel.reducer import empty_state, reduce, replay  # DELETE
from engine.kernel.renderer import (                   # DELETE
    apply_filter,
    apply_sort,
    resolve_view_entities,
    resolve_view_fields,
)
```

After cleanup:

```python
from engine.kernel.primitives import validate_primitive
from engine.kernel.reducer_v2 import empty_snapshot, reduce

__all__ = [
    "validate_primitive",
    "empty_snapshot",
    "reduce",
]
```

---

## tests_assembly/ Cleanup

The `tests_assembly/` directory exists but only contains `__init__.py` (no actual tests). Delete the directory.

---

## Execution Plan

### Phase 1: Delete dead files

```
DELETE engine/kernel/reducer.py
DELETE engine/kernel/renderer.py
DELETE engine/kernel/assembly.py
DELETE engine/kernel/postgres_storage.py
DELETE engine/kernel/smoke_test.py
DELETE engine/builds/  (entire directory)
DELETE engine/kernel/tests/tests_assembly/
DELETE engine/kernel/tests/test_postgres_storage.py
```

### Phase 2: Delete v1 tests

```
DELETE engine/kernel/tests/tests_reducer/test_reducer_cardinality.py
DELETE engine/kernel/tests/tests_reducer/test_reducer_cascade.py
DELETE engine/kernel/tests/tests_reducer/test_reducer_constraints.py
DELETE engine/kernel/tests/tests_reducer/test_reducer_grid_create.py
DELETE engine/kernel/tests/tests_reducer/test_reducer_happy_path.py
DELETE engine/kernel/tests/tests_reducer/test_reducer_rejections.py
DELETE engine/kernel/tests/tests_reducer/test_reducer_schema_evolution.py
DELETE engine/kernel/tests/tests_reducer/test_reducer_determinism.py
DELETE engine/kernel/tests/tests_reducer/test_reducer_idempotency.py
DELETE engine/kernel/tests/tests_reducer/test_reducer_round_trip.py
DELETE engine/kernel/tests/tests_reducer/test_reducer_walkthrough.py
```

### Phase 3: Clean up types.py

Remove v1-only types:
- `Snapshot`
- `Blueprint`
- `AideFile`
- `ApplyResult`
- `ParsedAide`
- `Escalation`
- `BLOCK_TYPES`
- `VIEW_TYPES`

### Phase 4: Update __init__.py

Replace v1 exports with v2:
- Remove `AideAssembly`, v1 `reduce`/`replay`/`empty_state`, renderer helpers
- Export `reduce`, `empty_snapshot` from `reducer_v2`

### Phase 5: Verify

```bash
# All backend tests pass
pytest backend/tests/ -v

# Remaining kernel tests pass
pytest engine/kernel/tests/ -v

# Lint clean
ruff check backend/ engine/

# No broken imports
python -c "from backend.main import app"
```

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Breaking import somewhere | Grep for all imports before deleting |
| Losing useful test patterns | v2 tests cover the active code path |
| Future need for v1 | Git history preserves everything |

---

## Line Count Impact

| Category | Lines Removed |
|----------|---------------|
| v1 reducer + renderer + assembly | ~670 |
| postgres_storage + smoke_test | ~150 |
| engine/builds/ | ~12,000 |
| v1 tests | ~2,000 |
| v1 types | ~100 |
| **Total** | **~15,000 lines** |

---

## Acceptance Criteria

- [ ] No dead files remain
- [ ] `__init__.py` exports only active code
- [ ] `types.py` contains only v2-compatible types
- [ ] All backend tests pass
- [ ] All remaining kernel tests pass (v2 suite)
- [ ] CI green
