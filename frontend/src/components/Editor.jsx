/**
 * Editor.jsx - Main editor component
 */

import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import * as api from '../lib/api.js';
import { useAide } from '../hooks/useAide.js';
import { useWebSocket } from '../hooks/useWebSocket.js';
import EditorHeader from './EditorHeader.jsx';
import Preview from './Preview.jsx';
import ChatOverlay from './ChatOverlay.jsx';

export default function Editor() {
  const { aideId } = useParams();
  const [aide, setAide] = useState(null);
  const [messages, setMessages] = useState([]);
  const { entityStore, handleDelta, handleSnapshot } = useAide();

  // Fetch aide data on mount
  useEffect(() => {
    async function loadAide() {
      const result = await api.fetchAide(aideId);
      if (result.data) {
        setAide(result.data);
      }
    }
    if (aideId) {
      loadAide();
    }
  }, [aideId]);

  const handleVoice = useCallback(({ text }) => {
    // Handle assistant voice messages from backend
    if (text) {
      setMessages((prev) => [...prev, { role: 'assistant', content: text }]);
    }
  }, []);

  const { send, sendDirectEdit } = useWebSocket(aideId, {
    onDelta: handleDelta,
    onSnapshot: handleSnapshot,
    onVoice: handleVoice,
  });

  const handleTitleChange = async (newTitle) => {
    if (aide) {
      setAide({ ...aide, title: newTitle });
    }
  };

  const handleSendMessage = (content) => {
    // Add user message to local state
    setMessages((prev) => [...prev, { role: 'user', content }]);
    send({
      type: 'message',
      content,
    });
  };

  return (
    <div className="editor" data-testid="editor">
      <EditorHeader
        aideId={aideId}
        title={aide?.title || 'Untitled'}
        onTitleChange={handleTitleChange}
      />
      <Preview entityStore={entityStore} onDirectEdit={sendDirectEdit} />
      <ChatOverlay messages={messages} onSend={handleSendMessage} />
    </div>
  );
}
