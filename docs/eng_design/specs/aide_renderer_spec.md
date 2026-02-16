# AIde — Renderer Spec

**Purpose:** The renderer is a pure function: `(snapshot, blueprint, events?) → HTML string`. It takes the current state and produces a complete, self-contained HTML file. No AI, no network calls, no randomness. Deterministic: same input → same output, always.

**Companion docs:** `aide_reducer_spec.md` (what produces the snapshot), `aide_primitive_schemas.md` (what's in the snapshot), `aide_architecture.md` (how it fits), design system in `docs/aide_design_system.md` (visual rules)

---

## Contract

```python
def render(
    snapshot: AideState,
    blueprint: Blueprint,
    events: list[Event] | None = None,
    options: RenderOptions | None = None,
) -> str:
    """
    Render a complete HTML file from snapshot state.
    Returns a UTF-8 HTML string.
    Pure function. No side effects. No IO.
    """
```

```python
@dataclass
class RenderOptions:
    include_events: bool = True       # Embed event log in HTML
    include_blueprint: bool = True    # Embed blueprint in HTML
    include_fonts: bool = True        # Link to Google Fonts
    footer: str | None = None         # "Made with AIde" for free tier, None for pro
    base_url: str = "https://toaide.com"
```

```python
@dataclass
class Blueprint:
    identity: str          # "Poker league. 8 players, biweekly Thursday."
    voice: str             # "No first person. State reflections only."
    prompt: str            # Full system prompt for any LLM
```

---

## Output Structure

The renderer produces a single HTML file with this exact structure:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{snapshot.meta.title}</title>

  <!-- OG tags for link previews -->
  <meta property="og:title" content="{snapshot.meta.title}">
  <meta property="og:type" content="website">
  <meta property="og:description" content="{derived description}">

  <!-- Blueprint: identity + voice + prompt -->
  <script type="application/aide-blueprint+json" id="aide-blueprint">
  {blueprint as JSON}
  </script>

  <!-- Snapshot: current structured state -->
  <script type="application/aide+json" id="aide-state">
  {snapshot as JSON, sorted keys}
  </script>

  <!-- Event log: full history (optional) -->
  <script type="application/aide-events+json" id="aide-events">
  {events as JSON array}
  </script>

  <!-- Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=IBM+Plex+Sans:wght@300;400;500&display=swap" rel="stylesheet">

  <!-- Styles: design system + style tokens -->
  <style>
  {rendered CSS}
  </style>
</head>
<body>
  <main class="aide-page">
    {rendered block tree}
  </main>
  {optional footer}
</body>
</html>
```

**No JavaScript.** The rendered page is static HTML + CSS. It works with JS disabled, in email clients, in feed readers, anywhere. The embedded JSON blocks are data — they're invisible to browsers but available to any tool that reads the file.

**Sorted JSON keys.** All embedded JSON uses sorted keys for determinism. Two snapshots with the same content produce identical JSON strings.

---

## CSS Generation

The renderer produces a single `<style>` block that combines the design system base CSS with the aide's style tokens.

### Base CSS (always included)

The design system CSS from `docs/aide_design_system.md` is the foundation. It includes:

- CSS custom properties (colors, fonts, spacing, radii, transitions)
- Typography classes (`.text-h1` through `.text-overline`)
- Layout (`.aide-page` container, responsive max-width)
- Accessibility (reduced motion, minimum contrast)

```css
/* ── Base ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: var(--font-sans);
  font-size: 16px;
  font-weight: 300;
  line-height: 1.65;
  color: var(--text-primary);
  background: var(--bg-primary);
  -webkit-font-smoothing: antialiased;
}

.aide-page {
  max-width: 720px;
  margin: 0 auto;
  padding: var(--space-12) var(--space-8);
}

@media (max-width: 640px) {
  .aide-page {
    padding: var(--space-8) var(--space-5);
  }
}
```

### Style Token Overrides

The renderer maps `snapshot.styles` tokens to CSS custom property overrides:

| Style token | CSS variable |
|-------------|-------------|
| `primary_color` | `--text-primary` |
| `bg_color` | `--bg-primary` |
| `text_color` | `--text-slate` |
| `font_family` | `--font-sans` |
| `heading_font` | `--font-serif` |
| `density` | Adjusts spacing scale (see below) |

**Density mapping:**

| Density | Spacing multiplier | Page padding | Section gap |
|---------|-------------------|--------------|-------------|
| `compact` | 0.75× | `var(--space-8)` | `var(--space-6)` |
| `comfortable` | 1× (default) | `var(--space-12)` | `var(--space-8)` |
| `spacious` | 1.25× | `var(--space-16)` | `var(--space-10)` |

If the aide has custom style tokens, they're emitted as overrides:

```css
:root {
  /* Aide style overrides */
  --text-primary: #1a365d;
  --bg-primary: #fffff0;
  --font-sans: 'Inter', sans-serif;
}
```

---

## Block Rendering

The renderer walks the block tree depth-first, starting from `block_root`, and emits HTML for each block.

```python
def render_block(block_id: str, snapshot: AideState) -> str:
    block = snapshot.blocks[block_id]
    html = BLOCK_RENDERERS[block.type](block, snapshot)
    
    # Render children recursively
    if block.children:
        for child_id in block.children:
            html += render_block(child_id, snapshot)
    
    return html
