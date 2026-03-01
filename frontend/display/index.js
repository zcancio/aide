/**
 * index.js — Backward-compatible UMD re-export
 * Preserves the original display.js public API
 */

const { RENDERER_CSS } = require('./tokens.js');
const { escapeHtml, humanize, getChildren, resolveDisplay } = require('./helpers.js');
const { renderHtml, buildNavBarHtml } = require('./render-html.js');
const { renderTextCli } = require('./render-text.js');
const { renderDocument } = require('./render-document.js');

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
