/**
 * render-text.js — CLI text rendering functions
 */

const { humanize } = require('./helpers.js');

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

module.exports = {
  renderTextCli
};
