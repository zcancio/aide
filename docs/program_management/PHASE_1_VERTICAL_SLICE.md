# Phase 1: One Complete Vertical Slice

## Overview

**Goal:** Type a message, see entities appear on screen. The full pipeline works end-to-end.

**Prerequisites:** Phase 0a (golden files), Phase 0b (reducer), Phase 0c (MockLLM + telemetry)

## The Slice

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

## Components to Build

### 1. WebSocket Server (`backend/routes/ws.py`)

Accept connections at `/ws/aide/{aide_id}`, receive messages, send typed deltas.

**Messages (client → server):**
```python
class UserMessage(BaseModel):
    type: Literal["message"] = "message"
    content: str
    message_id: str  # client-generated UUID
```

**Deltas (server → client):**
```python
class EntityDelta(BaseModel):
    type: Literal["entity.create", "entity.update", "entity.remove"]
    id: str
    data: dict | None = None

class VoiceDelta(BaseModel):
    type: Literal["voice"]
    text: str

class StreamStatus(BaseModel):
    type: Literal["stream.start", "stream.end", "stream.error"]
    message_id: str
    error: str | None = None
```

**Implementation:**
```python
@router.websocket("/ws/aide/{aide_id}")
async def aide_websocket(websocket: WebSocket, aide_id: str):
    await websocket.accept()
    # Load snapshot from memory/R2
    # On message: stream MockLLM → parse → reduce → send deltas
```

### 2. JSONL Parser (`backend/services/jsonl_parser.py`)

Buffers stream until newline, expands abbreviated fields, validates structure.

```python
class JSONLParser:
    """Parses streaming JSONL from LLM output."""

    def __init__(self):
        self.buffer = ""

    def feed(self, chunk: str) -> list[dict]:
        """Feed a chunk, return complete parsed lines."""
        self.buffer += chunk
        lines = []
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            if line.strip():
                try:
                    parsed = json.loads(line)
                    lines.append(self.expand_abbreviations(parsed))
                except json.JSONDecodeError:
                    # Skip malformed lines, log warning
                    pass
        return lines

    def expand_abbreviations(self, event: dict) -> dict:
        """Expand t→type, p→props, id→entity_id, etc."""
        # Per spec abbreviation mapping
        ...
```

### 3. Orchestrator (`backend/services/orchestrator.py`)

Wires together: message → MockLLM → parser → reducer → deltas.

```python
class Orchestrator:
    """Processes user messages through the LLM → reducer pipeline."""

    def __init__(self, aide_id: str, snapshot: dict, mock_llm: MockLLM):
        self.aide_id = aide_id
        self.snapshot = snapshot
        self.mock_llm = mock_llm
        self.parser = JSONLParser()
        self.tracker = LLMCallTracker(...)

    async def process_message(
        self,
        content: str,
        scenario: str = "create_graduation"  # For mock mode
    ) -> AsyncIterator[dict]:
        """Stream deltas for a user message."""
        self.tracker.start()

        async for chunk in self.mock_llm.stream(scenario, profile="instant"):
            for event in self.parser.feed(chunk + "\n"):
                result = reduce(self.snapshot, event)
                if result.accepted:
                    self.snapshot = result.snapshot
                    yield self.to_delta(event)
                else:
                    # Log rejection
                    pass

        self.tracker.mark_first_content()
        await self.tracker.finish()

    def to_delta(self, event: dict) -> dict:
        """Convert reducer event to client delta."""
        ...
```

### 4. React State Store (`frontend/src/store/`)

Holds entity graph, exposes hooks for components.

```typescript
// store/entityStore.ts
interface EntityStore {
  entities: Record<string, Entity>
  rootIds: string[]

  // Actions
  applyDelta(delta: EntityDelta): void

  // Selectors
  getEntity(id: string): Entity | undefined
  getChildren(parentId: string): Entity[]
}

// hooks/useEntity.ts
function useEntity(id: string): Entity | undefined {
  return useEntityStore((state) => state.entities[id])
}

// hooks/useChildren.ts
function useChildren(parentId: string): Entity[] {
  return useEntityStore((state) =>
    state.rootIds
      .filter(id => state.entities[id]?.parent === parentId)
      .map(id => state.entities[id])
  )
}
```

### 5. WebSocket Client (`frontend/src/services/`)

Connects to server, dispatches deltas to store.

```typescript
// services/websocket.ts
class AideWebSocket {
  private ws: WebSocket
  private store: EntityStore

  connect(aideId: string) {
    this.ws = new WebSocket(`/ws/aide/${aideId}`)
    this.ws.onmessage = (event) => {
      const delta = JSON.parse(event.data)
      this.handleDelta(delta)
    }
  }

  sendMessage(content: string) {
    this.ws.send(JSON.stringify({
      type: "message",
      content,
      message_id: crypto.randomUUID()
    }))
  }

  private handleDelta(delta: any) {
    switch (delta.type) {
      case "entity.create":
      case "entity.update":
      case "entity.remove":
        this.store.applyDelta(delta)
        break
      case "voice":
        // Route to chat panel
        break
      case "stream.start":
      case "stream.end":
        // Update loading state
        break
    }
  }
}
```

### 6. AideEntity Component (`frontend/src/components/`)

Recursive renderer with display resolution.