```

### Block Type → HTML

#### `heading`

```python
# Props: level (1-3), content
# Output:
<h{level} class="aide-heading aide-heading--{level}">{content}</h{level}>
```

```css
.aide-heading { margin-bottom: var(--space-4); }
.aide-heading--1 {
  font-family: var(--font-serif);
  font-size: clamp(32px, 4.5vw, 42px);
  font-weight: 400;
  line-height: 1.2;
  color: var(--text-primary);
}
.aide-heading--2 {
  font-family: var(--font-serif);
  font-size: clamp(24px, 3.5vw, 32px);
  font-weight: 400;
  line-height: 1.25;
  color: var(--text-primary);
}
.aide-heading--3 {
  font-family: var(--font-sans);
  font-size: 18px;
  font-weight: 500;
  line-height: 1.4;
  color: var(--text-primary);
}
```

#### `text`

```python
# Props: content
# Output:
<p class="aide-text">{content}</p>
```

Content supports basic inline formatting: `**bold**` → `<strong>`, `*italic*` → `<em>`, `[link text](url)` → `<a>`. No full Markdown. Just these three.

```css
.aide-text {
  font-family: var(--font-sans);
  font-size: 16px;
  font-weight: 300;
  line-height: 1.65;
  color: var(--text-secondary);
  margin-bottom: var(--space-4);
}
.aide-text a {
  color: var(--accent-steel);
  text-decoration: underline;
  text-decoration-color: var(--border);
  text-underline-offset: 2px;
}
.aide-text a:hover {
  text-decoration-color: var(--accent-steel);
}
```

#### `metric`

```python
# Props: label, value, trend? (optional: "up", "down", "flat")
# Output:
<div class="aide-metric">
  <span class="aide-metric__label">{label}</span>
  <span class="aide-metric__value">{value}</span>
</div>
```

```css
.aide-metric {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  padding: var(--space-3) 0;
}
.aide-metric__label {
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: 400;
  color: var(--text-secondary);
}
.aide-metric__label::after {
  content: ':';
}
.aide-metric__value {
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
}
```

#### `collection_view`

```python
# Props: source (collection ID), view (view ID)
# Output: depends on the view type (see View Rendering below)
```

This is the bridge between structured data and visual output. The renderer looks up the view, gets the collection, and delegates to the appropriate view renderer.

```python
def render_collection_view(block, snapshot):
    view = snapshot.views.get(block.props.get("view"))
    collection = snapshot.collections.get(block.props.get("source"))
    
    if not view or not collection:
        return render_empty_block()
    
    # Get non-removed entities
    entities = [e for e in collection.entities.values() if not e.get("_removed")]
    
    # Apply view config: sort, filter, group
    entities = apply_sort(entities, view.config)
    entities = apply_filter(entities, view.config)
    
    # Delegate to view type renderer
    return VIEW_RENDERERS[view.type](entities, collection.schema, view.config, snapshot.styles)
