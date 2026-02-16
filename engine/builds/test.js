/**
 * AIde Kernel — JavaScript Tests
 * Port of Python test cases for the JS/TS builds
 */

const engine = require('./engine.js');

// Test utilities
let testsPassed = 0;
let testsFailed = 0;

function assert(condition, message) {
  if (!condition) {
    console.error(`❌ FAIL: ${message}`);
    testsFailed++;
    throw new Error(message);
  }
  testsPassed++;
}

function assertEqual(actual, expected, message) {
  const actualStr = JSON.stringify(actual);
  const expectedStr = JSON.stringify(expected);
  if (actualStr !== expectedStr) {
    console.error(`❌ FAIL: ${message}`);
    console.error(`  Expected: ${expectedStr}`);
    console.error(`  Actual:   ${actualStr}`);
    testsFailed++;
    throw new Error(message);
  }
  testsPassed++;
}

function test(name, fn) {
  try {
    fn();
    console.log(`✅ PASS: ${name}`);
  } catch (e) {
    console.error(`❌ FAIL: ${name} - ${e.message}`);
  }
}

// ── Test Suite ──────────────────────────────────────────────────────────────

console.log('\n🧪 AIde Kernel - JavaScript Build Tests\n');

// Test 1: Empty State
test('Empty state initialization', () => {
  const state = engine.emptyState();
  assert(state.version === 1, 'Version should be 1');
  assert(Object.keys(state.collections).length === 0, 'Should have no collections');
  assert(state.blocks.block_root !== undefined, 'Should have block_root');
  assert(state.blocks.block_root.type === 'root', 'block_root should be root type');
});

// Test 2: Collection Create
test('Collection creation', () => {
  const state = engine.emptyState();
  const event = {
    id: 'evt_1',
    sequence: 1,
    timestamp: '2024-01-01T00:00:00Z',
    actor: 'user_123',
    source: 'test',
    type: 'collection.create',
    payload: {
      id: 'players',
      name: 'Players',
      schema: {
        name: 'string',
        score: 'int',
        active: 'bool'
      }
    }
  };

  const result = engine.reduce(state, event);
  assert(result.applied === true, 'Event should be applied');
  assert(result.error === null, 'Should have no error');
  assert(result.snapshot.collections.players !== undefined, 'Collection should exist');
  assertEqual(result.snapshot.collections.players.name, 'Players', 'Collection name should match');
});

// Test 3: Entity Create
test('Entity creation', () => {
  let state = engine.emptyState();

  // Create collection first
  const collEvent = {
    id: 'evt_1',
    sequence: 1,
    timestamp: '2024-01-01T00:00:00Z',
    actor: 'user_123',
    source: 'test',
    type: 'collection.create',
    payload: {
      id: 'players',
      schema: {
        name: 'string',
        score: 'int'
      }
    }
  };
  state = engine.reduce(state, collEvent).snapshot;

  // Create entity
  const entityEvent = {
    id: 'evt_2',
    sequence: 2,
    timestamp: '2024-01-01T00:00:01Z',
    actor: 'user_123',
    source: 'test',
    type: 'entity.create',
    payload: {
      collection: 'players',
      id: 'player_1',
      fields: {
        name: 'Alice',
        score: 100
      }
    }
  };

  const result = engine.reduce(state, entityEvent);
  assert(result.applied === true, 'Entity should be created');
  assert(result.snapshot.collections.players.entities.player_1 !== undefined, 'Entity should exist');
  assertEqual(result.snapshot.collections.players.entities.player_1.name, 'Alice', 'Entity name should match');
  assertEqual(result.snapshot.collections.players.entities.player_1.score, 100, 'Entity score should match');
});

// Test 4: Entity Update
test('Entity update', () => {
  let state = engine.emptyState();

  // Create collection
  state = engine.reduce(state, {
    id: 'evt_1', sequence: 1, timestamp: '2024-01-01T00:00:00Z',
    actor: 'user_123', source: 'test',
    type: 'collection.create',
    payload: { id: 'players', schema: { name: 'string', score: 'int' } }
  }).snapshot;

  // Create entity
  state = engine.reduce(state, {
    id: 'evt_2', sequence: 2, timestamp: '2024-01-01T00:00:01Z',
    actor: 'user_123', source: 'test',
    type: 'entity.create',
    payload: { collection: 'players', id: 'player_1', fields: { name: 'Alice', score: 100 } }
  }).snapshot;

  // Update entity
  const result = engine.reduce(state, {
    id: 'evt_3', sequence: 3, timestamp: '2024-01-01T00:00:02Z',
    actor: 'user_123', source: 'test',
    type: 'entity.update',
    payload: { ref: 'players/player_1', fields: { score: 150 } }
  });

  assert(result.applied === true, 'Update should be applied');
  assertEqual(result.snapshot.collections.players.entities.player_1.score, 150, 'Score should be updated');
  assertEqual(result.snapshot.collections.players.entities.player_1.name, 'Alice', 'Name should remain unchanged');
});

