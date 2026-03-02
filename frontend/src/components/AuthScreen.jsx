/**
 * AuthScreen.jsx - Authentication screen component
 */

import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth.jsx';

export default function AuthScreen() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { sendMagicLink, verifyToken, isAuthenticated } = useAuth();

  // Check for token in URL on mount
  useEffect(() => {
    const token = searchParams.get('token');
    if (token) {
      verifyToken(token).then((result) => {
        if (result.data) {
          navigate('/');
        }
      });
    }
  }, [searchParams, verifyToken, navigate]);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/');
    }
  }, [isAuthenticated, navigate]);

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