```

#### `divider`

```python
# Props: none
# Output:
<hr class="aide-divider">
```

```css
.aide-divider {
  border: none;
  border-top: 1px solid var(--border-light);
  margin: var(--space-6) 0;
}
```

#### `image`

```python
# Props: src, alt?, caption?
# Output:
<figure class="aide-image">
  <img src="{src}" alt="{alt}" loading="lazy">
  {if caption: <figcaption class="aide-image__caption">{caption}</figcaption>}
</figure>
```

```css
.aide-image { margin: var(--space-6) 0; }
.aide-image img { max-width: 100%; height: auto; border-radius: var(--radius-sm); }
.aide-image__caption {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-top: var(--space-2);
}
```

#### `callout`

```python
# Props: content, icon?
# Output:
<div class="aide-callout">
  {if icon: <span class="aide-callout__icon">{icon}</span>}
  <span class="aide-callout__content">{content}</span>
</div>
```

```css
.aide-callout {
  background: var(--bg-cream);
  border-left: 3px solid var(--border);
  padding: var(--space-4) var(--space-5);
  margin: var(--space-4) 0;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  font-size: 15px;
  line-height: 1.55;
  color: var(--text-slate);
}
```

#### `column_list`

```python
# Props: none (children are column blocks)
# Output:
<div class="aide-columns">
  {render children}
</div>
```

```css
.aide-columns {
  display: flex;
  gap: var(--space-6);
}
@media (max-width: 640px) {
  .aide-columns {
    flex-direction: column;
  }
}
```

#### `column`

```python
# Props: width? (e.g., "50%", "33%", "200px")
# Output:
<div class="aide-column" style="flex: {derived flex value}">
  {render children}
</div>
```

If `width` is a percentage, `flex: 0 0 {width}`. If omitted, `flex: 1`.

---

## View Rendering

Views determine how a collection's entities appear inside a `collection_view` block. Each view type has its own renderer.

### `list` view

The default. Simple vertical list of entities.

```python
# Output:
<ul class="aide-list">
  {for each entity:}
  <li class="aide-list__item {entity._styles classes}">
    {for each visible field:}
    <span class="aide-list__field aide-list__field--{field_name}">{value}</span>
    {end}
  </li>
  {end}
</ul>
```

**Field visibility:** If `show_fields` is set, show only those fields in that order. If `hide_fields` is set, show all fields except those. If neither, show all non-internal fields (skip fields starting with `_`).

**Primary field:** The first visible field renders with `.aide-list__field--primary` (stronger weight). Remaining fields render lighter.

```css
.aide-list {
  list-style: none;
  padding: 0;
}
.aide-list__item {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--border-light);
  font-size: 15px;
  line-height: 1.5;
}
.aide-list__item:last-child { border-bottom: none; }
.aide-list__field--primary {
  font-weight: 500;
  color: var(--text-primary);
}
.aide-list__field {
  color: var(--text-secondary);
}
/* Boolean fields render as checkmarks */
.aide-list__field--bool::before {
  content: '✓';
  color: var(--accent-forest);
  margin-right: var(--space-1);
}
.aide-list__field--bool-false::before {
  content: '○';
  color: var(--text-tertiary);
  margin-right: var(--space-1);
}
```

### `table` view

Tabular data with headers.

```python
# Output:
<div class="aide-table-wrap">
  <table class="aide-table">
    <thead>
      <tr>
        {for each visible field:}
        <th class="aide-table__th">{field display name}</th>
        {end}
      </tr>
    </thead>
    <tbody>
      {for each entity:}
      <tr class="aide-table__row {entity._styles classes}">
        {for each visible field:}
        <td class="aide-table__td aide-table__td--{field_type}">{formatted value}</td>
        {end}
      </tr>
      {end}
    </tbody>
  </table>
