# Phase 0b: Reducer Implementation

**Status:** ✅ Complete (2026-02-19)
**Prerequisites:** Phase 0a complete (golden files exist)
**Checkpoint:** All golden files reduce cleanly, test suite passes

---

## Goal

Build the v2 reducer as a pure function with no I/O. The reducer is the core state machine that applies JSONL events to produce snapshots.

```
reduce(snapshot, event) → snapshot | rejection
```

---

## Snapshot Structure

```python
Snapshot = {
    "meta": {
        "title": str | None,
        "identity": str | None,
        "annotations": [{"note": str, "pinned": bool, "ts": str}],
        "constraints": {constraint_id: Constraint}
    },
    "entities": {
        entity_id: {
            "id": str,
            "parent": str,  # "root" for top-level
            "display": str | None,
            "props": dict,
            "_removed": bool,
            "_styles": dict | None,
            "_children": [entity_id],  # ordered list of child IDs
            "_created_seq": int,
            "_updated_seq": int
        }
    },
    "relationships": [
        {"from": entity_id, "to": entity_id, "type": str, "cardinality": str}
    ],
    "rel_cardinalities": {rel_type: cardinality},  # persisted per type
    "rel_constraints": {constraint_id: Constraint},
    "styles": {
        "global": dict,  # primary_color, font_family, density
        "entities": {entity_id: dict}  # per-entity overrides
    },
    "_sequence": int  # monotonically increasing event counter
}
```

---

## Implementation Order

Build primitives in dependency order. Each primitive gets:
1. Handler function
2. Happy path tests
3. Rejection tests
4. Golden file validation

### 1. Entity Primitives (Core)

#### 1.1 `entity.create`

**Input:**
```json
{"t": "entity.create", "id": "guest_linda", "parent": "guests", "display": "row", "p": {"name": "Aunt Linda", "rsvp": "yes"}}
```

**Logic:**
1. Validate `id` is snake_case, max 64 chars
2. Reject if `id` already exists in `entities`
3. Reject if `parent` doesn't exist (unless `parent` == "root")
4. Create entity with `_removed: false`, `_children: []`
5. Append `id` to parent's `_children` list
6. Increment `_sequence`, set `_created_seq` and `_updated_seq`

**Tests:**
- [x] Create entity under root
- [x] Create entity under existing parent
- [x] Reject: duplicate ID
- [x] Reject: parent doesn't exist
- [x] Reject: invalid ID format (spaces, uppercase, >64 chars)
- [x] Props are stored correctly
- [x] Display hint inherited from parent if omitted

#### 1.2 `entity.update`

**Input:**
```json
{"t": "entity.update", "ref": "guest_linda", "p": {"rsvp": "confirmed", "dietary": "vegetarian"}}
```

**Logic:**
1. Reject if `ref` doesn't exist or is `_removed`
2. Merge `p` into existing `props` (shallow merge)
3. New fields extend the entity (schema inference)
4. Update `_updated_seq`

**Tests:**
- [x] Update existing prop
- [x] Add new prop (schema extension)
- [x] Multiple props in one update
- [x] Reject: entity doesn't exist
- [x] Reject: entity is removed

#### 1.3 `entity.remove`

**Input:**
```json
{"t": "entity.remove", "ref": "guest_linda"}
```

**Logic:**
1. Reject if `ref` doesn't exist
2. Set `_removed: true` on entity
3. Recursively set `_removed: true` on all descendants
4. Keep data for undo (soft delete)

**Tests:**
- [x] Remove leaf entity
- [x] Remove entity with children (cascade)
- [x] Reject: entity doesn't exist
- [x] Reject: already removed (idempotent? or reject?)

#### 1.4 `entity.move`

**Input:**
```json
{"t": "entity.move", "ref": "guest_linda", "parent": "vip_guests", "position": 0}
```

**Logic:**
1. Reject if `ref` doesn't exist or is removed
2. Reject if new `parent` doesn't exist or is removed
3. Reject if moving to self or own descendant (cycle prevention)
4. Remove `ref` from old parent's `_children`
5. Insert `ref` into new parent's `_children` at `position` (or append if omitted)
6. Update entity's `parent` field

