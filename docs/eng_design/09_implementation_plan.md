# AIde v2: Implementation Plan

> **Prerequisites:** [00 Overview](00_overview.md)
> **Status:** Pre-implementation

---

## Principles

1. **Each phase produces something testable.** No phase exists solely to "set up" the next one. Every checkpoint has a discrete output you can see, measure, or demo.
2. **Prove the design early.** Write prompts first, run them against real models, verify the JSONL output is clean and renderable. If the LLM can't produce what the spec describes, find out in week 1.
3. **Mock from real outputs.** Record the best real API responses as golden files. These become deterministic, free, fast mocks for all subsequent development and testing.
4. **Telemetry from day one.** If you can't measure it, you can't prove v2 is better than v1. Instrument before optimizing.
5. **Vertical slices, not horizontal layers.** Don't build "the whole reducer" then "the whole renderer." Build one complete path (entity.create → reduce → render → screen) and expand from there.

---

## Phase 0: Prove the Design (Week 1)

**Goal:** Prompts work. Real models produce valid JSONL. Golden files recorded. Reducer validates them.

This phase answers the most important question: **does the architecture hold up when a real LLM generates the output?**

### 0a: Prompts + Real API Runs

Write the prompts from [06 Prompts](06_prompts.md). Run them against real Anthropic models. Not in a product — just a script that assembles the prompt, calls the API, and saves the raw output.

```typescript
// prompt_test.ts — run against real API, save output
const response = await anthropic.messages.create({
  model: 'claude-haiku-4-5-20251001',
  system: buildPrompt('L2', graduationSnapshot),
  messages: [{ role: 'user', content: 'Aunt Linda RSVPed yes, bringing potato salad' }],
  stream: true,
})
saveToFile('golden/update_simple.jsonl', response)
```

**Run each scenario 3-5 times.** Observe variance. Pick the best output as the golden file. Note failure patterns (bad IDs, wrong display hints, schema errors) and tune the prompt.

**Scenarios to test:**

| Scenario | Tier | Input | What You're Validating |
|----------|------|-------|----------------------|
| First creation: graduation | L3 | "Plan Sophie's graduation party. Ceremony May 22 at UC Davis, 10am. ~40 guests. Coordinate food and travel." | Render order, display hint selection, voice narration, entity structure |
| First creation: poker league | L3 | "Set up a poker league. 8 players, biweekly Thursday, rotating hosts and snacks." | Different domain, schema inference |
| First creation: inspo board | L3 | "Make me an inspiration board for my kitchen renovation. I'm thinking warm wood tones, white countertops, open shelving." | Image entities, freeform mixed types, aesthetic display, minimal initial structure |
| Simple update | L2 | "Aunt Linda RSVPed yes" (with graduation snapshot) | Speed, minimal output, correct entity reference |
| Multi-field update | L2 | "Linda yes, bringing potato salad, driving from Portland" (with snapshot) | Multiple operations, relationship creation |
| Inspo board: add items | L2 | "Add this image [url]. Also add a note: brass hardware everywhere." (with inspo snapshot) | Image entity with src prop, text note entity, mixed types under same parent |
| Inspo board: add + categorize | L2 | "This one is for the backsplash area [url]" (with inspo snapshot) | Entity creation under specific section, user-driven categorization |
| Inspo board: reorganize | L3 | "Group everything by room — kitchen island, backsplash, pantry area" (with flat inspo snapshot) | Restructure freeform items into emergent categories, batch.start/end, entity.move |
| Escalation | L2 | "Add a seating chart with 5 tables" (with graduation snapshot) | L2 correctly emits escalate signal instead of guessing |
| Multi-intent | L2 | "Steve confirmed, do we have enough food?" (with graduation snapshot) | Mutations + query escalation in one stream |
| Query: negation | L4 | "Who hasn't RSVPed?" (with graduation snapshot, mix of yes/pending) | Accurate counting, shows work |
| Query: sufficiency | L4 | "Do we have enough food for everyone?" (with graduation snapshot) | Reasoning over entities |
| Query: inspo board | L4 | "Do I have enough backsplash ideas or should I keep looking?" (with inspo snapshot) | Reasoning over loosely structured data, subjective judgment |
| Restructure | L3 | "Organize the food by category" (with graduation snapshot) | batch.start/end, entity.move |
| Voice narration | L3 | First creation, observe voice lines | Interleaved every ~8-10 lines, helpful content |