</div>
```

**Field display names:** Convert snake_case to Title Case. `requested_by` → "Requested By". `checked` → "Checked".

```css
.aide-table-wrap {
  overflow-x: auto;
  margin: var(--space-4) 0;
}
.aide-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 15px;
}
.aide-table__th {
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-tertiary);
  text-align: left;
  padding: var(--space-2) var(--space-3);
  border-bottom: 2px solid var(--border);
}
.aide-table__td {
  padding: var(--space-3);
  border-bottom: 1px solid var(--border-light);
  color: var(--text-slate);
  vertical-align: top;
}
.aide-table__td--bool { text-align: center; }
.aide-table__td--int,
.aide-table__td--float { text-align: right; font-variant-numeric: tabular-nums; }
```

### `grid` view

For structured grids (Super Bowl squares, seating charts, etc.).

```python
# Config: row_labels, col_labels, show_fields
# Output:
<div class="aide-grid-wrap">
  <table class="aide-grid">
    <thead>
      <tr>
        <th></th>
        {for each col_label:}
        <th class="aide-grid__col-label">{label}</th>
        {end}
      </tr>
    </thead>
    <tbody>
      {for each row_label:}
      <tr>
        <th class="aide-grid__row-label">{row_label}</th>
        {for each col_label:}
        <td class="aide-grid__cell {state classes}">{cell content}</td>
        {end}
      </tr>
      {end}
    </tbody>
  </table>
</div>
```

Grid cells map entities by position (e.g., entity with `position: "A3"` maps to row A, col 3). Empty cells render as available.

```css
.aide-grid {
  border-collapse: collapse;
  font-size: 13px;
}
.aide-grid__col-label,
.aide-grid__row-label {
  font-weight: 500;
  color: var(--text-tertiary);
  padding: var(--space-2);
  text-align: center;
}
.aide-grid__cell {
  border: 1px solid var(--border-light);
  padding: var(--space-2);
  text-align: center;
  min-width: 48px;
  min-height: 48px;
  vertical-align: middle;
}
.aide-grid__cell--filled {
  background: var(--bg-cream);
  color: var(--text-primary);
  font-weight: 500;
}
.aide-grid__cell--empty {
  color: var(--text-tertiary);
}
```

### Future view types (not in v1)

| View type | Renders as | When needed |
|-----------|-----------|-------------|
| `calendar` | Monthly grid with events on dates | Trip itineraries, schedules |
| `kanban` | Column-based board grouped by status field | Task tracking, workflows |
| `dashboard` | Metric cards + summary stats | QBR pages, budget overviews |

These are synthesized by L3 as ViewPresets when requested. The renderer needs the corresponding renderer function before they work. For v1, unknown view types fall back to `table`.

---

## Value Formatting

Raw field values are formatted for display based on their schema type.

| Schema type | Raw value | Rendered |
|-------------|-----------|----------|
| `string` | `"Mike"` | Mike |
| `int` | `20` | 20 |
| `float` | `9.99` | 9.99 |
| `bool` | `true` | ✓ (with CSS class) |
| `bool` | `false` | ○ (with CSS class) |
| `date` | `"2026-02-27"` | Feb 27 |
| `datetime` | `"2026-02-27T19:00:00Z"` | Feb 27, 7:00 PM |
| `enum` | `"produce"` | Produce (title case) |
| `list` | `["milk","eggs"]` | milk, eggs |
| `null` | `null` | — (em dash) |
| `string?` | `null` | — |

Date formatting uses the aide's locale if set in meta, otherwise defaults to `en-US` short format.

---

## Entity Style Overrides

Entities with `_styles` get inline style adjustments or CSS classes.

```python
def entity_classes(entity):
    classes = []
    styles = entity.get("_styles", {})
    if styles.get("highlight"):
        classes.append("aide-highlight")
    return " ".join(classes)

