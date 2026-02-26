# Build Log: Prompt System Integration

**Date:** 2026-02-25
**Branch:** claude/issue-65
**Status:** ✅ Complete

## Summary

Integrated the eval-validated prompt architecture from `evals/scripts/` into production. The new system uses:
- Shared prefix + tier-specific instructions pattern
- Anthropic cache optimization (cache_control on content blocks)
- Rule-based tier classifier (100% accuracy on 63 multi-turn scenarios)
- Dynamic calendar context for date-aware prompts

## Changes Made

### 1. Prompt Files Migration

Copied eval-validated prompt files to production:
- `backend/prompts/shared_prefix.md` (~200 lines) - Voice, format, primitives, entity tree
- `backend/prompts/l2_tier.md` (~180 lines) - L2 mutation rules
- `backend/prompts/l3_tier.md` (~160 lines) - L3 structural rules
- `backend/prompts/l4_tier.md` (~110 lines) - L4 query rules

Removed old prompt files:
- `backend/prompts/l2_system.md`
- `backend/prompts/l3_system.md`
- `backend/prompts/l4_system.md`
- `backend/prompts/primitive_schemas.md` (content moved to shared_prefix)

### 2. Core Services Updates

**`backend/services/prompt_builder.py`** - Complete rewrite
- Added `build_system_blocks()` - Returns content blocks with cache_control
- Added `_build_calendar_context()` - Dynamic date context generation
- Template variable support: `{{current_date}}`, `{{calendar_context}}`
- Cache strategy: shared prefix (ephemeral), tier block (ephemeral), snapshot (uncached)
- Maintained backward-compatible flat string builders for tests: `build_l2_prompt()`, `build_l3_prompt()`, `build_l4_prompt()`

**`backend/services/tier_classifier.py`** - New file
- Rule-based classifier with 100% accuracy on 63 eval scenarios
- Decision tree: structural keywords → L3, questions → L4, first turn → L3, default → L2
- Domain-specific patterns for budget/quotes/tasks
- Multi-item creation detection (3+ comma items)

**`backend/services/anthropic_client.py`** - Updated
- `stream()` method now accepts `str | list[dict[str, Any]]` for system parameter
- Backward-compatible with legacy cache_ttl parameter
- Direct passthrough of content blocks to API

**`backend/services/streaming_orchestrator.py`** - Updated
- Replaced `classify()` with `classify_tier()`
- Uses `build_system_blocks()` instead of individual prompt builders
- Removed dependency on `TIER_CACHE_TTL` (now handled by content blocks)
- Simplified classification metadata (removed reason field)

**`backend/services/l2_compiler.py`** - Updated
- Removed direct prompt file loading
- Uses `build_l2_prompt()` from prompt_builder

**`backend/services/l3_synthesizer.py`** - Updated
- Removed direct prompt file loading
- Uses `build_l3_prompt()` from prompt_builder

### 3. Test Updates

**`backend/tests/test_prompt_builder.py`** - Updated
- Changed assertions from "L2 System Prompt" → "L2 (Compiler)", "aide-prompt-v3.1"
- Changed assertions from "L3 System Prompt" → "L3 (Architect)"
- Changed assertions from "L4 System Prompt" → "L4 (Analyst)"
- Updated conversation tail size expectations (10 → 5)
- Fixed assertions for cache_control in last tail message

**`backend/tests/test_streaming_orchestrator.py`** - Updated
- Updated prompt assertions to match new v3.1 markers

## Architecture Notes

### Cache Strategy

```
┌─────────────────────────────┐
│  shared_prefix.md           │  cache_control: ephemeral
│  (~2,500 tokens)            │  — shared across L2/L3/L4
│                             │
│  - Voice rules              │
│  - Output format (JSONL)    │
│  - Primitives reference     │
│  - Entity tree structure    │
│  - Message classification   │
├─────────────────────────────┤
│  l{N}_tier.md               │  cache_control: ephemeral
│  (~500-800 tokens)          │  — tier-specific
│                             │
│  - Tier role & rules        │
│  - Escalation triggers      │
│  - Examples                 │
├─────────────────────────────┤
│  Snapshot JSON              │  no cache (changes every turn)
│  (~100-500 tokens)          │
└─────────────────────────────┘
```

**Benefits:**
1. Shared prefix cached for 1 hour, saves ~2,500 tokens/call across all tiers
2. Tier blocks cached per-tier, saves ~500-800 tokens
3. Conversation tail breakpoint saves context tokens
4. Snapshot uncached (changes every mutation)

### Tier Classifier Decision Tree