### Why Each Eval Matters

**First creation: graduation party.** The flagship eval. Tests the full L3 pipeline from empty state to a complete, multi-section aide. Validates render order (meta → page → sections → children), display hint selection across types (card for ceremony, table for guests, checklist for todos), voice narration pacing, and the overall entity structure. If this doesn't work cleanly, nothing else matters. This is the eval you run first and run most often.

**First creation: poker league.** Proves the system generalizes beyond event coordination. The poker league has a different shape — a roster (table), a schedule (table), and standings (table with numeric fields). Tests whether the LLM picks appropriate display hints for a domain it wasn't explicitly prompted about. Also validates that entity IDs are domain-appropriate (player_mike, not guest_mike) — the LLM has to infer context from the user's description, not fall back to the graduation template.

**First creation: inspo board.** The opposite end of the spectrum from the graduation party. Tests image entities (`image` display with `src` props), freeform mixed entity types (images, text notes, color references as siblings under one parent), and aesthetic sensitivity. An inspo board that renders as a bulleted list has failed even if the data is correct. Also tests minimal initial structure — the user gave a vibe, not a schema. The LLM should create a loose collection, not over-scaffold with empty categories.

**Simple update.** The single most common interaction. Tests L2's core job: one user message, one entity mutation, minimal output. Validates that L2 finds the correct entity by name fuzzy match ("Aunt Linda" → `guest_linda`), emits only the fields that changed, and doesn't produce unnecessary voice lines. The golden file should be 1-2 lines. If L2 emits more than 3 lines for this, the prompt needs tuning.

**Multi-field update.** Tests L2 handling multiple operations from one natural language message. "Linda yes, bringing potato salad, driving from Portland" should produce an `entity.update` (RSVP), an `entity.create` (food item), and a `rel.set` (bringing relationship). Validates that L2 can decompose a compound message into discrete primitives and that relationships are created correctly with proper cardinality.

**Inspo board: add items.** Tests mixed entity creation — an image entity with a `src` prop alongside a text note entity, both under the same parent section. This is the only eval that exercises the `image` display type in an L2 context. Validates that L2 can create heterogeneous entities without being confused by the mixed types.

**Inspo board: add + categorize.** Tests user-driven categorization. The user isn't creating a new section — they're placing an item under an existing one by name. L2 needs to resolve "the backsplash area" to the correct parent entity and create the child there. This is a reference resolution test: can L2 match casual language to existing entity structure?

**Inspo board: reorganize.** The hardest structural test. Starting from a flat list of items dumped without organization, the LLM has to create new section entities, move existing items into them, and wrap the whole thing in `batch.start`/`batch.end` for atomic rendering. The categories ("kitchen island", "backsplash", "pantry area") don't exist yet — the LLM infers them from the user's instruction. Tests whether L3 can restructure without data loss and whether the batch signals produce clean atomic updates.

**Escalation.** Tests L2's self-awareness. "Add a seating chart with 5 tables" requires schema synthesis — new entity types, new structure, display hint decisions. L2 should recognize this is beyond its scope and emit `{"t":"escalate","tier":"L3","reason":"structural_change","extract":"add a seating chart with 5 tables"}` instead of guessing. A bad L2 would try to create a seating chart with wrong structure. A good L2 says "not my job" cleanly. This eval has a binary pass/fail: did L2 escalate, or did it guess?

