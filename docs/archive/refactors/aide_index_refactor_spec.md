# display.js — One Renderer, Three Runtimes

**Status:** Draft  
**Scope:** Extract display logic from `frontend/index.html` into `display.js`, kill `react_preview.py`  
**Goal:** One source of truth for "entity state → output" across editor, CLI, and publish.

---

## Architecture

```
display.js
├── resolveDisplay(entity, childIds, entities) → string
├── renderHtml(store)       ← editor: body fragment for Shadow DOM
├── renderText(store)       ← CLI: terminal unicode
├── renderDocument(store, options)  ← publish: full standalone HTML page
├── formatValue(value, type, channel) → string
├── CSS (exported string constant)
└── helpers: escapeHtml, humanize, getChildren, inferType
```

Three runtimes, one file:

| Consumer | Runtime | Calls | Gets |
|----------|---------|-------|------|
| Editor | Browser `<script>` | `renderHtml(store)` | HTML body fragment → `shadowRoot.innerHTML` |
| CLI | Node | `renderText(store)` | Unicode text → stdout |
| Publish | Node subprocess from Python | `renderDocument(store, opts)` | Full `<!DOCTYPE html>` page → R2 |

---

## What's In display.js

### `resolveDisplay(entity, childIds, entities) → string`

The ~30-line heuristic that determines display type. Extract of the existing `inferDisplay` from index.html. Returns `"table"`, `"checklist"`, `"card"`, `"metric"`, `"text"`, `"image"`, `"page"`, `"section"`, `"list"`.

### `renderHtml(store) → string`

What `buildPreviewHtml()` does today — walks root entities, resolves display, emits HTML body content. Includes `data-entity-id` and `data-field` attributes for inline editing. Does NOT include `<html>`, `<head>`, `<style>`, fonts — that's the Shadow DOM host's job.

This is a direct refactor of the existing `renderEntity` → `renderPage`/`renderTable`/`renderChecklist`/`renderCard`/etc. chain from index.html.

### `renderText(store) → string`

New. Same entity walk, same `resolveDisplay`, different output:

| Display | HTML | Text |
|---------|------|------|
| page | `<div class="aide-page">` | `Title\n═══════` |
| table | `<table>` with `<th>/<td>` | Aligned columns with `─` separators |
| checklist | Checkboxes with `data-entity-id` | `✓`/`○` prefixed lines |
| metric | `<div class="aide-metric">` | `Label: Value` |
| card | `<div class="aide-card">` | Indented key-value pairs |
| text | `<p>` | Plain text |
| image | `<figure><img>` | `[Image: alt]` |
| divider | `<hr>` | `────────────` |

### `renderDocument(store, options) → string`

Full standalone HTML page for publish. Wraps `renderHtml` output with:
- `<!DOCTYPE html>`, `<html>`, `<head>`, `<body>`
- `<title>`, OG meta tags (title, description)
- Google Fonts `<link>`
- `<style>` with the CSS constant
- Optional footer ("Made with AIde" for free tier)
- "Updated" timestamp

This replaces `react_preview.py` entirely.

### `formatValue(value, type, channel) → string`

Channel-aware value formatting:

| Type | HTML | Text |
|------|------|------|
| `null` | `<span class="aide-null">—</span>` | `—` |
| `boolean` (true) | `✓` (with checkbox HTML) | `✓` |
| `boolean` (false) | `○` (with checkbox HTML) | `○` |
| `date` | `Feb 27` (escaped) | `Feb 27` |
| `number` | `3` (escaped) | `3` |
| `string` | escaped | raw |

### CSS

The renderer CSS currently lives in `<script id="renderer-css-template">` in index.html and is duplicated in `react_preview.py`. Moves to an exported constant in `display.js`:

```javascript
const RENDERER_CSS = `
  .aide-page { max-width: 720px; margin: 0 auto; ... }
  .aide-table { ... }
  ...
`;
```

Editor: `shadowRoot.innerHTML = '<style>' + display.RENDERER_CSS + '</style>' + display.renderHtml(store)`

Publish: `renderDocument` embeds it in `<style>`.

One copy.

### `store` interface

The functions expect an object matching the existing `entityStore` shape:

```javascript
{
  entities: { id → { id, display, props, parent, ... } },
  rootIds: [ "id1", "id2", ... ],
  meta: { title, ... }
}
```

No changes to entityStore. The display module reads from it, never writes.

---

## UMD Tail

```javascript
// Browser: display.renderHtml(entityStore)
// Node: const display = require('./display.js')
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    resolveDisplay, renderHtml, renderText, renderDocument,
    formatValue, RENDERER_CSS, escapeHtml, humanize, getChildren, inferType
  };
}
```

No build step. `<script src="/static/display.js">` in the browser. `require('./display.js')` in Node.

---

## What Dies

| File | Reason |
|------|--------|
| `engine/kernel/react_preview.py` | Replaced by `renderDocument` |
| React display components in index.html | Confirmed dead code. `PreviewApp`, `AideEntity`, `PageDisplay`, `TableDisplay`, etc. Shadow DOM path doesn't use them. |
| Vanilla renderer functions in index.html | Moved to `display.js` (`renderEntity`, `renderPage`, `renderTable`, `renderCard`, `renderChecklist`, `buildPreviewHtml`, `inferDisplay`, `escapeHtml`, etc.) |
| Renderer CSS in index.html | Moved to `display.js` constant |
| Renderer CSS in `react_preview.py` | Moved to `display.js` constant |

