/**
 * tokens.js — CSS design tokens export
 * Exports RENDERER_CSS string for use in JavaScript
 */

const fs = require('fs');
const path = require('path');

// Read CSS file inline for Node.js
const RENDERER_CSS = fs.readFileSync(path.join(__dirname, 'tokens.css'), 'utf8');

module.exports = {
  RENDERER_CSS
};
