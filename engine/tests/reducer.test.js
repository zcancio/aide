/**
 * AIde Engine - Reducer Tests
 *
 * Ports key test cases from Python test suite.
 * Tests all 22 primitive types for the reducer.
 */

const { test, describe } = require('node:test');
const assert = require('node:assert');
const { emptyState, reduce } = require('../builds/engine.js');

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

// Fixtures
function stateWithCollection() {
  const result = reduce(emptyState(), makeEvent(1, 'collection.create', {
    id: 'grocery_list',
    name: 'Grocery List',
    schema: {
      name: 'string',
      store: 'string?',
      checked: 'bool',
    },
  }));
  assert.strictEqual(result.applied, true);
  return result.snapshot;
}

function stateWithEntity() {
  let state = stateWithCollection();
  const result = reduce(state, makeEvent(2, 'entity.create', {
    collection: 'grocery_list',
    id: 'item_milk',
    fields: { name: 'Milk', store: 'Whole Foods', checked: false },
  }));
  assert.strictEqual(result.applied, true);
  return result.snapshot;
}

function stateWithTwoEntities() {
  let state = stateWithEntity();
  const result = reduce(state, makeEvent(3, 'entity.create', {
    collection: 'grocery_list',
    id: 'item_eggs',
    fields: { name: 'Eggs', store: null, checked: false },
  }));
  assert.strictEqual(result.applied, true);
  return result.snapshot;
}

// ============================================================================
// 1. entity.create
// ============================================================================

describe('entity.create', () => {
  test('creates entity in collection', () => {
    const state = stateWithCollection();
    const result = reduce(state, makeEvent(2, 'entity.create', {
      collection: 'grocery_list',
      id: 'item_milk',
      fields: { name: 'Milk', store: 'Whole Foods', checked: false },
    }));

    assert.strictEqual(result.applied, true);
    assert.strictEqual(result.error, null);

    const entity = result.snapshot.collections.grocery_list.entities.item_milk;
    assert.strictEqual(entity.name, 'Milk');
    assert.strictEqual(entity.store, 'Whole Foods');
    assert.strictEqual(entity.checked, false);
    assert.strictEqual(entity._removed, false);
  });

  test('nullable fields default to null', () => {
    const state = stateWithCollection();
    const result = reduce(state, makeEvent(2, 'entity.create', {
      collection: 'grocery_list',
      id: 'item_bread',
      fields: { name: 'Bread', checked: false },
      // store (string?) not provided
    }));

    assert.strictEqual(result.applied, true);
    const entity = result.snapshot.collections.grocery_list.entities.item_bread;
    assert.strictEqual(entity.store, null);
  });

  test('rejects missing required field', () => {
    const state = stateWithCollection();
    const result = reduce(state, makeEvent(2, 'entity.create', {
      collection: 'grocery_list',
      id: 'item_bad',
      fields: { store: 'Trader Joes' },
      // missing name (required string) and checked (required bool)
    }));

    assert.strictEqual(result.applied, false);
    assert.ok(result.error.includes('REQUIRED_FIELD_MISSING'));
  });

  test('rejects type mismatch', () => {
    const state = stateWithCollection();
    const result = reduce(state, makeEvent(2, 'entity.create', {
      collection: 'grocery_list',
      id: 'item_bad',
      fields: { name: 123, checked: false }, // name should be string
    }));

    assert.strictEqual(result.applied, false);
    assert.ok(result.error.includes('TYPE_MISMATCH'));
  });
});

// ============================================================================
// 2. entity.update
// ============================================================================

describe('entity.update', () => {
  test('merges fields', () => {
    const state = stateWithEntity();
    const result = reduce(state, makeEvent(3, 'entity.update', {
      ref: 'grocery_list/item_milk',
      fields: { checked: true },
    }));

    assert.strictEqual(result.applied, true);
    const entity = result.snapshot.collections.grocery_list.entities.item_milk;
    assert.strictEqual(entity.checked, true);
    assert.strictEqual(entity.name, 'Milk'); // unchanged
    assert.strictEqual(entity.store, 'Whole Foods'); // unchanged
  });

  test('can set nullable to null', () => {
    const state = stateWithEntity();
    const result = reduce(state, makeEvent(3, 'entity.update', {
      ref: 'grocery_list/item_milk',
      fields: { store: null },
    }));

    assert.strictEqual(result.applied, true);
    const entity = result.snapshot.collections.grocery_list.entities.item_milk;
    assert.strictEqual(entity.store, null);
  });

  test('rejects nonexistent entity', () => {
    const state = stateWithCollection();
    const result = reduce(state, makeEvent(2, 'entity.update', {
      ref: 'grocery_list/nonexistent',
      fields: { checked: true },
    }));

    assert.strictEqual(result.applied, false);
    assert.ok(result.error.includes('ENTITY_NOT_FOUND'));
  });
});

