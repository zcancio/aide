/**
 * AideWS - WebSocket client for AIde
 * Handles connection, message routing, snapshot buffering, and reconnection
 */

export class AideWS {
  constructor() {
    this.ws = null;
    this.aideId = null;
    this.callbacks = {
      delta: [],
      meta: [],
      voice: [],
      status: [],
      snapshot: [],
      directEditError: [],
    };
    this.snapshotBuffer = [];
    this.isHydrating = false;
    this.reconnectDelay = 1000;
    this.maxReconnectDelay = 30000;
    this.currentReconnectDelay = 1000;
  }

  connect(aideId) {
    this.aideId = aideId;
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${location.host}/ws/aide/${aideId}`;

    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
          console.log('[AideWS] Connected:', url);
          this.currentReconnectDelay = this.reconnectDelay;
          resolve();
        };

        this.ws.onmessage = (event) => {
          this.handleMessage(event);
        };

        this.ws.onerror = (err) => {
          console.warn('[AideWS] Error:', err);
          reject(err);
        };

        this.ws.onclose = () => {
          console.log('[AideWS] Disconnected');
          this.scheduleReconnect();
        };
      } catch (err) {
        console.warn('[AideWS] Could not connect:', err);
        reject(err);
      }
    });
  }

  handleMessage(event) {
    let msg;
    try {
      msg = JSON.parse(event.data);
    } catch {
      return;
    }

    const { type } = msg;

    // Snapshot buffering
    if (type === 'snapshot.start') {
      this.isHydrating = true;
      this.snapshotBuffer = [];
      return;
    }

    if (type === 'snapshot.end') {
      this.isHydrating = false;
      this.callbacks.snapshot.forEach((cb) => cb([...this.snapshotBuffer]));
      this.snapshotBuffer = [];
      return;
    }

    // Buffer entity deltas during snapshot hydration
    if (this.isHydrating && (type === 'entity.create' || type === 'entity.update' || type === 'entity.remove')) {
      this.snapshotBuffer.push(msg);
      return;
    }

    // Route messages to callbacks
    if (type === 'entity.create' || type === 'entity.update' || type === 'entity.remove') {
      this.callbacks.delta.forEach((cb) => cb(msg));
    } else if (type === 'meta.update') {
      this.callbacks.meta.forEach((cb) => cb(msg.data));
    } else if (type === 'voice') {
      this.callbacks.voice.forEach((cb) => cb({ text: msg.text }));
    } else if (type === 'stream.start' || type === 'stream.end') {
      this.callbacks.status.forEach((cb) => cb({ type }));
    } else if (type === 'direct_edit.error') {
      this.callbacks.directEditError.forEach((cb) => cb({ error: msg.error }));
    }
  }

  onDelta(callback) {
    this.callbacks.delta.push(callback);
  }

  onMeta(callback) {
    this.callbacks.meta.push(callback);
  }

  onVoice(callback) {
    this.callbacks.voice.push(callback);
  }

  onStatus(callback) {
    this.callbacks.status.push(callback);
  }

  onSnapshot(callback) {
    this.callbacks.snapshot.push(callback);
  }

  onDirectEditError(callback) {
    this.callbacks.directEditError.push(callback);
  }

  send(data) {
    if (this.ws && this.ws.readyState === 1) { // WebSocket.OPEN
      this.ws.send(JSON.stringify(data));
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  scheduleReconnect() {
    if (!this.aideId) return;

    setTimeout(() => {
      console.log('[AideWS] Reconnecting...');
      this.connect(this.aideId).catch(() => {
        // Exponential backoff
        this.currentReconnectDelay = Math.min(
          this.currentReconnectDelay * 2,
          this.maxReconnectDelay
        );
      });
    }, this.currentReconnectDelay);
  }
}
