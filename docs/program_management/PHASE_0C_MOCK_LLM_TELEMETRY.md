# Phase 0c: Mock LLM + Telemetry

**Status:** Not Started
**Prerequisites:** Phase 0b complete (reducer passes all golden files)
**Checkpoint:** Mock LLM streams golden files with realistic timing. Telemetry table exists and captures data from test runs.

---

## Goal

Build the infrastructure for deterministic testing and performance measurement:
1. **Mock LLM** — streams golden files line-by-line with configurable delays
2. **Telemetry** — captures metrics from every LLM call and direct edit

This enables:
- Fast, deterministic tests (no real API calls)
- Realistic timing simulation for UX testing
- Performance measurement from day one
- Cost tracking per message/user

---

## Mock LLM

### Interface

```python
class MockLLM:
    """Streams golden files line-by-line with configurable delays."""

    async def stream(
        self,
        scenario: str,
        profile: str = "instant"
    ) -> AsyncIterator[str]:
        """
        Stream a golden file line by line.

        Args:
            scenario: Golden file name (e.g., "create_graduation")
            profile: Delay profile ("instant", "realistic_l2", "realistic_l3", "slow")

        Yields:
            Each line from the golden file
        """
        ...
```

### Delay Profiles

| Profile | Think Time | Per-Line Delay | Use Case |
|---------|------------|----------------|----------|
| `instant` | 0ms | 0ms | Unit tests — fast, deterministic |
| `realistic_l2` | 300ms | 200ms | Simulates Haiku L2 response |
| `realistic_l3` | 1500ms | 150ms | Simulates Sonnet L3 first creation |
| `slow` | 3000ms | 500ms | Stress testing UX, interrupt handling |

Think time = delay before first line (simulates model "thinking")
Per-line delay = delay between subsequent lines (simulates streaming)

### Implementation

```python
# engine/kernel/mock_llm.py

from pathlib import Path
import asyncio
from typing import AsyncIterator

GOLDEN_DIR = Path("engine/kernel/tests/fixtures/golden")

DELAY_PROFILES = {
    "instant": {"think_ms": 0, "per_line_ms": 0},
    "realistic_l2": {"think_ms": 300, "per_line_ms": 200},
    "realistic_l3": {"think_ms": 1500, "per_line_ms": 150},
    "slow": {"think_ms": 3000, "per_line_ms": 500},
}

class MockLLM:
    def __init__(self, golden_dir: Path = GOLDEN_DIR):
        self.golden_dir = golden_dir

    async def stream(
        self,
        scenario: str,
        profile: str = "instant"
    ) -> AsyncIterator[str]:
        delays = DELAY_PROFILES.get(profile, DELAY_PROFILES["instant"])

        # Load golden file
        path = self.golden_dir / f"{scenario}.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"Golden file not found: {path}")

        lines = path.read_text().strip().split("\n")

        # Think time before first line
        if delays["think_ms"] > 0:
            await asyncio.sleep(delays["think_ms"] / 1000)

        for i, line in enumerate(lines):
            if not line.strip():
                continue
            yield line

            # Per-line delay (skip after last line)
            if i < len(lines) - 1 and delays["per_line_ms"] > 0:
                await asyncio.sleep(delays["per_line_ms"] / 1000)
```

### Mock/Real Toggle

```python
# backend/services/llm_provider.py

from backend.config import settings
from engine.kernel.mock_llm import MockLLM

def get_llm():
    """Return MockLLM for tests, real LLM for production."""
    if settings.USE_MOCK_LLM:
        return MockLLM()
    else:
        return AnthropicLLM()  # Real implementation in Phase 4
```

Environment variable: `USE_MOCK_LLM=true` for tests, unset for production.

---

## Telemetry

### Schema

