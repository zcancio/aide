/**
 * display.js — Universal Renderer for AIde (Browser-compatible standalone bundle)
 *
 * This is a standalone UMD file for browser usage. For Node development,
 * see display/ directory which contains the modular structure:
 * - display/tokens.css + tokens.js — CSS design tokens
 * - display/helpers.js — Utility functions
 * - display/render-html.js — HTML rendering
 * - display/render-text.js — CLI text rendering
 * - display/render-document.js — Document publishing
 * - display/index.js — Node re-export
 *
 * Both produce byte-identical output (verified via tests in display/__tests__/).
 *
 * Usage:
 * - Browser: <script src="/static/display.js"> → window.display.renderHtml(store)
 * - Node: require('./display.js') → module.exports.renderHtml(store)
 * - Node (modular): require('./display/index.js') → same API, modular imports
 */

// ─────────────────────────────────────────────────────────────────────────────
// CSS — Single source of truth for renderer styles
// ─────────────────────────────────────────────────────────────────────────────

const RENDERER_CSS = `/* Import fonts for shadow DOM */
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Instrument+Sans:wght@400;500;600;700&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap');

/* CSS custom properties - scoped to preview root */
:host {
  /* Design system defaults */
  --font-serif: 'Playfair Display', Georgia, serif;
  --font-sans: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-heading: 'Instrument Sans', -apple-system, BlinkMacSystemFont, sans-serif;
  --text-primary: #2D2D2A;
  --text-secondary: #6B6963;
  --text-tertiary: #A8A5A0;
  --text-inverse: #F7F5F2;
  --bg-primary: #F7F5F2;
  --bg-secondary: #EFECEA;
  --bg-tertiary: #E6E3DF;
  --bg-elevated: #FFFFFF;
  /* Sage accent scale */
  --sage-50: #F0F3ED;
  --sage-100: #DDE4D7;
  --sage-200: #C2CCB8;
  --sage-300: #A3B394;
  --sage-400: #8B9E7C;
  --sage-500: #7C8C6E;
  --sage-600: #667358;
  --sage-700: #515C46;
  --sage-800: #3C4534;
  --sage-900: #282E23;
  --accent: var(--sage-500);
  --accent-hover: var(--sage-600);
  --accent-subtle: var(--sage-50);
  --accent-muted: var(--sage-100);
  --border-subtle: #E0DDD8;
  --border-default: #D4D1CC;
  --border-strong: #A8A5A0;
  --border: var(--border-default);
  --border-light: var(--border-subtle);
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --radius-full: 999px;
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

@media (prefers-color-scheme: dark) {
  :host {
    --text-primary: #E6E3DF;
    --text-secondary: #A8A5A0;
    --text-tertiary: #6B6963;
    --bg-primary: #1A1A18;
    --bg-secondary: #242422;
    --bg-tertiary: #2D2D2A;
    --bg-elevated: #242422;
    --border-subtle: #2F2F2B;
    --border-default: #3A3A36;
    --border-strong: #4A4A44;
    --border: var(--border-default);
    --border-light: var(--border-subtle);
    --accent-hover: #8FA07E;
  }
}

/* ── Base ── */
:host *, :host *::before, :host *::after { box-sizing: border-box; }

:host {
  font-family: var(--font-sans);
  font-size: 16px;
  font-weight: 400;
  line-height: 1.65;
  color: var(--text-primary);
  background: var(--bg-primary);
  -webkit-font-smoothing: antialiased;
}

:host .aide-page {
  max-width: 720px;
  margin: 0 auto;
  padding: 96px 40px;
}

/* Page header area: give intro content room before the first section divider */
:host .aide-page > .aide-heading--1,
body .aide-page > .aide-heading--1 {
  margin-bottom: var(--space-7);
}
:host .aide-page > .aide-text,
body .aide-page > .aide-text {
  margin-bottom: var(--space-4);
}
/* Ensure sections after intro content have proper top spacing */
:host .aide-page > .aide-text + .aide-section,
body .aide-page > .aide-text + .aide-section {
  margin-top: var(--space-4);
}

@media (max-width: 640px) {
  :host .aide-page {
    max-width: 520px;
    padding: 60px 20px;
  }
}

@media (prefers-reduced-motion: reduce) {
  :host *, :host *::before, :host *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}

/* ── Headings ── */
:host .aide-heading { margin-bottom: var(--space-6); }
:host .aide-heading--1 {
  font-family: var(--font-serif);
  font-size: clamp(36px, 4.5vw, 42px);
  font-weight: 700;
  line-height: 1.15;
  color: var(--text-primary);
  letter-spacing: -0.01em;
  margin-bottom: var(--space-9);
}
:host .aide-heading--2 {
  font-family: var(--font-serif);
  font-size: clamp(28px, 3.5vw, 32px);
  font-weight: 700;
  line-height: 1.25;
  color: var(--text-primary);
}
:host .aide-heading--3 {
  font-family: var(--font-heading);
  font-size: 18px;
  font-weight: 600;
  line-height: 1.4;
  color: var(--text-primary);
}

/* ── Text ── */
:host .aide-text {
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: 400;
  line-height: 1.65;
  color: var(--text-secondary);
  margin-bottom: var(--space-4);
  max-width: 65ch;
}
:host .aide-text a {
  color: var(--accent);
  text-decoration: underline;
  text-decoration-color: var(--border);
  text-underline-offset: 2px;
}
:host .aide-text a:hover {
  text-decoration-color: var(--accent);
}

/* ── Metric ── */
:host .aide-section__content > .aide-metric:first-child {
  /* When metrics are direct children, create an implicit flex row */
}
:host .aide-metric {
  display: inline-flex;
  align-items: baseline;
  gap: var(--space-2);
  margin-right: var(--space-4);
  margin-bottom: var(--space-3);
  padding: var(--space-2) var(--space-4);
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  line-height: 1.4;
}
:host .aide-metric__label {
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 400;
  color: var(--text-secondary);
  letter-spacing: 0.01em;
}
:host .aide-metric__label::after { content: ':'; }
:host .aide-metric__value {
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

/* ── Divider ── */
:host .aide-divider {
  border: none;
  border-top: 1px solid var(--border-light);
  margin: var(--space-6) 0;
}

/* ── Image ── */
:host .aide-image { margin: var(--space-5) 0; }
:host .aide-image img { max-width: 100%; height: auto; border-radius: var(--radius-md); display: block; }
:host .aide-image .aide-image__caption {
  font-size: 13px;
  color: var(--text-tertiary);
  padding-top: var(--space-2);
  line-height: 1.4;
}

/* ── Callout ── */
:host .aide-callout {
  background: var(--bg-secondary);
  border-left: 3px solid var(--border);
  padding: var(--space-4) var(--space-5);
  margin: var(--space-5) 0;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  font-size: 15px;
  line-height: 1.55;
  color: var(--text-secondary);
}

/* ── Columns ── */
:host .aide-columns {
  display: flex;
  gap: var(--space-6);
}
@media (max-width: 640px) {
  :host .aide-columns {
    flex-direction: column;
  }
}

/* ── Empty states ── */
:host .aide-empty {
  color: var(--text-tertiary);
  font-size: 15px;
  padding: var(--space-16) 0;
  text-align: center;
}
:host .aide-collection-empty {
  color: var(--text-tertiary);
  font-size: 14px;
  padding: var(--space-4) 0;
}

/* ── Highlight ── */
:host .aide-highlight {
  background-color: var(--accent-subtle);
}

/* ── List view ── */
:host .aide-list {
  list-style: none;
  padding: 0;
  margin: 0 0 var(--space-6);
}
:host .aide-list:last-child {
  margin-bottom: 0;
}
:host .aide-list__item {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--space-4);
  padding: var(--space-1) 0;
  font-size: 15px;
  line-height: 1.4;
}
:host .aide-list__item:last-child { }
:host .aide-list__left {
  font-weight: 500;
  font-size: 13px;
  color: var(--text-secondary);
  flex-shrink: 0;
}
:host .aide-list__right {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 400;
}

/* ── Table view ── */
:host .aide-table-wrap {
  overflow-x: auto;
  margin: var(--space-3) 0 var(--space-3);
}
:host .aide-table-wrap + .aide-table-wrap {
  margin-top: var(--space-6);
}
:host .aide-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 15px;
}
:host .aide-table__th {
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-secondary);
  text-align: left;
  padding: var(--space-3) var(--space-3);
  border-bottom: 2px solid var(--border-strong);
  background: var(--bg-tertiary);
  cursor: pointer;
  user-select: none;
  transition: color 0.15s;
}
:host .aide-table__th:hover {
  color: var(--text-secondary);
}
:host .aide-table__th--active {
  color: var(--text-primary);
}
:host .aide-table__sort-arrow {
  opacity: 0.3;
  margin-left: 4px;
}
:host .aide-table tbody tr:nth-child(even) {
  background: var(--bg-secondary);
}
:host .aide-table__td {
  padding: var(--space-3) var(--space-3);
  border-bottom: 1px solid var(--border-light);
  color: var(--text-secondary);
  vertical-align: top;
  font-size: 14px;
  line-height: 1.4;
}
:host .aide-table tbody tr:last-child .aide-table__td {
  border-bottom: none;
}
:host .aide-table__td--bool { text-align: center; }
:host .aide-table__td--int,
:host .aide-table__td--number,
:host .aide-table__td--float { text-align: right; font-variant-numeric: tabular-nums; }

/* ── Grid view ── */
:host .aide-grid {
  border-collapse: collapse;
  font-size: 13px;
}
:host .aide-grid__col-label,
:host .aide-grid__row-label {
  font-weight: 500;
  color: var(--text-tertiary);
  padding: var(--space-2);
  text-align: center;
}
:host .aide-grid__cell {
  border: 1px solid var(--border-light);
  padding: var(--space-2);
  text-align: center;
  min-width: 48px;
  min-height: 48px;
  vertical-align: middle;
}
:host .aide-grid__cell--filled {
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-weight: 500;
}
:host .aide-grid__cell--empty {
  color: var(--text-tertiary);
}

/* ── Group headers ── */
:host .aide-group { margin-bottom: var(--space-6); }
:host .aide-group__header {
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-tertiary);
  margin-bottom: var(--space-3);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--border-light);
}

/* ── Annotations ── */
:host .aide-annotations { margin-top: var(--space-10); }
:host .aide-annotation {
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--border-light);
}
:host .aide-annotation:last-child { border-bottom: none; }
:host .aide-annotation__text {
  font-size: 15px;
  color: var(--text-secondary);
  line-height: 1.5;
}
:host .aide-annotation__meta {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-left: var(--space-3);
}
:host .aide-annotation--pinned {
  border-left: 3px solid var(--accent);
  padding-left: var(--space-4);
}

/* ── Footer ── */
:host .aide-footer {
  margin-top: var(--space-12);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-light);
  font-size: 12px;
  color: var(--text-tertiary);
  text-align: center;
}
:host .aide-footer__link {
  color: var(--text-tertiary);
  text-decoration: none;
}
:host .aide-footer__link:hover {
  color: var(--text-secondary);
}

/* ── Card (React component) ── */
:host .aide-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: var(--space-4) var(--space-5);
  margin-bottom: var(--space-4);
}
/* Nested cards get indentation and subtle background */
:host .aide-card .aide-card {
  margin-top: var(--space-4);
  margin-left: var(--space-3);
  background: var(--bg-secondary);
  border-left: 3px solid var(--border-default);
}
:host .aide-card__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
  margin-bottom: var(--space-3);
}
:host .aide-card__field {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border-light);
  gap: var(--space-3);
}
:host .aide-card__field:last-child { border-bottom: none; }
:host .aide-card__label {
  color: var(--text-tertiary);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  flex-shrink: 0;
}
:host .aide-card__empty {
  color: var(--text-tertiary);
  font-size: 13px;
  font-style: italic;
  margin: 0;
}

/* ── Section (React component) ── */
:host .aide-section {
  margin-bottom: var(--space-4);
  padding-top: var(--space-7);
  padding-bottom: 0;
  border-top: 1px solid var(--border-default);
}
:host .aide-section:first-child {
  border-top: none;
  padding-top: 0;
}
:host .aide-section__title {
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 700;
  line-height: 1.25;
  color: var(--text-primary);
  margin-bottom: var(--space-5);
}
:host .aide-section__content {
  padding-top: var(--space-2);
}
/* Normalize first-child top spacing so all sections feel even */
:host .aide-section__content > :first-child {
  margin-top: 0;
}
/* Optical correction: bordered containers need extra air after section titles */
:host .aide-section__content > .aide-card:first-child,
:host .aide-section__content > .aide-checklist-container:first-child,
:host .aide-section__content > .aide-image:first-child,
:host .aide-section__content > .aide-metric:first-child {
  margin-top: var(--space-2);
}

/* ── Checklist (React component) ── */
:host .aide-checklist {
  list-style: none;
  padding: 0;
  margin-top: 0;
  margin-bottom: 0;
}
:host .aide-checklist__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-1);
}
/* Headings used as checklist titles need tighter bottom margin */
:host .aide-checklist-container > .aide-heading {
  margin-bottom: 0;
}
:host .aide-checklist__item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-1) 0;
  font-size: 14px;
  line-height: 1.5;
}
:host .aide-checklist__item:last-child { }
:host .aide-checklist__checkbox {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: var(--accent);
  flex-shrink: 0;
  margin-top: 3px;
}
:host .aide-checklist__label {
  font-weight: 500;
  color: var(--text-primary);
}
:host .aide-checklist__label--done {
  text-decoration: line-through;
  color: var(--text-tertiary);
}
:host .aide-checklist__summary {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-tertiary);
  padding: 0;
  margin-top: 0;
  margin-bottom: var(--space-7);
}

/* ── Editable field (React component) ── */
:host .editable-field {
  cursor: text;
  border-radius: 2px;
  padding: 1px 2px;
  margin: -1px -2px;
  transition: background-color 0.15s;
}
:host .editable-field:hover {
  background-color: rgba(0, 0, 0, 0.04);
}
:host .editable-field--empty {
  color: var(--text-tertiary);
}
:host .editable-input {
  font: inherit;
  color: inherit;
  background: var(--bg-elevated);
  border: 1px solid var(--accent);
  border-radius: var(--radius-sm);
  padding: 1px 4px;
  margin: -2px -5px;
  outline: none;
  min-width: 60px;
}

/* ── Mount animation ── */
:host .aide-mount-animation {
  animation: aide-fade-in 0.2s ease-out;
}
@keyframes aide-fade-in {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ── Nav Bar ── */
:host .aide-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 44px;
  background: var(--bg-elevated);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-bottom: 1px solid var(--border-default);
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-5);
  z-index: 200;
}

:host .aide-nav__back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border: none;
  background: none;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.15s;
}

:host .aide-nav__back:hover {
  color: var(--text-primary);
}

:host .aide-nav__title {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 55%;
}

:host .aide-nav__share {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border: none;
  background: none;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  border-radius: 6px;
}

:host .aide-nav__share:hover {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

/* ── Sticky Pill ── */
:host .aide-pill-container {
  position: fixed;
  top: 50px;
  left: 0;
  right: 0;
  z-index: 190;
  display: flex;
  justify-content: center;
  pointer-events: none;
}

:host .aide-pill {
  background: var(--bg-elevated);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid var(--border-default);
  border-radius: 999px;
  padding: 3px 14px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  white-space: nowrap;
  pointer-events: auto;
  animation: pillIn 0.15s ease-out;
}

@keyframes pillIn {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── Content offset for nav bar ── */
:host .aide-page-with-nav {
  padding-top: calc(44px + var(--space-7));
}

/* ── Legacy editable support (for vanilla JS fallback) ── */
:host .editable-value {
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 4px;
  display: inline;
}
:host .editable-value:hover {
  background: rgba(0, 0, 0, 0.04);
}

/* ── Fallback entity renderer ── */
:host .fb-entity {
  border-left: 2px solid var(--border);
  padding: 8px 0 8px 12px;
  margin: 4px 0;
}
:host .fb-header {
  display: flex;
  gap: 8px;
  align-items: baseline;
  margin-bottom: 4px;
}
:host .fb-id {
  font-weight: 600;
  color: var(--text-secondary);
  font-size: 12px;
}
:host .fb-display {
  font-size: 11px;
  color: var(--text-tertiary);
}
:host .fb-props {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 2px 12px;
  font-size: 12px;
  color: var(--text-secondary);
}
:host dt {
  font-weight: 500;
  color: var(--text-secondary);
}
:host dd {
  color: var(--text-secondary);
  word-break: break-word;
}`;

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

function escapeHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function humanize(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function getChildren(entities, parentId) {
  return Object.entries(entities)
    .filter(([, e]) => e.parent === parentId && !e._removed)
    .sort(([, a], [, b]) => (a._created_seq || 0) - (b._created_seq || 0))
    .map(([id]) => id);
}

// ─────────────────────────────────────────────────────────────────────────────
// Display Resolution
// ─────────────────────────────────────────────────────────────────────────────

function resolveDisplay(entity, childIds, entities) {
  const hint = (entity?.display || '').toLowerCase();
  if (hint) return hint;

  const props = entity?.props || {};
  if (props.src || props.url) return 'image';
  if (typeof props.done === 'boolean' || typeof props.checked === 'boolean') return 'card';
  if ((props.value !== undefined || props.count !== undefined) && Object.keys(props).filter(k => !k.startsWith('_')).length <= 3) return 'metric';
  if (props.text && Object.keys(props).filter(k => !k.startsWith('_')).length === 1) return 'text';

  if (childIds.length > 0) {
    const firstChild = entities[childIds[0]];
    const cp = firstChild?.props || {};
    if (typeof cp.done === 'boolean' || typeof cp.checked === 'boolean') return 'checklist';
    return 'table';
  }
  return 'card';
}

// ─────────────────────────────────────────────────────────────────────────────
// HTML Renderers
// ─────────────────────────────────────────────────────────────────────────────

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

function renderPage(entity, childIds, entities) {
  const props = entity.props || {};
  const title = props.title || props.name || '';
  const titleField = props.title !== undefined ? 'title' : 'name';
  const children = childIds.length > 0
    ? childIds.map(id => renderEntity(id, entities)).join('')
    : '<p class="aide-empty">Send a message to get started.</p>';
  return `<div class="aide-page">
    ${title ? `<h1 class="aide-heading aide-heading--1 editable-field" data-entity-id="${entity.id}" data-field="${titleField}">${escapeHtml(title)}</h1>` : ''}
    ${children}
  </div>`;
}

function renderSection(entity, childIds, entities) {
  const props = entity.props || {};
  const title = props.title || props.name || 'Section';
  const titleField = props.title !== undefined ? 'title' : 'name';
  const children = childIds.map(id => renderEntity(id, entities)).join('');
  return `<div class="aide-section">
    <div class="aide-section__title editable-field" data-entity-id="${entity.id}" data-field="${titleField}">${escapeHtml(title)}</div>
    <div class="aide-section__content">${children || '<p class="aide-collection-empty">No items yet.</p>'}</div>
  </div>`;
}

function renderMetric(entity) {
  const props = entity.props || {};
  const label = props.label || props.name || 'Value';
  const value = props.value ?? props.count ?? '';
  const valueField = props.value !== undefined ? 'value' : 'count';
  return `<div class="aide-metric">
    <span class="aide-metric__label">${escapeHtml(label)}</span>
    <span class="aide-metric__value editable-field" data-entity-id="${entity.id}" data-field="${valueField}">${escapeHtml(value)}</span>
  </div>`;
}

function renderText(entity) {
  const props = entity.props || {};
  const text = props.text || props.content || props.body || '';
  const field = props.text !== undefined ? 'text' : (props.content !== undefined ? 'content' : 'body');
  return `<p class="aide-text editable-field" data-entity-id="${entity.id}" data-field="${field}">${escapeHtml(text)}</p>`;
}

function renderImage(entity) {
  const props = entity.props || {};
  const src = props.src || props.url || '';
  const alt = props.alt || '';
  const caption = props.caption || '';
  return `<div class="aide-image">
    <img src="${escapeHtml(src)}" alt="${escapeHtml(alt)}">
    ${caption ? `<div class="aide-image__caption editable-field" data-entity-id="${entity.id}" data-field="caption">${escapeHtml(caption)}</div>` : ''}
  </div>`;
}

function renderChecklist(entity, childIds, entities) {
  const props = entity.props || {};
  const title = props.title || props.name || '';
  const titleField = props.title !== undefined ? 'title' : 'name';

  const items = childIds.map(id => {
    const child = entities[id];
    if (!child) return '';
    const cp = child.props || {};
    const done = cp.done || cp.checked || false;
    const doneField = cp.done !== undefined ? 'done' : 'checked';
    const label = cp.task || cp.label || cp.name || cp.title || '';
    const labelField = cp.task !== undefined ? 'task' : (cp.label !== undefined ? 'label' : (cp.name !== undefined ? 'name' : 'title'));
    return `<li class="aide-checklist__item">
      <input type="checkbox" class="aide-checklist__checkbox" ${done ? 'checked' : ''} data-entity-id="${id}" data-field="${doneField}" data-type="boolean">
      <span class="aide-checklist__label ${done ? 'aide-checklist__label--done' : ''} editable-field" data-entity-id="${id}" data-field="${labelField}">${escapeHtml(label)}</span>
    </li>`;
  }).join('');

  const completed = childIds.filter(id => {
    const child = entities[id];
    const cp = child?.props || {};
    return cp.done === true || cp.checked === true;
  }).length;

  return `<div class="aide-checklist-container">
    ${title ? `<h3 class="aide-heading aide-heading--3 editable-field" data-entity-id="${entity.id}" data-field="${titleField}">${escapeHtml(title)}</h3>` : ''}
    <ul class="aide-checklist">${items}</ul>
    <div class="aide-checklist__summary">${completed} of ${childIds.length} complete</div>
  </div>`;
}

function renderTable(entity, childIds, entities) {
  if (childIds.length === 0) return '<p class="aide-collection-empty">No items yet.</p>';

  // Collect columns from all children
  const colSet = new Set();
  childIds.forEach(id => {
    const child = entities[id];
    if (!child) return;
    Object.keys(child.props || {}).filter(k => !k.startsWith('_')).forEach(k => colSet.add(k));
  });
  const cols = Array.from(colSet);

  const thead = `<tr>${cols.map(c => `<th class="aide-table__th">${escapeHtml(humanize(c))}</th>`).join('')}</tr>`;
  const tbody = childIds.map(id => {
    const child = entities[id];
    if (!child) return '';
    const cp = child.props || {};
    return `<tr>${cols.map(c => `<td class="aide-table__td"><span class="editable-field" data-entity-id="${id}" data-field="${c}">${escapeHtml(cp[c] ?? '')}</span></td>`).join('')}</tr>`;
  }).join('');

  return `<div class="aide-table-wrap">
    <table class="aide-table">
      <thead>${thead}</thead>
      <tbody>${tbody}</tbody>
    </table>
  </div>`;
}

function renderList(entity, childIds, entities) {
  const items = childIds.map(id => {
    const child = entities[id];
    if (!child) return '';
    const cp = child.props || {};

    // Primary (name/title) on left, secondary on right
    const primaryField = cp.name !== undefined ? 'name' : (cp.title !== undefined ? 'title' : null);
    const primaryValue = primaryField ? cp[primaryField] : '';
    const secondaryProps = Object.entries(cp).filter(([k]) => !k.startsWith('_') && k !== 'name' && k !== 'title');

    const rightHtml = primaryValue
      ? `<span class="aide-list__right editable-field" data-entity-id="${id}" data-field="${primaryField}">${escapeHtml(primaryValue)}</span>`
      : '';
    const leftHtml = secondaryProps.map(([k, v]) =>
      `<span class="aide-list__left editable-field" data-entity-id="${id}" data-field="${k}">${escapeHtml(v)}</span>`
    ).join(' ');

    return `<li class="aide-list__item">${leftHtml}${rightHtml}</li>`;
  }).join('');
  return `<ul class="aide-list">${items}</ul>`;
}

function renderCard(entity, childIds, entities) {
  const props = entity.props || {};
  const title = props.title || props.name || '';
  const titleField = props.title !== undefined ? 'title' : 'name';
  const displayProps = Object.entries(props).filter(([k]) => !k.startsWith('_') && k !== 'title' && k !== 'name');

  const fields = displayProps.map(([k, v]) => `
    <div class="aide-card__field">
      <span class="aide-card__label">${escapeHtml(humanize(k))}</span>
      <span class="editable-field" data-entity-id="${entity.id}" data-field="${k}">${escapeHtml(v)}</span>
    </div>
  `).join('');

  const children = childIds.map(id => renderEntity(id, entities)).join('');

  return `<div class="aide-card">
    ${title ? `<div class="aide-card__title editable-field" data-entity-id="${entity.id}" data-field="${titleField}">${escapeHtml(title)}</div>` : ''}
    ${fields}
    ${children}
  </div>`;
}

function buildNavBarHtml(pageTitle) {
  return `<nav class="aide-nav">
    <button class="aide-nav__back" onclick="history.replaceState({}, '', '/'); location.reload();">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/>
      </svg>
      Back
    </button>
    <div class="aide-nav__title">${escapeHtml(pageTitle)}</div>
    <button class="aide-nav__share" onclick="navigator.clipboard.writeText(window.location.href).then(() => alert('Link copied'))">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/>
        <polyline points="16 6 12 2 8 6"/>
        <line x1="12" y1="2" x2="12" y2="15"/>
      </svg>
      Share
    </button>
  </nav>`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Public API: renderHtml (for browser Shadow DOM)
// ─────────────────────────────────────────────────────────────────────────────

function renderHtml(store) {
  if (store.rootIds.length === 0 && Object.keys(store.meta).length === 0) {
    return '<div class="aide-page"><p class="aide-empty">Send a message to get started.</p></div>';
  }
  // Sort rootIds by _created_seq before rendering
  const sortedRootIds = [...store.rootIds].sort((a, b) => {
    const seqA = store.entities[a]?._created_seq || 0;
    const seqB = store.entities[b]?._created_seq || 0;
    return seqA - seqB;
  });
  // Always wrap in .aide-page for consistent padding/layout
  const content = sortedRootIds.map(id => renderEntity(id, store.entities)).join('');
  // Check if content already has a page wrapper
  if (content.trim().startsWith('<div class="aide-page">')) {
    return content;
  }
  return `<div class="aide-page">${content}</div>`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Public API: renderTextCli (for CLI terminal output)
// ─────────────────────────────────────────────────────────────────────────────

function renderTextCli(store) {
  const lines = [];

  // Title
  const title = store.meta?.title || 'Untitled';
  lines.push(title);
  lines.push('═'.repeat(Math.min(title.length, 60)));
  lines.push('');

  // Get root entities - handle both rootIds and root_ids
  const rootIds = store.rootIds || store.root_ids || Object.entries(store.entities || {})
    .filter(([, e]) => !e._removed && (e.parent === 'root' || e.parent === null || !e.parent))
    .sort((a, b) => (a[1]._created_seq || 0) - (b[1]._created_seq || 0))
    .map(([id]) => id);

  // Build parent->children map for entities without _children
  const childrenMap = {};
  for (const [id, entity] of Object.entries(store.entities || {})) {
    if (entity._removed) continue;
    const parent = entity.parent;
    if (parent && parent !== 'root') {
      if (!childrenMap[parent]) childrenMap[parent] = [];
      childrenMap[parent].push(id);
    }
  }

  // Render each root entity
  for (const id of rootIds) {
    const entity = store.entities[id];
    if (!entity || entity._removed) continue;

    const entityLines = renderEntityText(entity, store.entities, childrenMap);
    if (entityLines.length > 0) {
      lines.push(...entityLines);
      lines.push('');
    }
  }

  return lines.join('\n').trimEnd();
}

function renderEntityText(entity, entities, childrenMap) {
  const lines = [];
  const props = entity.props || {};
  const display = (entity.display || '').toLowerCase();
  const title = props.title || props.name || '';

  // Get children - use _children if available, otherwise use childrenMap
  const childIds = (entity._children || childrenMap[entity.id] || []).filter(id => {
    const child = entities[id];
    return child && !child._removed;
  });

  // Page - just render children (title already shown at top)
  if (display === 'page') {
    for (const cid of childIds) {
      const child = entities[cid];
      if (!child) continue;
      const childLines = renderEntityText(child, entities, childrenMap);
      if (childLines.length > 0) {
        lines.push(...childLines);
        lines.push('');
      }
    }
    return lines;
  }

  // Section - header with children
  if (display === 'section') {
    if (title) {
      lines.push(title);
      lines.push('─'.repeat(Math.min(title.length, 40)));
    }

    // Recursively render children
    for (const cid of childIds) {
      const child = entities[cid];
      if (!child) continue;
      const childLines = renderEntityText(child, entities, childrenMap);
      lines.push(...childLines);
    }
    return lines;
  }

  // Checklist container
  if (display === 'checklist') {
    if (title) {
      lines.push(title);
      lines.push('─'.repeat(Math.min(title.length, 40)));
    }
    for (const cid of childIds) {
      const child = entities[cid];
      if (!child) continue;
      const cp = child.props || {};
      const done = cp.done === true || cp.checked === true;
      const label = cp.task || cp.label || cp.name || cp.title || cp.item || cid;
      lines.push(`${done ? '✓' : '○'} ${label}`);
    }
    return lines;
  }

  // List
  if (display === 'list') {
    if (title) {
      lines.push(title);
    }
    const childLines = renderChildrenText(childIds, entities, childrenMap);
    lines.push(...childLines);
    return lines;
  }

  // Table
  if (display === 'table') {
    if (title) {
      lines.push(title);
    }
    const childLines = renderChildrenText(childIds, entities, childrenMap);
    lines.push(...childLines);
    return lines;
  }

  // Metric
  if (display === 'metric') {
    const label = props.label || title || '';
    const value = props.value ?? '';
    lines.push(`  ${label}: ${value}`);
    return lines;
  }

  // Text
  if (display === 'text') {
    const text = props.text || props.content || '';
    if (text) lines.push(text);
    return lines;
  }

  // Image
  if (display === 'image') {
    const caption = props.caption || props.alt || '';
    lines.push(`  [Image${caption ? ': ' + caption : ''}]`);
    return lines;
  }

  // Card or default - single entity with fields
  const displayProps = Object.entries(props)
    .filter(([k]) => !['title', 'name'].includes(k));

  if (title) {
    lines.push(`  ${title}`);
  }
  for (const [k, v] of displayProps) {
    lines.push(`\t${humanize(k)}: ${formatTextValue(v)}`);
  }

  return lines;
}

function renderChildrenText(childIds, entities, childrenMap) {
  if (childIds.length === 0) return [];

  // Collect all unique field keys across children
  const allKeys = new Set();
  for (const cid of childIds) {
    const child = entities[cid];
    if (!child) continue;
    Object.keys(child.props || {}).filter(k => !k.startsWith('_')).forEach(k => allKeys.add(k));
  }
  const keys = Array.from(allKeys);
  if (keys.length === 0) return [];

  // Build rows as arrays of formatted values
  const rows = [];
  for (const cid of childIds) {
    const child = entities[cid];
    if (!child) continue;
    const cp = child.props || {};
    const row = keys.map(k => `${humanize(k)}: ${formatTextValue(cp[k])}`);
    rows.push(row);
  }

  // Calculate max width for each column
  const colWidths = keys.map((_, i) => Math.max(...rows.map(row => row[i].length)));

  // Render with padded columns
  return rows.map(row => {
    const padded = row.map((cell, i) => cell.padEnd(colWidths[i]));
    return `  ${padded.join('  │  ')}`;
  });
}

function formatTextValue(val) {
  if (val === null || val === undefined) return '—';
  if (typeof val === 'boolean') return val ? 'Yes' : 'No';
  if (Array.isArray(val)) return val.join(', ');
  return String(val);
}

// ─────────────────────────────────────────────────────────────────────────────
// Public API: renderDocument (for publish)
// ─────────────────────────────────────────────────────────────────────────────

function renderDocument(store, options) {
  options = options || {};
  const title = options.title || store.meta.title || 'AIde';
  const description = options.description || '';
  const footer = options.footer || null;
  const updatedAt = options.updatedAt || null;

  const bodyContent = renderHtml(store);

  // Replace :host selectors with body for standalone document
  const standaloneCss = RENDERER_CSS.replace(/:host\b/g, 'body');

  let footerHtml = '';
  if (footer) {
    footerHtml = `<div class="aide-footer">${escapeHtml(footer)}</div>`;
  }

  let updatedHtml = '';
  if (updatedAt) {
    updatedHtml = `<div class="aide-footer">Updated: ${escapeHtml(updatedAt)}</div>`;
  }

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(title)}</title>
  ${description ? `<meta name="description" content="${escapeHtml(description)}">` : ''}
  ${description ? `<meta property="og:title" content="${escapeHtml(title)}">` : ''}
  ${description ? `<meta property="og:description" content="${escapeHtml(description)}">` : ''}
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <style>
    ${standaloneCss}
  </style>
</head>
<body>
  ${bodyContent}
  ${footerHtml}
  ${updatedHtml}
</body>
</html>`;
}

// ─────────────────────────────────────────────────────────────────────────────
// UMD Export
// ─────────────────────────────────────────────────────────────────────────────

// Browser: window.display = { renderHtml, ... }
if (typeof window !== 'undefined') {
  window.display = {
    resolveDisplay,
    renderHtml,
    renderTextCli,
    renderDocument,
    escapeHtml,
    humanize,
    getChildren,
    RENDERER_CSS
  };
}

// Node: module.exports = { renderHtml, ... }
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    resolveDisplay,
    renderHtml,
    renderTextCli,
    renderDocument,
    escapeHtml,
    humanize,
    getChildren,
    RENDERER_CSS
  };
}
