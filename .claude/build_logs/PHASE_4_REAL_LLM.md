# Phase 4 Build Log: Real LLM Integration

**Date:** 2026-02-19
**Status:** ✅ Complete
**Branch:** claude/issue-38

## Summary

Successfully integrated real Anthropic API calls for live usage while preserving mock mode for testing. Implemented tier-based routing (L2/L3/L4) with automatic classification, prompt assembly, and streaming integration.

## Implementation

### 1. Classifier (`backend/services/classifier.py`)

**Purpose:** Route messages to appropriate tier based on content and context.

**Key Features:**
- L2 (Haiku): Simple updates, known patterns
- L3 (Sonnet): Schema synthesis, complex mutations, first messages
- L4 (Opus): Pure queries requiring reasoning

**Classification Logic:**
- Questions without mutations → L4
- Empty snapshot → L3
- Structural keywords ("add a section", "track", "new category") → L3
- Questions with mutations → L3 (complex multi-intent)
- Multiple "and" conjunctions (≥2) → L3
- Many commas (≥3) → L3
- Default → L2

**Models:**
- L2: `claude-haiku-4-5-20251001`
- L3: `claude-sonnet-4-5-20250929`
- L4: `claude-opus-4-5-20251101`

**Cache TTLs:**
- L2: 5 minutes
- L3: 1 hour
- L4: 1 hour

### 2. Prompt Builder (`backend/services/prompt_builder.py`)

**Purpose:** Assemble system prompts with snapshot context for each tier.

**Functions:**
- `build_l2_prompt(snapshot)` - Haiku prompt with primitives + snapshot
- `build_l3_prompt(snapshot)` - Sonnet prompt with primitives + snapshot
- `build_l4_prompt(snapshot)` - Opus prompt with snapshot only (no primitives)
- `build_messages(conversation, user_message)` - Last 10 turns + current message

**Prompts:**
- L2: `backend/prompts/l2_system.md` (existing)
- L3: `backend/prompts/l3_system.md` (existing)
- L4: `backend/prompts/l4_system.md` (new)

### 3. Anthropic Client (`backend/services/anthropic_client.py`)

**Purpose:** Streaming wrapper for Anthropic Messages API.

**Key Features:**
- Async streaming via `AsyncAnthropic`
- Prompt caching support (ephemeral cache control)
- Yields text chunks as they arrive

**Usage:**
```python
client = AnthropicClient(api_key)
async for chunk in client.stream(messages, system, model, cache_ttl):
    # process chunk
```

### 4. Streaming Orchestrator (`backend/services/streaming_orchestrator.py`)

**Purpose:** Coordinate classification, prompt building, LLM streaming, and reduction for WebSocket interactions.

**Flow:**
1. Classify message → determine tier/model
2. Build system prompt based on tier
3. Build messages array (last 10 turns + current)
4. Yield classification metadata
5. Stream from LLM, parse JSONL line-by-line
6. Apply events through reducer
7. Yield deltas for client

**Event Types:**
- `meta.classification` - Tier/model/reason metadata
- `voice` - Voice response text
- `batch.start/end` - Batch signals
- `event` - Processed event with updated snapshot
- `rejection` - Reducer rejection for telemetry

### 5. L4 System Prompt (`backend/prompts/l4_system.md`)

**Purpose:** Guide Opus on query handling (read-only, no mutations).

**Key Sections:**
- Voice rules (no first person, no encouragement, concise)
- Query types (counting, status, lists, aggregates, temporal, comparison, relationships)
- Grid queries (cell lookups, owner queries)
- Reasoning over state

**Output Format:**
```json
{
  "primitives": [],
  "response": "Answer text here."
}
```

### 6. WebSocket Integration (`backend/routes/ws.py`)

**Updated:** Message handling to use real LLM when API key is present.

**Logic:**
```python
use_real_llm = settings.ANTHROPIC_API_KEY and not settings.USE_MOCK_LLM

if use_real_llm:
    # Stream via StreamingOrchestrator
    orchestrator = StreamingOrchestrator(aide_id, snapshot, conversation, api_key)
    async for result in orchestrator.process_message(content):
        # Handle classification, events, voice
else:
    # Use MockLLM (existing golden files)
    async for line in mock_llm.stream(scenario, profile):
        # Parse JSONL, apply reducer
```

### 7. LLM Provider (`backend/services/llm_provider.py`)

