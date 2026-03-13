/**
 * EditorHeader.jsx - Editor header with back button and title
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import * as api from '../lib/api.js';
import { useAuth } from '../hooks/useAuth.jsx';
import { SignupModal } from './SignupModal.jsx';

export default function EditorHeader({ aideId, title = 'Untitled', onTitleChange }) {
  const navigate = useNavigate();
  const { isShadow } = useAuth();
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(title);
  const [showSignupModal, setShowSignupModal] = useState(false);

  const handleTitleClick = () => {
    setEditValue(title);
    setIsEditing(true);
  };

  const handleTitleBlur = async () => {
    setIsEditing(false);
    if (editValue.trim() && editValue !== title) {
      await api.updateAide(aideId, { title: editValue });
      if (onTitleChange) {
        onTitleChange(editValue);
      }
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
        {isShadow && (
          <button className="btn btn-secondary" onClick={() => setShowSignupModal(true)}>
            Sign up
          </button>
        )}
      </div>
      <SignupModal
        isOpen={showSignupModal}
        onClose={() => setShowSignupModal(false)}
      />
    </div>
  );
}
