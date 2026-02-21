# Engine Refactor: Strip Renderer

## Context

The engine (`engine.ts` / `engine.js`) is 920 lines. ~285 lines are HTML renderer + CSS that are now redundant — React owns rendering. The engine should become a pure state machine: events in → snapshot out.

## What to remove

Delete everything from the `// ── Renderer` section header (line 589 in .js, ~line 620 in .ts) through the end of the file. Specifically:

### Functions to delete
- `esc()` — HTML escaping
- `inline()` — markdown-to-HTML inline formatting
- `displayName()` — field name prettification
- `fmtValue()` — value formatting for HTML output
- `deriveDesc()` — OG description derivation
- `applySort()` — **move, don't delete** (see below)
- `applyFilter()` — **move, don't delete** (see below)
- `renderBlock()` — block tree → HTML
- `renderCollectionView()` — collection → HTML table/list
- `renderTable()` — entity list → HTML table
- `renderList()` — entity list → HTML list
- `renderAnnotations()` — annotations → HTML
- `render()` — main render entry point (the full-page HTML assembly)

### Constants to delete
- `CSS` — the entire CSS string constant (~50 lines)

### Functions to delete from exports
- `render` — remove from exports
- `parseAideHtml` — remove entirely (HTML parsing is server-side, not engine's job)

## What to promote to exports

These are currently private but React needs them. Move them from the renderer section into a new `// ── Query Helpers` section right after the reducer map, and **export** them:

```typescript
// ── Query Helpers ──────────────────────────────────────────────────────

export function baseType(t: SchemaType): string {
  if (typeof t === "string") return t.replace(/\?$/, "")
  if (typeof t === "object" && "enum" in t) return "enum"
  if (typeof t === "object" && "list" in t) return "list"
  return "unknown"
}

export function isNullable(t: SchemaType): boolean {
  return typeof t === "string" && t.endsWith("?")
}

export function applySort(entities: Entity[], cfg: Record<string, any>): Entity[] {
  const sb = cfg.sort_by
  if (!sb) return entities
  const rev = cfg.sort_order === "desc"
  return [...entities].sort((a, b) => {
    const av = a[sb], bv = b[sb]
    const an = av == null ? 1 : 0, bn = bv == null ? 1 : 0
    if (an !== bn) return an - bn
    if (av < bv) return rev ? 1 : -1
    if (av > bv) return rev ? -1 : 1
    return 0
  })
}

export function applyFilter(entities: Entity[], cfg: Record<string, any>): Entity[] {
  const f = cfg.filter
  if (!f) return entities
  return entities.filter(e => Object.entries(f).every(([k, v]) => e[k] === v))
}

export function resolveViewEntities(snapshot: AideState, viewId: string): Entity[] {
  const view = snapshot.views[viewId]
  if (!view) return []
  const coll = snapshot.collections[view.source]
  if (!coll || coll._removed) return []
  let entities = Object.values(coll.entities).filter(e => !e._removed)
  const cfg = view.config || {}
  entities = applySort(entities, cfg)
  entities = applyFilter(entities, cfg)
  return entities
}

export function resolveViewFields(snapshot: AideState, viewId: string): string[] {
  const view = snapshot.views[viewId]
  if (!view) return []
  const coll = snapshot.collections[view.source]
  if (!coll || coll._removed) return []
  const cfg = view.config || {}
  return cfg.show_fields || Object.keys(coll.schema).filter(f => !f.startsWith("_"))
}
```

Note: `baseType` is currently used internally by the reducer (in `fieldUpdate` for type compatibility checks). After this refactor it will be both internal AND exported. Don't break the internal usage — just add the `export` keyword.

## Update the file header

Change from:
```
Single-file kernel: primitives, validator, reducer, renderer.
```
To:
```
Single-file kernel: primitives, validator, reducer.
```

Update usage comment from:
```
import { emptyState, reduce, replay, render, parseAideHtml } from "./engine"
let snap = emptyState()
for (const evt of events) { snap = reduce(snap, evt).snapshot }
const html = render(snap, blueprint, events)
```
To:
```
import { emptyState, reduce, replay, baseType, resolveViewEntities } from "./engine"
let snap = emptyState()
for (const evt of events) { snap = reduce(snap, evt).snapshot }
// React renders from snapshot directly
```

## Remove unused types

- Delete `RenderOptions` interface
- Delete `Blueprint` interface (blueprint is app-level, not engine-level)
- Keep all other types — `AideState`, `Collection`, `Entity`, `Block`, `View`, `Event`, `Warning`, `ReduceResult`, `SchemaType`, etc.

## Files to update

1. **`engine.ts`** — the source of truth. Apply all changes here.
2. **`engine.js`** — regenerate by compiling the .ts, or manually apply the same deletions. The .js file is a hand-transpiled copy (no build step), so apply identical changes.
3. **`engine.py`** — check if it has the same renderer. If so, apply the same strip. Keep `base_type`, `apply_sort`, `apply_filter`, `resolve_view_entities`, `resolve_view_fields` as exported functions.

## Do NOT touch

- All reducer logic (lines 1–588 in .js) — zero changes
- Type system (`SCALAR_TYPES`, `isValidType`, `validateValue`) — zero changes
- `emptyState()`, `reduce()`, `replay()` — zero changes
- All 21 reducer functions (entity/collection/field/relationship/block/view/style/meta primitives)
- Constraint checking logic
- The `REDUCERS` map

## Validation

After refactoring, run the existing test suites. They should all pass since they test reducer behavior, not rendering:
- `test_reducer_happy_path.py`
- `test_reducer_rejections.py`
- `test_reducer_cardinality.py`
- `test_reducer_determinism.py`
- `test_reducer_round_trip.py`

If any test imports `render` or `parseAideHtml`, update those imports to remove them. The tests should only exercise `emptyState`, `reduce`, and `replay`.

## Expected outcome

| Metric | Before | After |
|--------|--------|-------|
| engine.ts lines | ~920 | ~620 |
| engine.js lines | ~874 | ~590 |
| Exports | `emptyState, reduce, replay, render, parseAideHtml` | `emptyState, reduce, replay, baseType, isNullable, applySort, applyFilter, resolveViewEntities, resolveViewFields` |
| CSS constant | 50 lines | 0 |
| HTML generation | 12 functions | 0 |

The engine becomes a pure state machine + query helpers. React does all rendering.
