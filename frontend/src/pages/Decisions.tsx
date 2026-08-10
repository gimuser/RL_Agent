import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { QueryState } from "../components/ui/QueryState";
import { useApi } from "../hooks/useApi";
import { decisionsService } from "../services/decisions.service";
import { formatDateTime, humanize } from "../utils/format";

export function DecisionsPage() {
  const decisions = useApi(decisionsService.getDecisions, { poll: true });
  const [query, setQuery] = useState("");
  return <>
    <PageHeader eyebrow="RL DECISIONS" title="Decision history" description="Agent decisions persisted by the current API." actions={<button className="button button--quiet" type="button" onClick={() => void decisions.refresh()} disabled={decisions.isRefreshing}>{decisions.isRefreshing ? "Refreshing…" : "Refresh"}</button>} />
    <QueryState state={decisions} empty={(data) => data.length === 0}>
      {(items) => <DecisionTable decisions={items} query={query} onQueryChange={setQuery} />}
    </QueryState>
  </>;
}

function DecisionTable({ decisions, query, onQueryChange }: { decisions: Awaited<ReturnType<typeof decisionsService.getDecisions>>; query: string; onQueryChange: (value: string) => void }) {
  const filtered = useMemo(() => {
    const normalized = query.toLowerCase().trim();
    return decisions.filter((decision) => !normalized || `${decision.id} ${decision.incident_id} ${decision.action}`.toLowerCase().includes(normalized));
  }, [decisions, query]);
  return <section className="panel table-panel">
    <div className="table-toolbar"><label className="search-input"><span aria-hidden="true">⌕</span><input value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="Search decision, alert, or action" aria-label="Search decisions" /></label><span>{filtered.length} decision{filtered.length === 1 ? "" : "s"}</span></div>
    {filtered.length === 0 ? <EmptyState compact title="No decisions match the search" description="Try another action, alert ID, or decision ID." /> : <div className="table-scroll"><table><thead><tr><th>Decision ID</th><th>Alert ID</th><th>Action</th><th>Timestamp</th><th>Priority</th><th>Reward</th></tr></thead><tbody>{filtered.map((decision) => <tr key={decision.id}><td className="mono">{decision.id}</td><td><Link className="table-link" to={`/alerts/${decision.incident_id}`}>{decision.incident_id}</Link></td><td><strong>{humanize(decision.action)}</strong></td><td>{formatDateTime(decision.timestamp)}</td><td><span className="not-provided">Not provided</span></td><td><span className="not-provided">Not provided</span></td></tr>)}</tbody></table></div>}
  </section>;
}
