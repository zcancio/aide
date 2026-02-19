# 02: JSONL Schema

> **Prerequisites:** [01 Data Model](01_data_model.md)
> **Next:** [03 Streaming Pipeline](03_streaming_pipeline.md) (how these lines get from LLM to screen)

---

## Wire Format

Every state mutation is a single line of JSON. The LLM emits one line per operation. The server parses each line on arrival.

```json
{"t":"entity.create","id":"guest_linda","parent":"guests","display":"row","p":{"name":"Aunt Linda","rsvp":"yes"}}
```

Field names are abbreviated to minimize tokens:

| Wire | Full Name | Description |
|------|-----------|-------------|
| `t` | type | Primitive type |
| `id` | id | Entity ID |
| `parent` | parent | Parent entity ID |
| `display` | display | Render hint |
| `p` | props | Data payload |
| `ref` | ref | Reference to existing entity |
| `from` | from | Relationship source |
| `to` | to | Relationship target |

The server expands abbreviations before writing to the event log.

---

## Primitives at a Glance

| Category | Primitives | Count |
|----------|-----------|-------|
| Entity | `entity.create`, `entity.update`, `entity.remove`, `entity.move`, `entity.reorder` | 5 |
| Relationship | `rel.set`, `rel.remove`, `rel.constrain` | 3 |
| Style | `style.set`, `style.entity` | 2 |
| Meta | `meta.set`, `meta.annotate`, `meta.constrain` | 3 |
| **Signals** | `escalate`, `voice`, `batch.start`, `batch.end` | 4 |
| **Total** | | **17** (13 state-modifying + 4 signals) |

---

## Entity Primitives

### `entity.create`

```json
{"t":"entity.create","id":"guest_linda","parent":"guests","display":"row","p":{"name":"Aunt Linda","rsvp":"yes","traveling_from":"Portland"}}
```

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | snake_case, max 64 chars |
| `parent` | yes | Parent entity ID. `"root"` for top-level. |
| `display` | no | Inherited from parent if omitted. |
| `p` | yes | Props. Schema inferred from values. |

Rejects if `id` exists or `parent` doesn't exist. Parents must be created before children.

### `entity.update`

```json
{"t":"entity.update","ref":"guest_linda","p":{"rsvp":"confirmed","dietary":"vegetarian"}}
```

Merges into existing props. Unmentioned fields unchanged. New fields extend the schema.

### `entity.remove`

```json
{"t":"entity.remove","ref":"guest_linda"}
```

Soft-deletes entity and all descendants. Data preserved for undo.

### `entity.move`

```json
{"t":"entity.move","ref":"guest_linda","parent":"vip_guests","position":0}
```

Moves entity (and descendants) to new parent. `position` optional (appends if omitted).

### `entity.reorder`

```json
{"t":"entity.reorder","ref":"guests","children":["guest_steve","guest_linda","guest_james"]}
```

Replaces child order. Must include all non-removed children.

---

## Relationship Primitives

### `rel.set`

```json
{"t":"rel.set","from":"guest_linda","to":"food_potato_salad","type":"bringing","cardinality":"many_to_one"}
```

`cardinality` set once per type, persisted. `many_to_one` auto-removes existing link from source. Rejects if either entity missing.

### `rel.remove`

```json
{"t":"rel.remove","from":"guest_linda","to":"food_potato_salad","type":"bringing"}
```

### `rel.constrain`

```json
{"t":"rel.constrain","id":"no_linda_steve","rule":"exclude_pair","entities":["guest_linda","guest_steve"],"rel_type":"seated_at","message":"Keep apart"}
```

Rules: `exclude_pair`, `require_pair`, `max_links`, `min_links`. Non-strict by default.

---

## Style Primitives

### `style.set` — Global tokens
```json
{"t":"style.set","p":{"primary_color":"#2d3748","font_family":"Inter","density":"comfortable"}}
```

### `style.entity` — Per-entity overrides
```json
{"t":"style.entity","ref":"guest_linda","p":{"highlight":true,"color":"#e53e3e"}}
```

---

## Meta Primitives

### `meta.set` — Aide-level metadata
```json
{"t":"meta.set","p":{"title":"Sophie's Graduation 2026","identity":"Graduation party coordination for ~40 guests"}}
```

### `meta.annotate` — Append a note
```json
{"t":"meta.annotate","p":{"note":"Guest count updated after Aunt Carol confirmed.","pinned":false}}
```

### `meta.constrain` — Structural constraint
```json
{"t":"meta.constrain","id":"max_guests","rule":"max_children","parent":"guests","value":50,"message":"Max 50 guests","strict":true}
```

---

## Signals

Signals instruct the server but **don't modify the entity graph.**

### `escalate` — Route to a higher tier

```json
{"t":"escalate","tier":"L4","reason":"query","extract":"do we have enough food for everyone?"}
```

Server queues the extracted text for async processing. See [05 Intelligence Tiers](05_intelligence_tiers.md).

