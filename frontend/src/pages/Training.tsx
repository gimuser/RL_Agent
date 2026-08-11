import { useCallback, useEffect, useState } from "react";
import { LineChart } from "../components/charts/LineChart";
import { KpiCard } from "../components/ui/KpiCard";
import { PageHeader } from "../components/ui/PageHeader";
import { QueryState } from "../components/ui/QueryState";
import { StatusBadge } from "../components/ui/StatusBadge";
import { useToast } from "../components/ui/ToastProvider";
import { useApi } from "../hooks/useApi";
import { trainingService } from "../services/training.service";
import type { ExperimentStatus } from "../types/domain";

export function TrainingPage() {
  const status = useApi(trainingService.getStatus, { poll: true });
  const history = useApi(trainingService.getHistory, { poll: true });
  const checkpoints = useApi(trainingService.getCheckpoints);
  const metrics = useApi(trainingService.getMetrics, { poll: true });
  const { notify } = useToast();
  const [experiment, setExperiment] = useState<ExperimentStatus | null>(null);
  const [runId, setRunId] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    const poll = async () => {
      const current = await trainingService.getExperimentStatus(runId);
      if (!cancelled) {
        setExperiment(current);
        if (current.status && !["completed", "failed", "stopped", "stopping"].includes(current.status)) {
          window.setTimeout(() => { void poll(); }, 2000);
        }
      }
    };
    void poll();
    return () => { cancelled = true; };
  }, [runId]);

  const startExperiment = useCallback(async () => {
    if (!window.confirm("Start the real multi-model experiment with the processed dataset?")) return;
    try {
      const models = [
        { name: "dqn_baseline", architecture: "standard", dqn_type: "standard", learning_rate: 1e-3, gamma: 0.99, batch_size: 64, memory_size: 50000, target_update: 1000, training_passes: 3 },
        { name: "dqn_double", architecture: "standard", dqn_type: "double", learning_rate: 5e-4, gamma: 0.99, batch_size: 64, memory_size: 50000, target_update: 1000, training_passes: 3 },
        { name: "dqn_dueling", architecture: "dueling", dqn_type: "standard", learning_rate: 1e-3, gamma: 0.98, batch_size: 64, memory_size: 50000, target_update: 1000, training_passes: 3 },
      ];
      notify({ tone: "info", title: "Experiment started" });
      const res = await trainingService.startExperiment(models);
      setRunId(res.run_id);
      setExperiment({ status: "started", run_id: res.run_id } as ExperimentStatus);
    } catch (err) {
      notify({ tone: "error", title: "Experiment failed", description: err instanceof Error ? err.message : String(err) });
    }
  }, [notify]);

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

  const currentModel = experiment?.current_model ?? "—";
  const totalModels = experiment?.total_models ?? 3;
  const trainingProgress = (experiment?.training ?? {}) as Record<string, unknown>;
  const evaluationProgress = (experiment?.evaluation ?? {}) as Record<string, unknown>;
  const trainingEnvironmentSteps = typeof trainingProgress.environment_steps === "number" ? trainingProgress.environment_steps : "—";
  const trainingGradientUpdates = typeof trainingProgress.gradient_updates === "number" ? trainingProgress.gradient_updates : "—";
  const trainingEpisodes = typeof trainingProgress.episodes === "number" ? trainingProgress.episodes : "—";
  const trainingMeanReward = typeof trainingProgress.mean_reward === "number" ? trainingProgress.mean_reward : "—";
  const trainingMeanLoss = typeof trainingProgress.mean_loss === "number" ? trainingProgress.mean_loss : "—";
  const evaluationSamples = typeof evaluationProgress.samples === "number" ? evaluationProgress.samples : "—";
  return <>
    <PageHeader eyebrow="MODEL TRAINING" title="Training control" description="The frontend now polls the real backend experiment status and displays live training and evaluation progress." actions={<div className="button-group"><button className="button button--primary" type="button" onClick={() => void runAction("start")}>Start training</button><button className="button button--danger" type="button" onClick={() => void runAction("stop")}>Stop training</button></div>} />
    <QueryState state={status}>{(data) => <section className="kpi-grid kpi-grid--four"><KpiCard label="Training status" value={<StatusBadge value={data.status} />} detail="Reported by training API" icon="⌁" /><KpiCard label="Current model" value={currentModel} detail={`Model ${experiment?.model_index ?? 0}/${totalModels}`} icon="◷" /><KpiCard label="Environment steps" value={String(trainingEnvironmentSteps)} detail="Reported by trainer" icon="◎" /><KpiCard label="Gradient updates" value={String(trainingGradientUpdates)} detail="From live training state" icon="⚙" /></section>}</QueryState>
    <section className="panel"><div className="panel__header"><div><p className="eyebrow">REAL EXPERIMENT</p><h2>Live experiment status</h2></div></div>
      <div style={{display: 'flex', gap: '8px', marginBottom: '12px'}}>
        <button className="button button--primary" onClick={() => void startExperiment()}>Start full experiment</button>
      </div>
      <div className="detail-list">
        <div><dt>Status</dt><dd>{experiment?.status ?? "idle"}</dd></div>
        <div><dt>Current model</dt><dd>{currentModel}</dd></div>
        <div><dt>Dataset pass</dt><dd>{String(trainingEpisodes)}</dd></div>
        <div><dt>Environment steps</dt><dd>{String(trainingEnvironmentSteps)}</dd></div>
        <div><dt>Mean reward</dt><dd>{String(trainingMeanReward)}</dd></div>
        <div><dt>Training loss</dt><dd>{String(trainingMeanLoss)}</dd></div>
        <div><dt>Evaluation samples</dt><dd>{String(evaluationSamples)}</dd></div>
        <div><dt>Checkpoint</dt><dd>{experiment?.checkpoint ?? '—'}</dd></div>
      </div>
    </section>
    <section className="split-grid">
      <article className="panel"><div className="panel__header"><div><p className="eyebrow">LOSS CURVE</p><h2>Training loss</h2></div></div><QueryState state={history} empty={(data) => data.history.length === 0}>{(data) => <LineChart label="Training loss by epoch" points={data.history.map((point) => ({ label: `Epoch ${point.epoch}`, value: point.loss }))} />}</QueryState></article>
      <article className="panel"><div className="panel__header"><div><p className="eyebrow">CHECKPOINTS</p><h2>Available models</h2></div></div><QueryState state={checkpoints} empty={(data) => data.checkpoints.length === 0}>{(data) => <ul className="checkpoint-list">{data.checkpoints.map((checkpoint) => <li key={checkpoint}><span aria-hidden="true">▣</span>{checkpoint}</li>)}</ul>}</QueryState></article>
    </section>
    <section className="panel"><div className="panel__header"><div><p className="eyebrow">REWARD & PERFORMANCE</p><h2>Evaluation summary</h2></div></div>
      <QueryState state={metrics} empty={(d) => d.metrics.length === 0}>
        {(data) => <LineChart label="Training loss (metrics)" points={data.metrics.map((m) => ({ label: `Epoch ${m.epoch}`, value: m.loss }))} />}
      </QueryState>
    </section>
  </>;
}