**Multi-intent.** Tests the most natural user behavior — saying multiple things at once, mixing mutations and queries. "Steve confirmed, do we have enough food?" should produce an `entity.update` for Steve AND an `escalate` to L4 for the query. Validates that mutations are emitted first (so the escalated query sees post-mutation state) and that L2 doesn't try to answer the question itself.

**Query: negation.** Tests L4's accuracy on the most common failure mode for smaller models. "Who hasn't RSVPed?" requires scanning all guest entities, filtering for those without `rsvp: "yes"`, and listing them by name. Haiku gets this wrong — it miscounts, misses negation, or lists the wrong people. Opus should get it right every time. The golden file should include the specific names, not just a count. Validates L4's "show your work" behavior.

**Query: sufficiency.** Tests L4's ability to reason across entity branches. "Do we have enough food?" requires counting guests, counting food items, and making a judgment. Unlike the negation query, there's no exact right answer — L4 has to reason about ratios and provide a useful recommendation. Validates that L4 produces structured reasoning, not just a yes/no.

**Query: inspo board.** Tests L4 on subjective, loosely structured data. "Do I have enough backsplash ideas?" can't be answered by counting. L4 has to assess variety, coverage, and whether the collection feels complete. This is the hardest query eval — it tests whether L4 can provide useful judgment when the data isn't numeric and the question isn't precise. If L4 just counts items and says "you have 4 backsplash items," it's failed.

**Restructure.** Tests L3 on an existing aide — not first creation, but reorganization. "Organize the food by category" means creating new parent entities (mains, sides, desserts), moving existing food items under them, and wrapping in batch signals. Validates that L3 can modify structure without data loss, that moved entities retain their props, and that the batch produces a clean atomic render. Also tests whether L3 invents reasonable category names or just uses generic ones.

**Voice narration.** A quality eval, not a correctness eval. Run any first creation (graduation, poker, inspo) and observe the voice lines. Are they interleaved every ~8-10 entity lines? Are they under 100 characters? Do they narrate progress ("Ceremony details set. Building guest tracking.") rather than explain actions ("I'm now creating the guest list section")? Do they follow voice rules (no first person, no encouragement)? This eval is graded by reading, not by automated test.

**Checkpoint 0a:** You have 10+ golden JSONL files from real model output. You know which prompts work, which need tuning, and what the failure modes are. You've validated that the v2 JSONL schema is producible by real models.

### 0a Results (v2.0 → v2.1)

First run against real Sonnet/Haiku produced 11 golden files. Key findings:

**What worked (7/11 scenarios passed):**
- `update_simple`: 1 line, perfect. `update_multi`: 3 lines with relationship, perfect.
- `inspo_add_items`: 2 lines, correct display types. `inspo_reorganize`: batch, moves, cleanup — perfect.
- `query_negation`: correct 3 names, no first person. `query_sufficiency`: good reasoning, actionable.
- Voice lines: well-paced, under 100 chars, no first person. Emission order: correct across all scenarios.

**What failed (4 issues found, all fixed in v2.1 prompts):**

| Issue | Severity | Root Cause | Fix in v2.1 |
|-------|----------|-----------|-------------|
| Code fences on all JSONL output | Medium | Models wrap output in ` ```jsonl ``` ` despite instruction | Added "CRITICAL: No code fences" + parser strips fence lines |
| L2 escalation: built seating chart instead of escalating | High | "Do NOT create" too weak for Haiku | "NEVER create new sections. NEVER create entities with display hints not in snapshot." |
| L2 multi-intent: dropped mutation, only escalated | High | No explicit example of mutations-then-escalation | Added concrete example showing both outputs |
| Poker: players as 8 cards instead of table | Medium | Display hint guidance too abstract | Added negative example: "8 players → table, NOT 8 cards" |

**Performance (no caching):**

| Tier | Avg TTFC | Target | Status |
|------|---------|--------|--------|
| L2 (Haiku) | 555ms | <500ms | Close — caching will help |
| L3 (Sonnet) | 1,506ms | <1,000ms | Over — monitor with caching |
| L4 (Sonnet) | 1,596ms | <2,000ms | OK |

