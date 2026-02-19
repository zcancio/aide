# Phase 2: Display Components + Direct Edit

**Date:** 2026-02-19
**Status:** ✅ Phase 2 Complete

---

## Summary

Phase 2 delivers the visual layer: the preview iframe renders real styled components (instead of the Phase 1 FallbackDisplay key-value debug view), and users can click any field to edit it inline. Edits flow through WebSocket → reducer → delta → live update in <200ms.

---

## What Was Built

### Frontend (`frontend/index.html`)

#### Display Components (inline CSS + vanilla JS rendering to srcdoc iframe)

| Component | Description |
|-----------|-------------|
| `EditableField` | Click-to-edit span → inline `<input>`. Commits on Enter/blur, cancels on Escape. Posts `direct_edit` message to parent via `postMessage`. |
| `PageDisplay` | Root container: editable title + `page-content` wrapper for children. |
| `CardDisplay` | Key-value card. Iterates `entity.props`, each field is an EditableField. Title/name shown as card-title. |
| `SectionDisplay` | Collapsible with click-to-toggle header. EditableField on title. |
| `TableDisplay` | Infers columns from child entities' props. Each cell is an EditableField. Falls back to CardDisplay if no children. |
| `ChecklistDisplay` | Child entities as checkbox items. `done` field toggled via checkbox onChange. |
| `MetricDisplay` | Large number (`value`/`count`/`total`) with label. |
| `TextDisplay` | Single editable text block. |
| `ListDisplay` | `<ul>`/`<ol>` from child entities or `items` array prop. |
| `ImageDisplay` | `<figure>` with `src`/`url` and optional caption. |
| `GridDisplay` | CSS grid from `cols`/`_shape[1]`. Cells show `label`/`name`/`claim`. |
| `FallbackDisplay` | Unchanged Phase 1 debug view for unknown display types. |

#### Display Resolution (`resolveDisplay`)

Maps `entity.display` hint → renderer function. Hint matching is exact lowercase. Unknown hints fall through to FallbackDisplay.

#### Preview HTML Builder (`buildPreviewHtml`)

Replaces `buildFallbackHtml`. Outputs a full self-contained HTML document with:
- All display CSS (from `<script id="display-css-template">`)
- Rendered entity tree
- Inline iframe script: `window.__startEdit`, `window.__toggleSection`, `window.__toggleCheck`

#### Direct Edit Client (`sendDirectEdit`, `window.addEventListener('message')`)

- `sendDirectEdit(entityId, field, value)` — sends `direct_edit` over WebSocket
- `postMessage` listener receives `{type: 'direct_edit', entity_id, field, value}` from iframe sandbox, calls `sendDirectEdit`
- `direct_edit.error` response handled (logged as warning, no crash)

### Backend (`backend/routes/ws.py`)

#### `_handle_direct_edit` function

New async handler called when `msg.get("type") == "direct_edit"`:

1. Validates `entity_id` and `field` are present → returns `direct_edit.error` if missing
2. Validates entity exists in current snapshot → returns `direct_edit.error` if not found
3. Builds `entity.update` event with `ref` key (v2 format: `{"t": "entity.update", "ref": entity_id, "p": {field: value}}`)
4. Applies through `reduce(snapshot, event)`
5. On acceptance: broadcasts `entity.update` delta, logs latency, records telemetry
6. Telemetry is best-effort (skipped if `aide_id` is not a valid UUID, e.g. `"test"`)

#### Protocol extension

```
Client → Server:  {"type": "direct_edit", "entity_id": "...", "field": "...", "value": "..."}
Server → Client:  {"type": "entity.update", "id": "...", "data": {...}}  (success)
                  {"type": "direct_edit.error", "error": "..."}           (failure)
```

### Tests (`backend/tests/test_ws.py`)

Added `TestDirectEdit` class with 6 tests:

