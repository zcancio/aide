"""
AIde Kernel — React Preview Generator

Generates HTML pages that render using the same React components
as the streaming preview. This ensures pixel-perfect consistency
between streaming and server-rendered views.

The React components are loaded via CDN and compiled client-side
with Babel standalone. This approach:
- Zero build step required
- Same rendering code for both streaming and refresh
- ~150KB additional load (React + ReactDOM + Babel)
"""

from __future__ import annotations

import json
from typing import Any


def render_react_preview(
    snapshot: dict[str, Any],
    title: str | None = None,
) -> str:
    """
    Render a complete HTML page using React components.

    Args:
        snapshot: The v2 snapshot with entities, meta, etc.
        title: Optional page title override

    Returns:
        Complete HTML string
    """
    # Extract data from snapshot
    entities = snapshot.get("entities", {})
    meta = snapshot.get("meta", {})

    # Compute root IDs (entities with parent "root" or no parent)
    root_ids = [
        eid for eid, e in entities.items()
        if not e.get("_removed") and e.get("parent") in (None, "root", "")
    ]

    # Use meta title or provided title
    page_title = title or meta.get("title") or "AIde"

    # Serialize for embedding
    entities_json = json.dumps(entities, ensure_ascii=False)
    meta_json = json.dumps(meta, ensure_ascii=False)
    root_ids_json = json.dumps(root_ids, ensure_ascii=False)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_escape_html(page_title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=IBM+Plex+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
<script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
<style>
{PREVIEW_CSS}
</style>
</head>
<body>
<div id="root"></div>
<script>
const INITIAL_ENTITIES = {entities_json};
const INITIAL_META = {meta_json};
const INITIAL_ROOT_IDS = {root_ids_json};

{REACT_COMPONENTS}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  React.createElement(EntityContext.Provider, {{
    value: {{ entities: INITIAL_ENTITIES, meta: INITIAL_META, rootIds: INITIAL_ROOT_IDS }}
  }},
    React.createElement(PreviewApp)
  )
);
</script>
</body>
</html>'''


def _escape_html(text: str) -> str:
    """HTML-escape text for safe embedding."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ─────────────────────────────────────────────────────────────────────────────
# CSS - Exact copy from frontend/index.html renderer-css-template
# ─────────────────────────────────────────────────────────────────────────────

PREVIEW_CSS = '''
/* CSS custom properties - exact copy from renderer.py */
:root {
  /* Design system defaults */
  --font-serif: 'Cormorant Garamond', Georgia, serif;
  --font-sans: 'IBM Plex Sans', -apple-system, sans-serif;
  --text-primary: #1a1a1a;
  --text-secondary: #4a4a4a;
  --text-tertiary: #8a8a8a;
  --text-slate: #374151;
  --bg-primary: #fafaf9;
  --bg-cream: #f5f1eb;
  --accent-navy: #1f2a44;
  --accent-steel: #5a6e8a;
  --accent-forest: #2d5a3d;
  --border: #d4d0c8;
  --border-light: #e8e4dc;
  --radius-sm: 4px;
  --radius-md: 8px;
  /* Spacing scale */
  --space-0: 0px;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-7: 32px;
  --space-8: 40px;
  --space-9: 48px;
  --space-10: 56px;
  --space-11: 64px;
  --space-12: 80px;
  --space-13: 96px;
  --space-14: 112px;
  --space-15: 128px;
  --space-16: 160px;
}

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

/* ── Card (React component) ── */
.aide-card {
  background: #fff;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  margin-bottom: var(--space-3);
}
.aide-card__title {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}
.aide-card__field {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: var(--space-1) 0;
  border-bottom: 1px solid var(--border-light);
  gap: var(--space-3);
}
.aide-card__field:last-child { border-bottom: none; }
.aide-card__label {
  color: var(--text-tertiary);
  font-size: 12px;
  text-transform: capitalize;
  flex-shrink: 0;
}