### v2.1 Results

Re-ran all 11 scenarios with v2.1 prompt fixes. All four targeted issues resolved:

| Fix | v2.0 | v2.1 | Status |
|-----|------|------|--------|
| Code fences | 2 failed lines per file | 0 failed lines (parser strips fences) | FIXED |
| L2 escalation | Built 6-entity seating chart (229 tokens) | Single escalation line (51 tokens) | FIXED |
| L2 multi-intent | Escalated only, dropped mutation | Mutation first, then escalation | FIXED |
| Poker display hints | 8 individual cards | 8 table display hints | FIXED |

**Performance comparison (v2.0 → v2.1):**

| Scenario | TTFC | TTC | Output Tokens |
|----------|------|-----|--------------|
| create_graduation | 1257→1405ms | 12.8→10.3s | 935→743 |
| create_poker | 1997→1094ms | 12.6→9.3s | 1068→768 |
| update_simple | 500→490ms | 735→739ms | 43→43 |
| escalation | 539→482ms | 1672→927ms | 229→51 |
| multi_intent | 657→521ms | 767→857ms | 34→55 |
| query_sufficiency | 1259→1466ms | 5820→3426ms | 199→71 |

Output tokens generally down, TTC generally down. The prompts are tighter.

**Observation:** `inspo_reorganize` used remove+recreate instead of `entity.move` (635 vs 358 tokens). Both strategies are valid — the data is preserved correctly either way. Could add "prefer entity.move over remove+recreate for restructuring" to L3 prompt, but not blocking.

**v2.1 golden files are the new baseline.** These are what the reducer and renderer should be built against.

### 0b: Reducer

Build the reducer. Pure function, no I/O.

Input: `(snapshot, event) → snapshot | rejection`

Implement in order:
1. `entity.create` (with parent validation)
2. `entity.update` (prop merge)
3. `entity.remove` (soft delete + descendants)
4. `entity.move`
5. `entity.reorder`
6. `rel.set` (with cardinality enforcement)
7. `rel.remove`
8. `style.set`, `style.entity`
9. `meta.set`, `meta.annotate`, `meta.constrain`

**Critical validation:** Feed the golden files from 0a through the reducer. Every line from a golden file should be accepted. If lines are rejected, either fix the prompt or fix the reducer — the golden files and the reducer must agree.

**Test suite:** Happy path + rejection tests for every primitive. Replay determinism test (same events → same snapshot). Golden file integration tests.

**Checkpoint 0b:** `reducer.test.ts` passes. All golden files reduce cleanly. You've proven: prompt → JSONL → reducer → valid snapshot.

### 0c: Mock LLM + Telemetry

**Mock LLM:** A function that streams golden files line-by-line with configurable delays.

```typescript
interface MockLLM {
  stream(scenario: string, opts?: { delayMs?: number }): AsyncIterable<string>
}

const DELAY_PROFILES = {
  instant: { perLineMs: 0 },                      // unit tests
  realistic_l2: { perLineMs: 200, thinkMs: 300 },  // simulates Haiku
  realistic_l3: { perLineMs: 150, thinkMs: 1500 }, // simulates Sonnet
  slow: { perLineMs: 500, thinkMs: 3000 },         // stress testing UX
}
```

**Mock/Real toggle:**

```typescript
const llm = config.useMocks ? new MockLLM() : new AnthropicLLM()
```

Tests always use mocks. Dev can toggle. Staging/prod use real API.

**Telemetry:** Instrument from the start.

