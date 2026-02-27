# AIde — Schema Design Spec

**Purpose:** Rules governing how the AI synthesizes, evolves, and renders entity schemas. Ensures structural consistency across runs while preserving flexibility for organic growth.

**Companion docs:** `01_data_model.md` (entity tree), `06_prompts.md` (L2/L3 instructions), `04_display_components.md` (display resolution)

---

## Principles

Three design philosophies inform how AIde handles schema:

**Protobuf philosophy — evolution is additive.** Add fields, don't remove them. New fields get sensible defaults. Never change a field's semantic meaning. Old entities without new fields work fine (nullable defaults to `null`). This is how an aide grows from "buy milk" to a categorized, assigned, budgeted grocery system without breaking anything that came before.

**BigQuery philosophy — nest only when necessary.** A prop can hold a list of strings. It becomes a child entity only when the items need their own fields. `["milk", "eggs"]` stays a list prop. `{item: "milk", store: "Whole Foods", price: 4.99}` becomes a child entity. The heuristic: if sub-items need more than one field, they're entities. If they're just a list of values, they're a prop.

**Deliberate schema philosophy — structure is chosen, not improvised.** The AI doesn't freestyle schemas. It classifies the domain into a known pattern, then fills in the specifics. The structural shape is predetermined. The model only decides field names and types — the part it's good at.

---

## Patterns

Every section in an aide maps to one of seven structural patterns. A pattern determines parent/child hierarchy and default display. The AI classifies on creation; the pattern is permanent for that section.

| Pattern | Structure | Default Display | Signal |
|---------|-----------|----------------|--------|
| **Flat list** | `root → item, item, item` | `list` or `checklist` | Simple items, no grouping field |
| **Roster** | `root → member, member, member` | `table` | People/things with role/status attributes |
| **Timeline** | `root → event, event, event` | `table` (sorted by date) | Date field present, chronological |
| **Tracker** | `root → subject → observation, obs` | `section` → `table` | Subjects tracked over time |
| **Board** | `root → item, item, item` | `cards` (grouped by status) | Status enum field present |
| **Ledger** | `root → line_item, line_item` | `table` + metric (total) | Amount/cost field present |
| **Assignment** | `root → slot, slot` + `root → assignee` + rels | `table` + relationships | Two entity types linked by relationships |
| **Grid** | `root → cell, cell, cell` (flat, coordinate-addressed) | `grid` (rows × cols) | Fixed dimensions, row/col fields |

### Composition

Most aides are 1–4 sections, each with its own pattern. Examples:

| Aide | Sections |
|------|----------|
| Grocery list | flat list |
| Poker league | roster + timeline + ledger |
| Group trip | roster + timeline + flat list (packing) + ledger (expenses) |
| Renovation | timeline (phases) + ledger (budget) + flat list (decisions) + board (materials) |
| Wedding | roster + timeline + ledger + flat list (todos) + assignment (seating) |
| Flu tracker | tracker |
| Super Bowl squares | grid (10×10) + roster (players) + ledger (pot) |
| Chess game | grid (8×8) |

### The Grid Pattern

Grids are fixed-dimension 2D layouts where cells are addressed by coordinate. Unlike other patterns where entities are ordered linearly, grid entities have `row` and `col` props that determine spatial position.

**Structure:** Flat entities under a section parent, each with `row` (int) and `col` (int) props. The section entity carries grid dimensions and optional axis labels.

```
squares (display: grid)
  props: {
    _rows: 10,
    _cols: 10,
    _row_labels: ["0","1","2","3","4","5","6","7","8","9"],
    _col_labels: ["0","1","2","3","4","5","6","7","8","9"],
  }
  ├── cell_0_0 (props: {row: 0, col: 0, owner: null})
  ├── cell_0_1 (props: {row: 0, col: 1, owner: "Mike"})
  └── ... (100 cells total)
```

**Key properties of grid sections:**