```typescript
// components/AideEntity.tsx
function AideEntity({ id }: { id: string }) {
  const entity = useEntity(id)
  const children = useChildren(id)

  if (!entity) return null

  const Display = resolveDisplay(entity.display)

  return (
    <Display entity={entity}>
      {children.map(child => (
        <AideEntity key={child.id} id={child.id} />
      ))}
    </Display>
  )
}

// resolvers/resolveDisplay.ts
function resolveDisplay(hint: string): ComponentType<DisplayProps> {
  // For Phase 1, everything uses FallbackDisplay
  return FallbackDisplay
}
```

### 7. FallbackDisplay (`frontend/src/components/displays/`)

Renders any entity as key-value pairs. The only display needed for Phase 1.

```typescript
// components/displays/FallbackDisplay.tsx
function FallbackDisplay({ entity, children }: DisplayProps) {
  return (
    <div className="fallback-display">
      <div className="entity-header">
        <span className="entity-id">{entity.id}</span>
        <span className="entity-display">[{entity.display}]</span>
      </div>
      <dl className="entity-props">
        {Object.entries(entity.props || {}).map(([key, value]) => (
          <Fragment key={key}>
            <dt>{key}</dt>
            <dd>{JSON.stringify(value)}</dd>
          </Fragment>
        ))}
      </dl>
      <div className="entity-children">
        {children}
      </div>
    </div>
  )
}
```

## File Structure

```
backend/
├── routes/
│   └── ws.py                    # WebSocket endpoint
├── services/
│   ├── jsonl_parser.py          # JSONL stream parser
│   └── orchestrator.py          # Message → delta pipeline
└── tests/
    ├── test_jsonl_parser.py
    ├── test_orchestrator.py
    └── test_ws.py

frontend/
├── src/
│   ├── store/
│   │   └── entityStore.ts       # Zustand store
│   ├── hooks/
│   │   ├── useEntity.ts
│   │   └── useChildren.ts
│   ├── services/
│   │   └── websocket.ts         # WS client
│   └── components/
│       ├── AideEntity.tsx       # Recursive renderer
│       └── displays/
│           └── FallbackDisplay.tsx
└── tests/
    └── ...
```

## Implementation Order

1. **JSONL Parser** - Pure function, easy to test
2. **Orchestrator** - Wires MockLLM → parser → reducer
3. **WebSocket Server** - Backend endpoint
4. **Entity Store** - Frontend state management
5. **WebSocket Client** - Connect frontend to backend
6. **AideEntity + FallbackDisplay** - Render entities

## Test Plan

### Unit Tests

```python
# test_jsonl_parser.py
def test_parse_single_line():
    parser = JSONLParser()
    lines = parser.feed('{"t":"entity.create","id":"page"}\n')
    assert len(lines) == 1
    assert lines[0]["type"] == "entity.create"

def test_parse_partial_then_complete():
    parser = JSONLParser()
    assert parser.feed('{"t":"ent') == []
    assert parser.feed('ity.create","id":"page"}\n') == [...]

def test_skip_malformed_line():
    parser = JSONLParser()
    lines = parser.feed('not json\n{"t":"entity.create"}\n')
    assert len(lines) == 1  # Skipped bad line

def test_expand_abbreviations():
    parser = JSONLParser()
    lines = parser.feed('{"t":"entity.create","p":{"name":"Test"}}\n')
    assert lines[0]["type"] == "entity.create"
    assert lines[0]["props"]["name"] == "Test"
```

```python
# test_orchestrator.py
async def test_process_message_yields_deltas():
    mock_llm = MockLLM()
    orch = Orchestrator(aide_id="test", snapshot={}, mock_llm=mock_llm)

    deltas = [d async for d in orch.process_message("test", scenario="update_simple")]

    assert len(deltas) >= 1
    assert all(d["type"].startswith("entity.") for d in deltas)

async def test_rejected_events_not_yielded():
    # Feed invalid event through orchestrator
    # Verify it's not in output deltas
    ...
```

### Integration Tests

```python
# test_ws.py
async def test_websocket_message_yields_deltas():
    async with websocket_client("/ws/aide/test-id") as ws:
        await ws.send_json({"type": "message", "content": "test", "message_id": "123"})

        # Collect deltas until stream.end
        deltas = []
        while True:
            msg = await ws.receive_json()
            deltas.append(msg)
            if msg["type"] == "stream.end":
                break

        assert any(d["type"] == "entity.create" for d in deltas)
```

### E2E Test (Manual)

1. Start backend with `uvicorn backend.main:app`
2. Open frontend at `http://localhost:3000`
3. Type "plan a graduation party" in chat
4. Observe entities appearing on screen via FallbackDisplay
5. Check telemetry table for recorded metrics

## Checkpoint Criteria

- [x] WebSocket endpoint accepts connections and receives messages
- [x] JSONL parser correctly buffers and expands abbreviations
- [x] Orchestrator streams MockLLM → parser → reducer → deltas
- [x] Frontend store receives and applies deltas
- [x] AideEntity recursively renders entity tree (FallbackDisplay in vanilla JS)
- [x] FallbackDisplay shows all entity props
- [ ] Telemetry records ttfc and ttc for each message (ttfc logged to server stdout; DB telemetry wired in Phase 1.3)
- [x] All tests pass

## Measurements

| Metric | Target | How to Measure |
|--------|--------|----------------|
| ttfc (mock, instant) | <50ms | Telemetry table |
| ttc (mock, instant) | <200ms | Telemetry table |
| ttfc (mock, realistic_l3) | <1600ms | Telemetry table |
| WebSocket latency | <20ms | Round-trip ping |
