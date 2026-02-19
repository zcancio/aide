# 04: Display Components

> **Prerequisites:** [01 Data Model](01_data_model.md)
> **Next:** [05 Intelligence Tiers](05_intelligence_tiers.md) · [07 Edge Cases](07_edge_cases.md) (for direct edit and undo behavior)

---

## Architecture

The renderer is a recursive walk of the entity tree. Each entity resolves to a React component based on its `display` hint. The entire renderer is ~9 components, ~385 lines.

```tsx
function AideEntity({ entityId }: { entityId: string }) {
  const entity = useEntity(entityId)
  const childIds = useChildren(entityId)
  const Component = resolveDisplay(entity.display)

  if (entity._removed) return null

  return (
    <Component entity={entity} entityId={entityId}>
      {childIds.map(childId => (
        <AideEntity key={childId} entityId={childId} />
      ))}
    </Component>
  )
}
```

The lookup:

```tsx
const DISPLAY_COMPONENTS = {
  page:      PageDisplay,
  section:   SectionDisplay,
  card:      CardDisplay,
  list:      ListDisplay,
  table:     TableDisplay,
  checklist: ChecklistDisplay,
  metric:    MetricDisplay,
  text:      TextDisplay,
  image:     ImageDisplay,
}

function resolveDisplay(hint?: string) {
  return DISPLAY_COMPONENTS[hint] || FallbackDisplay
}
```

There is no "streaming mode" vs "done mode." The client always renders from the current graph state. Whether that state arrived all at once (page load), progressively (JSONL stream), or as a single delta (direct edit) — same code path.

---

## Shared Contract

Every display component receives:

```tsx
interface DisplayProps {
  entity: Entity       // { id, parent, display, props, _removed, _styles }
  entityId: string
  children?: ReactNode // child AideEntity components, already resolved
}
```

Every display component must:

1. **Render with zero children.** Show placeholder or empty container.
2. **Render with any number of children.**
3. **Support direct editing on every prop value** via `EditableField`.
4. **Respect `_styles` overrides** (highlight, color).
5. **Animate in on mount** (200ms fade-in during streaming).
6. **Never crash on unexpected props.**

---

## EditableField

The foundation of "spreadsheet speed." Every rendered value is clickable to edit inline. This is the most important component in the system — it's what makes AIde a tool instead of a chatbot.

```tsx
function EditableField({ entityId, field, value, type }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const emitUpdate = useEmitUpdate()  // sends entity.update to server

  // Booleans toggle immediately — no edit mode
  if (type === 'boolean') {
    return <input type="checkbox" checked={!!value}
      onChange={() => emitUpdate(entityId, { [field]: !value })} />
  }

  // Display mode: click to edit
  if (!editing) {
    return <span className="editable-field" onClick={() => setEditing(true)}>
      {formatValue(value, type) || <span className="placeholder">—</span>}
    </span>
  }

  // Edit mode: input with commit on blur/enter, cancel on escape
  return <input autoFocus value={draft}
    type={type === 'number' ? 'number' : type === 'date' ? 'date' : 'text'}
    onChange={e => setDraft(e.target.value)}
    onBlur={() => { setEditing(false); if (draft !== value) emitUpdate(entityId, { [field]: coerce(draft, type) }) }}
    onKeyDown={e => {
      if (e.key === 'Enter') e.currentTarget.blur()
      if (e.key === 'Escape') { setDraft(value); setEditing(false) }
    }} />
}
```

**Behaviors:**
- Click → edit mode (tap on mobile)
- Blur or Enter → commit, emits `entity.update`, <200ms round trip
- Escape → cancel
- Booleans toggle immediately
- Dates open date picker
- Empty values show dash placeholder, still clickable

---

## Component Catalog

### PageDisplay

Root container. One per aide.

- Renders: centered max-width container (`720px`), large editable title, children stack vertically
- Empty state: "Say something to get started."

### SectionDisplay

Titled collapsible grouping. The main structural divider.

- Renders: titled block with bottom border, collapse toggle on header
- **Collapsible** via header click — essential for pages with 6+ sections
- Empty state: "No items yet."

