/**
 * Tests for useWebSocket hook
 * Tests WebSocket lifecycle, callbacks, and message sending
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useWebSocket } from '../useWebSocket.js';
import { AideWS } from '../../lib/ws.js';

vi.mock('../../lib/ws.js');

describe('useWebSocket', () => {
  let mockWsInstance;

  beforeEach(() => {
    vi.clearAllMocks();

    // Create mock instance with all methods
    mockWsInstance = {
      connect: vi.fn().mockResolvedValue(undefined),
      disconnect: vi.fn(),
      send: vi.fn(),
      onDelta: vi.fn(),
      onMeta: vi.fn(),
      onVoice: vi.fn(),
      onStatus: vi.fn(),
      onSnapshot: vi.fn(),
      onDirectEditError: vi.fn(),
    };

    // Mock the constructor to return our mock instance
    AideWS.mockImplementation(() => mockWsInstance);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('instantiates AideWS and connects on mount with aideId', async () => {
    const aideId = 'abc';
    const mockCallbacks = {
      onDelta: vi.fn(),
      onVoice: vi.fn(),
      onMeta: vi.fn(),
      onStatus: vi.fn(),
      onSnapshot: vi.fn(),
    };

    renderHook(() => useWebSocket(aideId, mockCallbacks));

    await waitFor(() => {
      expect(AideWS).toHaveBeenCalledTimes(1);
      expect(mockWsInstance.connect).toHaveBeenCalledWith(aideId);
    });
  });

  it('disconnects on unmount', async () => {
    const aideId = 'abc';
    const mockCallbacks = {
      onDelta: vi.fn(),
      onVoice: vi.fn(),
      onMeta: vi.fn(),
      onStatus: vi.fn(),
      onSnapshot: vi.fn(),
    };

    const { unmount } = renderHook(() => useWebSocket(aideId, mockCallbacks));

    await waitFor(() => {
      expect(mockWsInstance.connect).toHaveBeenCalledWith(aideId);
    });

    unmount();

    expect(mockWsInstance.disconnect).toHaveBeenCalled();
  });

  it('disconnects old connection and connects new when aideId changes', async () => {
    const mockCallbacks = {
      onDelta: vi.fn(),
      onVoice: vi.fn(),
      onMeta: vi.fn(),
      onStatus: vi.fn(),
      onSnapshot: vi.fn(),
    };

    const { rerender } = renderHook(
      ({ aideId }) => useWebSocket(aideId, mockCallbacks),
      { initialProps: { aideId: 'abc' } }
    );

    await waitFor(() => {
      expect(mockWsInstance.connect).toHaveBeenCalledWith('abc');
    });

    // Change aideId
    rerender({ aideId: 'def' });

    await waitFor(() => {
      expect(mockWsInstance.disconnect).toHaveBeenCalled();
      expect(mockWsInstance.connect).toHaveBeenCalledWith('def');
    });
  });

  it('registers onDelta, onVoice, onMeta, onStatus, onSnapshot callbacks', async () => {
    const aideId = 'abc';
    const mockCallbacks = {
      onDelta: vi.fn(),
      onVoice: vi.fn(),
      onMeta: vi.fn(),
      onStatus: vi.fn(),
      onSnapshot: vi.fn(),
    };

    renderHook(() => useWebSocket(aideId, mockCallbacks));

    await waitFor(() => {
      expect(mockWsInstance.onDelta).toHaveBeenCalledWith(mockCallbacks.onDelta);
      expect(mockWsInstance.onVoice).toHaveBeenCalledWith(mockCallbacks.onVoice);
      expect(mockWsInstance.onMeta).toHaveBeenCalledWith(mockCallbacks.onMeta);
      expect(mockWsInstance.onStatus).toHaveBeenCalledWith(mockCallbacks.onStatus);
      expect(mockWsInstance.onSnapshot).toHaveBeenCalledWith(mockCallbacks.onSnapshot);
    });
  });

  it('send calls ws.send with message', async () => {
    const aideId = 'abc';
    const mockCallbacks = {
      onDelta: vi.fn(),
      onVoice: vi.fn(),
      onMeta: vi.fn(),
      onStatus: vi.fn(),
      onSnapshot: vi.fn(),
    };

    const { result } = renderHook(() => useWebSocket(aideId, mockCallbacks));

    await waitFor(() => {
      expect(mockWsInstance.connect).toHaveBeenCalled();
    });

    const msg = { type: 'test', data: 'hello' };
    result.current.send(msg);

    expect(mockWsInstance.send).toHaveBeenCalledWith(msg);
  });

  it('sendDirectEdit calls ws.send with direct_edit message format', async () => {
    const aideId = 'abc';
    const mockCallbacks = {
      onDelta: vi.fn(),
      onVoice: vi.fn(),
      onMeta: vi.fn(),
      onStatus: vi.fn(),
      onSnapshot: vi.fn(),
    };

    const { result } = renderHook(() => useWebSocket(aideId, mockCallbacks));

    await waitFor(() => {
      expect(mockWsInstance.connect).toHaveBeenCalled();
    });

    const entityId = 'e1';
    const field = 'title';
    const value = 'New Title';

    result.current.sendDirectEdit(entityId, field, value);

    expect(mockWsInstance.send).toHaveBeenCalledWith({
      type: 'direct_edit',
      entity_id: entityId,
      field: field,
      value: value,
    });
  });

  it('exposes isConnected from WebSocket state', async () => {
    const aideId = 'abc';
    const mockCallbacks = {
      onDelta: vi.fn(),
      onVoice: vi.fn(),
      onMeta: vi.fn(),
      onStatus: vi.fn(),
      onSnapshot: vi.fn(),
    };

    const { result } = renderHook(() => useWebSocket(aideId, mockCallbacks));

    // Initial state should be false (not connected yet)
    expect(result.current.isConnected).toBe(false);

    await waitFor(() => {
      expect(mockWsInstance.connect).toHaveBeenCalled();
    });

    // After successful connection, should be true
    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });
  });
});
