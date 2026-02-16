/**
 * AIde Engine - Smoke Test
 *
 * Verifies that the JS engine build is functional.
 * Tests the full cycle: empty state → events → reduce → render → parse
 */

const { test } = require('node:test');
const assert = require('node:assert');
const { emptyState, reduce, replay, render, parseAideHtml } = require('../builds/engine.js');

// Helper to create events
function makeEvent(seq, type, payload) {
  return {
    id: `evt_${seq}`,
    sequence: seq,
    timestamp: new Date().toISOString(),
    actor: 'test',
    source: 'test',
    type,
    payload,
  };
}

test('emptyState returns valid initial state', () => {
  const state = emptyState();

  assert.strictEqual(state.version, 1);
  assert.deepStrictEqual(state.collections, {});
  assert.deepStrictEqual(state.relationships, []);
  assert.ok('block_root' in state.blocks);
  assert.strictEqual(state.blocks.block_root.type, 'root');
});

test('reduce applies collection.create', () => {
  const state = emptyState();
  const event = makeEvent(1, 'collection.create', {
    id: 'tasks',
    name: 'Tasks',
    schema: {
      title: 'string',
      done: 'bool',
      due: 'date?',
    },
  });

  const result = reduce(state, event);

  assert.strictEqual(result.applied, true);
  assert.strictEqual(result.error, null);
  assert.ok('tasks' in result.snapshot.collections);
  assert.strictEqual(result.snapshot.collections.tasks.name, 'Tasks');
  assert.strictEqual(result.snapshot.collections.tasks.schema.title, 'string');
});

test('reduce applies entity.create', () => {
  let state = emptyState();

  // Create collection first
  state = reduce(state, makeEvent(1, 'collection.create', {
    id: 'tasks',
    name: 'Tasks',
    schema: { title: 'string', done: 'bool' },
  })).snapshot;

  // Create entity
  const result = reduce(state, makeEvent(2, 'entity.create', {
    collection: 'tasks',
    id: 'task_1',
    fields: { title: 'Buy milk', done: false },
  }));

  assert.strictEqual(result.applied, true);
  const entity = result.snapshot.collections.tasks.entities.task_1;
  assert.strictEqual(entity.title, 'Buy milk');
  assert.strictEqual(entity.done, false);
  assert.strictEqual(entity._removed, false);
});

test('reduce rejects entity.create for missing collection', () => {
  const state = emptyState();
  const result = reduce(state, makeEvent(1, 'entity.create', {
    collection: 'nonexistent',
    id: 'item_1',
    fields: { name: 'Test' },
  }));

  assert.strictEqual(result.applied, false);
  assert.ok(result.error.includes('COLLECTION_NOT_FOUND'));
});

test('replay builds state from event sequence', () => {
  const events = [
    makeEvent(1, 'collection.create', {
      id: 'players',
      name: 'Players',
      schema: { name: 'string', score: 'int' },
    }),
    makeEvent(2, 'entity.create', {
      collection: 'players',
      id: 'player_1',
      fields: { name: 'Alice', score: 100 },
    }),
    makeEvent(3, 'entity.create', {
      collection: 'players',
      id: 'player_2',
      fields: { name: 'Bob', score: 85 },
    }),
    makeEvent(4, 'entity.update', {
      ref: 'players/player_1',
      fields: { score: 150 },
    }),
  ];

  const state = replay(events);

  assert.ok('players' in state.collections);
  const players = state.collections.players.entities;
  assert.strictEqual(Object.keys(players).length, 2);
  assert.strictEqual(players.player_1.score, 150);
  assert.strictEqual(players.player_2.score, 85);
});

test('render produces valid HTML', () => {
  let state = emptyState();

  // Build up state
  state = reduce(state, makeEvent(1, 'meta.update', {
    title: 'Test Page',
  })).snapshot;

  state = reduce(state, makeEvent(2, 'block.set', {
    id: 'block_heading',
    type: 'heading',
    parent: 'block_root',
    props: { level: 1, content: 'Welcome' },
  })).snapshot;

  const blueprint = { identity: 'test', voice: 'friendly', prompt: 'test' };
  const html = render(state, blueprint, []);

  assert.ok(html.includes('<!DOCTYPE html>'));
  assert.ok(html.includes('<title>Test Page</title>'));
  assert.ok(html.includes('Welcome'));
  assert.ok(html.includes('application/aide+json'));
  assert.ok(html.includes('application/aide-blueprint+json'));
});

test('parseAideHtml extracts embedded data', () => {
  const state = emptyState();
  const blueprint = { identity: 'test', voice: 'friendly', prompt: 'test' };
  const events = [
    makeEvent(1, 'meta.update', { title: 'Round Trip' }),
  ];

  const html = render(state, blueprint, events);
  const parsed = parseAideHtml(html);

  assert.strictEqual(parsed.blueprint.identity, 'test');
  assert.strictEqual(parsed.snapshot.version, 1);
  assert.ok(Array.isArray(parsed.events));
});

test('full round-trip: events → state → html → parse', () => {
  // Build complex state
  const events = [
    makeEvent(1, 'meta.update', { title: 'Poker League' }),
    makeEvent(2, 'collection.create', {
      id: 'roster',
      name: 'Players',
      schema: { name: 'string', status: 'string' },
    }),
    makeEvent(3, 'entity.create', {
      collection: 'roster',
      id: 'player_mike',
      fields: { name: 'Mike', status: 'active' },
    }),
    makeEvent(4, 'entity.create', {
      collection: 'roster',
      id: 'player_dave',
      fields: { name: 'Dave', status: 'active' },
    }),
    makeEvent(5, 'view.create', {
      id: 'roster_view',
      type: 'table',
      source: 'roster',
      config: { show_fields: ['name', 'status'] },
    }),
    makeEvent(6, 'block.set', {
      id: 'block_title',
      type: 'heading',
      parent: 'block_root',
      props: { level: 1, content: 'Poker League' },
    }),
    makeEvent(7, 'block.set', {
      id: 'block_roster',
      type: 'collection_view',
      parent: 'block_root',
      props: { view_id: 'roster_view' },
    }),
  ];

  const state = replay(events);
  const blueprint = { identity: 'poker', voice: 'casual', prompt: '' };
  const html = render(state, blueprint, events);

  // Parse it back
  const parsed = parseAideHtml(html);

  // Verify integrity
  assert.strictEqual(parsed.snapshot.meta.title, 'Poker League');
  assert.ok('roster' in parsed.snapshot.collections);
  assert.strictEqual(Object.keys(parsed.snapshot.collections.roster.entities).length, 2);
  assert.ok('roster_view' in parsed.snapshot.views);
  assert.strictEqual(parsed.events.length, events.length);
});

console.log('Smoke test complete.');
