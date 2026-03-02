/**
 * useAide - React hook for AIde entity store state management
 * Manages entities, deltas, snapshots, and messages
 */

import { useState } from 'react';
import { createStore, applyDelta, resetStore } from '../lib/entity-store.js';

export function useAide() {
  const [entityStore, setEntityStore] = useState(() => createStore());
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const handleDelta = (delta) => {
    setEntityStore((currentStore) => applyDelta(currentStore, delta));
  };

  const handleSnapshot = (entities, rootIds, meta) => {
    setEntityStore({
      entities,
      rootIds,
      meta,
    });
  };

  const resetState = () => {
    setEntityStore(resetStore());
    setMessages([]);
  };

  return {
    entityStore,
    messages,
    isLoading,
    handleDelta,
    handleSnapshot,
    resetState,
  };
}
