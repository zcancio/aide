# Prompt v3.0 — Migration Guide

## Summary

Complete rewrite of all 3 tier prompts from standalone files to shared-prefix architecture. Aligns deployed prompts with v2.1 engineering spec, fixes entity model mismatch, and resolves L4 output format bug.

## File Changes

| Old File | New File(s) | Notes |
|----------|------------|-------|
| `l2_system.md` | `shared_prefix.md` + `l2_tier.md` | Split into shared + tier-specific |
| `l3_system.md` | `shared_prefix.md` + `l3_tier.md` | Split into shared + tier-specific |
| `l4_system.md` | `shared_prefix.md` + `l4_tier.md` | Split into shared + tier-specific |
| `primitive_schemas.md` | (removed) | Primitives now inline in shared prefix |
| `prompt_builder.py` | `prompt_builder.py` | Updated to compose shared + tier |
| `eval_0a.py` | `eval_v3.py` | Rewritten: checks + cache validation |

## What Changed and Why

### 1. Shared Prefix (new)

**Before:** Each prompt duplicated voice rules, output format, and primitive references with slight inconsistencies (L2 said "JSONL format", L3 said "JSONL format — one JSON object per line, streamed as you generate", L4 said "JSON object in this exact format").

**After:** One `shared_prefix.md` with the canonical voice rules, JSONL format, primitive reference, display hints, emission order, entity ID rules, and prop schema. Identical text across all tiers. Changes in one place.

**Cache benefit:** The shared prefix text is the same bytes across L2/L3/L4 calls. While Anthropic caches are per-model (Haiku/Sonnet/Opus each cache separately), maintaining identical text means consistent behavior and single-file maintenance.

**Cache TTL:** All tiers use 1-hour TTL. No per-tier differentiation — simpler to reason about. Update `classifier.py` to set `cache_ttl = 3600` for L2 (was 300).

**Cache architecture:** The system prompt is split into two content blocks for Anthropic's API:
1. **Prefix + tier text** — cached (ephemeral, 1h). Static between calls. ~2,500 tokens saved.
2. **Snapshot (entityState)** — NOT cached. Changes every mutation, caching is wasted.

The conversation tail gets a cache breakpoint on its last message. Between rapid-fire user messages, only the new message is uncached input — the prior turns are identical and cache-hit. `build_system_blocks()` returns structured content blocks; the flat-string `build_l{N}_prompt()` wrappers remain for tests/mock mode.

### 2. Entity Tree Model (breaking change)

**Before:** L3 prompt used `collection.create` with schemas, `meta.update`, and `collection/entity_id` ref format. This is the Phase 1.3 data model.

**After:** Pure entity tree. `entity.create` with `parent` and `display`. No collections, no schemas, no field definitions. Entity shape inferred from props. Matches the v2 reducer (`reducer_v2.py`).

**Impact:** L3 will now emit `entity.create` with parent/display instead of `collection.create`. The streaming orchestrator's JSONL parser should already handle this (it parses `t` field and routes to reducer). Verify that the reducer handles the new format — check `reducer_v2.py` handler dispatch table.

### 3. L4 Output Format (bug fix → BUG-12)

**Before:** L4 prompt instructed the model to output `{"primitives": [], "response": "..."}` — a JSON blob. The streaming orchestrator expected JSONL lines or voice signals but received a JSON blob, resulting in empty query responses.

**After:** L4 outputs plain text. The prompt explicitly says "OVERRIDE: Ignore the JSONL output format above. Your output is plain text for the chat panel."

**Impact:** The streaming orchestrator needs to handle L4 responses differently — the raw text IS the response, not a JSONL stream to parse. Update the WebSocket handler:

```python
if tier == "L4":
    # L4 returns plain text, not JSONL
    full_text = ""
    async for chunk in client.stream(...):
        full_text += chunk
        yield {"type": "voice_chunk", "text": chunk}  # Stream to chat
    yield {"type": "voice", "text": full_text}
else:
    # L2/L3 return JSONL — parse line by line
    async for chunk in client.stream(...):
        # existing JSONL parsing logic
```

### 4. Escalation Format (alignment)

**Before:** L2 escalation was bare `{"t":"escalate"}` with no metadata. Server couldn't distinguish escalation reasons or route partial work.

