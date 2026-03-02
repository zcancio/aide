import { describe, it, expect } from 'vitest';
import { createStore, applyDelta, resetStore } from '../entity-store.js';

describe('entity-store', () => {
  it('createStore() returns { entities: {}, rootIds: [], meta: {} }', () => {
    const store = createStore();

    expect(store).toEqual({
      entities: {},
      rootIds: [],
      meta: {},
    });
  });

  it("applyDelta(store, { type: 'entity.create', id: 'e1', data: { id: 'e1', props: {name: 'A'} } }) — adds entity, adds to rootIds", () => {
    const store = createStore();
    const delta = {
      type: 'entity.create',
      id: 'e1',
      data: { id: 'e1', props: { name: 'A' } },
    };

    const newStore = applyDelta(store, delta);

    expect(newStore.entities['e1']).toEqual({ id: 'e1', props: { name: 'A' } });
    expect(newStore.rootIds).toContain('e1');
  });

  it('applyDelta with child entity (data has parent) — adds entity, does NOT add to rootIds', () => {
    const store = createStore();
    const delta = {
      type: 'entity.create',
      id: 'e2',
      data: { id: 'e2', parent: 'e1', props: { name: 'B' } },
    };

    const newStore = applyDelta(store, delta);

    expect(newStore.entities['e2']).toEqual({ id: 'e2', parent: 'e1', props: { name: 'B' } });
    expect(newStore.rootIds).not.toContain('e2');
  });

  it("applyDelta(store, { type: 'entity.update', id: 'e1', data: { props: {name: 'B'} } }) — merges data into existing entity", () => {
    let store = createStore();
    store = applyDelta(store, {
      type: 'entity.create',
      id: 'e1',
      data: { id: 'e1', props: { name: 'A', age: 10 } },
    });

    const newStore = applyDelta(store, {
      type: 'entity.update',
      id: 'e1',
      data: { props: { name: 'B' } },
    });

    expect(newStore.entities['e1']).toEqual({
      id: 'e1',
      props: { name: 'B' },
    });
  });

  it('applyDelta with entity.update on nonexistent entity — creates it', () => {
    const store = createStore();
    const delta = {
      type: 'entity.update',
      id: 'e3',
      data: { props: { name: 'C' } },
    };

    const newStore = applyDelta(store, delta);

    expect(newStore.entities['e3']).toEqual({ props: { name: 'C' } });
  });

  it("applyDelta(store, { type: 'entity.remove', id: 'e1' }) — removes entity from entities and rootIds", () => {
    let store = createStore();
    store = applyDelta(store, {
      type: 'entity.create',
      id: 'e1',
      data: { id: 'e1', props: { name: 'A' } },
    });

    const newStore = applyDelta(store, {
      type: 'entity.remove',
      id: 'e1',
    });

    expect(newStore.entities['e1']).toBeUndefined();
    expect(newStore.rootIds).not.toContain('e1');
  });

  it("applyDelta(store, { type: 'meta.update', data: { title: 'My Page' } }) — updates meta", () => {
    const store = createStore();
    const delta = {
      type: 'meta.update',
      data: { title: 'My Page' },
    };

    const newStore = applyDelta(store, delta);

    expect(newStore.meta).toEqual({ title: 'My Page' });
  });

  it('resetStore() returns empty store', () => {
    let store = createStore();
    store = applyDelta(store, {
      type: 'entity.create',
      id: 'e1',
      data: { id: 'e1', props: { name: 'A' } },
    });

    const emptyStore = resetStore();

    expect(emptyStore).toEqual({
      entities: {},
      rootIds: [],
      meta: {},
    });
  });

  it('Immutable: applyDelta returns a NEW object, does not mutate input store', () => {
    const store = createStore();
    const delta = {
      type: 'entity.create',
      id: 'e1',
      data: { id: 'e1', props: { name: 'A' } },
    };

    const newStore = applyDelta(store, delta);

    expect(newStore).not.toBe(store);
    expect(store.entities).toEqual({}); // Original unchanged
    expect(store.rootIds).toEqual([]); // Original unchanged
  });

  it('Immutable: original store.entities is not the same reference after applyDelta', () => {
    const store = createStore();
    const originalEntities = store.entities;

    const delta = {
      type: 'entity.create',
      id: 'e1',
      data: { id: 'e1', props: { name: 'A' } },
    };

    const newStore = applyDelta(store, delta);

    expect(newStore.entities).not.toBe(originalEntities);
  });
});