| Prop | Type | Description |
|------|------|-------------|
| `_rows` | int | Number of rows (set at creation, rarely changes) |
| `_cols` | int | Number of columns (set at creation, rarely changes) |
| `_row_labels` | list | Optional axis labels (team scores, rank numbers, letter coordinates) |
| `_col_labels` | list | Optional axis labels |

**Addressing:** "Mike claims row 3, column 7" → `entity.update` on the cell at that coordinate. L3 resolves the natural language coordinate reference to the entity ID.

**Cell ID convention:** Cell entity IDs encode their coordinates directly: `cell_{row}_{col}`. No lookup table needed — the ID *is* the index.

```
cell_0_0  cell_0_1  cell_0_2  ...  cell_0_9
cell_1_0  cell_1_1  cell_1_2  ...  cell_1_9
...
cell_9_0  cell_9_1  ...            cell_9_9
```

Coordinate resolution is string formatting:

```python
def cell_id(row: int, col: int) -> str:
    return f"cell_{row}_{col}"

def cell_coords(entity_id: str) -> tuple[int, int]:
    _, row, col = entity_id.split("_", 2)
    return int(row), int(col)
```

**Human-readable to index translation** is L3's job. The axis labels map human names to zero-indexed integers:

| Domain | Human input | Label lookup | Entity ID |
|--------|------------|-------------|-----------|
| Chess | "e4" | col `e` → index 4, row `4` → index 4 (from bottom) | `cell_4_4` |
| Super Bowl | "row 3, col 7" | Direct | `cell_3_7` |
| Bingo | "B-12" | col `B` → index 0, row `12` → index lookup | `cell_11_0` |
| Seating | "table 2, seat 5" | row → table index, col → seat index | `cell_1_4` |

The coordinate system lives in `_row_labels` and `_col_labels`. The entity ID is always numeric indices. L3 translates between the two.

**Pre-population:** L4 creates all cells on first message. A 10×10 grid = 100 `entity.create` calls. An 8×8 chessboard = 64 cells. This is front-loaded cost that makes subsequent updates cheap — "e4" is just an `entity.update` on a single cell.

**When to use grid vs table:**

| Use grid | Use table |
|----------|-----------|
| Fixed dimensions known at creation | Rows added/removed over time |
| Cells addressed by coordinate | Rows addressed by name/ID |
| 2D position is meaningful | Row order matters but column position doesn't |
| Sparse updates ("claim square 3,7") | Row-level updates ("update Mike's status") |

**Examples:**
- Super Bowl squares: 10×10, cells have `owner` and `paid` props, row/col labels are team score digits
- Chess: 8×8, cells have `piece` and `color` props, row labels 1–8, col labels a–h
- Seating chart (grid variant): rows × seats, cells have `guest` prop
- Bingo card: 5×5, cells have `number` and `called` props, col labels B-I-N-G-O

### Pattern evolution

Patterns aren't permanent — they evolve through additive operations. A flat list that gains a status enum becomes a board. A roster that gains a second entity type becomes an assignment. These transitions happen naturally and L3 handles them.

**The rule:** A pattern can evolve to any pattern reachable by additive operations (add fields, add sections, add relationships, change display). If it requires reparenting entities or deleting structural dimensions, it's a new aide.

**Lossless transitions (automatic, L3 handles):**

| From | To | What happens |
|------|----|-------------|
| flat list | checklist | Add a boolean field, change display |
| flat list | board | Add a status enum, renderer groups by it |
| flat list | table | Add 2+ fields, change display |
| flat list | timeline | Add a date field, sort by it |
| flat list | ledger | Add an amount field, add total metric |
| checklist | board | Add a status enum beyond done/not-done |
| checklist | table | Add 2+ fields, change display |
| roster | assignment | Add second entity type + relationships |
| timeline | ledger | Add amount fields to existing timeline entries |

All additive. No entities move. No parents change. Fields are added, display hints are updated, maybe a section is created. The structure just grew.

**Destructive transitions (disallowed — make a new aide):**

