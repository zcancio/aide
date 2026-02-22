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
    root_ids = [eid for eid, e in entities.items() if not e.get("_removed") and e.get("parent") in (None, "root", "")]

    # Use meta title or provided title
    page_title = title or meta.get("title") or "AIde"

    # Serialize for embedding
    entities_json = json.dumps(entities, ensure_ascii=False)
    meta_json = json.dumps(meta, ensure_ascii=False)
    root_ids_json = json.dumps(root_ids, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_escape_html(page_title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700\
&family=Instrument+Sans:wght@400;500;600;700\
&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap" rel="stylesheet">
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
    React.createElement(AppRoot)
  )
);
</script>
</body>
</html>"""


def _escape_html(text: str) -> str:
    """HTML-escape text for safe embedding."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ─────────────────────────────────────────────────────────────────────────────
# CSS - Exact copy from frontend/index.html renderer-css-template
# ─────────────────────────────────────────────────────────────────────────────

PREVIEW_CSS = """
/* CSS custom properties - design tokens per spec */
:root {
  /* Typography */
  --font-serif: 'Playfair Display', Georgia, serif;
  --font-sans: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-heading: 'Instrument Sans', -apple-system, BlinkMacSystemFont, sans-serif;

  /* Light mode (default) */
  --text-primary: #2D2D2A;
  --text-secondary: #6B6963;
  --text-tertiary: #A8A5A0;
  --text-inverse: #F7F5F2;
  --bg-primary: #F7F5F2;
  --bg-card: #FFFFFF;
  --bg-elevated: #FFFFFF;
  --border-subtle: #E0DDD8;
  --border-default: #D4D1CC;
  --border-strong: #A8A5A0;
  --sage-accent: #7C8C6E;
  --sage-hover: #667358;

  /* Derived */
  --border: var(--border-default);
  --border-light: var(--border-subtle);
  --accent: var(--sage-accent);

  /* Spacing */
  --nav-height: 44px;
}

@media (prefers-color-scheme: dark) {
  :root {
    --text-primary: #E6E3DF;
    --text-secondary: #A8A5A0;
    --text-tertiary: #6B6963;
    --bg-primary: #1A1A18;
    --bg-card: #242422;
    --bg-elevated: #2D2D2A;
    --border-light: #2F2F2B;
    --border-default: #3A3A36;
    --border-strong: #4A4A44;
    --sage-accent: #7C8C6E;
    --sage-hover: #8FA07E;
  }
}

/* ── Base ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: 400;
  line-height: 1.55;
  color: var(--text-primary);
  background: var(--bg-primary);
  -webkit-font-smoothing: antialiased;
}

.aide-page {
  max-width: 520px;
  margin: 0 auto;
  padding: 64px 20px 48px;
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}

/* ── Nav Bar ── */
.aide-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: var(--nav-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background: rgba(247, 245, 242, 0.9);
  backdrop-filter: blur(14px);
  border-bottom: 1px solid var(--border-light);
  z-index: 200;
}

@media (prefers-color-scheme: dark) {
  .aide-nav {
    background: rgba(26, 26, 24, 0.9);
  }
}

.aide-nav__back,
.aide-nav__share {
  font-size: 14px;
  color: var(--text-secondary);
  background: none;
  border: none;
  cursor: pointer;
  padding: 6px 8px;
  transition: color 0.15s;
}

.aide-nav__back:hover,
.aide-nav__share:hover {
  color: var(--text-primary);
}

.aide-nav__title {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  font-size: 14px;
  font-weight: 600;
  max-width: 55%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Sticky Section Pill ── */
.aide-pill-container {
  position: fixed;
  top: 50px;
  left: 0;
  right: 0;
  display: flex;
  justify-content: center;
  pointer-events: none;
  z-index: 150;
}

.aide-pill {
  background: rgba(239, 236, 234, 0.94);
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  padding: 3px 14px;
  font-size: 13px;
  font-weight: 600;
  pointer-events: auto;
  animation: pill-enter 0.15s ease-out;
}

@media (prefers-color-scheme: dark) {
  .aide-pill {
    background: rgba(36, 36, 34, 0.94);
  }
}

@keyframes pill-enter {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── Pencil FAB ── */
.aide-fab {
  position: fixed;
  bottom: 22px;
  right: 22px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--sage-accent);
  border: none;
  color: var(--text-inverse);
  font-size: 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  transition: all 0.15s;
  z-index: 50;
}

.aide-fab:hover {
  background: var(--sage-hover);
  transform: scale(1.06);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.3);
}

.aide-fab-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
}

.aide-fab-backdrop {
  position: absolute;
  inset: 0;
  background: transparent;
}

.aide-fab-input-bar {
  position: fixed;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  width: min(480px, calc(100vw - 32px));
  background: var(--bg-card);
  border-radius: 14px;
  padding: 12px;
  display: flex;
  gap: 8px;
  align-items: flex-end;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  animation: slide-up 0.15s ease-out;
}

@keyframes slide-up {
  from { opacity: 0; transform: translateX(-50%) translateY(20px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}

.aide-fab-textarea {
  flex: 1;
  font-family: var(--font-sans);
  font-size: 15px;
  line-height: 1.5;
  color: var(--text-primary);
  background: transparent;
  border: none;
  outline: none;
  resize: none;
  max-height: 100px;
  overflow-y: auto;
}

.aide-fab-textarea::placeholder {
  color: var(--text-tertiary);
}

.aide-fab-send {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: none;
  background: var(--bg-elevated);
  color: var(--text-tertiary);
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.aide-fab-send--active {
  background: var(--sage-accent);
  color: var(--text-inverse);
}

.aide-fab-send:hover:not(:disabled) {
  background: var(--sage-hover);
  color: var(--text-inverse);
}

.aide-fab-send:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

/* ── Section ── */
.aide-section {
  margin-bottom: 14px;
}

.aide-section__title {
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 700;
  line-height: 1.3;
  color: var(--text-primary);
  margin-bottom: 14px;
}

.aide-section__content {
  margin-top: 6px;
}

.aide-collection-empty {
  color: var(--text-tertiary);
  font-size: 14px;
}

/* ── Text ── */
.aide-text {
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: 400;
  line-height: 1.55;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

/* ── Metric ── */
.aide-metric {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  margin-right: 16px;
}
.aide-metric__label {
  font-size: 14px;
  font-weight: 400;
  color: var(--text-secondary);
}
.aide-metric__label::after { content: ':'; }
.aide-metric__value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}


/* ── Table ── */
.aide-table-container {
  margin-bottom: 12px;
}

.aide-subsection-title {
  font-family: var(--font-heading);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.aide-table-wrap {
  overflow-x: auto;
  margin: 4px 0;
}

.aide-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.aide-table__th {
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-tertiary);
  text-align: left;
  padding: 5px 8px;
  border-bottom: 1px solid var(--border-strong);
  cursor: pointer;
  user-select: none;
  transition: color 0.15s;
}

.aide-table__th:hover {
  color: var(--text-secondary);
}

.aide-table__th--active {
  color: var(--text-primary);
}

.aide-table__th--numeric {
  text-align: right;
}

.aide-table__sort-arrow {
  font-size: 10px;
  opacity: 1;
}

.aide-table__sort-arrow--inactive {
  opacity: 0.3;
}

.aide-table__td {
  padding: 5px 8px;
  border-bottom: 1px solid var(--border-light);
  color: var(--text-secondary);
  vertical-align: top;
}

.aide-table__td--numeric {
  text-align: right;
  font-variant-numeric: tabular-nums;
}


/* ── Footer ── */
.aide-footer {
  margin-top: 48px;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
  font-size: 12px;
  color: var(--text-tertiary);
  text-align: center;
}

/* ── Card ── */
.aide-card {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
}

.aide-card__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.aide-card__field {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 4px 0;
  border-bottom: 1px solid var(--border-light);
  gap: 12px;
}

.aide-card__field:last-child {
  border-bottom: none;
}

.aide-card__label {
  color: var(--text-tertiary);
  font-size: 12px;
  text-transform: uppercase;
  flex-shrink: 0;
}

.aide-card__value {
  color: var(--text-primary);
  font-size: 14px;
}


/* ── Checklist ── */
.aide-checklist-container {
  margin-bottom: 12px;
}

.aide-checklist__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.aide-checklist {
  list-style: none;
  padding: 0;
}

.aide-checklist__item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 5px 0;
  border-bottom: 1px solid var(--border-light);
  font-size: 14px;
  line-height: 1.5;
}

.aide-checklist__item:last-child {
  border-bottom: none;
}

.aide-checklist__checkbox {
  width: 15px;
  height: 15px;
  cursor: pointer;
  accent-color: var(--sage-accent);
  flex-shrink: 0;
  margin-top: 3px;
}

.aide-checklist__label {
  font-weight: 500;
  color: var(--text-primary);
}

.aide-checklist__label--done {
  text-decoration: line-through;
  color: var(--text-tertiary);
}

.aide-checklist__counter {
  font-size: 12px;
  color: var(--text-tertiary);
  padding-top: 6px;
}

"""


