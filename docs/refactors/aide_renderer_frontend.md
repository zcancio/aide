# aide — Renderer Frontend Instructions

**For:** Claude Code implementation of the aide page renderer — the React component tree that turns entity state into interactive HTML.

**Reference mockup:** `aide_compact.html` (dark mode compact variant — the current target fidelity)

---

## Architecture

The renderer is a **pure function from entity state → component tree**. There is no router, no global store, no build step for published pages. The entity map is the single source of truth.

### Entity Map

All state lives in a flat `Record<string, Entity>`:

```typescript
type Entity = {
  display?: string       // explicit display hint: "section" | "table" | "checklist" | "metric" | "text" | "card"
  parent: string         // parent entity ID, or "root" for top-level
  props: Record<string, any>  // arbitrary key-value pairs
}
```

Children are derived by filtering on `parent`. There is no `children` array — the tree is implicit.

### Resolution Order

Every entity resolves to a display component. Resolution is a pure function:

```
1. Explicit display hint → use that component
2. Heuristic detection:
   a. Has `value` or `count` prop, ≤3 display props → Metric
   b. Has `text` prop, ≤1 display prop → Text
   c. Has children where first child has `done` or `checked` boolean → Checklist
   d. Has children with 2+ shared fields → Table (auto-promotion)
   e. Fallback → Card
3. Section-level auto-table promotion (see below)
```

### Auto-Table Promotion

**This is critical.** When a Section's direct children are all untyped entities that share ≥2 fields, skip individual Card rendering and render one Table for the group. This eliminates the biggest source of visual bloat.

Detection logic (runs in the Section component):

```javascript
function shouldAutoTable(childIds, entities) {
  if (childIds.length < 2) return false
  const fieldSets = childIds.map(id => {
    const e = entities[id]
    if (!e || e.display) return null           // skip explicit display hints
    const p = e.props || {}
    if (typeof p.done === "boolean") return null // skip checklist items
    const fields = Object.keys(p).filter(k => !k.startsWith("_"))
    return fields.length >= 2 ? new Set(fields) : null
  })
  if (fieldSets.some(s => s === null)) return false
  const first = fieldSets[0]
  const shared = [...first].filter(f => fieldSets.every(s => s.has(f)))
  return shared.length >= 2
}
```

If `shouldAutoTable` returns true, the Section renders `<AutoTable childIds={...} />` instead of mapping children to individual `<AideEntity>` components.

---

## Components

### Section

- **No collapse affordance.** Sections are always expanded. No arrow, no toggle.
- Playfair Display, 20px, weight 700, primary text color
- `marginBottom: 14px`, content starts `marginTop: 6px` after header
- Registers itself with the scroll tracking system for sticky pill display

### Table (and AutoTable)

- Sortable column headers — click to sort asc, click again for desc
- Header row: 11px uppercase, 600 weight, `letter-spacing: 0.08em`, tertiary color
- Active sort column: header text switches to primary color, arrow (▲/▼) full opacity
- Inactive columns: faint ▲ arrow at 0.3 opacity
- Data rows: 14px, secondary text color
- Numeric values: `text-align: right`, `font-variant-numeric: tabular-nums`
- Row borders: light border color, header border slightly stronger
- Sort is client-side, locale-aware with `{ numeric: true, sensitivity: "base" }`

```javascript
// Shared hook used by both Table and AutoTable
function useSortedRows(childIds, entities) {
  const [sortCol, setSortCol] = useState(null)
  const [sortDir, setSortDir] = useState("asc")
  const onSort = useCallback((col) => {
    if (sortCol === col) setSortDir(d => d === "asc" ? "desc" : "asc")
    else { setSortCol(col); setSortDir("asc") }
  }, [sortCol])
  const sorted = useMemo(() => {
    if (!sortCol) return childIds
    return [...childIds].sort((a, b) => {
      const av = entities[a]?.props?.[sortCol]
      const bv = entities[b]?.props?.[sortCol]
      if (av == null && bv == null) return 0
      if (av == null) return 1; if (bv == null) return -1
      let cmp = typeof av === "number" && typeof bv === "number"
        ? av - bv
        : String(av).localeCompare(String(bv), undefined, { numeric: true, sensitivity: "base" })
      return sortDir === "asc" ? cmp : -cmp
    })
  }, [childIds, entities, sortCol, sortDir])
  return { sorted, sortCol, sortDir, onSort }
}
```

### Checklist