// ============================================================================
// 3. entity.remove
// ============================================================================

describe('entity.remove', () => {
  test('soft deletes entity', () => {
    const state = stateWithEntity();
    const result = reduce(state, makeEvent(3, 'entity.remove', {
      ref: 'grocery_list/item_milk',
    }));

    assert.strictEqual(result.applied, true);
    const entity = result.snapshot.collections.grocery_list.entities.item_milk;
    assert.strictEqual(entity._removed, true);
    assert.strictEqual(entity.name, 'Milk'); // data preserved
  });
});

// ============================================================================
// 4. collection.create
// ============================================================================

describe('collection.create', () => {
  test('creates empty collection', () => {
    const result = reduce(emptyState(), makeEvent(1, 'collection.create', {
      id: 'tasks',
      name: 'Tasks',
      schema: {
        title: 'string',
        done: 'bool',
        due: 'date?',
      },
    }));

    assert.strictEqual(result.applied, true);
    const coll = result.snapshot.collections.tasks;
    assert.strictEqual(coll.name, 'Tasks');
    assert.strictEqual(coll.schema.title, 'string');
    assert.strictEqual(coll.schema.done, 'bool');
    assert.strictEqual(coll.schema.due, 'date?');
    assert.deepStrictEqual(coll.entities, {});
    assert.strictEqual(coll._removed, false);
  });

  test('rejects duplicate collection', () => {
    const state = stateWithCollection();
    const result = reduce(state, makeEvent(2, 'collection.create', {
      id: 'grocery_list', // already exists
      name: 'Another List',
      schema: { item: 'string' },
    }));

    assert.strictEqual(result.applied, false);
    assert.ok(result.error.includes('COLLECTION_ALREADY_EXISTS'));
  });
});

// ============================================================================
// 5. collection.update
// ============================================================================

describe('collection.update', () => {
  test('updates name and settings', () => {
    const state = stateWithCollection();
    const result = reduce(state, makeEvent(2, 'collection.update', {
      id: 'grocery_list',
      name: 'Weekly Groceries',
      settings: { default_store: 'Whole Foods' },
    }));

    assert.strictEqual(result.applied, true);
    const coll = result.snapshot.collections.grocery_list;
    assert.strictEqual(coll.name, 'Weekly Groceries');
    assert.strictEqual(coll.settings.default_store, 'Whole Foods');
  });
});

// ============================================================================
// 6. collection.remove
// ============================================================================

describe('collection.remove', () => {
  test('removes collection and entities', () => {
    const state = stateWithTwoEntities();
    const result = reduce(state, makeEvent(4, 'collection.remove', {
      id: 'grocery_list',
    }));

    assert.strictEqual(result.applied, true);
    const coll = result.snapshot.collections.grocery_list;
    assert.strictEqual(coll._removed, true);
    // All entities also removed
    for (const entity of Object.values(coll.entities)) {
      assert.strictEqual(entity._removed, true);
    }
  });
});

// ============================================================================
// 7. field.add
// ============================================================================

describe('field.add', () => {
  test('adds nullable field with backfill', () => {
    const state = stateWithTwoEntities();
    const result = reduce(state, makeEvent(4, 'field.add', {
      collection: 'grocery_list',
      name: 'category',
      type: 'string?',
      default: null,
    }));

    assert.strictEqual(result.applied, true);
    const schema = result.snapshot.collections.grocery_list.schema;
    assert.ok('category' in schema);
    assert.strictEqual(schema.category, 'string?');

    // Existing entities backfilled
    for (const entity of Object.values(result.snapshot.collections.grocery_list.entities)) {
      assert.strictEqual(entity.category, null);
    }
  });

  test('rejects required field without default on non-empty collection', () => {
    const state = stateWithTwoEntities();
    const result = reduce(state, makeEvent(4, 'field.add', {
      collection: 'grocery_list',
      name: 'priority',
      type: 'int', // required, no default
    }));

    assert.strictEqual(result.applied, false);
    assert.ok(result.error.includes('REQUIRED_FIELD_NO_DEFAULT'));
  });
});

// ============================================================================
// 8. field.update
// ============================================================================

