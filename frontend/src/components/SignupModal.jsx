/**
 * SignupModal - Modal to prompt shadow users to sign up
 * Can be triggered by turn limit (blocking) or voluntary signup (dismissible)
 */

import { useState } from 'react';
import { useAuth } from '../hooks/useAuth.jsx';

export function SignupModal({ isOpen, onClose, turnCount, turnLimit }) {
  const { convertShadowUser } = useAuth();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sent, setSent] = useState(false);

  if (!isOpen) return null;

  // Modal is dismissible only if onClose is provided (voluntary signup)
  const isBlocking = !onClose;
  const showTurnInfo = turnCount !== undefined && turnLimit !== undefined;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const result = await convertShadowUser(email);
      if (result.error) {
        setError(result.error);
      } else {
        setSent(true);
      }
    } catch (err) {
      setError(err.message || 'Failed to send magic link');
    } finally {
      setLoading(false);
    }
  };

  const handleOverlayClick = (e) => {
    if (!isBlocking && e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div className="modal-overlay" data-testid="signup-modal-overlay" onClick={handleOverlayClick}>
      <div className="modal signup-modal">
        {!isBlocking && (
          <button className="modal-close" onClick={onClose} aria-label="Close">
            &times;
          </button>
        )}
        <h2>{showTurnInfo ? 'Continue with AIde' : 'Create your account'}</h2>
        <p className="modal-subtitle">
          {showTurnInfo
            ? `You've used ${turnCount} of ${turnLimit} free turns. Enter your email to keep building.`
            : 'Enter your email to save your work and unlock more features.'}
        </p>

        {sent ? (
          <div className="sent-message">
            <p>Check your email for a magic link to continue.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoFocus
            />
            {error && <div className="error-message">{error}</div>}
            <button type="submit" disabled={loading} className="btn btn-primary">
              {loading ? 'Sending...' : 'Send magic link'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
