# AIde — Reducer Spec

**Purpose:** The reducer is a pure function: `(snapshot, event) → snapshot`. It takes the current state and one event, returns the new state. Replay all events from an empty state and you get the current snapshot. This is the heart of the kernel — everything above it (the AI, the ears) produces events, and everything below it (the renderer, the HTML file) consumes the snapshot.

**Companion docs:** `aide_primitive_schemas.md` (what goes in), `aide_architecture.md` (how it fits)

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
  "version": 1,
  "meta": {},
  "collections": {},
  "relationships": [],
  "relationship_types": {},
  "constraints": [],
  "blocks": {
    "block_root": { "type": "root", "children": [] }
  },
  "views": {},
  "styles": {},
  "annotations": []
}
```

The only thing that exists in empty state is `block_root`. Everything else is created by events.

---

## Reduction Rules by Primitive

### Entity Primitives

#### `entity.create`

```
Input:  snapshot + { collection: "grocery_list", id: "item_milk", fields: { name: "Milk", checked: false } }

Steps:
1. Lookup collection "grocery_list" in snapshot.collections
   → REJECT if collection doesn't exist
   → REJECT if collection is removed
2. Check id "item_milk" doesn't already exist in collection.entities
   → REJECT if entity exists and is not removed
   → If entity exists but IS removed: treat as re-creation (overwrite)