```sql
-- alembic/versions/XXX_add_telemetry_table.py

CREATE TABLE telemetry (
    id              SERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ DEFAULT NOW(),
    aide_id         UUID NOT NULL,
    user_id         UUID,
    event_type      TEXT NOT NULL,  -- 'llm_call', 'direct_edit', 'undo', 'escalation'

    -- LLM call fields
    tier            TEXT,           -- 'L2', 'L3', 'L4'
    model           TEXT,           -- 'haiku', 'sonnet', 'opus'
    prompt_ver      TEXT,           -- 'v2.1'
    ttfc_ms         INT,            -- time to first content
    ttc_ms          INT,            -- time to complete
    input_tokens    INT,
    output_tokens   INT,
    cache_read_tokens   INT,
    cache_write_tokens  INT,

    -- Reducer stats
    lines_emitted   INT,
    lines_accepted  INT,
    lines_rejected  INT,

    -- Escalation
    escalated       BOOLEAN DEFAULT FALSE,
    escalation_reason TEXT,

    -- Cost
    cost_usd        NUMERIC(10,6),

    -- Direct edit fields
    edit_latency_ms INT,

    -- Context
    message_id      UUID,           -- groups events for undo
    error           TEXT,

    -- Constraints
    CONSTRAINT valid_event_type CHECK (
        event_type IN ('llm_call', 'direct_edit', 'undo', 'escalation')
    )
);

-- Indexes for common queries
CREATE INDEX idx_telemetry_aide_ts ON telemetry(aide_id, ts);
CREATE INDEX idx_telemetry_tier_ts ON telemetry(tier, ts);
CREATE INDEX idx_telemetry_user_ts ON telemetry(user_id, ts);
CREATE INDEX idx_telemetry_event_type ON telemetry(event_type, ts);
```

### Pydantic Models

```python
# backend/models/telemetry.py

from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from decimal import Decimal

class TelemetryEvent(BaseModel):
    aide_id: UUID
    user_id: UUID | None = None
    event_type: str  # 'llm_call', 'direct_edit', 'undo', 'escalation'

    # LLM call fields
    tier: str | None = None
    model: str | None = None
    prompt_ver: str | None = None
    ttfc_ms: int | None = None
    ttc_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None

    # Reducer stats
    lines_emitted: int | None = None
    lines_accepted: int | None = None
    lines_rejected: int | None = None

    # Escalation
    escalated: bool = False
    escalation_reason: str | None = None

    # Cost
    cost_usd: Decimal | None = None

    # Direct edit
    edit_latency_ms: int | None = None

    # Context
    message_id: UUID | None = None
    error: str | None = None

    model_config = {"extra": "forbid"}
```

### Repository

```python
# backend/repos/telemetry_repo.py

from backend.db import user_conn, system_conn
from backend.models.telemetry import TelemetryEvent
from uuid import UUID

async def record_event(event: TelemetryEvent) -> int:
    """Record a telemetry event. Returns the event ID."""
    async with system_conn() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO telemetry (
                aide_id, user_id, event_type,
                tier, model, prompt_ver,
                ttfc_ms, ttc_ms,
                input_tokens, output_tokens,
                cache_read_tokens, cache_write_tokens,
                lines_emitted, lines_accepted, lines_rejected,
                escalated, escalation_reason,
                cost_usd, edit_latency_ms,
                message_id, error
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
            ) RETURNING id
            """,
            event.aide_id, event.user_id, event.event_type,
            event.tier, event.model, event.prompt_ver,
            event.ttfc_ms, event.ttc_ms,
            event.input_tokens, event.output_tokens,
            event.cache_read_tokens, event.cache_write_tokens,
            event.lines_emitted, event.lines_accepted, event.lines_rejected,
            event.escalated, event.escalation_reason,
            event.cost_usd, event.edit_latency_ms,
            event.message_id, event.error
        )
        return row["id"]

async def get_aide_stats(aide_id: UUID) -> dict:
    """Get aggregate stats for an aide."""
    async with system_conn() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE event_type = 'llm_call') as llm_calls,
                COUNT(*) FILTER (WHERE event_type = 'direct_edit') as direct_edits,
                COUNT(*) FILTER (WHERE escalated = true) as escalations,
                AVG(ttfc_ms) FILTER (WHERE tier = 'L2') as avg_l2_ttfc,
                AVG(ttfc_ms) FILTER (WHERE tier = 'L3') as avg_l3_ttfc,
                SUM(cost_usd) as total_cost,
                SUM(lines_accepted)::float / NULLIF(SUM(lines_emitted), 0) as accept_rate
            FROM telemetry
            WHERE aide_id = $1
            """,
            aide_id
        )
        return dict(row)
```

