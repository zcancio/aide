/**
 * Tests for render-document.js - document publishing functions
 */

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const { emptyStore, pokerLeagueStore } = require('./fixtures.js');

test('render-document.js exports renderDocument function', () => {
  const renderDocument = require('../render-document.js');
  assert.strictEqual(typeof renderDocument.renderDocument, 'function', 'renderDocument should be a function');
});

test('renderDocument(pokerLeagueStore) matches snapshot', () => {
  const { renderDocument } = require('../render-document.js');
  const output = renderDocument(pokerLeagueStore, {
    title: 'Poker League',
    footer: 'Made with aide'
  });
  const snapshot = fs.readFileSync(path.join(__dirname, 'snapshots/poker-league-document.html'), 'utf8');
  assert.strictEqual(output, snapshot);
});

test('renderDocument(emptyStore) matches snapshot', () => {
  const { renderDocument } = require('../render-document.js');
  const output = renderDocument(emptyStore, {
    title: 'Test',
    footer: 'Made with aide'
  });
  const snapshot = fs.readFileSync(path.join(__dirname, 'snapshots/empty-document.html'), 'utf8');
  assert.strictEqual(output, snapshot);
});