- Title: 14px, 600 weight, primary text color
- Items: 14px, 500 weight. Checked items get tertiary color + `line-through`
- Checkbox: 15px, `accent-color` set to sage
- Row spacing: 5px vertical padding, light border between items
- Counter: `{done}/{total}` in 12px tertiary text below items

### Metric

- **Inline layout.** Metrics use `display: inline-flex` so multiple metrics in the same section flow side-by-side (not stacked).
- Format: `{label}: {value}` — label in 14px secondary, value in 14px 600 weight primary
- `margin-right: 16px` between adjacent metrics

### Text

- 15px body, `line-height: 1.55`, secondary text color
- `marginBottom: 8px`

### Card (fallback)

- Background: card color, 1px border, 8px radius, `padding: 10px 12px`
- Title (from `props.title` or `props.name`): 14px, 600 weight
- Key-value rows: label in 12px tertiary uppercase, value in 14px primary, light border between rows
- Cards should be rare — auto-table promotion catches most cases

---

## Display Prop Filtering

Two props are excluded from display columns/key-value rendering:

- `title` — used for component header, not a data column
- `name` — used for component header when `title` absent
- Any prop starting with `_` — internal metadata

```javascript
function displayProps(props) {
  const skip = new Set(["title", "name"])
  return Object.fromEntries(
    Object.entries(props || {}).filter(([k]) => !k.startsWith("_") && !skip.has(k))
  )
}
```

Column detection for tables unions all children's prop keys (excluding `_`-prefixed).

---

## Page Chrome

### Nav Bar

- Fixed top, 44px height, z-index 200
- Frosted glass: `backdrop-filter: blur(14px)`, semi-transparent background, bottom border
- **Left:** Back button (← arrow + "Back" label), 14px, secondary color, hover → primary
- **Center:** Page title, 14px 600 weight, absolutely centered (`left: 50%, transform: translateX(-50%)`), truncates with ellipsis at 55% max-width
- **Right:** Share button (upload arrow + "Share" label), 14px, secondary color, hover → elevated background

### Sticky Section Pill

As the user scrolls past a section header, a pill appears centered below the nav bar showing the current section name.

- Appears when section header scrolls above nav threshold AND section bottom is still visible
- Disappears when scrolling back above all sections or past the section bottom
- Container: `position: fixed`, `top: NAV_H + 6`, full-width flex centering (`left: 0, right: 0, justify-content: center`) — **do NOT use `left: 50%` + `translateX(-50%)` as it misaligns with the scrollbar**
- `pointer-events: none` on container, `pointer-events: auto` on pill itself
- Pill: frosted glass background, 1px strong border, `border-radius: 999px`, `padding: 3px 14px`, 13px 600 weight
- Entrance animation: `translateY(-6px) → 0` with opacity, 0.15s ease-out

**Scroll tracking implementation:**

- Sections register via Context (`SectionRegistry`) providing their entity ID, title, and DOM ref
- Single `scroll` event listener with `requestAnimationFrame` throttling
- For each registered section, check `getBoundingClientRect()`:
  - `rect.top < threshold` (section header scrolled past nav) AND `rect.bottom > threshold + 24` (section still visible)
  - Last matching section wins (handles overlapping regions)
- Only update state when active section changes (compare with ref to avoid re-renders)

### Pencil FAB (Chat Input)

- **Closed state:** Fixed `bottom: 22px, right: 22px`, 56px circle, sage background, white pencil icon (24px)
  - Hover: darker sage, `scale(1.06)`, stronger shadow
  - `z-index: 50`

- **Open state:** FAB disappears, input bar slides up from bottom
  - Transparent backdrop (click to dismiss)
  - Input bar: card background, 14px radius, `max-width: 480px`, centered horizontally
  - Auto-focused textarea, 15px DM Sans, auto-grows to 100px max
  - Send button: 34px circle on right. Muted elevated color when empty, sage when has text
  - **Keyboard:** Enter sends + closes, Shift+Enter newline, Escape closes
  - Entrance: `slideUp` animation, 0.15s ease-out

### Footer

- `marginTop: 48px`, `paddingTop: 12px`, top border
- "Made with aide" — 12px tertiary text, centered
- Omitted for Pro tier

---

## Design Tokens

### Light Mode

```
Background:       #F7F5F2 (body)  →  #FFFFFF (cards/elevated)
Text primary:     #2D2D2A
Text secondary:   #6B6963
Text tertiary:    #A8A5A0
Border subtle:    #E0DDD8
Border default:   #D4D1CC
Border strong:    #A8A5A0
Sage accent:      #7C8C6E  (hover: #667358)
```

