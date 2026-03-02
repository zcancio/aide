/**
 * ChatOverlay.jsx - Chat overlay with three-state behavior
 */

import { useState, useRef, useEffect } from 'react';
import ChatInput from './ChatInput.jsx';
import ChatMessage from './ChatMessage.jsx';

export default function ChatOverlay({ messages = [], onSend, initialState = 'input' }) {
  const [state, setState] = useState(initialState);
  const [touchStart, setTouchStart] = useState(null);
  const overlayRef = useRef(null);
  const collapseTimerRef = useRef(null);

  // Auto-collapse timers
  useEffect(() => {
    if (collapseTimerRef.current) {
      clearTimeout(collapseTimerRef.current);
    }

    if (state === 'expanded') {
      // Expanded → input after 5s
      collapseTimerRef.current = setTimeout(() => {
        setState('input');
      }, 5000);
    } else if (state === 'input') {
      // Input → hidden after 30s
      collapseTimerRef.current = setTimeout(() => {
        setState('hidden');
      }, 30000);
    }

    return () => {
      if (collapseTimerRef.current) {
        clearTimeout(collapseTimerRef.current);
      }
    };
  }, [state]);

  // Cmd/Ctrl+K to open
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setState('input');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleTouchStart = (e) => {
    setTouchStart({
      y: e.touches[0].clientY,
      state,
    });
  };

  const handleTouchMove = (e) => {
    if (!touchStart) return;

    const deltaY = e.touches[0].clientY - touchStart.y;

    // Swipe down threshold: 80px
    if (deltaY > 80) {
      if (touchStart.state === 'expanded') {
        setState('input');
        setTouchStart(null);
      } else if (touchStart.state === 'input') {
        setState('hidden');
        setTouchStart(null);
      }
    }

    // Swipe up threshold: -80px
    if (deltaY < -80) {
      if (touchStart.state === 'hidden') {
        setState('input');
        setTouchStart(null);
      } else if (touchStart.state === 'input') {
        setState('expanded');
        setTouchStart(null);
      }
    }
  };

  const handleTouchEnd = () => {
    setTouchStart(null);
  };

  const handleHandleClick = () => {
    if (state === 'hidden') {
      setState('input');
    } else if (state === 'input') {
      setState('expanded');
    } else {
      setState('input');
    }
  };

  const handleSend = (content) => {
    // Sending from hidden auto-opens to input
    if (state === 'hidden') {
      setState('input');
    }
    onSend(content);
  };

  return (
    <div
      ref={overlayRef}
      className="chat-overlay"
      data-testid="chat-overlay"
      data-state={state}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      <div
        className="chat-handle"
        data-testid="chat-handle"
        onClick={handleHandleClick}
      >
        <div className="chat-handle-bar" />
      </div>

      <div className="chat-history" data-testid="message-history">
        {messages.map((msg, i) => (
          <ChatMessage key={i} role={msg.role} content={msg.content} />
        ))}
      </div>

      <ChatInput onSend={handleSend} />
    </div>
  );
}
