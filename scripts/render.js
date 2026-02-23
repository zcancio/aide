#!/usr/bin/env node
/**
 * render.js — Node subprocess renderer for AIde publish
 *
 * Reads JSON from stdin with format:
 * {
 *   "state": { "entities": {}, "rootIds": [], "meta": {} },
 *   "title": "Page Title",
 *   "description": "Optional description",
 *   "footer": "Optional footer text",
 *   "updatedAt": "Optional timestamp"
 * }
 *
 * Outputs full HTML document to stdout.
 */

const fs = require('fs');
const path = require('path');

// Load display.js module
const display = require(path.join(__dirname, '../frontend/display.js'));

// Read JSON input from stdin
let inputData = '';

process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => {
  inputData += chunk;
});

process.stdin.on('end', () => {
  try {
    const input = JSON.parse(inputData);

    // Extract parameters with defaults for missing properties
    const rawState = input.state || {};
    const store = {
      entities: rawState.entities || {},
      rootIds: rawState.rootIds || [],
      meta: rawState.meta || {}
    };
    const options = {
      title: input.title || store.meta.title || 'AIde',
      description: input.description || '',
      footer: input.footer || null,
      updatedAt: input.updatedAt || null
    };

    // Render document
    const html = display.renderDocument(store, options);

    // Output to stdout
    process.stdout.write(html);
    process.exit(0);
  } catch (error) {
    process.stderr.write(`Render error: ${error.message}\n`);
    process.exit(1);
  }
});