| From | To | Why |
|------|----|-----|
| anything | grid | Fundamentally different: fixed dimensions, coordinate-addressed cells |
| grid | anything | Loses 2D structure, cell IDs become meaningless |
| anything | tracker | Requires reparenting all entities under new subject parents |
| tracker | anything flat | Flattens a two-level hierarchy, loses subject grouping |

These require moving entities between parents or fundamentally reshaping the tree. L3 should respond:

> "Tracking by subject needs a different structure. Create a new aide for that?"

If someone's aide needs a destructive transition, they make a new aide. Aides are cheap to create, and the old one still exists.

---

## Field Evolution Rules

Inspired by protobuf's numbered field contract, adapted for AIde's schemaless props.

### Adding fields

New fields are always nullable unless a default is provided. Existing entities get `null` (or the default) for the new field. This is the most common evolution — an aide grows by gaining fields.

```
Turn 1:  "buy milk and eggs"
         → props: {name: "Milk", done: false}

Turn 10: "actually track which store each item is from"
         → field added: store (string?, default: null)
         → existing entities get store: null
         → new entities include store
```

**Rules:**
- New fields MUST be nullable (`?` suffix) OR have an explicit default
- Adding a required field without a default is rejected if entities exist
- Field names are always `snake_case`, singular nouns
- Max 20 fields per entity type (soft limit, warn at 15)

### Changing field types

Type changes follow a compatibility matrix. Compatible changes apply silently. Incompatible changes are rejected.

| From → To | Allowed | Notes |
|-----------|---------|-------|
| `string → enum` | Yes | If all existing values match enum options |
| `string → int` | Yes | If all existing values are numeric |
| `string → date` | Yes | If all existing values are ISO dates |
| `int → float` | Yes | Lossless widening |
| `int → string` | Yes | Lossless widening |
| `float → int` | Warn | Lossy truncation |
| `enum → enum` | Yes | If all existing values exist in new set |
| `enum → string` | Yes | Lossless widening |
| `bool → string` | Yes | Lossless widening |
| `string → bool` | No | Ambiguous |
| Any → `list` | No | Structural change |
| `list` → any | No | Structural change |

### Removing fields

Fields are never explicitly removed in normal operation. The AI simply stops writing to them. Old entities retain the value in their props; new entities omit it. The renderer skips fields not present on an entity.

If cleanup is needed (e.g., sensitive data), `field.remove` strips the value from all entities in the snapshot. The event log preserves history.

### Renaming fields

Renames propagate to all existing entities in the same operation. The old field key is deleted, the new key is set. Views referencing the old name update automatically.

```
field.update { collection: "tasks", name: "assignee", rename: "owner" }
→ all entities: delete props.assignee, set props.owner = old value
→ all views: sort_by/group_by/show_fields references updated
```

---

## The Array vs Entity Heuristic

When the AI encounters sub-items within an entity, it must decide: list prop or child entities?

### Use a list prop when:

- Items are single values (strings, numbers)
- Items don't need independent identity (no relationships, no updates by reference)
- The list is short and unlikely to grow past ~20 items
- Items don't need their own metadata

```json
{
  "id": "game_feb27",
  "props": {
    "date": "2026-02-27",
    "snacks": ["chips", "beer", "pretzels"]
  }
}
```

### Use child entities when:

- Items have 2+ fields each
- Items need to be individually updated ("mark the chips as bought")
- Items might have relationships to other entities
- Items could grow to need more fields over time
- Items need identity (referenced by name in conversation)

```json
{
  "id": "game_feb27",
  "props": { "date": "2026-02-27" },
  "_children": ["snack_chips", "snack_beer", "snack_pretzels"]
}
// where each child has props: {item: "Chips", who: "Mike", bought: false}
```

### The decision rule

```
if sub-items need > 1 field → child entities
if sub-items are just values → list prop
if unsure → start as list prop, promote to entities when a second field appears
```

This mirrors BigQuery's model: arrays work when items are simple. When items get complex, break them into their own rows.

---

## Display Resolution

