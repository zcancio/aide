/**
 * ChatMessage.jsx - Individual chat message component
 */

export default function ChatMessage({ role, content }) {
  return (
    <div className="chat-message" data-role={role}>
      <div className="chat-message-role">{role}</div>
      <div className="chat-message-content">{content}</div>
    </div>
  );
}