### CardDisplay

Bordered card showing props as labeled key-value pairs.

- Renders: bordered container, `title` as header, remaining props as "Label: Value" rows
- Each value editable. `humanize()` converts `traveling_from` → "Traveling From"
- Best for: singular important items (ceremony details, venue info)

### ListDisplay

Vertical list of children.

- Renders: titled list, each child as a list item
- Child rendering: first string prop as primary label, remaining props as secondary metadata tags
- Empty state: "No items yet."

### TableDisplay

The workhorse. Structured data with multiple fields.

- Renders: titled table with column headers derived from the union of all children's props
- **Every cell is directly editable** — click any cell to change the value
- During streaming: headers appear with first row, subsequent rows append. New props on later rows add columns dynamically.
- Empty state: "No items yet."
- Best for: guest lists, food assignments, anything with 3+ fields per item

### ChecklistDisplay

List with checkboxes.

- Renders: list items with checkbox targeting a boolean prop (`done` → `checked` → first boolean found)
- **Checkbox toggle emits `entity.update` directly** — no LLM, instant
- Checked items show strikethrough
- Summary line: "3 of 7 complete"
- Empty state: "No items yet."

### MetricDisplay

Single important number with label.

- Renders: large centered value with smaller label below
- Value is editable
- Best for: "38 guests confirmed", "$1,200 remaining"

### TextDisplay

Freeform paragraph. Welcome messages, notes, descriptions.

- Renders: paragraph of plain text (no markdown in v1)
- Click opens `<textarea>` sized to content. Blur or Ctrl+Enter to save.
- Max ~100 words (enforced in system prompt, not component)

### ImageDisplay

Image from URL with optional caption.

- Renders: image at full width, editable caption below
- No upload in v1 — user pastes URL
- Empty state: "Paste an image URL to display here"

### FallbackDisplay

Catches unknown display hints. **Never crashes.**

- Renders: generic card with key-value pairs, children below
- Appears when: LLM typo, future hint on old client, inference can't determine type

---

## Display Hint Inference

When `display` is omitted on `entity.create`:

| Condition | Inferred Display |
|-----------|-----------------|
| Has `content` prop (string >20 chars) | `text` |
| Has `src` prop | `image` |
| Has `checked`/`done` boolean | parent uses `checklist` |
| Has 4+ props | parent uses `table` |
| Has <4 props | parent uses `list` |
| Is root entity | `page` |

---

## Helpers

```tsx
humanize("traveling_from")          → "Traveling From"
getDisplayableProps(entity.props)    → excludes title, _removed, _styles, _* fields
inferType(value)                     → "string" | "number" | "boolean" | "date"
deriveColumns(children)              → union of all children's prop keys, in first-seen order
formatValue(value, type)             → display string ("✓", formatted date, etc.)
applyStyles(entity._styles)         → React CSSProperties ({ backgroundColor, color, etc. })
```

---

## Mount Animation

All components wrapped in mount animation during streaming:

```css
.aide-mount-animation {
  animation: aide-fade-in 0.2s ease-out;
}
@keyframes aide-fade-in {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0); }
}
```

---

## Size

| Component | ~Lines | Children? | Direct Edit | Empty State |
|-----------|--------|-----------|-------------|-------------|
| PageDisplay | 20 | yes | title | "Say something to get started." |
| SectionDisplay | 25 | yes | title | "No items yet." |
| CardDisplay | 30 | optional | all props | — |
| ListDisplay + item | 40 | yes | all props | "No items yet." |
| TableDisplay | 45 | yes | all cells | "No items yet." |
| ChecklistDisplay + item | 45 | yes | label + checkbox | "No items yet." |
| MetricDisplay | 20 | no | value | — |
| TextDisplay | 15 | no | content | — |
| ImageDisplay | 20 | no | caption, src | placeholder |
| FallbackDisplay | 25 | yes | all props | — |
| EditableField | 40 | — | — | dash |
| Helpers | 60 | — | — | — |
| **Total** | **~385** | | | |
