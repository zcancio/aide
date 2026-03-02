/**
 * Tests for useAide hook
 * Tests entity store state management and delta/snapshot handling
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAide } from '../useAide.js';
import * as entityStore from '../../lib/entity-store.js';

vi.mock('../../lib/entity-store.js');

describe('useAide', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock createStore to return an empty store
    entityStore.createStore.mockReturnValue({
      entities: {},
      rootIds: [],
      meta: {},
    });

    // Mock applyDelta to return a modified store
    entityStore.applyDelta.mockImplementation((store, delta) => {
      if (delta.type === 'entity.create') {
        return {
          ...store,
          entities: { ...store.entities, [delta.id]: delta.data },
        };
      }
      return store;
    });

    // Mock resetStore to return empty store
    entityStore.resetStore.mockReturnValue({
      entities: {},
      rootIds: [],
      meta: {},
    });
  });

  it('returns initial state with empty entityStore and messages', () => {
    const { result } = renderHook(() => useAide());

    expect(result.current.entityStore).toEqual({
      entities: {},
      rootIds: [],
      meta: {},
    });
    expect(result.current.messages).toEqual([]);
    expect(result.current.isLoading).toBe(false);
  });

  it('handleDelta calls applyDelta and updates entityStore state', () => {
    const { result } = renderHook(() => useAide());

    const delta = {
      type: 'entity.create',
      id: 'e1',
      data: { title: 'Test Entity' },
    };

    act(() => {
      result.current.handleDelta(delta);
    });

    expect(entityStore.applyDelta).toHaveBeenCalledWith(
      expect.objectContaining({
        entities: {},
        rootIds: [],
        meta: {},
      }),
      delta
    );

    expect(result.current.entityStore.entities).toHaveProperty('e1');
  });

  it('handleSnapshot sets store directly with new entities, rootIds, and meta', () => {
    const { result } = renderHook(() => useAide());

    const newEntities = {
      e1: { title: 'Entity 1' },
      e2: { title: 'Entity 2' },
    };
    const newRootIds = ['e1'];
    const newMeta = { title: 'My Aide' };

    act(() => {
      result.current.handleSnapshot(newEntities, newRootIds, newMeta);
    });

    expect(result.current.entityStore).toEqual({
      entities: newEntities,
      rootIds: newRootIds,
      meta: newMeta,
    });
  });

  it('resetState returns store to empty using resetStore', () => {
    const { result } = renderHook(() => useAide());

    // First add some data
    act(() => {
      result.current.handleSnapshot(
        { e1: { title: 'Entity 1' } },
        ['e1'],
        { title: 'Aide' }
      );
    });

    expect(result.current.entityStore.entities).toHaveProperty('e1');

    // Then reset
    act(() => {
      result.current.resetState();
    });

    expect(entityStore.resetStore).toHaveBeenCalled();
    expect(result.current.entityStore).toEqual({
      entities: {},
      rootIds: [],
      meta: {},
    });
  });

  it('state updates trigger re-render', () => {
    const { result } = renderHook(() => useAide());

    const initialStore = result.current.entityStore;

    const delta = {
      type: 'entity.create',
      id: 'e1',
      data: { title: 'Test' },
    };

    act(() => {
      result.current.handleDelta(delta);
    });

    // Verify reference changed (new object)
    expect(result.current.entityStore).not.toBe(initialStore);
  });
});
