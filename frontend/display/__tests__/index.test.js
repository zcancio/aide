/**
 * Tests for index.js - backward-compatible UMD re-export
 */

const test = require('node:test');
const assert = require('node:assert');

test('index.js exports full public API', () => {
  const display = require('../index.js');
  assert.strictEqual(typeof display.resolveDisplay, 'function', 'resolveDisplay should be exported');
  assert.strictEqual(typeof display.renderHtml, 'function', 'renderHtml should be exported');
  assert.strictEqual(typeof display.renderTextCli, 'function', 'renderTextCli should be exported');
  assert.strictEqual(typeof display.renderDocument, 'function', 'renderDocument should be exported');
  assert.strictEqual(typeof display.escapeHtml, 'function', 'escapeHtml should be exported');
  assert.strictEqual(typeof display.humanize, 'function', 'humanize should be exported');
  assert.strictEqual(typeof display.getChildren, 'function', 'getChildren should be exported');
  assert.strictEqual(typeof display.RENDERER_CSS, 'string', 'RENDERER_CSS should be exported');
});
