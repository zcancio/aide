# 04: Display Components

> **Prerequisites:** [Data Model](core_data_model.md)
> **Next:** [05 Intelligence Tiers](05_intelligence_tiers.md) · [07 Edge Cases](07_edge_cases.md) (for direct edit and undo behavior)

---

## Architecture

The renderer is a recursive walk of the entity tree that produces HTML strings. Each entity resolves to a render function based on its `display` hint. The HTML is injected into a Shadow DOM container for style isolation.

**Implementation:** `frontend/src/lib/display/render-html.js`

```js
function renderEntity(entityId, entities) {
  const entity = entities[entityId];
  if (!entity || entity._removed) return '';

  const childIds = getChildren(entities, entityId);
  const display = resolveDisplay(entity, childIds, entities);

  switch (display) {
    case 'page': return renderPage(entity, childIds, entities);
    case 'section': return renderSection(entity, childIds, entities);
    case 'metric': return renderMetric(entity);
    case 'text': return renderText(entity);
    case 'image': return renderImage(entity);
    case 'checklist': return renderChecklist(entity, childIds, entities);
    case 'table': return renderTable(entity, childIds, entities);
    case 'list': return renderList(entity, childIds, entities);
    default: return renderCard(entity, childIds, entities);
  }
}

export function renderHtml(store) {
  if (!store || !store.entities) return '';
  // ... renders root entities into HTML string
}
```

There is no "streaming mode" vs "done mode." The client always renders from the current graph state. Whether that state arrived all at once (page load), progressively (WebSocket stream), or as a single delta (direct edit) — same code path.

---

## Direct Editing

Every rendered value is clickable to edit inline. This is implemented via data attributes on HTML elements:

```html
<span class="editable-field"
      data-entity-id="guest_linda"
      data-field="name">Aunt Linda</span>
```

The Editor component listens for clicks on `.editable-field` elements and opens an inline input. On blur or Enter, it emits a `direct_edit` message via WebSocket:

```js
{ type: "direct_edit", entity_id: "guest_linda", field: "name", value: "Linda" }
```

**Behaviors:**
- Click → edit mode (tap on mobile)
- Blur or Enter → commit, emits `direct_edit`, <200ms round trip
- Escape → cancel
- Booleans (checkboxes) toggle immediately via `data-type="boolean"`
- Empty values show dash placeholder, still clickable

---

## Component Catalog

### renderPage

Root container. One per aide.

```js
function renderPage(entity, childIds, entities) {
  const title = props.title || props.name || '';
  return `<div class="aide-page">
    <h1 class="editable-field" data-entity-id="${entity.id}" data-field="title">${title}</h1>
    ${children || '<p class="aide-empty">Send a message to get started.</p>'}
  </div>`;
}
```

### renderSection

Titled grouping. The main structural divider.

- Renders: titled block, children below
- Empty state: "No items yet."

### renderCard

Bordered card showing props as labeled key-value pairs.

- Renders: bordered container, `title` as header, remaining props as "Label: Value" rows
- Each value editable via `editable-field` class
- Best for: singular important items (ceremony details, venue info)
- Fallback when display hint is unknown or omitted

### renderList

Vertical list of children.

- Renders: `<ul>` with children as `<li>` items
- Primary field (name/title) on left, secondary props on right
- Empty state: "No items yet."

### renderTable

The workhorse. Structured data with multiple fields.

- Renders: `<table>` with column headers derived from union of all children's props
- **Every cell is directly editable** — click any cell to change the value
- Columns derived dynamically: `Object.keys(child.props).filter(k => !k.startsWith('_'))`
- Empty state: "No items yet."
- Best for: guest lists, food assignments, anything with 3+ fields per item

### renderChecklist

List with checkboxes.

- Renders: `<ul>` with checkbox input for boolean prop (`done` or `checked`)
- **Checkbox toggle emits `direct_edit` directly** — no LLM, instant
- Checked items show strikethrough via CSS class
- Summary line: "3 of 7 complete"

### renderMetric

Single important number with label.

- Renders: large centered value with smaller label
- Value is editable
- Best for: "38 guests confirmed", "$1,200 remaining"

### renderText

Freeform paragraph. Welcome messages, notes, descriptions.