| Metric | What It Measures |
|--------|-----------------|
| `ttfc` | Time to first content (ms from message send to first render delta) |
| `ttc` | Time to complete (ms from message send to stream end) |
| `reducer_accept_rate` | % of JSONL lines accepted per message |
| `reducer_reject_reasons` | Counted by reason code |
| `tier_distribution` | % of messages per tier |
| `escalation_rate` | % of L2 messages that escalate |
| `cache_hit_rate` | From Anthropic `cache_read_input_tokens` |
| `input_tokens` | Per call |
| `output_tokens` | Per call |
| `cost_per_message` | Computed from tokens × pricing |
| `direct_edit_count` | Direct edits vs AI edits per aide |
| `undo_count` | Per session |

Storage: `telemetry` table in Neon. Each row is one LLM call or direct edit.

**Checkpoint 0c:** Mock LLM streams golden files with realistic timing. Telemetry table exists and captures data from test runs.

---

## Phase 1: One Complete Vertical Slice (Week 2)

**Goal:** Type a message, see entities appear on screen. The full pipeline works end-to-end.

### The Slice

```
User types message
  → Server receives via WebSocket
  → Mock LLM streams golden file
  → Server parses each JSONL line
  → Reducer applies to snapshot
  → Server pushes delta to client via WebSocket
  → Client patches React state
  → AideEntity renders the entity
  → User sees it on screen
```

### What to Build

1. **WebSocket server** — accepts connections at `/ws/aide/{aide_id}`, receives messages, sends typed deltas.
2. **JSONL parser** — buffers stream until newline, expands abbreviated fields.
3. **Wire it together** — message → mock LLM → parser → reducer → WebSocket delta.
4. **React state store** — holds entity graph, exposes `useEntity(id)` and `useChildren(id)` hooks.
5. **AideEntity component** — recursive renderer with `resolveDisplay()`.
6. **FallbackDisplay** — the only display component needed initially. Renders any entity as key-value pairs.

**Checkpoint 1:** Open the app, type "plan a graduation party", see entities appear on screen one by one using mock responses. Telemetry logs ttfc and ttc. FallbackDisplay renders everything — ugly but functional.

---

## Phase 2: Display Components + Direct Edit (Week 3)

**Goal:** The page looks like a real product. Direct editing works.

### Display Components (build in this order)

1. **PageDisplay** — root container with editable title
2. **CardDisplay** — ceremony details rendered as a card
3. **TableDisplay** — guest list rendered as a table with editable cells
4. **ChecklistDisplay** — todos with working checkboxes
5. **SectionDisplay** — collapsible sections
6. **EditableField** — click-to-edit on all rendered values
7. **MetricDisplay, TextDisplay, ListDisplay, ImageDisplay** — fill in the rest

### Direct Edit Pipeline

1. User clicks a field → inline input opens.
2. User edits and commits (Enter/blur).
3. Client emits `entity.update` via WebSocket.
4. Server applies through reducer (same pipeline as AI edits).
5. Server pushes delta back. Client confirms.

**Checkpoint 2:** Open the app with a mock-created graduation aide. Click any field and edit it. Toggle a checkbox. See it update in <200ms. Telemetry tracks direct edit count and latency.

**Measurement:** Direct edit latency. Target: <200ms p95.

---

## Phase 3: Streaming + Progressive Rendering (Week 4)

**Goal:** The page builds itself progressively during JSONL streaming. Voice lines appear in chat.

### What to Build

1. **Streaming parser** — process lines as they arrive from mock LLM, not after stream completes.
2. **Mount animation** — 200ms fade-in on new entities.
3. **Voice line routing** — `voice` signals extracted from stream and displayed in chat panel.
4. **Batch handling** — `batch.start`/`batch.end` buffer and flush.
5. **Status indicators** — typing indicator during stream, "Stopped" on interrupt.
6. **Interrupt** — Stop button cancels stream, keeps partial state.

**Checkpoint 3:** Watch the graduation aide build itself progressively with mock responses. Voice lines narrate in chat. Hit Stop mid-stream, see partial state preserved.

**Measurement:** ttfc with streaming. Target: <500ms to first visible entity (mock with realistic delays).

---

## Phase 4: Real LLM Integration (Week 5)

**Goal:** Replace mocks with real Anthropic API calls for live usage. Mocks stay for tests.

