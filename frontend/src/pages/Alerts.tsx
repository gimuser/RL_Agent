import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { QueryState } from "../components/ui/QueryState";
import { StatusBadge } from "../components/ui/StatusBadge";
import { useApi } from "../hooks/useApi";
import { alertsService } from "../services/alerts.service";

const PAGE_SIZE = 10;

export function AlertsPage() {
  const alerts = useApi(alertsService.getAlerts, { poll: true });
  const [query, setQuery] = useState("");
  const [severity, setSeverity] = useState("all");
  const [page, setPage] = useState(1);

  return (
    <>
      <PageHeader eyebrow="ALERT OPERATIONS" title="Alert queue" description="Search and inspect the alerts currently returned by the API." />
      <section className="panel filter-panel">
        <label className="search-input"><span aria-hidden="true">⌕</span><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder="Search alert, source, or ID" aria-label="Search alerts" /></label>
        <label className="select-label">Severity<select value={severity} onChange={(event) => { setSeverity(event.target.value); setPage(1); }}><option value="all">All severities</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></label>
        <button className="button button--quiet" type="button" onClick={() => void alerts.refresh()} disabled={alerts.isRefreshing}>{alerts.isRefreshing ? "Refreshing…" : "Refresh"}</button>
      </section>
      <QueryState state={alerts} empty={(data) => data.length === 0}>
        {(items) => <AlertsTable alerts={items} query={query} severity={severity} page={page} onPageChange={setPage} />}
      </QueryState>
    </>
  );
}

function AlertsTable({
  alerts,
  query,
  severity,
  page,
  onPageChange,
}: {
  alerts: Awaited<ReturnType<typeof alertsService.getAlerts>>;
  query: string;
  severity: string;
  page: number;
  onPageChange: (page: number) => void;
}) {
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return alerts.filter((alert) => {
      const matchesSeverity = severity === "all" || alert.severity.toLowerCase() === severity;
      const haystack = `${alert.id} ${alert.title} ${alert.source}`.toLowerCase();
      return matchesSeverity && (!normalized || haystack.includes(normalized));
    });
  }, [alerts, query, severity]);
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const resolvedPage = Math.min(page, totalPages);
  const visible = filtered.slice((resolvedPage - 1) * PAGE_SIZE, resolvedPage * PAGE_SIZE);

  if (visible.length === 0) return <EmptyState title="No alerts match the current filters" description="Try clearing the search or selecting another severity." />;
  return (
    <section className="panel table-panel">
      <div className="table-panel__summary"><span>{filtered.length} alert{filtered.length === 1 ? "" : "s"} returned</span><span>API pagination is currently handled client-side for this view.</span></div>
      <div className="table-scroll"><table className="alerts-table"><thead><tr><th>ID</th><th>Alert</th><th>Severity</th><th>Source</th><th>RL decision</th><th /></tr></thead><tbody>
        {visible.map((alert) => <tr key={alert.id}><td className="mono">{alert.id}</td><td><strong>{alert.title}</strong></td><td><StatusBadge value={alert.severity} /></td><td>{alert.source}</td><td><span className="not-provided">Not provided</span></td><td><Link className="table-link" to={`/alerts/${alert.id}`}>Details →</Link></td></tr>)}
      </tbody></table></div>
      <Pagination page={resolvedPage} totalPages={totalPages} onPageChange={onPageChange} />
    </section>
  );
}

function Pagination({ page, totalPages, onPageChange }: { page: number; totalPages: number; onPageChange: (page: number) => void }) {
  return <nav className="pagination" aria-label="Alert pagination"><button type="button" className="button button--quiet" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>← Previous</button><span>Page {page} of {totalPages}</span><button type="button" className="button button--quiet" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>Next →</button></nav>;
}
