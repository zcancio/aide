/**
 * Tests for render-text.js - CLI text rendering functions
 */

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const { emptyStore, pokerLeagueStore, simpleTextStore, nestedStore } = require('./fixtures.js');

test('render-text.js exports renderTextCli function', () => {
  const renderText = require('../render-text.js');
  assert.strictEqual(typeof renderText.renderTextCli, 'function', 'renderTextCli should be a function');
});

test('renderTextCli(pokerLeagueStore) matches snapshot', () => {
  const { renderTextCli } = require('../render-text.js');
  const output = renderTextCli(pokerLeagueStore);
  const snapshot = fs.readFileSync(path.join(__dirname, 'snapshots/poker-league.txt'), 'utf8');
  assert.strictEqual(output, snapshot);
});

test('renderTextCli(emptyStore) matches snapshot', () => {
  const { renderTextCli } = require('../render-text.js');
  const output = renderTextCli(emptyStore);
  const snapshot = fs.readFileSync(path.join(__dirname, 'snapshots/empty.txt'), 'utf8');
  assert.strictEqual(output, snapshot);
});

test('renderTextCli(simpleTextStore) matches snapshot', () => {
  const { renderTextCli } = require('../render-text.js');
  const output = renderTextCli(simpleTextStore);
  const snapshot = fs.readFileSync(path.join(__dirname, 'snapshots/simple-text.txt'), 'utf8');
  assert.strictEqual(output, snapshot);
});

test('renderTextCli(nestedStore) matches snapshot', () => {
  const { renderTextCli } = require('../render-text.js');
  const output = renderTextCli(nestedStore);
  const snapshot = fs.readFileSync(path.join(__dirname, 'snapshots/nested.txt'), 'utf8');
  assert.strictEqual(output, snapshot);
});
