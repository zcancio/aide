/**
 * useWebSocket - React hook for WebSocket connection management
 * Manages WebSocket lifecycle, connection state, and message routing
 */

import { useEffect, useRef, useState } from 'react';
import { AideWS } from '../lib/ws.js';

export function useWebSocket(aideId, callbacks = {}) {
  const wsRef = useRef(null);
  const [isConnected, setIsConnected] = useState(false);

  const {
    onDelta,
    onMeta,
    onVoice,
    onStatus,
    onSnapshot,
    onDirectEditError,
  } = callbacks;

  useEffect(() => {
    if (!aideId) return;

    // Create WebSocket instance
    const ws = new AideWS();
    wsRef.current = ws;

    // Register callbacks
    if (onDelta) ws.onDelta(onDelta);
    if (onMeta) ws.onMeta(onMeta);
    if (onVoice) ws.onVoice(onVoice);
    if (onStatus) ws.onStatus(onStatus);
    if (onSnapshot) ws.onSnapshot(onSnapshot);
    if (onDirectEditError) ws.onDirectEditError(onDirectEditError);

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
  }, [aideId, onDelta, onMeta, onVoice, onStatus, onSnapshot, onDirectEditError]);

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
