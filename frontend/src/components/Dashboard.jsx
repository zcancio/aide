/**
 * Dashboard.jsx - Dashboard component with aide grid
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import * as api from '../lib/api.js';
import { useAuth } from '../hooks/useAuth.jsx';
import AideCard from './AideCard.jsx';

export default function Dashboard() {
  const [aides, setAides] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const { user } = useAuth();

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
    </div>
  );
}
