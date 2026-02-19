# Phase 3: Streaming + Progressive Rendering

## Overview

**Goal:** The page builds itself progressively during JSONL streaming. Voice lines appear in chat.

**Prerequisites:** Phase 2 (display components + direct edit)

## What to Build

### 1. Realistic Delay Profiles

Update MockLLM to use realistic streaming delays that simulate actual LLM behavior.

```python
# engine/kernel/mock_llm.py - update delay profiles
DELAY_PROFILES = {
    "instant": {"initial": 0, "per_line": 0},
    "realistic_l2": {"initial": 200, "per_line": 50},   # Haiku: fast
    "realistic_l3": {"initial": 800, "per_line": 100},  # Sonnet: moderate
    "realistic_l4": {"initial": 1500, "per_line": 150}, # Opus: slower
    "slow": {"initial": 2000, "per_line": 300},         # Testing
}
```

### 2. Progressive Entity Rendering

Entities appear one-by-one as they stream in, not all at once after stream completes.

**Current behavior:** MockLLM yields lines instantly, entities appear in batches.

**Target behavior:** With realistic delays, user sees entities fade in progressively.

```javascript
// Frontend: track new entities for animation
entityStore.applyDelta = function(delta) {
  if (delta.type === 'entity.create') {
    this.entities[delta.id] = { ...delta.data, _isNew: true };
    // Clear _isNew after animation
    setTimeout(() => {
      if (this.entities[delta.id]) {
        delete this.entities[delta.id]._isNew;
      }
    }, 300);
  }
  // ... rest of applyDelta
};
```

### 3. Mount Animation

200ms fade-in on new entities.

```css
/* CSS for entity mount animation */
.aide-card,
.aide-section,
.checklist-item,
.aide-table tbody tr {
  animation: entity-mount 200ms ease-out;
}

@keyframes entity-mount {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* For entities added after initial render */
.entity-new {
  animation: entity-mount 200ms ease-out;
}
```

### 4. Voice Line Routing

Voice signals already routed to chat (Phase 1). Enhance with:
- Typing indicator while voice is being assembled
- Voice messages appear with slight delay for natural feel
- Voice text fades in smoothly

```javascript
// Enhanced voice handling
if (msg.type === 'voice') {
  // Add with animation class
  conversationHistory.push({
    role: 'assistant',
    content: msg.text,
    _isNew: true
  });
  renderHistory();

  // Scroll to bottom smoothly
  historyPanel.scrollTo({
    top: historyPanel.scrollHeight,
    behavior: 'smooth'
  });
}
```

### 5. Batch Handling

Buffer events between `batch.start` and `batch.end` signals, then flush all at once.

```python
# backend/routes/ws.py - batch handling
batch_buffer: list[dict] = []
in_batch = False

for event in parsed_events:
    event_type = event.get("t", "")

    if event_type == "batch.start":
        in_batch = True
        batch_buffer = []
        continue

    if event_type == "batch.end":
        in_batch = False
        # Apply all buffered events
        for buffered_event in batch_buffer:
            result = reduce(snapshot, buffered_event)
            if result.accepted:
                snapshot = result.snapshot
                await send_delta(buffered_event)
        batch_buffer = []
        continue

    if in_batch:
        batch_buffer.append(event)
    else:
        # Normal processing
        result = reduce(snapshot, event)
        if result.accepted:
            snapshot = result.snapshot
            await send_delta(event)
```

### 6. Status Indicators

**Typing indicator:** Already exists, update text progression.

```javascript
const streamingStates = [
  'Thinking',
  'Building',
  'Adding details',
  'Almost done'
];

let stateIndex = 0;
const thinkingInterval = setInterval(() => {
  stateIndex = Math.min(stateIndex + 1, streamingStates.length - 1);
  thinkingText.textContent = streamingStates[stateIndex];
}, 1500);
```

**Entity count indicator:** Show progress during stream.

```javascript
// Show entity count in thinking indicator
function updateStreamProgress() {
  const count = Object.keys(entityStore.entities).length;
  if (count > 0) {
    thinkingText.textContent = `Building (${count} items)`;
  }
}
```

### 7. Stop/Interrupt Button

Cancel stream mid-way, keep partial state.

