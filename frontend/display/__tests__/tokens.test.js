/**
 * Tests for tokens.js - CSS design tokens export
 */

const test = require('node:test');
const assert = require('node:assert');

test('tokens.js exports RENDERER_CSS as non-empty string', () => {
  const tokens = require('../tokens.js');
  assert.ok(tokens.RENDERER_CSS, 'RENDERER_CSS should be defined');
  assert.strictEqual(typeof tokens.RENDERER_CSS, 'string', 'RENDERER_CSS should be a string');
  assert.ok(tokens.RENDERER_CSS.length > 0, 'RENDERER_CSS should not be empty');
});

test('RENDERER_CSS contains :host (shadow DOM scoping)', () => {
  const tokens = require('../tokens.js');
  assert.ok(tokens.RENDERER_CSS.includes(':host'), 'Should contain :host selector');
});

test('RENDERER_CSS contains --font-serif design token', () => {
  const tokens = require('../tokens.js');
  assert.ok(tokens.RENDERER_CSS.includes('--font-serif: \'Playfair Display\''), 'Should contain font-serif token');
});

test('RENDERER_CSS contains --sage-500 color token', () => {
  const tokens = require('../tokens.js');
  assert.ok(tokens.RENDERER_CSS.includes('--sage-500: #7C8C6E'), 'Should contain sage-500 color');
});

test('RENDERER_CSS contains dark mode tokens', () => {
  const tokens = require('../tokens.js');
  assert.ok(tokens.RENDERER_CSS.includes('@media (prefers-color-scheme: dark)'), 'Should contain dark mode media query');
});

test('RENDERER_CSS contains component styles', () => {
  const tokens = require('../tokens.js');
  assert.ok(tokens.RENDERER_CSS.includes('.aide-table'), 'Should contain .aide-table styles');
  assert.ok(tokens.RENDERER_CSS.includes('.aide-card'), 'Should contain .aide-card styles');
  assert.ok(tokens.RENDERER_CSS.includes('.aide-checklist'), 'Should contain .aide-checklist styles');
});
