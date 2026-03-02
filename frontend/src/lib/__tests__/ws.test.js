import { describe, it, expect, beforeEach, vi } from 'vitest';
import { AideWS } from '../ws.js';

describe('ws', () => {
  let mockWebSocket;
  let wsInstance;

  beforeEach(() => {
    // Mock WebSocket class
    mockWebSocket = {
      send: vi.fn(),
      close: vi.fn(),
      readyState: 1, // OPEN
      onopen: null,
      onmessage: null,
      onerror: null,
      onclose: null,
    };

    global.WebSocket = vi.fn(() => mockWebSocket);
  });

  it("connect('aide-123') constructs WebSocket to ws://host/ws/aide/aide-123", async () => {
    // Mock location
    global.location = { protocol: 'http:', host: 'localhost:3000' };

    wsInstance = new AideWS();
    const connectPromise = wsInstance.connect('aide-123');

    // Simulate onopen
    mockWebSocket.onopen();
    await connectPromise;

    expect(global.WebSocket).toHaveBeenCalledWith('ws://localhost:3000/ws/aide/aide-123');
  });

  it('connect() resolves when onopen fires', async () => {
    global.location = { protocol: 'http:', host: 'localhost:3000' };

    wsInstance = new AideWS();
    const connectPromise = wsInstance.connect('aide-123');

    // Should not be resolved yet
    let resolved = false;
    connectPromise.then(() => {
      resolved = true;
    });

    await new Promise((r) => setTimeout(r, 10));
    expect(resolved).toBe(false);

    // Trigger onopen
    mockWebSocket.onopen();
    await connectPromise;
    expect(resolved).toBe(true);
  });

  it('onDelta(cb) — cb called with delta when entity.create message received', async () => {
    global.location = { protocol: 'http:', host: 'localhost:3000' };

    wsInstance = new AideWS();
    const connectPromise = wsInstance.connect('aide-123');
    mockWebSocket.onopen();
    await connectPromise;

    const deltaCb = vi.fn();
    wsInstance.onDelta(deltaCb);

    const delta = { type: 'entity.create', id: 'e1', data: { props: { name: 'A' } } };
    mockWebSocket.onmessage({ data: JSON.stringify(delta) });

    expect(deltaCb).toHaveBeenCalledWith(delta);
  });

  it('onDelta(cb) — cb called for entity.update and entity.remove', async () => {
    global.location = { protocol: 'http:', host: 'localhost:3000' };

    wsInstance = new AideWS();
    const connectPromise = wsInstance.connect('aide-123');
    mockWebSocket.onopen();
    await connectPromise;

    const deltaCb = vi.fn();
    wsInstance.onDelta(deltaCb);

    const updateDelta = { type: 'entity.update', id: 'e1', data: { props: { name: 'B' } } };
    mockWebSocket.onmessage({ data: JSON.stringify(updateDelta) });
    expect(deltaCb).toHaveBeenCalledWith(updateDelta);

    const removeDelta = { type: 'entity.remove', id: 'e1' };
    mockWebSocket.onmessage({ data: JSON.stringify(removeDelta) });
    expect(deltaCb).toHaveBeenCalledWith(removeDelta);

    expect(deltaCb).toHaveBeenCalledTimes(2);
  });

  it('onMeta(cb) — cb called when meta.update message received', async () => {
    global.location = { protocol: 'http:', host: 'localhost:3000' };

    wsInstance = new AideWS();
    const connectPromise = wsInstance.connect('aide-123');
    mockWebSocket.onopen();
    await connectPromise;

    const metaCb = vi.fn();
    wsInstance.onMeta(metaCb);

    const metaUpdate = { type: 'meta.update', data: { title: 'My Page' } };
    mockWebSocket.onmessage({ data: JSON.stringify(metaUpdate) });

    expect(metaCb).toHaveBeenCalledWith({ title: 'My Page' });
  });

  it('onVoice(cb) — cb called with { text } when voice message received', async () => {
    global.location = { protocol: 'http:', host: 'localhost:3000' };

    wsInstance = new AideWS();
    const connectPromise = wsInstance.connect('aide-123');
    mockWebSocket.onopen();
    await connectPromise;

    const voiceCb = vi.fn();
    wsInstance.onVoice(voiceCb);

    const voiceMsg = { type: 'voice', text: 'Hello there' };
    mockWebSocket.onmessage({ data: JSON.stringify(voiceMsg) });

    expect(voiceCb).toHaveBeenCalledWith({ text: 'Hello there' });
  });

  it("onStatus(cb) — cb called with { type: 'stream.start' } and { type: 'stream.end' }", async () => {
    global.location = { protocol: 'http:', host: 'localhost:3000' };

    wsInstance = new AideWS();
    const connectPromise = wsInstance.connect('aide-123');
    mockWebSocket.onopen();
    await connectPromise;

    const statusCb = vi.fn();
    wsInstance.onStatus(statusCb);

    mockWebSocket.onmessage({ data: JSON.stringify({ type: 'stream.start' }) });
    expect(statusCb).toHaveBeenCalledWith({ type: 'stream.start' });

    mockWebSocket.onmessage({ data: JSON.stringify({ type: 'stream.end' }) });
    expect(statusCb).toHaveBeenCalledWith({ type: 'stream.end' });

    expect(statusCb).toHaveBeenCalledTimes(2);
  });

  it('onSnapshot(cb) — cb called with batched entities between snapshot.start and snapshot.end', async () => {
    global.location = { protocol: 'http:', host: 'localhost:3000' };

    wsInstance = new AideWS();
    const connectPromise = wsInstance.connect('aide-123');
    mockWebSocket.onopen();
    await connectPromise;

    const snapshotCb = vi.fn();
    wsInstance.onSnapshot(snapshotCb);

    // Start snapshot
    mockWebSocket.onmessage({ data: JSON.stringify({ type: 'snapshot.start' }) });

    // Send entities
    mockWebSocket.onmessage({
      data: JSON.stringify({ type: 'entity.create', id: 'e1', data: { props: { name: 'A' } } }),
    });
    mockWebSocket.onmessage({
      data: JSON.stringify({ type: 'entity.create', id: 'e2', data: { props: { name: 'B' } } }),
    });

    // Callback should not be called yet
    expect(snapshotCb).not.toHaveBeenCalled();

    // End snapshot
    mockWebSocket.onmessage({ data: JSON.stringify({ type: 'snapshot.end' }) });

    // Now callback should be called with batched entities
    expect(snapshotCb).toHaveBeenCalledWith([
      { type: 'entity.create', id: 'e1', data: { props: { name: 'A' } } },
      { type: 'entity.create', id: 'e2', data: { props: { name: 'B' } } },
    ]);
  });

  it('onDirectEditError(cb) — cb called when direct_edit.error received', async () => {
    global.location = { protocol: 'http:', host: 'localhost:3000' };

    wsInstance = new AideWS();
    const connectPromise = wsInstance.connect('aide-123');
    mockWebSocket.onopen();
    await connectPromise;

    const errorCb = vi.fn();
    wsInstance.onDirectEditError(errorCb);

    mockWebSocket.onmessage({
      data: JSON.stringify({ type: 'direct_edit.error', error: 'Field not editable' }),
    });

    expect(errorCb).toHaveBeenCalledWith({ error: 'Field not editable' });
  });

  it("send({ type: 'message', content: 'hi' }) sends JSON string over WS", async () => {
    global.location = { protocol: 'http:', host: 'localhost:3000' };

    wsInstance = new AideWS();
    const connectPromise = wsInstance.connect('aide-123');
    mockWebSocket.onopen();
    await connectPromise;

    wsInstance.send({ type: 'message', content: 'hi' });

    expect(mockWebSocket.send).toHaveBeenCalledWith(
      JSON.stringify({ type: 'message', content: 'hi' })
    );
  });

  it('disconnect() calls ws.close()', async () => {
    global.location = { protocol: 'http:', host: 'localhost:3000' };

    wsInstance = new AideWS();
    const connectPromise = wsInstance.connect('aide-123');
    mockWebSocket.onopen();
    await connectPromise;

    wsInstance.disconnect();

    expect(mockWebSocket.close).toHaveBeenCalled();
  });

  it('after onclose, attempts reconnect after 1s delay', async () => {
    vi.useFakeTimers();
    global.location = { protocol: 'http:', host: 'localhost:3000' };

    wsInstance = new AideWS();
    const connectPromise = wsInstance.connect('aide-123');
    mockWebSocket.onopen();
    await connectPromise;

    // Clear the initial WebSocket call
    global.WebSocket.mockClear();

    // Trigger onclose
    mockWebSocket.onclose();

    // Should not reconnect immediately
    expect(global.WebSocket).not.toHaveBeenCalled();

    // Advance timers by 1 second
    await vi.advanceTimersByTimeAsync(1000);

    // Now should attempt reconnect
    expect(global.WebSocket).toHaveBeenCalledWith('ws://localhost:3000/ws/aide/aide-123');

    vi.useRealTimers();
  });
});
