import { useCallback } from "react";
import { LineChart } from "../components/charts/LineChart";
import { EmptyState } from "../components/ui/EmptyState";
import { KpiCard } from "../components/ui/KpiCard";
import { PageHeader } from "../components/ui/PageHeader";
import { QueryState } from "../components/ui/QueryState";
import { StatusBadge } from "../components/ui/StatusBadge";
import { useToast } from "../components/ui/ToastProvider";
import { useApi } from "../hooks/useApi";
import { trainingService } from "../services/training.service";

export function TrainingPage() {
  const status = useApi(trainingService.getStatus, { poll: true });
  const history = useApi(trainingService.getHistory, { poll: true });
  const checkpoints = useApi(trainingService.getCheckpoints);
  const { notify } = useToast();
  const runAction = useCallback(async (action: "start" | "stop") => {
    const verb = action === "start" ? "start" : "stop";
    if (!window.confirm(`Are you sure you want to ${verb} training?`)) return;
    try {
      const response = await trainingService[action]();
      notify({ tone: "success", title: response.message });
      await status.refresh();
    } catch (error) {
      notify({ tone: "error", title: "Training action failed", description: error instanceof Error ? error.message : "Unable to reach the API." });
    }
  }, [notify, status]);
  return <>
    <PageHeader eyebrow="MODEL TRAINING" title="Training control" description="Start and stop commands call the configured API only after confirmation." actions={<div className="button-group"><button className="button button--primary" type="button" onClick={() => void runAction("start")}>Start training</button><button className="button button--danger" type="button" onClick={() => void runAction("stop")}>Stop training</button></div>} />
    <QueryState state={status}>{(data) => <section className="kpi-grid kpi-grid--three"><KpiCard label="Training status" value={<StatusBadge value={data.status} />} detail="Reported by training API" icon="⌁" /><KpiCard label="Current epoch" value={data.current_epoch} detail="No total epoch value supplied" icon="◷" /><KpiCard label="Progress" value="—" detail="No progress endpoint supplied" icon="◎" /></section>}</QueryState>
    <section className="split-grid">
      <article className="panel"><div className="panel__header"><div><p className="eyebrow">LOSS CURVE</p><h2>Training loss</h2></div></div><QueryState state={history} empty={(data) => data.history.length === 0}>{(data) => <LineChart label="Training loss by epoch" points={data.history.map((point) => ({ label: `Epoch ${point.epoch}`, value: point.loss }))} />}</QueryState></article>
      <article className="panel"><div className="panel__header"><div><p className="eyebrow">CHECKPOINTS</p><h2>Available models</h2></div></div><QueryState state={checkpoints} empty={(data) => data.checkpoints.length === 0}>{(data) => <ul className="checkpoint-list">{data.checkpoints.map((checkpoint) => <li key={checkpoint}><span aria-hidden="true">▣</span>{checkpoint}</li>)}</ul>}</QueryState></article>
    </section>
    <section className="panel"><div className="panel__header"><div><p className="eyebrow">REWARD & PERFORMANCE</p><h2>Awaiting metrics</h2></div></div><EmptyState compact title="No reward or performance curve available" description="The training API currently exposes loss history only. Reward, F1, learning rate, batch size, and duration will appear here when their endpoints are added." /></section>
  </>;
}