**Tests:**
- [x] Move to different parent
- [x] Move with position
- [x] Move to end (no position)
- [x] Reject: entity doesn't exist
- [x] Reject: new parent doesn't exist
- [x] Reject: move to self
- [x] Reject: move to own descendant (cycle)

#### 1.5 `entity.reorder`

**Input:**
```json
{"t": "entity.reorder", "ref": "guests", "children": ["guest_steve", "guest_linda", "guest_james"]}
```

**Logic:**
1. Reject if `ref` doesn't exist or is removed
2. Validate `children` contains exactly all non-removed children of `ref`
3. Replace `_children` list with new order

**Tests:**
- [x] Reorder children
- [x] Reject: missing children in list
- [x] Reject: extra children in list
- [x] Reject: includes removed children

---

### 2. Relationship Primitives

#### 2.1 `rel.set`

**Input:**
```json
{"t": "rel.set", "from": "guest_linda", "to": "food_potato_salad", "type": "bringing", "cardinality": "many_to_one"}
```

**Logic:**
1. Reject if `from` or `to` entity doesn't exist or is removed
2. If `type` already has cardinality set, use that (ignore provided cardinality)
3. If first time seeing `type`, store `cardinality` in `rel_cardinalities`
4. **Cardinality enforcement:**
   - `many_to_one`: Remove existing relationships from `from` with same `type`
   - `one_to_one`: Remove existing from `from` AND to `to` with same `type`
   - `many_to_many`: No auto-removal
5. Add relationship to `relationships` list

**Tests:**
- [x] Create new relationship
- [x] Cardinality persisted on first set
- [x] many_to_one: auto-remove old link
- [x] one_to_one: auto-remove both sides
- [x] many_to_many: multiple links allowed
- [x] Reject: from entity doesn't exist
- [x] Reject: to entity doesn't exist

#### 2.2 `rel.remove`

**Input:**
```json
{"t": "rel.remove", "from": "guest_linda", "to": "food_potato_salad", "type": "bringing"}
```

**Logic:**
1. Find and remove matching relationship from `relationships` list
2. No-op if relationship doesn't exist (idempotent)

**Tests:**
- [x] Remove existing relationship
- [x] No-op if doesn't exist

#### 2.3 `rel.constrain`

**Input:**
```json
{"t": "rel.constrain", "id": "no_linda_steve", "rule": "exclude_pair", "entities": ["guest_linda", "guest_steve"], "rel_type": "seated_at", "message": "Keep apart", "strict": false}
```

**Logic:**
1. Store constraint in `rel_constraints`
2. If `strict: true`, validate existing relationships don't violate
3. Rules: `exclude_pair`, `require_pair`, `max_links`, `min_links`

**Tests:**
- [x] Add constraint
- [x] Strict constraint rejects violating state
- [x] Non-strict constraint allows with warning

---

### 3. Style Primitives

#### 3.1 `style.set`

**Input:**
```json
{"t": "style.set", "p": {"primary_color": "#2d3748", "font_family": "Inter", "density": "comfortable"}}
```

**Logic:**
1. Merge `p` into `styles.global`

**Tests:**
- [x] Set global styles
- [x] Merge with existing styles

#### 3.2 `style.entity`

**Input:**
```json
{"t": "style.entity", "ref": "guest_linda", "p": {"highlight": true, "color": "#e53e3e"}}
```

**Logic:**
1. Reject if `ref` doesn't exist
2. Store in `styles.entities[ref]` or merge if exists
3. Also store in entity's `_styles` field

**Tests:**
- [x] Set entity styles
- [x] Reject: entity doesn't exist

---

### 4. Meta Primitives

#### 4.1 `meta.set`

**Input:**
```json
{"t": "meta.set", "p": {"title": "Sophie's Graduation 2026", "identity": "Graduation party coordination"}}
```

**Logic:**
1. Merge `p` into `meta` (title, identity)

**Tests:**
- [x] Set title
- [x] Set identity
- [x] Update existing meta

#### 4.2 `meta.annotate`

