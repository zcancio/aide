# AIde Flight Recorder Design

## Overview

The flight recorder captures every AI turn — user message, LLM calls, primitives emitted, snapshot before/after — and ships it asynchronously to R2 as JSONL. This enables offline debugging, LLM quality analysis, and shadow model comparison without blocking the user response path.

---

## Goals

1. **Zero latency impact**: captures happen in-process, uploads happen in a background queue.
2. **Complete turn audit**: every turn is fully reproducible from the log (input + output + context).
3. **Shadow model comparison**: production model results recorded alongside shadow model results for quality benchmarking.
4. **JSONL format**: append-friendly, streamable, importable into any analytics tool.

---

## Architecture

```
User message
    │
    ▼
Orchestrator.process_message()
    │
    ├─► FlightRecorder.start_turn()   ← capture turn_id, user_msg, snapshot_before
    │
    ├─► L2/L3 (production call)
    │       └─► FlightRecorder.record_llm_call()   ← model, prompt, response, usage
    │
    ├─► Shadow L2/L3 (non-blocking, sequential after production)
    │       └─► FlightRecorder.record_shadow_call()  ← same fields, flagged as shadow=True
    │
    ├─► Reducer + Renderer
    │
    ├─► FlightRecorder.end_turn()     ← snapshot_after, primitives_applied, response_text
    │
    └─► FlightRecorderUploader.enqueue(record)   ← non-blocking
             │
             ▼
         asyncio.Queue
             │
             ▼  (background task, batching)
         R2: flight-logs/{aide_id}/{date}/{batch_id}.jsonl
```

---

## Data Format

Each line in the JSONL file is one complete turn record:

```json
{
  "turn_id": "turn_abc123",
  "aide_id": "uuid",
  "user_id": "uuid",
  "timestamp": "2026-02-17T12:00:00Z",
  "source": "web",
  "user_message": "got the milk",
  "snapshot_before": { ... },
  "snapshot_after": { ... },
  "llm_calls": [
    {
      "call_id": "call_1",
      "shadow": false,
      "model": "claude-3-5-haiku-20241022",
      "tier": "L2",
      "prompt": "...",
      "response": "...",
      "usage": { "input_tokens": 500, "output_tokens": 100 },
      "latency_ms": 450,
      "error": null
    },
    {
      "call_id": "call_2",
      "shadow": true,
      "model": "claude-sonnet-4-20250514",
      "tier": "L2",
      "prompt": "...",
      "response": "...",
      "usage": { "input_tokens": 500, "output_tokens": 95 },
      "latency_ms": 380,
      "error": null
    }
  ],
  "primitives_emitted": [ ... ],
  "primitives_applied": 3,
  "response_text": "Milk: done.",
  "total_latency_ms": 890
}
```

---

## Storage Layout

```
R2 bucket: aide-workspaces (reuse existing private bucket)

flight-logs/
  {aide_id}/
    {YYYY-MM-DD}/
      {batch_id}.jsonl    ← up to 100 turns per file
```

Batching reduces R2 API calls. Each batch is flushed when it reaches 100 records or 60 seconds elapse, whichever comes first.

---

## Model Configuration

### Production Models
- **L2**: `claude-3-5-haiku-20241022` (Haiku-class, ~$0.001/call for intent compilation)
- **L3**: `claude-sonnet-4-20250514` (Sonnet-class, ~$0.02/call for schema synthesis)

### Shadow Models (recorded, not applied)
- **L2 shadow**: `claude-sonnet-4-20250514` (higher-tier for quality comparison)
- **L3 shadow**: `claude-opus-4-6` (higher-tier for quality comparison)

Shadow calls use higher-tier models to measure the quality tradeoff of production model choices. They run sequentially after production calls complete and do not affect state or the user response.

---

## Implementation

### `backend/services/flight_recorder.py`

```python
class FlightRecorder:
    """Captures all data for one AI turn."""

    def start_turn(turn_id, aide_id, user_id, source, user_message, snapshot_before) -> None
    def record_llm_call(call_id, shadow, model, tier, prompt, response, usage, latency_ms, error) -> None
    def end_turn(snapshot_after, primitives_emitted, primitives_applied, response_text) -> TurnRecord
```

### `backend/services/flight_recorder_uploader.py`

```python
class FlightRecorderUploader:
    """Background task: batches TurnRecords and uploads to R2."""

    def enqueue(record: TurnRecord) -> None        # non-blocking, O(1)
    async def run() -> None                         # background loop
    async def flush() -> None                       # force flush (shutdown)
```

---

## Error Handling

- R2 upload failures: retry once with 2s delay, then drop (event log in DB is source of truth).
- Shadow call failures: log and continue — never fail the production turn.
- Queue full (>10,000 records): drop oldest, log warning.
- Serialization errors: log and skip the record.

---

## Privacy

- `user_message` and `snapshot` are stored as-is (same PII posture as existing DB).
- Flight logs are in the private `aide-workspaces` R2 bucket, accessible only with credentials.
- No PII scrubbing in v1 (same as conversation storage).

---

## Acceptance Criteria

- [ ] Each turn produces exactly one JSONL record uploaded to R2.
- [ ] Shadow calls are recorded but not applied to state.
- [ ] Upload failures do not delay or fail user responses.
- [ ] Background uploader starts with the app, stops cleanly on shutdown.
- [ ] Queue bounded at 10,000 records; drops oldest on overflow with log warning.
