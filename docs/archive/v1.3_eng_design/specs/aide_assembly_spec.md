# AIde — Assembly Spec (v1.3)

**Purpose:** The assembly layer sits between the pure functions (reducer, renderer) and the outside world (R2 storage, the orchestrator, published URLs). It coordinates: loading an aide's HTML file, extracting its embedded state, applying new events through the reducer, re-rendering through the renderer, reassembling the HTML file, and uploading it. It also handles creation, forking, parsing, and integrity checks.

The reducer and renderer are pure. The assembly is where IO happens.

**Companion docs:** `unified_entity_model.md`, `aide_reducer_spec.md`, `aide_renderer_spec.md`, `aide_primitive_schemas_spec.md`, `aide_architecture.md`

---

## Contract

```python
class AideAssembly:
    """
    Manages the lifecycle of an aide's HTML file.
    Coordinates reducer + renderer + storage.
    """

    async def load(self, aide_id: str) -> AideFile
    async def apply(self, aide_file: AideFile, events: list[Event]) -> ApplyResult
    async def save(self, aide_file: AideFile) -> None
    async def create(self, blueprint: Blueprint) -> AideFile
    async def fork(self, aide_id: str) -> AideFile
    async def publish(self, aide_file: AideFile) -> str
```

```python
@dataclass
class AideFile:
    aide_id: str
    snapshot: AideState          # v1.3: includes schemas, entities (not collections)
    events: list[Event]
    blueprint: Blueprint
    html: str                    # The full assembled HTML string
    last_sequence: int           # Highest event sequence number
    size_bytes: int              # Total file size
    loaded_from: str             # "r2" or "new"
```

**v1.3 AideState structure:**
```python
AideState {
    version: int           # 3
    meta: dict             # title, identity, visibility
    schemas: dict          # TypeScript interfaces + templates
    entities: dict         # entities with _schema references
    blocks: dict           # page structure
    styles: dict           # visual tokens
    constraints: list      # aide-level rules
    annotations: list      # notes
}
```

```python
@dataclass
class ApplyResult:
    aide_file: AideFile          # Updated file with new state, events, and HTML
    applied: list[Event]         # Events that were applied
    rejected: list[tuple[Event, str]]  # Events that failed + reason
    warnings: list[Warning]      # From the reducer
```

---

## Operations

### `load` — Read an aide from R2

```
load(aide_id) → AideFile

Steps:
1. Fetch HTML file from R2: aide-workspaces/{aide_id}/index.html
   → If not found: raise AideNotFound
2. Parse the HTML file (see Parsing below)
   → Extract blueprint from <script type="application/aide-blueprint+json">
   → Extract snapshot from <script type="application/aide+json">
   → Extract events from <script type="application/aide-events+json">
3. Validate snapshot version field
   → If version > supported: raise VersionNotSupported
4. Determine last_sequence from events (max sequence number, or 0 if no events)
5. Return AideFile with all extracted data

Errors:
  AideNotFound — file doesn't exist in R2
  ParseError — HTML exists but embedded JSON is malformed
  VersionNotSupported — snapshot version is from a future format
```

**Caching:** The orchestrator may cache loaded AideFiles in memory for the duration of a request. Do not cache across requests — the file may have changed (another ear applied events).

### `apply` — Run events through reducer and re-render

```
apply(aide_file, events) → ApplyResult

Steps:
1. Assign metadata to each event:
   → id: evt_{date}_{next_sequence}
   → sequence: aide_file.last_sequence + 1, +2, +3...
   → timestamp: now (UTC)
   (actor, source, intent, message come from the caller)

2. For each event, in order:
   a. Validate primitive payload (aide_primitive_schemas.md validation rules)
      → If invalid: add to rejected list, skip to next event
   b. reduce(aide_file.snapshot, event) → ReduceResult
      → If rejected: add to rejected list with error reason, skip
      → If applied: update aide_file.snapshot, collect warnings
      → Append event to aide_file.events

3. If any events were applied:
   a. Re-render: render(snapshot, blueprint, events, options) → html string
   b. Update aide_file.html with new HTML
   c. Update aide_file.last_sequence
   d. Update aide_file.size_bytes

4. Return ApplyResult with updated file, applied events, rejections, warnings

Properties:
  - Partial application: if event 2 of 5 is rejected, events 1, 3, 4, 5 still apply
  - Order preserved: events are applied in the order given
  - No IO: apply is purely in-memory. Call save() to persist.
```

### `save` — Write an aide back to R2

```
save(aide_file) → None

Steps:
1. Upload aide_file.html to R2: aide-workspaces/{aide_id}/index.html
   → Content-Type: text/html; charset=utf-8
   → Cache-Control: no-cache (workspace files are mutable)
2. Update metadata in Postgres:
   → aides.updated_at = now()
   → aides.size_bytes = aide_file.size_bytes (if tracked)

Errors:
  R2UploadFailed — retry once, then raise
```