- Renders: `<p>` with content from `text`, `content`, or `body` prop
- Click to edit inline
- Max ~100 words (enforced in system prompt, not component)

### renderImage

Image from URL with optional caption.

- Renders: `<img>` with optional caption below
- No upload — user pastes URL
- Caption is editable

---

## Display Hint Inference

When `display` is omitted on `entity.create`, the renderer infers it.

**Implementation:** `frontend/src/lib/display/helpers.js`

```js
export function resolveDisplay(entity, childIds, entities) {
  const hint = (entity?.display || '').toLowerCase();
  if (hint) return hint;

  const props = entity?.props || {};
  if (props.src || props.url) return 'image';
  if (typeof props.done === 'boolean' || typeof props.checked === 'boolean') return 'card';
  if ((props.value !== undefined || props.count !== undefined) &&
      Object.keys(props).filter(k => !k.startsWith('_')).length <= 3) return 'metric';
  if (props.text && Object.keys(props).filter(k => !k.startsWith('_')).length === 1) return 'text';

  if (childIds.length > 0) {
    const firstChild = entities[childIds[0]];
    const cp = firstChild?.props || {};
    if (typeof cp.done === 'boolean' || typeof cp.checked === 'boolean') return 'checklist';
    return 'table';
  }
  return 'card';
}
```

| Condition | Inferred Display |
|-----------|-----------------|
| Has `src` or `url` prop | `image` |
| Has `done` or `checked` boolean | `card` |
| Has `value`/`count` with ≤3 props | `metric` |
| Has only `text` prop | `text` |
| Has children with boolean props | `checklist` |
| Has children (default) | `table` |
| No children (default) | `card` |

---

## Helpers

**Implementation:** `frontend/src/lib/display/helpers.js`

```js
escapeHtml(str)              // Escape HTML entities
humanize("traveling_from")   // → "Traveling From"
getChildren(entities, parentId)  // Get child entity IDs, sorted by _created_seq
resolveDisplay(entity, childIds, entities)  // Infer display hint
```

---

## CSS Classes

The renderer uses a consistent class naming convention:

| Class | Purpose |
|-------|---------|
| `.aide-page` | Root container |
| `.aide-section` | Section wrapper |
| `.aide-section__title` | Section heading |
| `.aide-card` | Card container |
| `.aide-card__title` | Card heading |
| `.aide-card__field` | Key-value row |
| `.aide-table` | Table element |
| `.aide-table__th` | Table header cell |
| `.aide-table__td` | Table data cell |
| `.aide-checklist` | Checklist `<ul>` |
| `.aide-checklist__item` | Checklist `<li>` |
| `.aide-checklist__checkbox` | Checkbox input |
| `.aide-checklist__label--done` | Strikethrough for completed |
| `.aide-list` | List `<ul>` |
| `.aide-metric` | Metric container |
| `.aide-text` | Text paragraph |
| `.aide-image` | Image container |
| `.aide-empty` | Empty state message |
| `.editable-field` | Clickable editable value |

Styles are defined in `frontend/display/tokens.css` and injected into Shadow DOM for isolation.

---

## Shadow DOM Architecture

The preview uses Shadow DOM to isolate aide content styles from the editor chrome. This prevents CSS conflicts and ensures published pages render identically in the editor.

**Implementation:** `frontend/src/components/Preview.jsx`

