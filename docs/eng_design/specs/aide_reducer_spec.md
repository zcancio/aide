# AIde — Reducer Spec (v3)

**Purpose:** The reducer is a pure function: `(snapshot, event) → snapshot`. It takes the current state and one event, returns the new state. Replay all events from an empty state and you get the current snapshot. This is the heart of the kernel — everything above it (the AI, the ears) produces events, and everything below it (the renderer, the HTML file) consumes the snapshot.

**Companion docs:** `aide_primitive_schemas_spec.md` (what goes in), `unified_entity_model.md` (v3 data model), `aide_architecture.md` (how it fits)

---

## Contract

```python
def reduce(snapshot: AideState, event: Event) -> ReduceResult:
    """
    Apply one event to the current snapshot.
    Returns new snapshot + any warnings/errors.
    Pure function. No side effects. No IO. No AI calls.
    """
```

```python
def replay(events: list[Event]) -> AideState:
    """
    Rebuild snapshot from scratch by reducing over all events.
    replay(events) == reduce(reduce(reduce(empty(), e1), e2), e3)...
    """
    snapshot = empty_state()
    for event in events:
        result = reduce(snapshot, event)
        snapshot = result.snapshot
    return snapshot
```

### ReduceResult

```python
@dataclass
class ReduceResult:
    snapshot: AideState        # The new state
    applied: bool              # Whether the event was applied
    warnings: list[Warning]    # Constraint violations, type coercions, etc.
    error: str | None          # If applied is False, why
```

Events either apply cleanly, apply with warnings, or reject with an error. The reducer never throws exceptions — it returns structured results.

### Determinism Guarantee

The reducer is deterministic. Given the same sequence of events, it produces the same snapshot every time. No randomness, no timestamps, no external state. This means:

- Any client can replay the event log and arrive at the same state
- Tests are trivial: fixed input → fixed output
- Debugging is replay: reproduce any bug by replaying events up to that point

---

## Empty State

When an aide has no events, the snapshot is:

```json
{
  "version": 3,
  "meta": {},
  "schemas": {},
  "entities": {},
  "blocks": {
    "block_root": { "type": "root", "children": [] }
  },
  "styles": {},
  "constraints": [],
  "annotations": []
}
```

The only thing that exists in empty state is `block_root`. Everything else is created by events.

---

## TypeScript Parsing

The reducer uses tree-sitter to parse TypeScript interfaces and validate entity fields.

```python
from tree_sitter import Parser
import tree_sitter_typescript as ts

parser = Parser(ts.language_typescript())

def parse_interface(code: str) -> dict[str, TypeInfo]:
    """
    Parse TypeScript interface, return field name -> type info mapping.

    Returns: { "name": TypeInfo(type="string", optional=False), ... }
    """
    tree = parser.parse(code.encode())
    fields = {}

    for node in tree.root_node.children:
        if node.type == "interface_declaration":
            for child in node.children:
                if child.type == "object_type":
                    for prop in child.children:
                        if prop.type == "property_signature":
                            name = prop.child_by_field_name("name").text.decode()
                            type_node = prop.child_by_field_name("type")
                            optional = any(c.type == "?" for c in prop.children)
                            fields[name] = TypeInfo(
                                type=type_node.text.decode(),
                                optional=optional
                            )
    return fields

@dataclass
class TypeInfo:
    type: str        # "string", "number", "boolean", "Record<string, T>", etc.
    optional: bool   # Was there a ? after the field name
```

Parsed interfaces are cached per schema to avoid re-parsing on every validation.

---

## Reduction Rules by Primitive

### Schema Primitives

#### `schema.create`

```
Input:  snapshot + { id: "GroceryItem", interface: "interface GroceryItem { name: string; checked: boolean; }", render_html: "...", render_text: "...", styles: "..." }

Steps:
1. Parse TypeScript interface using tree-sitter
   → REJECT if parsing fails (syntax error)
2. Check id doesn't already exist in snapshot.schemas
   → REJECT if schema exists
3. Store schema in snapshot.schemas[id]:
   {
     id: "GroceryItem",
     interface: "interface GroceryItem { name: string; checked: boolean; }",
     parsed: { "name": TypeInfo("string", false), "checked": TypeInfo("boolean", false) },
     render_html: "...",
     render_text: "...",
     styles: "..."
   }

Output: snapshot with new schema
```

