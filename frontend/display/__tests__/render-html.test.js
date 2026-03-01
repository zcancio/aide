/**
 * Tests for render-html.js - HTML rendering functions
 */

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const { emptyStore, pokerLeagueStore, simpleTextStore, nestedStore } = require('./fixtures.js');

test('render-html.js exports required functions', () => {
  const renderHtml = require('../render-html.js');
  assert.strictEqual(typeof renderHtml.renderHtml, 'function', 'renderHtml should be a function');
  assert.strictEqual(typeof renderHtml.buildNavBarHtml, 'function', 'buildNavBarHtml should be a function');
});

test('renderHtml(pokerLeagueStore) matches snapshot', () => {
  const { renderHtml } = require('../render-html.js');
  const output = renderHtml(pokerLeagueStore);
  const snapshot = fs.readFileSync(path.join(__dirname, 'snapshots/poker-league.html'), 'utf8');
  assert.strictEqual(output, snapshot);
});

test('renderHtml(emptyStore) matches snapshot', () => {
  const { renderHtml } = require('../render-html.js');
  const output = renderHtml(emptyStore);
  const snapshot = fs.readFileSync(path.join(__dirname, 'snapshots/empty.html'), 'utf8');
  assert.strictEqual(output, snapshot);
});

test('renderHtml(simpleTextStore) matches snapshot', () => {
  const { renderHtml } = require('../render-html.js');
  const output = renderHtml(simpleTextStore);
  const snapshot = fs.readFileSync(path.join(__dirname, 'snapshots/simple-text.html'), 'utf8');
  assert.strictEqual(output, snapshot);
});

test('renderHtml(nestedStore) matches snapshot', () => {
  const { renderHtml } = require('../render-html.js');
  const output = renderHtml(nestedStore);
  const snapshot = fs.readFileSync(path.join(__dirname, 'snapshots/nested.html'), 'utf8');
  assert.strictEqual(output, snapshot);
});