/* ── Section (React component) ── */
.aide-section {
  margin-bottom: var(--space-6);
}
.aide-section__header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  padding: var(--space-1) 0;
  user-select: none;
}
.aide-section__icon {
  color: var(--text-tertiary);
  font-size: 12px;
  width: 14px;
  text-align: center;
  transition: transform 0.2s;
}
.aide-section__icon--collapsed {
  transform: rotate(-90deg);
}
.aide-section__title {
  font-family: var(--font-serif);
  font-size: clamp(24px, 3.5vw, 32px);
  font-weight: 400;
  line-height: 1.25;
  color: var(--text-primary);
}
.aide-section__content {
  margin-top: var(--space-3);
}
.aide-section__content--collapsed {
  display: none;
}

/* ── Checklist (React component) ── */
.aide-checklist {
  list-style: none;
  padding: 0;
  margin-bottom: var(--space-4);
}
.aide-checklist__item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--border-light);
  font-size: 15px;
  line-height: 1.5;
}
.aide-checklist__item:last-child { border-bottom: none; }
.aide-checklist__checkbox {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: var(--accent-navy);
  flex-shrink: 0;
  margin-top: 2px;
}
.aide-checklist__label {
  font-weight: 500;
  color: var(--text-primary);
}
.aide-checklist__label--done {
  text-decoration: line-through;
  color: var(--text-tertiary);
}
.aide-checklist__summary {
  font-size: 13px;
  color: var(--text-tertiary);
  padding-top: var(--space-2);
}

/* ── Editable field (React component) ── */
.editable-field {
  cursor: text;
  border-radius: 2px;
  padding: 1px 2px;
  margin: -1px -2px;
  transition: background-color 0.15s;
}
.editable-field:hover {
  background-color: rgba(0, 0, 0, 0.04);
}
.editable-field--empty {
  color: var(--text-tertiary);
}
.editable-input {
  font: inherit;
  color: inherit;
  background: #fff;
  border: 1px solid var(--accent-steel);
  border-radius: 2px;
  padding: 1px 4px;
  margin: -2px -5px;
  outline: none;
  min-width: 60px;
}
}

/* ── Mount animation ── */
@keyframes aide-fade-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
.aide-mount-animation {
  animation: aide-fade-in 0.2s ease-out;
}
'''


# ─────────────────────────────────────────────────────────────────────────────
# React Components - Exact copy from frontend/index.html REACT_COMPONENTS_TEMPLATE
# ─────────────────────────────────────────────────────────────────────────────

REACT_COMPONENTS = '''
const { useState, useContext, createContext, useMemo } = React;

// ── Entity Context ────────────────────────────────────
const EntityContext = createContext({ entities: {}, meta: {}, rootIds: [] });

function useEntity(id) {
  const { entities } = useContext(EntityContext);
  return entities[id] || null;
}

function useChildren(parentId) {
  const { entities } = useContext(EntityContext);
  return Object.entries(entities)
    .filter(([, e]) => e.parent === parentId)
    .map(([id]) => id);
}

function useMeta() {
  const { meta } = useContext(EntityContext);
  return meta;
}

function useRootIds() {
  const { rootIds } = useContext(EntityContext);
  return rootIds;
}

// ── Helpers ────────────────────────────────────────────
function humanize(str) {
  if (!str) return '';
  return str.replace(/_/g, ' ').replace(/\\b\\w/g, c => c.toUpperCase());
}

function getDisplayableProps(props) {
  if (!props) return {};
  const skip = new Set(['title', 'name', '_removed', '_styles', '_pos', '_schema', '_shape']);
  return Object.fromEntries(
    Object.entries(props).filter(([k]) => !k.startsWith('_') && !skip.has(k))
  );
}

function inferType(value) {
  if (typeof value === 'boolean') return 'boolean';
  if (typeof value === 'number') return 'number';
  if (typeof value === 'string' && /^\\d{4}-\\d{2}-\\d{2}/.test(value)) return 'date';
  return 'string';
}

