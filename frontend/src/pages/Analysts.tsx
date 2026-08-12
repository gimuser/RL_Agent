import { PageHeader } from "../components/ui/PageHeader";
import { QueryState } from "../components/ui/QueryState";
import { StatusBadge } from "../components/ui/StatusBadge";
import { useApi } from "../hooks/useApi";
import { liveAlertsService } from "../services/liveAlerts.service";
import { formatDecimal, formatNumber } from "../utils/format";

export function AnalystsPage() {
  const workload = useApi(liveAlertsService.getWorkload, { poll: true });
  return <>
    <PageHeader eyebrow="ANALYST OPERATIONS" title="Workload balancing" description="Current analyst identity, assignment, capacity, and availability are backed by MongoDB." />
    <section className="split-grid">
      <article className="panel"><div className="panel__header"><div><p className="eyebrow">ANALYST WORKLOAD</p><h2>Current allocation</h2></div></div>
        <QueryState state={workload} empty={(data) => data.items.length === 0}>
          {(data) => <div className="table-scroll"><table className="alerts-table"><thead><tr><th>Analyst</th><th>Role</th><th>Load</th><th>Capacity</th><th>Available</th><th>Utilization</th></tr></thead><tbody>
            {data.items.map((item) => <tr key={item.analyst_id}><td><strong>{item.name}</strong><div className="muted">{item.analyst_id}</div></td><td>{item.role}</td><td>{formatNumber(item.load)}</td><td>{formatNumber(item.capacity)}</td><td>{formatNumber(item.available)}</td><td><StatusBadge value={`${formatDecimal(item.utilization * 100, 0)}%`} /></td></tr>)}
          </tbody></table></div>}
        </QueryState>
      </article>
      <article className="panel"><div className="panel__header"><div><p className="eyebrow">LOAD BALANCING</p><h2>Distribution signals</h2></div></div><QueryState state={workload}>{(data) => <dl className="detail-list"><Detail label="Average analyst load" value={formatDecimal(data.average_analyst_load, 2)} /><Detail label="Load variance" value={formatDecimal(data.load_variance, 2)} /><Detail label="Most loaded analyst" value={data.most_loaded_analyst ? `${data.most_loaded_analyst.name} (${data.most_loaded_analyst.load})` : "—"} /><Detail label="Least loaded analyst" value={data.least_loaded_analyst ? `${data.least_loaded_analyst.name} (${data.least_loaded_analyst.load})` : "—"} /></dl>}</QueryState></article>
    </section>
    <section className="panel"><div className="panel__header"><div><p className="eyebrow">ASSIGNMENT DATA</p><h2>Analyst-ready queue</h2></div></div><QueryState state={workload}>{(data) => <div className="api-notice"><strong>{data.items.length} active analyst records</strong><p>Use alert details to assign a pending alert to an available analyst. Every assignment is recorded in the MongoDB activity history.</p></div>}</QueryState></section>
  </>;
}

function Detail({ label, value }: { label: string; value: string }) { return <div><dt>{label}</dt><dd>{value}</dd></div>; }
