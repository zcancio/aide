"""
AIde Kernel — Renderer (v3 Unified Entity Model)

Pure function: (snapshot, blueprint, events?, options?) → HTML string (or text string)
No AI. No IO. Deterministic: same input → same output, always.

v3 key changes:
- Multi-channel: render_html for web, render_text for SMS/terminal/Slack
- Mustache templates in schemas with {{>fieldname}} for child collections
- Schema styles collected into CSS
- Grid rendering via _shape detection and CSS grid layout
- Entities rendered using their schema's render_html/render_text template

Reference: docs/eng_design/unified_entity_model.md, aide_renderer_spec.md
"""

from __future__ import annotations

import json
import re
from html import escape as _html_escape
from typing import Any

import chevron

from engine.kernel.ts_parser import parse_interface_cached
from engine.kernel.types import (
    Blueprint,
    Event,
    RenderOptions,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render(
    snapshot: dict[str, Any],
    blueprint: Blueprint,
    events: list[Event] | None = None,
    options: RenderOptions | None = None,
) -> str:
    """
    Render a complete HTML file from snapshot state.
    Returns a UTF-8 HTML string.
    Pure function. No side effects. No IO.
    """
    opts = options or RenderOptions()
    events = events or []

    if opts.channel == "text":
        return _render_text(snapshot, blueprint, opts)

    return _render_html(snapshot, blueprint, events, opts)


def render_block(block_id: str, snapshot: dict[str, Any]) -> str:
    """
    Render a single block and its children recursively.
    Returns an HTML fragment string.
    Pure function. No side effects. No IO.
    """
    return _render_block(block_id, snapshot)


def render_entity(
    entity_path: str,
    snapshot: dict[str, Any],
    channel: str = "html",
) -> str:
    """
    Render an entity or nested field using its schema template.
    Supports paths like "chessboard" (top-level) or "chessboard/squares" (nested field).
    Returns an HTML or text fragment.
    Pure function. No side effects. No IO.
    """
    # Parse path: entity_id or entity_id/field_name
    parts = entity_path.split("/")
    entity_id = parts[0]

    entity = snapshot.get("entities", {}).get(entity_id)
    if entity is None or entity.get("_removed"):
        return ""

    # If path has more parts, navigate to the nested field
    if len(parts) > 1:
        field_name = parts[1]
        field_value = entity.get(field_name)
        if field_value is None:
            return ""

        # Try to infer child schema from parent's schema interface
        # e.g., "squares: Record<string, Square>" -> child schema is "square"
        parent_schema_id = entity.get("_schema", "")
        child_schema_id = _infer_child_schema(parent_schema_id, field_name, snapshot)

        # If field is a Record with _shape, render as grid
        if isinstance(field_value, dict) and "_shape" in field_value:
            return _render_grid_collection(field_value, field_value["_shape"], snapshot, channel, child_schema_id)
        # Otherwise render as child collection
        if isinstance(field_value, dict):
            return _render_child_collection(field_value, field_name, snapshot, channel, child_schema_id)
        return ""

    # Top-level entity rendering
    schema_id = entity.get("_schema", "")
    schema = snapshot.get("schemas", {}).get(schema_id, {})

    if channel == "text":
        template = schema.get("render_text", "")
    else:
        template = schema.get("render_html", "")

    if not template:
        return _default_entity_html(entity_id, entity, snapshot, channel)

    return _render_entity_with_template(entity_id, entity, template, snapshot, channel, schema_id)


def _infer_child_schema(parent_schema_id: str, field_name: str, snapshot: dict[str, Any]) -> str | None:
    """
    Infer the child schema ID from a parent schema's interface.

    Given a parent schema with interface like:
        interface Chessboard { squares: Record<string, Square>; }

    And field_name "squares", returns "square" (lowercase of "Square").

    Returns None if unable to infer.
    """
    if not parent_schema_id:
        return None

    parent_schema = snapshot.get("schemas", {}).get(parent_schema_id, {})
    interface_src = parent_schema.get("interface", "")
    if not interface_src:
        return None

    # Parse interface to get field types
    iface = parse_interface_cached(interface_src)
    if iface is None:
        return None

    field_info = iface.fields.get(field_name)
    if not field_info:
        return None

    # field_info.ts_type might be "Record<string, Square>" or similar
    # Extract the value type from Record<K, V>
    type_str = field_info.ts_type
    match = re.search(r"Record<[^,]+,\s*(\w+)>", type_str)
    if match:
        child_type = match.group(1)
        # Convert to snake_case and check if schema exists
        child_schema_id = child_type.lower()
        if child_schema_id in snapshot.get("schemas", {}):
            return child_schema_id
        # Try snake_case conversion for PascalCase
        # e.g., GroceryItem -> grocery_item
        snake_case_id = re.sub(r"(?<!^)(?=[A-Z])", "_", child_type).lower()
        if snake_case_id in snapshot.get("schemas", {}):
            return snake_case_id

    return None


# ---------------------------------------------------------------------------
# HTML rendering (primary channel)
# ---------------------------------------------------------------------------

BASE_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--font-body);
  background: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.6;
}
.aide-page {
  max-width: 720px;
  margin: 0 auto;
  padding: 32px 24px;
}
@media (max-width: 640px) {
  .aide-page { padding: 20px 16px; }
}
h1, h2, h3 {
  font-family: var(--font-heading);
  font-weight: 500;
  line-height: 1.2;
  margin-bottom: 8px;
}
h1 { font-size: 2rem; }
h2 { font-size: 1.5rem; }
h3 { font-size: 1.2rem; }
p { margin-bottom: 8px; }
.aide-empty { color: #888; font-style: italic; }
.aide-footer {
  margin-top: 48px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
  font-size: 12px;
  color: #aaa;
  text-align: center;
}
.aide-annotations { margin-top: 32px; }
.aide-annotation {
  padding: 12px;
  border-left: 3px solid var(--accent);
  margin-bottom: 8px;
  font-size: 14px;
}
.aide-annotation-time { font-size: 11px; color: #888; margin-top: 4px; }
/* Grid layout for _shape-based collections */
.aide-grid {
  display: grid;
  gap: 2px;
}
.aide-grid-cell {
  border: 1px solid var(--border);
  padding: 4px;
  text-align: center;
  font-size: 13px;
}
.aide-grid-header {
  font-weight: 600;
  background: var(--bg-secondary, #f0f0f0);
}
"""


def _render_html(
    snapshot: dict[str, Any],
    blueprint: Blueprint,
    events: list[Event],
    opts: RenderOptions,
) -> str:
    parts: list[str] = []

    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="en">')
    parts.append("<head>")
    parts.append('  <meta charset="utf-8">')
    parts.append('  <meta name="viewport" content="width=device-width, initial-scale=1">')

    # Title
    title = escape(snapshot.get("meta", {}).get("title", "AIde"))
    parts.append(f"  <title>{title}</title>")

    # OG tags
    parts.append(_render_og_tags(snapshot, opts))

    # Blueprint JSON
    if opts.include_blueprint:
        bp_json = json.dumps(blueprint.to_dict(), sort_keys=True, ensure_ascii=False)
        parts.append('  <script type="application/aide-blueprint+json" id="aide-blueprint">')
        parts.append(f"  {bp_json}")
        parts.append("  </script>")

    # Snapshot JSON
    snap_json = json.dumps(snapshot, sort_keys=True, ensure_ascii=False)
    parts.append('  <script type="application/aide+json" id="aide-state">')
    parts.append(f"  {snap_json}")
    parts.append("  </script>")

    # Events JSON
    if opts.include_events and events:
        events_json = json.dumps([e.to_dict() for e in events], sort_keys=True, ensure_ascii=False)
        parts.append('  <script type="application/aide-events+json" id="aide-events">')
        parts.append(f"  {events_json}")
        parts.append("  </script>")

    # Fonts
    if opts.include_fonts:
        parts.append('  <link rel="preconnect" href="https://fonts.googleapis.com">')
        parts.append('  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>')
        parts.append(
            '  <link href="https://fonts.googleapis.com/css2?'
            "family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400"
            '&family=IBM+Plex+Sans:wght@300;400;500&display=swap" rel="stylesheet">'
        )

    # CSS
    parts.append("  <style>")
    parts.append(_render_css(snapshot))
    parts.append("  </style>")

    parts.append("</head>")
    parts.append("<body>")
    parts.append('  <main class="aide-page">')

    # Content
    body_html = _render_content_html(snapshot)
    if body_html:
        parts.append(body_html)
    else:
        parts.append('    <p class="aide-empty">This page is empty.</p>')

    # Annotations
    annotations_html = _render_annotations_html(snapshot)
    if annotations_html:
        parts.append(annotations_html)

    parts.append("  </main>")

    # Footer
    if opts.footer:
        parts.append(f'  <footer class="aide-footer">{escape(opts.footer)}</footer>')

    parts.append("</body>")
    parts.append("</html>")

    return "\n".join(parts)


def _render_css(snapshot: dict[str, Any]) -> str:
    """Generate CSS from style tokens + schema styles."""
    styles = snapshot.get("styles", {})

    # Map style tokens to CSS custom properties
    primary_color = styles.get("primary_color", "#2d3748")
    bg_color = styles.get("bg_color", "#fafaf9")
    text_color = styles.get("text_color", "#1a1a1a")
    font_family = styles.get("font_family", "IBM Plex Sans, sans-serif")
    heading_font = styles.get("heading_font", "Cormorant Garamond, serif")

    css_vars = f"""
:root {{
  --font-body: {font_family};
  --font-heading: {heading_font};
  --text-primary: {text_color};
  --bg-primary: {bg_color};
  --accent: {primary_color};
  --border: rgba(0,0,0,0.1);
}}
""".strip()

    schema_css_parts = []
    for schema in snapshot.get("schemas", {}).values():
        if schema.get("_removed"):
            continue
        schema_styles = schema.get("styles", "")
        if schema_styles:
            schema_css_parts.append(schema_styles)

    schema_css = "\n".join(schema_css_parts)

    return "\n".join([css_vars, BASE_CSS, schema_css])


def _render_content_html(snapshot: dict[str, Any]) -> str:
    """Render main content from blocks or auto-render entities."""
    blocks = snapshot.get("blocks", {})
    root = blocks.get("block_root", {})
    children = root.get("children", [])

    if children:
        return _render_block_tree(snapshot)

    # No explicit blocks — auto-render top-level entities
    entities = snapshot.get("entities", {})
    active_entities = [(eid, e) for eid, e in entities.items() if not e.get("_removed")]
    if not active_entities:
        return ""

    parts = []
    for entity_id, _entity in active_entities:
        html = render_entity(entity_id, snapshot, channel="html")
        if html:
            parts.append(html)

    return "\n".join(parts)


def _render_block_tree(snapshot: dict[str, Any]) -> str:
    """Render the full block tree starting from block_root."""
    blocks = snapshot.get("blocks", {})
    root = blocks.get("block_root", {})
    parts = []
    for child_id in root.get("children", []):
        parts.append(_render_block(child_id, snapshot))
    return "\n".join(parts)


def _render_block(block_id: str, snapshot: dict[str, Any]) -> str:
    """Render a single block and its children recursively."""
    blocks = snapshot.get("blocks", {})
    block = blocks.get(block_id)
    if block is None:
        return ""

    block_type = block.get("type", "")

    if block_type == "root":
        parts = [_render_block(c, snapshot) for c in block.get("children", [])]
        return "\n".join(parts)

    if block_type == "heading":
        level = block.get("level", 2)
        text = escape(block.get("text", ""))
        return f"<h{level}>{text}</h{level}>"

    if block_type == "text":
        content = _render_inline(block.get("text", ""))
        return f"<p>{content}</p>"

    if block_type == "metric":
        label = escape(block.get("label", ""))
        value = escape(str(block.get("value", "")))
        return (
            f'<div class="aide-metric">'
            f'<span class="aide-metric-label">{label}</span>'
            f'<span class="aide-metric-value">{value}</span>'
            f"</div>"
        )

    if block_type == "entity_view":
        # source can be in props (v3) or directly on block (legacy)
        props = block.get("props", {})
        source = props.get("source", "") or block.get("source", "")
        if source:
            return render_entity(source, snapshot, channel="html")
        return ""

    if block_type == "divider":
        return "<hr>"

    if block_type == "image":
        src = escape(block.get("src", ""))
        alt = escape(block.get("alt", ""))
        caption = block.get("caption", "")
        img = f'<img src="{src}" alt="{alt}" loading="lazy">'
        if caption:
            return f"<figure>{img}<figcaption>{escape(caption)}</figcaption></figure>"
        return f"<figure>{img}</figure>"

    if block_type == "callout":
        icon = escape(block.get("icon", "ℹ️"))
        content = _render_inline(block.get("text", ""))
        return (
            f'<div class="aide-callout">'
            f'<span class="aide-callout-icon">{icon}</span>'
            f'<div class="aide-callout-content">{content}</div>'
            f"</div>"
        )

    if block_type == "column_list":
        children = block.get("children", [])
        cols = [f'<div class="aide-column">{_render_block(c, snapshot)}</div>' for c in children]
        return f'<div class="aide-columns">{" ".join(cols)}</div>'

    if block_type == "column":
        parts = [_render_block(c, snapshot) for c in block.get("children", [])]
        return "\n".join(parts)

    # Unknown block type — render children
    parts = [_render_block(c, snapshot) for c in block.get("children", [])]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Entity template rendering
# ---------------------------------------------------------------------------


def _render_entity_with_template(
    entity_id: str,
    entity: dict[str, Any],
    template: str,
    snapshot: dict[str, Any],
    channel: str,
    parent_schema_id: str | None = None,
    field_name: str | None = None,
) -> str:
    """Render entity using Mustache template, resolving {{>field}} child partials."""
    # Build the data context for the entity
    context = _build_entity_context(entity_id, entity, snapshot, channel)

    # Handle {{>fieldname}} partials by pre-rendering child collections
    # chevron doesn't natively handle dict-of-dicts as sections for us,
    # so we resolve child collection partials before passing to chevron
    schema_id = entity.get("_schema") or parent_schema_id
    resolved = _resolve_child_partials(template, entity, snapshot, channel, schema_id)

    try:
        rendered = chevron.render(resolved, context)
    except Exception:
        rendered = _default_entity_html(entity_id, entity, snapshot, channel)

    return rendered


def _build_entity_context(
    entity_id: str,
    entity: dict[str, Any],
    snapshot: dict[str, Any],
    channel: str,
) -> dict[str, Any]:
    """Build Mustache context dict from entity fields."""
    context: dict[str, Any] = {"_id": entity_id}

    for key, value in entity.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict):
            # Child collection — will be handled by partials, skip here
            pass
        else:
            context[key] = value

    return context


def _resolve_child_partials(
    template: str,
    entity: dict[str, Any],
    snapshot: dict[str, Any],
    channel: str,
    entity_schema_id: str | None = None,
) -> str:
    """
    Replace {{>fieldname}} with pre-rendered child collection HTML/text.
    This pre-processes partials before passing to chevron.
    """
    # Find all {{>fieldname}} references
    partial_pattern = re.compile(r"\{\{>\s*(\w+)\s*\}\}")

    def replace_partial(m: re.Match) -> str:
        field_name = m.group(1)
        child_collection = entity.get(field_name)
        if not isinstance(child_collection, dict):
            return ""
        # Determine child schema from parent's interface if available
        child_schema_id = _lookup_child_schema_id(entity_schema_id, field_name, snapshot)
        return _render_child_collection(child_collection, field_name, snapshot, channel, child_schema_id)

    return partial_pattern.sub(replace_partial, template)


def _lookup_child_schema_id(
    parent_schema_id: str | None,
    field_name: str,
    snapshot: dict[str, Any],
) -> str | None:
    """
    Look up the child schema ID for a Record field from the parent's TypeScript interface.

    For `interface GroceryList { items: Record<string, GroceryItem>; }`,
    `_lookup_child_schema_id("grocery_list", "items", snap)` returns "grocery_item".

    The schema IDs in the snapshot use snake_case (e.g. "grocery_item") but the interface
    uses PascalCase (e.g. "GroceryItem"). We find the match by checking all schemas whose
    interface name matches the Record's item type.
    """
    if not parent_schema_id:
        return None

    parent_schema = snapshot.get("schemas", {}).get(parent_schema_id, {})
    interface_src = parent_schema.get("interface", "")
    if not interface_src:
        return None

    iface = parse_interface_cached(interface_src)
    if iface is None:
        return None

    field_def = iface.fields.get(field_name)
    if field_def is None or field_def.kind != "record":
        return None

    # record_item_type is the PascalCase type name (e.g. "GroceryItem")
    item_type_name = field_def.record_item_type
    if not item_type_name:
        return None

    # Find a schema whose interface name matches item_type_name
    for schema_id, schema_def in snapshot.get("schemas", {}).items():
        if schema_def.get("_removed"):
            continue
        child_iface_src = schema_def.get("interface", "")
        if not child_iface_src:
            continue
        child_iface = parse_interface_cached(child_iface_src)
        if child_iface and child_iface.name == item_type_name:
            return schema_id

    return None


def _render_child_collection(
    collection: dict[str, Any],
    field_name: str,
    snapshot: dict[str, Any],
    channel: str,
    inferred_schema_id: str | None = None,
) -> str:
    """Render all children in a Record collection, sorted by _pos."""
    # Get shape for grid layout
    shape = collection.get("_shape")

    # Get active children (exclude _shape and _removed)
    children = [
        (cid, child)
        for cid, child in collection.items()
        if not cid.startswith("_") and isinstance(child, dict) and not child.get("_removed")
    ]

    if shape and isinstance(shape, list):
        return _render_grid_collection(collection, shape, snapshot, channel, inferred_schema_id)

    # Sort by _pos, then by insertion order
    children.sort(key=lambda x: (x[1].get("_pos", 999999), x[0]))

    if not children:
        return ""

    parts = []
    for child_id, child in children:
        # Child's own _schema takes precedence, then inferred from parent interface
        child_schema_id = child.get("_schema") or inferred_schema_id or ""
        child_schema = snapshot.get("schemas", {}).get(child_schema_id, {})

        if channel == "text":
            child_template = child_schema.get("render_text", "")
        else:
            child_template = child_schema.get("render_html", "")

        if child_template:
            resolved = _resolve_child_partials(child_template, child, snapshot, channel, child_schema_id)
            child_context = _build_entity_context(child_id, child, snapshot, channel)
            try:
                rendered = chevron.render(resolved, child_context)
            except Exception:
                rendered = _default_entity_html(child_id, child, snapshot, channel)
        else:
            rendered = _default_entity_html(child_id, child, snapshot, channel)

        parts.append(rendered)

    return "\n".join(parts)


def _render_grid_collection(
    collection: dict[str, Any],
    shape: list[int],
    snapshot: dict[str, Any],
    channel: str,
    inferred_schema_id: str | None = None,
) -> str:
    """Render a grid collection using _shape for dimensions."""
    if channel == "text":
        return _render_grid_text(collection, shape, snapshot, inferred_schema_id)

    if len(shape) != 2:
        # Only 2D grids supported for HTML rendering
        return _render_child_collection_no_shape(collection, snapshot, channel)

    rows, cols = shape[0], shape[1]

    # Check if child schema provides its own template - if so, render without wrapper divs
    child_schema = snapshot.get("schemas", {}).get(inferred_schema_id or "", {})
    has_schema_template = bool(child_schema.get("render_html", ""))

    # Use minimal grid wrapper if schema provides template (cells handle their own styling)
    # Otherwise use aide-grid with auto columns for generic rendering
    if has_schema_template:
        # Use fixed cell size for proper grid rendering (50px default, scales to ~400px for 8x8)
        cell_size = max(30, min(60, 400 // max(rows, cols)))
        grid_width = cell_size * cols
        grid_height = cell_size * rows
        parts = [f'<div class="aide-grid" style="display: grid; grid-template-columns: repeat({cols}, {cell_size}px); grid-template-rows: repeat({rows}, {cell_size}px); width: {grid_width}px; height: {grid_height}px; gap: 0;">']
    else:
        css_cols = " ".join(["auto"] * cols)
        parts = [f'<div class="aide-grid" style="grid-template-columns: {css_cols};">']

    for row in range(rows):
        for col in range(cols):
            key = f"{row}_{col}"
            cell = collection.get(key)
            if cell and not cell.get("_removed"):
                cell_schema_id = cell.get("_schema") or inferred_schema_id or ""
                cell_schema = snapshot.get("schemas", {}).get(cell_schema_id, {})
                cell_template = cell_schema.get("render_html", "")
                if cell_template:
                    resolved = _resolve_child_partials(cell_template, cell, snapshot, channel, cell_schema_id)
                    cell_context = _build_entity_context(key, cell, snapshot, channel)
                    try:
                        content = chevron.render(resolved, cell_context)
                    except Exception:
                        content = escape(str(next(iter(v for k, v in cell.items() if not k.startswith("_")), "")))
                    # Output template directly without wrapper when schema provides template
                    parts.append(content)
                else:
                    # First non-system field as content - use wrapper for generic cells
                    first_val = next((v for k, v in cell.items() if not k.startswith("_")), "")
                    content = escape(str(first_val)) if first_val else ""
                    parts.append(f'<div class="aide-grid-cell">{content}</div>')
            else:
                # Empty cell - render as schema template with no data or plain wrapper
                if has_schema_template:
                    cell_template = child_schema.get("render_html", "")
                    if cell_template:
                        cell_context = _build_entity_context(key, {}, snapshot, channel)
                        try:
                            content = chevron.render(cell_template, cell_context)
                        except Exception:
                            content = ""
                        parts.append(content)
                    else:
                        parts.append('<div class="aide-grid-cell"></div>')
                else:
                    parts.append('<div class="aide-grid-cell"></div>')

    parts.append("</div>")
    return "\n".join(parts)


def _render_grid_text(
    collection: dict[str, Any],
    shape: list[int],
    snapshot: dict[str, Any],
    inferred_schema_id: str | None = None,
) -> str:
    """Render a 2D grid as ASCII text."""
    if len(shape) != 2:
        return ""

    rows, cols = shape[0], shape[1]
    lines = []
    for row in range(rows):
        row_cells = []
        for col in range(cols):
            key = f"{row}_{col}"
            cell = collection.get(key)
            if cell and not cell.get("_removed"):
                cell_schema_id = cell.get("_schema") or inferred_schema_id or ""
                cell_schema = snapshot.get("schemas", {}).get(cell_schema_id, {})
                cell_template = cell_schema.get("render_text", "")
                if cell_template:
                    resolved = _resolve_child_partials(cell_template, cell, snapshot, "text", cell_schema_id)
                    cell_context = _build_entity_context(key, cell, snapshot, "text")
                    try:
                        content = chevron.render(resolved, cell_context).strip()
                    except Exception:
                        content = "?"
                else:
                    first_val = next((v for k, v in cell.items() if not k.startswith("_")), "")
                    content = str(first_val) if first_val else "."
            else:
                content = "."
            row_cells.append(content[:2].ljust(2))
        lines.append(" ".join(row_cells))

    return "\n".join(lines)


def _render_child_collection_no_shape(
    collection: dict[str, Any],
    snapshot: dict[str, Any],
    channel: str,
) -> str:
    """Render a collection without _shape (fallback)."""
    children = [
        (cid, child)
        for cid, child in collection.items()
        if not cid.startswith("_") and isinstance(child, dict) and not child.get("_removed")
    ]
    children.sort(key=lambda x: (x[1].get("_pos", 999999), x[0]))
    parts = []
    for child_id, child in children:
        parts.append(_default_entity_html(child_id, child, snapshot, channel))
    return "\n".join(parts)


def _default_entity_html(
    entity_id: str,
    entity: dict[str, Any],
    snapshot: dict[str, Any],
    channel: str,
) -> str:
    """Fallback rendering when no schema template is available."""
    if channel == "text":
        fields = [f"{k}: {v}" for k, v in entity.items() if not k.startswith("_") and not isinstance(v, dict)]
        return " | ".join(fields) if fields else entity_id

    # HTML fallback: render as a definition list
    fields = [(k, v) for k, v in entity.items() if not k.startswith("_") and not isinstance(v, dict)]
    if not fields:
        return f'<div class="aide-entity" id="{escape(entity_id)}"></div>'

    items = "".join(f"<dt>{escape(k)}</dt><dd>{escape(str(v))}</dd>" for k, v in fields)
    return f'<div class="aide-entity" id="{escape(entity_id)}"><dl>{items}</dl></div>'


# ---------------------------------------------------------------------------
# Text rendering (secondary channel)
# ---------------------------------------------------------------------------


def _render_text(
    snapshot: dict[str, Any],
    blueprint: Blueprint,
    opts: RenderOptions,
) -> str:
    """Render aide as plain text (for SMS, terminal, Slack)."""
    parts: list[str] = []

    title = snapshot.get("meta", {}).get("title", "")
    if title:
        parts.append(title)
        parts.append("=" * len(title))
        parts.append("")

    entities = snapshot.get("entities", {})
    for entity_id, entity in entities.items():
        if entity.get("_removed"):
            continue
        text = render_entity(entity_id, snapshot, channel="text")
        if text:
            parts.append(text)
            parts.append("")

    return "\n".join(parts).rstrip()


# ---------------------------------------------------------------------------
# Annotations
# ---------------------------------------------------------------------------


def _render_annotations_html(snapshot: dict[str, Any]) -> str:
    annotations = snapshot.get("annotations", [])
    if not annotations:
        return ""

    items = []
    for ann in annotations:
        note = escape(ann.get("note", ""))
        ts = escape(ann.get("timestamp", ""))
        items.append(f'<div class="aide-annotation">{note}<div class="aide-annotation-time">{ts}</div></div>')

    return f'<div class="aide-annotations">\n{"  ".join(items)}\n</div>'


# ---------------------------------------------------------------------------
# OG tags
# ---------------------------------------------------------------------------


def _render_og_tags(snapshot: dict[str, Any], opts: RenderOptions) -> str:
    meta = snapshot.get("meta", {})
    title = escape(meta.get("title", "AIde"))
    identity = escape(meta.get("identity", ""))
    base_url = opts.base_url if opts else "https://toaide.com"

    lines = [
        f'  <meta property="og:title" content="{title}">',
        '  <meta property="og:type" content="website">',
    ]
    if identity:
        lines.append(f'  <meta property="og:description" content="{identity}">')
    lines.append(f'  <meta property="og:url" content="{base_url}">')

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Inline formatting helpers
# ---------------------------------------------------------------------------

_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC_RE = re.compile(r"\*([^*]+)\*")


def escape(text: str) -> str:
    """HTML-escape user content."""
    return _html_escape(str(text), quote=True)


def _render_inline(text: str) -> str:
    """Apply inline markdown formatting to text."""
    text = escape(text)
    text = _LINK_RE.sub(r'<a href="\2">\1</a>', text)
    text = _BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = _ITALIC_RE.sub(r"<em>\1</em>", text)
    return text
