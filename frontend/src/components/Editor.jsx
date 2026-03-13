/**
 * Editor.jsx - Main editor component
 */

import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import * as api from '../lib/api.js';
import { useAide } from '../hooks/useAide.js';
import { useWebSocket } from '../hooks/useWebSocket.js';
import { useAuth } from '../hooks/useAuth.jsx';
import EditorHeader from './EditorHeader.jsx';
import Preview from './Preview.jsx';
import ChatOverlay from './ChatOverlay.jsx';
import { SignupModal } from './SignupModal.jsx';

export default function Editor() {
  const { aideId } = useParams();
  useAuth(); // Initialize auth (creates shadow session if needed)
  const [aide, setAide] = useState(null);
  const [messages, setMessages] = useState([]);
  const [showSignupModal, setShowSignupModal] = useState(false);
  const [turnInfo, setTurnInfo] = useState({ count: 0, limit: 20 });
  const { entityStore, handleDelta, handleSnapshot } = useAide();

  // Fetch aide data and conversation history on mount
  useEffect(() => {
    async function loadAide() {
      const result = await api.fetchAide(aideId);
      if (result.data) {
        setAide(result.data);
      }
    }
    async function loadHistory() {
      const result = await api.fetchConversationHistory(aideId);
      if (result.data?.messages) {
        setMessages(result.data.messages);
      }
    }
    if (aideId) {
      loadAide();
      loadHistory();
    }
  }, [aideId]);

  const handleVoice = useCallback(({ text }) => {
    // Handle assistant voice messages from backend
    if (text) {
      setMessages((prev) => [...prev, { role: 'assistant', content: text }]);
    }
  }, []);

  const handleStreamError = useCallback((msg) => {
    // Handle stream errors, including turn limit
    if (msg.error === 'TURN_LIMIT_REACHED') {
      setTurnInfo({
        count: msg.turn_count || 0,
        limit: msg.turn_limit || 20,
      });
      setShowSignupModal(true);
    }
  }, []);

  const { send, sendDirectEdit } = useWebSocket(aideId, {
    onDelta: handleDelta,
    onSnapshot: handleSnapshot,
    onVoice: handleVoice,
    onStreamError: handleStreamError,
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
      <SignupModal
        isOpen={showSignupModal}
        turnCount={turnInfo.count}
        turnLimit={turnInfo.limit}
      />
    </div>
  );
}