### Dark Mode

```
Background:       #1A1A18 (body)  →  #242422 (cards)  →  #2D2D2A (elevated)
Text primary:     #E6E3DF
Text secondary:   #A8A5A0
Text tertiary:    #6B6963
Border light:     #2F2F2B
Border default:   #3A3A36
Border strong:    #4A4A44
Sage accent:      #7C8C6E  (hover: #8FA07E — goes LIGHTER in dark mode)
Nav glass:        rgba(26, 26, 24, 0.9)
Pill glass:       rgba(36, 36, 34, 0.94)
```

### Typography

| Level | Font | Size | Weight |
|-------|------|------|--------|
| Page title | Playfair Display | 28px | 700 |
| Section heading | Playfair Display | 20px | 700 |
| Subsection / card title | Instrument Sans | 14px | 600 |
| Body text | DM Sans | 15px | 400 |
| Table/list content | DM Sans | 14px | 400–500 |
| Table headers | DM Sans | 11px | 600 (uppercase, 0.08em tracking) |
| Labels/captions | DM Sans | 12px | 400–500 |
| Nav/pill | DM Sans | 13–14px | 500–600 |

### Google Fonts Link

```html
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Instrument+Sans:wght@400;500;600;700&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap" rel="stylesheet">
```

### Font Stacks

```css
--font-serif: 'Playfair Display', Georgia, serif;
--font-heading: 'Instrument Sans', -apple-system, BlinkMacSystemFont, sans-serif;
--font-sans: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
```

---

## Layout

- `max-width: 520px` (compact) or `720px` (comfortable), centered
- Page padding: `20px` (compact) or `40px` (comfortable)
- Content top padding = nav bar height (44px)
- Section bottom margin: 14px
- Table row padding: `5px 8px`
- Card padding: `10px 12px`, margin-bottom 8px

---

## Interactions

All interactions are client-side, no server round-trip:

| Interaction | Behavior |
|------------|----------|
| Sort column | Click header → sort asc, click again → desc, click different column → reset to asc |
| Checkbox toggle | Toggle `done` state in local React state (does not mutate entity map) |
| FAB open | Pencil button → input bar with backdrop |
| FAB close | Enter (with text), Escape, backdrop click |
| Scroll pill | Tracks current section via IntersectionObserver-style rect checks |

---

## What NOT to Build

- **No collapse/expand on sections.** Sections are always open.
- **No drag-and-drop.** Entity order is determined by the entity map.
- **No inline editing.** All edits go through the FAB chat input → AI → event pipeline.
- **No client-side routing.** Each aide is one page.
- **No JavaScript in published pages.** Published pages are static HTML+CSS. The React renderer is for the editor preview only. Published pages get the same visual output as server-rendered HTML from the Python/JS engine.

---

## File Map

| File | Purpose |
|------|---------|
| `engine.py` | Python renderer — produces static HTML string from snapshot |
| `engine.ts` | TypeScript renderer — same logic, for Node/edge |
| `engine.js` | Browser-compatible JS renderer — runs in Claude surfaces |
| `frontend/` | Editor UI — React app that wraps the renderer with nav, FAB, scroll tracking |
| `aide_compact.html` | Reference mockup — dark mode compact with all components demonstrated |
| `aide_preview.html` | Reference mockup — light mode comfortable with all components |
| `aide_preview_dark.html` | Reference mockup — dark mode comfortable |

---

## Testing

### Visual Regression

Each component should render identically across the three engine implementations (Python, TypeScript, JS). The test fixture is the poker league entity map from the mockups.

### Component Resolution

Test the heuristic chain with edge cases:
- Entity with `display: "table"` but no children → Card fallback
- Entity with `value` prop + 4 other props → Card (not Metric — too many props)
- Section with 3 children, 2 share fields, 1 doesn't → no auto-table (all must qualify)
- Section with 2 children sharing 1 field → no auto-table (need ≥2 shared fields)
- Section with 2 children sharing 3 fields → auto-table
- Section with children that have explicit `display` → no auto-table (skip typed entities)

### Sort

- Numeric sort: `[8, 6, 5, 4, 3]` → asc `[3, 4, 5, 6, 8]`
- String sort with numbers: `["Feb 27", "Mar 6", "Mar 13"]` → natural order via `{ numeric: true }`
- Null handling: nulls sort to end regardless of direction
- Mixed types: string comparison as fallback
