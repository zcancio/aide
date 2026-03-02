/**
 * useWebSocket - React hook for WebSocket connection management
 * Manages WebSocket lifecycle, connection state, and message routing
 */

import { useEffect, useRef, useState } from 'react';
import { AideWS } from '../lib/ws.js';

export function useWebSocket(aideId, callbacks = {}) {
  const wsRef = useRef(null);
  const callbacksRef = useRef(callbacks);
  const [isConnected, setIsConnected] = useState(false);

  // Keep callbacks ref updated without triggering reconnect
  callbacksRef.current = callbacks;

  useEffect(() => {
    if (!aideId) return;

    // Create WebSocket instance
    const ws = new AideWS();
    wsRef.current = ws;

    // Register callbacks via ref to avoid stale closures
    const cb = callbacksRef.current;
    if (cb.onDelta) ws.onDelta(cb.onDelta);
    if (cb.onMeta) ws.onMeta(cb.onMeta);
    if (cb.onVoice) ws.onVoice(cb.onVoice);
    if (cb.onStatus) ws.onStatus(cb.onStatus);
    if (cb.onSnapshot) ws.onSnapshot(cb.onSnapshot);
    if (cb.onDirectEditError) ws.onDirectEditError(cb.onDirectEditError);

    // Connect
    ws.connect(aideId)
      .then(() => {
        setIsConnected(true);
      })
      .catch((err) => {
        console.error('[useWebSocket] Connection failed:', err);
        setIsConnected(false);
      });

    // Cleanup on unmount or aideId change
    return () => {
      setIsConnected(false);
      ws.disconnect();
    };
  }, [aideId]);

  const send = (msg) => {
    if (wsRef.current) {
      wsRef.current.send(msg);
    }
  };

  const sendDirectEdit = (entityId, field, value) => {
    if (wsRef.current) {
      wsRef.current.send({
        type: 'direct_edit',
        entity_id: entityId,
        field: field,
        value: value,
      });
    }
  };

  return {
    isConnected,
    send,
    sendDirectEdit,
  };
}
