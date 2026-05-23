export default function CaseStatus({ caseData, onStatusChange }) {
  if (!caseData) return null;

  const colorClass = caseData.is_critical
    ? 'critical'
    : caseData.sentiment === 'NEGATIVE'
      ? 'negative'
      : caseData.sentiment === 'POSITIVE'
        ? 'positive'
        : 'neutral';

  return (
    <div className={`case-status ${colorClass}`}>
      <header>
        <h3>Case #{caseData.case_id}</h3>
        <span className={`badge ${colorClass}`}>
          {caseData.is_critical ? 'CRITICAL' : caseData.sentiment || 'NEUTRAL'}
        </span>
      </header>
      <dl>
        <dt>Status</dt>
        <dd>
          <select
            value={caseData.status}
            onChange={(e) => onStatusChange?.(caseData.case_id, e.target.value)}
          >
            <option value="OPEN">OPEN</option>
            <option value="PENDING">PENDING</option>
            <option value="RESOLVED">RESOLVED</option>
            <option value="CLOSED">CLOSED</option>
          </select>
        </dd>
        <dt>Şöbə</dt>
        <dd>{caseData.department}</dd>
        <dt>Urgency</dt>
        <dd>{caseData.urgency_score}/5</dd>
        <dt>Emotion</dt>
        <dd>{caseData.emotion || '—'}</dd>
        <dt>Müştəri</dt>
        <dd>{caseData.customer_name || '—'}</dd>
        <dt>Telefon</dt>
        <dd>{caseData.customer_phone || '—'}</dd>
      </dl>
      <p className="issue">{caseData.issue_description}</p>
      <style>{`
        .case-status {
          border-radius: 12px;
          padding: 1rem;
          border-left: 4px solid var(--ab-border);
        }
        .case-status.critical { border-left-color: var(--critical); background: #fef2f2; }
        .case-status.negative { border-left-color: var(--negative); background: #fff7ed; }
        .case-status.neutral { border-left-color: var(--neutral); background: #fefce8; }
        .case-status.positive { border-left-color: var(--positive); background: #f0fdf4; }
        header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
        .badge { font-size: 0.7rem; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 600; }
        .badge.critical { background: var(--critical); color: white; }
        dl { display: grid; grid-template-columns: auto 1fr; gap: 0.25rem 1rem; font-size: 0.85rem; }
        dt { color: #666; }
        select { padding: 0.25rem; border-radius: 6px; border: 1px solid var(--ab-border); }
        .issue { margin-top: 0.75rem; font-size: 0.9rem; color: #444; }
      `}</style>
    </div>
  );
}
