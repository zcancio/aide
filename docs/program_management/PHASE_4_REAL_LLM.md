# Phase 4: Real LLM Integration

## Overview

**Goal:** Replace mocks with real Anthropic API calls for live usage. Mocks stay for tests.

**Prerequisites:** Phase 3 (streaming + progressive rendering)

## What to Build

### 1. Anthropic Streaming Client

Connect to Anthropic Messages API, stream response, feed to existing JSONL pipeline.

```python
# backend/services/anthropic_client.py
import anthropic
from typing import AsyncIterator

class AnthropicClient:
    """Streams responses from Anthropic Messages API."""

    def __init__(self, api_key: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def stream(
        self,
        messages: list[dict],
        system: str,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
        cache_ttl: int | None = None,
    ) -> AsyncIterator[str]:
        """
        Stream response from Anthropic API.

        Yields text chunks as they arrive.
        """
        # Build cache control if specified
        system_with_cache = system
        if cache_ttl:
            system_with_cache = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral", "ttl": cache_ttl}
                }
            ]

        async with self.client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system_with_cache,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text
```

### 2. Prompt Assembly

Combine system prompt + snapshot + conversation for each tier.

```python
# backend/services/prompt_builder.py
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

def load_prompt(name: str) -> str:
    """Load prompt from prompts directory."""
    return (PROMPTS_DIR / f"{name}.md").read_text()

def build_l2_prompt(snapshot: dict) -> str:
    """Build L2 (Haiku) system prompt with snapshot context."""
    base = load_prompt("l2_system")
    primitives = load_prompt("primitive_schemas")
    snapshot_json = json.dumps(snapshot, indent=2)

    return f"""{base}

## Primitive Schemas
{primitives}

## Current Snapshot
```json
{snapshot_json}
```
"""

def build_l3_prompt(snapshot: dict) -> str:
    """Build L3 (Sonnet) system prompt with snapshot context."""
    base = load_prompt("l3_system")
    primitives = load_prompt("primitive_schemas")
    snapshot_json = json.dumps(snapshot, indent=2)

    return f"""{base}

## Primitive Schemas
{primitives}

## Current Snapshot
```json
{snapshot_json}
```
"""

def build_messages(conversation: list[dict], user_message: str) -> list[dict]:
    """Build messages array for API call."""
    messages = []

    # Include recent conversation tail (last 10 turns)
    for turn in conversation[-10:]:
        messages.append({
            "role": turn["role"],
            "content": turn["content"]
        })

    # Add current user message
    messages.append({
        "role": "user",
        "content": user_message
    })

    return messages
```

### 3. Tier Classifier

Rule-based routing to L2/L3/L4 based on message content and context.

```python
# backend/services/classifier.py
from dataclasses import dataclass
from typing import Literal

Tier = Literal["L2", "L3", "L4"]

@dataclass
class ClassificationResult:
    tier: Tier
    reason: str

def classify(
    message: str,
    snapshot: dict,
    has_schema: bool,
) -> ClassificationResult:
    """
    Classify message to appropriate tier.

    L2 (Haiku): Simple updates, known patterns
    L3 (Sonnet): New schemas, complex mutations
    L4 (Opus): Queries requiring reasoning
    """
    message_lower = message.lower()

    # L4: Questions and queries
    if any(q in message_lower for q in ["?", "how many", "do we have", "is there", "what is", "who"]):
        # Check if it's a pure query vs mutation+query
        has_mutation_keywords = any(k in message_lower for k in [
            "add", "update", "change", "set", "remove", "delete", "rsvp"
        ])
        if not has_mutation_keywords:
            return ClassificationResult(tier="L4", reason="pure_query")

    # L3: No schema exists yet (first message)
    if not has_schema or not snapshot.get("entities"):
        return ClassificationResult(tier="L3", reason="no_schema")

    # L3: Structural changes
    structural_keywords = [
        "add a section", "create a new", "add table", "new category",
        "reorganize", "restructure", "add column"
    ]
    if any(k in message_lower for k in structural_keywords):
        return ClassificationResult(tier="L3", reason="structural_change")

    # L3: Complex multi-part messages
    if message.count(",") >= 3 or message.count(" and ") >= 2:
        return ClassificationResult(tier="L3", reason="complex_message")

    # L2: Simple updates (default)
    return ClassificationResult(tier="L2", reason="simple_update")

# Model mapping
TIER_MODELS = {
    "L2": "claude-haiku-4-5-20251001",
    "L3": "claude-sonnet-4-5-20250929",
    "L4": "claude-opus-4-5-20251101",
}

# Cache TTLs (seconds)
TIER_CACHE_TTL = {
    "L2": 300,   # 5 minutes
    "L3": 3600,  # 1 hour
    "L4": 3600,  # 1 hour
}
```

