import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { QueryState } from "../components/ui/QueryState";
import { useApi } from "../hooks/useApi";
import { decisionsService } from "../services/decisions.service";

export function AnalystsPage() {
  const decisions = useApi(decisionsService.getDecisions, { poll: true });
  return <>
    <PageHeader eyebrow="ANALYST OPERATIONS" title="Workload balancing" description="The dashboard waits for analyst-assignment and capacity data rather than estimating workload." />
    <section className="split-grid">
      <article className="panel"><div className="panel__header"><div><p className="eyebrow">ANALYST WORKLOAD</p><h2>Current allocation</h2></div></div><EmptyState compact title="No analyst workload endpoint" description="The current API provides no analyst identity, assignment, capacity, or availability fields." /></article>
      <article className="panel"><div className="panel__header"><div><p className="eyebrow">LOAD BALANCING</p><h2>Distribution signals</h2></div></div><dl className="detail-list"><Detail label="Average analyst load" /><Detail label="Load variance" /><Detail label="Most loaded analyst" /><Detail label="Least loaded analyst" /></dl></article>
    </section>
    <section className="panel"><div className="panel__header"><div><p className="eyebrow">ASSIGNMENT DATA</p><h2>Decisions without assignee fields</h2></div></div><QueryState state={decisions} empty={(data) => data.length === 0}>{(items) => <div className="api-notice"><strong>{items.length} decision records retrieved</strong><p>These records expose an alert ID and action, but not the assigned analyst. Workload cannot be calculated reliably from them.</p></div>}</QueryState></section>
  </>;
}

function Detail({ label }: { label: string }) { return <div><dt>{label}</dt><dd className="not-provided">Not provided by API</dd></div>; }
