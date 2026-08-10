import { PageHeader } from "../components/ui/PageHeader";
import { QueryState } from "../components/ui/QueryState";
import type { AsyncState } from "../types/api";
import { useApi } from "../hooks/useApi";
import { alertsService } from "../services/alerts.service";
import { decisionsService } from "../services/decisions.service";
import { rewardsService } from "../services/rewards.service";
import { formatDateTime, formatDecimal } from "../utils/format";

export function HistoryPage() {
  const alerts = useApi(alertsService.getAlerts);
  const decisions = useApi(decisionsService.getDecisions);
  const rewards = useApi(rewardsService.getRewards);
  return <>
    <PageHeader eyebrow="SYSTEM RECORDS" title="History" description="Persisted alerts, decisions, and reward events currently available through the API." />
    <section className="history-grid"><HistoryPanel title="Alert history" state={alerts}>{(items) => <ul className="record-list">{items.map((item) => <li key={item.id}><strong>{item.title}</strong><span>{item.severity} · {item.source}</span></li>)}</ul>}</HistoryPanel><HistoryPanel title="Decision history" state={decisions}>{(items) => <ul className="record-list">{items.map((item) => <li key={item.id}><strong>{item.action}</strong><span>Alert #{item.incident_id} · {formatDateTime(item.timestamp)}</span></li>)}</ul>}</HistoryPanel><HistoryPanel title="Reward history" state={rewards}>{(items) => <ul className="record-list">{items.map((item) => <li key={item.id}><strong className={item.reward_value >= 0 ? "positive" : "negative"}>{item.reward_value >= 0 ? "+" : ""}{formatDecimal(item.reward_value)}</strong><span>Decision #{item.decision_id} · {formatDateTime(item.timestamp)}</span></li>)}</ul>}</HistoryPanel></section>
    <section className="panel"><div className="panel__header"><div><p className="eyebrow">NOT YET EXPOSED</p><h2>Training history and model versions</h2></div></div><p className="muted">Training checkpoints are visible on the Training page. A model-version history endpoint is not currently available.</p></section>
  </>;
}
function HistoryPanel<T>({ title, state, children }: { title: string; state: AsyncState<T>; children: (data: T) => React.ReactNode }) { return <article className="panel"><div className="panel__header"><div><p className="eyebrow">PERSISTED DATA</p><h2>{title}</h2></div></div><QueryState state={state} empty={(data) => Array.isArray(data) && data.length === 0}>{children}</QueryState></article>; }