**Frontend:**
```javascript
// Add stop button next to send button
<button id="stop-btn" class="action-btn" title="Stop" style="display:none;">
  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
    <rect x="6" y="6" width="12" height="12" rx="2"/>
  </svg>
</button>

// Show stop button during streaming
function setSendingState(sending) {
  document.getElementById('send-btn').style.display = sending ? 'none' : '';
  document.getElementById('stop-btn').style.display = sending ? '' : 'none';
  // ...
}

// Stop handler
document.getElementById('stop-btn').addEventListener('click', () => {
  if (aideWs && aideWs.readyState === WebSocket.OPEN) {
    aideWs.send(JSON.stringify({ type: 'interrupt' }));
  }
});
```

**Backend:**
```python
# Handle interrupt message
if msg_type == "interrupt":
    # Set flag to stop processing
    interrupt_requested = True
    await websocket.send_text(json.dumps({
        "type": "stream.interrupted",
        "message_id": current_message_id
    }))
    continue

# In stream loop, check flag
async for line in mock_llm.stream(scenario, profile="realistic_l3"):
    if interrupt_requested:
        break
    # ... process line
```

### 8. Profile Selection

Allow switching between delay profiles for testing.

```python
# WebSocket message to set profile
if msg_type == "set_profile":
    current_profile = msg.get("profile", "realistic_l3")
    continue

# Use current_profile in stream call
async for line in mock_llm.stream(scenario, profile=current_profile):
```

## File Changes

```
backend/
├── routes/
│   └── ws.py                    # Batch handling, interrupt, profile selection
└── tests/
    └── test_streaming.py        # Streaming behavior tests

engine/kernel/
└── mock_llm.py                  # Already has delay profiles

frontend/
└── index.html                   # Mount animation, stop button, progress indicator
```

## Implementation Order

1. **Mount animation CSS** - Add keyframe animation
2. **Stop button** - Frontend UI + WebSocket interrupt message
3. **Backend interrupt handling** - Stop stream on interrupt
4. **Batch handling** - Buffer and flush batch events
5. **Progress indicator** - Show entity count during stream
6. **Profile selection** - Allow switching delay profiles
7. **Tests** - Verify streaming behavior

## Test Plan

### Unit Tests

```python
# test_streaming.py

async def test_interrupt_stops_stream():
    async with websocket_client("/ws/aide/test") as ws:
        # Start stream with slow profile
        ws.send_text(json.dumps({
            "type": "set_profile",
            "profile": "slow"
        }))
        ws.send_text(json.dumps({
            "type": "message",
            "content": "graduation party",
            "message_id": "int-test"
        }))

        # Wait for first entity
        msg = ws.receive_json()
        assert msg["type"] == "stream.start"
        msg = ws.receive_json()
        assert msg["type"] == "entity.create"

        # Send interrupt
        ws.send_text(json.dumps({"type": "interrupt"}))

        # Should get interrupted status
        while True:
            msg = ws.receive_json()
            if msg["type"] == "stream.interrupted":
                break

        # Partial state should be preserved
        # (entities created before interrupt remain)

async def test_batch_events_applied_together():
    # Test that batch.start/batch.end buffers events
    ...

async def test_realistic_delays_produce_progressive_rendering():
    # With realistic_l3 profile, measure time between deltas
    ...
```

### E2E Test (Manual)

1. Start server with `realistic_l3` profile
2. Create new aide with "plan a graduation party"
3. Watch entities fade in one-by-one (not all at once)
4. Voice messages appear in chat as they stream
5. Click Stop mid-stream - verify partial page preserved
6. Verify thinking indicator shows progress ("Building (5 items)")

## Checkpoint Criteria

- [ ] Entities fade in with 200ms animation as they arrive
- [ ] Voice lines appear in chat during streaming
- [ ] Stop button cancels stream, keeps partial state
- [ ] Batch events applied together
- [ ] Progress indicator shows entity count
- [ ] ttfc with realistic_l3 < 500ms

## Measurements

| Metric | Target | How to Measure |
|--------|--------|----------------|
| ttfc (realistic_l3) | <500ms | Time from send to first entity visible |
| Animation smoothness | 60fps | Chrome DevTools Performance |
| Interrupt latency | <100ms | Time from click to stream stop |