1. Structural keywords (create, track, reorganize) → L3
2. Questions (?, query starters, analysis requests) → L4
3. No entities exist → L3 (first turn)
4. Budget/quotes/tasks introduction (empty tables) → L3
5. Multi-item creation (3+ comma items) → L3
6. Default → L2 (routine mutations)

## Test Results

```bash
# Prompt builder tests
backend/tests/test_prompt_builder.py::test_l2_prompt_includes_snapshot PASSED
backend/tests/test_prompt_builder.py::test_l3_prompt_includes_snapshot PASSED
backend/tests/test_prompt_builder.py::test_l4_prompt_includes_snapshot PASSED
backend/tests/test_prompt_builder.py::test_messages_includes_conversation_tail PASSED
backend/tests/test_prompt_builder.py::test_messages_with_short_conversation PASSED
backend/tests/test_prompt_builder.py::test_messages_with_empty_conversation PASSED
backend/tests/test_prompt_builder.py::test_snapshot_json_is_valid PASSED
backend/tests/test_prompt_builder.py::test_l2_prompt_structure PASSED
backend/tests/test_prompt_builder.py::test_l3_prompt_structure PASSED
backend/tests/test_prompt_builder.py::test_l4_prompt_structure PASSED

# Streaming orchestrator tests
backend/tests/test_streaming_orchestrator.py::test_classification_logic_no_schema PASSED
backend/tests/test_streaming_orchestrator.py::test_classification_logic_question PASSED
backend/tests/test_streaming_orchestrator.py::test_classification_logic_simple_update PASSED
backend/tests/test_streaming_orchestrator.py::test_prompt_building_l2 PASSED
backend/tests/test_streaming_orchestrator.py::test_prompt_building_l3 PASSED
backend/tests/test_streaming_orchestrator.py::test_prompt_building_l4 PASSED

# All backend tests: 207 passed
```

## Validation

### Linting & Formatting
```bash
ruff check backend/ && ruff format --check backend/
# All checks passed!
```

### Classifier Accuracy
The rule-based classifier achieves 100% accuracy on 63 multi-turn eval scenarios (validated in evals/scripts/).

### Next Steps for Validation

To validate in production against eval scenarios:
```bash
cd evals/scripts
python eval_multiturn.py --save
```

Expected: 63/63 classifier accuracy, >0.95 avg score across all scenarios.

## Files Changed

| File | Lines Changed | Notes |
|------|--------------|-------|
| `backend/prompts/shared_prefix.md` | +200 | New from evals |
| `backend/prompts/l2_tier.md` | +180 | New from evals |
| `backend/prompts/l3_tier.md` | +160 | New from evals |
| `backend/prompts/l4_tier.md` | +110 | New from evals |
| `backend/prompts/l2_system.md` | -80 | Removed |
| `backend/prompts/l3_system.md` | -100 | Removed |
| `backend/prompts/l4_system.md` | -60 | Removed |
| `backend/prompts/primitive_schemas.md` | -150 | Removed |
| `backend/services/prompt_builder.py` | ~180 | Complete rewrite |
| `backend/services/tier_classifier.py` | +143 | New file |
| `backend/services/anthropic_client.py` | ~10 | Type signature update |
| `backend/services/streaming_orchestrator.py` | ~15 | Integration updates |
| `backend/services/l2_compiler.py` | ~5 | Use prompt_builder |
| `backend/services/l3_synthesizer.py` | ~5 | Use prompt_builder |
| `backend/tests/test_prompt_builder.py` | ~20 | Updated assertions |
| `backend/tests/test_streaming_orchestrator.py` | ~10 | Updated assertions |

**Net change:** +600 lines (mostly new prompts), improved token efficiency, 100% classifier accuracy

## Rollback Plan

If issues arise:
1. Revert to commit before this PR
2. Old prompt files are preserved in git history
3. Streaming orchestrator still supports legacy path via `classify()` in classifier.py

## Performance Impact

**Expected token savings per call:**
- Shared prefix cache: ~2,500 tokens saved (shared across all tiers)
- Tier block cache: ~500-800 tokens saved
- Conversation tail cache: ~200-500 tokens saved (depending on history)
- **Total: ~3,200-3,800 tokens saved per API call after first call**

**Cost reduction:** ~75% reduction in input token costs after cache warmup

## Deployment Notes

- No database migrations required
- No environment variable changes
- Backward compatible with existing orchestrator paths
- Cache warmup happens automatically on first API call per tier
- Cache duration: 1 hour (Anthropic ephemeral cache TTL)

---

**Built by:** Claude Sonnet 4.5
**Spec:** docs/eng_design/specs/prompt_integration_spec.md
