# 02: Tool Calls

> **Prerequisites:** [Data Model](core_data_model.md)
> **Next:** [Streaming Pipeline](core_streaming_pipeline.md) (how tool calls flow from LLM to screen)

---

## Overview

The LLM communicates state changes via **Anthropic tool calls**. Three tools handle all mutations:

| Tool | Purpose |
|------|---------|
| `mutate_entity` | Create, update, or remove entities |
| `voice` | State reflections shown in chat |
| `set_relationship` | Link entities together |

The server parses each tool call, applies it through the reducer, and sends entity deltas to the client via WebSocket.

---

## Tools

### `mutate_entity`

All entity operations use a single tool with an `action` field:

```json
{
  "name": "mutate_entity",
  "input": {
    "action": "create",
    "id": "guest_linda",
    "parent": "guests",
    "display": "row",
    "props": {
      "name": "Aunt Linda",
      "rsvp": "yes",
      "traveling_from": "Portland"
    }
  }
}
```

| Action | Required Fields | Description |
|--------|-----------------|-------------|
| `create` | `id`, `parent`, `props` | Create new entity. `display` optional (inherited from parent). |
| `update` | `ref`, `props` | Merge props into existing entity. |
| `remove` | `ref` | Soft-delete entity and descendants. |

**Field details:**

| Field | Notes |
|-------|-------|
| `id` | snake_case, max 64 chars. Used for create. |
| `ref` | Reference to existing entity. Used for update/remove. |
| `parent` | Parent entity ID. `"root"` for top-level. |
| `display` | Render hint: `page`, `card`, `table`, `checklist`, `row`, etc. |
| `props` | Data payload. Schema inferred from values. |

### `voice`

State reflections shown in the chat panel:

```json
{
  "name": "voice",
  "input": {
    "text": "Added Aunt Linda to guest list. She's bringing potato salad."
  }
}
```

Max ~100 characters. No first person, no encouragement, no emojis. Optional — simple updates often don't need one.

### `set_relationship`

Link entities together:

```json
{
  "name": "set_relationship",
  "input": {
    "from": "guest_linda",
    "to": "food_potato_salad",
    "type": "bringing"
  }
}
```

---

## Server-Side Processing

The server receives tool calls from the Anthropic API stream and:

1. **Normalizes** the tool call to internal event format
2. **Applies** through the reducer (`engine/kernel/reducer.py`)
3. **Sends** entity deltas to client via WebSocket
4. **Persists** updated snapshot to PostgreSQL

### Internal Event Format

Tool calls are normalized to short-form events for the reducer:

```python
# mutate_entity create -> entity.create
{"t": "entity.create", "id": "guest_linda", "parent": "guests", "display": "row", "p": {"name": "Aunt Linda"}}

# mutate_entity update -> entity.update
{"t": "entity.update", "ref": "guest_linda", "p": {"rsvp": "confirmed"}}

# mutate_entity remove -> entity.remove
{"t": "entity.remove", "ref": "guest_linda"}

# voice -> voice
{"t": "voice", "text": "Guest added."}

# set_relationship -> rel.set
{"t": "rel.set", "from": "guest_linda", "to": "food_potato_salad", "type": "bringing"}
```

---

## Primitives Reference

The reducer handles these internal event types:

| Category | Event Types |
|----------|-------------|
| Entity | `entity.create`, `entity.update`, `entity.remove` |
| Relationship | `rel.set`, `rel.remove` |
| Meta | `meta.set`, `meta.update` |
| Style | `style.set`, `style.entity` |
| Signal | `voice` |

---

## Examples

### First Creation (L3, ~10 tool calls)

```
mutate_entity: action=create, id=page, parent=root, display=page, props={title: "Sophie's Graduation 2026"}
voice: "Building graduation party page."
mutate_entity: action=create, id=ceremony, parent=page, display=card, props={title: "Ceremony", date: "2026-05-22"}
mutate_entity: action=create, id=guests, parent=page, display=table, props={title: "Guest List"}
mutate_entity: action=create, id=food, parent=page, display=table, props={title: "Food & Drinks"}
mutate_entity: action=create, id=todos, parent=page, display=checklist, props={title: "To Do"}
voice: "Structure ready. Adding starter tasks."
mutate_entity: action=create, id=todo_invites, parent=todos, props={task: "Send invitations", done: false}
mutate_entity: action=create, id=todo_venue, parent=todos, props={task: "Book party venue", done: false}
voice: "Graduation page created. Add guests to get started."
```

### Simple Update (~2 tool calls)

```
mutate_entity: action=create, id=guest_linda, parent=guests, props={name: "Aunt Linda", rsvp: "yes"}
set_relationship: from=guest_linda, to=food_potato_salad, type=bringing
```

### Direct Edit (No LLM)

When the user clicks a field and edits it directly, the client sends via WebSocket:

```json
{"type": "direct_edit", "entity_id": "guest_linda", "field": "rsvp", "value": "confirmed"}
```

The server applies this through the same reducer pipeline. Same event format, same undo behavior — just bypasses the LLM.

---

## Token Efficiency

Tool calls are more token-efficient than generating raw HTML:

| Approach | Tokens | Latency |
|----------|--------|---------|
| v1: HTML + explanations | ~3-5K | ~10s |
| v2: Tool calls only | ~600-1500 | <4s |

The LLM never generates what the renderer can derive.
