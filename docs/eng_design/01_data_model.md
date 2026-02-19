# 01: Data Model

> **Prerequisites:** [00 Overview](00_overview.md)
> **Next:** [02 JSONL Schema](02_jsonl_schema.md) (the wire format for mutating the model)

---

## The Entity Tree

All state in an aide is an entity tree. An entity can contain other entities. That's the whole data model.

```
grad_page (display: "page")
├── ceremony (display: "card")
│   props: {date: "2026-05-22", time: "10:00 AM", location: "UC Davis"}
├── guests (display: "table")
│   ├── aunt_linda
│   │   props: {name: "Aunt Linda", rsvp: "yes", traveling_from: "Portland"}
│   ├── uncle_steve
│   │   props: {name: "Uncle Steve", rsvp: "yes", dietary: "vegetarian"}
│   └── cousin_james
│       props: {name: "Cousin James", rsvp: "pending"}
├── food (display: "table")
│   ├── potato_salad
│   │   props: {item: "Potato Salad", who: "Aunt Linda"}
│   └── chips
│       props: {item: "Chips & Dip", who: "Uncle Steve"}
└── todos (display: "checklist")
    ├── send_invites
    │   props: {task: "Send invitations", done: false}
    └── book_venue
        props: {task: "Book party venue", done: true}
```

## Entity Shape

```
Entity {
  id: string          // unique, snake_case, max 64 chars
  parent: string      // parent entity ID ("root" for top-level)
  display: string     // render hint (page, card, table, list, checklist, etc.)
  props: {}           // the actual data — field names and values
  _removed: boolean   // soft delete flag
  _styles: {}         // visual overrides (highlight, color)
}
```

Every entity has exactly one parent. The `parent` field is the only structural relationship. This is a tree, not a graph — deterministic top-down rendering, no cycles, unambiguous containment.

## What Changed from v1

v1 had three parallel structures the LLM had to generate and keep consistent:

| v1 Concept | v2 Equivalent |
|-----------|--------------|
| Collection + schema | Entity with children (schema inferred from props) |
| Block tree | Entity tree (entity IS its block) |
| View (list view, table view) | `display` hint on entity |
| 25 primitive types | 13 primitive types + 4 signals |

Fewer concepts → fewer tokens → faster generation → simpler reducer.

---

## Relationships (Cross-Links)

The tree handles containment (what's inside what). Relationships handle connections across branches.

```
guests/aunt_linda ── bringing ──► food/potato_salad
guests/uncle_steve ── driving ──► guests/aunt_linda
```

```
Relationship {
  from: entity_id     // source
  to: entity_id       // target
  type: string        // "bringing", "driving", "assigned_to"
  cardinality: string // "many_to_one", "one_to_one", "many_to_many"
}
```

**Cardinality enforcement:**
- `many_to_one`: Setting a new link auto-removes the old one. "Seat Linda at table 5" auto-removes her from table 3.
- `one_to_one`: Both sides exclusive.
- `many_to_many`: No auto-removal.

Cardinality is set once per relationship type and persisted.

**When entities are removed:** Relationships involving removed entities are excluded from queries. The relationship data is preserved in the event log for undo.

**Renderer usage:** The renderer mostly walks the tree. It only references relationships when a display component needs to show connections (e.g., "Bringing: Potato Salad" on Linda's guest row).

---

## Schema Inference

v1 required upfront schema declaration (`collection.create` with field types). v2 infers schema from data.

When the first guest entity is created with `{name: "Aunt Linda", rsvp: "yes", traveling_from: "Portland"}`, the system infers:

| Value | Inferred Type |
|-------|--------------|
| `"Aunt Linda"` | string |
| `42` | int |
| `3.14` | float |
| `true` / `false` | boolean |
| `"2026-05-22"` | date (ISO pattern match) |
| `["a", "b"]` | list |

When a later entity adds a new field (e.g., `dietary: "vegetarian"` on Uncle Steve), the schema evolves — the new field is added as nullable for existing entities that don't have it.

This eliminates an entire class of primitives and means the LLM doesn't have to think about types — it just writes data.

---

## Display Hints

The `display` field tells the React compiler how to render an entity and its children. See [04 Display Components](04_display_components.md) for the full component catalog.

| Hint | Renders As | Best For |
|------|-----------|----------|
| `page` | Root container with title | Top-level aide entity |
| `section` | Titled collapsible section | Major groupings |
| `card` | Bordered card, props as key-value pairs | Singular important items |
| `list` | Vertical list | Simple enumerations |
| `table` | Table, children as rows, props as columns | Structured data with 3+ fields |
| `checklist` | List with checkboxes | Tasks, to-dos |
| `metric` | Large value with label | KPIs, counts |
| `text` | Rendered paragraph | Welcome messages, notes |
| `image` | Image from URL with caption | Photos |

**When omitted:** The compiler infers the display hint from the entity's props shape:
- Has `content` prop (string >20 chars) → `text`
- Has `src` prop → `image`
- Has `checked`/`done` boolean → parent treats as `checklist`
- Has 4+ props → parent treats as `table`
- Has <4 props → parent treats as `list`
- Is root → `page`

---

## Constraints

Constraints are rules about relationships or structure that the reducer enforces.

**Relationship constraints:** `exclude_pair` (keep Linda and Steve apart), `require_pair`, `max_links`, `min_links`.

**Structural constraints:** `max_children` (max 50 guests).

Constraints can be strict (violations reject the operation) or non-strict (violations warn but allow). Non-strict is the default — better to let the operation through and surface a warning than to silently reject.

---

## Event Sourcing

The entity tree is built by replaying an ordered list of events. Every mutation (from the LLM or from direct user edits) is an event. The reducer is a pure function: `events[] → snapshot`.

This enables:
- **Undo:** Replay events minus the last batch → previous state. See [07 Edge Cases](07_edge_cases.md).
- **Time travel:** Replay events up to any point → state at that point.
- **Determinism:** Same events always produce the same snapshot.
- **Debugging:** The event log is a complete audit trail.

Events are stored in the event log with full metadata (sequence number, timestamp, actor, source). The entity tree snapshot is derived state, rebuilt from events.

→ The event format is defined in [02 JSONL Schema](02_jsonl_schema.md).
