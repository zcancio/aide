/**
 * Entity Store - Immutable state management for entities
 * All functions return new objects, never mutate inputs
 */

export function createStore() {
  return {
    entities: {},
    rootIds: [],
    meta: {},
  };
}

export function applyDelta(store, delta) {
  const { type, id, data } = delta;

  if (type === 'entity.create') {
    const newEntities = { ...store.entities, [id]: data || {} };
    const parent = (data || {}).parent;
    const isRoot = !parent || parent === 'root';
    const newRootIds = isRoot && !store.rootIds.includes(id)
      ? [...store.rootIds, id]
      : store.rootIds;

    return {
      ...store,
      entities: newEntities,
      rootIds: newRootIds,
    };
  }

  if (type === 'entity.update') {
    const existingEntity = store.entities[id];
    const newEntity = existingEntity
      ? { ...existingEntity, ...data }
      : data || {};

    const newEntities = {
      ...store.entities,
      [id]: newEntity,
    };

    return {
      ...store,
      entities: newEntities,
    };
  }

  if (type === 'entity.remove') {
    const newEntities = { ...store.entities };
    delete newEntities[id];

    const newRootIds = store.rootIds.filter((rootId) => rootId !== id);

    return {
      ...store,
      entities: newEntities,
      rootIds: newRootIds,
    };
  }

  if (type === 'meta.update') {
    return {
      ...store,
      meta: data || {},
    };
  }

  return store;
}

export function resetStore() {
  return createStore();
}