// Test 5: Replay
test('Replay events', () => {
  const events = [
    {
      id: 'evt_1', sequence: 1, timestamp: '2024-01-01T00:00:00Z',
      actor: 'user_123', source: 'test',
      type: 'collection.create',
      payload: { id: 'tasks', schema: { title: 'string', done: 'bool' } }
    },
    {
      id: 'evt_2', sequence: 2, timestamp: '2024-01-01T00:00:01Z',
      actor: 'user_123', source: 'test',
      type: 'entity.create',
      payload: { collection: 'tasks', id: 'task_1', fields: { title: 'Test task', done: false } }
    },
    {
      id: 'evt_3', sequence: 3, timestamp: '2024-01-01T00:00:02Z',
      actor: 'user_123', source: 'test',
      type: 'entity.update',
      payload: { ref: 'tasks/task_1', fields: { done: true } }
    }
  ];

  const state = engine.replay(events);
  assert(state.collections.tasks !== undefined, 'Collection should exist');
  assert(state.collections.tasks.entities.task_1 !== undefined, 'Entity should exist');
  assertEqual(state.collections.tasks.entities.task_1.done, true, 'Task should be marked done');
});

// Test 6: Type Validation
test('Type validation - reject invalid types', () => {
  const state = engine.emptyState();

  // Create collection with int field
  const createResult = engine.reduce(state, {
    id: 'evt_1', sequence: 1, timestamp: '2024-01-01T00:00:00Z',
    actor: 'user_123', source: 'test',
    type: 'collection.create',
    payload: { id: 'items', schema: { count: 'int' } }
  });

  // Try to create entity with string value for int field
  const result = engine.reduce(createResult.snapshot, {
    id: 'evt_2', sequence: 2, timestamp: '2024-01-01T00:00:01Z',
    actor: 'user_123', source: 'test',
    type: 'entity.create',
    payload: { collection: 'items', id: 'item_1', fields: { count: 'invalid' } }
  });

  assert(result.applied === false, 'Should reject invalid type');
  assert(result.error !== null, 'Should have error');
  assert(result.error.includes('TYPE_MISMATCH'), 'Should be type mismatch error');
});

// Test 7: Determinism
test('Determinism - same events produce same state', () => {
  const events = [
    {
      id: 'evt_1', sequence: 1, timestamp: '2024-01-01T00:00:00Z',
      actor: 'user_123', source: 'test',
      type: 'collection.create',
      payload: { id: 'items', schema: { name: 'string' } }
    },
    {
      id: 'evt_2', sequence: 2, timestamp: '2024-01-01T00:00:01Z',
      actor: 'user_123', source: 'test',
      type: 'entity.create',
      payload: { collection: 'items', id: 'item_1', fields: { name: 'Test' } }
    }
  ];

  const state1 = engine.replay(events);
  const state2 = engine.replay(events);

  assertEqual(state1, state2, 'Replaying same events should produce identical state');
});

// Test 8: Render - basic HTML generation
test('Render - generate HTML', () => {
  let state = engine.emptyState();
  state.meta.title = 'Test Page';

  const blueprint = { identity: 'test', voice: 'test voice', prompt: '' };
  const html = engine.render(state, blueprint, []);

  assert(html.includes('<!DOCTYPE html>'), 'Should have DOCTYPE');
  assert(html.includes('<title>Test Page</title>'), 'Should have title');
  assert(html.includes('application/aide+json'), 'Should embed state JSON');
});

// Test 9: Parse Aide HTML
test('Parse Aide HTML - extract embedded data', () => {
  const state = engine.emptyState();
  state.meta.title = 'Test';
  const blueprint = { identity: 'test', voice: 'test', prompt: '' };
  const events = [];

  const html = engine.render(state, blueprint, events);
  const parsed = engine.parseAideHtml(html);

  assert(parsed.snapshot !== null, 'Should extract snapshot');
  assert(parsed.blueprint !== null, 'Should extract blueprint');
  assertEqual(parsed.snapshot.meta.title, 'Test', 'Should parse title correctly');
});

// Test 10: Block operations
test('Block operations', () => {
  let state = engine.emptyState();

  // Add heading block
  const result = engine.reduce(state, {
    id: 'evt_1', sequence: 1, timestamp: '2024-01-01T00:00:00Z',
    actor: 'user_123', source: 'test',
    type: 'block.set',
    payload: {
      id: 'heading_1',
      type: 'heading',
      parent: 'block_root',
      props: { content: 'Welcome', level: 1 }
    }
  });

  assert(result.applied === true, 'Block should be created');
  assert(result.snapshot.blocks.heading_1 !== undefined, 'Block should exist');
  assertEqual(result.snapshot.blocks.heading_1.props.content, 'Welcome', 'Block content should match');
  assert(result.snapshot.blocks.block_root.children.includes('heading_1'), 'Block should be child of root');
});

// ── Summary ─────────────────────────────────────────────────────────────────

console.log(`\n${'='.repeat(60)}`);
console.log(`✅ Tests passed: ${testsPassed}`);
console.log(`❌ Tests failed: ${testsFailed}`);
console.log('='.repeat(60));

if (testsFailed > 0) {
  process.exit(1);
}