describe('field.update', () => {
  test('renames field', () => {
    const state = stateWithTwoEntities();
    const result = reduce(state, makeEvent(4, 'field.update', {
      collection: 'grocery_list',
      name: 'store',
      rename: 'location',
    }));

    assert.strictEqual(result.applied, true);
    const schema = result.snapshot.collections.grocery_list.schema;
    assert.ok(!('store' in schema));
    assert.ok('location' in schema);

    // Entities updated too
    for (const entity of Object.values(result.snapshot.collections.grocery_list.entities)) {
      assert.ok(!('store' in entity));
      assert.ok('location' in entity);
    }
  });
});

// ============================================================================
// 9. field.remove
// ============================================================================

describe('field.remove', () => {
  test('removes field from schema and entities', () => {
    const state = stateWithTwoEntities();
    const result = reduce(state, makeEvent(4, 'field.remove', {
      collection: 'grocery_list',
      name: 'store',
    }));

    assert.strictEqual(result.applied, true);
    const schema = result.snapshot.collections.grocery_list.schema;
    assert.ok(!('store' in schema));

    for (const entity of Object.values(result.snapshot.collections.grocery_list.entities)) {
      assert.ok(!('store' in entity));
    }
  });
});

// ============================================================================
// 10-11. relationship.set, relationship.constrain
// ============================================================================

describe('relationship primitives', () => {
  test('creates relationship', () => {
    let state = emptyState();
    // Create two collections with entities
    state = reduce(state, makeEvent(1, 'collection.create', {
      id: 'players', name: 'Players', schema: { name: 'string' },
    })).snapshot;
    state = reduce(state, makeEvent(2, 'collection.create', {
      id: 'games', name: 'Games', schema: { date: 'date' },
    })).snapshot;
    state = reduce(state, makeEvent(3, 'entity.create', {
      collection: 'players', id: 'player_1', fields: { name: 'Alice' },
    })).snapshot;
    state = reduce(state, makeEvent(4, 'entity.create', {
      collection: 'games', id: 'game_1', fields: { date: '2026-03-01' },
    })).snapshot;

    const result = reduce(state, makeEvent(5, 'relationship.set', {
      from: 'players/player_1',
      to: 'games/game_1',
      type: 'hosting',
      cardinality: 'many_to_one',
    }));

    assert.strictEqual(result.applied, true);
    assert.strictEqual(result.snapshot.relationships.length, 1);
    assert.strictEqual(result.snapshot.relationships[0].type, 'hosting');
  });
});

// ============================================================================
// 12-14. block.set, block.remove, block.reorder
// ============================================================================

describe('block primitives', () => {
  test('creates block in tree', () => {
    const result = reduce(emptyState(), makeEvent(1, 'block.set', {
      id: 'block_title',
      type: 'heading',
      parent: 'block_root',
      props: { level: 1, content: 'My Page' },
    }));

    assert.strictEqual(result.applied, true);
    assert.ok('block_title' in result.snapshot.blocks);
    assert.strictEqual(result.snapshot.blocks.block_title.type, 'heading');
    assert.ok(result.snapshot.blocks.block_root.children.includes('block_title'));
  });

  test('updates existing block', () => {
    let state = reduce(emptyState(), makeEvent(1, 'block.set', {
      id: 'block_title', type: 'heading', parent: 'block_root',
      props: { level: 1, content: 'Original' },
    })).snapshot;

    const result = reduce(state, makeEvent(2, 'block.set', {
      id: 'block_title',
      props: { content: 'Updated' },
    }));

    assert.strictEqual(result.applied, true);
    assert.strictEqual(result.snapshot.blocks.block_title.props.content, 'Updated');
    assert.strictEqual(result.snapshot.blocks.block_title.type, 'heading'); // unchanged
  });

  test('removes block', () => {
    let state = reduce(emptyState(), makeEvent(1, 'block.set', {
      id: 'block_title', type: 'heading', parent: 'block_root',
      props: { level: 1, content: 'Test' },
    })).snapshot;

    const result = reduce(state, makeEvent(2, 'block.remove', {
      id: 'block_title',
    }));

    assert.strictEqual(result.applied, true);
    assert.ok(!('block_title' in result.snapshot.blocks));
    assert.ok(!result.snapshot.blocks.block_root.children.includes('block_title'));
  });

  test('cannot remove root', () => {
    const result = reduce(emptyState(), makeEvent(1, 'block.remove', {
      id: 'block_root',
    }));

    assert.strictEqual(result.applied, false);
    assert.ok(result.error.includes('CANT_REMOVE_ROOT'));
  });
});

// ============================================================================
// 15-17. view.create, view.update, view.remove
// ============================================================================