Display is derived from schema shape, not chosen independently by the AI. This removes a degree of freedom and ensures consistency.

### Explicit hints

The AI can set `display` on any entity. When present, it overrides inference:

```
page, section, card, list, table, checklist, grid, metric, text, image
```

### Inference from props (when display is omitted)

| Condition | Inferred Display |
|-----------|-----------------|
| Has `src` or `url` prop | `image` |
| Has `content` prop (>20 chars) | `text` |
| Has `value`/`count` prop, ≤3 total props | `metric` |
| Has boolean `done`/`checked`/`completed` | `checklist` (on parent) |
| Children all have `row` + `col` props | `grid` (on parent) |
| Has 4+ uniform props across children | `table` (on parent) |
| Has <4 props per child | `list` (on parent) |
| Is a root entity | `page` |

### Inference from field count (for section-level)

| Fields per child entity | Default display |
|------------------------|-----------------|
| 1 field (just `name`) | `list` |
| 1 field (`name`) + 1 boolean | `checklist` |
| 2–3 fields | `cards` |
| 4+ fields | `table` |

### User overrides

"Show this as a table" is a single `entity.update` on the section:

```json
{"t": "entity.update", "ref": "tasks", "p": {"display": "table"}}
```

L2 handles this. No restructuring, no schema change, no L3 needed.

---

## Grouping Without Restructuring

When an aide needs visual grouping but doesn't need structural hierarchy, use field-based grouping instead of parent entities.

### The scenario

A flat list of Christmas activities gains a second day. Instead of creating day-parent entities and moving children:

1. Add a `date` field to the schema (nullable, L2 operation)
2. Backfill existing entities with their date
3. Set a `_group_by: "date"` renderer hint on the section

The renderer groups visually. The entity tree is unchanged.

### When to use grouping vs real parents

| Use `_group_by` | Use parent entities |
|-----------------|-------------------|
| Grouping labels are simple values (dates, statuses) | Group headers need their own props (title, description, notes) |
| Items might move between groups frequently | Containment is permanent and meaningful |
| Under ~100 total entities | Deep hierarchy needed (3+ levels) |
| Retroactive — grouping added after entities exist | Designed from the start |

### Renderer hints (underscore-prefixed props on section entities)

| Prop | Effect |
|------|--------|
| `_group_by` | Group children by this field value |
| `_sort_by` | Sort children by this field |
| `_sort_order` | `asc` (default) or `desc` |
| `_show_fields` | Array of field names to display |
| `_hide_fields` | Array of field names to hide |

These are regular props on the section entity, updated via `entity.update`. The reducer doesn't treat them specially — only the renderer reads them.

---

## Schema Synthesis Protocol

How L4 creates schemas for new aides and new sections.

### Step 1: Classify the pattern

From the user's first message, L4 identifies which of the seven patterns apply. Multiple sections may be needed.

```
"poker league, 8 guys, biweekly Thursday"
→ roster (players) + timeline (games) + ledger (buy-ins)
```

### Step 2: Choose field names using canonical rules

Field names follow strict conventions to eliminate run-to-run variation:

| Rule | Example | Not this |
|------|---------|----------|
| Always `snake_case` | `first_name` | `firstName`, `FirstName` |
| Singular nouns | `name` | `player_name`, `full_name` |
| Bare adjective for booleans | `done`, `active`, `confirmed` | `is_done`, `has_confirmed` |
| `status` for enum state | `status` | `current_status`, `state` |
| `date` for single dates | `date` | `event_date`, `game_date` |
| `start`/`end` for ranges | `start`, `end` | `start_date`, `end_date` |
| `amount` for money | `amount` | `cost`, `price`, `total` |
| `note` for freetext | `note` | `notes`, `description`, `comments` |

### Step 3: Choose entity IDs using canonical rules

| Rule | Example |
|------|---------|
| Section IDs are plural | `players`, `games`, `expenses` |
| Entity IDs are `{singular}_{slug}` | `player_mike`, `game_feb27` |
| Slugs from names use lowercase, underscores | `expense_uber_to_airport` |
| Date slugs use short form | `game_feb27`, `session_mar13` |
| Max 64 characters | Truncate slug if needed |

