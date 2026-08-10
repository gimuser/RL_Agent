import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { QueryState } from "../components/ui/QueryState";
import { StatusBadge } from "../components/ui/StatusBadge";
import { useApi } from "../hooks/useApi";
import { dashboardService } from "../services/dashboard.service";
import { pipelineService } from "../services/pipeline.service";
import { trainingService } from "../services/training.service";
import { formatDateTime, formatDecimal, formatNumber } from "../utils/format";

export function AgentPage() {
  const summary = useApi(dashboardService.getSummary, { poll: true });
  const training = useApi(trainingService.getStatus, { poll: true });
  const pipeline = useApi(pipelineService.getStatus, { poll: true });
  return <>
    <PageHeader eyebrow="RL AGENT" title="Agent oversight" description="Current data is composed only from dashboard, training, and pipeline endpoints; a dedicated agent endpoint is not yet exposed." />
    <section className="split-grid">
      <article className="panel"><div className="panel__header"><div><p className="eyebrow">AVAILABLE STATUS</p><h2>Runtime signals</h2></div></div>
        <QueryState state={summary}>{(data) => <dl className="detail-list"><Detail label="Training state" value={data.training_status} badge /><Detail label="Current episode" value={formatNumber(data.current_episode)} /><Detail label="Average reward" value={formatDecimal(data.average_reward)} /><Detail label="Reported accuracy" value={`${formatDecimal(data.accuracy * 100, 1)}%`} /><Detail label="Model version" value="Not provided by API" muted /><Detail label="Algorithm" value="Not provided by API" muted /></dl>}</QueryState>
      </article>
      <article className="panel"><div className="panel__header"><div><p className="eyebrow">ENVIRONMENT</p><h2>Pipeline state</h2></div></div>
        <QueryState state={pipeline}>{(data) => <dl className="detail-list"><Detail label="Pipeline" value={data.status} badge /><Detail label="Last run" value={formatDateTime(data.last_run)} /><Detail label="Agent endpoint" value="Not available" muted /></dl>}</QueryState>
        <div className="divider" />
        <QueryState state={training}>{(data) => <div className="inline-stat"><span>Training endpoint</span><StatusBadge value={data.status} /><strong>Epoch {data.current_epoch}</strong></div>}</QueryState>
      </article>
    </section>
    <section className="panel"><div className="panel__header"><div><p className="eyebrow">MODEL DETAILS</p><h2>Awaiting agent telemetry</h2></div></div><EmptyState compact title="No model metadata endpoint" description="Algorithm, model version, policy metrics, confidence, and environment health are not available from the current FastAPI router." /></section>
  </>;
}

function Detail({ label, value, badge = false, muted = false }: { label: string; value: string; badge?: boolean; muted?: boolean }) {
  return <div><dt>{label}</dt><dd className={muted ? "not-provided" : ""}>{badge ? <StatusBadge value={value} /> : value}</dd></div>;
}
