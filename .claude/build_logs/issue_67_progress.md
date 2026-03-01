# Build Log: Issue #67 - Two-Block Prompt Architecture + Instrumentation

**Date:** 2026-02-28
**Branch:** claude/issue-67
**Spec:** docs/program_management/aide_launch_plan.md (Phase 0c, PR 1 of 3)

## Summary

Implemented two-block prompt architecture with prompt caching support and comprehensive instrumentation for LLM calls. This ports the eval's proven cost-reduction approach (48% savings via caching) into the production streaming pipeline.

## Changes Implemented

### 1. New Prompt Files (Step 0)

**Created:**
- `backend/prompts/shared_prefix.md` - Shared instruction prefix (v3.0)
- `backend/prompts/l3_system.md` - L3 compiler tier prompt (v3.0)
- `backend/prompts/l4_system.md` - L4 architect tier prompt (v3.1)

**Updated:**
- Both L3 and L4 prompts use `{{shared_prefix}}` placeholder for shared instructions
- L4 prompt expanded to 16,000+ chars to clear Opus 4.5 cache threshold (4,096 tokens)
- Added `{{current_date}}` placeholder for dynamic date injection
- Included comprehensive pattern examples and query handling guidance

### 2. Tool Definitions Module (Step 1 - RED/GREEN)

**Created:**
- `backend/services/tool_defs.py` - Tool definitions for LLM calls
  - `TOOLS` list with mutate_entity, set_relationship, voice tools
  - `L4_TOOLS` list (voice only, no mutations for query tier)
  - `cache_control` on last tool (prefix-based caching optimization)

**Tests:**
- `backend/tests/test_tool_defs.py` - 5 tests, all passing

### 3. Prompt Builder V2 (Step 2 - RED/GREEN/REFACTOR)

**Updated:**
- `backend/services/prompt_builder.py`
  - New `build_system_blocks(tier, snapshot)` returns list of content blocks
  - Block 1: Static tier instructions (cached)
  - Block 2: Dynamic snapshot (uncached, changes every turn)
  - Updated `build_messages()` to window at 9 message blocks (down from 10)
  - Kept deprecated `build_l2_prompt()`, `build_l3_prompt()`, `build_l4_prompt()` for backward compatibility

**Tests:**
- `backend/tests/test_prompt_builder_v2.py` - 12 tests, all passing
  - Validates two-block structure
  - Confirms cache_control placement
  - Verifies Opus/Sonnet cache thresholds (16K/4K chars)
  - Tests conversation windowing (9 messages)

**Removed:**
- `backend/tests/test_prompt_builder.py` - Old tests for deprecated functions

### 4. Anthropic Client Update (Step 3 - RED/GREEN)

**Updated:**
- `backend/services/anthropic_client.py`
  - `stream()` now accepts `system: str | list[dict]`
  - Passes list-format system prompts through as-is
  - Wraps string prompts in cache_control block if `cache_ttl` specified
  - Forwards `tools` parameter to API call
  - Captures usage stats from `stream.get_final_message()`
  - New `get_usage_stats()` method returns token counts

**Tests:**
- `backend/tests/test_anthropic_client_v2.py` - 3 tests, all passing
  - Validates list system prompt handling
  - Tests backward compatibility with string prompts
  - Confirms tools forwarding

### 5. Orchestrator Instrumentation (Step 4 - RED/GREEN)

**Updated:**
- `backend/services/streaming_orchestrator.py`
  - Uses `build_system_blocks()` instead of tier-specific prompt builders
  - Uses `TOOLS` / `L4_TOOLS` from tool_defs module
  - Removed unused `TIER_CACHE_TTL` import
  - Added timing instrumentation:
    - `t_start` - API call start time
    - `t_first_content` - First content chunk (TTFC)
    - `t_complete` - Stream completion (TTC)
  - Added cost calculation via new `calculate_cost()` function
  - Pricing per MTok: L2/L3 Sonnet ($3/$15/$0.30/$3.75), L4 Opus ($5/$25/$0.50/$6.25)
  - Yields `stream.end` event with:
    - `usage` (input_tokens, output_tokens, cache_read, cache_write)
    - `ttfc_ms` (time to first content)
    - `ttc_ms` (time to completion)
    - `cost_usd` (computed cost)