Reasons: `query`, `unknown_entity_shape`, `ambiguous_intent`, `complex_conditional`, `structural_change`.

### `voice` — State reflection for chat

```json
{"t":"voice","text":"Guest list: 38 confirmed. Food: 12 dishes committed."}
```

Max 100 characters. No first person, no encouragement, no emojis. Optional — most L2 updates don't need one. For L3 creation streams, emit every ~8-10 lines to narrate progress.

### `batch.start` / `batch.end` — Atomic render group

```jsonl
{"t":"batch.start"}
{"t":"entity.create","id":"food_mains","parent":"food","display":"list","p":{"title":"Main Dishes"}}
{"t":"entity.move","ref":"food_ribs","parent":"food_mains"}
{"t":"entity.move","ref":"food_chicken","parent":"food_mains"}
{"t":"batch.end"}
```

Server buffers deltas between start/end, flushes as one atomic update. Safety valve: 30-second timeout forces flush. If stream ends mid-batch, flush what's buffered.

**When to use:** Restructuring operations (moving multiple entities). Normal top-down creation doesn't need batching. See [03 Streaming Pipeline](03_streaming_pipeline.md) for details.

---

## Event Wrapping

The LLM emits abbreviated JSONL. The server wraps each line in a full event envelope before writing to the log:

```json
{
  "id": "evt_20260522_007",
  "sequence": 7,
  "timestamp": "2026-05-22T14:30:00Z",
  "actor": "user_abc123",
  "source": "web",
  "message_id": "msg_xyz",
  "type": "entity.create",
  "payload": {
    "id": "guest_linda",
    "parent": "guests",
    "display": "row",
    "props": { "name": "Aunt Linda", "rsvp": "yes" }
  }
}
```

| Field | Description |
|-------|-------------|
| `id` | Unique event ID: `evt_{date}_{sequence}` |
| `sequence` | Monotonically increasing per aide |
| `timestamp` | UTC ISO 8601 |
| `actor` | User ID or `"system"` |
| `source` | `"web"`, `"direct_edit"`, `"signal"`, `"system"` |
| `message_id` | Groups events for undo (one user message = one batch) |
| `type` | Expanded primitive type |
| `payload` | Expanded field names |

The LLM never generates event metadata. It just generates data.

**Direct edits** use the same format — when the user clicks a field and changes it, the client emits `entity.update` through the same pipeline. Source is `"direct_edit"`. Same reducer, same event log, same undo behavior.

---

## Full Examples

### First Creation (L3, ~13 lines, ~600 tokens, ~3s)

```jsonl
{"t":"meta.set","p":{"title":"Sophie's Graduation 2026","identity":"Graduation party. ~40 guests."}}
{"t":"entity.create","id":"page","parent":"root","display":"page","p":{"title":"Sophie's Graduation 2026"}}
{"t":"entity.create","id":"ceremony","parent":"page","display":"card","p":{"title":"Ceremony","date":"2026-05-22","time":"10:00 AM","location":"UC Davis Pavilion"}}
{"t":"voice","text":"Ceremony details set. Building guest tracking."}
{"t":"entity.create","id":"guests","parent":"page","display":"table","p":{"title":"Guest List"}}
{"t":"entity.create","id":"food","parent":"page","display":"table","p":{"title":"Food & Drinks"}}
{"t":"entity.create","id":"travel","parent":"page","display":"table","p":{"title":"Travel & Lodging"}}
{"t":"entity.create","id":"todos","parent":"page","display":"checklist","p":{"title":"To Do"}}
{"t":"voice","text":"Structure ready. Adding starter tasks."}
{"t":"entity.create","id":"todo_invites","parent":"todos","p":{"task":"Send invitations","done":false}}
{"t":"entity.create","id":"todo_venue","parent":"todos","p":{"task":"Book party venue","done":false}}
{"t":"entity.create","id":"todo_cake","parent":"todos","p":{"task":"Order cake","done":false}}
{"t":"style.set","p":{"primary_color":"#2d3748","font_family":"Inter"}}
{"t":"voice","text":"Graduation page created. Add guests to get started."}
```

### L2 Update (~3 lines, ~150 tokens, <1s)

```jsonl
{"t":"entity.create","id":"guest_linda","parent":"guests","p":{"name":"Aunt Linda","rsvp":"yes","traveling_from":"Portland"}}
{"t":"entity.create","id":"food_potato_salad","parent":"food","p":{"item":"Potato Salad","who":"Aunt Linda"}}
{"t":"rel.set","from":"guest_linda","to":"food_potato_salad","type":"bringing"}
```

### Multi-Intent with Escalation (~2 lines from L2, query dispatched to L4)

```jsonl
{"t":"entity.create","id":"guest_steve","parent":"guests","p":{"name":"Uncle Steve","rsvp":"yes","dietary":"vegetarian"}}
{"t":"escalate","tier":"L4","reason":"query","extract":"do we have enough vegetarian options?"}
```