### Telemetry Service

```python
# backend/services/telemetry.py

import time
from contextlib import asynccontextmanager
from uuid import UUID
from backend.models.telemetry import TelemetryEvent
from backend.repos import telemetry_repo

class LLMCallTracker:
    """Context manager for tracking LLM call metrics."""

    def __init__(
        self,
        aide_id: UUID,
        user_id: UUID | None,
        tier: str,
        model: str,
        message_id: UUID | None = None,
    ):
        self.event = TelemetryEvent(
            aide_id=aide_id,
            user_id=user_id,
            event_type="llm_call",
            tier=tier,
            model=model,
            message_id=message_id,
            prompt_ver="v2.1",
        )
        self.start_time: float | None = None
        self.first_content_time: float | None = None

    def start(self):
        self.start_time = time.perf_counter()

    def mark_first_content(self):
        if self.first_content_time is None:
            self.first_content_time = time.perf_counter()
            self.event.ttfc_ms = int((self.first_content_time - self.start_time) * 1000)

    def set_tokens(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_read: int = 0,
        cache_write: int = 0,
    ):
        self.event.input_tokens = input_tokens
        self.event.output_tokens = output_tokens
        self.event.cache_read_tokens = cache_read
        self.event.cache_write_tokens = cache_write
        self.event.cost_usd = calculate_cost(
            self.event.model, input_tokens, output_tokens, cache_read
        )

    def set_reducer_stats(self, emitted: int, accepted: int, rejected: int):
        self.event.lines_emitted = emitted
        self.event.lines_accepted = accepted
        self.event.lines_rejected = rejected

    def set_escalation(self, reason: str):
        self.event.escalated = True
        self.event.escalation_reason = reason

    def set_error(self, error: str):
        self.event.error = error

    async def finish(self):
        if self.start_time:
            self.event.ttc_ms = int((time.perf_counter() - self.start_time) * 1000)
        await telemetry_repo.record_event(self.event)


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
) -> float:
    """Calculate cost in USD based on model pricing."""
    # Pricing as of 2026 (per 1M tokens)
    PRICING = {
        "haiku": {"input": 0.25, "output": 1.25, "cache_read": 0.03},
        "sonnet": {"input": 3.00, "output": 15.00, "cache_read": 0.30},
        "opus": {"input": 15.00, "output": 75.00, "cache_read": 1.50},
    }

    prices = PRICING.get(model, PRICING["sonnet"])

    # Cache read tokens are cheaper, subtract from input
    regular_input = input_tokens - cache_read_tokens

    cost = (
        (regular_input / 1_000_000) * prices["input"]
        + (cache_read_tokens / 1_000_000) * prices["cache_read"]
        + (output_tokens / 1_000_000) * prices["output"]
    )

    return round(cost, 6)
```

---

## Implementation Order

### 1. Mock LLM (engine/kernel/)

| Task | File | Tests |
|------|------|-------|
| Create MockLLM class | `engine/kernel/mock_llm.py` | - |
| Delay profiles | `engine/kernel/mock_llm.py` | - |
| Unit tests | `engine/kernel/tests/test_mock_llm.py` | 6 tests |

**Tests:**
- [ ] `test_streams_golden_file_lines` — all lines yielded
- [ ] `test_instant_profile_no_delay` — completes in <10ms
- [ ] `test_realistic_l2_timing` — ~300ms think + ~200ms/line
- [ ] `test_realistic_l3_timing` — ~1500ms think + ~150ms/line
- [ ] `test_missing_golden_file_raises` — FileNotFoundError
- [ ] `test_skips_empty_lines` — blank lines not yielded