#### `schema.update`

```
Input:  snapshot + { id: "GroceryItem", interface: "interface GroceryItem { name: string; checked: boolean; store?: string; }" }

Steps:
1. Lookup schema
   → REJECT if doesn't exist
2. If interface provided:
   a. Parse new TypeScript interface
      → REJECT if parsing fails
   b. For each existing entity with _schema == this id:
      → Check fields against new interface
      → WARN if entity has fields not in new interface (ignored, but noted)
      → REJECT if existing field has incompatible type
3. Update schema properties (interface, render_html, render_text, styles)
   → Only update fields that are provided in payload
4. Re-cache parsed interface

Output: snapshot with updated schema
```

#### `schema.remove`

```
Input:  snapshot + { id: "GroceryItem" }

Steps:
1. Lookup schema
   → REJECT if doesn't exist
2. Check no entities reference this schema
   → REJECT if any entity has _schema == "GroceryItem"
3. Remove from snapshot.schemas

Output: snapshot with schema removed
```

---

### Entity Primitives

#### `entity.create`

```
Input:  snapshot + { id: "grocery_list", _schema: "GroceryList", title: "Weekly Groceries", items: { item_milk: { name: "Milk", checked: false, _pos: 1.0 } } }

Steps:
1. Lookup schema "GroceryList" in snapshot.schemas
   → REJECT if schema doesn't exist
2. Check id doesn't already exist in snapshot.entities
   → REJECT if entity exists (not removed)
   → If entity exists but IS removed: treat as re-creation (overwrite)
3. Parse entity path if nested:
   → "grocery_list" = top-level entity
   → "grocery_list/items/item_milk" = child entity
4. Validate fields against parsed schema interface:
   a. For each required field (not optional): check it's present
      → REJECT if required field missing
   b. For each provided field: check type matches
      → REJECT if type mismatch
   c. For Record<string, T> fields: recursively validate children
      → Each child must conform to type T's schema
5. Store entity in snapshot.entities[id]:
   {
     _schema: "GroceryList",
     _removed: false,
     _created_seq: event.sequence,
     title: "Weekly Groceries",
     items: {
       item_milk: { name: "Milk", checked: false, _pos: 1.0, _removed: false }
     }
   }

Output: snapshot with new entity
```

#### `entity.update`

```
Input:  snapshot + { id: "grocery_list", title: "This Week's Groceries", items: { item_milk: { checked: true }, item_bread: { name: "Bread", _pos: 1.5 }, item_eggs: null } }

Steps:
1. Resolve entity path:
   → "grocery_list" = snapshot.entities["grocery_list"]
   → "grocery_list/items/item_milk" = snapshot.entities["grocery_list"].items["item_milk"]
2. Lookup entity
   → REJECT if doesn't exist
   → REJECT if removed
3. Get schema from entity._schema
4. Validate updated fields against schema interface
   → REJECT if type mismatch
5. For Record<string, T> fields (like "items"):
   a. For each key in payload:
      → If value is null: set child._removed = true
      → If child exists: merge fields
      → If child doesn't exist: create with provided fields
   b. Children not mentioned are unchanged
6. Merge top-level fields into entity
7. Set entity._updated_seq = event.sequence

Output: snapshot with updated entity
```

#### `entity.remove`

```
Input:  snapshot + { id: "grocery_list/items/item_milk" }

Steps:
1. Resolve entity path
2. Lookup entity
   → REJECT if doesn't exist
   → WARN if already removed (idempotent)
3. Set entity._removed = true
4. Recursively set _removed = true on all nested children
5. Set entity._removed_seq = event.sequence

Output: snapshot with entity marked as removed
```

**Soft-delete semantics:** Removed entities stay in the snapshot data structure (for undo via event replay). They are excluded from:
- Rendering
- Child counts
- Constraint validation

---

### Block Primitives

#### `block.set`

