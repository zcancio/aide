/**
 * AdminDashboard.jsx - Admin dashboard with stats, users, audit logs, and aide search
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth.jsx';
import * as api from '../lib/api.js';

const TABS = {
  STATS: 'stats',
  USERS: 'users',
  LOGS: 'logs',
  SEARCH: 'search',
};

export default function AdminDashboard() {
  const { user, isLoading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState(TABS.STATS);

  // Stats state
  const [stats, setStats] = useState(null);
  const [statsLoading, setStatsLoading] = useState(true);

  // Users state
  const [users, setUsers] = useState([]);
  const [usersTotal, setUsersTotal] = useState(0);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersOffset, setUsersOffset] = useState(0);

  // Audit logs state
  const [logs, setLogs] = useState([]);
  const [logsTotal, setLogsTotal] = useState(0);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logsOffset, setLogsOffset] = useState(0);

  // Search state
  const [searchType, setSearchType] = useState('aide_id');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const [hasSearched, setHasSearched] = useState(false);

  // Breakglass modal state
  const [breakglassAide, setBreakglassAide] = useState(null);
  const [breakglassReason, setBreakglassReason] = useState('');
  const [breakglassLoading, setBreakglassLoading] = useState(false);
  const [breakglassError, setBreakglassError] = useState(null);

  // 404 for non-admins
  if (!authLoading && (!user || !user.is_admin)) {
    return (
      <div className="admin-404">
        <h1>404</h1>
        <p>Page not found</p>
        <button className="btn btn-primary" onClick={() => navigate('/')}>
          Go Home
        </button>
      </div>
    );
  }

  // Load stats on mount
  useEffect(() => {
    async function loadStats() {
      setStatsLoading(true);
      const result = await api.fetchAdminStats();
      if (result.data) {
        setStats(result.data);
      }
      setStatsLoading(false);
    }
    if (user?.is_admin) {
      loadStats();
    }
  }, [user]);

  // Load users when tab switches
  useEffect(() => {
    if (activeTab === TABS.USERS && users.length === 0 && user?.is_admin) {
      loadUsers(0);
    }
  }, [activeTab, user]);

  // Load logs when tab switches
  useEffect(() => {
    if (activeTab === TABS.LOGS && logs.length === 0 && user?.is_admin) {
      loadLogs(0);
    }
  }, [activeTab, user]);

  async function loadUsers(offset) {
    setUsersLoading(true);
    const result = await api.fetchAdminUsers(100, offset);
    if (result.data) {
      setUsers(result.data.users);
      setUsersTotal(result.data.total);
      setUsersOffset(offset);
    }
    setUsersLoading(false);
  }

  async function loadLogs(offset) {
    setLogsLoading(true);
    const [logsResult, countResult] = await Promise.all([
      api.fetchAdminAuditLogs(100, offset),
      api.fetchAdminAuditLogsCount(),
    ]);
    if (logsResult.data) {
      setLogs(logsResult.data);
      setLogsOffset(offset);
    }
    if (countResult.data) {
      setLogsTotal(countResult.data.count);
    }
    setLogsLoading(false);
  }

  async function handleSearch(e) {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setSearchLoading(true);
    setSearchError(null);
    setHasSearched(true);

    const result = await api.searchAdminAides(
      searchType === 'aide_id' ? searchQuery.trim() : null,
      searchType === 'email' ? searchQuery.trim() : null
    );

    if (result.error) {
      setSearchError(result.error);
      setSearchResults([]);
    } else {
      setSearchResults(result.data || []);
    }
    setSearchLoading(false);
  }

  async function handleBreakglassSubmit(e) {
    e.preventDefault();
    if (!breakglassAide || breakglassReason.length < 10) return;

    setBreakglassLoading(true);
    setBreakglassError(null);

    const result = await api.breakglassViewAide(breakglassAide.id, breakglassReason);

    if (result.error) {
      setBreakglassError(result.error);
      setBreakglassLoading(false);
    } else {
      navigate(`/a/${breakglassAide.id}`);
    }
  }

  function closeBreakglassModal() {
    setBreakglassAide(null);
    setBreakglassReason('');
    setBreakglassError(null);
  }

  function formatDate(dateStr) {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleString();
  }

  if (authLoading) {
    return <div className="admin-loading">Loading...</div>;
  }

  return (
    <div className="admin-dashboard">
      <header className="admin-header">
        <button className="btn btn-ghost" onClick={() => navigate('/')}>
          &larr; Back
        </button>
        <h1>Admin Dashboard</h1>
      </header>

      <nav className="admin-tabs">
        {Object.entries({
          [TABS.STATS]: 'System Stats',
          [TABS.USERS]: 'Users',
          [TABS.LOGS]: 'Audit Logs',
          [TABS.SEARCH]: 'Aide Search',
        }).map(([key, label]) => (
          <button
            key={key}
            className={`admin-tab ${activeTab === key ? 'admin-tab--active' : ''}`}
            onClick={() => setActiveTab(key)}
          >
            {label}
          </button>
        ))}
      </nav>

      <main className="admin-content">
        {/* Stats Tab */}
        {activeTab === TABS.STATS && (
          <div className="admin-stats">
            {statsLoading ? (
              <div className="admin-loading">Loading stats...</div>
            ) : stats ? (
              <>
                <div className="admin-stats-grid">
                  <div className="admin-stat-card">
                    <div className="admin-stat-value">{stats.total_users}</div>
                    <div className="admin-stat-label">Total Users</div>
                  </div>
                  <div className="admin-stat-card">
                    <div className="admin-stat-value">{stats.total_aides}</div>
                    <div className="admin-stat-label">Total Aides</div>
                  </div>
                  <div className="admin-stat-card">
                    <div className="admin-stat-value">{stats.total_audit_logs}</div>
                    <div className="admin-stat-label">Audit Log Entries</div>
                  </div>
                </div>

                <div className="admin-stats-breakdown">
                  <div className="admin-breakdown-section">
                    <h3>Users by Tier</h3>
                    <div className="admin-breakdown-list">
                      {Object.entries(stats.users_by_tier || {}).map(([tier, count]) => (
                        <div key={tier} className="admin-breakdown-item">
                          <span className="admin-breakdown-key">{tier}</span>
                          <span className="admin-breakdown-value">{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="admin-breakdown-section">
                    <h3>Aides by Status</h3>
                    <div className="admin-breakdown-list">
                      {Object.entries(stats.aides_by_status || {}).map(([status, count]) => (
                        <div key={status} className="admin-breakdown-item">
                          <span className="admin-breakdown-key">{status}</span>
                          <span className="admin-breakdown-value">{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="admin-error">Failed to load stats</div>
            )}
          </div>
        )}

        {/* Users Tab */}
        {activeTab === TABS.USERS && (
          <div className="admin-users">
            {usersLoading ? (
              <div className="admin-loading">Loading users...</div>
            ) : (
              <>
                <div className="admin-table-header">
                  <span>
                    Showing {users.length} of {usersTotal} users
                  </span>
                </div>
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Email</th>
                      <th>Name</th>
                      <th>Tier</th>
                      <th>Aides</th>
                      <th>Turns</th>
                      <th>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.id}>
                        <td>
                          {u.email}
                          {u.is_admin && <span className="admin-badge">Admin</span>}
                        </td>
                        <td>{u.name || '-'}</td>
                        <td>
                          <span className={`tier-badge tier-${u.tier}`}>{u.tier}</span>
                        </td>
                        <td>{u.aide_count}</td>
                        <td>{u.turn_count}</td>
                        <td>{formatDate(u.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {usersTotal > 100 && (
                  <div className="admin-pagination">
                    <button
                      className="btn btn-ghost"
                      disabled={usersOffset === 0}
                      onClick={() => loadUsers(Math.max(0, usersOffset - 100))}
                    >
                      Previous
                    </button>
                    <button
                      className="btn btn-ghost"
                      disabled={usersOffset + 100 >= usersTotal}
                      onClick={() => loadUsers(usersOffset + 100)}
                    >
                      Next
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Audit Logs Tab */}
        {activeTab === TABS.LOGS && (
          <div className="admin-logs">
            {logsLoading ? (
              <div className="admin-loading">Loading audit logs...</div>
            ) : (
              <>
                <div className="admin-table-header">
                  <span>
                    Showing {logs.length} of {logsTotal} entries
                  </span>
                </div>
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Admin</th>
                      <th>Action</th>
                      <th>Target User</th>
                      <th>Target Aide</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((log) => (
                      <tr key={log.id}>
                        <td>{formatDate(log.created_at)}</td>
                        <td>{log.admin_email}</td>
                        <td>{log.action}</td>
                        <td>{log.target_user_email || '-'}</td>
                        <td>
                          {log.target_aide_title ? (
                            <span title={log.target_aide_id}>{log.target_aide_title}</span>
                          ) : (
                            '-'
                          )}
                        </td>
                        <td className="admin-reason-cell" title={log.reason}>
                          {log.reason}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {logsTotal > 100 && (
                  <div className="admin-pagination">
                    <button
                      className="btn btn-ghost"
                      disabled={logsOffset === 0}
                      onClick={() => loadLogs(Math.max(0, logsOffset - 100))}
                    >
                      Previous
                    </button>
                    <button
                      className="btn btn-ghost"
                      disabled={logsOffset + 100 >= logsTotal}
                      onClick={() => loadLogs(logsOffset + 100)}
                    >
                      Next
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Search Tab */}
        {activeTab === TABS.SEARCH && (
          <div className="admin-search">
            <form onSubmit={handleSearch} className="admin-search-form">
              <div className="admin-search-type">
                <label>
                  <input
                    type="radio"
                    name="searchType"
                    value="aide_id"
                    checked={searchType === 'aide_id'}
                    onChange={(e) => setSearchType(e.target.value)}
                  />
                  <span>Aide ID</span>
                </label>
                <label>
                  <input
                    type="radio"
                    name="searchType"
                    value="email"
                    checked={searchType === 'email'}
                    onChange={(e) => setSearchType(e.target.value)}
                  />
                  <span>User Email</span>
                </label>
              </div>

              <div className="admin-search-input">
                <input
                  type="text"
                  placeholder={
                    searchType === 'aide_id' ? 'Enter aide UUID...' : 'Enter email...'
                  }
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={searchLoading || !searchQuery.trim()}
                >
                  {searchLoading ? 'Searching...' : 'Search'}
                </button>
              </div>
            </form>

            {searchError && <div className="admin-error">{searchError}</div>}

            {searchResults.length > 0 && (
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Status</th>
                    <th>Owner</th>
                    <th>Updated</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {searchResults.map((aide) => (
                    <tr key={aide.id}>
                      <td>{aide.title}</td>
                      <td>
                        <span className={`status-badge status-${aide.status}`}>
                          {aide.status}
                        </span>
                      </td>
                      <td>{aide.owner_email}</td>
                      <td>{formatDate(aide.updated_at)}</td>
                      <td>
                        <button
                          className="btn btn-ghost"
                          onClick={() => setBreakglassAide(aide)}
                        >
                          View (Breakglass)
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {searchResults.length === 0 && hasSearched && !searchLoading && !searchError && (
              <div className="admin-empty">No aides found</div>
            )}
          </div>
        )}
      </main>

      {/* Breakglass Modal */}
      {breakglassAide && (
        <div className="admin-modal-overlay" onClick={closeBreakglassModal}>
          <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
            <h2>Breakglass Access</h2>
            <p>
              You are about to view aide <strong>{breakglassAide.title}</strong> owned by{' '}
              <strong>{breakglassAide.owner_email}</strong>.
            </p>
            <p className="admin-modal-warning">This action will be logged to the audit trail.</p>

            <form onSubmit={handleBreakglassSubmit}>
              <label>
                Reason (required, min 10 characters):
                <textarea
                  value={breakglassReason}
                  onChange={(e) => setBreakglassReason(e.target.value)}
                  placeholder="Enter justification for accessing this aide..."
                  rows={3}
                />
              </label>

              {breakglassError && <div className="admin-error">{breakglassError}</div>}

              <div className="admin-modal-actions">
                <button type="button" className="btn btn-ghost" onClick={closeBreakglassModal}>
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-danger"
                  disabled={breakglassLoading || breakglassReason.length < 10}
                >
                  {breakglassLoading ? 'Loading...' : 'View Aide'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
