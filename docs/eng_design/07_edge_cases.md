# 07: Edge Cases & Reliability

> **Prerequisites:** [00 Overview](00_overview.md) · [03 Streaming Pipeline](03_streaming_pipeline.md)
> **Related:** [04 Display Components](04_display_components.md) (for direct edit details)

---

## Core Principle: Two Speeds

| Speed | Latency | LLM? | Examples |
|-------|---------|------|----------|
| **Spreadsheet** | <200ms | No | Edit field, toggle checkbox, drag to reorder, delete, undo |
| **AI** | 1-5s | Yes | Add guest, create section, ask question, first creation |

The fast loop is the escape hatch that makes the slow loop trustworthy. If every correction requires an AI round trip, users abandon after the second mistake.

---

## Interrupt

User hits Stop during JSONL streaming.

1. Client sends interrupt signal via WebSocket.
2. Server cancels LLM stream.
3. **Entities already reduced are kept.** They're valid state.
4. Incomplete JSONL line in buffer is discarded.
5. Chat input immediately available.

**Why keep partial state:** User hit Stop because they saw something wrong, not because everything was wrong. They say "remove the decorations section" as a quick follow-up instead of regenerating.

**UI:** Stop button visible during generation. On stop: "Stopped — 15 of ~30 items created."

---

## Network Drop

Connection lost mid-stream.

**Server:** Continues processing LLM stream to completion. Saves final snapshot to R2. Work already paid for — don't waste it.

**Client:** Shows "Connection lost. Reconnecting..." On reconnect, requests current snapshot. Receives complete graph, renders in one pass. User missed the animation but result is correct.

---

## Undo

**Undo is event-log replay, not LLM-powered.**

1. Every user message produces a batch of events tagged with `message_id`.
2. **Undo** = replay all events excluding the last batch.
3. Reducer is a pure function — replay produces identical state.
4. Undone events move to redo stack.

**Granularity:** Message level. One user message = one undo step.

**Depth:** Last 20 message batches. Milliseconds to replay.

**UI:** Undo button always visible (Cmd+Z / Ctrl+Z). Page animates to previous state. Toast: "Undone: 'move Aunt Linda to vegetarian table'" with Redo option.

**Undo is instant. No spinner, no LLM call.**

---

## Retry

Three paths depending on what went wrong:

### Path 1: Direct Edit (detail was wrong)

Date says May 23 instead of May 22. Click it, change it. Under 200ms.

Every rendered field value is directly editable:
- Text → inline text input
- Date → date picker
- Boolean → immediate toggle
- Number → number input
- Enum → dropdown
- Entity position → drag to reorder

**The user never needs to talk to the AI to fix a typo. This is non-negotiable.**

### Path 2: Retry Message (AI misunderstood)

Hit ↻ on last AI response. Triggers Undo + re-send same message. LLM regenerates (may differ due to temperature).

Use when the AI fundamentally misunderstood intent.

### Path 3: Follow-Up Correction (natural language)

Type "that date should be May 22" in chat. L2 compiles to `entity.update`. Slower than direct edit (~1-2s) but natural for chat-oriented users.

---

## Error States

### Malformed JSONL
Server skips line, continues to next. If 3+ consecutive parse failures → cancel stream, report error. Partial success always preserved.

### Reducer Rejection
Event structurally invalid. Skip, log, continue. If 3+ consecutive rejections → escalate to next tier.

### LLM Timeout
No tokens for 15 seconds → cancel stream, keep applied entities. "Response timed out. [N] items created. You can continue."

### R2 Save Failure
Retry 3x with exponential backoff. If all fail → hold snapshot in memory, show "Changes active but not yet saved" banner. Clear on success.

---

## Speed Budget

| Action | Target | LLM? |
|--------|--------|------|
| Toggle checkbox | <100ms | No |
| Edit field inline | <200ms | No |
| Undo / Redo | <300ms | No |
| Reorder (drag) | <200ms | No |
| Delete entity | <200ms | No |
| L2 update | <1.5s | Yes (Haiku) |
| L2 correction | <1.5s | Yes (Haiku) |
| L3 new section | <3s first content | Yes (Sonnet) |
| L3 first creation | <1s first content, <4s complete | Yes (Sonnet) |
| L4 query | <5s | Yes (Opus) |

---

## The Trust Equation

**Trust = speed of recovery × reliability of AI × visibility of what happened**

- **Speed of recovery:** Direct edit for details, undo for mistakes, retry for misunderstandings.
- **Reliability:** Three-tier routing, eval suites, reducer validation.
- **Visibility:** The page IS the feedback. No hidden state. Entities appear as created. Changes visible instantly.

The user needs to know: I say something, the page changes, and if it's wrong I can fix it immediately.
