/**
 * AuthScreen.jsx - Authentication screen component
 */

import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth.jsx';

export default function AuthScreen() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState(null);
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { sendMagicLink, isAuthenticated, isShadow } = useAuth();

  // Check for error in URL on mount (from failed magic link verification)
  useEffect(() => {
    const errorParam = searchParams.get('error');
    if (errorParam) {
      const errorMessages = {
        too_many_attempts: 'Too many verification attempts. Please wait a moment.',
        invalid_link: 'Invalid magic link. Please request a new one.',
        link_used: 'This magic link has already been used. Please request a new one.',
        link_expired: 'This magic link has expired. Please request a new one.',
      };
      setError(errorMessages[errorParam] || 'Authentication failed. Please request a new link.');
    }
  }, [searchParams]);

  // Redirect if already authenticated (but allow shadow users to access login)
  useEffect(() => {
    if (isAuthenticated && !isShadow) {
      navigate('/');
    }
  }, [isAuthenticated, isShadow, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;

    await sendMagicLink(email);
    setSent(true);
  };

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <h1>aide</h1>
        <p>For what you're living.</p>

        {error && (
          <div className="auth-error">
            {error}
          </div>
        )}

        {!sent ? (
          <form className="auth-form" onSubmit={handleSubmit}>
            <input
              type="email"
              className="auth-input"
              placeholder="Your email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <button type="submit" className="btn btn-primary">
              Send magic link
            </button>
          </form>
        ) : (
          <div className="auth-confirmation">
            Check your email for a sign-in link.
          </div>
        )}
      </div>
    </div>
  );
}
