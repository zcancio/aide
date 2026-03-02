/**
 * Editor.jsx - Main editor component
 */

import { useParams } from 'react-router-dom';
import { useAide } from '../hooks/useAide.js';
import { useWebSocket } from '../hooks/useWebSocket.js';
import EditorHeader from './EditorHeader.jsx';
import Preview from './Preview.jsx';
import ChatOverlay from './ChatOverlay.jsx';

export default function Editor() {
  const { aideId } = useParams();
  const { entityStore, handleDelta, handleSnapshot } = useAide();
  const { send, sendDirectEdit } = useWebSocket(aideId, {
    onDelta: handleDelta,
    onSnapshot: handleSnapshot,
  });

  const handleSendMessage = (content) => {
    send({
      type: 'message',
      content,
    });
  };

  return (
    <div className="editor" data-testid="editor">
      <EditorHeader aideId={aideId} />
      <Preview entityStore={entityStore} onDirectEdit={sendDirectEdit} />
      <ChatOverlay messages={[]} onSend={handleSendMessage} />
    </div>
  );
}
