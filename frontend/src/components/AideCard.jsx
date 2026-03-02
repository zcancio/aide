/**
 * AideCard.jsx - Individual aide card component
 */

export default function AideCard({ aide, onClick }) {
  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    }).format(date);
  };

  const getStatus = () => {
    if (aide.status === 'archived') return 'archived';
    if (aide.published_slug) return 'published';
    return 'draft';
  };

  const status = getStatus();

  return (
    <div
      className="aide-card"
      data-aide-id={aide.id}
      onClick={onClick}
    >
      <div className="aide-card-title">{aide.title || 'Untitled'}</div>
      <div className="aide-card-meta">
        <span className={`status-badge status-${status}`}>{status}</span>
        <span>{formatDate(aide.updated_at)}</span>
      </div>
    </div>
  );
}