3. Validate fields against collection.schema
   → REJECT if required (non-nullable) schema fields are missing from fields
   → REJECT if field value types don't match schema types
   → WARN if fields contains keys not in schema (ignore them, don't store)
4. If id is null/missing: auto-generate as "{collection}_{sequential_int}" 
5. Store entity in snapshot.collections[collection].entities[id]
   → Entity includes all provided fields
   → Nullable schema fields not in the payload default to null
   → Add _removed: false, _created_seq: event.sequence

Output: snapshot with new entity in collection
```

#### `entity.update`

```
Input:  snapshot + { ref: "grocery_list/item_milk", fields: { checked: true } }

Steps:
1. Parse ref → collection_id: "grocery_list", entity_id: "item_milk"
2. Lookup entity
   → REJECT if collection doesn't exist
   → REJECT if entity doesn't exist
   → REJECT if entity is removed
3. Validate field values against schema types
   → REJECT if type mismatch
4. Merge: for each key in payload.fields, set entity[key] = payload.fields[key]
   → Unmentioned fields are unchanged
   → Setting a nullable field to null is allowed
5. Update entity._updated_seq = event.sequence

Output: snapshot with updated entity
```

**Filter variant:**

```
Input:  snapshot + { filter: { collection: "grocery_list", where: { checked: true } }, fields: { archived: true } }

Steps:
1. Lookup collection
   → REJECT if collection doesn't exist
2. Find all non-removed entities where all conditions in "where" match
   → Field equality: entity[field] == where[field]
3. Apply field updates to each matching entity (same validation as ref variant)
4. Return count of updated entities in warnings (informational)

Output: snapshot with all matching entities updated
```

#### `entity.remove`

```
Input:  snapshot + { ref: "grocery_list/item_milk" }

Steps:
1. Parse ref → collection_id, entity_id
2. Lookup entity
   → REJECT if collection doesn't exist
   → REJECT if entity doesn't exist
   → WARN if entity is already removed (idempotent — no error, no change)
3. Set entity._removed = true, entity._removed_seq = event.sequence
4. Mark any relationships involving this entity as excluded

Output: snapshot with entity marked as removed
```

**Soft-delete semantics:** Removed entities stay in the snapshot data structure (for undo via event replay). They are excluded from:
- Collection entity counts
- View rendering
- Relationship resolution
- Filter matches

---

### Collection Primitives

#### `collection.create`

```
Input:  snapshot + { id: "grocery_list", name: "Grocery List", schema: { name: "string", checked: "bool", store: "string?" }, settings: {} }

Steps:
1. Check id doesn't exist in snapshot.collections
   → REJECT if collection exists and is not removed
   → If exists but IS removed: treat as re-creation
2. Validate schema: every value must be a recognized field type
   → REJECT if any type is unrecognized
3. Store collection in snapshot.collections[id]:
   {
     id: "grocery_list",
     name: "Grocery List",
     schema: { ... },
     settings: { ... },
     entities: {},
     _removed: false,
     _created_seq: event.sequence
   }

Output: snapshot with new empty collection
```

#### `collection.update`

```
Input:  snapshot + { id: "grocery_list", name: "Weekly Groceries", settings: { default_store: "Whole Foods" } }

Steps:
1. Lookup collection
   → REJECT if doesn't exist or is removed
2. If name provided: update collection.name
3. If settings provided: shallow-merge into collection.settings
   → Existing keys not mentioned in payload are preserved
   → New keys are added
   → Explicit null removes a key

Output: snapshot with updated collection properties
```

#### `collection.remove`

```
Input:  snapshot + { id: "grocery_list" }

Steps:
1. Lookup collection
   → REJECT if doesn't exist
   → WARN if already removed (idempotent)
2. Set collection._removed = true
3. Set _removed = true on ALL entities in the collection
4. Mark all relationships involving entities in this collection as excluded
5. Mark all views with source == this collection as removed
6. Mark all blocks with type "collection_view" referencing this collection as removed

Output: snapshot with collection and all dependents removed
```

---

### Field Primitives

#### `field.add`

```
Input:  snapshot + { collection: "grocery_list", name: "category", type: "string?", default: null }

Steps:
1. Lookup collection
   → REJECT if doesn't exist or is removed
2. Check field name doesn't already exist in schema
   → REJECT if field exists
3. Validate type is recognized
4. If type is required (no ?) and no default provided:
   → REJECT — can't add a required field without a default (existing entities would be invalid)
5. Add field to collection.schema
6. Backfill: for every existing non-removed entity in the collection:
   → Set entity[name] = default (or null if nullable)

Output: snapshot with expanded schema and backfilled entities
```

#### `field.update`

```
Input:  snapshot + { collection: "grocery_list", name: "category", type: {"enum": ["produce","dairy","meat","pantry","other"]} }

Steps:
1. Lookup collection and field
   → REJECT if collection or field doesn't exist
2. If type change requested:
   → Check compatibility (see type compatibility matrix below)
   → If incompatible: REJECT
   → If compatible but lossy: WARN
3. If rename requested:
   → Check new name doesn't conflict with existing field
   → Rename field in schema
   → Rename field key in ALL entities in the collection
4. Update schema definition

Output: snapshot with updated schema (and optionally renamed field across entities)
```

**Type compatibility matrix:**

| From → To | string | int | float | bool | enum | date | list |
|-----------|--------|-----|-------|------|------|------|------|
| string | ✓ | check* | check* | check* | check** | check* | ✗ |
| int | ✓ | ✓ | ✓ | ✓ (0/1) | check** | ✗ | ✗ |
| float | ✓ | lossy | ✓ | ✗ | check** | ✗ | ✗ |
| bool | ✓ | ✓ (0/1) | ✗ | ✓ | check** | ✗ | ✗ |
| enum | ✓ | ✗ | ✗ | ✗ | check** | ✗ | ✗ |
| date | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ |
| list | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |

`check*` = scan all existing values, reject if any can't convert
`check**` = scan all existing values, reject if any not in the enum
`lossy` = float → int truncates decimals, warn

#### `field.remove`

```
Input:  snapshot + { collection: "grocery_list", name: "category" }

Steps:
1. Lookup collection and field
   → REJECT if either doesn't exist
2. Remove field from collection.schema
3. Remove field key from ALL entities in the collection
4. If any views reference this field in show_fields, hide_fields, sort_by, group_by, filter:
   → Remove the field reference from the view config
   → WARN

Output: snapshot with field removed from schema and all entities
```

---

### Relationship Primitives

#### `relationship.set`

```
Input:  snapshot + { from: "roster/player_dave", to: "schedule/game_feb27", type: "hosting", cardinality: "many_to_one" }

Steps:
1. Resolve both entity refs
   → REJECT if either entity doesn't exist or is removed
2. Lookup relationship type in snapshot.relationship_types
   → If type doesn't exist: register it with the provided cardinality (default "many_to_one")
   → If type exists: use stored cardinality (ignore payload cardinality — it's set once)
3. Enforce cardinality:
   a. many_to_one: source entity can have only ONE relationship of this type
      → Remove any existing relationship where from == this entity AND type == this type
   b. one_to_one: both sides exclusive
      → Remove existing where from == this entity AND type == this type
      → Remove existing where to == target entity AND type == this type
   c. many_to_many: no auto-removal
4. Check constraints (see constraint checking below)
   → If violated: WARN (but still apply unless constraint is strict)
5. Append relationship to snapshot.relationships:
   { from, to, type, data, _seq: event.sequence }

Output: snapshot with new relationship (old conflicting relationships removed per cardinality)
```

**Cardinality examples:**

`many_to_one` — "seated_at": each guest at ONE table. Setting Linda at table_5 auto-removes her from table_3.

`one_to_one` — "paired_with": each entity at ONE partner. Setting A→B auto-removes A's old partner AND B's old partner.

`many_to_many` — "tagged_with": a guest can have many tags, a tag can apply to many guests. No auto-removal.

#### `relationship.constrain`

```
Input:  snapshot + { id: "constraint_no_linda_steve", rule: "exclude_pair", entities: ["guests/guest_linda", "guests/guest_steve"], relationship_type: "seated_at", message: "Keep Linda and Steve at different tables" }

Steps:
1. Validate referenced entities exist (if provided)
   → WARN if entities don't exist (constraint is still stored — entities might be created later)
2. Store constraint in snapshot.constraints:
   { id, rule, entities, relationship_type, value, message, strict: false }

Output: snapshot with new constraint
```

---

### Block Primitives

#### `block.set`

```
Input:  snapshot + { id: "block_next_game", type: "metric", parent: "block_root", position: 1, props: { label: "Next game", value: "Thu Feb 27 at Dave's" } }

Steps:
1. If block id already exists in snapshot.blocks:
   → UPDATE mode: merge props into existing block, optionally reparent/reposition
2. If block id doesn't exist:
   → CREATE mode: full type and props required
   → REJECT if type is missing
3. Resolve parent
   → REJECT if parent doesn't exist
   → Default parent: "block_root"
4. Handle positioning:
   a. If position provided: insert at that index in parent.children
      → Shift existing children at >= position
   b. If no position: append to end of parent.children
5. If reparenting (block exists but parent changed):
   → Remove block id from old parent.children
   → Insert into new parent.children at position
6. Store/update block in snapshot.blocks[id]:
   { id, type, parent, props, children: [] (if new) }

Output: snapshot with created/updated block in the tree
```

#### `block.remove`

```
Input:  snapshot + { id: "block_next_game" }

Steps:
1. Lookup block
   → REJECT if doesn't exist
   → REJECT if id is "block_root" (can't remove root)
2. Collect block and ALL descendants (recursive)
3. Remove block id from parent.children
4. Delete all collected blocks from snapshot.blocks

Output: snapshot with block and children removed from tree
```

#### `block.reorder`

```
Input:  snapshot + { parent: "block_root", children: ["block_title", "block_roster", "block_next_game", "block_schedule"] }

Steps:
1. Lookup parent
   → REJECT if doesn't exist
2. Validate all ids in children are currently children of this parent
   → WARN if any ids are not current children (ignore unknown ids)
3. Set parent.children to the provided order
4. Any current children NOT in the provided list: append at the end (preserve, don't drop)

Output: snapshot with reordered children
```

---

### View Primitives

#### `view.create`

```
Input:  snapshot + { id: "roster_view", type: "list", source: "roster", config: { show_fields: ["name", "status"], sort_by: "name", sort_order: "asc" } }

Steps:
1. Check id doesn't already exist in snapshot.views
   → REJECT if exists
2. Validate source collection exists
   → REJECT if doesn't exist or is removed
3. Validate config fields reference real schema fields (if show_fields, sort_by, etc. provided)
   → WARN if a referenced field doesn't exist in the collection schema (store anyway — schema might evolve)
4. Store view in snapshot.views[id]:
   { id, type, source, config }

Output: snapshot with new view
```

#### `view.update`

```
Input:  snapshot + { id: "roster_view", config: { show_fields: ["name", "status", "snack_duty"] } }

Steps:
1. Lookup view
   → REJECT if doesn't exist
2. If type change: update type
3. If config: shallow-merge into existing config
4. Validate updated config references (same as create)

Output: snapshot with updated view
```

#### `view.remove`

```
Input:  snapshot + { id: "roster_view" }

Steps:
1. Lookup view
   → REJECT if doesn't exist
2. Remove from snapshot.views
3. Any blocks referencing this view (collection_view blocks with view == this id):
   → Set their view reference to null
   → WARN (block will fall back to default rendering)

Output: snapshot with view removed
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
Input:  snapshot + { ref: "roster/player_mike", styles: { highlight: true, bg_color: "#fef3c7" } }

Steps:
1. Resolve entity ref
   → REJECT if entity doesn't exist or is removed
2. Merge styles into entity._styles (a reserved key on the entity)
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
Input:  snapshot + { id: "constraint_max_players", rule: "collection_max_entities", collection: "roster", value: 10, message: "Maximum 10 players" }

Steps:
1. Store in snapshot.constraints (same list as relationship constraints)
   → If constraint with same id exists: update it
   → Otherwise: append
2. Immediately validate against current state:
   → If rule is "collection_max_entities" and collection already exceeds value: WARN
   → If rule is "unique_field" and duplicates exist: WARN

Output: snapshot with new constraint (and immediate validation warnings if applicable)
```

---

## Constraint Checking

Constraints are checked reactively — on every event that could violate them. The reducer doesn't re-check all constraints on every event, only relevant ones.

**When to check which constraints:**

| Event type | Check |
|------------|-------|
| `entity.create` | `collection_max_entities`, `unique_field`, `required_fields` |
| `entity.update` | `unique_field`, `required_fields`, relationship constraints (if relationship-relevant fields changed) |
| `relationship.set` | `exclude_pair`, `require_same`, `max_per_target`, `min_per_target` |
| `collection.remove` | Nothing (removing can't violate) |
| `field.remove` | `required_fields` (warn if a required-fields constraint references this field) |

**Constraint rules:**

| Rule | Check | Example |
|------|-------|---------|
| `exclude_pair` | Two entities must NOT share the same target via this relationship type | Linda and Steve can't be at the same table |
| `require_same` | Two entities MUST share the same target | VIP couples must be at the same table |
| `max_per_target` | No target can have more than N sources of this type | Max 8 guests per table |
| `min_per_target` | Every target must have at least N sources | Every table must have at least 2 guests |
| `collection_max_entities` | Collection can't exceed N entities | Max 10 players in roster |
| `unique_field` | No two entities in a collection can share the same value for this field | No duplicate email addresses |
| `required_fields` | These fields must be non-null on every entity | Every guest must have a name |

**Warning vs. rejection:**

By default, constraint violations produce warnings, not rejections. The event still applies. This is deliberate — an organizer saying "seat Linda at table 5 with Steve" should see a warning, not a refusal. They might have a good reason.

If a constraint has `strict: true`, violations reject the event.

---

## Error Handling

The reducer never panics. Every code path returns a ReduceResult.

**Rejection reasons (event not applied):**

| Code | Meaning |
|------|---------|
| `COLLECTION_NOT_FOUND` | Referenced collection doesn't exist |
| `ENTITY_NOT_FOUND` | Referenced entity doesn't exist |
| `ENTITY_ALREADY_EXISTS` | entity.create with duplicate ID |
| `COLLECTION_ALREADY_EXISTS` | collection.create with duplicate ID |
| `FIELD_ALREADY_EXISTS` | field.add with duplicate name |
| `FIELD_NOT_FOUND` | field.update/remove on nonexistent field |
| `VIEW_NOT_FOUND` | view.update/remove on nonexistent view |
| `BLOCK_NOT_FOUND` | block.set (update mode) / block.remove on nonexistent block |
| `BLOCK_TYPE_MISSING` | block.set (create mode) without type |
| `CANT_REMOVE_ROOT` | block.remove on block_root |
| `REQUIRED_FIELD_MISSING` | entity.create missing required fields |
| `TYPE_MISMATCH` | Field value doesn't match schema type |
| `INCOMPATIBLE_TYPE_CHANGE` | field.update with incompatible type conversion |
| `REQUIRED_FIELD_NO_DEFAULT` | field.add with required type but no default |
| `STRICT_CONSTRAINT_VIOLATED` | Strict constraint violated |
| `UNKNOWN_PRIMITIVE` | Unrecognized event type |

**Warning reasons (event applied, but something to note):**

| Code | Meaning |
|------|---------|
| `CONSTRAINT_VIOLATED` | Non-strict constraint violated |
| `ALREADY_REMOVED` | Removing something already removed (idempotent) |
| `UNKNOWN_FIELD_IGNORED` | Entity data included a field not in schema |
| `VIEW_FIELD_MISSING` | View config references field not in schema |
| `BLOCK_VIEW_MISSING` | Block references a view that was removed |
| `LOSSY_TYPE_CONVERSION` | float → int lost decimal precision |
| `ENTITIES_AFFECTED` | Informational: N entities affected by bulk update |

---

## Performance Characteristics

The reducer is designed to be fast. Not "optimize later" fast — structurally fast.

**Per-event cost:** O(1) for most primitives. Entity create/update/remove touch one entity. Block operations touch one path in the tree. The only potentially expensive operations are:

- `entity.update` with `filter`: O(n) where n = entities in collection
- `field.add` with backfill: O(n) entities
- `field.remove`: O(n) entities
- `field.update` with type compatibility check: O(n) entities
- `collection.remove`: O(n) entities + O(m) relationships
- Constraint checking: O(constraints) per relevant event

**Replay cost:** O(events × per-event). For a 500-event aide, replay takes milliseconds. For a 10,000-event aide (extreme), it might take 50–100ms. If replay becomes slow, compact the event log: snapshot the current state, discard events, start appending from the new baseline.

**Memory:** The snapshot is the full state in memory. A large aide (200 guests, 500 events) is ~100KB of JSON. This fits comfortably in any runtime.

---

## Incremental vs. Full Replay

In production, the reducer runs **incrementally** — it applies one event at a time to the current snapshot. Full replay is only needed for:

- Rebuilding state from the HTML file (extract events, replay)
- Undo (replay all events except the last N)
- Time travel (replay events up to sequence N)
- Integrity check (replay all, compare to stored snapshot)

The orchestrator workflow is:

```
1. Load snapshot from aide-state in HTML file
2. AI emits one or more primitives
3. For each primitive:
   a. Wrap in event (add id, sequence, timestamp, metadata)
   b. reduce(snapshot, event) → new snapshot
   c. If rejected: report error to orchestrator, stop
   d. If warnings: collect for response
4. Append all events to aide-events in HTML file
5. Replace aide-state with final snapshot
6. Re-render <body> from final snapshot
7. Write HTML file
```

This means the reducer applies 1–5 events per user message, not hundreds. The full replay path exists for correctness, not for hot-path performance.

---

## Testing Strategy

The reducer is the most testable component in the system. Pure function, no IO, no mocking.

**Test categories:**

1. **Happy path per primitive.** 22 tests minimum, one per primitive type. Apply event to appropriate state, verify snapshot.

2. **Rejection per primitive.** Each rejection reason has a test. Entity not found, collection not found, type mismatch, etc.

3. **Cardinality enforcement.** Seat Linda at table 3, then seat Linda at table 5 (many_to_one). Verify table 3 link is gone.

4. **Constraint checking.** Create exclude_pair constraint, then violate it. Verify warning. Set strict, verify rejection.

5. **Schema evolution.** Add field with default, verify backfill. Remove field, verify cleanup. Rename field, verify entities updated.

6. **Cascade.** Remove collection, verify entities, views, blocks, and relationships all cleaned up.

7. **Idempotency.** Remove already-removed entity. Update with same values. Set relationship that already exists.

8. **Determinism.** Replay the same 50 events 100 times. Verify identical snapshot every time (JSON serialization order matters — use sorted keys).

9. **Round-trip.** Generate snapshot, serialize to JSON, deserialize, verify equality.

10. **Walkthrough.** Full grocery list scenario: create collection, add 5 items, check off 2, add a field (category), remove an item, change store. Verify final state matches expected snapshot exactly.
