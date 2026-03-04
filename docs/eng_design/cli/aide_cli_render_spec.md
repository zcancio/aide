# AIde CLI: History, Streaming & Text Rendering

**Status:** Design
**Phase:** Post-CLI-auth (builds on `aide_cli_spec.md`)
**Date:** 2026-02-23
**Depends on:** CLI auth spec, engine.js, streaming orchestrator

## Overview

Three capabilities that make the CLI feel like a real terminal for your aides:

1. **History** — load and display past conversation turns in the REPL
2. **Streaming** — voice text arrives incrementally as the AI thinks, not after it's done
3. **Text rendering** — the CLI spawns a local Node process that runs `renderText()` from the engine, producing unicode snapshots of your aide's state directly in the terminal

Together these turn the CLI from a fire-and-forget message sender into something you can keep open all day.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│  aide CLI (Python)                          │
│                                             │
│  ┌───────────┐   ┌──────────────────────┐   │
│  │   REPL    │──▶│  HTTP Client (httpx)  │──────▶ AIde API
│  │           │   │  SSE streaming        │◀──────  (SSE)
│  │  /history │   └──────────────────────┘   │
│  │  /view    │                              │
│  │  /watch   │   ┌──────────────────────┐   │
│  │           │──▶│  Node Bridge (child)  │   │
│  └───────────┘   │  stdin/stdout JSON    │   │
│                  │  engine.js loaded     │   │
│                  │  renderText() exposed │   │
│                  └──────────────────────┘   │
└─────────────────────────────────────────────┘
```

The CLI is Python. The engine is JavaScript. Rather than rewrite the renderer in Python (drift risk), the CLI spawns a single long-lived Node child process that loads `engine.js` and exposes `renderText()` over stdin/stdout JSON-RPC. This is the same pattern the web editor uses — one engine, multiple surfaces.

---

## 1. History

### API Endpoint

Already exists: `GET /api/aides/{aide_id}/conversation`

Returns `ConversationHistoryResponse`:
```json
{
  "messages": [
    { "role": "user", "content": "running a basketball league, 8 teams" },
    { "role": "assistant", "content": "Next step: draft order." },
    { "role": "user", "content": "mike's team beat dave's 88-72" },
    { "role": "assistant", "content": "Standings updated. Mike: 3-1. Dave: 2-2." }
  ]
}
```

### REPL Command

```
aide > /history
  you: running a basketball league, 8 teams
  aide: Next step: draft order.

  you: mike's team beat dave's 88-72
  aide: Standings updated. Mike: 3-1. Dave: 2-2.

aide > /history 5
  (shows last 5 exchanges)
```

### Display Rules

- Show most recent messages first (reverse chronological), capped at `n` (default 20)
- User messages prefixed with `you:` in dim/default color
- Assistant messages prefixed with `aide:` in accent color (ANSI green, `\033[32m`)
- Blank line between exchanges (user + assistant = one exchange)
- If conversation exceeds terminal height, paginate with `--more--` (or just truncate — v1 keeps it simple)
- Empty history: `No conversation history.`

### Implementation

```python
def cmd_history(n: int = 20):
    resp = client.get(f"/api/aides/{current_aide_id}/conversation")
    messages = resp.json()["messages"]

    # Show last n messages (n counts individual messages, not pairs)
    recent = messages[-n:]

    for i, msg in enumerate(recent):
        prefix = "\033[90myou:\033[0m" if msg["role"] == "user" else "\033[32maide:\033[0m"
        print(f"  {prefix} {msg['content']}")
        # Blank line after assistant messages (end of exchange)
        if msg["role"] == "assistant" and i < len(recent) - 1:
            print()
```

---

## 2. Streaming

### Current Flow (batch)

```
aide > mike's team beat dave's 88-72
  [waits 1-3 seconds]
  Standings updated. Mike: 3-1. Dave: 2-2.
```

### Streaming Flow

```
aide > mike's team beat dave's 88-72
  Standings updated. Mike: 3-1. Dave: 2-2.█
  ↑ text appears character by character
```

### SSE Endpoint

Uses the existing streaming endpoint: `POST /api/aide/{aide_id}/chat` with `Accept: text/event-stream`.

The CLI only cares about two event types:

| SSE Event | CLI Action |
|-----------|------------|
| `voice` | Print text incrementally to terminal |
| `done` | Finalize line, re-enable input |

The CLI ignores `primitive` events (no client-side reduce needed — that's for the web editor's live preview). The server still applies primitives and persists state.

### SSE Client

```python
import httpx

async def stream_message(aide_id: str, message: str):
    """Send message and stream voice response."""
    print("  ", end="", flush=True)  # indent for response

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{api_url}/api/aide/{aide_id}/chat",
            json={"message": message},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "text/event-stream",
            },
            timeout=60.0,
        ) as response:
            buffer = ""
            async for line in response.aiter_lines():
                if line.startswith("event: "):
                    event_type = line[7:]
                elif line.startswith("data: "):
                    data = json.loads(line[6:])

                    if event_type == "voice":
                        text = data.get("text", "")
                        print(text, end="", flush=True)

                    elif event_type == "done":
                        print()  # newline after streaming completes
                        return data  # snapshot_hash, event_count

    print()  # safety newline
