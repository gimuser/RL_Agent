import { Link } from "react-router-dom";
import { KpiCard } from "../components/ui/KpiCard";
import { PageHeader } from "../components/ui/PageHeader";
import { QueryState } from "../components/ui/QueryState";
import { StatusBadge } from "../components/ui/StatusBadge";
import { useApi } from "../hooks/useApi";
import { alertsService } from "../services/alerts.service";
import { dashboardService } from "../services/dashboard.service";
import { systemService } from "../services/system.service";
import { decisionsService } from "../services/decisions.service";
import { rewardsService } from "../services/rewards.service";
import { formatDateTime, formatDecimal, formatNumber } from "../utils/format";

export function DashboardPage() {
  const summary = useApi(dashboardService.getSummary, { poll: true });
  const alerts = useApi(alertsService.getAlerts, { poll: true });
  const decisions = useApi(decisionsService.getDecisions, { poll: true });
  const rewards = useApi(rewardsService.getRewards, { poll: true });
  const apis = useApi(systemService.getApis, { poll: true });

  return (
    <>
      <PageHeader
        eyebrow="SOC SUPERVISION"
        title="Operations dashboard"
        description="Live operational data from the SOAR-RL API. Values refresh on the configured polling interval."
        actions={<Link className="button button--primary" to="/alerts">Review alerts <span aria-hidden="true">→</span></Link>}
      />

      <QueryState state={summary}>
        {(data) => (
          <section className="kpi-grid" aria-label="SOC key performance indicators">
            <KpiCard label="Total alerts" value={formatNumber(data.total_alerts)} detail="Registered alerts" icon="◇" />
            <KpiCard label="Processed alerts" value={formatNumber(data.processed_alerts)} detail="Alerts with decisions" icon="✓" tone="success" />
            <KpiCard label="Total decisions" value={formatNumber(data.total_decisions)} detail="Recorded agent decisions" icon="↗" />
            <KpiCard label="Average reward" value={formatDecimal(data.average_reward)} detail="Across recorded rewards" icon="✦" tone="success" />
            <KpiCard label="Processing time" value={`${formatDecimal(data.average_latency)} ms`} detail="Reported average latency" icon="◷" />
            <KpiCard label="Accuracy" value={data.accuracy === null ? "—" : `${formatDecimal(data.accuracy * 100, 1)}%`} detail="Reported evaluation accuracy" icon="◎" />
            <KpiCard label="Reward events" value={formatNumber(data.total_rewards)} detail="Persisted reward records" icon="◌" />
            <KpiCard label="Current episode" value={formatNumber(data.current_episode)} detail="Reported training episode" icon="⌁" tone="warning" />
          </section>
        )}
      </QueryState>

      <section className="dashboard-grid">
        <article className="panel panel--wide">
          <div className="panel__header">
            <div>
              <p className="eyebrow">ALERT OVERVIEW</p>
              <h2>Recent alerts</h2>
            </div>
            <Link className="text-link" to="/alerts">View all alerts →</Link>
          </div>
          <QueryState state={alerts} empty={(data) => data.length === 0}>
            {(items) => (
              <div className="table-scroll">
                <table>
                  <thead><tr><th>Alert</th><th>Severity</th><th>Source</th><th>Action</th></tr></thead>
                  <tbody>
                    {items.slice(0, 6).map((alert) => (
                      <tr key={alert.id}>
                        <td><strong>{alert.title}</strong><span className="muted">ID {alert.id}</span></td>
                        <td><StatusBadge value={alert.severity} /></td>
                        <td>{alert.source}</td>
                        <td><Link className="table-link" to={`/alerts/${alert.id}`}>Inspect</Link></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </QueryState>
        </article>

        <article className="panel">
          <div className="panel__header">
            <div><p className="eyebrow">AGENT ACTIVITY</p><h2>Recent decisions</h2></div>
            <Link className="text-link" to="/decisions">History →</Link>
          </div>
          <QueryState state={decisions} empty={(data) => data.length === 0}>
            {(items) => <ul className="activity-feed">
              {items.slice(0, 6).map((decision) => (
                <li key={decision.id}>
                  <span className="activity-feed__mark" aria-hidden="true">↗</span>
                  <div><strong>{decision.action}</strong><p>Alert #{decision.incident_id} · {formatDateTime(decision.timestamp)}</p></div>
                </li>
              ))}
            </ul>}
          </QueryState>
        </article>
      </section>

      <section className="dashboard-grid dashboard-grid--bottom">
        <article className="panel">
          <div className="panel__header"><div><p className="eyebrow">SYSTEM HEALTH</p><h2>Service readiness</h2></div></div>
          <div className="health-list">
            <HealthItem label="API" state={summary.data?.training_status ? "online" : "unknown"} />
            <HealthItem label="Database" state={summary.data?.database_status ?? "unknown"} />
            <HealthItem label="Training" state={summary.data?.training_status ?? "unknown"} />
            <HealthItem label="RL agent" state="unknown" note="No agent status endpoint" />
            <div style={{ marginTop: 12 }}>
              <p className="eyebrow">API Components</p>
              <QueryState state={apis} empty={(d) => (d?.components?.length ?? 0) === 0}>{(data) => (
                <ul className="metric-list">
                  {data.components.map((c) => <li key={c.name}><strong>{c.name}</strong>: <StatusBadge value={c.status} /></li>)}
                </ul>
              )}</QueryState>
            </div>
          </div>
        </article>
        <article className="panel">
          <div className="panel__header"><div><p className="eyebrow">REWARDS</p><h2>Latest reward events</h2></div><Link className="text-link" to="/history">View history →</Link></div>
          <QueryState state={rewards} empty={(data) => data.length === 0}>
            {(items) => <ul className="metric-list">
              {items.slice(0, 5).map((reward) => <li key={reward.id}><span>Decision #{reward.decision_id}</span><strong className={reward.reward_value >= 0 ? "positive" : "negative"}>{reward.reward_value >= 0 ? "+" : ""}{formatDecimal(reward.reward_value)}</strong></li>)}
            </ul>}
          </QueryState>
        </article>
        <article className="panel rl-cycle">
          <div className="panel__header"><div><p className="eyebrow">RL DECISION CYCLE</p><h2>How a decision flows</h2></div></div>
          <ol><li>Observation</li><li>Agent</li><li>Action</li><li>Environment</li><li>Reward</li><li>Policy update</li></ol>
        </article>
      </section>
    </>
  );
}

function HealthItem({ label, state, note }: { label: string; state: string; note?: string }) {
  return <div className="health-list__item"><span>{label}</span><div>{note && <small>{note}</small>}<StatusBadge value={state} /></div></div>;
}
