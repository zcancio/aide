/**
 * Tests for module isolation boundaries
 */

const test = require('node:test');
const assert = require('node:assert');

test('render-text.js does NOT export renderHtml or RENDERER_CSS', () => {
  const renderText = require('../render-text.js');
  assert.strictEqual(renderText.renderHtml, undefined, 'render-text should not export renderHtml');
  assert.strictEqual(renderText.RENDERER_CSS, undefined, 'render-text should not export RENDERER_CSS');
});

test('render-html.js does NOT export renderTextCli', () => {
  const renderHtml = require('../render-html.js');
  assert.strictEqual(renderHtml.renderTextCli, undefined, 'render-html should not export renderTextCli');
});

test('helpers.js does NOT export any render functions', () => {
  const helpers = require('../helpers.js');
  assert.strictEqual(helpers.renderHtml, undefined, 'helpers should not export renderHtml');
  assert.strictEqual(helpers.renderTextCli, undefined, 'helpers should not export renderTextCli');
  assert.strictEqual(helpers.renderDocument, undefined, 'helpers should not export renderDocument');
});

test('tokens.js does NOT export any functions', () => {
  const tokens = require('../tokens.js');
  const keys = Object.keys(tokens);
  const functions = keys.filter(k => typeof tokens[k] === 'function');
  assert.strictEqual(functions.length, 0, 'tokens should only export CSS string, no functions');
});
