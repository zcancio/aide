/**
 * Display module entry point (ES module)
 *
 * Exports the renderer CSS and renderHtml function for use in the SPA.
 */

// Import CSS as raw string for Shadow DOM injection
import RENDERER_CSS from '../../../display/tokens.css?raw';

// Re-export rendering functions
export { renderHtml } from './render-html.js';
export { RENDERER_CSS };