# ─────────────────────────────────────────────────────────────────────────────
# React Components - Exact copy from frontend/index.html REACT_COMPONENTS_TEMPLATE
# ─────────────────────────────────────────────────────────────────────────────

REACT_COMPONENTS = """
const { useState, useContext, createContext, useMemo, useCallback, useRef, useEffect } = React;

// ── Entity Context ────────────────────────────────────
const EntityContext = createContext({ entities: {}, meta: {}, rootIds: [] });

// ── Section Registry Context (for scroll tracking) ───
const SectionRegistryContext = createContext({ register: () => {}, unregister: () => {}, activeSection: null });

function useEntity(id) {
  const { entities } = useContext(EntityContext);
  return entities[id] || null;
}

function useChildren(parentId) {
  const { entities } = useContext(EntityContext);
  return Object.entries(entities)
    .filter(([, e]) => e.parent === parentId && !e._removed)
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

function displayProps(props) {
  if (!props) return {};
  const skip = new Set(['title', 'name']);
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
  children.forEach(id => {
    const entity = entities[id];
    const props = entity?.props || {};
    const displayed = displayProps(props);
    Object.keys(displayed).forEach(k => cols.add(k));
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

// ── Auto-table promotion detection ────────────────────
function shouldAutoTable(childIds, entities) {
  if (childIds.length < 2) return false;

  const fieldSets = childIds.map(id => {
    const e = entities[id];
    if (!e || e.display) return null; // skip explicit display hints
    const p = e.props || {};
    if (typeof p.done === 'boolean' || typeof p.checked === 'boolean') return null; // skip checklist items
    const fields = Object.keys(displayProps(p));
    return fields.length >= 2 ? new Set(fields) : null;
  });

  if (fieldSets.some(s => s === null)) return false;

  const first = fieldSets[0];
  const shared = [...first].filter(f => fieldSets.every(s => s.has(f)));
  return shared.length >= 2;
}

// ── Sorted Rows Hook (for Table/AutoTable) ────────────
function useSortedRows(childIds, entities) {
  const [sortCol, setSortCol] = useState(null);
  const [sortDir, setSortDir] = useState('asc');

  const onSort = useCallback((col) => {
    if (sortCol === col) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortCol(col);
      setSortDir('asc');
    }
  }, [sortCol]);

  const sorted = useMemo(() => {
    if (!sortCol) return childIds;
    return [...childIds].sort((a, b) => {
      const av = entities[a]?.props?.[sortCol];
      const bv = entities[b]?.props?.[sortCol];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      let cmp = typeof av === 'number' && typeof bv === 'number'
        ? av - bv
        : String(av).localeCompare(String(bv), undefined, { numeric: true, sensitivity: 'base' });
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [childIds, entities, sortCol, sortDir]);

  return { sorted, sortCol, sortDir, onSort };
}

// ── Display Components ─────────────────────────────────


function SectionDisplay({ entity, entityId }) {
  const { entities } = useContext(EntityContext);
  const { register, unregister } = useContext(SectionRegistryContext);
  const props = entity?.props || {};
  const title = props.title || props.name || 'Section';
  const childIds = useChildren(entityId);
  const sectionRef = useRef(null);

  // Register section for scroll tracking
  useEffect(() => {
    if (sectionRef.current) {
      register(entityId, title, sectionRef.current);
      return () => unregister(entityId);
    }
  }, [entityId, title, register, unregister]);

  // Check for auto-table promotion
  const useAutoTable = shouldAutoTable(childIds, entities);

  let children;
  if (useAutoTable) {
    children = React.createElement(AutoTable, { childIds });
  } else if (childIds.length > 0) {
    children = childIds.map(id => React.createElement(AideEntity, { key: id, entityId: id }));
  } else {
    children = null;
  }

  return React.createElement('div', {
    className: 'aide-section',
    ref: sectionRef
  },
    React.createElement('h2', { className: 'aide-section__title' }, title),
    React.createElement('div', { className: 'aide-section__content' },
      children || React.createElement('p', { className: 'aide-collection-empty' }, 'No items yet.')
    )
  );
}

function CardDisplay({ entity, entityId }) {
  const props = entity?.props || {};
  const title = props.title || props.name || '';
  const displayedProps = displayProps(props);
  const styles = applyStyles(entity?._styles);

  return React.createElement('div', { className: 'aide-card', style: styles },
    title && React.createElement('div', { className: 'aide-card__title' }, title),
    Object.entries(displayedProps).map(([key, value]) =>
      React.createElement('div', { key, className: 'aide-card__field' },
        React.createElement('span', { className: 'aide-card__label' }, humanize(key)),
        React.createElement('span', { className: 'aide-card__value' }, formatValue(value, inferType(value)))
      )
    )
  );
}


function TableDisplay({ entity, entityId }) {
  const { entities } = useContext(EntityContext);
  const childIds = useChildren(entityId);
  const props = entity?.props || {};
  const title = props.title || props.name || '';

  if (childIds.length === 0) {
    return React.createElement(CardDisplay, { entity, entityId });
  }

  const columns = deriveColumns(childIds, entities);
  const { sorted, sortCol, sortDir, onSort } = useSortedRows(childIds, entities);

  return React.createElement('div', { className: 'aide-table-container' },
    title && React.createElement('h3', { className: 'aide-subsection-title' }, title),
    React.createElement('div', { className: 'aide-table-wrap' },
      React.createElement('table', { className: 'aide-table' },
        React.createElement('thead', null,
          React.createElement('tr', null,
            columns.map(col => {
              const isActive = sortCol === col;
              const isNumeric = childIds.some(id => typeof entities[id]?.props?.[col] === 'number');
              const thClass = 'aide-table__th' +
                (isActive ? ' aide-table__th--active' : '') +
                (isNumeric ? ' aide-table__th--numeric' : '');
              return React.createElement('th', {
                key: col,
                className: thClass,
                onClick: () => onSort(col)
              },
                humanize(col),
                ' ',
                isActive
                  ? React.createElement('span', { className: 'aide-table__sort-arrow' },
                      sortDir === 'asc' ? '▲' : '▼')
                  : React.createElement('span', {
                      className: 'aide-table__sort-arrow aide-table__sort-arrow--inactive'
                    }, '▲')
              );
            })
          )
        ),
        React.createElement('tbody', null,
          sorted.map(cid => {
            const child = entities[cid];
            const cp = child?.props || {};
            return React.createElement('tr', { key: cid },
              columns.map(col => {
                const type = inferType(cp[col]);
                return React.createElement('td', {
                  key: col,
                  className: 'aide-table__td' + (type === 'number' ? ' aide-table__td--numeric' : '')
                },
                  formatValue(cp[col], type)
                );
              })
            );
          })
        )
      )
    )
  );
}

function AutoTable({ childIds }) {
  const { entities } = useContext(EntityContext);
  const columns = deriveColumns(childIds, entities);
  const { sorted, sortCol, sortDir, onSort } = useSortedRows(childIds, entities);

  return React.createElement('div', { className: 'aide-table-wrap' },
    React.createElement('table', { className: 'aide-table' },
      React.createElement('thead', null,
        React.createElement('tr', null,
          columns.map(col => {
            const isActive = sortCol === col;
            const isNumeric = childIds.some(id => typeof entities[id]?.props?.[col] === 'number');
            const thClass = 'aide-table__th' +
              (isActive ? ' aide-table__th--active' : '') +
              (isNumeric ? ' aide-table__th--numeric' : '');
            return React.createElement('th', {
              key: col,
              className: thClass,
              onClick: () => onSort(col)
            },
              humanize(col),
              ' ',
              isActive
                ? React.createElement('span', { className: 'aide-table__sort-arrow' },
                    sortDir === 'asc' ? '▲' : '▼')
                : React.createElement('span', {
                    className: 'aide-table__sort-arrow aide-table__sort-arrow--inactive'
                  }, '▲')
            );
          })
        )
      ),
      React.createElement('tbody', null,
        sorted.map(cid => {
          const child = entities[cid];
          const cp = child?.props || {};
          return React.createElement('tr', { key: cid },
            columns.map(col => {
              const type = inferType(cp[col]);
              return React.createElement('td', {
                key: col,
                className: 'aide-table__td' + (type === 'number' ? ' aide-table__td--numeric' : '')
              },
                formatValue(cp[col], type)
              );
            })
          );
        })
      )
    )
  );
}

function ChecklistDisplay({ entity, entityId }) {
  const { entities } = useContext(EntityContext);
  const childIds = useChildren(entityId);
  const props = entity?.props || {};
  const title = props.title || props.name || '';
  const [checkedItems, setCheckedItems] = useState({});

  if (childIds.length === 0) {
    return React.createElement(CardDisplay, { entity, entityId });
  }

  const done = childIds.filter(cid => {
    const cp = entities[cid]?.props || {};
    const localChecked = checkedItems[cid];
    return localChecked !== undefined ? localChecked : (cp.done === true || cp.checked === true);
  }).length;

  const total = childIds.length;

  return React.createElement('div', { className: 'aide-checklist-container' },
    title && React.createElement('h3', { className: 'aide-checklist__title' }, title),
    React.createElement('div', { className: 'aide-checklist' },
      childIds.map(cid => {
        const child = entities[cid];
        const cp = child?.props || {};
        const isChecked = checkedItems[cid] !== undefined
          ? checkedItems[cid]
          : (cp.done === true || cp.checked === true);
        const label = cp.task || cp.label || cp.name || cid;

        return React.createElement('div', { key: cid, className: 'aide-checklist__item' },
          React.createElement('input', {
            type: 'checkbox',
            className: 'aide-checklist__checkbox',
            checked: isChecked,
            onChange: (e) => {
              const newState = { ...checkedItems, [cid]: e.target.checked };
              setCheckedItems(newState);
            }
          }),
          React.createElement('span', {
            className: 'aide-checklist__label' + (isChecked ? ' aide-checklist__label--done' : '')
          }, label)
        );
      })
    ),
    React.createElement('div', { className: 'aide-checklist__counter' },
      done + '/' + total
    )
  );
}

function MetricDisplay({ entity, entityId }) {
  const props = entity?.props || {};
  const value = props.value ?? props.count ?? props.total ?? '';
  const label = props.label || props.name || '';
  const styles = applyStyles(entity?._styles);

  return React.createElement('div', { className: 'aide-metric', style: styles },
    React.createElement('span', { className: 'aide-metric__label' }, label),
    ' ',
    React.createElement('span', { className: 'aide-metric__value' }, String(value))
  );
}

function TextDisplay({ entity, entityId }) {
  const props = entity?.props || {};
  const text = props.text || props.content || props.body || '';

  return React.createElement('p', { className: 'aide-text' }, text);
}

// ── Display Resolution ─────────────────────────────────
const DISPLAY_COMPONENTS = {
  section: SectionDisplay,
  table: TableDisplay,
  checklist: ChecklistDisplay,
  metric: MetricDisplay,
  text: TextDisplay,
  card: CardDisplay
};

function resolveDisplay(entity, childIds, entities) {
  // 1. Explicit display hint
  const hint = (entity?.display || '').toLowerCase();
  if (DISPLAY_COMPONENTS[hint]) return DISPLAY_COMPONENTS[hint];

  // 2. Heuristic detection
  const props = entity?.props || {};
  const displayedProps = displayProps(props);
  const propCount = Object.keys(displayedProps).length;

  // 2a. Has value or count prop, ≤3 display props → Metric
  if ((props.value !== undefined || props.count !== undefined) && propCount <= 3) {
    return MetricDisplay;
  }

  // 2b. Has text prop, ≤1 display prop → Text
  if (props.text !== undefined && propCount <= 1) {
    return TextDisplay;
  }

  // 2c. Has children where first child has done or checked boolean → Checklist
  if (childIds && childIds.length > 0 && entities) {
    const firstChild = entities[childIds[0]];
    const cp = firstChild?.props || {};
    if (typeof cp.done === 'boolean' || typeof cp.checked === 'boolean') {
      return ChecklistDisplay;
    }

    // 2d. Has children with 2+ shared fields → Table (auto-promotion)
    // Note: auto-table promotion is handled at Section level
    // For explicit table display with children
    return TableDisplay;
  }

  // 2e. Fallback → Card
  return CardDisplay;
}

// ── AideEntity (recursive renderer) ────────────────────
function AideEntity({ entityId }) {
  const { entities } = useContext(EntityContext);
  const entity = useEntity(entityId);
  const childIds = useChildren(entityId);
  const Component = resolveDisplay(entity, childIds, entities);

  if (!entity || entity._removed) return null;

  // Section and Table/Checklist handle their own children
  const shouldPassChildren = Component !== SectionDisplay &&
    Component !== TableDisplay &&
    Component !== ChecklistDisplay;
  const children = (shouldPassChildren && childIds.length > 0)
    ? childIds.map(id => React.createElement(AideEntity, { key: id, entityId: id }))
    : null;

  return React.createElement(Component, { entity, entityId }, children);
}

// ── Nav Bar ─────────────────────────────────────────────
function NavBar({ title }) {
  return React.createElement('nav', { className: 'aide-nav' },
    React.createElement('button', { className: 'aide-nav__back' },
      React.createElement('span', null, '← Back')
    ),
    React.createElement('div', { className: 'aide-nav__title' }, title),
    React.createElement('button', { className: 'aide-nav__share' },
      React.createElement('span', null, 'Share ↑')
    )
  );
}

// ── Sticky Section Pill ─────────────────────────────────
function StickyPill({ sectionTitle }) {
  if (!sectionTitle) return null;
  return React.createElement('div', { className: 'aide-pill-container' },
    React.createElement('div', { className: 'aide-pill' }, sectionTitle)
  );
}

// ── Pencil FAB ─────────────────────────────────────────
function PencilFAB() {
  const [isOpen, setIsOpen] = useState(false);
  const [message, setMessage] = useState('');

  const handleSend = () => {
    if (message.trim()) {
      // In a real implementation, this would send the message
      console.log('Send message:', message);
      setMessage('');
      setIsOpen(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    } else if (e.key === 'Escape') {
      setIsOpen(false);
      setMessage('');
    }
  };

  if (isOpen) {
    return React.createElement('div', { className: 'aide-fab-overlay' },
      React.createElement('div', {
        className: 'aide-fab-backdrop',
        onClick: () => { setIsOpen(false); setMessage(''); }
      }),
      React.createElement('div', { className: 'aide-fab-input-bar' },
        React.createElement('textarea', {
          className: 'aide-fab-textarea',
          placeholder: 'Ask or edit...',
          value: message,
          autoFocus: true,
          onChange: (e) => setMessage(e.target.value),
          onKeyDown: handleKeyDown
        }),
        React.createElement('button', {
          className: 'aide-fab-send' + (message.trim() ? ' aide-fab-send--active' : ''),
          onClick: handleSend,
          disabled: !message.trim()
        }, '→')
      )
    );
  }

  return React.createElement('button', {
    className: 'aide-fab',
    onClick: () => setIsOpen(true)
  }, '✎');
}

// ── Footer ─────────────────────────────────────────────
function Footer() {
  return React.createElement('footer', { className: 'aide-footer' },
    'Made with aide'
  );
}

// ── Section Registry Provider ──────────────────────────
function SectionRegistry({ children }) {
  const [sections, setSections] = useState(new Map());
  const [activeSection, setActiveSection] = useState(null);

  const register = useCallback((id, title, ref) => {
    setSections(prev => new Map(prev).set(id, { title, ref }));
  }, []);

  const unregister = useCallback((id) => {
    setSections(prev => {
      const next = new Map(prev);
      next.delete(id);
      return next;
    });
  }, []);

  useEffect(() => {
    let rafId;
    const NAV_HEIGHT = 44;
    const threshold = NAV_HEIGHT + 6;

    const checkScroll = () => {
      let current = null;
      sections.forEach(({ title, ref }, id) => {
        const rect = ref.getBoundingClientRect();
        if (rect.top < threshold && rect.bottom > threshold + 24) {
          current = title;
        }
      });
      setActiveSection(current);
    };

    const handleScroll = () => {
      if (rafId) return;
      rafId = requestAnimationFrame(() => {
        checkScroll();
        rafId = null;
      });
    };

    window.addEventListener('scroll', handleScroll);
    checkScroll();

    return () => {
      window.removeEventListener('scroll', handleScroll);
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, [sections]);

  return React.createElement(SectionRegistryContext.Provider, {
    value: { register, unregister, activeSection }
  }, children);
}

// ── PreviewApp (root) ──────────────────────────────────
function PreviewApp() {
  const meta = useMeta();
  const rootIds = useRootIds();
  const { activeSection } = useContext(SectionRegistryContext);
  const title = meta.title || 'Untitled';

  return React.createElement(React.Fragment, null,
    React.createElement(NavBar, { title }),
    React.createElement(StickyPill, { sectionTitle: activeSection }),
    React.createElement('main', { className: 'aide-page' },
      rootIds.length > 0
        ? rootIds.map(id => React.createElement(AideEntity, { key: id, entityId: id }))
        : React.createElement('p', { className: 'aide-empty' }, 'Send a message to get started.')
    ),
    React.createElement(Footer),
    React.createElement(PencilFAB)
  );
}

// ── Root with Context Providers ────────────────────────
function AppRoot() {
  return React.createElement(SectionRegistry, null,
    React.createElement(PreviewApp)
  );
}
"""