### 4. Orchestrator Update

Wire real LLM into existing pipeline, fallback to mock for tests.

```python
# backend/services/orchestrator.py
from backend.services.anthropic_client import AnthropicClient
from backend.services.prompt_builder import build_l2_prompt, build_l3_prompt, build_messages
from backend.services.classifier import classify, TIER_MODELS, TIER_CACHE_TTL

class Orchestrator:
    """Orchestrates message processing through LLM pipeline."""

    def __init__(
        self,
        aide_id: str,
        snapshot: dict,
        conversation: list[dict],
        use_mock: bool = False,
        api_key: str | None = None,
    ):
        self.aide_id = aide_id
        self.snapshot = snapshot
        self.conversation = conversation
        self.use_mock = use_mock

        if not use_mock and api_key:
            self.client = AnthropicClient(api_key)
        else:
            self.client = None

    async def process_message(
        self,
        content: str,
    ) -> AsyncIterator[dict]:
        """Process user message and yield deltas."""
        # Classify message
        has_schema = bool(self.snapshot.get("entities"))
        classification = classify(content, self.snapshot, has_schema)

        tier = classification.tier
        model = TIER_MODELS[tier]
        cache_ttl = TIER_CACHE_TTL[tier]

        # Build prompt based on tier
        if tier == "L2":
            system = build_l2_prompt(self.snapshot)
        else:
            system = build_l3_prompt(self.snapshot)

        messages = build_messages(self.conversation, content)

        # Stream from LLM
        line_buffer = ""
        async for chunk in self.client.stream(
            messages=messages,
            system=system,
            model=model,
            cache_ttl=cache_ttl,
        ):
            line_buffer += chunk
            while "\n" in line_buffer:
                line, line_buffer = line_buffer.split("\n", 1)
                if line.strip():
                    try:
                        event = json.loads(line)
                        result = reduce(self.snapshot, event)
                        if result.accepted:
                            self.snapshot = result.snapshot
                            yield self._to_delta(event)
                    except json.JSONDecodeError:
                        pass  # Skip malformed lines
```

### 5. WebSocket Integration

Update ws.py to use real LLM when available.

```python
# backend/routes/ws.py - updates

# Add config check for API key
from backend import config

async def aide_websocket(websocket: WebSocket, aide_id: str) -> None:
    # ...existing code...

    # Determine if we should use real LLM
    use_mock = not config.settings.ANTHROPIC_API_KEY or current_profile == "mock"

    # In message handler:
    if use_mock:
        # Use MockLLM (existing code)
        async for line in mock_llm.stream(scenario, profile=current_profile):
            # ...existing processing...
    else:
        # Use real LLM
        orchestrator = Orchestrator(
            aide_id=aide_id,
            snapshot=snapshot,
            conversation=conversation_history,
            api_key=config.settings.ANTHROPIC_API_KEY,
        )
        async for delta in orchestrator.process_message(content):
            await websocket.send_text(json.dumps(delta))
```

### 6. Telemetry Updates

Record tier, model, cache hits, and token usage.

```python
# backend/models/telemetry.py - add fields
class TelemetryEvent(BaseModel):
    # ...existing fields...
    tier: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None
```

## File Structure

