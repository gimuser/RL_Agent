import { LineChart } from "../components/charts/LineChart";
import { EmptyState } from "../components/ui/EmptyState";
import { KpiCard } from "../components/ui/KpiCard";
import { PageHeader } from "../components/ui/PageHeader";
import { QueryState } from "../components/ui/QueryState";
import { useApi } from "../hooks/useApi";
import { dashboardService } from "../services/dashboard.service";
import { rewardsService } from "../services/rewards.service";
import { formatDecimal } from "../utils/format";

export function MetricsPage() {
  const summary = useApi(dashboardService.getSummary, { poll: true });
  const rewards = useApi(rewardsService.getRewards, { poll: true });
  const rewardStats = useApi(rewardsService.getStatistics, { poll: true });
  return <>
    <PageHeader eyebrow="MODEL EVALUATION" title="Metrics" description="Metrics are displayed only when supplied by the current API contracts." />
    <QueryState state={summary}>{(data) => <section className="kpi-grid kpi-grid--four"><KpiCard label="Accuracy" value={`${formatDecimal(data.accuracy * 100, 1)}%`} detail="Reported dashboard metric" icon="◎" /><KpiCard label="Average reward" value={formatDecimal(data.average_reward)} detail="Reported dashboard metric" icon="✦" /><KpiCard label="Avg. processing time" value={`${formatDecimal(data.average_latency)} ms`} detail="Reported dashboard metric" icon="◷" /><KpiCard label="F1 score" value="—" detail="Not exposed by API" icon="◇" /></section>}</QueryState>
    <section className="split-grid"><article className="panel"><div className="panel__header"><div><p className="eyebrow">REWARD HISTORY</p><h2>Reward events</h2></div></div><QueryState state={rewards} empty={(data) => data.length === 0}>{(data) => <LineChart label="Reward history" points={data.map((point) => ({ label: `#${point.id}`, value: point.reward_value }))} valueFormatter={(value) => formatDecimal(value)} />}</QueryState></article><article className="panel"><div className="panel__header"><div><p className="eyebrow">REWARD RANGE</p><h2>Aggregate values</h2></div></div><QueryState state={rewardStats}>{(data) => <dl className="detail-list"><Detail label="Mean reward" value={formatDecimal(data.mean_reward)} /><Detail label="Best reward" value={formatDecimal(data.max_reward)} /><Detail label="Lowest reward" value={formatDecimal(data.min_reward)} /></dl>}</QueryState></article></section>
    <section className="panel"><div className="panel__header"><div><p className="eyebrow">BASELINE COMPARISON</p><h2>Baseline vs RL agent</h2></div></div><EmptyState compact title="No comparison dataset available" description="The backend currently does not expose baseline, precision, recall, F1, MTTR, or analyst-load comparison data." /></section>
  </>;
}
function Detail({ label, value }: { label: string; value: string }) { return <div><dt>{label}</dt><dd>{value}</dd></div>; }
