# AIde Flight Recorder + Shadow LLM Design

**Status:** Design
**Author:** Claude
**Date:** 2024-02-17

## Overview

Two interconnected features for observability and model comparison:

1. **Flight Recorder**: Capture comprehensive turn-by-turn data (user messages, LLM calls, primitives, snapshots) as JSONL files stored in R2
2. **Shadow LLM Calls**: Run comparison calls with different models sequentially after production calls to evaluate model performance

## Goals

- Full replay capability for debugging and analysis
- Compare model outputs without affecting production
- Non-blocking: logging must not delay user responses
- Privacy: logs stored securely in R2, not console

## Architecture

```
User Message
     │
     ▼
┌────────────────────────────────────────────────────────┐
│  Orchestrator                                          │
│  ┌─────────────────┐                                   │
│  │ FlightRecorder  │◄─── Created per turn              │
│  └────────┬────────┘                                   │
│           │                                            │
│     ┌─────▼─────┐                                      │
│     │  L2/L3    │──► Production call ──► Record        │
│     │ Services  │──► Shadow call ────► Record (seq)    │
│     └─────┬─────┘                                      │
│           │                                            │
│     ┌─────▼─────┐                                      │
│     │  Reducer  │──► Per-event records                 │
│     └─────┬─────┘                                      │
│           │                                            │
│  ┌────────▼────────┐                                   │
│  │ Enqueue upload  │──► Non-blocking                   │
│  └────────┬────────┘                                   │
└───────────┼────────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────────────────────┐
│  FlightRecorderUploader (background task)              │
│  - Queue records                                       │
│  - Buffer by aide_id/date                              │
│  - Batch upload to R2 every 30s or 10 records          │
└────────────────────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────────────────────┐
│  R2: flight-logs/{aide_id}/{date}/{batch}.jsonl        │
└────────────────────────────────────────────────────────┘
```

## Model Configuration

| Tier | Production Model | Shadow Model |
|------|------------------|--------------|
| L2 | claude-sonnet-4-20250514 | claude-3-5-haiku-20241022 |
| L3 | claude-opus-4-20250514 | claude-sonnet-4-20250514 |

Shadow calls run **sequentially** after production calls complete. Shadow results are recorded but never applied to state.

## Data Model

### TurnRecord (one JSON object per JSONL line)

```json
{
    "turn_id": "turn_abc123def456",
    "aide_id": "uuid",
    "user_id": "uuid",
    "timestamp": "2024-01-15T12:34:56Z",
    "turn_number": 5,

    "user_message": "add milk to the list",
    "has_image": false,
    "source": "web",

    "snapshot_before": { "...full state..." },
    "snapshot_after": { "...full state..." },

    "route_to": "L2",
    "route_reason": "standard message",

    "llm_calls": [
        {
            "call_id": "prod_abc123",
            "is_shadow": false,
            "tier": "L2",
            "model": "claude-sonnet-4-20250514",
            "system_prompt_hash": "a1b2c3d4e5f6",
            "raw_response": "...",
            "parsed_json": { "primitives": [...], "response": "..." },
            "token_usage": { "input_tokens": 1234, "output_tokens": 567 },
            "latency_ms": 1200,
            "error": null
        },
        {
            "call_id": "shadow_def456",
            "is_shadow": true,
            "tier": "L2",
            "model": "claude-3-5-haiku-20241022",
            "...same structure..."
        }
    ],

    "grid_input_primitives": [...],
    "grid_output_primitives": [...],
    "grid_error": null,

    "reducer_events": [
        {
            "event_type": "entity.create",
            "payload": { "collection": "items", "..." },
            "applied": true,
            "error": null,
            "warnings": []
        }
    ],

    "response_text": "Added milk.",

    "total_duration_ms": 1500,
    "phase_durations": {
        "llm": 1200,
        "grid": 10,
        "reducer": 50,
        "persist": 200
    },

    "error": null
}
```

### LLMCallRecord