```

### Fallback

If the streaming endpoint isn't available (older backend), fall back to the batch `POST /api/message` endpoint. Detect via response content-type: `text/event-stream` → stream, `application/json` → batch.

### Interrupt

Ctrl-C during streaming:
1. Cancel the HTTP request (closes SSE connection)
2. Print newline
3. Return to `aide >` prompt
4. Server-side: the orchestrator detects the closed connection and stops the LLM stream (already implemented for web)

---

## 3. Text Rendering

### Why Node?

The engine (`engine.js`) is the single source of truth for rendering. The v1.3 renderer spec defines a `text` channel that produces unicode output for SMS, Signal, and terminal. Running it via Node means:

- Zero drift between terminal, SMS, and web rendering
- Engine updates are picked up automatically
- No Python port to maintain
- Same pure function contract: `renderText(snapshot) → string`

### `renderText` Function

This is a new export added to `engine.js`. It follows the text channel spec from the v1.3 renderer:

```javascript
/**
 * Render snapshot as unicode text for terminal/SMS/Slack.
 * Pure function. No IO. Deterministic.
 *
 * @param {AideState} snapshot - Current aide state
 * @returns {string} Unicode text representation
 */
function renderText(snapshot) {
    const lines = []

    // Title
    const title = snapshot.meta?.title || "Untitled"
    lines.push(title)
    lines.push("═".repeat(Math.min(title.length, 60)))
    lines.push("")

    // Walk collections
    for (const [colId, col] of Object.entries(snapshot.collections || {})) {
        if (col._removed) continue

        const entities = Object.entries(col.entities || {})
            .filter(([, e]) => !e._removed)
            .sort((a, b) => (a[1]._created_seq || 0) - (b[1]._created_seq || 0))

        if (entities.length === 0) continue

        // Collection header
        lines.push(col.name || colId)
        lines.push("─".repeat(Math.min((col.name || colId).length, 40)))

        // Render entities
        for (const [eid, entity] of entities) {
            lines.push(renderEntityText(entity, col.schema))
        }

        lines.push("")  // blank line between collections
    }

    // Annotations
    const pinned = (snapshot.annotations || []).filter(a => a.pinned)
    if (pinned.length > 0) {
        lines.push("Notes")
        lines.push("─────")
        for (const ann of pinned) {
            lines.push(`• ${ann.note}`)
        }
        lines.push("")
    }

    return lines.join("\n").trimEnd()
}