```
Input:  snapshot + { id: "block_list", type: "entity_view", parent: "block_root", position: 1.5, props: { source: "grocery_list" } }

Steps:
1. If block id already exists in snapshot.blocks:
   → UPDATE mode: merge props, optionally reparent/reposition
2. If block id doesn't exist:
   → CREATE mode: type required
   → REJECT if type is missing
3. Resolve parent
   → REJECT if parent doesn't exist
   → Default parent: "block_root"
4. Handle positioning with _pos (fractional indexing):
   → If position provided: set block._pos = position
   → If no position on create: append (max _pos + 1)
5. If reparenting (block exists but parent changed):
   → Update block.parent to new parent
6. Store/update block in snapshot.blocks[id]:
   { id, type, parent, _pos, props, children: [] (if new) }

Output: snapshot with created/updated block
```

#### `block.remove`

```
Input:  snapshot + { id: "block_list" }

Steps:
1. Lookup block
   → REJECT if doesn't exist
   → REJECT if id is "block_root"
2. Collect block and ALL descendants (recursive)
3. Remove all collected blocks from snapshot.blocks

Output: snapshot with block and children removed
```

#### `block.reorder`

```
Input:  snapshot + { parent: "block_root", children: ["block_title", "block_list", "block_footer"] }

Steps:
1. Lookup parent
   → REJECT if doesn't exist
2. Assign _pos values based on order:
   → children[0]._pos = 1.0
   → children[1]._pos = 2.0
   → children[2]._pos = 3.0
3. Blocks in parent not listed: append at end with higher _pos values

Output: snapshot with reordered children
```

---

### Style Primitives

#### `style.set`

```
Input:  snapshot + { primary_color: "#2d3748", density: "compact" }

Steps:
1. Shallow-merge all keys in payload into snapshot.styles
   → Known tokens update existing values
   → Unknown tokens are stored (forward-compatibility)
   → Explicit null removes a token

Output: snapshot with updated style tokens
```

#### `style.set_entity`

```
Input:  snapshot + { id: "grocery_list/items/item_milk", styles: { highlight: true, bg_color: "#fef3c7" } }

Steps:
1. Resolve entity path
   → REJECT if entity doesn't exist or is removed
2. Merge styles into entity._styles (a reserved key)
   → If entity has no _styles, create it

Output: snapshot with entity-level style overrides
```

---

### Meta Primitives

#### `meta.update`

```
Input:  snapshot + { title: "Poker League — Spring 2026" }

Steps:
1. Shallow-merge all keys in payload into snapshot.meta
   → Known properties (title, identity, visibility, archived) update
   → Unknown properties are stored

Output: snapshot with updated meta
```

#### `meta.annotate`

```
Input:  snapshot + { note: "Host rotation advanced.", pinned: false }

Steps:
1. Append to snapshot.annotations:
   { note, pinned: false, seq: event.sequence, timestamp: event.timestamp }

Output: snapshot with new annotation
```

#### `meta.constrain`

```
Input:  snapshot + { id: "constraint_max_players", rule: "max_children", path: "poker_league/players", value: 10, message: "Maximum 10 players" }

Steps:
1. Store in snapshot.constraints
   → If constraint with same id exists: update it
   → Otherwise: append
2. Immediately validate against current state:
   → If rule is "max_children" and path already exceeds value: WARN
   → If rule is "unique_field" and duplicates exist: WARN

Output: snapshot with new constraint (and immediate validation warnings if applicable)
```

---

### Grid Primitives

#### `grid.create`

```
Input:  snapshot + { id: "squares", _schema: "SquareGrid", title: "Super Bowl Squares", cells: { _shape: [10, 10] } }

Steps:
1. Validate schema exists
2. Expand _shape into children:
   → [10, 10] generates 100 children: cell_0_0, cell_0_1, ..., cell_9_9
   → Each child gets _pos based on row-major order
3. Store as regular entity with expanded children

Output: snapshot with entity containing generated grid cells
```

#### `grid.query`

```
Input:  snapshot + { id: "squares/cells", cell_ref: "FU", field: "owner" }

Steps:
1. Resolve cell_ref using row_labels and col_labels from meta
   → "FU" with row_labels=["A"-"J"], col_labels=["P"-"Z"] → row 5, col 5 → "cell_5_5"
2. Lookup entity at resolved path
3. Return field value

Output: query result (not a snapshot mutation)
```