**After:** Full escalation format: `{"t":"escalate","tier":"L3","reason":"structural_change","extract":"add a budget section"}`. Enables the server to:
- Keep mutations L2 already emitted
- Pass the `extract` to L3 as focused context
- Log escalation reasons for classifier tuning

### 5. Display Hint Rules (quality improvement)

**Before:** L3 had abstract guidance ("pick display hints deliberately"). Led to 8 players rendered as 8 individual cards instead of one table.

**After:** Explicit rules with negative examples:
- "CRITICAL: Multiple items with the same fields → table, NOT individual cards"
- "8 players with name/wins/points → ONE table with 8 rows"
- Children of tables use `display: "row"`

### 6. Voice Narration Cadence (quality improvement)

**Before:** No guidance on when to emit voice lines during L3 streaming.

**After:** "Emit a voice line every ~8-10 entity lines to narrate progress." With examples showing the narration style ("Ceremony details set. Building guest tracking.").

### 7. Conversation Tail Caching + Compression (token savings)

**Before:** `build_messages()` included last 10 turns raw, including full JSONL mutation responses. No caching on messages.

**After:** `build_messages()` defaults to 5 turns. Previous mutation responses are summarized as "[N operations applied]" to save tokens. Previous query responses (L4) are included in full since they're short text. A `cache_control` breakpoint is set on the last tail message — between rapid-fire messages, only the new user message is uncached input.

### 8. Removed primitive_schemas.md Dependency

**Before:** `prompt_builder.py` loaded and appended `primitive_schemas.md` (the Phase 1.3 format with `collection.create`, `field.add`, etc.) to L2 and L3 prompts. This contradicted the shared prefix's v2 primitive format.

**After:** Primitive reference is inline in the shared prefix using v2 abbreviated format. No separate file needed. L2/L3/L4 all see the same primitive definitions.

## Deployment Checklist

1. **Copy prompt files** to `backend/prompts/`:
   - `shared_prefix.md`
   - `l2_tier.md`
   - `l3_tier.md`
   - `l4_tier.md`

2. **Replace** `backend/services/prompt_builder.py` with the new version. Key change: use `build_system_blocks(tier, snapshot)` in the streaming orchestrator — it returns content blocks with `cache_control` for the Anthropic API. The flat `build_l{N}_prompt()` wrappers remain for tests.

3. **Update streaming orchestrator** to handle L4 plain text output (see section 3 above).

4. **Remove** old files (or keep as archive):
   - `backend/prompts/l2_system.md`
   - `backend/prompts/l3_system.md`
   - `backend/prompts/l4_system.md`
   - `backend/prompts/primitive_schemas.md` (if no longer referenced elsewhere)

5. **Update tests** in `test_prompt_builder.py`:
   - Change assertions to look for "aide-prompt-v3.0" instead of "L2 System Prompt"
   - Verify shared prefix appears in all tier prompts
   - Verify L4 prompt contains "OVERRIDE" text
   - Remove assertions about "## Primitive Schemas" section (now inline)

6. **Run eval scenarios** against the new prompts to validate:
   - First creation (graduation, poker) → correct entity tree structure
   - Simple update → L2 emits entity.update with correct ref
   - Escalation → L2 emits full escalation with reason/extract
   - Query → L4 returns plain text, appears in chat
   - Multi-intent → mutations + escalation in same response
   - Display hints → tables for multi-item groups, cards for singular entities

   ```bash
   # Quick smoke test (1 per tier, ~30s)
   python eval_v3.py --smoke

   # Full suite with golden file output
   python eval_v3.py --save-golden

   # Cache validation only (2 calls per tier, checks cache hits)
   python eval_v3.py --cache-only
   ```

## Token Budget (estimated)

| Section | Tokens | Cached? |
|---------|--------|---------|
| Shared prefix + tier | ~2,500 | ✅ 1h (ephemeral) |
| Snapshot (entityState) | ~500-3,000 | ❌ changes every mutation |
| Conversation tail (5 turns) | ~200 | ✅ ephemeral breakpoint on last tail msg |
| Current user message | ~50-200 | ❌ new every call |
| **L2 total (small aide)** | **~3,000** | **~2,500 cached** |
| **L3 total (small aide)** | **~3,400** | **~2,500 cached** |
| **L4 total (small aide)** | **~2,900** | **~2,500 cached** |

The streaming orchestrator should use `build_system_blocks()` (returns content block list with `cache_control`) instead of the flat-string wrappers when calling the Anthropic API.