| Field | Type | Description |
|-------|------|-------------|
| call_id | string | Unique ID for this call |
| is_shadow | bool | True if shadow call |
| tier | string | "L2" or "L3" |
| model | string | Full model ID |
| system_prompt_hash | string | SHA-256 hash (first 16 chars) |
| user_content_preview | string | First 500 chars of prompt |
| raw_response | string | Complete raw response |
| parsed_json | object? | Parsed JSON if successful |
| parse_error | string? | Error message if parsing failed |
| token_usage | object | {input_tokens, output_tokens} |
| latency_ms | int | Call duration in milliseconds |
| error | string? | Error message if call failed |

### ReducerEventRecord

| Field | Type | Description |
|-------|------|-------------|
| event_type | string | Primitive type (e.g., "entity.create") |
| payload | object | Primitive payload |
| applied | bool | True if reducer accepted |
| error | string? | Error message if rejected |
| warnings | string[] | Non-fatal warnings |

## File Structure

### New Files

```
backend/
├── services/
│   └── flight_recorder.py    # FlightRecorder + FlightRecorderUploader
```

### Modified Files

```
backend/
├── config.py                  # Add model config, feature flags
├── main.py                    # Start/stop uploader in lifespan
├── services/
│   ├── orchestrator.py        # Create recorder, capture data, enqueue
│   ├── l2_compiler.py         # Add recorder param, shadow calls
│   ├── l3_synthesizer.py      # Add recorder param, shadow calls
│   └── r2.py                  # Add upload_flight_log method
```

## Implementation Details

### FlightRecorder Class

```python
class FlightRecorder:
    """Accumulates turn data during processing."""

    def __init__(self, aide_id: UUID, user_id: UUID, turn_number: int):
        self.turn_id = f"turn_{uuid.uuid4().hex[:12]}"
        self.aide_id = str(aide_id)
        self.user_id = str(user_id)
        self.turn_number = turn_number
        self.timestamp = datetime.now(UTC).isoformat()
        self._llm_calls: list[LLMCallRecord] = []
        self._reducer_events: list[ReducerEventRecord] = []
        self._phase_times: dict[str, int] = {}
        self._start_time = time.perf_counter()
        # ... other fields initialized to defaults ...

    def record_llm_call(self, record: LLMCallRecord) -> None:
        """Record an LLM call (production or shadow)."""
        self._llm_calls.append(record)

    def record_reducer_event(self, event_type: str, payload: dict,
                             applied: bool, error: str | None = None) -> None:
        """Record a reducer event result."""
        self._reducer_events.append(...)

    def mark_phase(self, phase: str) -> None:
        """Mark end of a phase, recording elapsed time."""
        elapsed_ms = int((time.perf_counter() - self._start_time) * 1000)
        self._phase_times[phase] = elapsed_ms

    def to_json_line(self) -> str:
        """Serialize to single JSON line for JSONL."""
        return json.dumps(self._to_dict(), default=str) + "\n"
```

### FlightRecorderUploader Class

```python
class FlightRecorderUploader:
    """Background task: queue → buffer → batch upload to R2."""

    def __init__(self):
        self._queue: asyncio.Queue[TurnRecord] = asyncio.Queue(maxsize=1000)
        self._buffer: dict[str, list[str]] = {}  # key -> JSON lines
        self._buffer_size = 10        # Flush after N records
        self._flush_interval = 30     # Flush every N seconds
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        """Start background upload task."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    def stop(self) -> None:
        """Stop task and flush remaining."""
        self._running = False
        if self._task:
            self._task.cancel()

    def enqueue(self, recorder: FlightRecorder) -> None:
        """Queue for upload. Non-blocking, drops if queue full."""
        try:
            self._queue.put_nowait(recorder)
        except asyncio.QueueFull:
            pass  # Drop record if backed up

    async def _run_loop(self) -> None:
        """Background loop: drain queue, buffer, flush to R2."""
        last_flush = time.time()
        while self._running:
            # Drain queue with timeout
            # Add to buffer keyed by aide_id/date
            # Flush if buffer full or interval elapsed
            # Upload to R2 as JSONL batch
```

