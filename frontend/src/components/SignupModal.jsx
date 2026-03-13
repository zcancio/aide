/**
 * SignupModal - Modal to prompt shadow users to sign up after reaching turn limit
 */

import { useState } from 'react';
import { useAuth } from '../hooks/useAuth.jsx';

export function SignupModal({ isOpen, turnCount, turnLimit }) {
  const { convertShadowUser } = useAuth();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sent, setSent] = useState(false);

  if (!isOpen) return null;

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

  return (
    <div className="modal-overlay" data-testid="signup-modal-overlay">
      <div className="modal signup-modal">
        <h2>Continue with AIde</h2>
        <p className="modal-subtitle">
          You've used {turnCount} of {turnLimit} free turns.
          Enter your email to keep building.
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
