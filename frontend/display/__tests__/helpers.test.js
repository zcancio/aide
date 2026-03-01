/**
 * Tests for helpers.js - utility functions
 */

const test = require('node:test');
const assert = require('node:assert');

test('helpers.js exports all required functions', () => {
  const helpers = require('../helpers.js');
  assert.strictEqual(typeof helpers.escapeHtml, 'function', 'escapeHtml should be a function');
  assert.strictEqual(typeof helpers.humanize, 'function', 'humanize should be a function');
  assert.strictEqual(typeof helpers.getChildren, 'function', 'getChildren should be a function');
  assert.strictEqual(typeof helpers.resolveDisplay, 'function', 'resolveDisplay should be a function');
});

test('escapeHtml: null returns empty string', () => {
  const { escapeHtml } = require('../helpers.js');
  assert.strictEqual(escapeHtml(null), '');
  assert.strictEqual(escapeHtml(undefined), '');
});

test('escapeHtml: escapes HTML special characters', () => {
  const { escapeHtml } = require('../helpers.js');
  assert.strictEqual(escapeHtml('<script>alert("xss")</script>'), '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;');
  assert.strictEqual(escapeHtml('"quotes"'), '&quot;quotes&quot;');
  assert.strictEqual(escapeHtml('&ampersand'), '&amp;ampersand');
});

test('escapeHtml: passes through clean strings', () => {
  const { escapeHtml } = require('../helpers.js');
  assert.strictEqual(escapeHtml('Hello World'), 'Hello World');
  assert.strictEqual(escapeHtml('123'), '123');
});

test('humanize: snake_case to Title Case', () => {
  const { humanize } = require('../helpers.js');
  assert.strictEqual(humanize('snake_case'), 'Snake Case');
  assert.strictEqual(humanize('first_name'), 'First Name');
  assert.strictEqual(humanize('user_id'), 'User Id');
});

test('humanize: already capitalized words preserved', () => {
  const { humanize } = require('../helpers.js');
  assert.strictEqual(humanize('already_Good'), 'Already Good');
});

test('getChildren: returns sorted child IDs by _created_seq', () => {
  const { getChildren } = require('../helpers.js');
  const entities = {
    'parent': { id: 'parent', _created_seq: 1 },
    'child-2': { id: 'child-2', parent: 'parent', _created_seq: 3 },
    'child-1': { id: 'child-1', parent: 'parent', _created_seq: 2 },
    'child-3': { id: 'child-3', parent: 'parent', _created_seq: 4 }
  };
  const children = getChildren(entities, 'parent');
  assert.deepStrictEqual(children, ['child-1', 'child-2', 'child-3']);
});

test('getChildren: excludes _removed entities', () => {
  const { getChildren } = require('../helpers.js');
  const entities = {
    'parent': { id: 'parent', _created_seq: 1 },
    'child-1': { id: 'child-1', parent: 'parent', _created_seq: 2 },
    'child-2': { id: 'child-2', parent: 'parent', _removed: true, _created_seq: 3 }
  };
  const children = getChildren(entities, 'parent');
  assert.deepStrictEqual(children, ['child-1']);
});

test('getChildren: returns empty array for no children', () => {
  const { getChildren } = require('../helpers.js');
  const entities = {
    'parent': { id: 'parent', _created_seq: 1 }
  };
  const children = getChildren(entities, 'parent');
  assert.deepStrictEqual(children, []);
});

test('resolveDisplay: returns "image" for src prop', () => {
  const { resolveDisplay } = require('../helpers.js');
  const entity = { props: { src: 'https://example.com/img.png' } };
  assert.strictEqual(resolveDisplay(entity, [], {}), 'image');
});

test('resolveDisplay: returns "metric" for value prop', () => {
  const { resolveDisplay } = require('../helpers.js');
  const entity = { props: { value: 42 } };
  assert.strictEqual(resolveDisplay(entity, [], {}), 'metric');
});

test('resolveDisplay: returns "text" for text prop', () => {
  const { resolveDisplay } = require('../helpers.js');
  const entity = { props: { text: 'Hello world' } };
  assert.strictEqual(resolveDisplay(entity, [], {}), 'text');
});

test('resolveDisplay: returns "checklist" when first child has done prop', () => {
  const { resolveDisplay } = require('../helpers.js');
  const entity = { props: {} };
  const entities = {
    'child-1': { props: { done: false } }
  };
  assert.strictEqual(resolveDisplay(entity, ['child-1'], entities), 'checklist');
});

test('resolveDisplay: returns "table" for parent with children', () => {
  const { resolveDisplay } = require('../helpers.js');
  const entity = { props: {} };
  const entities = {
    'child-1': { props: { name: 'Alice' } }
  };
  assert.strictEqual(resolveDisplay(entity, ['child-1'], entities), 'table');
});

test('resolveDisplay: returns "card" as default', () => {
  const { resolveDisplay } = require('../helpers.js');
  const entity = { props: { foo: 'bar' } };
  assert.strictEqual(resolveDisplay(entity, [], {}), 'card');
});

test('resolveDisplay: explicit display hint overrides all inference', () => {
  const { resolveDisplay } = require('../helpers.js');
  const entity = { display: 'section', props: { text: 'Should not be text' } };
  assert.strictEqual(resolveDisplay(entity, [], {}), 'section');
});