def entity_inline_style(entity):
    styles = entity.get("_styles", {})
    parts = []
    if "bg_color" in styles:
        parts.append(f"background-color: {styles['bg_color']}")
    if "text_color" in styles:
        parts.append(f"color: {styles['text_color']}")
    return "; ".join(parts)
```

```css
.aide-highlight {
  background-color: rgba(31, 42, 68, 0.04);
}
```

---

## Sorting and Filtering

Applied before rendering when a view has `sort_by`, `filter`, or `group_by` config.

### Sort

```python
def apply_sort(entities, config):
    sort_by = config.get("sort_by")
    if not sort_by:
        return entities  # preserve insertion order
    
    order = config.get("sort_order", "asc")
    reverse = order == "desc"
    
    return sorted(entities, key=lambda e: sort_key(e.get(sort_by)), reverse=reverse)

def sort_key(value):
    if value is None:
        return (1, "")   # nulls sort last
    if isinstance(value, bool):
        return (0, int(value))
    return (0, value)
```

### Filter

```python
def apply_filter(entities, config):
    filt = config.get("filter")
    if not filt:
        return entities
    
    return [e for e in entities if all(
        e.get(field) == value for field, value in filt.items()
    )]
```

### Group By

```python
def apply_group(entities, config, schema):
    group_by = config.get("group_by")
    if not group_by:
        return {"_ungrouped": entities}
    
    groups = {}
    for entity in entities:
        key = entity.get(group_by) or "_none"
        groups.setdefault(key, []).append(entity)
    return groups
```

When grouped, each group renders with a group header:

```html
<div class="aide-group">
  <h4 class="aide-group__header">{group name}</h4>
  {rendered entities}
</div>
```

```css
.aide-group { margin-bottom: var(--space-6); }
.aide-group__header {
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-tertiary);
  margin-bottom: var(--space-3);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--border-light);
}
```

---

## Annotations Rendering

If `snapshot.annotations` is non-empty and there's no explicit block for it, the renderer appends an annotations section after the last block.

```html
<section class="aide-annotations">
  <h3 class="aide-heading aide-heading--3">Notes</h3>
  {for each annotation, most recent first:}
  <div class="aide-annotation {if pinned: aide-annotation--pinned}">
    <span class="aide-annotation__text">{note}</span>
    <span class="aide-annotation__meta">{formatted timestamp}</span>
  </div>
  {end}
</section>
```

```css
.aide-annotations { margin-top: var(--space-10); }
.aide-annotation {
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--border-light);
}
.aide-annotation:last-child { border-bottom: none; }
.aide-annotation__text {
  font-size: 15px;
  color: var(--text-slate);
  line-height: 1.5;
}
.aide-annotation__meta {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-left: var(--space-3);
}
.aide-annotation--pinned {
  border-left: 3px solid var(--accent-navy);
  padding-left: var(--space-4);
}
```

---

## Footer

Free-tier aides include a footer. Pro aides don't.

```html
<footer class="aide-footer">
  <a href="https://toaide.com" class="aide-footer__link">Made with AIde</a>
  <span class="aide-footer__sep">·</span>
  <span class="aide-footer__updated">Updated {formatted date}</span>
</footer>
```

```css
.aide-footer {
  margin-top: var(--space-16);
  padding-top: var(--space-6);
  border-top: 1px solid var(--border-light);
  font-size: 12px;
  color: var(--text-tertiary);
  text-align: center;
}
.aide-footer__link {
  color: var(--text-tertiary);
  text-decoration: none;
}
.aide-footer__link:hover {
  color: var(--text-secondary);
}
.aide-footer__sep { margin: 0 var(--space-2); }
```

---

## OG / Meta Tags

For link previews in Signal, iMessage, Slack, etc.

```python
def render_og_tags(snapshot):
    title = snapshot.meta.get("title", "AIde")
    
    # Derive description from first text block or first collection summary
    description = derive_description(snapshot)
    
    return f"""
    <meta property="og:title" content="{escape(title)}">
    <meta property="og:type" content="website">
    <meta property="og:description" content="{escape(description)}">
    <meta name="description" content="{escape(description)}">
    """

