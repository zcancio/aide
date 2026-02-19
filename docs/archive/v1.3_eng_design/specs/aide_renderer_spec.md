# AIde — Renderer Spec (v1.3)

**Purpose:** The renderer is a pure function that transforms snapshots into output for different channels. For HTML, it produces a complete, self-contained web page. For text, it produces unicode for SMS, terminal, or Slack. No AI, no network calls, no randomness. Deterministic: same input → same output, always.

**Companion docs:** `aide_reducer_spec.md` (what produces the snapshot), `aide_primitive_schemas_spec.md` (what's in the snapshot), `unified_entity_model.md` (v1.3 data model), design system in `docs/aide_design_system.md` (visual rules)

---

## Contract

```python
def render(
    snapshot: AideState,
    blueprint: Blueprint,
    channel: str = "html",           # "html" or "text"
    events: list[Event] | None = None,
    options: RenderOptions | None = None,
) -> str:
    """
    Render snapshot for the specified channel.
    Returns UTF-8 string (HTML or plain text).
    Pure function. No side effects. No IO.
    """
```

```python
@dataclass
class RenderOptions:
    include_events: bool = True       # Embed event log in HTML (ignored for text)
    include_blueprint: bool = True    # Embed blueprint in HTML (ignored for text)
    include_fonts: bool = True        # Link to fonts in HTML (ignored for text)
    footer: str | None = None         # "Made with AIde" for free tier
    base_url: str = "https://toaide.com"
```

### Channels

| Channel | Output | Use Case |
|---------|--------|----------|
| `html` | Full HTML document | Web browser, published pages |
| `text` | Unicode plain text | SMS, Signal, terminal, Slack |

The renderer uses schema templates (`render_html` and `render_text`) to produce channel-appropriate output.

---

## Multi-Channel Rendering

Schemas define templates for each channel:

```json
{
  "GroceryItem": {
    "interface": "interface GroceryItem { name: string; checked: boolean; }",
    "render_html": "<li class=\"item {{#checked}}done{{/checked}}\">{{name}}</li>",
    "render_text": "{{#checked}}✓{{/checked}}{{^checked}}○{{/checked}} {{name}}",
    "styles": ".item { padding: 8px; } .item.done { opacity: 0.5; }"
  }
}
```

When rendering an entity:
1. Look up its schema via `_schema`
2. Select the template for the target channel (`render_html` or `render_text`)
3. Render using Mustache substitution

---

## Mustache Templating

All templates use Mustache syntax (logic-less, safe, no code execution):

```mustache
{{name}}                              <!-- field interpolation -->
{{#checked}}done{{/checked}}          <!-- truthy section -->
{{^checked}}pending{{/checked}}       <!-- falsy section -->
{{>items}}                            <!-- render child collection -->
```

### Available Variables

- All fields from the entity
- `_id` — entity ID
- `_pos` — position value (for sorted display)
- `_index` — computed index after sorting (0-based)

### Child Collection Rendering

`{{>fieldname}}` renders a `Record<string, T>` field:

```json
{
  "GroceryList": {
    "interface": "interface GroceryList { title: string; items: Record<string, GroceryItem>; }",
    "render_html": "<div class=\"list\"><h2>{{title}}</h2><ul>{{>items}}</ul></div>",
    "render_text": "{{title}}\n─────────\n{{>items}}"
  }
}
```

The renderer:
1. Gets children from the specified field
2. Filters out removed children (`_removed: true`)
3. Sorts by `_pos`
4. Renders each child using its schema's template
5. Applies layout per `_view.type` (list, table, grid)

---

## HTML Channel

### Output Structure

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
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond&family=IBM+Plex+Sans&display=swap" rel="stylesheet">

  <!-- Styles: design system + schema styles + style tokens -->
  <style>
  {base CSS}
  {collected schema styles}
  {style token overrides}
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

**No JavaScript.** The rendered page is static HTML + CSS. It works with JS disabled, in email clients, in feed readers.

### CSS Generation

The renderer produces CSS from three sources:

1. **Base CSS** — design system foundation
2. **Schema styles** — `styles` field from each schema used
3. **Token overrides** — `snapshot.styles` mapped to CSS custom properties

```css
/* Base CSS */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--font-sans);
  font-size: 16px;
  color: var(--text-primary);
  background: var(--bg-primary);
}
.aide-page {
  max-width: 720px;
  margin: 0 auto;
  padding: var(--space-12) var(--space-8);
}

/* Schema styles */
.item { padding: 8px; }
.item.done { opacity: 0.5; text-decoration: line-through; }
.list { padding: 16px; }

/* Token overrides */
:root {
  --text-primary: #1a365d;
  --bg-primary: #fffff0;
  --font-sans: 'Inter', sans-serif;
}
```

### Style Token Mapping

| Style token | CSS variable |
|-------------|-------------|
| `primary_color` | `--text-primary` |
| `bg_color` | `--bg-primary` |
| `text_color` | `--text-slate` |
| `font_family` | `--font-sans` |
| `heading_font` | `--font-serif` |
| `density` | Adjusts spacing scale |

---

## Text Channel

Text output is unicode-only, suitable for SMS, terminal, and chat platforms.

### Output Structure

```
{meta.title}
════════════

{rendered entities}

{optional footer}
```

### Text Formatting

Since text has no CSS, the renderer uses unicode characters for visual structure:

| Element | Unicode |
|---------|---------|
| Title underline | `════════════` (double line) |
| Section divider | `────────────` (single line) |
| Checked item | `✓` |
| Unchecked item | `○` |
| Bullet | `•` |
| Nested indent | 2 spaces per level |

### Example Output

```
Weekly Groceries
════════════════

○ Milk
✓ Eggs
○ Bread

────────────
Updated Feb 27
```

---

## Block Rendering

Blocks define page structure. The renderer walks the block tree depth-first and emits output for each block.

### Block Types

| Type | HTML Output | Text Output |
|------|-------------|-------------|
| `heading` | `<h1>`, `<h2>`, `<h3>` | Text + underline |
| `text` | `<p>` | Plain text |
| `metric` | `<div class="metric">` | `Label: Value` |
| `entity_view` | Rendered entity via schema template | Rendered entity via schema template |
| `divider` | `<hr>` | `────────────` |
| `image` | `<figure><img>` | `[Image: {alt}]` |
| `callout` | `<div class="callout">` | `> {content}` |
| `column_list` | `<div class="columns">` | Vertical stack |
| `column` | `<div class="column">` | (no wrapper) |

### entity_view Block

The `entity_view` block renders an entity using its schema template:

```python
def render_entity_view(block, snapshot, channel):
    entity_path = block.props.get("source")
    entity = resolve_path(snapshot.entities, entity_path)

    if not entity or entity.get("_removed"):
        return render_empty(channel)

    schema = snapshot.schemas.get(entity.get("_schema"))
    template_key = f"render_{channel}"  # render_html or render_text
    template = schema.get(template_key, "")

    return mustache_render(template, entity, snapshot, channel)
```

---

## View Layouts

When rendering child collections (`{{>items}}`), the renderer uses `_view.type` to determine layout:

### List Layout

```python
# HTML
<ul class="aide-list">
  {for each child}
  <li>{rendered child}</li>
  {end}
</ul>

# Text
{for each child}
{rendered child}
{end}
```

### Table Layout

```python
# HTML
<table class="aide-table">
  <thead><tr>{field headers}</tr></thead>
  <tbody>{for each child: <tr>{field values}</tr>}</tbody>
</table>

# Text
{field headers, tab-separated}
────────────────────────────
{for each child: field values, tab-separated}
```

### Grid Layout

```python
# HTML
<div class="aide-grid" style="grid-template-columns: repeat({cols}, 1fr)">
  {for each cell}{rendered cell}{end}
</div>

# Text
{for each row}
{cells joined by |}{newline}
{end}
```

---

## Value Formatting

Raw field values are formatted for display based on type:

| Type | Raw | HTML | Text |
|------|-----|------|------|
| `string` | `"Mike"` | Mike | Mike |
| `number` | `9.99` | 9.99 | 9.99 |
| `boolean` | `true` | `<span class="bool-true">✓</span>` | ✓ |
| `boolean` | `false` | `<span class="bool-false">○</span>` | ○ |
| `Date` | `"2026-02-27"` | Feb 27 | Feb 27 |
| `null` | `null` | — (em dash) | — |
| `string[]` | `["a","b"]` | a, b | a, b |

---

## Entity Style Overrides

Entities with `_styles` get visual adjustments in HTML output:

```python
def apply_entity_styles(entity, html_output):
    styles = entity.get("_styles", {})

    classes = []
    if styles.get("highlight"):
        classes.append("aide-highlight")

    inline = []
    if "bg_color" in styles:
        inline.append(f"background-color: {styles['bg_color']}")

    return wrap_with_styles(html_output, classes, inline)
```

For text channel, entity styles are ignored (no styling in plain text).

---

## Sort and Filter

Applied when rendering child collections:

```python
def render_children(children, view_config, snapshot, channel):
    # 1. Filter removed
    visible = [c for c in children.values() if not c.get("_removed")]

    # 2. Apply filter if configured
    if view_config.get("filter"):
        visible = apply_filter(visible, view_config["filter"])

    # 3. Sort by _pos (default) or configured field
    sort_field = view_config.get("sort", {}).get("field", "_pos")
    sort_dir = view_config.get("sort", {}).get("direction", "asc")
    visible = sorted(visible, key=lambda e: e.get(sort_field), reverse=(sort_dir == "desc"))

    # 4. Render each
    return [render_entity(c, snapshot, channel) for c in visible]
```

---

## Empty States

### No entities

```html
<!-- HTML -->
<p class="aide-empty">No items yet.</p>
```

```
<!-- Text -->
(No items)
```

### Missing schema

If an entity's `_schema` doesn't exist in `snapshot.schemas`, render with a fallback:

```html
<!-- HTML -->
<div class="aide-entity">{JSON representation}</div>
```

```
<!-- Text -->
{entity_id}: {field summary}
```

---

## Footer

Free-tier aides include a footer:

```html
<!-- HTML -->
<footer class="aide-footer">
  <a href="https://toaide.com">Made with AIde</a>
  <span>·</span>
  <span>Updated Feb 27</span>
</footer>
```

```
<!-- Text -->

────────────
Made with AIde · Updated Feb 27
```

---

## OG / Meta Tags (HTML only)

For link previews in Signal, iMessage, Slack:

```python
def render_og_tags(snapshot):
    title = snapshot.meta.get("title", "AIde")
    description = derive_description(snapshot)

    return f"""
    <meta property="og:title" content="{escape(title)}">
    <meta property="og:type" content="website">
    <meta property="og:description" content="{escape(description)}">
    """

def derive_description(snapshot):
    # Strategy 1: identity from meta
    if snapshot.meta.get("identity"):
        return snapshot.meta["identity"][:160]

    # Strategy 2: count of top-level entities
    count = len([e for e in snapshot.entities.values() if not e.get("_removed")])
    return f"{count} items"
```

---

## HTML Sanitization

The renderer produces HTML from structured data and Mustache templates. Content is text-escaped before insertion:

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

Mustache templates from schemas are trusted (they come from L3 synthesis), but all entity field values are escaped. This prevents XSS regardless of what data the user provides.

---

## Performance

The renderer is fast by design. It's Mustache template expansion over a tree walk.

**Expected performance:**
- 10-entity aide: < 1ms
- 100-entity aide: < 5ms
- 500-entity aide: < 20ms

**Output sizes:**
- Grocery list (HTML): ~5–10KB
- Poker league (HTML): ~15–25KB
- Text output: typically 10–20% of HTML size

---

## Testing Strategy

**Test categories:**

1. **Block type rendering.** Each block type × both channels.

2. **Schema template rendering.** Mustache interpolation, sections, child collections.

3. **View layouts.** List, table, grid × both channels.

4. **Value formatting.** Every field type with real and null values.

5. **Sort/filter.** Various view configs, verify entity order.

6. **Entity styles.** HTML classes and inline styles applied correctly.

7. **Empty states.** No entities, missing schema.

8. **Cross-channel consistency.** Same snapshot produces semantically equivalent output in both channels.

9. **Determinism.** Same input → identical output, every time.

10. **HTML validity.** Valid HTML5, parseable embedded JSON, no script injection.
