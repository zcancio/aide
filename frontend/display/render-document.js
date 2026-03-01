/**
 * render-document.js — Standalone HTML document rendering for publishing
 */

const { renderHtml } = require('./render-html.js');
const { RENDERER_CSS } = require('./tokens.js');
const { escapeHtml } = require('./helpers.js');

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

module.exports = {
  renderDocument
};