function renderEntityText(entity, schema) {
    const fields = schema || {}
    const parts = []

    // Checkbox-style for boolean fields named done/checked/complete
    const checkField = Object.keys(fields).find(f =>
        ["done", "checked", "complete"].includes(f) && baseType(fields[f]) === "bool"
    )

    if (checkField) {
        const checked = entity[checkField]
        const label = entity.name || entity.title || entity.id || "?"
        return `${checked ? "✓" : "○"} ${label}`
    }

    // Name/title as primary, other fields as secondary
    const nameField = entity.name || entity.title || null
    const otherFields = Object.entries(entity)
        .filter(([k]) => !k.startsWith("_") && k !== "name" && k !== "title")
        .filter(([k]) => k in fields)  // only schema fields
        .map(([k, v]) => `${humanize(k)}: ${fmtValueText(v, fields[k])}`)

    if (nameField && otherFields.length > 0) {
        return `  ${nameField}  │  ${otherFields.join("  │  ")}`
    } else if (nameField) {
        return `  ${nameField}`
    } else {
        return `  ${otherFields.join("  │  ")}`
    }
}

function humanize(key) {
    return key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())
}

function fmtValueText(val, type) {
    if (val === null || val === undefined) return "—"
    if (typeof val === "boolean") return val ? "Yes" : "No"
    if (Array.isArray(val)) return val.join(", ")
    return String(val)
}
```

### Unicode Formatting Reference

| Element | Unicode | Example |
|---------|---------|---------|
| Title underline | `═══════` | `Basketball League` / `══════════════════` |
| Section divider | `───────` | `Roster` / `──────` |
| Checked item | `✓` | `✓ Milk` |
| Unchecked item | `○` | `○ Bread` |
| Bullet | `•` | `• Bring snacks Thursday` |
| Field separator | `│` | `Mike  │  3-1  │  Active` |
| Null value | `—` (em dash) | `Phone: —` |
| Nested indent | 2 spaces | `  Dave  │  2-2` |

### Example Output

```
Basketball League
═════════════════

Roster
──────
  Mike    │  Record: 3-1  │  Status: Active
  Dave    │  Record: 2-2  │  Status: Active
  Sarah   │  Record: 4-0  │  Status: Active
  Tom     │  Record: 1-3  │  Status: Active

Schedule
────────
  Game 5  │  Date: Feb 27  │  Home: Mike  │  Away: Tom
  Game 6  │  Date: Mar 13  │  Home: Sarah │  Away: Dave

Notes
─────
• Draft order was randomized
• Next game at Dave's place
```

---

## Node Bridge

### Architecture

The CLI spawns one Node child process on startup and keeps it alive for the session. Communication is JSON-RPC over stdin/stdout. This avoids the ~200ms cold start penalty of launching Node per render.

```
Python CLI                     Node Bridge
    │                              │
    │  {"method":"renderText",     │
    │   "params":{"snapshot":{}}}  │
    │─────────────stdin───────────▶│
    │                              │  engine.js renderText()
    │◀────────────stdout──────────│
    │  {"result":"Basketball..."}  │
    │                              │
    │  {"method":"reduce",         │
    │   "params":{"snapshot":{},   │
    │    "event":{}}}              │
    │─────────────stdin───────────▶│
    │                              │  engine.js reduce()
    │◀────────────stdout──────────│
    │  {"result":{"applied":true,  │
    │   "snapshot":{}}}            │
    │                              │
```

### Bridge Script (`cli/aide_cli/bridge.js`)

```javascript
#!/usr/bin/env node
/**
 * Node bridge for AIde CLI.
 * Loads engine.js, exposes renderText + reduce over stdin/stdout JSON-RPC.
 * Long-lived process — spawned once per CLI session.
 */

const enginePath = process.argv[2] || require("path").join(
    require("os").homedir(), ".aide", "engine.js"
)
const { reduce, replay, emptyState, renderText } = require(enginePath)
const readline = require("readline")

const rl = readline.createInterface({ input: process.stdin })

rl.on("line", (line) => {
    try {
        const req = JSON.parse(line)
        let result

        switch (req.method) {
            case "renderText":
                result = renderText(req.params.snapshot)
                break

            case "reduce":
                result = reduce(req.params.snapshot, req.params.event)
                break

            case "replay":
                result = replay(req.params.events)
                break

            case "ping":
                result = "pong"
                break

            default:
                result = { error: `Unknown method: ${req.method}` }
        }

        process.stdout.write(JSON.stringify({ id: req.id, result }) + "\n")
    } catch (err) {
        process.stdout.write(JSON.stringify({
            id: null,
            error: err.message
        }) + "\n")
    }
})

