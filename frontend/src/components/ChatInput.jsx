/**
 * ChatInput.jsx - Chat input component
 */

import { useState } from 'react';

export default function ChatInput({ onSend }) {
  const [value, setValue] = useState('');

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = () => {
    if (value.trim()) {
      onSend(value);
      setValue('');
    }
  };

  return (
    <div className="chat-input-bar">
      <textarea
        className="chat-input"
        placeholder="Message..."
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={1}
      />
      <button
        className="chat-send-btn"
        onClick={handleSend}
        disabled={!value.trim()}
      >
        Send
      </button>
    </div>
  );
}