---

## What Stays in index.html

Everything that isn't display logic:

- HTML skeleton (auth screen, dashboard, editor layout)
- Editor chrome CSS
- Entity store (`entityStore`, `applyDelta`)
- Shadow DOM setup (attach shadow, scroll save/restore, event delegation for inline edits, link interception, checkbox binding)
- WebSocket client (delta routing, snapshot hydration, direct edits)
- Chat UI (messages, markdown, streaming indicators)
- Auth (magic link flow)
- Dashboard (aide grid, cards, archive)
- Editor orchestration (openEditor, showScreen, URL routing, publish button)

Shadow DOM preview becomes:

```javascript
function refreshEntityPreview() {
    if (!shadowRoot) { /* setup shadow root, event delegation... */ }
    const scrollY = shadowRoot.host.scrollTop;
    const html = display.renderHtml(entityStore);
    shadowRoot.innerHTML = '<style>' + display.RENDERER_CSS + '</style>' + html;
    requestAnimationFrame(() => { shadowRoot.host.scrollTop = scrollY; });
}
```

---

## Publish Path Changes

Before:
```python
# backend/routes/publish.py
from engine.kernel.react_preview import render_react_preview
html = render_react_preview(aide.state, title=title)
```

After:
```python
# backend/routes/publish.py
import subprocess, json

def render_published_html(state, title, footer=None):
    payload = json.dumps({"state": state, "title": title, "footer": footer})
    result = subprocess.run(
        ["node", "-e",
         "const d=require('./static/display.js');"
         f"const p=JSON.parse('{...}');"  # careful with escaping
         "process.stdout.write(d.renderDocument(p.state,p));"],
        capture_output=True, text=True, timeout=5
    )
    if result.returncode != 0:
        raise RuntimeError(f"Render failed: {result.stderr}")
    return result.stdout
```

Or cleaner — a tiny `render.js` script:

```javascript
// scripts/render.js
const display = require('../static/display.js');
const input = JSON.parse(require('fs').readFileSync('/dev/stdin', 'utf8'));
process.stdout.write(display.renderDocument(input.state, input));
```

```python
result = subprocess.run(
    ["node", "scripts/render.js"],
    input=json.dumps({"state": state, "title": title, "footer": footer}),
    capture_output=True, text=True, timeout=5
)
```

---

## CLI

Thin Node script:

```javascript
// cli/aide-view.js
const display = require('../static/display.js');
const state = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
console.log(display.renderText(state));
```

Streaming version:

```javascript
// cli/aide-stream.js
const display = require('../static/display.js');
const WebSocket = require('ws');

const store = { entities: {}, rootIds: [], meta: {} };
const ws = new WebSocket(`wss://get.toaide.com/ws/aide/${aideId}`);

ws.on('message', (data) => {
    const delta = JSON.parse(data);
    applyDelta(store, delta);  // same logic as entityStore.applyDelta
    process.stdout.write('\x1B[2J\x1B[H');  // clear screen
    console.log(display.renderText(store));
});
```

---

## Migration Steps

### Step 1: Create `display.js` with extracted code

Move from index.html into `display.js`:
- `inferDisplay` → `resolveDisplay`
- `renderEntity`, `renderPage`, `renderTable`, `renderChecklist`, `renderCard`, `renderMetric`, `renderText`, `renderImage`, `renderSection`, `renderList`
- `buildPreviewHtml` → `renderHtml`
- `escapeHtml`, `humanize`, `getChildren`, `inferType`, `formatValue`, `deriveColumns`, `applyStyles`
- Renderer CSS constant
- UMD export tail

**Gate:** `display.renderHtml(entityStore)` produces identical output to old `buildPreviewHtml()`.

### Step 2: Wire editor to display.js

- Add `<script src="/static/display.js">` to index.html
- Replace `buildPreviewHtml()` call with `display.renderHtml(entityStore)`
- Replace inline CSS template reference with `display.RENDERER_CSS`
- Delete moved functions from index.html
- Delete React display components (dead code)

**Gate:** Editor preview identical. Inline editing works. Scroll preserved.

### Step 3: Add `renderText`

Write `renderText(store)` in display.js alongside `renderHtml`. Same `resolveDisplay` call, different output formatting.

**Gate:** `node -e "const d=require('./display.js'); ..."` with a test entity store produces readable terminal output.

### Step 4: Add `renderDocument`, kill `react_preview.py`

Write `renderDocument(store, options)` — wraps `renderHtml` in full HTML page.

Update `backend/routes/publish.py` to call Node subprocess instead of `render_react_preview`.

Delete `engine/kernel/react_preview.py`.

**Gate:** Published pages at `/s/{slug}` look identical. OG tags present. Footer injection works.

---

## Acceptance Criteria

1. **One file.** All display logic lives in `display.js`. No rendering code in index.html, no rendering code in Python.
2. **Editor unchanged.** Shadow DOM preview identical before and after. Inline editing works.
3. **Publish unchanged.** Pages at `/s/{slug}` visually identical. OG tags, footer, fonts all present.
4. **CLI works.** `renderText(store)` produces readable terminal output for tables, checklists, cards, metrics, pages.
5. **Three runtimes.** `display.js` loads in browser via `<script>`, in Node via `require`, and renders standalone HTML via `renderDocument`.
6. **One CSS.** Renderer styles defined once in `display.js`, used by both Shadow DOM and published pages.