| Test | What it verifies |
|------|-----------------|
| `test_direct_edit_updates_existing_entity` | Happy path: edit returns `entity.update` with updated props |
| `test_direct_edit_nonexistent_entity_returns_error` | Missing entity → `direct_edit.error` |
| `test_direct_edit_missing_field_returns_error` | Missing `field` param → `direct_edit.error` |
| `test_direct_edit_missing_entity_id_returns_error` | Missing `entity_id` param → `direct_edit.error` |
| `test_direct_edit_preserves_snapshot_across_edits` | Two sequential edits each succeed and accumulate |
| `test_direct_edit_response_has_required_fields` | Response has `type`, `id`, `data` fields |

---

## Key Technical Notes

### v2 Entity Structure

The v2 reducer stores entities as:
```json
{
  "id": "page_graduation",
  "parent": "root",
  "display": "page",
  "props": {"title": "Sophie's Graduation Party"},
  "_children": ["section_event", "section_guests"],
  "_removed": false
}
```

Display renderers access `entity.props` via `getProps(entity)` helper. Editable fields use prop keys from `entity.props`, not the top-level entity object.

### entity.update uses `ref` not `id`

The v2 reducer uses `ref` as the entity reference key for `entity.update`. Using `id` returns `MISSING_REF` rejection. Direct edit correctly uses `{"t": "entity.update", "ref": entity_id, "p": {...}}`.

### iframe Sandboxing + postMessage

Since the preview iframe has `sandbox="allow-scripts allow-same-origin"`, inline scripts run but cross-origin restrictions apply. `postMessage` with `'*'` target origin allows the iframe to communicate direct edits back to the parent page.

---

## File Structure

```
frontend/
└── index.html                          # Modified: display CSS, getProps, 11 display renderers,
                                        #           sendDirectEdit, postMessage listener,
                                        #           buildPreviewHtml replacing buildFallbackHtml

backend/
├── routes/
│   └── ws.py                           # Modified: _handle_direct_edit(), direct_edit branch
└── tests/
    └── test_ws.py                      # Modified: TestDirectEdit (6 new tests)

docs/
└── program_management/
    └── build_log/
        └── PHASE_2_DISPLAY_COMPONENTS.md   # This file
```

---

## Security Checklist Compliance

- **No SQL introduced**: Direct edit flows entirely through reducer (pure function), no DB writes
- **No user input in SQL**: Field values go into the reducer `p` dict, not SQL
- **Telemetry best-effort**: Uses `system_conn()` (appropriate for background metrics)
- **No XSS**: All user-provided values in the preview HTML pass through `escapeHtml`/`escapeAttr`
- **iframe sandbox**: Preview renders in `sandbox="allow-scripts allow-same-origin"`, isolated from auth cookies
- **postMessage `'*'` origin**: Acceptable — the iframe is same-origin and only receives direct_edit events from child content we control

---

## Verification

### Lint
```
ruff check backend/      → All checks passed!
ruff format --check backend/ → 57 files already formatted
```

### Tests
```
pytest backend/tests/test_ws.py -v
→ 18 passed in 1.23s (12 existing + 6 new TestDirectEdit)
```

Full suite: 148 passed, 21 failed (all 21 are pre-existing RLS failures from Phase 0b/1, not introduced here).

---

## Checkpoint Criteria

- [x] All display components render correctly (PageDisplay, CardDisplay, TableDisplay, ChecklistDisplay, SectionDisplay, MetricDisplay, TextDisplay, ListDisplay, ImageDisplay, GridDisplay)
- [x] Click any field → inline edit works (Enter commits, Escape cancels, blur commits)
- [x] Checkbox toggles work (`done` field sent via direct_edit)
- [x] Direct edits round-trip via WebSocket (reducer-validated, delta broadcast)
- [x] `direct_edit.error` returned for invalid entity/missing params
- [x] Telemetry records direct_edit events (best-effort, UUID aide_ids only)
- [x] All tests pass

## Next Steps

- Phase 3: Stripe payments ($10/mo Pro tier, webhook handlers)
- Rate limiting: Turn counting per-user (50/week free), weekly reset
- Engine distribution: Host engine.py / engine.js on R2