### What to Build

1. **Anthropic streaming client** — connects to Messages API, streams response, feeds JSONL parser.
2. **Prompt assembly** — shared prefix + tier instructions + snapshot + conversation tail.
3. **Cache control headers** — correct TTLs per tier (5-min for L2, 1-hour for L3/L4).
4. **Classifier** — rule-based, routes messages to L2/L3/L4.
5. **Live prompt tuning** — iterate on prompts with real traffic. Record improved outputs as updated golden files.

**Checkpoint 4:** The full pipeline works with real Anthropic API. Create a graduation aide from scratch with Sonnet. Add guests with Haiku. Ask a question with Opus. All telemetry flowing.

**Measurements:**
- ttfc with real Sonnet (target: <1s)
- ttc for first creation (target: <4s)
- ttfc with real Haiku (target: <500ms)
- L2 reducer accept rate (target: >95%)
- Cache hit rate after 5+ turns (target: >80% for L2)

---

## Phase 5: Undo, Error Handling, Resilience (Week 5-6)

**Goal:** The system handles everything that can go wrong.

### What to Build

1. **Event log** — all events persisted with message_id batching.
2. **Undo/Redo** — event replay, message-level granularity, 20-batch stack.
3. **Retry** — undo + re-send on ↻ button.
4. **Malformed JSONL handling** — skip bad lines, continue stream.
5. **Consecutive rejection escalation** — 3+ rejections → cancel → escalate.
6. **Network drop recovery** — server finishes stream, client reconnects and fetches snapshot.
7. **R2 persistence** — save events.jsonl and snapshot.json after each mutation.
8. **R2 failure handling** — retry with backoff, hold in memory on failure.

**Checkpoint 5:** Create an aide, make 5 changes, undo 3, redo 1. Disconnect wifi mid-stream, reconnect, see completed page. Feed malformed golden file — observe partial success.

**Measurements:**
- Undo latency (target: <300ms)
- Recovery time after network drop (target: <2s)

---

## Phase 6: Escalation + Multi-Intent (Week 6)

**Goal:** The three-tier system works as designed.

### What to Build

1. **L2 → L3 escalation** — server detects escalation signal, re-routes to Sonnet, keeps applied mutations.
2. **L2 → L4 escalation** — query extraction, async Opus call, response appears in chat.
3. **Multi-intent rendering** — mutations render immediately, query answer arrives later.
4. **Classifier tuning** — run against test suite of 50+ messages, check routing accuracy.

**Checkpoint 6:** Send "Aunt Linda RSVPed yes, she's bringing potato salad, and do we have enough food?" See page update in <1.5s, then query answer in chat 3-5s later. Classifier accuracy >90%.

---

## Phase 7: Publish + Polish (Week 6-7)

**Goal:** Ship-ready. Published pages work. Performance meets targets.

### What to Build

1. **Server-side rendering** — entity graph to static HTML using same React components.
2. **Publish flow** — user hits Publish, server renders to R2, serves at `toaide.com/s/{slug}`.
3. **Auto-publish** — optionally re-render on every state change.
4. **Performance audit** — measure all targets, identify and fix gaps.
5. **Load testing** — simulate 10 concurrent aides, verify no degradation.

**Checkpoint 7:** Create an aide, publish it, open the public URL in incognito. See the page. Make a change, re-publish, see the update.

**Final Measurements Dashboard:**

| Metric | v1 Baseline | v2 Target | v2 Actual |
|--------|------------|-----------|-----------|
| First creation ttfc | ~10s | <1s | ? |
| First creation ttc | ~10s | <4s | ? |
| L2 update ttfc | ~3s | <500ms | ? |
| L2 update ttc | ~3s | <1.5s | ? |
| Direct edit latency | n/a | <200ms | ? |
| L4 query time | ~3s | <5s | ? |
| L2 reducer accept rate | n/a | >95% | ? |
| Cache hit rate (L2) | n/a | >80% | ? |
| Cost per free user/week | ~$0.50 | <$0.70 | ? |
| Undo latency | n/a | <300ms | ? |

