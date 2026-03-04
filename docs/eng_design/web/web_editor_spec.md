# Web Editor Spec

> **Prerequisites:** [Display Components](../core/core_display_components.md) · [Streaming Pipeline](../core/core_streaming_pipeline.md)
> **Related:** [UI Design System](../../ux/aide_ui_design_system_spec.md)

---

## Overview

The web editor is a React SPA that renders aide content in a Shadow DOM container with an editing chrome overlay. This spec covers web-specific implementation details.

**Implementation:** `frontend/src/`

---

## Shadow DOM Architecture

The preview uses Shadow DOM to isolate aide content styles from the editor chrome.

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

**Implementation:** `frontend/src/components/Preview.jsx`

```js
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
| **No CSS conflicts** | User-generated class names won't clash with app |
| **Scoped event handling** | Event delegation within shadow root only |

### CSS Import Strategy

```js
// frontend/src/lib/display/index.js
import RENDERER_CSS from '../../../display/tokens.css?raw';
export { RENDERER_CSS };
```

The `?raw` suffix imports CSS as a string for injection into Shadow DOM. Vite handles this at build time.

---

## Direct Editing

Every rendered value is clickable to edit inline via data attributes:

```html
<span class="editable-field"
      data-entity-id="guest_linda"
      data-field="name">Aunt Linda</span>
```

### Event Delegation

**Implementation:** `frontend/src/components/Preview.jsx`

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

### Direct Edit Protocol

On edit completion, emit via WebSocket:

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

Styles are defined in `frontend/display/tokens.css` and injected into Shadow DOM.

---

## Editing Chrome

The editor chrome wraps the aide preview:

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
├─────────────────────────────────────────────────────────┤
│  ChatOverlay                                            │
│  ┌─────────────────────────────────────────────────────┐│
│  │ ═══════                                   (handle)  ││
│  │ [User]: Add Aunt Linda                              ││
│  │ [AI]: Linda added to guest list.                    ││
│  │ ┌─────────────────────────────────────┐             ││
│  │ │ What are you running?        ⌘K │             ││
│  │ └─────────────────────────────────────┘             ││
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

---

## Renderer Implementation

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

### Helpers

**Implementation:** `frontend/src/lib/display/helpers.js`

```js
escapeHtml(str)              // Escape HTML entities
humanize("traveling_from")   // → "Traveling From"
getChildren(entities, parentId)  // Get child entity IDs, sorted by _created_seq
resolveDisplay(entity, childIds, entities)  // Infer display hint
```

---

## Build & Bundle

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
