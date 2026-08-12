import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getAuthoritativeFullTrainingStatus,
  startAuthoritativeFullTraining,
  stopAuthoritativeFullTraining,
  type AuthoritativeTrainingStatus,
} from "../services/training.service";

const nf = new Intl.NumberFormat("en-US");

function n(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? nf.format(value) : "—";
}
function d(value: unknown, digits = 4) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "—";
}
function pct(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "—";
}

export function TrainingControlCenter() {
  const [state, setState] = useState<AuthoritativeTrainingStatus | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [cycleBusy, setCycleBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const response = await getAuthoritativeFullTrainingStatus();
      setState(response);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(), 3000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  const results = state?.results;
  const training = results?.training;
  const comparison = results?.comparison;
  const candidates = comparison?.candidates ?? [];
  const currentCandidate = training?.candidate_index ?? 0;
  const totalCandidates = (training?.candidate_count ?? candidates.length) || 3;
  const history = training?.history ?? [];
  const latest = history.at(-1);
  const live = results?.live_inference as any;
  const post = results?.post_training as any;
  const liveSummary = live?.summary ?? live ?? post?.inference ?? post?.live_inference ?? null;

  const completedCount = candidates.filter((item) => String(item?.status ?? "").toLowerCase().includes("live") || item?.live_inference || item?.live_cycle_id).length;

  const actionCounts = liveSummary?.action_distribution ?? training?.action_distribution ?? {};
  const liveTotal = Object.values(actionCounts).reduce((sum: number, value: any) => sum + (Number(value) || 0), 0);

  async function start() {
    if (!confirm("Start the 3-candidate sequential experiment? Each candidate will train automatically, receive a fresh 40-alert cycle, and route human-review alerts to analysts.")) return;
    setBusy(true);
    setError("");
    try {
      await startAuthoritativeFullTraining();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function stop() {
    if (!confirm("Stop the sequential experiment? Completed candidate/live-cycle telemetry will remain archived.")) return;
    setBusy(true);
    try {
      await stopAuthoritativeFullTraining();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function newCycle() {
    if (state?.status === "running") {
      setError("Create a new live cycle after training, not while the model sequence is actively training.");
      return;
    }
    if (!confirm("Start a completely fresh 40-alert evaluation cycle? The source files stay unchanged; current Mongo alert state and analyst decisions will be archived.")) return;
    setCycleBusy(true);
    try {
      const response = await fetch("/api/live-cycle/new", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "manual_refresh", metadata: { source: "training-control" } }),
      });
      if (!response.ok) throw new Error(`Live cycle reset failed (${response.status})`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setCycleBusy(false);
    }
  }

  const progress = totalCandidates > 0 ? Math.min(100, ((Math.max(0, currentCandidate - 1) + (state?.status === "completed" ? 1 : 0)) / totalCandidates) * 100) : 0;
  const epochMax = training?.epochs ?? 0;
  const epochCurrent = training?.actual_epochs ?? latest?.epoch ?? 0;

  const actionCards = useMemo(() => [
    { key: "allow", label: "Allow", value: Number(actionCounts.allow ?? 0) },
    { key: "block", label: "Block", value: Number(actionCounts.block ?? 0) },
    { key: "human_review", label: "Human review", value: Number(actionCounts.human_review ?? 0) },
  ], [actionCounts]);

  return (
    <div className="lux-training">
      <section className="lux-hero">
        <div>
          <div className="lux-kicker">RL CONTROL ROOM · SEQUENTIAL EXPERIMENT</div>
          <h1>Train → evaluate → route</h1>
          <p>One training command runs all configured model candidates sequentially. Every completed candidate receives a fresh copy of the isolated 40-alert holdout before the next candidate begins.</p>
        </div>
        <div className="lux-hero-actions">
          <button className="lux-button lux-button--ghost" disabled={busy || cycleBusy} onClick={() => void refresh()}>Refresh telemetry</button>
          <button className="lux-button lux-button--ghost" disabled={busy || cycleBusy} onClick={() => void newCycle()}>New live cycle</button>
          {state?.status === "running"
            ? <button className="lux-button lux-button--danger" disabled={busy} onClick={() => void stop()}>{busy ? "Stopping…" : "Stop sequence"}</button>
            : <button className="lux-button lux-button--primary" disabled={busy} onClick={() => void start()}>{busy ? "Starting…" : "Start all 3 candidates"}</button>}
        </div>
      </section>

      {error && <div className="lux-alert">{error}</div>}

      <section className="lux-statusbar">
        <div><span>Sequence status</span><strong className={`lux-status lux-status--${state?.status ?? "idle"}`}>{state?.status ?? "idle"}</strong></div>
        <div><span>Candidate</span><strong>{currentCandidate ? `${currentCandidate} / ${totalCandidates}` : "Waiting"}</strong></div>
        <div><span>Epoch</span><strong>{n(epochCurrent)} / {n(epochMax)}</strong></div>
        <div><span>Updates</span><strong>{n(training?.total_updates_used)}</strong></div>
        <div><span>Live alerts</span><strong>{liveTotal ? `${n(liveTotal)} actions` : "Fresh cycle"}</strong></div>
      </section>

      <section className="lux-card">
        <div className="lux-card-head">
          <div><div className="lux-card-label">AUTOMATIC PIPELINE</div><h2>Three-model sequence</h2></div>
          <span className="lux-pill">No manual candidate start</span>
        </div>
        <div className="lux-progress"><i style={{ width: `${progress}%` }} /></div>
        <div className="lux-mini-grid" style={{ marginTop: 14 }}>
          {[0, 1, 2].map((index) => {
            const candidate = candidates[index] as any;
            const active = currentCandidate === index + 1 && state?.status === "running";
            const done = Boolean(candidate?.live_inference || candidate?.live_cycle_id || (state?.status === "completed" && index < completedCount));
            return (
              <div key={index} style={{ borderColor: active ? "var(--lux-blue)" : undefined }}>
                <span>Candidate {index + 1}</span>
                <strong>{candidate?.name ?? ["dqn_lr_0005", "dqn_lr_001", "dqn_lr_002"][index]}</strong>
                <small className="lux-muted">{active ? "Training now" : done ? "Trained + live evaluated" : "Queued"}</small>
              </div>
            );
          })}
        </div>
      </section>

      <section className="lux-metrics-grid">
        <article className="lux-card lux-card--hero"><div className="lux-card-label">CURRENT POLICY REWARD</div><div className="lux-number">{d(training?.policy_reward ?? latest?.policy_reward, 6)}</div><div className="lux-sub">Learned-policy reward, not the static oracle ceiling.</div></article>
        <article className="lux-card"><div className="lux-card-label">VALIDATION SCORE</div><div className="lux-number">{d(training?.validation_score, 4)}</div><div className="lux-sub">Selection score from validation incidents only.</div></article>
        <article className="lux-card"><div className="lux-card-label">TOTAL UPDATES</div><div className="lux-number">{n(training?.total_updates_used)}</div><div className="lux-sub">Automatically derived from rows, batch size, and actual epochs.</div></article>
        <article className="lux-card"><div className="lux-card-label">BEST MODEL</div><div className="lux-number">{String((comparison?.best as any)?.name ?? "—")}</div><div className="lux-sub">Champion chosen only after validation comparison.</div></article>
      </section>

      <section className="lux-main-grid">
        <article className="lux-card">
          <div className="lux-card-label">LIVE 40-ALERT EVALUATION</div>
          <h2>Latest inference cycle</h2>
          <div className="lux-mini-grid" style={{ marginTop: 16 }}>
            <div><span>Cycle</span><strong>{liveSummary?.cycle_id ?? liveSummary?.decision_cycle_id ?? "—"}</strong></div>
            <div><span>Considered</span><strong>{n(liveSummary?.alerts_considered)}</strong></div>
            <div><span>Processed</span><strong>{n(liveSummary?.alerts_processed)}</strong></div>
            <div><span>Human review</span><strong>{n(liveSummary?.human_review_routed)}</strong></div>
          </div>
          <div className="lux-main-grid" style={{ marginTop: 14 }}>
            {actionCards.map((item) => <div key={item.key} className="lux-mini-grid"><div><span>{item.label}</span><strong>{n(item.value)}</strong></div></div>)}
          </div>
          <p className="lux-muted" style={{ marginTop: 14 }}>Each candidate receives a new MongoDB cycle. The original <code>live_source.csv</code>, <code>live_processed.csv</code>, and <code>live_mapping.csv</code> remain untouched.</p>
        </article>

        <article className="lux-card">
          <div className="lux-card-label">RESET SEMANTICS</div>
          <h2>Fresh means fresh</h2>
          <div className="lux-rule"><b>1</b><div><strong>Archive</strong><p>Previous alert decisions, reviews, and activity are stored under <code>live_alert_cycles</code>.</p></div></div>
          <div className="lux-rule"><b>2</b><div><strong>Rebuild</strong><p>The active Mongo queue is rebuilt from the immutable 40-alert source/processed/lineage files.</p></div></div>
          <div className="lux-rule"><b>3</b><div><strong>Re-infer</strong><p>The next model sees every one of the 40 alerts as untouched for its own decision cycle.</p></div></div>
        </article>
      </section>
    </div>
  );
}

export default TrainingControlCenter;
