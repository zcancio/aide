/**
 * render-html.js — HTML rendering functions for browser Shadow DOM (ES module)
 */

import { escapeHtml, humanize, getChildren, resolveDisplay } from './helpers.js';

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

export function renderHtml(store) {
  if (!store || !store.entities) return '';

  if (store.rootIds.length === 0 && Object.keys(store.meta || {}).length === 0) {
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