### Step 4: Emit in render order

Structure first, content second. The page must look coherent at every intermediate state during streaming. L4 emits in this order:

```
1. meta.set (title, identity)
2. Section entities (parents, with display hints)
3. Child entities within each section
4. Relationships (after both endpoints exist)
5. Style tokens
```

### Step 5: Emit via streaming tool use

L4 and L3 emit primitives as Anthropic tool calls, not JSONL. This is the single wire format for all surfaces — streaming chat, MCP servers, Claude.ai Projects.

**Two tools:**

```python
tools = [
    {
        "name": "mutate_entity",
        "description": "Create, update, or remove an entity",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"enum": ["create", "update", "remove", "move", "reorder"]},
                "id": {"type": "string", "description": "Entity ID (for create)"},
                "ref": {"type": "string", "description": "Entity ID (for update/remove)"},
                "parent": {"type": "string", "description": "'root' or parent entity ID"},
                "display": {"type": "string", "enum": ["page", "section", "card", "list", "table", "checklist", "grid", "metric", "text", "image"]},
                "props": {"type": "object"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "set_relationship",
        "description": "Set, remove, or constrain a relationship between entities",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"enum": ["set", "remove", "constrain"]},
                "from": {"type": "string"},
                "to": {"type": "string"},
                "type": {"type": "string"},
                "cardinality": {"enum": ["one_to_one", "many_to_one", "many_to_many"]},
            },
            "required": ["action", "type"]
        }
    }
]
```

**Streaming mechanics:**

The Anthropic streaming API emits `input_json_delta` events as the model generates a tool call, then `content_block_stop` when the call is complete. The pipeline:

1. Buffer `input_json_delta` chunks for each tool call
2. On `content_block_stop`: parse complete JSON, validate against schema
3. Decompose tool call into reducer event (`mutate_entity` with `action: "create"` → `entity.create`)
4. Apply to reducer → get new snapshot
5. Push render delta to client

Each tool call = one primitive = one reducer step = one render update. The user sees entities appear as each tool call completes, same progressive rendering as JSONL but with schema-validated output.

**Voice is just text.**

A single API response interleaves text blocks and tool use blocks:

```json
{
  "content": [
    {"type": "text", "text": "Poker league. 8 players, biweekly Thursday."},
    {"type": "tool_use", "name": "mutate_entity", "input": {...}},
    {"type": "tool_use", "name": "mutate_entity", "input": {...}},
    {"type": "text", "text": "Roster and schedule ready."},
  ]
}
```

The client routes by block type:

| Stream event | Client action |
|-------------|---------------|
| `text_delta` | Push to chat UI as voice response |
| `input_json_delta` | Buffer for tool call |
| `content_block_stop` (tool) | Parse → validate → reduce → render |

No voice tool. No voice signal primitive. The model's natural text output IS the voice. L4/L3 system prompts say "emit brief state reflections between tool calls" and the model interleaves naturally. The reducer never sees voice — it only processes tool calls.

**Why tool use over JSONL:**

- **One wire format everywhere.** Streaming chat, MCP servers, Claude.ai Projects, Claude Code skills all use the same tool definitions. No separate JSONL parsing path.
- **Schema-constrained output.** The model fills in a validated schema rather than generating freeform JSON. Fewer malformed events, more structural consistency.
- **MCP native.** The tools are already MCP-shaped. External agents call `mutate_entity` and `set_relationship` the same way L4/L3 do internally.

**Decomposition layer:**

Between tool call output and reducer input, a thin translation expands tool calls to reducer events:

```python
def decompose(tool_name: str, params: dict) -> dict:
    if tool_name == "mutate_entity":
        action = params["action"]
        event_type = f"entity.{action}"
        return {
            "t": event_type,
            "id": params.get("id"),
            "ref": params.get("ref"),
            "parent": params.get("parent"),
            "display": params.get("display"),
            "p": params.get("props", {}),
        }
    elif tool_name == "set_relationship":
        action = params["action"]
        event_type = f"rel.{action}"
        return {
            "t": event_type,
            **{k: v for k, v in params.items() if k != "action"},
        }
```

