/**
 * useAide - React hook for AIde entity store state management
 * Manages entities, deltas, and snapshots
 */

import { useState } from 'react';
import { createStore, applyDelta, resetStore } from '../lib/entity-store.js';

export function useAide() {
  const [entityStore, setEntityStore] = useState(() => createStore());

  const handleDelta = (delta) => {
    setEntityStore((currentStore) => applyDelta(currentStore, delta));
  };

  const handleSnapshot = (deltas) => {
    // Apply all buffered deltas to build the full store
    setEntityStore(() => {
      let store = createStore();
      for (const delta of deltas) {
        store = applyDelta(store, delta);
      }
      return store;
    });
  };

  const resetState = () => {
    setEntityStore(resetStore());
  };

  return {
    entityStore,
    handleDelta,
    handleSnapshot,
    resetState,
  };
}
