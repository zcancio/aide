# aide Telemetry Design

> **Status:** Implemented
> **Implementation:** `backend/services/telemetry.py`, `backend/repos/telemetry_repo.py`, `backend/models/telemetry.py`

## Overview

The telemetry system captures metrics for every AI turn — user message, LLM calls, tool calls emitted, token usage, and timing. Data is persisted to PostgreSQL for real-time dashboards, cost tracking, and eval comparison.

---

## Goals

1. **Zero latency impact**: Telemetry writes happen after the user response is sent.
2. **Eval-compatible format**: Turn data matches the golden file format for quality benchmarking.
3. **Cost tracking**: Per-turn and per-aide cost calculation with cache awareness.
4. **Query support**: SQL-based queries for dashboards and debugging.

---

## Architecture

```
User message
    │
    ▼
StreamingOrchestrator.process_message()
    │
    ├─► TurnRecorder.start_turn()        ← capture turn_num, tier, model, message
    │
    ├─► LLM streaming
    │       ├─► TurnRecorder.mark_first_content()   ← TTFC
    │       ├─► TurnRecorder.record_tool_call()     ← each tool_use event
    │       └─► TurnRecorder.record_text_block()    ← text responses
    │
    ├─► TurnRecorder.set_usage()         ← tokens from API response
    │
    └─► TurnRecorder.finish()            ← persist to aide_turn_telemetry table
             │
             ▼
        PostgreSQL: aide_turn_telemetry
```

---

## Components

### LLMCallTracker

Quick metrics tracker for individual LLM calls. Used for the `telemetry` table (aggregate stats).

```python
class LLMCallTracker:
    def __init__(aide_id, user_id, tier, model, prompt_ver, message_id)
    def start() -> None                    # Record call start time
    def mark_first_content() -> None       # Record TTFC
    def set_tokens(input, output, cache_read, cache_write) -> None
    def set_kernel_stats(emitted, accepted, rejected) -> None
    def set_escalation(reason) -> None
    def set_error(error) -> None
    async def finish() -> int              # Persist to telemetry table
```

### TurnRecorder

Full turn recorder in eval-compatible format. Used for the `aide_turn_telemetry` table.

```python
class TurnRecorder:
    def __init__(aide_id, user_id)
    def start_turn(turn_num, tier, model, message) -> None
    def record_tool_call(name, input, timestamp_ms) -> None
    def record_text_block(text, timestamp_ms) -> None
    def set_system_prompt(prompt) -> None
    def mark_first_content() -> None
    def set_usage(input_tokens, output_tokens, cache_read, cache_creation) -> None
    def set_validation(passed, issues) -> None
    async def finish() -> UUID | None      # Persist to aide_turn_telemetry table
```

---

## Data Models

### TelemetryEvent (aggregate metrics)

```python
class TelemetryEvent(BaseModel):
    aide_id: UUID
    user_id: UUID | None
    event_type: str           # 'llm_call', 'direct_edit', 'undo', 'escalation'
    tier: str | None          # 'L3', 'L4'
    model: str | None         # 'haiku', 'sonnet', 'opus'
    prompt_ver: str | None
    ttfc_ms: int | None       # time to first content
    ttc_ms: int | None        # time to complete
    input_tokens: int | None
    output_tokens: int | None
    cache_read_tokens: int | None
    cache_write_tokens: int | None
    lines_emitted: int | None
    lines_accepted: int | None
    lines_rejected: int | None
    escalated: bool
    escalation_reason: str | None
    cost_usd: Decimal | None
    edit_latency_ms: int | None
    message_id: UUID | None
    error: str | None
```

### TurnTelemetry (eval-compatible format)

```python
class TurnTelemetry(BaseModel):
    turn: int
    tier: str
    model: str
    message: str
    tool_calls: list[dict]    # [{name, input, timestamp_ms?}]
    text_blocks: list[dict | str]
    system_prompt: str | None
    usage: TokenUsage
    ttfc_ms: int
    ttc_ms: int
    validation: dict | None   # {passed, issues}
```

### AideTelemetry (full aide export)

```python
class AideTelemetry(BaseModel):
    aide_id: str
    name: str
    scenario_id: str | None
    pattern: str | None
    timestamp: str
    turns: list[TurnTelemetry]
    final_snapshot: dict | None
```