function formatValue(value, type) {
  if (value === null || value === undefined) return '—';
  if (type === 'boolean') return value ? '✓' : '○';
  if (type === 'date' && typeof value === 'string') {
    try {
      const d = new Date(value);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch { return value; }
  }
  return String(value);
}

function deriveColumns(children, entities) {
  const cols = new Set();
  const skip = new Set(['_pos', '_schema', '_shape']);
  children.forEach(id => {
    const entity = entities[id];
    const props = entity?.props || {};
    Object.keys(props).filter(k => !k.startsWith('_') && !skip.has(k)).forEach(k => cols.add(k));
  });
  return Array.from(cols);
}

function applyStyles(styles) {
  if (!styles) return {};
  const css = {};
  if (styles.bg_color) css.backgroundColor = styles.bg_color;
  if (styles.text_color) css.color = styles.text_color;
  return css;
}

// ── EditableField ──────────────────────────────────────
function EditableField({ entityId, field, value, type = 'string', className = '' }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value ?? '');

  const emitUpdate = (newValue) => {
    window.parent.postMessage({
      type: 'direct_edit',
      entity_id: entityId,
      field: field,
      value: newValue
    }, '*');
  };

  // Booleans toggle immediately
  if (type === 'boolean') {
    return React.createElement('input', {
      type: 'checkbox',
      className: 'aide-checklist__checkbox',
      checked: !!value,
      onChange: () => emitUpdate(!value)
    });
  }

  if (!editing) {
    const displayValue = formatValue(value, type);
    const isEmpty = value === null || value === undefined || value === '';
    return React.createElement('span', {
      className: 'editable-field ' + (isEmpty ? 'editable-field--empty ' : '') + className,
      onClick: () => { setDraft(value ?? ''); setEditing(true); }
    }, displayValue);
  }

  return React.createElement('input', {
    type: type === 'number' ? 'number' : type === 'date' ? 'date' : 'text',
    className: 'editable-input',
    value: draft,
    autoFocus: true,
    onChange: (e) => setDraft(e.target.value),
    onBlur: () => {
      setEditing(false);
      if (draft !== value) {
        const coerced = type === 'number' ? Number(draft) : draft;
        emitUpdate(coerced);
      }
    },
    onKeyDown: (e) => {
      if (e.key === 'Enter') e.target.blur();
      if (e.key === 'Escape') { setDraft(value ?? ''); setEditing(false); }
    }
  });
}

// ── Display Components ─────────────────────────────────

function PageDisplay({ entity, entityId, children }) {
  const props = entity?.props || {};
  const title = props.title || props.name || '';
  return React.createElement('div', { className: 'aide-page aide-mount-animation' },
    title && React.createElement('h1', { className: 'aide-heading aide-heading--1' },
      React.createElement(EditableField, { entityId, field: 'title', value: title })
    ),
    children || React.createElement('p', { className: 'aide-empty' }, 'Say something to get started.')
  );
}

function SectionDisplay({ entity, entityId, children }) {
  const [collapsed, setCollapsed] = useState(false);
  const props = entity?.props || {};
  const title = props.title || props.name || 'Section';

  return React.createElement('div', { className: 'aide-section aide-mount-animation' },
    React.createElement('div', {
      className: 'aide-section__header',
      onClick: () => setCollapsed(!collapsed)
    },
      React.createElement('span', {
        className: 'aide-section__icon' + (collapsed ? ' aide-section__icon--collapsed' : '')
      }, '▾'),
      React.createElement('span', { className: 'aide-section__title' },
        React.createElement(EditableField, { entityId, field: 'title', value: title })
      )
    ),
    React.createElement('div', {
      className: 'aide-section__content' + (collapsed ? ' aide-section__content--collapsed' : '')
    }, children || React.createElement('p', { className: 'aide-collection-empty' }, 'No items yet.'))
  );
}

function CardDisplay({ entity, entityId, children }) {
  const props = entity?.props || {};
  const title = props.title || props.name || '';
  const displayProps = getDisplayableProps(props);
  const styles = applyStyles(entity?._styles);

  return React.createElement('div', { className: 'aide-card aide-mount-animation', style: styles },
    title && React.createElement('div', { className: 'aide-card__title' },
      React.createElement(EditableField, { entityId, field: props.title !== undefined ? 'title' : 'name', value: title })
    ),
    Object.entries(displayProps).map(([key, value]) =>
      React.createElement('div', { key, className: 'aide-card__field' },
        React.createElement('span', { className: 'aide-card__label' }, humanize(key)),
        React.createElement(EditableField, { entityId, field: key, value, type: inferType(value) })
      )
    ),
    children
  );
}