**Atomicity:** R2 PutObject is atomic — readers see either the old version or the new version, never a partial write. This means save doesn't need locking for correctness. Two concurrent saves will both succeed; the last one wins. For v1 (single writer per aide), this is fine. Multi-writer (v2) needs optimistic concurrency (see Concurrency section).

### `create` — Initialize a new aide

```
create(blueprint) → AideFile

Steps:
1. Generate aide_id (uuid4 or nanoid)
2. Build empty snapshot (v1.3 structure):
   {
     version: 3,
     meta: {},
     schemas: {},
     entities: {},
     blocks: { block_root: { type: "root", children: [] } },
     styles: {},
     constraints: [],
     annotations: []
   }
3. Set snapshot.meta.title from blueprint.identity (first sentence or "Untitled")
4. Render HTML from empty snapshot + blueprint
5. Return AideFile with:
   → snapshot: empty state
   → events: []
   → blueprint: provided blueprint
   → html: rendered empty page
   → last_sequence: 0
   → loaded_from: "new"

Note: create does NOT save to R2 automatically. The caller decides
when to persist (typically after the first batch of events from L3
schema synthesis, so an empty file never hits storage).
```

### `publish` — Copy workspace file to published bucket

```
publish(aide_file) → url: str

Steps:
1. Determine slug:
   → Use aides.slug from Postgres if set
   → Otherwise generate: 8-char nanoid, lowercase alphanumeric
2. Optionally strip or compact event log for published version:
   → If aide_file.events > 500: strip events (snapshot is sufficient for viewing)
   → Otherwise: include events (allows forking with full history)
3. Optionally inject footer for free tier:
   → Lookup user tier from Postgres
   → If free: render with footer option
   → If pro: render without footer
4. Upload to R2: aide-published/{slug}/index.html
   → Content-Type: text/html; charset=utf-8
   → Cache-Control: public, max-age=60 (short cache — pages update frequently)
5. Record in published_versions table:
   → aide_id, version (increment), r2_key, size_bytes, published_at
6. Return URL: https://toaide.com/p/{slug}

Published vs. workspace:
  - Workspace (aide-workspaces/): the living file, updated on every event
  - Published (aide-published/): the public snapshot, updated on publish
  
For v1, publish happens on every save (auto-publish). Users always see the latest.
For v2, publish can be gated (draft mode, scheduled publish).
```

### `fork` — Clone an aide

```
fork(aide_id) → AideFile

Steps:
1. Load source aide
2. Create new aide_id
3. Copy snapshot (deep clone)
4. Copy blueprint
5. Clear events (forked aide starts with clean history)
6. Clear all entity _created_seq, _updated_seq, _removed_seq metadata
7. Update snapshot.meta: remove title (or prefix with "Copy of")
8. Re-render HTML with new snapshot
9. Return new AideFile (unsaved — caller persists)

What carries over: schema, entities, blocks, views, styles, blueprint
What doesn't: events, conversation history, macros, user identity
```

---

## Parsing

The parser extracts structured data from an existing HTML file. This is the inverse of assembly — it reads what the renderer wrote.

```python
def parse_aide_html(html: str) -> ParsedAide:
    """
    Extract blueprint, snapshot, and events from an aide HTML file.
    Uses standard HTML parsing — no regex on script tags.
    """
```

```python
@dataclass
class ParsedAide:
    blueprint: Blueprint | None
    snapshot: AideState | None   # v1.3: includes schemas, entities
    events: list[Event]
    title: str                    # From <title> tag
    has_blueprint: bool
    has_snapshot: bool
    has_events: bool
    version: int                  # Snapshot version (3 for v1.3)
```

### Extraction rules

| Script tag type | ID | Required | Content |
|----------------|-----|----------|---------|
| `application/aide-blueprint+json` | `aide-blueprint` | no | Blueprint JSON |
| `application/aide+json` | `aide-state` | yes | Snapshot JSON |
| `application/aide-events+json` | `aide-events` | no | Event log JSON array |

**Parsing steps:**

1. Parse HTML with a standard parser (Python `html.parser` or `lxml`).
2. Find `<script>` tags by their `type` attribute.
3. Extract inner text of each matching script tag.
4. Parse as JSON.
5. Validate: snapshot must have `version` field. Events must be an array.
6. Return ParsedAide.

**Tolerance:** The parser is lenient on missing optional sections. An aide file with only a snapshot (no blueprint, no events) is valid — it's just a snapshot with no history and no portability metadata. This allows hand-crafted or imported aides.

**Validation:** After parsing, the assembly can optionally run an integrity check (see below).

