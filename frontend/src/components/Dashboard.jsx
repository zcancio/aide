/**
 * Dashboard.jsx - Dashboard component with aide grid
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import * as api from '../lib/api.js';
import { useAuth } from '../hooks/useAuth.jsx';
import AideCard from './AideCard.jsx';
import { SignupModal } from './SignupModal.jsx';

function LoginModal({ isOpen, onClose }) {
  const { sendMagicLink } = useAuth();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    await sendMagicLink(email);
    setSent(true);
    setLoading(false);
  };

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal signup-modal">
        <button className="modal-close" onClick={onClose} aria-label="Close">&times;</button>
        <h2>Log in</h2>
        <p className="modal-subtitle">Enter your email to receive a magic link.</p>
        {sent ? (
          <div className="sent-message">
            <p>Check your email for a magic link.</p>
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
            <button type="submit" disabled={loading} className="btn btn-primary">
              {loading ? 'Sending...' : 'Send magic link'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [aides, setAides] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showSignupModal, setShowSignupModal] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const navigate = useNavigate();
  const { user, isShadow } = useAuth();

  useEffect(() => {
    async function loadAides() {
      const result = await api.fetchAides();
      if (result.data) {
        setAides(result.data);
      }
      setLoading(false);
    }
    loadAides();
  }, []);

  const handleNew = async () => {
    const result = await api.createAide();
    if (result.data) {
      navigate(`/a/${result.data.id}`);
    }
  };

  if (loading) {
    return <div className="dashboard" data-testid="dashboard">Loading...</div>;
  }

  return (
    <div className="dashboard" data-testid="dashboard">
      <div className="dashboard-header">
        <h1>Your aides</h1>
        <div style={{ display: 'flex', gap: '8px' }}>
          {isShadow && (
            <>
              <button className="btn btn-ghost" onClick={() => setShowLoginModal(true)}>
                Log in
              </button>
              <button className="btn btn-secondary" onClick={() => setShowSignupModal(true)}>
                Sign up
              </button>
            </>
          )}
          {user?.is_admin && (
            <button className="btn btn-ghost" onClick={() => navigate('/admin')}>
              Admin
            </button>
          )}
          <button className="btn btn-primary" onClick={handleNew}>
            + New
          </button>
        </div>
      </div>

      {aides.length === 0 ? (
        <div className="empty-state">
          <p>Nothing yet.</p>
          <button className="btn btn-primary" onClick={handleNew}>
            Create your first aide
          </button>
        </div>
      ) : (
        <div className="aide-grid">
          {aides.map((aide) => (
            <AideCard
              key={aide.id}
              aide={aide}
              onClick={() => navigate(`/a/${aide.id}`)}
            />
          ))}
        </div>
      )}
      <SignupModal
        isOpen={showSignupModal}
        onClose={() => setShowSignupModal(false)}
      />
      <LoginModal
        isOpen={showLoginModal}
        onClose={() => setShowLoginModal(false)}
      />
    </div>
  );
}
