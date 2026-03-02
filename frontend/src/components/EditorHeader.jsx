/**
 * EditorHeader.jsx - Editor header with back button and title
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import * as api from '../lib/api.js';

export default function EditorHeader({ aideId }) {
  const navigate = useNavigate();
  const [title, setTitle] = useState('Untitled');
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(title);

  const handleTitleClick = () => {
    setEditValue(title);
    setIsEditing(true);
  };

  const handleTitleBlur = async () => {
    setIsEditing(false);
    if (editValue.trim() && editValue !== title) {
      setTitle(editValue);
      await api.updateAide(aideId, { title: editValue });
    }
  };

  const handleTitleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleTitleBlur();
    }
    if (e.key === 'Escape') {
      setIsEditing(false);
      setEditValue(title);
    }
  };

  return (
    <div className="editor-header" data-testid="editor-header">
      <div className="editor-header-left">
        <button className="editor-back" onClick={() => navigate('/')}>
          ← Dashboard
        </button>
        {isEditing ? (
          <input
            type="text"
            className="editor-title-input"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={handleTitleBlur}
            onKeyDown={handleTitleKeyDown}
            autoFocus
          />
        ) : (
          <div className="editor-title" onClick={handleTitleClick}>
            {title}
          </div>
        )}
      </div>
      <div className="editor-header-right">
        {/* Future: share/publish buttons */}
      </div>
    </div>
  );
}