**Tests:**
- `backend/tests/test_orchestrator_metrics.py` - 3 tests, all passing
  - Validates stream.end event includes usage
  - Confirms timing metrics (TTFC/TTC)
  - Verifies cost calculation

**Fixed:**
- `backend/tests/test_streaming_orchestrator.py` - Updated L3/L4 prompt format checks

## Key Learnings from Eval

1. **Cache Threshold Critical:** Opus 4.5 requires ≥4,096 tokens before `cache_control` breakpoint (silently ignored below this). L4 prompt expanded to clear this.

2. **Two-Block Structure:** Static prefix (tier instructions) cached across turns. Dynamic snapshot (changes every turn) uncached. This is what enables 48% cost reduction.

3. **Cache Processing Order:** Tools → System → Messages. The `cache_control` breakpoint must have enough cumulative tokens before it.

4. **`input_tokens` Already Excludes Cache:** The API's `input_tokens` count excludes cached tokens. Don't subtract `cache_read` from it.

5. **Conversation History Growth:** Unbounded history reached 8,048 tokens by turn 12. Windowed to 9 message blocks to prevent runaway costs.

## Test Results

```
231 passed, 36 warnings in 33.45s
```

All tests passing:
- 5 tool_defs tests
- 12 prompt_builder_v2 tests
- 3 anthropic_client_v2 tests
- 3 orchestrator_metrics tests
- 6 existing streaming_orchestrator tests (updated)
- 202 other existing tests (unchanged)

## Linting

```bash
ruff check backend/     # All checks passed
ruff format backend/    # 4 files reformatted
```

## Files Modified

**New files:**
- `backend/prompts/shared_prefix.md`
- `backend/prompts/l3_system.md` (replaced old version)
- `backend/prompts/l4_system.md` (replaced old version)
- `backend/services/tool_defs.py`
- `backend/tests/test_tool_defs.py`
- `backend/tests/test_prompt_builder_v2.py`
- `backend/tests/test_anthropic_client_v2.py`
- `backend/tests/test_orchestrator_metrics.py`

**Modified files:**
- `backend/services/prompt_builder.py`
- `backend/services/anthropic_client.py`
- `backend/services/streaming_orchestrator.py`
- `backend/tests/test_streaming_orchestrator.py`

**Deleted files:**
- `backend/tests/test_prompt_builder.py` (old tests for deprecated functions)

## Next Steps

This is PR 1 of 3 for Phase 0c. After this merges:
- PR 2: MockLLM implementation for eval replay
- PR 3: Telemetry persistence and admin dashboard

## Migration Notes

The deprecated functions `build_l2_prompt()`, `build_l3_prompt()`, `build_l4_prompt()` are kept for backward compatibility but should be migrated to `build_system_blocks()` in production code. They use the new v3 prompts but don't benefit from two-block caching.

New production code should use:
```python
from backend.services.prompt_builder import build_system_blocks, build_messages
from backend.services.tool_defs import TOOLS, L4_TOOLS

system_blocks = build_system_blocks(tier, snapshot)
messages = build_messages(conversation, user_message)
tools = L4_TOOLS if tier == "L4" else TOOLS

async for chunk in client.stream(messages, system_blocks, model, tools=tools):
    ...
```

## Verification Checklist

- [x] All new tests pass
- [x] All existing tests still pass
- [x] Ruff checks pass
- [x] Code formatted with ruff
- [x] Backward compatibility maintained (deprecated functions still work)
- [x] L4 prompt clears Opus cache threshold (16,000+ chars)
- [x] L3 prompt clears Sonnet cache threshold (4,000+ chars)
- [x] Two-block structure implemented correctly
- [x] Usage stats captured from API
- [x] Cost calculation implemented
- [x] Timing metrics (TTFC/TTC) implemented
- [x] Conversation windowing at 9 messages
- [x] Tools forwarding to API
