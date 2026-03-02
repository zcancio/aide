/**
 * helpers.js — Utility functions for display rendering (ES module)
 */

export function escapeHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function humanize(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export function getChildren(entities, parentId) {
  return Object.entries(entities)
    .filter(([, e]) => e.parent === parentId && !e._removed)
    .sort(([, a], [, b]) => (a._created_seq || 0) - (b._created_seq || 0))
    .map(([id]) => id);
}

export function resolveDisplay(entity, childIds, entities) {
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