```
backend/
├── services/
│   ├── anthropic_client.py      # Anthropic API wrapper
│   ├── prompt_builder.py        # Prompt assembly
│   ├── classifier.py            # Tier routing
│   └── orchestrator.py          # Message processing pipeline
├── prompts/
│   ├── l2_system.md             # Existing
│   ├── l3_system.md             # Existing
│   ├── l4_system.md             # New - query handling
│   └── primitive_schemas.md     # Existing
├── routes/
│   └── ws.py                    # Updated for real LLM
├── models/
│   └── telemetry.py             # Updated with tier/token fields
└── tests/
    ├── test_classifier.py       # Classifier tests
    ├── test_prompt_builder.py   # Prompt assembly tests
    └── test_orchestrator.py     # Integration tests (with mock)
```

## Implementation Order

1. **Classifier** - Rule-based tier routing
2. **Prompt builder** - Assemble prompts with snapshot
3. **Anthropic client** - Streaming wrapper
4. **Orchestrator** - Wire together
5. **WebSocket update** - Integrate real LLM
6. **Telemetry update** - Add tier/token tracking
7. **Tests** - Classifier accuracy, prompt assembly

## Test Plan

### Unit Tests

```python
# test_classifier.py
def test_simple_update_routes_to_l2():
    result = classify("Mark Sarah as attending", {}, has_schema=True)
    assert result.tier == "L2"

def test_question_routes_to_l4():
    result = classify("How many guests are attending?", {}, has_schema=True)
    assert result.tier == "L4"

def test_no_schema_routes_to_l3():
    result = classify("Plan a graduation party", {}, has_schema=False)
    assert result.tier == "L3"

def test_structural_change_routes_to_l3():
    result = classify("Add a new section for decorations", {}, has_schema=True)
    assert result.tier == "L3"

def test_mutation_with_query_routes_to_l3():
    result = classify("Add Aunt Linda and do we have enough food?", {}, has_schema=True)
    assert result.tier == "L3"  # Multi-intent
```

```python
# test_prompt_builder.py
def test_l2_prompt_includes_snapshot():
    snapshot = {"entities": {"page": {"title": "Test"}}}
    prompt = build_l2_prompt(snapshot)
    assert "Test" in prompt
    assert "Primitive Schemas" in prompt

def test_messages_includes_conversation_tail():
    conversation = [{"role": "user", "content": f"msg{i}"} for i in range(20)]
    messages = build_messages(conversation, "new message")
    assert len(messages) == 11  # Last 10 + new
```

### Integration Tests (with Mock)

```python
# test_orchestrator.py
@pytest.mark.asyncio
async def test_orchestrator_streams_deltas():
    # Use mock client that returns golden file content
    orch = Orchestrator(aide_id="test", snapshot={}, conversation=[], use_mock=True)
    deltas = [d async for d in orch.process_message("plan a graduation party")]
    assert len(deltas) > 0

@pytest.mark.asyncio
async def test_orchestrator_classifies_correctly():
    orch = Orchestrator(aide_id="test", snapshot={}, conversation=[], use_mock=True)
    # First message should use L3
    # ... verify tier in telemetry
```

### E2E Test (Manual with Real API)

1. Set `ANTHROPIC_API_KEY` in environment
2. Start server, login via dev-login
3. Create new aide with "plan a graduation party for Sophie"
4. Verify entities stream in from real Sonnet response
5. Add a guest: "Add Uncle Mike, he's bringing dessert"
6. Verify Haiku handles simple update
7. Ask: "Do we have enough food for everyone?"
8. Verify Opus provides reasoning response
9. Check telemetry table for tier, model, token counts

## Checkpoint Criteria

- [ ] Classifier routes messages correctly (>90% accuracy on test suite)
- [ ] L3 creates new aide from scratch with Sonnet
- [ ] L2 handles simple updates with Haiku
- [ ] L4 answers queries with Opus
- [ ] Cache control headers set correctly per tier
- [ ] Telemetry records tier, model, tokens
- [ ] Mock mode still works for tests

## Measurements

| Metric | Target | How to Measure |
|--------|--------|----------------|
| ttfc (Sonnet) | <1s | Telemetry |
| ttc (first creation) | <4s | Telemetry |
| ttfc (Haiku) | <500ms | Telemetry |
| L2 accept rate | >95% | Reducer rejections |
| Cache hit rate (5+ turns) | >80% | Cache read tokens > 0 |
| Classifier accuracy | >90% | Test suite |