### 2. Telemetry Migration (alembic/)

| Task | File |
|------|------|
| Create migration | `alembic/versions/XXX_add_telemetry_table.py` |
| Add indexes | Same file |

### 3. Telemetry Models (backend/models/)

| Task | File |
|------|------|
| TelemetryEvent model | `backend/models/telemetry.py` |

### 4. Telemetry Repository (backend/repos/)

| Task | File | Tests |
|------|------|-------|
| record_event | `backend/repos/telemetry_repo.py` | 2 tests |
| get_aide_stats | `backend/repos/telemetry_repo.py` | 1 test |

**Tests:**
- [ ] `test_record_event_creates_row`
- [ ] `test_record_event_with_all_fields`
- [ ] `test_get_aide_stats_aggregates`

### 5. Telemetry Service (backend/services/)

| Task | File | Tests |
|------|------|-------|
| LLMCallTracker | `backend/services/telemetry.py` | 4 tests |
| calculate_cost | `backend/services/telemetry.py` | 3 tests |

**Tests:**
- [ ] `test_tracker_records_ttfc`
- [ ] `test_tracker_records_ttc`
- [ ] `test_tracker_records_reducer_stats`
- [ ] `test_tracker_records_escalation`
- [ ] `test_cost_calculation_haiku`
- [ ] `test_cost_calculation_sonnet`
- [ ] `test_cost_calculation_with_cache`

### 6. LLM Provider Toggle (backend/services/)

| Task | File |
|------|------|
| get_llm() function | `backend/services/llm_provider.py` |
| Add USE_MOCK_LLM to config | `backend/config.py` |

---

## File Structure

```
engine/kernel/
├── mock_llm.py                 # MockLLM class
└── tests/
    └── test_mock_llm.py        # Mock LLM tests

backend/
├── config.py                   # Add USE_MOCK_LLM
├── models/
│   └── telemetry.py            # TelemetryEvent model
├── repos/
│   └── telemetry_repo.py       # Telemetry DB operations
└── services/
    ├── llm_provider.py         # Mock/real toggle
    └── telemetry.py            # LLMCallTracker, cost calculation

alembic/versions/
└── XXX_add_telemetry_table.py  # Migration
```

---

## Acceptance Criteria

1. **Mock LLM streams golden files** — all 9 golden files stream correctly
2. **Delay profiles work** — instant is <10ms, realistic_l3 is ~3-4s for graduation
3. **Telemetry table exists** — migration runs cleanly
4. **Events recorded** — `record_event()` creates rows with all fields
5. **Stats aggregation works** — `get_aide_stats()` returns correct aggregates
6. **Cost calculation accurate** — matches Anthropic pricing
7. **Mock/real toggle** — `USE_MOCK_LLM=true` returns MockLLM

---

## Test Coverage Target

| Component | Tests |
|-----------|-------|
| MockLLM | 6 |
| telemetry_repo | 3 |
| telemetry service | 7 |
| **Total** | **16 tests** |

---

## Notes

- Telemetry uses `system_conn()` not `user_conn()` — telemetry is system-level, not user-scoped
- RLS not needed on telemetry table — users don't query it directly
- Cost calculation uses current Anthropic pricing — update if pricing changes
- Mock LLM lives in `engine/kernel/` because it's part of the kernel test infrastructure
- Real LLM implementation comes in Phase 4

---

## Integration with Phase 1

Phase 0c outputs feed directly into Phase 1:

```
Phase 1 WebSocket handler:
  message received
  → get_llm() returns MockLLM (in tests) or real LLM (in prod)
  → LLMCallTracker.start()
  → stream golden file / real API
  → LLMCallTracker.mark_first_content() on first line
  → reducer processes each line
  → LLMCallTracker.set_reducer_stats()
  → LLMCallTracker.finish() records to telemetry table
```

The mock enables Phase 1 development without real API calls. The telemetry enables measurement from the first end-to-end test.