```
┌─────────────────────────────────────────────────────────┐
│  Document (editor chrome styles)                        │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  <div ref={containerRef}>                         │  │
│  │                                                   │  │
│  │    #shadow-root (open)                           │  │
│  │    ┌───────────────────────────────────────────┐  │  │
│  │    │  <style>                                  │  │  │
│  │    │    /* tokens.css - aide content styles */ │  │  │
│  │    │  </style>                                 │  │  │
│  │    │                                           │  │  │
│  │    │  <div class="aide-preview-content">       │  │  │
│  │    │    <!-- renderHtml() output -->           │  │  │
│  │    │    <div class="aide-page">...</div>       │  │  │
│  │    │  </div>                                   │  │  │
│  │    └───────────────────────────────────────────┘  │  │
│  │                                                   │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Initialization

```js
// Preview.jsx
useEffect(() => {
  if (!containerRef.current || shadowRef.current) return;

  // Create Shadow DOM once
  const shadow = containerRef.current.attachShadow({ mode: 'open' });
  shadowRef.current = shadow;

  // Inject stylesheet
  const style = document.createElement('style');
  style.textContent = RENDERER_CSS;  // tokens.css as raw string
  shadow.appendChild(style);

  // Create content container
  const content = document.createElement('div');
  content.className = 'aide-preview-content';
  shadow.appendChild(content);
}, []);
```

### Why Shadow DOM

| Concern | Solution |
|---------|----------|
| **Style isolation** | Editor CSS cannot affect aide content; aide content cannot affect editor |
| **Consistent rendering** | Preview matches published page exactly (same CSS, same HTML) |
| **No CSS conflicts** | User-generated class names in aide content won't clash with app |
| **Scoped event handling** | Event delegation within shadow root only |

### CSS Import Strategy

```js
// frontend/src/lib/display/index.js
import RENDERER_CSS from '../../../display/tokens.css?raw';
export { RENDERER_CSS };
```

The `?raw` suffix imports CSS as a string for injection into Shadow DOM. Vite handles this at build time.

### Event Delegation

Events bubble up within the shadow tree. The Preview component uses event delegation:

```js
content.addEventListener('click', (e) => {
  // Direct edit: click on editable field
  const editable = e.target.closest('.editable-field');
  if (editable && onDirectEdit) {
    const entityId = editable.dataset.entityId;
    const field = editable.dataset.field;
    // ... prompt and emit direct_edit
  }

  // Checkbox toggle
  const checkbox = e.target.closest('.aide-checklist__checkbox');
  if (checkbox && onDirectEdit) {
    onDirectEdit(entityId, field, checkbox.checked);
  }

  // External links open in new tab
  const link = e.target.closest('a');
  if (link && link.href) {
    e.preventDefault();
    window.open(link.href, '_blank');
  }
});
```

---

## Editing Chrome

The editor chrome is the UI shell that wraps the aide preview. It consists of three components:

```
┌─────────────────────────────────────────────────────────┐
│  EditorHeader                                           │
│  ┌─────────────────────────────────────────────────────┐│
│  │ ← Back    My Graduation Party     Publish ▾  Share ││
│  └─────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────┤
│                                                         │
│                      Preview                            │
│                 (Shadow DOM content)                    │
│                                                         │
│                                                         │
│                                                         │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  ChatOverlay                                            │
│  ┌─────────────────────────────────────────────────────┐│
│  │ ═══════                                   (handle)  ││
│  │ [User]: Add Aunt Linda                              ││
│  │ [AI]: Linda added to guest list.                    ││
│  │ ┌─────────────────────────────────┐                 ││
│  │ │ What are you running?        ⌘K │                 ││
│  │ └─────────────────────────────────┘                 ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### EditorHeader

**Implementation:** `frontend/src/components/EditorHeader.jsx`

- Back button → navigate to dashboard
- Editable title (inline rename)
- Publish/unpublish toggle
- Share button (copy published URL)

### Preview

**Implementation:** `frontend/src/components/Preview.jsx`

- Shadow DOM container (see above)
- Receives `entityStore` from `useAide()` hook
- Calls `renderHtml(entityStore)` on every store change
- Preserves scroll position across re-renders
- Delegates direct edit clicks to parent

### ChatOverlay

**Implementation:** `frontend/src/components/ChatOverlay.jsx`

Three-state overlay behavior:

| State | Height | Visibility | Transition To |
|-------|--------|------------|---------------|
| `hidden` | Handle only | Drag handle visible | Swipe up → `input` |
| `input` | Input bar | Input + handle | Swipe up → `expanded`, swipe down → `hidden` |
| `expanded` | Full height | History + input | Swipe down → `input` |

**Auto-collapse timers:**
- `expanded` → `input` after 5 seconds of inactivity
- `input` → `hidden` after 30 seconds of inactivity
- New message arrival → auto-expand to `expanded`

**Keyboard shortcut:** `Cmd/Ctrl+K` opens overlay to `input` state

**Touch gestures:**
- Swipe up 80px → expand one level
- Swipe down 80px → collapse one level

---

## SPA Design

The frontend is a React single-page application with client-side routing.

**Implementation:** `frontend/src/components/App.jsx`

### Route Structure