---

## Type Validation

### Type Checking Rules

| TypeScript Type | Valid JSON Values |
|-----------------|-------------------|
| `string` | any string, NOT null |
| `string?` | any string OR absent |
| `string \| null` | any string OR null |
| `number` | integer or float, NOT null |
| `boolean` | true or false, NOT null |
| `Date` | ISO 8601 date string |
| `"a" \| "b" \| "c"` | one of the literal values |
| `string[]` | array of strings |
| `Record<string, T>` | object where each value is T |

### Type Coercion

The reducer does NOT coerce types. A number field must receive a number, not a string "5". Type mismatches are rejected.

---

## Constraint Checking

Constraints are checked reactively — on every event that could violate them.

**When to check which constraints:**

| Event type | Check |
|------------|-------|
| `entity.create` | `max_children`, `unique_field`, `required_fields` |
| `entity.update` | `unique_field`, `required_fields` |
| `schema.remove` | Nothing (can only remove unused schemas) |

**Constraint rules:**

| Rule | Check |
|------|-------|
| `max_children` | Path can't have more than N children |
| `min_children` | Path must have at least N children |
| `unique_field` | No duplicate values for field in children |
| `required_fields` | Listed fields must be non-null |

**Warning vs. rejection:** By default, constraint violations produce warnings, not rejections. The event still applies. If a constraint has `strict: true`, violations reject the event.

---

## Error Handling

The reducer never panics. Every code path returns a ReduceResult.

**Rejection reasons (event not applied):**

| Code | Meaning |
|------|---------|
| `SCHEMA_NOT_FOUND` | Referenced schema doesn't exist |
| `SCHEMA_ALREADY_EXISTS` | schema.create with duplicate ID |
| `SCHEMA_IN_USE` | schema.remove but entities reference it |
| `SCHEMA_PARSE_ERROR` | TypeScript interface failed to parse |
| `ENTITY_NOT_FOUND` | Referenced entity doesn't exist |
| `ENTITY_ALREADY_EXISTS` | entity.create with duplicate ID |
| `REQUIRED_FIELD_MISSING` | entity.create missing required fields |
| `TYPE_MISMATCH` | Field value doesn't match schema type |
| `BLOCK_NOT_FOUND` | block operation on nonexistent block |
| `BLOCK_TYPE_MISSING` | block.set (create mode) without type |
| `CANT_REMOVE_ROOT` | block.remove on block_root |
| `STRICT_CONSTRAINT_VIOLATED` | Strict constraint violated |
| `UNKNOWN_PRIMITIVE` | Unrecognized event type |

**Warning reasons (event applied, but something to note):**

| Code | Meaning |
|------|---------|
| `CONSTRAINT_VIOLATED` | Non-strict constraint violated |
| `ALREADY_REMOVED` | Removing something already removed |
| `UNKNOWN_FIELD_IGNORED` | Entity data included a field not in schema |
| `SCHEMA_FIELD_ADDED` | Schema update added new field, existing entities missing it |

---

## Performance Characteristics

**Per-event cost:** O(1) for most primitives. Entity create/update touch one entity tree. Block operations touch one path.

**Expensive operations:**
- `schema.update` with interface change: O(n) where n = entities with this schema
- `entity.remove` on parent: O(children) to mark all as removed
- Constraint checking: O(siblings) for unique_field

**Replay cost:** O(events × per-event). For a 500-event aide, replay takes milliseconds.

---

## Testing Strategy

**Test categories:**

1. **Happy path per primitive.** schema.create, entity.create, entity.update, etc.

2. **TypeScript parsing.** Various interfaces: optional fields, union types, Record types, arrays.

3. **Nested entity operations.** Create parent with children, update child via path, remove child.

4. **Schema evolution.** Update interface, verify existing entities still validate (or warn appropriately).

5. **Constraint checking.** Create max_children constraint, exceed it, verify warning.

6. **Determinism.** Replay the same events 100 times. Identical snapshot every time.

7. **Round-trip.** Generate snapshot, serialize to JSON, deserialize, verify equality.

8. **Walkthrough.** Full grocery list scenario from first message to 20 operations.
