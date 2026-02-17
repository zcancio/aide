"""
AIde Kernel — Renderer

Pure function: (snapshot, blueprint, events?, options?) → HTML string
No AI. No IO. Deterministic: same input → same output, always.

Produces a complete, self-contained HTML file with:
- Embedded blueprint, snapshot, and event log as JSON
- CSS from design system + style token overrides
- Block tree rendered depth-first as HTML
- OG meta tags for link previews

Reference: aide_renderer_spec.md
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from html import escape as _html_escape
from typing import Any

from engine.kernel.types import (
    Blueprint,
    Event,
    RenderOptions,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_block(block_id: str, snapshot: dict[str, Any]) -> str:
    """
    Render a single block and its children recursively.
    Returns an HTML fragment string.
    Pure function. No side effects. No IO.
    """
    return _render_block(block_id, snapshot)


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

    parts: list[str] = []

    # DOCTYPE and opening
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="en">')
    parts.append("<head>")
    parts.append('  <meta charset="utf-8">')
    parts.append('  <meta name="viewport" content="width=device-width, initial-scale=1">')

    # Title
    title = escape(snapshot.get("meta", {}).get("title", "AIde"))
    parts.append(f"  <title>{title}</title>")

    # OG tags
    parts.append(_render_og_tags(snapshot))

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

    # Block tree
    body_html = _render_block_tree(snapshot)
    if body_html:
        parts.append(body_html)
    else:
        # No explicit blocks — auto-render collections if they exist
        auto_html = _auto_render_collections(snapshot)
        if auto_html:
            parts.append(auto_html)
        else:
            parts.append('    <p class="aide-empty">This page is empty.</p>')

    # Annotations
    annotations_html = _render_annotations(snapshot)
    if annotations_html:
        parts.append(annotations_html)

    parts.append("  </main>")

    # Footer
    if opts.footer:
        parts.append(_render_footer(opts.footer))

    parts.append("</body>")
    parts.append("</html>")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# HTML escaping
# ---------------------------------------------------------------------------


def escape(text: str) -> str:
    """HTML-escape user content."""
    return _html_escape(text, quote=True)


# ---------------------------------------------------------------------------
# OG tags
# ---------------------------------------------------------------------------


def _render_og_tags(snapshot: dict) -> str:
    title = escape(snapshot.get("meta", {}).get("title", "AIde"))
    description = escape(_derive_description(snapshot))

    return (
        f'  <meta property="og:title" content="{title}">\n'
        f'  <meta property="og:type" content="website">\n'
        f'  <meta property="og:description" content="{description}">\n'
        f'  <meta name="description" content="{description}">'
    )


def _derive_description(snapshot: dict) -> str:
    """Derive a description for OG tags from snapshot content."""
    blocks = snapshot.get("blocks", {})
    root = blocks.get("block_root", {})

    # Strategy 1: first text block
    for block_id in root.get("children", []):
        block = blocks.get(block_id, {})
        if block.get("type") == "text":
            content = block.get("props", {}).get("content", "")
            return content[:160]

    # Strategy 2: collection summary
    for coll in snapshot.get("collections", {}).values():
        if coll.get("_removed"):
            continue
        count = sum(1 for e in coll.get("entities", {}).values() if not e.get("_removed"))
        name = coll.get("name", coll.get("id", "Items"))
        return f"{name}: {count} items"

    # Strategy 3: title
    return snapshot.get("meta", {}).get("title", "A living page")


# ---------------------------------------------------------------------------
# CSS generation
# ---------------------------------------------------------------------------


def _render_css(snapshot: dict) -> str:
    """Generate the full CSS block: base + style token overrides."""
    styles = snapshot.get("styles", {})
    parts: list[str] = []

    # CSS custom properties (defaults + overrides)
    parts.append(":root {")
    parts.append("  /* Design system defaults */")
    parts.append("  --font-serif: 'Cormorant Garamond', Georgia, serif;")
    parts.append("  --font-sans: 'IBM Plex Sans', -apple-system, sans-serif;")
    parts.append("  --text-primary: #1a1a1a;")
    parts.append("  --text-secondary: #4a4a4a;")
    parts.append("  --text-tertiary: #8a8a8a;")
    parts.append("  --text-slate: #374151;")
    parts.append("  --bg-primary: #fafaf9;")
    parts.append("  --bg-cream: #f5f1eb;")
    parts.append("  --accent-navy: #1f2a44;")
    parts.append("  --accent-steel: #5a6e8a;")
    parts.append("  --accent-forest: #2d5a3d;")
    parts.append("  --border: #d4d0c8;")
    parts.append("  --border-light: #e8e4dc;")
    parts.append("  --radius-sm: 4px;")
    parts.append("  --radius-md: 8px;")
    # Spacing scale
    for i, px in enumerate([0, 4, 8, 12, 16, 20, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160]):
        parts.append(f"  --space-{i}: {px}px;")

    # Style token overrides
    if styles.get("primary_color"):
        parts.append(f"  --text-primary: {styles['primary_color']};")
    if styles.get("bg_color"):
        parts.append(f"  --bg-primary: {styles['bg_color']};")
    if styles.get("text_color"):
        parts.append(f"  --text-slate: {styles['text_color']};")
    if styles.get("font_family"):
        parts.append(f"  --font-sans: '{styles['font_family']}', -apple-system, sans-serif;")
    if styles.get("heading_font"):
        parts.append(f"  --font-serif: '{styles['heading_font']}', Georgia, serif;")

    parts.append("}")

    # Base styles
    parts.append(BASE_CSS)

    # Block type styles
    parts.append(BLOCK_CSS)

    # View type styles
    parts.append(VIEW_CSS)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Block tree rendering
# ---------------------------------------------------------------------------


def _auto_render_collections(snapshot: dict) -> str:
    """
    Auto-render all collections when no explicit blocks exist.
    Creates a heading + appropriate view for each non-removed collection.
    Detects grid patterns (row/col fields) and renders as grid.
    """
    collections = snapshot.get("collections", {})
    parts: list[str] = []

    for coll_id, coll in collections.items():
        if coll.get("_removed"):
            continue

        # Collection heading
        name = coll.get("name", coll_id)
        parts.append(f'    <h2 class="aide-heading aide-heading--2">{escape(name)}</h2>')

        # Get non-removed entities
        entities = [
            {**e, "_id": eid}
            for eid, e in coll.get("entities", {}).items()
            if not e.get("_removed")
        ]

        if not entities:
            parts.append('    <p class="aide-collection-empty">No items yet.</p>')
            continue

        schema = coll.get("schema", {})

        # Detect grid pattern: has row and col integer fields
        has_row = schema.get("row") in ("int", "int?")
        has_col = schema.get("col") in ("int", "int?")

        if has_row and has_col:
            # Render as grid (pass meta for team names)
            meta = snapshot.get("meta", {})
            parts.append(_render_auto_grid(entities, schema, meta))
        else:
            # Render as table view
            parts.append(_render_table_view(entities, schema, {}, {}))

    return "\n".join(parts)


def _render_auto_grid(entities: list[dict], schema: dict, meta: dict | None = None) -> str:
    """
    Render entities with row/col fields as a visual grid.
    Used for Super Bowl squares, bingo cards, seating charts, etc.
    """
    meta = meta or {}

    # Find grid dimensions
    rows = set()
    cols = set()
    grid_map: dict[tuple[int, int], dict] = {}

    for entity in entities:
        row = entity.get("row")
        col = entity.get("col")
        if row is not None and col is not None:
            rows.add(row)
            cols.add(col)
            grid_map[(row, col)] = entity

    if not rows or not cols:
        return '    <p class="aide-collection-empty">No grid data.</p>'

    row_list = sorted(rows)
    col_list = sorted(cols)

    # Determine what to show in each cell (first non-row/col field, or owner)
    display_field = None
    for field in schema:
        if field not in ("row", "col") and not field.startswith("_"):
            display_field = field
            break

    # Get axis labels from meta (for Super Bowl squares, seating charts, etc.)
    # row_label/col_label: single string label for the axis (e.g., team name)
    # row_labels/col_labels: array of labels to replace numeric indices
    row_label = meta.get("row_label", "")
    col_label = meta.get("col_label", "")
    row_labels = meta.get("row_labels", [])  # e.g., ["A", "B", "C", ...]
    col_labels = meta.get("col_labels", [])  # e.g., ["1", "2", "3", ...]

    parts = ['    <div class="aide-grid-wrap" style="display:flex;justify-content:center;padding:16px;">']
    parts.append('      <table class="aide-grid" style="border-collapse:collapse;text-align:center;width:100%;max-width:500px;table-layout:fixed;">')

    parts.append("        <thead>")

    # Column label header (if set)
    if col_label:
        parts.append("          <tr>")
        # Empty corner cells: 1 for row numbers, plus 1 if row_label exists
        if row_label:
            parts.append('            <th style="padding:4px;"></th>')  # Row label column
        parts.append('            <th style="padding:4px;"></th>')  # Row numbers column
        parts.append(f'            <th colspan="{len(col_list)}" style="padding:6px 4px;font-weight:700;color:#222;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;border-bottom:2px solid #333;">{escape(col_label)}</th>')
        parts.append("          </tr>")

    # Header row with column numbers/labels
    parts.append("          <tr>")
    # Empty cells: 1 for row numbers, plus 1 if row_label exists
    if row_label:
        parts.append('            <th style="padding:4px;"></th>')  # Row label column
    parts.append('            <th style="padding:4px;"></th>')  # Row numbers column
    for idx, col in enumerate(col_list):
        # Use custom col_labels if provided, otherwise use numeric index
        col_display = col_labels[idx] if idx < len(col_labels) else col
        parts.append(f'            <th style="padding:4px;font-weight:600;color:#444;font-size:11px;">{escape(str(col_display))}</th>')
    parts.append("          </tr>")
    parts.append("        </thead>")

    # Grid rows - with row label spanning all rows on the left
    parts.append("        <tbody>")
    for i, row in enumerate(row_list):
        parts.append("          <tr>")
        # Add vertical row label on first row, spanning all rows
        if i == 0 and row_label:
            parts.append(f'            <th rowspan="{len(row_list)}" style="padding:6px 4px;font-weight:700;color:#222;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;writing-mode:vertical-lr;transform:rotate(180deg);border-right:2px solid #333;text-align:center;">{escape(row_label)}</th>')
        # Note: when row_label exists and i > 0, we skip because rowspan covers it
        # Row number/label - use custom row_labels if provided
        row_display = row_labels[i] if i < len(row_labels) else row
        parts.append(f'            <th style="padding:4px;font-weight:600;color:#444;font-size:11px;">{escape(str(row_display))}</th>')
        for col in col_list:
            entity = grid_map.get((row, col))
            if entity and display_field:
                value = entity.get(display_field)
                if value:
                    cell_content = escape(str(value))
                    cell_style = "padding:0;border:1px solid #ccc;background:#e8f4e8;font-size:11px;aspect-ratio:1;vertical-align:middle;"
                else:
                    cell_content = ""
                    cell_style = "padding:0;border:1px solid #ddd;aspect-ratio:1;vertical-align:middle;"
            else:
                cell_content = ""
                cell_style = "padding:0;border:1px solid #ddd;aspect-ratio:1;vertical-align:middle;"
            parts.append(f'            <td style="{cell_style}">{cell_content}</td>')
        parts.append("          </tr>")
    parts.append("        </tbody>")
    parts.append("      </table>")
    parts.append("    </div>")

    return "\n".join(parts)


def _render_block_tree(snapshot: dict) -> str:
    """Walk the block tree depth-first from block_root, emit HTML."""
    blocks = snapshot.get("blocks", {})
    root = blocks.get("block_root", {})
    children = root.get("children", [])

    if not children:
        return ""

    parts: list[str] = []
    for child_id in children:
        html = _render_block(child_id, snapshot)
        if html:
            parts.append(html)

    return "\n".join(parts)


def _render_block(block_id: str, snapshot: dict) -> str:
    """Render a single block and its children recursively."""
    blocks = snapshot.get("blocks", {})
    block = blocks.get(block_id)
    if block is None or block.get("_removed"):
        return ""

    block_type = block.get("type", "")
    renderer = _BLOCK_RENDERERS.get(block_type)
    if renderer is None:
        return ""

    html = renderer(block, snapshot)

    # Render children recursively (for container blocks)
    children = block.get("children", [])
    if children and block_type in ("column_list", "column", "root"):
        child_parts: list[str] = []
        for child_id in children:
            child_html = _render_block(child_id, snapshot)
            if child_html:
                child_parts.append(child_html)
        if child_parts:
            html = html.replace("<!--children-->", "\n".join(child_parts))
        else:
            html = html.replace("<!--children-->", "")

    return html


# ---------------------------------------------------------------------------
# Block type renderers
# ---------------------------------------------------------------------------


def _render_heading(block: dict, snapshot: dict) -> str:
    props = block.get("props", {})
    level = props.get("level", 1)
    level = max(1, min(3, level))
    content = escape(props.get("content", ""))
    return f'    <h{level} class="aide-heading aide-heading--{level}">{content}</h{level}>'


def _render_text(block: dict, snapshot: dict) -> str:
    props = block.get("props", {})
    content = props.get("content", "")
    html_content = _format_inline(content)
    return f'    <p class="aide-text">{html_content}</p>'


def _render_metric(block: dict, snapshot: dict) -> str:
    props = block.get("props", {})
    label = escape(props.get("label", ""))
    value = escape(str(props.get("value", "")))
    return (
        f'    <div class="aide-metric">\n'
        f'      <span class="aide-metric__label">{label}</span>\n'
        f'      <span class="aide-metric__value">{value}</span>\n'
        f"    </div>"
    )


def _render_collection_view_block(block: dict, snapshot: dict) -> str:
    props = block.get("props", {})
    view_id = props.get("view")
    source_id = props.get("source")

    views = snapshot.get("views", {})
    collections = snapshot.get("collections", {})

    view = views.get(view_id) if view_id else None
    collection = collections.get(source_id) if source_id else None

    if collection is None or collection.get("_removed"):
        return ""

    # Get non-removed entities
    entities = [{**e, "_id": eid} for eid, e in collection.get("entities", {}).items() if not e.get("_removed")]

    if not entities:
        return '    <p class="aide-collection-empty">No items yet.</p>'

    schema = collection.get("schema", {})
    config = view.get("config", {}) if view else {}
    view_type = view.get("type", "table") if view else "table"

    # Apply sort, filter, group
    entities = _apply_sort(entities, config)
    entities = _apply_filter(entities, config)

    # Check empty after filtering
    if not entities:
        return '    <p class="aide-collection-empty">No items match the filter.</p>'

    # Delegate to view renderer
    view_renderer = _VIEW_RENDERERS.get(view_type, _render_table_view)
    return view_renderer(entities, schema, config, snapshot.get("styles", {}))


def _render_divider(block: dict, snapshot: dict) -> str:
    return '    <hr class="aide-divider">'


def _render_image(block: dict, snapshot: dict) -> str:
    props = block.get("props", {})
    src = escape(props.get("src", ""))
    alt = escape(props.get("alt", ""))
    caption = props.get("caption")

    parts = ['    <figure class="aide-image">']
    parts.append(f'      <img src="{src}" alt="{alt}" loading="lazy">')
    if caption:
        parts.append(f'      <figcaption class="aide-image__caption">{escape(caption)}</figcaption>')
    parts.append("    </figure>")
    return "\n".join(parts)


def _render_callout(block: dict, snapshot: dict) -> str:
    props = block.get("props", {})
    content = escape(props.get("content", ""))
    icon = props.get("icon")

    parts = ['    <div class="aide-callout">']
    if icon:
        parts.append(f'      <span class="aide-callout__icon">{escape(icon)}</span>')
    parts.append(f'      <span class="aide-callout__content">{content}</span>')
    parts.append("    </div>")
    return "\n".join(parts)


def _render_column_list(block: dict, snapshot: dict) -> str:
    return '    <div class="aide-columns">\n<!--children-->\n    </div>'


def _render_column(block: dict, snapshot: dict) -> str:
    props = block.get("props", {})
    width = props.get("width")
    if width and "%" in str(width):
        style = f"flex: 0 0 {width}"
    else:
        style = "flex: 1"
    return f'    <div class="aide-column" style="{style}">\n<!--children-->\n    </div>'


def _render_root(block: dict, snapshot: dict) -> str:
    """Root block - container for all children."""
    return "<!--children-->"


_BLOCK_RENDERERS = {
    "root": _render_root,
    "heading": _render_heading,
    "text": _render_text,
    "metric": _render_metric,
    "collection_view": _render_collection_view_block,
    "divider": _render_divider,
    "image": _render_image,
    "callout": _render_callout,
    "column_list": _render_column_list,
    "column": _render_column,
}


# ---------------------------------------------------------------------------
# View renderers
# ---------------------------------------------------------------------------


def _render_list_view(entities: list[dict], schema: dict, config: dict, styles: dict) -> str:
    show_fields = _visible_fields(schema, config)
    if not show_fields:
        return '    <p class="aide-collection-empty">No fields to display.</p>'

    parts = ['    <ul class="aide-list">']
    for entity in entities:
        entity_class = _entity_css_class(entity)
        entity_style = _entity_inline_style(entity)
        style_attr = f' style="{entity_style}"' if entity_style else ""

        parts.append(f'      <li class="aide-list__item {entity_class}"{style_attr}>')
        for i, field_name in enumerate(show_fields):
            value = entity.get(field_name)
            field_type = schema.get(field_name, "string")
            formatted = _format_value(value, field_type)
            cls = "aide-list__field--primary" if i == 0 else "aide-list__field"
            bool_cls = _bool_class(value, field_type)
            parts.append(f'        <span class="{cls} {bool_cls}">{formatted}</span>')
        parts.append("      </li>")
    parts.append("    </ul>")
    return "\n".join(parts)


def _render_table_view(entities: list[dict], schema: dict, config: dict, styles: dict) -> str:
    show_fields = _visible_fields(schema, config)
    if not show_fields:
        return '    <p class="aide-collection-empty">No fields to display.</p>'

    parts = ['    <div class="aide-table-wrap">']
    parts.append('      <table class="aide-table">')
    parts.append("        <thead>")
    parts.append("          <tr>")
    for field_name in show_fields:
        display_name = escape(_field_display_name(field_name))
        parts.append(f'            <th class="aide-table__th">{display_name}</th>')
    parts.append("          </tr>")
    parts.append("        </thead>")
    parts.append("        <tbody>")

    for entity in entities:
        entity_class = _entity_css_class(entity)
        entity_style = _entity_inline_style(entity)
        style_attr = f' style="{entity_style}"' if entity_style else ""
        parts.append(f'          <tr class="aide-table__row {entity_class}"{style_attr}>')
        for field_name in show_fields:
            value = entity.get(field_name)
            field_type = schema.get(field_name, "string")
            bt = _base_type_str(field_type)
            formatted = _format_value(value, field_type)
            parts.append(f'            <td class="aide-table__td aide-table__td--{bt}">{formatted}</td>')
        parts.append("          </tr>")

    parts.append("        </tbody>")
    parts.append("      </table>")
    parts.append("    </div>")
    return "\n".join(parts)


def _render_grid_view(entities: list[dict], schema: dict, config: dict, styles: dict) -> str:
    row_labels = config.get("row_labels", [])
    col_labels = config.get("col_labels", [])
    show_fields = _visible_fields(schema, config)

    # Build position map
    pos_map: dict[str, dict] = {}
    for entity in entities:
        pos = entity.get("position", "")
        if pos:
            pos_map[pos] = entity

    parts = ['    <div class="aide-grid-wrap">']
    parts.append('      <table class="aide-grid">')
    parts.append("        <thead>")
    parts.append("          <tr>")
    parts.append("            <th></th>")
    for col in col_labels:
        parts.append(f'            <th class="aide-grid__col-label">{escape(str(col))}</th>')
    parts.append("          </tr>")
    parts.append("        </thead>")
    parts.append("        <tbody>")

    for row in row_labels:
        parts.append("          <tr>")
        parts.append(f'            <th class="aide-grid__row-label">{escape(str(row))}</th>')
        for col in col_labels:
            cell_key = f"{row}{col}"
            entity = pos_map.get(cell_key)
            if entity:
                cell_content = ", ".join(
                    _format_value(entity.get(f), schema.get(f, "string"))
                    for f in show_fields
                    if entity.get(f) is not None
                ) or escape(str(entity.get("_id", "")))
                parts.append(f'            <td class="aide-grid__cell aide-grid__cell--filled">{cell_content}</td>')
            else:
                parts.append('            <td class="aide-grid__cell aide-grid__cell--empty"></td>')
        parts.append("          </tr>")

    parts.append("        </tbody>")
    parts.append("      </table>")
    parts.append("    </div>")
    return "\n".join(parts)


_VIEW_RENDERERS = {
    "list": _render_list_view,
    "table": _render_table_view,
    "grid": _render_grid_view,
}


# ---------------------------------------------------------------------------
# Sort / Filter / Group
# ---------------------------------------------------------------------------


def _apply_sort(entities: list[dict], config: dict) -> list[dict]:
    sort_by = config.get("sort_by")
    if not sort_by:
        return entities
    order = config.get("sort_order", "asc")
    reverse = order == "desc"

    # Separate entities with values from those with null
    with_value = [e for e in entities if e.get(sort_by) is not None]
    with_null = [e for e in entities if e.get(sort_by) is None]

    # Sort only the non-null entities
    with_value.sort(key=lambda e: _sort_key(e.get(sort_by)), reverse=reverse)

    # Nulls always sort last
    return with_value + with_null


def _sort_key(value: Any) -> tuple:
    # Value is guaranteed non-None at this point
    if isinstance(value, bool):
        return (0, int(value))
    return (0, value)


def _apply_filter(entities: list[dict], config: dict) -> list[dict]:
    filt = config.get("filter")
    if not filt:
        return entities
    return [e for e in entities if all(e.get(k) == v for k, v in filt.items())]


# ---------------------------------------------------------------------------
# Value formatting
# ---------------------------------------------------------------------------


def _format_value(value: Any, field_type: str | dict) -> str:
    """Format a field value for display."""
    if value is None:
        return "\u2014"  # em dash

    bt = _base_type_str(field_type)

    if bt == "bool":
        return "\u2713" if value else "\u25cb"
    if bt == "date" and isinstance(value, str):
        return _format_date(value)
    if bt == "datetime" and isinstance(value, str):
        return _format_datetime(value)
    if bt == "enum":
        return escape(str(value).replace("_", " ").title())
    if bt == "list" and isinstance(value, list):
        if not value:
            return "\u2014"  # em dash for empty list
        return escape(", ".join(str(v) for v in value))

    return escape(str(value))


def _format_date(iso_str: str) -> str:
    """Format ISO date to short form: Feb 27."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d").replace(" 0", " ")
    except (ValueError, AttributeError):
        return escape(iso_str)


