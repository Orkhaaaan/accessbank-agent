import { useCallback, useEffect, useState } from 'react';
import {
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import CaseStatus from './CaseStatus';

const COLORS = ['#f47920', '#1a1a2e', '#3b82f6', '#16a34a', '#ca8a04'];

const sentimentColor = (c) => {
  if (c.is_critical) return 'critical';
  if (c.sentiment === 'NEGATIVE') return 'negative';
  if (c.sentiment === 'POSITIVE') return 'positive';
  return 'neutral';
};

export default function OperatorDashboard({ apiBase }) {
  const [cases, setCases] = useState([]);
  const [stats, setStats] = useState(null);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [filters, setFilters] = useState({
    department: '',
    status: '',
    sentiment: '',
    is_critical: '',
  });

  const loadCases = useCallback(async () => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v) params.set(k, v);
    });
    const res = await fetch(`${apiBase}/api/cases?${params}`);
    const data = await res.json();
    setCases(data);
  }, [apiBase, filters]);

  const loadStats = useCallback(async () => {
    const res = await fetch(`${apiBase}/api/stats/dashboard`);
    setStats(await res.json());
  }, [apiBase]);

  useEffect(() => {
    loadCases();
    loadStats();
    const id = setInterval(() => {
      loadCases();
      loadStats();
    }, 5000);
    return () => clearInterval(id);
  }, [loadCases, loadStats]);

  const openCase = async (caseId) => {
    setSelected(caseId);
    const res = await fetch(`${apiBase}/api/cases/${caseId}`);
    setDetail(await res.json());
  };

  const updateStatus = async (caseId, status) => {
    await fetch(`${apiBase}/api/cases/${caseId}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    loadCases();
    if (selected === caseId) openCase(caseId);
  };

  const deptData = stats?.department_load
    ? Object.entries(stats.department_load).map(([name, value]) => ({ name, value }))
    : [];

  const tokenCost = stats?.token_usage?.total_cost_usd ?? 0;

  return (
    <div className="dashboard">
      <div className="stats-row">
        <div className="stat-card">
          <span>Bugün</span>
          <strong>{stats?.today ?? 0}</strong>
        </div>
        <div className="stat-card">
          <span>Həftə</span>
          <strong>{stats?.week ?? 0}</strong>
        </div>
        <div className="stat-card">
          <span>Ay</span>
          <strong>{stats?.month ?? 0}</strong>
        </div>
        <div className="stat-card">
          <span>Açıq case</span>
          <strong>{stats?.open_cases ?? 0}</strong>
        </div>
        <div className="stat-card">
          <span>Orta həll (saat)</span>
          <strong>{stats?.avg_resolution_hours ?? '—'}</strong>
        </div>
        <div className="stat-card accent">
          <span>API xərc (USD)</span>
          <strong>${tokenCost.toFixed(4)}</strong>
        </div>
      </div>

      <div className="charts-row">
        <div className="chart-box">
          <h4>Şöbə yüklənməsi</h4>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={deptData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label>
                {deptData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="chart-box">
          <h4>Sentiment trend (cases)</h4>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart
              data={cases.slice(0, 20).reverse().map((c, i) => ({
                i,
                urgency: c.urgency_score || 1,
                label: c.case_id,
              }))}
            >
              <XAxis dataKey="label" hide />
              <YAxis domain={[1, 5]} />
              <Tooltip />
              <Line type="monotone" dataKey="urgency" stroke="#f47920" strokeWidth={2} dot />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="filters">
        <select
          value={filters.department}
          onChange={(e) => setFilters((f) => ({ ...f, department: e.target.value }))}
        >
          <option value="">Bütün şöbələr</option>
          <option>Digital Banking</option>
          <option>Card Operations</option>
          <option>Transfers & Payments</option>
          <option>Loans & Applications</option>
          <option>Customer Service / Branch</option>
        </select>
        <select
          value={filters.status}
          onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
        >
          <option value="">Bütün statuslar</option>
          <option>OPEN</option>
          <option>PENDING</option>
          <option>RESOLVED</option>
          <option>CLOSED</option>
        </select>
        <select
          value={filters.sentiment}
          onChange={(e) => setFilters((f) => ({ ...f, sentiment: e.target.value }))}
        >
          <option value="">Sentiment</option>
          <option>POSITIVE</option>
          <option>NEUTRAL</option>
          <option>NEGATIVE</option>
        </select>
        <select
          value={filters.is_critical}
          onChange={(e) => setFilters((f) => ({ ...f, is_critical: e.target.value }))}
        >
          <option value="">Kritiklik</option>
          <option value="true">CRITICAL only</option>
          <option value="false">Non-critical</option>
        </select>
      </div>

      <div className="dashboard-grid">
        <div className="case-feed">
          <h3>Canlı case axını</h3>
          {cases.map((c) => (
            <button
              key={c.case_id}
              type="button"
              className={`case-row ${sentimentColor(c)} ${selected === c.case_id ? 'selected' : ''}`}
              onClick={() => openCase(c.case_id)}
            >
              <span className="id">#{c.case_id}</span>
              <span className="dept">{c.department}</span>
              <span className="status">{c.status}</span>
              {c.is_critical && <span className="crit">⚠️</span>}
            </button>
          ))}
        </div>
        <div className="case-detail">
          {detail?.case ? (
            <>
              <CaseStatus
                caseData={{ ...detail.case, status: detail.case.status }}
                onStatusChange={updateStatus}
              />
              <div className="conversation">
                <h4>Söhbət</h4>
                {(detail.messages || []).map((m, i) => (
                  <div key={i} className={`conv-msg ${m.role}`}>
                    <strong>{m.role}:</strong> {m.content}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="placeholder">Case seçin</p>
          )}
        </div>
      </div>

      <style>{`
        .stats-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
        .stat-card { background: white; padding: 1rem; border-radius: 12px; border: 1px solid var(--ab-border); }
        .stat-card span { display: block; font-size: 0.75rem; color: #666; }
        .stat-card strong { font-size: 1.5rem; }
        .stat-card.accent strong { color: var(--ab-orange); }
        .charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem; }
        @media (max-width: 900px) { .charts-row { grid-template-columns: 1fr; } }
        .chart-box { background: white; padding: 1rem; border-radius: 12px; border: 1px solid var(--ab-border); }
        .chart-box h4 { font-size: 0.9rem; margin-bottom: 0.5rem; }
        .filters { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1rem; }
        .filters select { padding: 0.5rem; border-radius: 8px; border: 1px solid var(--ab-border); }
        .dashboard-grid { display: grid; grid-template-columns: 320px 1fr; gap: 1rem; min-height: 400px; }
        @media (max-width: 900px) { .dashboard-grid { grid-template-columns: 1fr; } }
        .case-feed, .case-detail { background: white; border-radius: 12px; border: 1px solid var(--ab-border); padding: 1rem; overflow-y: auto; max-height: 500px; }
        .case-feed h3 { font-size: 0.95rem; margin-bottom: 0.75rem; }
        .case-row {
          display: grid;
          grid-template-columns: 60px 1fr auto auto;
          gap: 0.5rem;
          width: 100%;
          text-align: left;
          padding: 0.6rem;
          border: none;
          border-radius: 8px;
          margin-bottom: 0.35rem;
          background: var(--ab-gray);
          font-size: 0.85rem;
        }
        .case-row.selected { outline: 2px solid var(--ab-orange); }
        .case-row.critical { background: #fef2f2; }
        .case-row.negative { background: #fff7ed; }
        .case-row.positive { background: #f0fdf4; }
        .case-row.neutral { background: #fefce8; }
        .conversation { margin-top: 1rem; }
        .conv-msg { font-size: 0.85rem; padding: 0.5rem 0; border-bottom: 1px solid var(--ab-border); }
        .placeholder { color: #999; padding: 2rem; text-align: center; }
      `}</style>
    </div>
  );
}
