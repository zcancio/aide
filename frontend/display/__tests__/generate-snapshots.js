/**
 * Generate snapshots from the current monolith
 * Run once to capture expected output
 */

const fs = require('fs');
const path = require('path');
const display = require('../index.js');
const { emptyStore, pokerLeagueStore, simpleTextStore, nestedStore } = require('./fixtures.js');

const snapshotsDir = path.join(__dirname, 'snapshots');
if (!fs.existsSync(snapshotsDir)) {
  fs.mkdirSync(snapshotsDir, { recursive: true });
}

const fixtures = {
  'empty': emptyStore,
  'poker-league': pokerLeagueStore,
  'simple-text': simpleTextStore,
  'nested': nestedStore
};

for (const [name, store] of Object.entries(fixtures)) {
  // HTML render
  const html = display.renderHtml(store);
  fs.writeFileSync(path.join(snapshotsDir, `${name}.html`), html, 'utf8');

  // Text render
  const text = display.renderTextCli(store);
  fs.writeFileSync(path.join(snapshotsDir, `${name}.txt`), text, 'utf8');

  // Document render
  const doc = display.renderDocument(store, {
    title: store.meta.title || 'Test',
    footer: 'Made with aide'
  });
  fs.writeFileSync(path.join(snapshotsDir, `${name}-document.html`), doc, 'utf8');

  console.log(`✓ Generated snapshots for ${name}`);
}

console.log('\nSnapshots generated successfully.');
