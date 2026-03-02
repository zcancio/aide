import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useWebSocket } from './useWebSocket';

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  constructor(url) {
    this.url = url;
    this.readyState = MockWebSocket.CONNECTING;
    this.onopen = null;
    this.onclose = null;
    this.onmessage = null;
    this.onerror = null;
    this.sentMessages = [];

    // Simulate connection opening
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 10);
  }

  send(data) {
    this.sentMessages.push(data);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }

  // Test helper to simulate receiving a message
  simulateMessage(data) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }));
    }
  }
}

describe('useWebSocket', () => {
  let mockWs;

  beforeEach(() => {
    vi.clearAllMocks();
    global.WebSocket = vi.fn((url) => {
      mockWs = new MockWebSocket(url);
      return mockWs;
    });
  });

  afterEach(() => {
    if (mockWs) {
      mockWs.close();
    }
  });

  it('connects to ws://host/ws/aide/{aideId} on mount', async () => {
    const { result } = renderHook(() => useWebSocket('aide123'));

    await waitFor(() => {
      expect(global.WebSocket).toHaveBeenCalledWith(
        expect.stringContaining('/ws/aide/aide123')
      );
    });
  });

  it('parses entity.create delta → calls applyDelta', async () => {
    const onDelta = vi.fn();

    renderHook(() =>
      useWebSocket('aide123', {
        onDelta,
      })
    );

    await waitFor(() => expect(mockWs.readyState).toBe(MockWebSocket.OPEN));

    act(() => {
      mockWs.simulateMessage({
        type: 'entity.create',
        entity_id: 'entity1',
        data: { name: 'Test' },
      });
    });

    await waitFor(() => {
      expect(onDelta).toHaveBeenCalledWith({
        type: 'entity.create',
        entity_id: 'entity1',
        data: { name: 'Test' },
      });
    });
  });

  it('parses entity.update delta → calls applyDelta', async () => {
    const onDelta = vi.fn();

    renderHook(() =>
      useWebSocket('aide123', {
        onDelta,
      })
    );

    await waitFor(() => expect(mockWs.readyState).toBe(MockWebSocket.OPEN));

    act(() => {
      mockWs.simulateMessage({
        type: 'entity.update',
        entity_id: 'entity1',
        data: { name: 'Updated' },
      });
    });

    await waitFor(() => {
      expect(onDelta).toHaveBeenCalledWith({
        type: 'entity.update',
        entity_id: 'entity1',
        data: { name: 'Updated' },
      });
    });
  });

  it('parses voice delta → calls onVoice', async () => {
    const onVoice = vi.fn();

    renderHook(() =>
      useWebSocket('aide123', {
        onVoice,
      })
    );

    await waitFor(() => expect(mockWs.readyState).toBe(MockWebSocket.OPEN));

    act(() => {
      mockWs.simulateMessage({
        type: 'voice',
        content: 'Test message',
      });
    });

    await waitFor(() => {
      expect(onVoice).toHaveBeenCalledWith({
        type: 'voice',
        content: 'Test message',
      });
    });
  });

  it('parses stream.start / stream.end → calls onStatus', async () => {
    const onStatus = vi.fn();

    renderHook(() =>
      useWebSocket('aide123', {
        onStatus,
      })
    );

    await waitFor(() => expect(mockWs.readyState).toBe(MockWebSocket.OPEN));

    act(() => {
      mockWs.simulateMessage({ type: 'stream.start' });
    });

    await waitFor(() => {
      expect(onStatus).toHaveBeenCalledWith({ type: 'stream.start' });
    });

    act(() => {
      mockWs.simulateMessage({ type: 'stream.end' });
    });

    await waitFor(() => {
      expect(onStatus).toHaveBeenCalledWith({ type: 'stream.end' });
    });
  });

  it('sendMessage(content) sends { type: "message", content } over WS', async () => {
    const { result } = renderHook(() => useWebSocket('aide123'));

    await waitFor(() => expect(mockWs.readyState).toBe(MockWebSocket.OPEN));

    act(() => {
      result.current.sendMessage('Hello');
    });

    await waitFor(() => {
      expect(mockWs.sentMessages.length).toBe(1);
    });

    const sent = JSON.parse(mockWs.sentMessages[0]);
    expect(sent).toMatchObject({
      type: 'message',
      content: 'Hello',
    });
    expect(sent.message_id).toBeDefined();
  });

  it('sendDirectEdit(entityId, field, value) sends direct_edit message', async () => {
    const { result } = renderHook(() => useWebSocket('aide123'));

    await waitFor(() => expect(mockWs.readyState).toBe(MockWebSocket.OPEN));

    act(() => {
      result.current.sendDirectEdit('entity1', 'name', 'Updated Name');
    });

    await waitFor(() => {
      expect(mockWs.sentMessages.length).toBe(1);
    });

    const sent = JSON.parse(mockWs.sentMessages[0]);
    expect(sent).toEqual({
      type: 'direct_edit',
      entity_id: 'entity1',
      field: 'name',
      value: 'Updated Name',
    });
  });

  it('closes cleanly on unmount', async () => {
    const { unmount } = renderHook(() => useWebSocket('aide123'));

    await waitFor(() => expect(mockWs.readyState).toBe(MockWebSocket.OPEN));

    const closeSpy = vi.spyOn(mockWs, 'close');

    unmount();

    expect(closeSpy).toHaveBeenCalled();
  });

  it('reconnects on disconnect (with backoff)', async () => {
    vi.useFakeTimers();

    renderHook(() => useWebSocket('aide123'));

    await waitFor(() => expect(mockWs.readyState).toBe(MockWebSocket.OPEN));

    // Simulate disconnect
    act(() => {
      mockWs.close();
    });

    // Fast-forward timer for reconnect (1s backoff)
    act(() => {
      vi.advanceTimersByTime(1100);
    });

    await waitFor(() => {
      expect(global.WebSocket).toHaveBeenCalledTimes(2);
    });

    vi.useRealTimers();
  });
});