def derive_description(snapshot):
    # Strategy 1: first text block's content
    for block_id in snapshot.blocks["block_root"]["children"]:
        block = snapshot.blocks[block_id]
        if block["type"] == "text":
            return block["props"]["content"][:160]
    
    # Strategy 2: collection summary
    for coll in snapshot.collections.values():
        if coll.get("_removed"):
            continue
        count = len([e for e in coll["entities"].values() if not e.get("_removed")])
        return f"{coll.get('name', coll['id'])}: {count} items"
    
    # Strategy 3: just the title
    return snapshot.meta.get("title", "A living page")
```

---

## Empty States

### No blocks (only block_root with empty children)

```html
<main class="aide-page">
  <p class="aide-empty">This page is empty.</p>
</main>
```

```css
.aide-empty {
  color: var(--text-tertiary);
  font-size: 15px;
  padding: var(--space-16) 0;
  text-align: center;
}
```

### Empty collection (view exists but collection has no non-removed entities)

```html
<p class="aide-collection-empty">No items yet.</p>
```

### Missing view (block references a view that doesn't exist)

Fall back to a default table view of the collection. If the collection also doesn't exist, render nothing.

---

## HTML Sanitization

The renderer produces HTML from structured data, not from user-provided HTML strings. This means XSS is not possible by default — content fields are text-escaped before insertion.

```python
def escape(text: str) -> str:
    """HTML-escape user content."""
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;"))
```

The only exception is inline formatting (`**bold**`, `*italic*`, `[link](url)`) in `text` blocks, which is parsed with a strict allowlist:

- `<strong>` from `**...**`
- `<em>` from `*...*`
- `<a href="...">` from `[...](...)` — href is validated as http/https only

No other HTML passes through. No `<script>`, no `<iframe>`, no event handlers.

---

## Performance

The renderer is fast by design. It's string concatenation over a tree walk.

**Expected performance:**
- 10-block aide (grocery list): < 1ms
- 50-block aide with 200 entities (wedding seating): < 5ms
- 100-block aide with 500 entities (extreme): < 20ms

**Output sizes:**
- Grocery list: ~5–10KB HTML
- Poker league: ~15–25KB HTML
- Wedding with 200 guests: ~40–80KB HTML
- Including embedded JSON: add snapshot + events size (see `aide_architecture.md` for size budget)

---

## Testing Strategy

The renderer is the second-most testable component after the reducer. Pure function, deterministic, no IO.

**Test categories:**

1. **Block type rendering.** One test per block type. Feed a snapshot with a single block, verify correct HTML output.

2. **View type rendering.** One test per view type × realistic data. Grocery list in list view, schedule in table view, squares in grid view.

3. **Style token application.** Change `primary_color`, verify CSS override appears. Change `density`, verify spacing changes.

4. **Entity style overrides.** Highlight an entity, verify CSS class and inline style appear in output.

5. **Sort/filter/group.** Create a collection with 10 entities, apply various view configs, verify entity order in output.

6. **Value formatting.** Every field type with real and null values. Dates, bools, enums, lists.

7. **Inline formatting.** Bold, italic, link in text blocks. Verify HTML output. Also verify XSS attempts are escaped.

8. **Empty states.** No blocks, empty collection, missing view.

9. **Full round-trip.** Build a realistic grocery list snapshot by hand, render, open in browser, verify it looks right. This is a visual test — screenshot comparison or manual review.

10. **Determinism.** Render the same snapshot 100 times, verify identical output every time.

11. **File structure.** Verify output is valid HTML5 (doctype, head, body, proper nesting). Verify embedded JSON is parseable. Verify blueprint, state, and events are all present when options say to include them.