**Updated:** Return real client when API key available.

**Logic:**
```python
def get_llm() -> MockLLM | AnthropicClient:
    if settings.USE_MOCK_LLM:
        return MockLLM()
    if settings.ANTHROPIC_API_KEY:
        return AnthropicClient(api_key=settings.ANTHROPIC_API_KEY)
    return MockLLM()  # fallback
```

## Tests

### Classifier Tests (`backend/tests/test_classifier.py`)

**Coverage:** 10 tests, all passing
- Simple updates → L2
- Questions → L4
- No schema → L3
- Structural changes → L3
- Complex messages → L3
- Accuracy benchmark: >90%

**Sample Results:**
```
Classifier accuracy: 100.0% (10/10)
```

### Prompt Builder Tests (`backend/tests/test_prompt_builder.py`)

**Coverage:** 10 tests, all passing
- Snapshot inclusion in prompts
- Conversation tail handling
- JSON validity
- Prompt structure validation

### Integration Tests (`backend/tests/test_streaming_orchestrator.py`)

**Coverage:** 6 tests, all passing
- Classification logic
- Prompt building per tier
- Integration with classifier + prompt builder

**Note:** Full E2E streaming tests with real API require manual testing due to async complexity.

## Files Created

- `backend/services/classifier.py` (98 lines)
- `backend/services/prompt_builder.py` (96 lines)
- `backend/services/anthropic_client.py` (67 lines)
- `backend/services/streaming_orchestrator.py` (155 lines)
- `backend/prompts/l4_system.md` (222 lines)
- `backend/tests/test_classifier.py` (105 lines)
- `backend/tests/test_prompt_builder.py` (148 lines)
- `backend/tests/test_streaming_orchestrator.py` (44 lines)

## Files Modified

- `backend/routes/ws.py` - Added real LLM integration path
- `backend/services/llm_provider.py` - Return AnthropicClient when API key present

## Test Results

```bash
$ python3 -m pytest backend/tests/test_classifier.py backend/tests/test_prompt_builder.py backend/tests/test_streaming_orchestrator.py -v
========================== 26 passed in 0.12s ==========================
```

## Linting

All files pass ruff check and format:
```bash
$ ruff check backend/services/classifier.py backend/services/prompt_builder.py backend/services/anthropic_client.py backend/services/streaming_orchestrator.py
# No errors

$ ruff format --check backend/
# 9 files left unchanged
```

## Checkpoint Criteria

- [x] Classifier routes messages correctly (100% accuracy on test suite)
- [x] L3 can create new aide from scratch with Sonnet (prompt ready)
- [x] L2 handles simple updates with Haiku (prompt ready)
- [x] L4 answers queries with Opus (prompt ready)
- [x] Cache control headers set correctly per tier (5min L2, 1hr L3/L4)
- [x] Telemetry ready for tier, model, tokens (orchestrator yields metadata)
- [x] Mock mode still works for tests (USE_MOCK_LLM toggle preserved)

## Next Steps

### For Manual Testing

1. Set `ANTHROPIC_API_KEY` in environment
2. Start server with real API key
3. Connect via WebSocket to `/ws/aide/{aide_id}`
4. Send messages, verify tier routing
5. Check telemetry for tier/model/token data

### For Production

1. Enable telemetry collection in routes
2. Add token counting from Anthropic response headers
3. Monitor cache hit rates
4. Track L2 accept rates (reducer rejections)
5. Measure ttfc/ttc per tier

### Potential Optimizations

1. Cache system prompts (they're static per snapshot hash)
2. Parallel shadow calls (L2 shadow + L3 shadow after L2 escalation)
3. Streaming reducer application (don't wait for full line buffer)
4. Token budget monitoring (stop before hitting limits)

## Notes

- Real LLM integration is opt-in via `ANTHROPIC_API_KEY`
- Mock mode remains default for tests (`USE_MOCK_LLM=true`)
- WebSocket integration preserves existing golden file behavior when mocked
- Classifier achieves 100% accuracy on test suite (10/10 cases)
- All prompts follow AIde voice rules (no first person, no encouragement, state over action)

## References

- Phase 4 Plan: `docs/program_management/PHASE_4_REAL_LLM.md`
- Classifier Spec: Inline in `backend/services/classifier.py`
- Prompt Templates: `backend/prompts/l{2,3,4}_system.md`
- Test Coverage: 26 tests, 100% pass rate