---

## Storage

### PostgreSQL Tables

**telemetry** — Aggregate metrics per LLM call:

```sql
CREATE TABLE telemetry (
    id              SERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ DEFAULT NOW(),
    aide_id         UUID NOT NULL,
    user_id         UUID,
    event_type      TEXT NOT NULL,
    tier            TEXT,
    model           TEXT,
    prompt_ver      TEXT,
    ttfc_ms         INT,
    ttc_ms          INT,
    input_tokens    INT,
    output_tokens   INT,
    cache_read_tokens   INT,
    cache_write_tokens  INT,
    lines_emitted   INT,
    lines_accepted  INT,
    lines_rejected  INT,
    escalated       BOOLEAN DEFAULT FALSE,
    escalation_reason TEXT,
    cost_usd        NUMERIC(8,6),
    edit_latency_ms INT,
    message_id      UUID,
    error           TEXT
);

CREATE INDEX idx_telemetry_aide ON telemetry(aide_id, ts);
CREATE INDEX idx_telemetry_tier ON telemetry(tier, ts);
```

**aide_turn_telemetry** — Full turn data (eval-compatible):

```sql
CREATE TABLE aide_turn_telemetry (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aide_id         UUID NOT NULL REFERENCES aides(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    turn_num        INT NOT NULL,
    tier            TEXT NOT NULL,
    model           TEXT NOT NULL,
    message         TEXT NOT NULL,
    tool_calls      JSONB NOT NULL,
    text_blocks     JSONB NOT NULL,
    system_prompt   TEXT,
    usage           JSONB NOT NULL,
    ttfc_ms         INT NOT NULL,
    ttc_ms          INT NOT NULL,
    validation      JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_aide_turn_telemetry_aide ON aide_turn_telemetry(aide_id);
```

---

## Pricing

Cost calculation with cache-aware billing:

```python
_PRICING = {
    "haiku":  {"input": 0.25,  "output": 1.25,  "cache_read": 0.03},
    "sonnet": {"input": 3.00,  "output": 15.00, "cache_read": 0.30},
    "opus":   {"input": 15.00, "output": 75.00, "cache_read": 1.50},
}

def calculate_cost(model, input_tokens, output_tokens, cache_read_tokens):
    prices = _PRICING.get(model, _PRICING["sonnet"])
    regular_input = max(0, input_tokens - cache_read_tokens)
    return (
        (regular_input / 1_000_000) * prices["input"]
        + (cache_read_tokens / 1_000_000) * prices["cache_read"]
        + (output_tokens / 1_000_000) * prices["output"]
    )
```

---

## API Endpoint

**GET /api/aides/{aide_id}/telemetry**

Returns full telemetry for an aide in eval-compatible format:

```json
{
  "aide_id": "uuid",
  "name": "Poker League",
  "timestamp": "2026-02-17T12:00:00Z",
  "turns": [
    {
      "turn": 1,
      "tier": "L4",
      "model": "opus",
      "message": "Set up a poker league...",
      "tool_calls": [
        {"name": "mutate_entity", "input": {"action": "create", "id": "page", ...}},
        {"name": "voice", "input": {"text": "Poker league created."}}
      ],
      "text_blocks": [],
      "usage": {"input_tokens": 1200, "output_tokens": 450, "cache_read": 800},
      "ttfc_ms": 1250,
      "ttc_ms": 4500
    }
  ],
  "final_snapshot": {...}
}
```

---

## Error Handling

- **DB write failures**: Log and continue — telemetry is non-critical.
- **Missing usage data**: `TurnRecorder.finish()` returns `None` if usage not set.
- **Serialization errors**: Log and skip the record.

---

## Privacy

- `message` and `tool_calls` are stored as-is (same PII posture as conversation storage).
- Telemetry tables follow RLS — users can only query their own data.
- No PII scrubbing in v1 (same as conversation storage).

---

## Not Implemented

The original design included features that were descoped:

- **Shadow model calls**: Recording cheaper model outputs for comparison
- **R2 JSONL storage**: Batched uploads to R2 for archival
- **Background uploader**: Async queue with batching

These may be added in future iterations if needed for cost optimization or offline analysis.
