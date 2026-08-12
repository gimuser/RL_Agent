import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getAuthoritativeFullTrainingStatus,
  startAuthoritativeFullTraining,
  stopAuthoritativeFullTraining,
  type AuthoritativeHistoryPoint,
  type AuthoritativeTrainingStatus,
} from "../services/training.service";

const nf = new Intl.NumberFormat("en-US");

function n(v: unknown) {
  return typeof v === "number" && Number.isFinite(v) ? nf.format(v) : "—";
}
function d(v: unknown, digits = 4) {
  return typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : "—";
}
function pct(v: unknown) {
  return typeof v === "number" && Number.isFinite(v) ? `${(v * 100).toFixed(1)}%` : "—";
}
function value(point: AuthoritativeHistoryPoint, metric: string) {
  if (metric === "loss") return point.loss;
  if (metric === "policy") return point.policy_reward ?? point.avg_reward ?? point.average_reward ?? 0;
  if (metric === "oracle") return point.oracle_average_reward ?? 0;
  if (metric === "efficiency") return point.reward_efficiency ?? 0;
  if (metric === "validation") return point.validation_score ?? 0;
  if (metric === "updates") return point.total_updates ?? point.updates ?? 0;
  return 0;
}

function Sparkline({ history, metric }: { history: AuthoritativeHistoryPoint[]; metric: string }) {
  if (!history.length) return <div className="lux-empty">Waiting for the first completed epoch.</div>;
  const values = history.map((p) => value(p, metric));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => {
    const x = (i / Math.max(1, values.length - 1)) * 100;
    const y = 92 - ((v - min) / span) * 78;
    return `${x},${y}`;
  }).join(" ");
  return (
    <div className="lux-chart-wrap">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="lux-chart" aria-label={`${metric} chart`}>
        <defs><linearGradient id={`lux-${metric}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="currentColor" stopOpacity=".30"/><stop offset="100%" stopColor="currentColor" stopOpacity="0"/></linearGradient></defs>
        <polygon points={`0,100 ${pts} 100,100`} fill={`url(#lux-${metric})`} />
        <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="2.4" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="lux-chart-axis"><span>E{history[0].epoch}</span><span>E{history[history.length - 1].epoch}</span></div>
    </div>
  );
}

export function TrainingLuxuryPage() {
  const [response, setResponse] = useState<AuthoritativeTrainingStatus | null>(null);
  const [metric, setMetric] = useState("loss");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      setResponse(await getAuthoritativeFullTrainingStatus());
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 3000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const run = response?.results;
  const training = run?.training;
  const history = training?.history ?? [];
  const latest = history.at(-1);
  const comparison = run?.comparison;
  const candidates = comparison?.candidates ?? [];
  const best = comparison?.best ?? null;
  const running = response?.status === "running";
  const percentDone = training?.epochs && training?.actual_epochs ? Math.min(100, (training.actual_epochs / training.epochs) * 100) : 0;
  const updatePercent = training?.max_total_updates && training?.total_updates_used ? Math.min(100, (training.total_updates_used / training.max_total_updates) * 100) : 0;

  const rewardDelta = useMemo(() => {
    if (!latest) return null;
    const p = latest.policy_reward ?? latest.avg_reward ?? latest.average_reward;
    const o = latest.oracle_average_reward;
    return typeof p === "number" && typeof o === "number" ? o - p : null;
  }, [latest]);

  async function start() {
    if (!confirm("Start adaptive multi-model training on the real incident-level dataset?")) return;
    setBusy(true); setError("");
    try { await startAuthoritativeFullTraining(); await refresh(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }
  async function stop() {
    if (!confirm("Stop the current training process? Completed telemetry will be preserved.")) return;
    setBusy(true); setError("");
    try { await stopAuthoritativeFullTraining(); await refresh(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }

  return (
    <div className="lux-training">
      <section className="lux-hero">
        <div>
          <div className="lux-kicker">RL CONTROL ROOM · ADAPTIVE TRAINING</div>
          <h1>Model intelligence console</h1>
          <p>Luxury live telemetry for convergence, policy reward, update budget, early stopping, and automatic model selection.</p>
        </div>
        <div className="lux-hero-actions">
          <button className="lux-button lux-button--ghost" disabled={refreshing || busy} onClick={() => void refresh()}>{refreshing ? "Syncing…" : "Refresh"}</button>
          {running ? <button className="lux-button lux-button--danger" disabled={busy} onClick={() => void stop()}>{busy ? "Stopping…" : "Stop training"}</button> : <button className="lux-button lux-button--primary" disabled={busy} onClick={() => void start()}>{busy ? "Starting…" : "Start adaptive training"}</button>}
        </div>
      </section>

      {error && <div className="lux-alert">{error}</div>}

      <section className="lux-statusbar">
        <div><span>Status</span><strong className={`lux-status lux-status--${response?.status ?? "idle"}`}>{response?.status ?? "idle"}</strong></div>
        <div><span>Candidate</span><strong>{training?.candidate_index ? `${training.candidate_index} / ${training.candidate_count ?? "—"}` : "—"}</strong></div>
        <div><span>Learning rate</span><strong>{training?.learning_rate ?? "—"}</strong></div>
        <div><span>Best epoch</span><strong>{n(training?.best_epoch)}</strong></div>
        <div><span>Patience</span><strong>{training?.patience_used != null ? `${n(training.patience_used)} / ${n(training.patience)}` : "—"}</strong></div>
      </section>

      <section className="lux-metrics-grid">
        <article className="lux-card lux-card--hero"><div className="lux-card-label">POLICY REWARD</div><div className="lux-number">{d(training?.policy_reward ?? training?.final_avg_reward, 6)}</div><div className="lux-sub">Reward actually obtained by the learned policy.</div><Sparkline history={history} metric="policy"/></article>
        <article className="lux-card"><div className="lux-card-label">ORACLE GAP</div><div className="lux-number">{d(rewardDelta, 6)}</div><div className="lux-sub">Oracle reward − policy reward.</div><Sparkline history={history} metric="oracle"/></article>
        <article className="lux-card"><div className="lux-card-label">POLICY EFFICIENCY</div><div className="lux-number">{pct(training?.reward_efficiency)}</div><div className="lux-sub">How close the learned policy is to the available reward ceiling.</div><Sparkline history={history} metric="efficiency"/></article>
        <article className="lux-card"><div className="lux-card-label">LOSS</div><div className="lux-number">{d(training?.final_loss, 6)}</div><div className="lux-sub">Latest completed epoch.</div><Sparkline history={history} metric="loss"/></article>
      </section>

      <section className="lux-main-grid">
        <article className="lux-card lux-card--wide">
          <div className="lux-card-head"><div><div className="lux-card-label">TELEMETRY</div><h2>Learning dynamics</h2></div><div className="lux-tabs">{["loss","policy","oracle","efficiency","validation","updates"].map((m) => <button key={m} className={metric === m ? "active" : ""} onClick={() => setMetric(m)}>{m}</button>)}</div></div>
          <div className="lux-big-chart"><Sparkline history={history} metric={metric}/></div>
          <div className="lux-chart-footer"><span>Epoch {history[0]?.epoch ?? "—"}</span><strong>{metric === "policy" ? "Policy reward" : metric === "oracle" ? "Oracle reward" : metric === "efficiency" ? "Reward efficiency" : metric === "validation" ? "Validation selection score" : metric === "updates" ? "Cumulative optimizer updates" : "Loss"}</strong><span>Epoch {history.at(-1)?.epoch ?? "—"}</span></div>
        </article>

        <article className="lux-card">
          <div className="lux-card-label">AUTOMATIC BUDGET</div><h2>Update engine</h2>
          <div className="lux-progress-block"><div className="lux-progress-top"><span>Epoch ceiling</span><strong>{n(training?.actual_epochs)} / {n(training?.epochs)}</strong></div><div className="lux-progress"><i style={{width: `${percentDone}%`}}/></div></div>
          <div className="lux-progress-block"><div className="lux-progress-top"><span>Optimizer updates</span><strong>{n(training?.total_updates_used)} / {n(training?.max_total_updates)}</strong></div><div className="lux-progress lux-progress--gold"><i style={{width: `${updatePercent}%`}}/></div></div>
          <div className="lux-mini-grid"><div><span>Updates / epoch</span><strong>{n(training?.updates_per_epoch)}</strong></div><div><span>Batch size</span><strong>{n(training?.batch_size)}</strong></div><div><span>Patience</span><strong>{n(training?.patience)}</strong></div><div><span>Min delta</span><strong>{d(training?.min_delta, 4)}</strong></div></div>
          <div className="lux-explain"><strong>Why reward can look stable</strong><p>The old telemetry averaged the reward ceiling implied by the labels, so it did not reflect the model. This version tracks the action chosen by the current Q-network and reports the oracle ceiling separately.</p></div>
        </article>
      </section>

      <section className="lux-main-grid">
        <article className="lux-card">
          <div className="lux-card-head"><div><div className="lux-card-label">MODEL SELECTION</div><h2>Candidate leaderboard</h2></div><span className="lux-pill">Test untouched</span></div>
          <div className="lux-table-wrap"><table className="lux-table"><thead><tr><th>Model</th><th>LR</th><th>Epochs</th><th>Val optimality</th><th>Val efficiency</th><th>Score</th></tr></thead><tbody>{candidates.map((c, i) => <tr key={String(c.name)} className={best?.name === c.name ? "is-best" : ""}><td><strong>{String(c.name ?? `Model ${i+1}`)}</strong>{best?.name === c.name && <span className="lux-best">BEST</span>}</td><td>{String(c.learning_rate ?? "—")}</td><td>{n(c.actual_epochs)}</td><td>{pct((c.best_validation as any)?.policy_optimality)}</td><td>{pct((c.best_validation as any)?.reward_efficiency)}</td><td>{d(c.validation_score, 4)}</td></tr>)}</tbody></table></div>
        </article>

        <article className="lux-card">
          <div className="lux-card-label">TRAINING POLICY</div><h2>Automatic stop logic</h2>
          <div className="lux-rule"><b>1</b><div><strong>Minimum learning window</strong><p>Never stop before the configured minimum epoch count.</p></div></div>
          <div className="lux-rule"><b>2</b><div><strong>Validation improvement</strong><p>Model score = 70% validation optimality + 30% validation reward efficiency.</p></div></div>
          <div className="lux-rule"><b>3</b><div><strong>Patience</strong><p>Stop after the policy stabilizes for the configured number of epochs.</p></div></div>
          <div className="lux-rule"><b>4</b><div><strong>Safety ceiling</strong><p>The optimizer also has an automatic total-update budget derived from dataset size and the epoch ceiling.</p></div></div>
        </article>
      </section>

      <section className="lux-card">
        <div className="lux-card-head"><div><div className="lux-card-label">EPOCH LEDGER</div><h2>Recent training events</h2></div><span className="lux-muted">Last {Math.min(12, history.length)} epochs</span></div>
        <div className="lux-table-wrap lux-table-wrap--tall"><table className="lux-table"><thead><tr><th>Epoch</th><th>Loss</th><th>Policy reward</th><th>Oracle</th><th>Efficiency</th><th>Total updates</th><th>Validation</th><th>Patience</th></tr></thead><tbody>{history.slice(-12).reverse().map((r) => <tr key={r.epoch}><td>{n(r.epoch)}</td><td>{d(r.loss, 6)}</td><td>{d(r.policy_reward ?? r.avg_reward, 6)}</td><td>{d(r.oracle_average_reward, 6)}</td><td>{pct(r.reward_efficiency)}</td><td>{n(r.total_updates)}</td><td>{d(r.validation_score, 4)}</td><td>{r.patience_used != null ? n(r.patience_used) : "—"}</td></tr>)}</tbody></table></div>
      </section>
    </div>
  );
}

export default TrainingLuxuryPage;