---

## Integrity Checks

```python
async def check_integrity(aide_file: AideFile) -> list[IntegrityIssue]:
    """
    Verify that the aide file is internally consistent.
    Returns empty list if everything checks out.
    """
```

### Checks performed

| Check | What | Severity |
|-------|------|----------|
| Replay match | Replay all events from empty state, compare to stored snapshot | Error |
| Sequence continuity | Event sequences are monotonically increasing with no gaps | Warning |
| Schema references | Every entity's `_schema` references an existing schema | Error |
| Schema validation | Every entity's fields match its schema's TypeScript interface | Warning |
| Block tree integrity | All parent references are valid, no orphan blocks, no cycles | Error |
| Entity path validity | All block sources reference existing entities | Warning |
| Blueprint present | Blueprint section exists and has identity + voice | Warning |
| Version check | Snapshot version is supported (currently 3) | Error |

**When to run:**

- After `load` — optional, for debugging. Skip in hot path.
- After `fork` — always, to catch corruption in source.
- On demand — admin/debug tool.
- NOT after `apply` — the reducer guarantees consistency.

**Replay match:** The most important check. Replay all events from empty state using the reducer, compare the resulting snapshot to the stored snapshot. If they differ, the stored snapshot is stale or corrupted. The replayed version is authoritative — it can replace the stored snapshot (self-healing).

```python
async def repair(aide_file: AideFile) -> AideFile:
    """
    Rebuild snapshot by replaying event log. Re-render HTML.
    Use when integrity check finds replay mismatch.
    """
    replayed = replay(aide_file.events)
    aide_file.snapshot = replayed
    aide_file.html = render(replayed, aide_file.blueprint, aide_file.events)
    return aide_file
```

---

## Concurrency

### v1: Single writer, no locking

In v1, each aide has one writer at a time (the orchestrator handling a single message). R2 PutObject is atomic. Last write wins. No locking needed.

Race condition window: if two messages for the same aide arrive simultaneously (e.g., two Signal group members text at the same moment), both orchestrator instances load the same snapshot, both apply their event independently, both save. The second save overwrites the first, losing one event.

**v1 mitigation:** Serialize messages per aide. The orchestrator queues messages per aide_id and processes them sequentially. A simple in-memory dict of asyncio locks per aide_id:

```python
_aide_locks: dict[str, asyncio.Lock] = {}

async def with_aide_lock(aide_id: str):
    if aide_id not in _aide_locks:
        _aide_locks[aide_id] = asyncio.Lock()
    async with _aide_locks[aide_id]:
        yield
```

This works for a single Railway instance. Multiple instances require a distributed lock (Redis, Postgres advisory locks) — deferred to v2.

### v2: Optimistic concurrency

For multi-instance deployments, use optimistic concurrency on R2:

1. On load, record the R2 object's ETag.
2. On save, use R2's `If-Match` conditional put with the ETag.
3. If the ETag changed (another writer saved), the put fails.
4. On conflict: reload, re-apply events, re-save.

This is the standard optimistic concurrency pattern. The event-sourced architecture makes re-application straightforward — just replay the failed events on top of the new snapshot.

---

## Event Log Compaction

For long-lived aides, the event log grows. Compaction reduces size while preserving the current state.

### Strategies

**Strip on publish:** The published file gets only the snapshot, no events. Viewers don't need history. The workspace file keeps the full log.

**Checkpoint:** After N events (e.g., 500), create a checkpoint: snapshot the current state as the new baseline, archive old events to a separate file or discard them. New events append from the checkpoint.

```python
async def compact(aide_file: AideFile, keep_recent: int = 50) -> AideFile:
    """
    Compact the event log.
    Keeps the most recent `keep_recent` events.
    The snapshot already reflects all events, so old events
    are redundant for rendering.
    """
    if len(aide_file.events) <= keep_recent:
        return aide_file  # Nothing to compact
    
    aide_file.events = aide_file.events[-keep_recent:]
    aide_file.html = render(aide_file.snapshot, aide_file.blueprint, aide_file.events)
    return aide_file
```

**When to compact:**
- When `aide_file.size_bytes` exceeds 200KB
- When `len(aide_file.events)` exceeds 500
- On publish (strip events from published copy)
- On explicit user request ("clean up history")

**What compaction loses:**
- Full time-travel (can only replay back to the checkpoint)
- Full audit trail (old events are gone)
- Full undo (can only undo recent events)

For v1, compaction is not needed — aides won't hit these limits during the MVP.

---

## R2 Layout

```
aide-workspaces/
  {aide_id}/
    index.html              ← The living aide file (snapshot + events + body + blueprint)

aide-published/
  {slug}/
    index.html              ← The published snapshot (possibly compacted)
```

