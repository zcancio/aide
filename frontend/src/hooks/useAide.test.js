import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useAide } from './useAide';

// Mock engine functions
vi.mock('../engine', () => ({
  emptyState: () => ({
    schemas: {},
    entities: {},
  }),
  reduce: (snapshot, delta) => {
    // Simple mock reduce - just apply delta to snapshot
    if (delta.type === 'entity.create') {
      return {
        ...snapshot,
        entities: {
          ...snapshot.entities,
          [delta.entity_id]: delta.data,
        },
      };
    }
    if (delta.type === 'entity.update') {
      return {
        ...snapshot,
        entities: {
          ...snapshot.entities,
          [delta.entity_id]: {
            ...snapshot.entities[delta.entity_id],
            ...delta.data,
          },
        },
      };
    }
    return snapshot;
  },
}));

describe('useAide', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });

  it('returns emptyState() initially', () => {
    const { result } = renderHook(() => useAide());

    expect(result.current.entityState).toEqual({
      schemas: {},
      entities: {},
    });
    expect(result.current.messages).toEqual([]);
    expect(result.current.blueprint).toBeNull();
  });

  it('loadAide(id) fetches aide state from API, populates entityState + messages + blueprint', async () => {
    const mockAideData = {
      snapshot: {
        schemas: { Store: {} },
        entities: { store1: { _schema: 'Store', name: 'Test Store' } },
      },
      messages: [{ role: 'user', content: 'Hello' }],
      blueprint: { title: 'Test Aide' },
    };

    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockAideData,
    });

    const { result } = renderHook(() => useAide());

    await act(async () => {
      await result.current.loadAide('aide123');
    });

    await waitFor(() => {
      expect(result.current.entityState).toEqual(mockAideData.snapshot);
    });

    expect(result.current.messages).toEqual(mockAideData.messages);
    expect(result.current.blueprint).toEqual(mockAideData.blueprint);
    expect(global.fetch).toHaveBeenCalledWith('/api/aides/aide123');
  });

  it('applyDelta(delta) updates entityState via reducer, triggers re-render', async () => {
    const { result } = renderHook(() => useAide());

    act(() => {
      result.current.applyDelta({
        type: 'entity.create',
        entity_id: 'entity1',
        data: { name: 'New Entity' },
      });
    });

    expect(result.current.entityState.entities.entity1).toEqual({
      name: 'New Entity',
    });
  });

  it('sendMessage(text) posts to API, returns response', async () => {
    const mockResponse = { message_id: 'msg123', success: true };

    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const { result } = renderHook(() => useAide());

    // Set aide ID first
    await act(async () => {
      result.current.setAideId('aide456');
    });

    const response = await act(async () => {
      return result.current.sendMessage('Test message');
    });

    expect(response).toEqual(mockResponse);
    expect(global.fetch).toHaveBeenCalledWith('/api/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        aide_id: 'aide456',
        message: 'Test message',
      }),
    });
  });

  it('resetState() returns to emptyState()', () => {
    const { result } = renderHook(() => useAide());

    // First, add some state
    act(() => {
      result.current.applyDelta({
        type: 'entity.create',
        entity_id: 'entity1',
        data: { name: 'Test' },
      });
    });

    expect(result.current.entityState.entities.entity1).toBeDefined();

    // Now reset
    act(() => {
      result.current.resetState();
    });

    expect(result.current.entityState).toEqual({
      schemas: {},
      entities: {},
    });
    expect(result.current.messages).toEqual([]);
  });
});