**Input:**
```json
{"t": "meta.annotate", "p": {"note": "Guest count updated.", "pinned": false}}
```

**Logic:**
1. Append to `meta.annotations` list with timestamp

**Tests:**
- [x] Add annotation
- [x] Pinned annotation

#### 4.3 `meta.constrain`

**Input:**
```json
{"t": "meta.constrain", "id": "max_guests", "rule": "max_children", "parent": "guests", "value": 50, "message": "Max 50 guests", "strict": true}
```

**Logic:**
1. Store constraint in `meta.constraints`
2. If `strict: true`, validate current state doesn't violate

**Tests:**
- [x] Add structural constraint
- [x] Strict constraint enforcement

---

### 5. Signal Handling

Signals don't modify the snapshot but are parsed by the reducer.

#### 5.1 `voice`
- Extract and return separately (for chat display)
- Don't modify snapshot

#### 5.2 `escalate`
- Extract and return separately (for tier routing)
- Don't modify snapshot

#### 5.3 `batch.start` / `batch.end`
- Track batch state in reducer context
- Return batch boundaries for renderer buffering

---

## Test Suite Structure

```
engine/kernel/tests/
├── test_reducer_entity.py       # entity.* primitives
├── test_reducer_relationship.py # rel.* primitives
├── test_reducer_style.py        # style.* primitives
├── test_reducer_meta.py         # meta.* primitives
├── test_reducer_signals.py      # voice, escalate, batch
├── test_reducer_determinism.py  # same events → same snapshot
├── test_reducer_golden.py       # validate all golden files
└── conftest.py                  # fixtures, empty snapshot factory
```

### Golden File Integration Tests

```python
def test_golden_files_reduce_cleanly():
    """Every line from every golden file should be accepted."""
    golden_dir = Path("engine/kernel/tests/fixtures/golden")

    for golden_file in golden_dir.glob("*.jsonl"):
        snapshot = empty_snapshot()

        for line in golden_file.read_text().splitlines():
            if not line.strip() or line.startswith("```"):
                continue  # skip empty lines and code fences

            event = json.loads(line)
            result = reduce(snapshot, event)

            assert result.accepted, f"{golden_file.name}: {event} rejected: {result.reason}"
            snapshot = result.snapshot
```

### Determinism Test

```python
def test_replay_determinism():
    """Same events always produce identical snapshot."""
    events = load_golden_file("create_graduation.jsonl")

    snapshot1 = reduce_all(empty_snapshot(), events)
    snapshot2 = reduce_all(empty_snapshot(), events)

    assert snapshot1 == snapshot2
```

---

## File Structure

```
engine/kernel/
├── __init__.py
├── types.py          # Snapshot, Entity, Relationship, Event types
├── reducer.py        # Main reduce() function + handlers
├── validators.py     # ID validation, constraint checking
└── tests/
    └── ...
```

---

## Acceptance Criteria

1. **All golden files reduce cleanly** — zero rejections on valid golden file lines
2. **Test coverage >90%** — every primitive has happy path + rejection tests
3. **Determinism verified** — replay produces identical snapshots
4. **Pure function** — no I/O, no side effects, no global state
5. **Clear error messages** — rejections include reason and context

---

## Estimated Effort

| Task | Estimate |
|------|----------|
| Types + empty snapshot | 2 hours |
| entity.create, entity.update | 3 hours |
| entity.remove, entity.move, entity.reorder | 3 hours |
| rel.set, rel.remove, rel.constrain | 3 hours |
| style.set, style.entity | 1 hour |
| meta.set, meta.annotate, meta.constrain | 2 hours |
| Signal handling | 1 hour |
| Golden file integration tests | 2 hours |
| Determinism tests | 1 hour |
| **Total** | **~18 hours** |

---

## Notes

- The v1.3 reducer exists in `engine/kernel/reducer.py` but uses the old schema format (`ref`, `fields` nesting, TypeScript interfaces). The v2 reducer is a rewrite with the simplified JSONL format.
- Consider whether to replace v1.3 reducer or build v2 alongside it during transition.
- Golden files from phase 0a are stored in `engine/kernel/tests/fixtures/golden/`.
