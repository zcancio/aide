/**
 * Display module entry point (ES module)
 *
 * Single source of truth for AIde rendering.
 * Used by:
 * - Vite SPA (direct import)
 * - Node scripts via esbuild-bundled display.js (UMD)
 */

// Re-export CSS
export { RENDERER_CSS } from './tokens.js';

// Re-export rendering functions
export { renderHtml } from './render-html.js';
export { renderDocument } from './render-document.js';
export { renderTextCli } from './render-text.js';

// Re-export helpers for UMD bundle
export { escapeHtml, humanize, getChildren, resolveDisplay } from './helpers.js';
