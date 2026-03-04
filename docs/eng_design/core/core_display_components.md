# Display Components

> **Prerequisites:** [Data Model](core_data_model.md)
> **Next:** [Intelligence Tiers](core_intelligence_tiers.md) · [Reliability & Performance](core_reliability_and_performance.md)
> **Implementations:** [Web Editor Spec](../web/web_editor_spec.md) · [CLI Render Spec](../cli/aide_cli_render_spec.md)

---

## Architecture

The renderer is a recursive walk of the entity tree. Each entity resolves to a **display type** based on its `display` hint (explicit or inferred). The renderer produces output appropriate to its target — HTML strings for web, ANSI for CLI, etc.

**Core algorithm:**

```
renderEntity(entityId, entities):
  entity = entities[entityId]
  if !entity or entity._removed: return empty

  childIds = getChildren(entities, entityId)
  display = resolveDisplay(entity, childIds, entities)

  switch display:
    'page'      → renderPage(entity, childIds, entities)
    'section'   → renderSection(entity, childIds, entities)
    'card'      → renderCard(entity, childIds, entities)
    'table'     → renderTable(entity, childIds, entities)
    'checklist' → renderChecklist(entity, childIds, entities)
    'list'      → renderList(entity, childIds, entities)
    'metric'    → renderMetric(entity)
    'text'      → renderText(entity)
    'image'     → renderImage(entity)
    default     → renderCard(entity, childIds, entities)
```

**Key principle:** There is no "streaming mode" vs "done mode." The viewer always renders from the current graph state. Whether that state arrived all at once (page load), progressively (WebSocket stream), or as a single delta (direct edit) — same code path.

---

## Component Catalog

Each display type describes a semantic rendering. Viewers implement these for their target platform.

### page

Root container. One per aide.

| Property | Description |
|----------|-------------|
| `title` or `name` | Page heading |
| Children | Rendered sequentially below title |
| Empty state | Prompt to send first message |

### section

Titled grouping. The main structural divider.

| Property | Description |
|----------|-------------|
| `title` or `name` | Section heading |
| Children | Rendered within section |
| Empty state | "No items yet." |

### card

Bordered container showing props as labeled key-value pairs.

| Property | Description |
|----------|-------------|
| `title` or `name` | Card heading |
| All other props | Rendered as "Label: Value" rows |
| Fallback | Used when display hint is unknown or omitted |

Best for: singular important items (ceremony details, venue info).

### table

Structured data with multiple fields. The workhorse component.

| Property | Description |
|----------|-------------|
| Children | Each child is a row |
| Columns | Union of all children's props (excluding `_` prefixed) |
| Empty state | "No items yet." |

Best for: guest lists, food assignments, anything with 3+ fields per item.

**Every cell should be directly editable** in interactive viewers.

### checklist

List with boolean completion state.

| Property | Description |
|----------|-------------|
| Children | Each child is a checklist item |
| Boolean prop | `done` or `checked` on each child |
| Summary | "X of Y complete" |

**Checkbox toggle should be instant** — no LLM round trip.

### list

Vertical list of children.

| Property | Description |
|----------|-------------|
| Children | Rendered as list items |
| Primary field | `name` or `title` displayed prominently |
| Secondary fields | Other props displayed subordinately |

### metric

Single important number with label.

| Property | Description |
|----------|-------------|
| `value` or `count` | The number to display prominently |
| `label` or `name` | Description of what the number represents |

Best for: "38 guests confirmed", "$1,200 remaining".

### text

Freeform paragraph.

| Property | Description |
|----------|-------------|
| `text`, `content`, or `body` | The paragraph content |

Max ~100 words (enforced in system prompt, not renderer).

### image

Image with optional caption.

| Property | Description |
|----------|-------------|
| `src` or `url` | Image URL |
| `caption` or `alt` | Optional description |

---

## Display Hint Inference

When `display` is omitted on `entity.create`, the renderer infers it from entity shape.

**Inference rules (in order):**

| Condition | Inferred Display |
|-----------|-----------------|
| Has `src` or `url` prop | `image` |
| Has `done` or `checked` boolean | `card` |
| Has `value`/`count` with ≤3 props | `metric` |
| Has only `text` prop | `text` |
| Has children with boolean props | `checklist` |
| Has children (default) | `table` |
| No children (default) | `card` |

**Pseudocode:**

```
resolveDisplay(entity, childIds, entities):
  hint = entity.display?.toLowerCase()
  if hint: return hint

  props = entity.props or {}

  if props.src or props.url: return 'image'
  if typeof props.done == 'boolean' or typeof props.checked == 'boolean': return 'card'
  if (props.value !== undefined or props.count !== undefined) and visibleProps <= 3: return 'metric'
  if props.text and visibleProps == 1: return 'text'

  if childIds.length > 0:
    firstChild = entities[childIds[0]]
    if firstChild has done/checked boolean: return 'checklist'
    return 'table'

  return 'card'
```

---

## Helpers

Each viewer implementation needs these utilities:

| Helper | Purpose |
|--------|---------|
| `escapeOutput(str)` | Escape for target format (HTML entities, ANSI codes, etc.) |
| `humanize("traveling_from")` | Convert snake_case to "Traveling From" |
| `getChildren(entities, parentId)` | Get child entity IDs, sorted by `_created_seq` |
| `resolveDisplay(entity, childIds, entities)` | Apply inference rules above |

---

## Viewer Requirements

Each viewer (web, CLI, etc.) must implement:

### Required

1. **Render all 9 display types** with appropriate output for the platform
2. **Handle empty states** gracefully
3. **Apply display hint inference** when `display` is omitted
4. **Escape user content** to prevent injection (HTML, ANSI, etc.)

### Interactive Viewers (Web Editor)

1. **Direct editing** — every value should be editable without LLM round trip
2. **Boolean toggles** — instant, no LLM
3. **Visual feedback** — show streaming state, editable affordances

### Read-Only Viewers (Published Pages, CLI)

1. **Static rendering** — no edit affordances needed
2. **Optimize for output** — minimize payload, maximize readability

---

## Implementation Reference

| Viewer | Implementation | Notes |
|--------|----------------|-------|
| Web (interactive) | `frontend/src/lib/display/render-html.js` | Shadow DOM, direct edit |
| Web (published) | Server-rendered HTML | Static, no JS required |
| CLI | `engine/kernel/cli_renderer.py` | ANSI output |

See [Web Editor Spec](../web/web_editor_spec.md) for web-specific details (Shadow DOM, editing chrome, SPA).