```
/                    → Dashboard (list of aides)
/a/:aideId           → Editor (single aide)
/flight-recorder     → Dev tool (telemetry viewer)
/demo/*              → Public demo patterns (no auth)
```

### Auth Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   App.jsx       │     │  AuthProvider   │     │   AuthScreen    │
│                 │     │                 │     │                 │
│  <AuthProvider> │────▶│  useAuth()      │────▶│  Magic link     │
│    <AppRoutes>  │     │  isLoading      │     │  email form     │
│  </AuthProvider>│     │  isAuthenticated│     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                │
                                │ authenticated
                                ▼
                        ┌─────────────────┐
                        │  Dashboard /    │
                        │  Editor         │
                        └─────────────────┘
```

**Auth states:**
1. `isLoading: true` → show nothing (checking session)
2. `isAuthenticated: false` → show `AuthScreen`
3. `isAuthenticated: true` → show authenticated routes

### State Management

No Redux, no external state library. React hooks only.

| Hook | Purpose | Scope |
|------|---------|-------|
| `useAuth()` | Authentication state | App-wide (context) |
| `useAide()` | Entity store + delta handling | Per-editor |
| `useWebSocket()` | WebSocket connection + message handling | Per-editor |
| `useState()` | Local component state | Component |

### Data Flow

```
┌────────────────────────────────────────────────────────────────────┐
│                           Editor.jsx                               │
│                                                                    │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │ useAide()    │    │useWebSocket()│    │ useState (messages)  │  │
│  │              │    │              │    │                      │  │
│  │ entityStore  │◄───│ onDelta      │    │ messages array       │  │
│  │ handleDelta  │    │ onSnapshot   │    │ setMessages          │  │
│  │ handleSnapshot│   │ onVoice ─────┼───▶│                      │  │
│  └──────┬───────┘    │              │    └──────────────────────┘  │
│         │            │ send()       │                              │
│         ▼            │ sendDirectEdit│                             │
│  ┌──────────────┐    └──────┬───────┘                              │
│  │  Preview     │           │                                      │
│  │              │           ▼                                      │
│  │ renderHtml() │    ┌──────────────┐                              │
│  └──────────────┘    │ ChatOverlay  │                              │
│                      │              │                              │
│                      │ onSend ──────┼──▶ WebSocket message         │
│                      └──────────────┘                              │
└────────────────────────────────────────────────────────────────────┘
```

### Entity Store

**Implementation:** `frontend/src/lib/entity-store.js`

Immutable store with delta application:

```js
// Store shape
{
  entities: { [id]: EntityData },
  rootIds: string[],
  meta: { title?, identity?, ... }
}

// Delta types
{ type: 'entity.create', id, data }
{ type: 'entity.update', id, data }
{ type: 'entity.remove', id }
{ type: 'meta.update', data }
```

All functions return new objects — no mutation:

```js
export function applyDelta(store, delta) {
  if (delta.type === 'entity.create') {
    return {
      ...store,
      entities: { ...store.entities, [delta.id]: delta.data },
      rootIds: isRoot ? [...store.rootIds, delta.id] : store.rootIds,
    };
  }
  // ...
}
```

### Hydration Flow

On editor mount:

1. **REST calls** (parallel):
   - `GET /api/aides/{aideId}` → aide metadata
   - `GET /api/aides/{aideId}/history` → conversation history

2. **WebSocket connect** → `/ws/aide/{aideId}`

3. **Server sends snapshot** (hydration):
   ```
   { type: "snapshot.start" }
   { type: "entity.create", id: "page", data: {...} }
   { type: "entity.create", id: "guests", data: {...} }
   ...
   { type: "snapshot.end" }
   ```

4. **Client applies deltas** → `handleSnapshot(deltas)`

5. **Preview renders** → `renderHtml(entityStore)`

### Build & Bundle

**Tooling:** Vite

```
frontend/
├── index.html          # SPA entry point
├── src/
│   ├── main.jsx        # React DOM render
│   ├── components/     # React components
│   ├── hooks/          # Custom hooks
│   └── lib/
│       ├── api.js      # REST client
│       ├── ws.js       # WebSocket client
│       ├── entity-store.js
│       └── display/    # Renderer
└── display/
    └── tokens.css      # Aide content styles
```

**Output:** Single `index.html` with bundled JS/CSS, served by FastAPI for all SPA routes.