def _format_datetime(iso_str: str) -> str:
    """Format ISO datetime to: Feb 27, 7:00 PM."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        date_part = dt.strftime("%b %d").replace(" 0", " ")
        time_part = dt.strftime("%-I:%M %p") if hasattr(dt, "strftime") else dt.strftime("%I:%M %p").lstrip("0")
        return f"{date_part}, {time_part}"
    except (ValueError, AttributeError):
        return escape(iso_str)


def _format_inline(text: str) -> str:
    """
    Parse minimal inline formatting in text blocks.
    Supports: **bold** → <strong>, *italic* → <em>, [text](url) → <a>
    """
    # Escape first, then apply formatting
    text = escape(text)

    # Links: [text](url) — must be http/https
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r'<a href="\2">\1</a>',
        text,
    )

    # Bold: **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)

    # Italic: *text*
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)

    return text


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------


def _visible_fields(schema: dict, config: dict) -> list[str]:
    """Determine which fields to show and in what order."""
    show = config.get("show_fields")
    hide = config.get("hide_fields", [])

    if show:
        return [f for f in show if f in schema]

    # Default: all non-internal fields minus hidden
    return [f for f in schema if not f.startswith("_") and f not in hide]


def _field_display_name(field_name: str) -> str:
    """Convert snake_case to Title Case."""
    return field_name.replace("_", " ").title()


def _base_type_str(field_type: str | dict) -> str:
    """Get base type as string for CSS classes."""
    if isinstance(field_type, str):
        return field_type.rstrip("?")
    if isinstance(field_type, dict):
        if "enum" in field_type:
            return "enum"
        if "list" in field_type:
            return "list"
    return "string"


def _bool_class(value: Any, field_type: str | dict) -> str:
    bt = _base_type_str(field_type)
    if bt != "bool":
        return ""
    return "aide-list__field--bool" if value else "aide-list__field--bool-false"


def _entity_css_class(entity: dict) -> str:
    classes: list[str] = []
    styles = entity.get("_styles", {})
    if styles.get("highlight"):
        classes.append("aide-highlight")
    return " ".join(classes)


def _entity_inline_style(entity: dict) -> str:
    styles = entity.get("_styles", {})
    parts: list[str] = []
    if "bg_color" in styles:
        parts.append(f"background-color: {styles['bg_color']}")
    if "text_color" in styles:
        parts.append(f"color: {styles['text_color']}")
    return "; ".join(parts)


# ---------------------------------------------------------------------------
# Annotations
# ---------------------------------------------------------------------------


def _render_annotations(snapshot: dict) -> str:
    annotations = snapshot.get("annotations", [])
    if not annotations:
        return ""

    # Pinned first, then most recent
    pinned = [a for a in annotations if a.get("pinned")]
    unpinned = sorted(
        [a for a in annotations if not a.get("pinned")],
        key=lambda a: a.get("seq", 0),
        reverse=True,
    )
    ordered = pinned + unpinned

    parts = ['    <section class="aide-annotations">']
    parts.append('      <h3 class="aide-heading aide-heading--3">Notes</h3>')

    for ann in ordered:
        pinned_cls = " aide-annotation--pinned" if ann.get("pinned") else ""
        note = escape(ann.get("note", ""))
        ts = ann.get("timestamp", "")
        formatted_ts = _format_datetime(ts) if ts else ""

        parts.append(f'      <div class="aide-annotation{pinned_cls}">')
        parts.append(f'        <span class="aide-annotation__text">{note}</span>')
        if formatted_ts:
            parts.append(f'        <span class="aide-annotation__meta">{formatted_ts}</span>')
        parts.append("      </div>")

    parts.append("    </section>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------


def _render_footer(text: str) -> str:
    return (
        '  <footer class="aide-footer">\n'
        f'    <a href="https://toaide.com" class="aide-footer__link">{escape(text)}</a>\n'
        "  </footer>"
    )


# ---------------------------------------------------------------------------
# CSS constants
# ---------------------------------------------------------------------------

BASE_CSS = """
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

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
"""

BLOCK_CSS = """
/* ── Headings ── */
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