function ListDisplay({ entity, entityId, children }) {
  const props = entity?.props || {};
  const title = props.title || props.name || '';

  return React.createElement('div', { className: 'aide-mount-animation' },
    title && React.createElement('h3', { className: 'aide-heading aide-heading--3' },
      React.createElement(EditableField, { entityId, field: 'title', value: title })
    ),
    React.createElement('ul', { className: 'aide-list' },
      children || React.createElement('li', { className: 'aide-collection-empty' }, 'No items yet.')
    )
  );
}

function TableDisplay({ entity, entityId, children }) {
  const { entities } = useContext(EntityContext);
  const childIds = useChildren(entityId);
  const props = entity?.props || {};
  const title = props.title || props.name || '';

  if (childIds.length === 0) {
    return React.createElement(CardDisplay, { entity, entityId, children });
  }

  const columns = deriveColumns(childIds, entities);

  return React.createElement('div', { className: 'aide-mount-animation' },
    title && React.createElement('h3', { className: 'aide-heading aide-heading--3' },
      React.createElement(EditableField, { entityId, field: 'title', value: title })
    ),
    React.createElement('div', { className: 'aide-table-wrap' },
      React.createElement('table', { className: 'aide-table' },
        React.createElement('thead', null,
          React.createElement('tr', null,
            columns.map(col =>
              React.createElement('th', { key: col, className: 'aide-table__th' }, humanize(col))
            )
          )
        ),
        React.createElement('tbody', null,
          childIds.map(cid => {
            const child = entities[cid];
            const cp = child?.props || {};
            return React.createElement('tr', { key: cid, className: 'aide-mount-animation' },
              columns.map(col =>
                React.createElement('td', { key: col, className: 'aide-table__td aide-table__td--' + inferType(cp[col]) },
                  React.createElement(EditableField, { entityId: cid, field: col, value: cp[col], type: inferType(cp[col]) })
                )
              )
            );
          })
        )
      )
    )
  );
}

function ChecklistDisplay({ entity, entityId, children }) {
  const { entities } = useContext(EntityContext);
  const childIds = useChildren(entityId);
  const props = entity?.props || {};
  const title = props.title || props.name || '';

  if (childIds.length === 0) {
    return React.createElement(CardDisplay, { entity, entityId, children });
  }

  const completed = childIds.filter(cid => {
    const cp = entities[cid]?.props || {};
    return cp.done === true || cp.checked === true || cp.completed === true;
  }).length;

  return React.createElement('div', { className: 'aide-mount-animation' },
    title && React.createElement('h3', { className: 'aide-heading aide-heading--3' },
      React.createElement(EditableField, { entityId, field: 'title', value: title })
    ),
    React.createElement('div', { className: 'aide-checklist' },
      childIds.map(cid => {
        const child = entities[cid];
        const cp = child?.props || {};
        const done = cp.done === true || cp.checked === true || cp.completed === true;
        const label = cp.task || cp.label || cp.name || cid;
        const labelField = cp.task !== undefined ? 'task' : (cp.label !== undefined ? 'label' : 'name');

        return React.createElement('div', { key: cid, className: 'aide-checklist__item aide-mount-animation' },
          React.createElement(EditableField, { entityId: cid, field: 'done', value: done, type: 'boolean' }),
          React.createElement('span', {
            className: 'aide-checklist__label' + (done ? ' aide-checklist__label--done' : '')
          },
            React.createElement(EditableField, { entityId: cid, field: labelField, value: label })
          )
        );
      })
    ),
    React.createElement('div', { className: 'aide-checklist__summary' },
      completed + ' of ' + childIds.length + ' complete'
    )
  );
}

function MetricDisplay({ entity, entityId }) {
  const props = entity?.props || {};
  const value = props.value ?? props.count ?? props.total ?? '';
  const label = props.label || props.name || '';
  const styles = applyStyles(entity?._styles);

  return React.createElement('div', { className: 'aide-metric aide-mount-animation', style: styles },
    React.createElement('span', { className: 'aide-metric__label' }, label),
    React.createElement('span', { className: 'aide-metric__value' },
      React.createElement(EditableField, { entityId, field: 'value', value, type: inferType(value) })
    )
  );
}

function TextDisplay({ entity, entityId }) {
  const props = entity?.props || {};
  const text = props.text || props.content || props.body || '';
  const field = props.text !== undefined ? 'text' : (props.content !== undefined ? 'content' : 'body');

  return React.createElement('p', { className: 'aide-text aide-mount-animation' },
    React.createElement(EditableField, { entityId, field, value: text })
  );
}