**Latency:** Each tool call buffers until complete (~400–600ms per primitive vs ~200ms for JSONL token streaming). The difference is imperceptible during page build. For bulk operations like grid pre-population, the model can emit tool calls rapidly in sequence.

---

## Limits

| Dimension | Soft limit | Hard limit | What happens |
|-----------|-----------|------------|--------------|
| Entities per aide | 200 | 500 | Warn → suggest export |
| Fields per entity type | 15 | 20 | Warn → suggest splitting |
| Children per parent | 10 | 150 | Warn at 50 (except grids, which pre-populate) |
| Sections per aide | 4 | 8 | Warn → suggest new aide |
| List prop length | 20 | 50 | Warn → suggest child entities |
| Nesting depth | 2 | 3 | Reject deeper nesting |
| Grid dimensions | 10×10 | 20×20 | Warn → grids beyond 400 cells degrade performance |

When an aide approaches hard limits, the response includes a state reflection:

> "142 items across 5 sections. Tools like Asana or Notion handle this scale better. Export as CSV?"

---

## Routing Model

No rules-based classifier. Two tiers, simple decision.

### L4 (Opus) — The Architect

Handles the first message and escalations. This is where structural decisions happen.

**When:**
- First message of any aide (always)
- L3 escalation: schema evolution, new section needed, ambiguous scope change
- Queries that require holistic understanding of the aide

**Temperature:** 0.2 — initial structure choice benefits from slight exploration, constrained by golden examples and pattern classification.

**Cost:** Higher per call, but first messages are rare relative to total turns. Escalations should be <10% of subsequent messages.

### L3 (Sonnet) — The Compiler

Handles every message after the first. Entity resolution, field updates, adding children, multi-intent messages. Sonnet is capable enough to handle the edge cases that Haiku would have escalated on.

**When:**
- Every message after the first (always)
- Escalates to L4 when it encounters: new entity types it can't fit into existing sections, structural ambiguity, requests that feel like "second first messages" ("actually let's also track expenses")

**Temperature:** 0 — pure compilation against established schema. No creativity needed.

**Escalation signal:**
```json
{"t": "escalate", "tier": "L4", "reason": "schema_evolution", "extract": "the part that needs architectural decisions"}
```

### L2 (Haiku) — Shelved

Not removed from the codebase, but not in the routing path. Haiku can be reintroduced later with empirical data on which messages are truly trivial. The cost delta between Haiku and Sonnet on a short `entity.update` is negligible compared to the debugging cost of misrouted messages.

**Reintroduction criteria:** When flight recorder data shows >70% of L3 calls are single-entity updates with zero escalations, L2 can handle that subset.

### Routing logic

```python
def route(aide: Aide, message: str) -> str:
    if not aide.has_entities():
        return "L4"
    return "L3"
```

That's the entire classifier.

---

## Consistency Verification

### Shadow comparison

For first messages (where structural variation is highest), run L4 twice and diff the schemas. Log divergence. Over time, golden examples and naming conventions should drive divergence toward zero.

### Post-LLM normalization

Before events hit the reducer, a thin normalization layer canonicalizes:

- Field names → `snake_case`, strip prefixes
- Entity IDs → lowercase, underscore-separated
- Collection/section IDs → plural form
- Boolean field names → strip `is_`/`has_` prefix

This catches the long tail of naming variation that survives prompting.

### Determinism tests

Same user message + same snapshot → same events. Tested via golden file replay:

```python
events_a = synthesize("poker league, 8 guys")
events_b = synthesize("poker league, 8 guys")
assert structural_shape(events_a) == structural_shape(events_b)
# Field names and entity IDs may differ slightly
# Structural shape (patterns, parent/child, display hints) must not
```
