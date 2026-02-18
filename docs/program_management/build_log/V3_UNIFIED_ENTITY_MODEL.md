# Build Log — v3 Unified Entity Model

**Date:** February 2026
**Issue:** Implement v3 Unified Entity Model
**Status:** Complete

---

## Summary

Refactored the AIde kernel from the v2 collection-based model to the v3 Unified Entity Model as specified in `docs/eng_design/unified_entity_model.md`.

**Key architectural shift:**
- `collections` + nested entities → `schemas` (TypeScript interfaces) + top-level `entities`
- Custom field types (`"string"`, `"int?"`) → TypeScript interfaces parsed by tree-sitter
- Single-channel HTML rendering → Multi-channel: `render_html` + `render_text` via Mustache templates
- Collection-scoped CRUD → Path-based entity addressing (`grocery_list/items/item_milk`)

---

## Files Changed

### New Files

| File | Description |
|------|-------------|
| `engine/kernel/ts_parser.py` | TypeScript interface parser using tree-sitter. Exports `parse_interface`, `parse_interface_cached`, `validate_entity_fields`, `ParsedInterface`, `ParsedField`. Handles: scalar types, Record<string,T>, T[], union/enum types, optional fields. Falls back to regex parsing if tree-sitter unavailable. |

### Modified Files

| File | Changes |
|------|---------|
| `requirements.txt` | Added `tree-sitter>=0.23.0`, `tree-sitter-typescript>=0.23.0`, `chevron>=0.14.0` |
| `engine/kernel/types.py` | Rewrote `Snapshot` dataclass: `collections`/`views`/`relationships`/`constraints`/`annotations` → `schemas`/`entities`. Version 3. Added `parse_entity_path()`, `is_valid_entity_path()`. Removed v2-only types/constants. |
| `engine/kernel/reducer.py` | Full rewrite. Handlers: `schema.create/update/remove`, `entity.create/update/remove` (path-based), `block.set/remove/reorder`, `style.set`, `meta.update/annotate`. Path resolution (`_get_entity_at_path`, `_set_entity_at_path`). TypeScript interface validation on entity create/update. Soft deletes with cascade to nested children. |
| `engine/kernel/renderer.py` | Full rewrite. Multi-channel: `render()` dispatches to `_render_html` or `_render_text`. `render_entity()` uses schema's `render_html`/`render_text` Mustache templates. Child collection rendering via `{{>fieldname}}` resolved by looking up child schema from parent's TypeScript interface (`Record<string,T>` → T → schema ID). Grid rendering: `_shape: [rows, cols]` → CSS grid (HTML) or ASCII grid (text). Schema styles collected into page CSS. |
| `engine/kernel/primitives.py` | Full rewrite. Validates v3 primitives: `schema.*`, `entity.*`, `block.*`, `style.set`, `meta.*`. Checks TypeScript interface parsability on `schema.create/update`. |

### Rewritten Tests (all pass, 720 total)

**Reducer tests** — rewritten for v3 primitives:
- `test_reducer_happy_path.py` — 29 tests (schema.*, entity.*, block.*, style.set, meta.*)
- `test_reducer_rejections.py` — 22 tests
- `test_reducer_determinism.py` — 13 tests (N-times replay, incremental vs full)
- `test_reducer_round_trip.py` — 22 tests
- `test_reducer_idempotency.py` — 13 tests
- `test_reducer_cascade.py` — 12 tests (soft delete + nested cascade)
- `test_reducer_constraints.py` — 17 tests (TypeScript interface validation)
- `test_reducer_cardinality.py` — 18 tests (path-based CRUD at depth 1/2/3)
- `test_reducer_schema_evolution.py` — 17 tests (schema.update)
- `test_reducer_grid_create.py` — 13 tests (_shape-based grids)
- `test_reducer_walkthrough.py` — 5 full scenario tests

**Renderer tests** — updated for v3 state structure

**Assembly tests** — updated: `collection.create` → `schema.create`, v2 entity format → v3

**Primitives validation tests** — rewritten for v3 primitives

---

## Design Decisions

### Schema IDs are snake_case, interface names are PascalCase

Schema IDs follow the AIde ID convention (`grocery_item`, `grocery_list`). TypeScript interface names are PascalCase by convention (`GroceryItem`, `GroceryList`). The renderer resolves `{{>items}}` by:
1. Finding the parent entity's schema interface
2. Parsing `Record<string, GroceryItem>` to extract `GroceryItem`
3. Searching all schemas for one whose parsed interface name equals `GroceryItem`
4. Using that schema's `render_html` / `render_text` template

This is transparent to the AI — it writes natural TypeScript, the renderer resolves the mapping.

### Entity validation is at-create-time, warnings at update-time

`entity.create` rejects if field values don't match the TypeScript interface (hard reject). `entity.update` adds warnings but doesn't reject — partial updates are valid and many updates only set a subset of fields.

### _shape is stored in child collection dict, not on the entity

`entity.squares._shape = [8, 8]` — the shape lives alongside the cell keys in the collection dict. The renderer detects `_shape` when iterating over a child collection and switches to grid layout.

### No migration needed

Per the issue: existing aides will be cleared before v3 rollout. No migration script written.

---

## Test Results

```
720 passed, 4 skipped in 6.16s
```

4 skipped = 2 postgres storage tests (known `put_published` UUID column issue, pre-existing) + 2 assembly tests (sequence validation not yet implemented, pre-existing).

---

## Checklist

- [x] `tree-sitter` and `tree-sitter-typescript` dependencies added
- [x] TypeScript parser module (`engine/kernel/ts_parser.py`) created
- [x] `types.py` updated with v3 state structure
- [x] `reducer.py` updated: `schema.create/update/remove`, `entity.create/update/remove` with path resolution
- [x] `renderer.py` updated: Mustache templates, multi-channel, child schema resolution, grid layout
- [x] `primitives.py` updated: v3 validators
- [x] All existing tests rewritten for v3 model
- [x] `ruff check` passes on all source files
- [x] `ruff format --check` passes on all source files
- [x] 720 tests pass