---

## Mock Strategy Details

### Golden File Lifecycle

```
Week 1: Write prompts → run against real API → record best outputs → golden files v1
Week 5: Tune prompts with live traffic → record improved outputs → golden files v2
Ongoing: Regression tests always run against latest golden files
```

Golden files are version-controlled alongside the code. They're the contract between the prompt and the reducer — if a prompt change breaks golden file validation, you've introduced a regression.

### Recording Real Responses

```typescript
// Record mode: save real API response to file
const stream = anthropic.messages.stream(...)
const recorder = new GoldenFileRecorder('golden/create_graduation_v2.jsonl')
for await (const chunk of stream) {
  recorder.write(chunk)
  parser.feed(chunk)  // normal processing continues
}
recorder.close()
```

### Using Mocks in Tests

```typescript
// Unit test — instant, deterministic
test('entity.create produces valid snapshot', async () => {
  const events = loadGoldenFile('golden/update_simple.jsonl')
  const snapshot = events.reduce(reducer, emptySnapshot)
  expect(snapshot.entities.guest_linda.props.name).toBe('Aunt Linda')
})

// Integration test — realistic timing
test('progressive rendering shows entities one by one', async () => {
  const llm = new MockLLM('realistic_l3')
  const stream = llm.stream('create_graduation')
  // ... assert entities appear progressively
})

// E2E test — full pipeline with mock
test('full graduation aide creation', async () => {
  const llm = new MockLLM('realistic_l3')
  // ... type message, assert page builds, measure ttfc
})
```

---

## Telemetry Schema

```sql
CREATE TABLE telemetry (
  id            SERIAL PRIMARY KEY,
  ts            TIMESTAMPTZ DEFAULT NOW(),
  aide_id       TEXT NOT NULL,
  user_id       TEXT,
  event_type    TEXT NOT NULL,  -- 'llm_call', 'direct_edit', 'undo', 'escalation'
  tier          TEXT,           -- 'L2', 'L3', 'L4'
  model         TEXT,           -- 'haiku', 'sonnet', 'opus'
  prompt_ver    TEXT,           -- 'aide-prompt-v2.0'
  ttfc_ms       INT,
  ttc_ms        INT,
  input_tokens      INT,
  output_tokens     INT,
  cache_read_tokens   INT,
  cache_write_tokens  INT,
  lines_emitted     INT,
  lines_accepted    INT,
  lines_rejected    INT,
  escalated         BOOLEAN,
  escalation_reason TEXT,
  cost_usd      NUMERIC(8,6),
  edit_latency_ms INT,
  message_id    TEXT,
  error         TEXT
);

CREATE INDEX idx_telemetry_aide ON telemetry(aide_id, ts);
CREATE INDEX idx_telemetry_tier ON telemetry(tier, ts);
```

---

## Phase Summary

| Phase | Week | Output | Key Metric |
|-------|------|--------|------------|
| 0a | 1 | Prompts validated against real API, golden files recorded | Reducer accept rate on real output |
| 0b | 1 | Reducer passes all tests + golden file validation | Accept/reject correctness |
| 0c | 1 | Mock LLM + telemetry pipeline | Data flowing |
| 1 | 2 | Full vertical slice (message → screen) | ttfc with mock |
| 2 | 3 | Display components + direct edit | Direct edit <200ms |
| 3 | 4 | Streaming + progressive rendering | ttfc <500ms (mock) |
| 4 | 5 | Real LLM integration + classifier | ttfc <1s (real), accept >95% |
| 5 | 5-6 | Undo, errors, resilience | Undo <300ms |
| 6 | 6 | Escalation + multi-intent | Classifier accuracy >90% |
| 7 | 6-7 | Publish + polish | All targets met |

**Total: ~7 weeks to ship-ready.**