// Signal readiness
process.stdout.write(JSON.stringify({ ready: true }) + "\n")
```

### Python Client (`cli/aide_cli/node_bridge.py`)

```python
import json
import subprocess
import os
from pathlib import Path

class NodeBridge:
    """Manages long-lived Node child process for engine operations."""

    def __init__(self):
        self.process = None
        self._id = 0

    def start(self):
        """Spawn Node process. Called once on CLI startup."""
        bridge_path = Path(__file__).parent / "bridge.js"
        engine_path = Path.home() / ".aide" / "engine.js"

        if not engine_path.exists():
            raise RuntimeError("Engine not found. Run `aide login` or check network.")

        self.process = subprocess.Popen(
            ["node", str(bridge_path), str(engine_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Wait for ready signal
        line = self.process.stdout.readline()
        msg = json.loads(line)
        assert msg.get("ready"), "Node bridge failed to start"

    def call(self, method: str, params: dict) -> any:
        """Send JSON-RPC call, return result."""
        self._id += 1
        request = json.dumps({"id": self._id, "method": method, "params": params})
        self.process.stdin.write(request + "\n")
        self.process.stdin.flush()

        line = self.process.stdout.readline()
        response = json.loads(line)

        if "error" in response:
            raise RuntimeError(f"Node bridge error: {response['error']}")

        return response["result"]

    def render_text(self, snapshot: dict) -> str:
        """Render snapshot as unicode text."""
        return self.call("renderText", {"snapshot": snapshot})

    def stop(self):
        """Kill Node process."""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            self.process = None
```

### Engine Fetching

The CLI fetches `engine.js` from the server on every startup. No vendored copy — the CLI always runs the latest engine.

```
aide REPL startup:
  1. Check Node is available
  2. GET {api_url}/api/engine.js → save to ~/.aide/engine.js
  3. Spawn Node bridge with that file
```

The server serves the engine from a simple static route:

```python
@router.get("/api/engine.js")
async def get_engine():
    """Serve current engine.js. No auth required."""
    return FileResponse("engine/builds/engine.js", media_type="application/javascript")
```

**Tradeoffs:** This adds ~100-200ms to CLI startup (one HTTP fetch) but guarantees the CLI and server are always in sync. No version mismatch bugs. No `aide update` command needed. R2 CDN caching comes later when startup latency matters.

**Offline:** If the fetch fails (no network), the CLI falls back to `~/.aide/engine.js` from the last successful fetch. If no cached copy exists, the CLI starts without the Node bridge — streaming and `/history` still work, but `/view` and `/watch` print a warning: `Engine unavailable. Connect to the network to enable text rendering.`

**Node requirement:** Node 18+ must be available on the system. The CLI checks on startup:

```python
def check_node():
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        version = int(result.stdout.strip().lstrip("v").split(".")[0])
        if version < 18:
            print("aide requires Node.js 18+. Current:", result.stdout.strip())
            sys.exit(1)
    except FileNotFoundError:
        print("aide requires Node.js. Install: https://nodejs.org")
        sys.exit(1)
```

---

## New REPL Commands

### `/view` — Render Current State

```
aide > /view
Basketball League
═════════════════

Roster
──────
  Mike    │  Record: 3-1  │  Status: Active
  Dave    │  Record: 2-2  │  Status: Active

Schedule
────────
  Game 5  │  Date: Feb 27  │  Home: Mike  │  Away: Tom
```

Implementation:
1. `GET /api/aides/{aide_id}` → includes `snapshot` in response
2. Pass snapshot to `node_bridge.render_text(snapshot)`
3. Print result

### `/watch` — Live Render After Each Turn

A toggle that automatically renders the text view after every message.

```
aide > /watch on
  Watch mode: showing state after each message.

aide > mike's team beat dave's 88-72
  Standings updated. Mike: 3-1. Dave: 2-2.

  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄

  Basketball League
  ═════════════════

  Roster
  ──────
    Mike    │  Record: 3-1  │  Status: Active
    Dave    │  Record: 2-2  │  Status: Active
  ...

aide > /watch off
  Watch mode: off.
```

The dotted separator (`┄`) visually divides the voice response from the rendered state.

When watch mode is on, after each `done` SSE event:
1. Fetch updated snapshot from `GET /api/aides/{aide_id}`
2. Render via node bridge
3. Print below the voice response

---

## Updated REPL Commands Table

Adding to the CLI spec:

| Command | Action |
|---------|--------|
| `/history [n]` | Show last n messages (default 20) |
| `/view` | Render current aide state as unicode text |
| `/watch [on\|off]` | Toggle auto-render after each message |

Updated `/help` output:

```
aide > /help

Commands:
  /list           Show your aides
  /switch <n>     Switch to a different aide
  /new            Start a new aide
  /page           Open published page in browser
  /info           Current aide details
  /history [n]    Show last n messages (default 20)
  /view           Render current state in terminal
  /watch [on|off] Auto-render state after each message
  /help           Show this help
  /quit           Exit (or Ctrl-D)

Everything else is sent as a message to the current aide.
```

---

## Streaming + Watch Mode Combined

When both streaming and watch mode are active, the full turn looks like:

```
aide > granite countertops came in at $4,200
  Countertops: $4,200. Total: $18,350 of $25,000.    ← streamed voice

  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄

  Home Renovation Budget                               ← renderText()
  ════════════════════════

  Expenses
  ────────
    Countertops     │  $4,200   │  Installed
    Flooring        │  $6,800   │  In Progress
    Plumbing        │  $3,200   │  Complete
    Electrical      │  $4,150   │  Complete

  Summary
  ───────
    Total Spent: $18,350
    Budget: $25,000
    Remaining: $6,650
```

### Timing

```
t=0.0s   User sends message
t=0.8s   First voice token streams to terminal
t=1.5s   Voice complete. Print newline.
t=1.6s   Fetch updated snapshot (GET /api/aides/{id})
t=1.7s   Node bridge renderText() (<5ms)
t=1.7s   Print separator + rendered state
t=1.8s   Prompt re-enabled
```

The snapshot fetch adds ~100ms. The Node bridge render is <5ms. Total overhead for watch mode: ~150ms after voice completes — imperceptible.

---

## Backend Changes

### New: Include Snapshot in Aide Response

`GET /api/aides/{aide_id}` currently returns aide metadata. Add an `include_snapshot` query param:

```
GET /api/aides/{aide_id}?include_snapshot=true
```

Response adds:
```json
{
  "id": "...",
  "title": "Basketball League",
  "snapshot": { ... },   // full AideState
  "status": "published",
  "slug": "basketball-league",
  ...
}
```

This avoids a separate endpoint. The web editor already has the snapshot in memory; only the CLI needs to fetch it explicitly.

### New: `renderText` Export in engine.js

Add `renderText` and `renderEntityText` to `engine.js` exports:

```javascript
exports.renderText = renderText;
```

This is a backwards-compatible addition. Existing imports are unaffected.

---

## Files to Create

| File | Purpose |
|------|---------|
| `cli/aide_cli/bridge.js` | Node bridge — JSON-RPC over stdin/stdout, loads engine from `~/.aide/engine.js` |
| `cli/aide_cli/node_bridge.py` | Python client for Node bridge (spawn, call, restart) |
| `backend/routes/engine.py` | `GET /api/engine.js` — serves current engine build |

## Files to Modify

| File | Changes |
|------|---------|
| `engine/builds/engine.js` | Add `renderText`, `renderEntityText`, `humanize`, `fmtValueText` |
| `engine/builds/engine.ts` | Add TypeScript types for renderText |
| `cli/aide_cli/repl.py` | Add `/view`, `/watch`, `/history` commands; switch to async SSE loop |
| `cli/aide_cli/client.py` | Add SSE streaming support; add `get_aide(id, include_snapshot)`; add `fetch_engine()` |
| `cli/aide_cli/config.py` | Engine cache path (`~/.aide/engine.js`) |
| `backend/routes/aides.py` | Add `include_snapshot` query param to GET aide endpoint |
| `backend/main.py` | Register engine router |

## Existing (No Changes)

- `backend/services/streaming_orchestrator.py` — SSE streaming already works
- `backend/routes/conversations.py` — conversation history API already exists
- `backend/repos/conversation_repo.py` — conversation CRUD already exists

---

## Testing Plan

### Unit Tests (CI — `pytest cli/`)

- Node bridge: start, ping/pong, renderText, stop, restart on crash
- History formatting: user/assistant prefixes, blank lines, truncation
- SSE parser: voice events extracted, primitives ignored, done triggers callback
- ANSI color codes: correct escape sequences for user vs assistant messages

### Node Bridge Tests (CI — `node --test`)

- `renderText` with empty snapshot → title only
- `renderText` with groceries → checkmarks for booleans
- `renderText` with roster → field separator table format
- `renderText` with annotations → bullet list
- `renderText` determinism: same snapshot → identical output × 100
- JSON-RPC error handling: malformed input, unknown method

### Integration Tests (CI — `pytest backend/`)

- `GET /api/engine.js` returns valid JavaScript (no auth required)
- `GET /api/engine.js` response includes `renderText` export
- `GET /api/aides/{id}?include_snapshot=true` returns snapshot
- `GET /api/aides/{id}` without param does NOT return snapshot (payload size)
- SSE endpoint streams voice events with Bearer token auth
- Conversation history endpoint returns messages in order

### Local Dev

```bash
# Start backend
uvicorn backend.main:app --reload

# In another terminal — test streaming
aide --api-url http://localhost:8000

aide > test message
  [should see streamed response]

aide > /view
  [should see unicode render]

aide > /watch on
aide > another message
  [voice streams, then state renders]
```

### Node Bridge Smoke Test

```bash
# Fetch engine first
curl -s http://localhost:8000/api/engine.js -o ~/.aide/engine.js

# Direct bridge test without CLI
echo '{"id":1,"method":"ping","params":{}}' | node cli/aide_cli/bridge.js
# Should output: {"ready":true}\n{"id":1,"result":"pong"}

echo '{"id":2,"method":"renderText","params":{"snapshot":{"version":1,"meta":{"title":"Test"},"collections":{},"relationships":[],"relationship_types":{},"constraints":[],"blocks":{},"views":{},"styles":{},"annotations":[]}}}' | node cli/aide_cli/bridge.js
# Should output: {"ready":true}\n{"id":2,"result":"Test\n═══"}
```

### E2E (Manual)

- Stream a long L3 response (first aide creation) — verify progressive text output
- Ctrl-C during stream — verify clean interrupt, prompt returns
- `/history` after 10+ exchanges — verify correct ordering and formatting
- `/view` on complex aide (50+ entities) — verify readable layout
- `/watch on` + rapid messages — verify renders don't overlap
- Kill Node process mid-session — verify bridge restarts transparently
- No Node installed — verify clear error message and exit

---

## What's Explicitly Not in v1

- **Color themes** — Fixed ANSI colors (green for aide, dim for user). No `--theme` flag.
- **Wide table rendering** — No auto-width calculation based on terminal width. Fixed 2-space indent.
- **Pager** — No `less`-style scrolling for `/view` output. Use terminal scroll.
- **Local reduce** — The CLI doesn't apply primitives locally. Server is always authoritative. The Node bridge *can* run `reduce()` but we don't use it in v1.
- **Custom renderText templates** — Uses the built-in generic renderer. Schema-specific `render_text` Mustache templates come later.
- **`aide update`** — Engine is fetched fresh on every startup. Explicit update command not needed.