**Key format rules:**
- aide_id is a UUID or nanoid. Immutable.
- slug is user-facing. Mutable (can be changed from random to custom on pro tier).
- Workspace is keyed by aide_id (internal). Published is keyed by slug (external).

**R2 operations used:**

| Operation | When | Notes |
|-----------|------|-------|
| GetObject | `load` | Returns full HTML string |
| PutObject | `save`, `publish` | Atomic overwrite |
| DeleteObject | Aide deletion | Remove workspace and published files |
| HeadObject | Size check, ETag for concurrency | Lightweight metadata fetch |

**R2 client setup:**

```python
import boto3

r2 = boto3.client(
    "s3",
    endpoint_url=config.R2_ENDPOINT,
    aws_access_key_id=config.R2_ACCESS_KEY,
    aws_secret_access_key=config.R2_SECRET_KEY,
    region_name="auto",
)

WORKSPACE_BUCKET = "aide-workspaces"
PUBLISHED_BUCKET = "aide-published"
```

---

## The Full Cycle

Here's the complete flow when a message arrives, using all the pieces:

```
1. Message arrives at ear (web chat, Signal)
2. Ear normalizes → POST /api/message { aide_id, text, image?, actor, source }

3. Orchestrator acquires aide lock

4. Assembly.load(aide_id)
   → Fetch from R2
   → Parse HTML → extract snapshot, events, blueprint
   → Return AideFile

5. Orchestrator sends to L2:
   → User message + snapshot + primitive schemas + conversation history
   → L2 returns primitives (or escalation → L3)

6. Assembly.apply(aide_file, primitives_as_events)
   → Validate each primitive
   → Reduce each event into snapshot
   → Re-render HTML from new snapshot
   → Return ApplyResult with updated AideFile

7. Assembly.save(aide_file)
   → Upload HTML to R2 workspace bucket

8. Assembly.publish(aide_file)
   → Upload HTML to R2 published bucket (possibly with footer, compacted events)
   → Return published URL

9. Orchestrator releases aide lock

10. Return response to ear:
    → Response text (from L2/L3)
    → Published page URL
    → Warnings (if any)

11. Ear sends response to user (web chat reply, Signal message)
```

**New aide flow** (first message, no aide_id):

```
1. Message arrives with no aide_id
2. Assembly.create(default_blueprint) → empty AideFile
3. Orchestrator sends to L3 (schema synthesis from first message)
4. L3 returns: collection.create + entity.create + block.set + view.create + meta.update
5. Assembly.apply(aide_file, L3_events)
6. Assembly.save(aide_file)
7. Assembly.publish(aide_file)
8. Record aide_id in Postgres (aides table)
9. Return response + page URL to user
```

---

## Error Recovery

| Failure | Impact | Recovery |
|---------|--------|----------|
| R2 read fails | Can't load aide | Retry once. If still fails, return error to user. |
| Reducer rejects all events | No state change | Return rejection reasons to orchestrator. Orchestrator can retry with L3. |
| R2 write fails | State updated in memory but not persisted | Retry once. If still fails, the event is lost. Event log in memory is correct — next successful save will include it. |
| R2 write conflict (v2) | Another writer saved first | Reload, re-apply failed events on new snapshot, re-save. |
| Parse error on load | HTML file is corrupted | Attempt repair from event log. If no events, aide is unrecoverable. Log alert. |
| Integrity check fails | Snapshot doesn't match events | Run repair (replay events → rebuild snapshot). Save repaired file. |

---

## Testing Strategy

**Test categories:**

1. **Round-trip.** Create → apply 10 events → save → load → verify snapshot matches. The most important test.

2. **Parse ↔ assemble.** Render an HTML file, parse it back, verify all extracted data matches the original inputs.

3. **Apply with rejections.** Send 5 events where #3 is invalid. Verify #1, #2, #4, #5 applied, #3 rejected with reason.

4. **Create empty.** Create a new aide, verify the HTML is valid, the snapshot is empty state, the blueprint is embedded.

5. **Fork.** Create an aide with 20 events, fork it, verify the fork has the same snapshot but empty events and a new aide_id.

6. **Publish with footer.** Publish a free-tier aide, verify footer appears. Publish a pro aide, verify no footer.

7. **Compaction.** Create an aide with 600 events, compact to 50, verify snapshot unchanged, event count is 50, HTML is smaller.

8. **Integrity check.** Deliberately corrupt a snapshot (change one field), run integrity check, verify it detects the mismatch. Run repair, verify it fixes it.

9. **Concurrency.** Simulate two concurrent applies to the same aide (using the lock mechanism), verify both events are preserved and ordered correctly.

10. **New aide flow.** Simulate a first message with no aide_id, verify the full create → L3 → apply → save → publish flow produces a valid aide at a URL.