### Shadow Call Implementation

```python
# In l2_compiler.py and l3_synthesizer.py

async def compile(self, message, snapshot, recent_events,
                  flight_recorder: FlightRecorder | None = None):

    # 1. Production call
    start = time.perf_counter()
    result = await ai_provider.call_claude(
        model=settings.L2_PRODUCTION_MODEL,  # Sonnet
        system=self.system_prompt,
        messages=messages,
        max_tokens=4096,
    )
    latency_ms = int((time.perf_counter() - start) * 1000)

    # 2. Record production call
    if flight_recorder:
        flight_recorder.record_llm_call(LLMCallRecord(
            is_shadow=False,
            tier="L2",
            model=settings.L2_PRODUCTION_MODEL,
            raw_response=result["content"],
            latency_ms=latency_ms,
            ...
        ))

    # 3. Shadow call (sequential, after production)
    if flight_recorder and settings.SHADOW_LLM_ENABLED:
        shadow_start = time.perf_counter()
        try:
            shadow_result = await ai_provider.call_claude(
                model=settings.L2_SHADOW_MODEL,  # Haiku
                system=self.system_prompt,
                messages=messages,
                max_tokens=4096,
                max_retries=0,  # Don't retry shadow calls
            )
            flight_recorder.record_llm_call(LLMCallRecord(
                is_shadow=True,
                tier="L2",
                model=settings.L2_SHADOW_MODEL,
                ...
            ))
        except Exception as e:
            # Record shadow failure but don't affect production
            flight_recorder.record_llm_call(LLMCallRecord(
                is_shadow=True,
                error=str(e),
                ...
            ))

    # 4. Continue with normal processing (uses production result)
```

### R2 Storage

```
aide-workspaces/
└── flight-logs/
    └── {aide_id}/
        └── {date}/
            ├── {timestamp}_{batch_id}.jsonl
            ├── {timestamp}_{batch_id}.jsonl
            └── ...
```

Using unique batch files per upload avoids read-modify-write race conditions. A separate analysis process can concatenate files per day if needed.

### Configuration

```python
# backend/config.py

# Production models
L2_PRODUCTION_MODEL: str = "claude-sonnet-4-20250514"
L3_PRODUCTION_MODEL: str = "claude-opus-4-20250514"

# Shadow models
L2_SHADOW_MODEL: str = "claude-3-5-haiku-20241022"
L3_SHADOW_MODEL: str = "claude-sonnet-4-20250514"

# Feature flags
SHADOW_LLM_ENABLED: bool = os.environ.get("SHADOW_LLM_ENABLED", "true") == "true"
FLIGHT_RECORDER_ENABLED: bool = os.environ.get("FLIGHT_RECORDER_ENABLED", "true") == "true"
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| LLM call timeout | Record with error field, continue |
| Shadow call fails | Log error in record, don't affect production |
| R2 upload fails | Log error, data lost (best-effort) |
| Queue full | Drop new records |
| App crash | Buffered records lost |
| Large snapshots | Accept for now; compress later if needed |

## Verification Plan

1. **Unit tests**: FlightRecorder serialization, JSON structure validation
2. **Integration test**: Send message → verify JSONL appears in R2
3. **Shadow call test**: Verify both production and shadow calls recorded with correct models
4. **Non-blocking test**: Verify response time unaffected by recorder
5. **Manual inspection**: Download JSONL, verify contents match expected structure

## Future Considerations

- **Compression**: GZIP JSONL content for storage efficiency
- **Snapshot diffs**: Store only changed fields to reduce size
- **Sampling**: Option to record only N% of turns in production
- **Viewer**: Web UI to replay and analyze flight logs
- **Alerting**: Detect when shadow and production diverge significantly