/* ── Text ── */
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

/* ── Metric ── */
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
.aide-metric__label::after { content: ':'; }
.aide-metric__value {
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
}

/* ── Divider ── */
.aide-divider {
  border: none;
  border-top: 1px solid var(--border-light);
  margin: var(--space-6) 0;
}

/* ── Image ── */
.aide-image { margin: var(--space-6) 0; }
.aide-image img { max-width: 100%; height: auto; border-radius: var(--radius-sm); }
.aide-image__caption {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-top: var(--space-2);
}

/* ── Callout ── */
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

/* ── Columns ── */
.aide-columns {
  display: flex;
  gap: var(--space-6);
}
@media (max-width: 640px) {
  .aide-columns {
    flex-direction: column;
  }
}

/* ── Empty states ── */
.aide-empty {
  color: var(--text-tertiary);
  font-size: 15px;
  padding: var(--space-16) 0;
  text-align: center;
}
.aide-collection-empty {
  color: var(--text-tertiary);
  font-size: 14px;
  padding: var(--space-4) 0;
}

/* ── Highlight ── */
.aide-highlight {
  background-color: rgba(31, 42, 68, 0.04);
}
"""

VIEW_CSS = """
/* ── List view ── */
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

/* ── Table view ── */
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

/* ── Grid view ── */
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

/* ── Group headers ── */
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

/* ── Annotations ── */
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

/* ── Footer ── */
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
"""