describe('view primitives', () => {
  test('creates view', () => {
    const state = stateWithCollection();
    const result = reduce(state, makeEvent(2, 'view.create', {
      id: 'grocery_view',
      type: 'list',
      source: 'grocery_list',
      config: { show_fields: ['name', 'checked'] },
    }));

    assert.strictEqual(result.applied, true);
    const view = result.snapshot.views.grocery_view;
    assert.strictEqual(view.type, 'list');
    assert.strictEqual(view.source, 'grocery_list');
  });

  test('updates view config', () => {
    let state = stateWithCollection();
    state = reduce(state, makeEvent(2, 'view.create', {
      id: 'grocery_view', type: 'list', source: 'grocery_list',
      config: { show_fields: ['name'] },
    })).snapshot;

    const result = reduce(state, makeEvent(3, 'view.update', {
      id: 'grocery_view',
      config: { show_fields: ['name', 'store'] },
    }));

    assert.strictEqual(result.applied, true);
    assert.deepStrictEqual(result.snapshot.views.grocery_view.config.show_fields, ['name', 'store']);
  });

  test('removes view', () => {
    let state = stateWithCollection();
    state = reduce(state, makeEvent(2, 'view.create', {
      id: 'grocery_view', type: 'list', source: 'grocery_list', config: {},
    })).snapshot;

    const result = reduce(state, makeEvent(3, 'view.remove', {
      id: 'grocery_view',
    }));

    assert.strictEqual(result.applied, true);
    assert.ok(!('grocery_view' in result.snapshot.views));
  });
});

// ============================================================================
// 18-19. style.set, style.set_entity
// ============================================================================

describe('style primitives', () => {
  test('sets global styles', () => {
    const result = reduce(emptyState(), makeEvent(1, 'style.set', {
      primary_color: '#1a365d',
      font_family: 'Georgia',
    }));

    assert.strictEqual(result.applied, true);
    assert.strictEqual(result.snapshot.styles.primary_color, '#1a365d');
    assert.strictEqual(result.snapshot.styles.font_family, 'Georgia');
  });

  test('sets entity styles', () => {
    const state = stateWithEntity();
    const result = reduce(state, makeEvent(3, 'style.set_entity', {
      ref: 'grocery_list/item_milk',
      styles: { highlight: true, bg_color: '#fef3c7' },
    }));

    assert.strictEqual(result.applied, true);
    const entity = result.snapshot.collections.grocery_list.entities.item_milk;
    assert.strictEqual(entity._styles.highlight, true);
    assert.strictEqual(entity._styles.bg_color, '#fef3c7');
  });
});

// ============================================================================
// 20-22. meta.update, meta.annotate, meta.constrain
// ============================================================================

describe('meta primitives', () => {
  test('updates meta properties', () => {
    const result = reduce(emptyState(), makeEvent(1, 'meta.update', {
      title: 'Poker League',
      visibility: 'unlisted',
    }));

    assert.strictEqual(result.applied, true);
    assert.strictEqual(result.snapshot.meta.title, 'Poker League');
    assert.strictEqual(result.snapshot.meta.visibility, 'unlisted');
  });

  test('appends annotation', () => {
    const result = reduce(emptyState(), makeEvent(1, 'meta.annotate', {
      note: 'League started.',
      pinned: false,
    }));

    assert.strictEqual(result.applied, true);
    assert.strictEqual(result.snapshot.annotations.length, 1);
    assert.strictEqual(result.snapshot.annotations[0].note, 'League started.');
  });

  test('stores constraint', () => {
    const state = stateWithCollection();
    const result = reduce(state, makeEvent(2, 'meta.constrain', {
      id: 'max_items',
      rule: 'collection_max_entities',
      collection: 'grocery_list',
      value: 50,
      message: 'Max 50 items',
    }));

    assert.strictEqual(result.applied, true);
    assert.strictEqual(result.snapshot.constraints.length, 1);
    assert.strictEqual(result.snapshot.constraints[0].value, 50);
  });
});

// ============================================================================
// Determinism
// ============================================================================

describe('determinism', () => {
  test('same events produce identical state', () => {
    const events = [
      makeEvent(1, 'collection.create', {
        id: 'items', name: 'Items', schema: { name: 'string' },
      }),
      makeEvent(2, 'entity.create', {
        collection: 'items', id: 'item_1', fields: { name: 'First' },
      }),
      makeEvent(3, 'entity.create', {
        collection: 'items', id: 'item_2', fields: { name: 'Second' },
      }),
    ];

    // Run twice
    let state1 = emptyState();
    let state2 = emptyState();
    for (const evt of events) {
      state1 = reduce(state1, evt).snapshot;
      state2 = reduce(state2, evt).snapshot;
    }

    assert.deepStrictEqual(state1, state2);
  });
});

console.log('Reducer tests complete.');