function ImageDisplay({ entity, entityId }) {
  const props = entity?.props || {};
  const src = props.src || props.url || '';
  const caption = props.caption || '';

  return React.createElement('figure', { className: 'aide-image aide-mount-animation' },
    src && React.createElement('img', { src, alt: caption, loading: 'lazy' }),
    caption && React.createElement('figcaption', { className: 'aide-image__caption' },
      React.createElement(EditableField, { entityId, field: 'caption', value: caption })
    )
  );
}

function FallbackDisplay({ entity, entityId, children }) {
  const props = entity?.props || {};
  const displayProps = Object.entries(props).filter(([k]) => !k.startsWith('_'));

  return React.createElement('div', { className: 'aide-card aide-mount-animation' },
    displayProps.map(([key, value]) =>
      React.createElement('div', { key, className: 'aide-card__field' },
        React.createElement('span', { className: 'aide-card__label' }, humanize(key)),
        React.createElement(EditableField, { entityId, field: key, value, type: inferType(value) })
      )
    ),
    children
  );
}

// ── Display Resolution ─────────────────────────────────
const DISPLAY_COMPONENTS = {
  page: PageDisplay,
  section: SectionDisplay,
  card: CardDisplay,
  list: ListDisplay,
  table: TableDisplay,
  checklist: ChecklistDisplay,
  metric: MetricDisplay,
  text: TextDisplay,
  image: ImageDisplay
};

function resolveDisplay(entity, childIds, entities) {
  const hint = (entity?.display || '').toLowerCase();
  if (DISPLAY_COMPONENTS[hint]) return DISPLAY_COMPONENTS[hint];

  // Heuristics based on props and children
  const props = entity?.props || {};

  // Image
  if (props.src || props.url) return ImageDisplay;

  // Checklist items have done/checked/completed - leaf nodes
  if (typeof props.done === 'boolean' || typeof props.checked === 'boolean' || typeof props.completed === 'boolean') {
    return CardDisplay;
  }

  // Metric (few fields with value/count)
  if ((props.value !== undefined || props.count !== undefined) && Object.keys(props).filter(k => !k.startsWith('_')).length <= 3) {
    return MetricDisplay;
  }

  // Text block
  if (props.text && Object.keys(props).filter(k => !k.startsWith('_')).length === 1) {
    return TextDisplay;
  }

  // If entity has multiple children, render as table or checklist
  if (childIds && childIds.length > 0 && entities) {
    const firstChild = entities[childIds[0]];
    const cp = firstChild?.props || {};
    // Check if children are checklist items
    if (typeof cp.done === 'boolean' || typeof cp.checked === 'boolean' || typeof cp.completed === 'boolean') {
      return ChecklistDisplay;
    }
    // Multiple children with props → table
    return TableDisplay;
  }

  return CardDisplay;
}

// ── AideEntity (recursive renderer) ────────────────────
function AideEntity({ entityId }) {
  const { entities } = useContext(EntityContext);
  const entity = useEntity(entityId);
  const childIds = useChildren(entityId);
  const Component = resolveDisplay(entity, childIds, entities);

  if (!entity || entity._removed) return null;

  // For table/checklist displays, don't recursively render children
  // - the component handles its own child rendering
  const shouldPassChildren = Component !== TableDisplay && Component !== ChecklistDisplay;
  const children = (shouldPassChildren && childIds.length > 0)
    ? childIds.map(id => React.createElement(AideEntity, { key: id, entityId: id }))
    : null;

  return React.createElement(Component, { entity, entityId }, children);
}

// ── PreviewApp (root) ──────────────────────────────────
function PreviewApp() {
  const meta = useMeta();
  const rootIds = useRootIds();

  return React.createElement('main', { className: 'aide-page' },
    meta.title && React.createElement('h1', { className: 'aide-heading aide-heading--1' }, meta.title),
    rootIds.length > 0
      ? rootIds.map(id => React.createElement(AideEntity, { key: id, entityId: id }))
      : React.createElement('p', { className: 'aide-empty' }, 'Send a message to get started.')
  );
}
'''
