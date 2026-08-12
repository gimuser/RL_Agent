#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKUP = ROOT / "backups" / f"final_stabilization_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def replace_function(path: Path, name: str, new_source: str) -> None:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^def {re.escape(name)}\(.*?(?=^def |^class |\Z)", re.M | re.S)
    match = pattern.search(text)
    if not match:
        raise RuntimeError(f"Could not find function {name} in {path}")
    path.write_text(text[:match.start()] + new_source.rstrip() + "\n\n" + text[match.end():], encoding="utf-8")


def run(cmd: list[str], cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, text=True, check=check)


def patch_backend() -> None:
    controller = ROOT / "backend/app/services/authoritative_training_control.py"
    trainer = ROOT / "backend/app/rl_agent/trainer.py"
    sequential = ROOT / "backend/app/rl_agent/sequential_experiment.py"
    post = ROOT / "backend/app/services/post_training_service.py"
    alerts = ROOT / "backend/app/services/live_alert_service.py"

    replace_function(controller, "_history", '''def _history() -> list[dict[str, Any]]:
    data = _load_json(TRAIN_METRICS) or {}
    current_run = _run_id
    if current_run and data.get("run_id") != current_run:
        return []
    raw = data.get("metrics")
    if not isinstance(raw, list):
        return []
    output = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if current_run and item.get("run_id") != current_run:
            continue
        if not isinstance(item.get("epoch"), (int, float)) or not isinstance(item.get("loss"), (int, float)):
            continue
        output.append({
            "run_id": item.get("run_id"), "epoch": item["epoch"], "loss": item["loss"],
            "avg_reward": item.get("average_reward"), "policy_reward": item.get("policy_reward", item.get("average_reward")),
            "oracle_average_reward": item.get("oracle_average_reward"), "reward_efficiency": item.get("reward_efficiency"),
            "updates": item.get("updates"), "total_updates": item.get("total_updates"), "updates_per_epoch": item.get("updates_per_epoch"),
            "rows": item.get("rows"), "incidents": item.get("incidents"),
            "action_distribution": item.get("action_distribution") or item.get("action_counts"),
            "time_seconds": item.get("time_seconds"), "validation": item.get("validation"),
            "validation_score": item.get("validation_score"), "best_epoch": item.get("best_epoch"),
            "patience_used": item.get("patience_used"), "improved": item.get("improved"),
            "stopping_reason": item.get("stopping_reason"), "algorithm": item.get("algorithm"),
        })
    return output''')

    replace_function(controller, "_sync_process_state", '''def _sync_process_state() -> None:
    global _process, _log_handle, _last_return_code, _last_message
    if _process is None:
        return
    code = _process.poll()
    if code is None:
        return
    _last_return_code = code
    if code == 0:
        _last_message = "Selected model training, candidate live cycles, champion selection, and final live cycle completed."
    elif code < 0:
        _last_message = f"Training process terminated by signal {-code}."
    else:
        _last_message = f"Training process exited with return code {code}."
    _write_run_state(status="completed" if code == 0 else "stopped" if code < 0 else "failed", return_code=code, finished_at=datetime.now(timezone.utc).isoformat())
    if _log_handle:
        try:
            _log_handle.close()
        except Exception:
            pass
        _log_handle = None
    _process = None''')

    replace_function(controller, "status", '''def status() -> dict[str, Any]:
    with _lock:
        try:
            _sync_process_state()
            run_state = _load_json(RUN_STATE) or {}
            running = _process is not None and _process.poll() is None
            training = _load_json(TRAIN_METRICS) or {}
            testing = _load_json(TEST_METRICS) or {}
            comparison = _load_json(COMPARISON) or {}
            split = _load_json(SPLIT_REPORT) or {}
            inference = _load_json(INFERENCE) or {}
            same_run = bool(_run_id) and training.get("run_id") == _run_id
            history = _history() if same_run else []
            last = history[-1] if history else {}
            config = training.get("config") if isinstance(training.get("config"), dict) and same_run else {"run_id": _run_id, "selected_models": _selected_models}
            if running:
                state, message = "running", f"Training selected models: {', '.join(_selected_models)}"
            elif _last_return_code == 0:
                state, message = "completed", _last_message
            elif _last_return_code is not None:
                state, message = ("stopped" if "stop" in _last_message.lower() else "failed"), _last_message
            elif same_run and history:
                state, message = "completed", "Persisted training results available."
            else:
                state, message = "idle", "No active training run. Select algorithms to start a new experiment."
            if not same_run:
                training = {"metrics": []}
                comparison = {}
                inference = {"run_id": _run_id, "status": "idle", "alerts_considered": 0, "alerts_processed": 0, "human_review_routed": 0, "action_distribution": {}}
            results = {
                "run_id": run_state.get("run_id", _run_id),
                "dataset": {"name": "train_processed.csv", "train_rows": split.get("train_rows"), "validation_rows": split.get("validation_rows"), "test_rows": split.get("test_rows"), "train_incidents": split.get("train_incidents"), "validation_incidents": split.get("validation_incidents"), "test_incidents": split.get("test_incidents"), "incident_overlap": split.get("incident_overlap"), "features": split.get("features"), "feature_count": len(split.get("features", [])) if isinstance(split.get("features"), list) else None, "synthetic_data": False, "unseen_incidents": True},
                "training": {"run_id": config.get("run_id"), "model_name": config.get("model_name"), "algorithm": config.get("algorithm"), "display_name": config.get("display_name"), "candidate_index": config.get("candidate_index"), "candidate_count": config.get("candidate_count", len(_selected_models)), "selected_models": config.get("selected_models", _selected_models), "learning_rate": config.get("learning_rate"), "epochs": config.get("max_epochs", config.get("epochs")), "actual_epochs": training.get("actual_epochs", last.get("epoch")), "min_epochs": config.get("min_epochs"), "patience": config.get("patience"), "min_delta": config.get("min_delta"), "stability_window": config.get("stability_window"), "stability_tolerance": config.get("stability_tolerance"), "batch_size": config.get("batch_size"), "updates_per_epoch": training.get("updates_per_epoch") or last.get("updates_per_epoch"), "max_total_updates": training.get("max_total_updates") or config.get("max_total_updates"), "total_updates_used": training.get("total_updates_used", last.get("total_updates")), "policy_reward": last.get("policy_reward"), "oracle_average_reward": last.get("oracle_average_reward"), "reward_efficiency": last.get("reward_efficiency"), "validation": last.get("validation"), "validation_score": last.get("validation_score"), "best_epoch": training.get("best_epoch", last.get("best_epoch")), "stopping_reason": training.get("stopping_reason") or last.get("stopping_reason"), "history": history},
                "comparison": comparison,
                "evaluation": {"samples": testing.get("test_rows"), "throughput_rows_per_second": testing.get("throughput_rows_per_second"), "average_reward": testing.get("average_reward"), "oracle_average_reward": testing.get("oracle_average_reward"), "policy_optimality": testing.get("policy_optimality"), "reward_efficiency": testing.get("reward_efficiency"), "reward_regret": testing.get("reward_regret"), "action_distribution": testing.get("action_distribution"), "per_class": testing.get("per_class")},
                "model": {"path": str(MODEL_PATH), "exists": MODEL_PATH.exists(), "size_bytes": MODEL_PATH.stat().st_size if MODEL_PATH.exists() else None, "modified_at": datetime.fromtimestamp(MODEL_PATH.stat().st_mtime, tz=timezone.utc).isoformat() if MODEL_PATH.exists() else None},
                "live_inference": inference,
                "post_training": None,
            }
            return _json_safe({"status": state, "message": message, "started_at": _started_at, "pid": _process.pid if running and _process else None, "results": results})
        except Exception as exc:
            return {"status": "error", "message": f"Training telemetry error: {exc}", "results": {"training": {"history": []}, "dataset": {}, "evaluation": {}, "comparison": {}, "model": {}}}''')

    # Preserve all epoch history in the callback and isolate it per candidate/run.
    replace_function(sequential, "_write_live_candidate_metrics", '''def _write_live_candidate_metrics(config: dict[str, Any], result: dict[str, Any], index: int, count: int) -> None:
    current = {}
    if TRAIN_METRICS_PATH.exists():
        try:
            current = json.loads(TRAIN_METRICS_PATH.read_text(encoding="utf-8"))
        except Exception:
            current = {}
    same_candidate = (
        current.get("run_id") == config.get("run_id")
        and current.get("config", {}).get("candidate_index") == index
    )
    old_metrics = current.get("metrics", []) if same_candidate and isinstance(current.get("metrics"), list) else []
    merged = {int(x["epoch"]): x for x in old_metrics if isinstance(x, dict) and x.get("epoch") is not None}
    for x in result.get("metrics", []) or []:
        if isinstance(x, dict) and x.get("epoch") is not None:
            row = dict(x)
            row["run_id"] = config.get("run_id")
            merged[int(row["epoch"])] = row
    payload = {
        "run_id": config.get("run_id"),
        "config": {**config, "candidate_index": index, "candidate_count": count},
        "metrics": [merged[k] for k in sorted(merged)],
        "best_epoch": result.get("best_epoch"),
        "actual_epochs": result.get("actual_epochs"),
        "total_updates_used": result.get("total_updates_used"),
        "updates_per_epoch": result.get("updates_per_epoch"),
        "max_total_updates": result.get("max_total_updates"),
        "stopping_reason": result.get("stopping_reason"),
    }
    TRAIN_METRICS_PATH.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")''')

    seq_text = sequential.read_text(encoding="utf-8")
    seq_text = seq_text.replace('def main() -> None:\n    print(', 'def main() -> None:\n    run_id = os.getenv("REAL_RL_RUN_ID", "")\n    print(')
    seq_text = seq_text.replace('candidate_path = EXPERIMENTS_DIR / f"{name}.pt"', 'candidate_path = EXPERIMENTS_DIR / f"{run_id}__{name}.pt"')
    seq_text = seq_text.replace('{"model_name": name, "algorithm": algorithm,', '{"run_id": run_id, "model_name": name, "algorithm": algorithm,')
    seq_text = seq_text.replace('"experiment_mode": "sequential_algorithm_then_live_cycle"}', '"experiment_mode": "sequential_algorithm_then_live_cycle", "run_id": run_id}')
    seq_text = seq_text.replace('metadata={"model_name": name, "algorithm": algorithm,', 'metadata={"run_id": run_id, "model_name": name, "algorithm": algorithm,')
    seq_text = seq_text.replace('metadata={"winner": best["name"],', 'metadata={"run_id": run_id, "winner": best["name"],')
    seq_text = seq_text.replace('selected_config.update({"model_name": best["display_name"],', 'selected_config.update({"run_id": run_id, "model_name": best["display_name"],')
    sequential.write_text(seq_text, encoding="utf-8")

    # Ensure trainer history rows and config carry the current run id.
    trainer_text = trainer.read_text(encoding="utf-8")
    trainer_text = trainer_text.replace('algorithm_info = algorithm_metadata(algorithm)\n', 'algorithm_info = algorithm_metadata(algorithm)\n    run_id = os.getenv("REAL_RL_RUN_ID", "")\n')
    trainer_text = trainer_text.replace('"updates_per_epoch": updates_per_epoch,\n        "max_total_updates": update_budget,', '"updates_per_epoch": updates_per_epoch,\n        "max_total_updates": update_budget,\n        "run_id": run_id,')
    trainer_text = trainer_text.replace('"epoch": epoch, "rows": n_rows,', '"run_id": run_id, "epoch": epoch, "rows": n_rows,')
    trainer.write_text(trainer_text, encoding="utf-8")

    post.write_text('''from __future__ import annotations\n\nfrom typing import Any\n\n\ndef promote_and_infer() -> dict[str, Any]:\n    """Compatibility endpoint only. Sequential experiments already perform champion promotion and final live inference."""\n    return {\n        "status": "skipped",\n        "message": "Final promotion is owned by the sequential experiment runner; duplicate post-training inference is disabled.",\n    }\n''', encoding="utf-8")

    alerts_text = alerts.read_text(encoding="utf-8")
    alerts_text = alerts_text.replace('"policy_metrics": inference.get("summary"),', '"policy_metrics": inference,')
    alerts.write_text(alerts_text, encoding="utf-8")


def patch_frontend() -> None:
    package = ROOT / "frontend/package.json"
    data = json.loads(package.read_text(encoding="utf-8"))
    data.setdefault("dependencies", {})["recharts"] = "3.10.1"
    data["dependencies"].setdefault("react-is", "19.1.1")
    package.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    live = ROOT / "frontend/src/pages/TrainingLive.tsx"
    live.write_text(r'''import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Area,
  AreaChart,
  Brush,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./TrainingLive.css";
import { getAuthoritativeFullTrainingStatus, stopAuthoritativeFullTraining, type AuthoritativeHistoryPoint, type AuthoritativeTrainingStatus } from "../services/training.service";

const nf = new Intl.NumberFormat("en-US");
const number = (v: unknown, digits = 4) => typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : "—";
const pct = (v: unknown) => typeof v === "number" && Number.isFinite(v) ? `${(v * 100).toFixed(2)}%` : "—";

function readTheme() {
  const root = document.documentElement;
  const dark = root.dataset.theme === "dark" || root.classList.contains("dark") || root.classList.contains("theme-dark") || window.matchMedia("(prefers-color-scheme: dark)").matches;
  return {
    dark,
    text: dark ? "#e8eef7" : "#172033",
    muted: dark ? "#91a0b7" : "#667085",
    grid: dark ? "#263449" : "#dfe5ef",
    card: dark ? "#101826" : "#ffffff",
    border: dark ? "#263449" : "#d9e1ec",
    loss: dark ? "#72a8ff" : "#245fe6",
    reward: dark ? "#61d3a7" : "#087f5b",
    validation: dark ? "#c9a2ff" : "#7048e8",
    efficiency: dark ? "#ffc06b" : "#d97706",
    updates: dark ? "#ff8f73" : "#c2410c",
    allow: dark ? "#72a8ff" : "#245fe6",
    block: dark ? "#ff9277" : "#c2410c",
    review: dark ? "#caa3ff" : "#7048e8",
  };
}

function ChartCard({ title, history, data, field, color, formatter, height = 290 }: { title: string; history: AuthoritativeHistoryPoint[]; data: Record<string, any>[]; field: string; color: string; formatter: (v: unknown) => string; height?: number }) {
  const theme = readTheme();
  const best = data.length ? data.reduce((a, b) => Number(b[field] ?? -Infinity) > Number(a[field] ?? -Infinity) ? b : a, data[0]) : null;
  return <article className="tl-chart-card">
    <div className="tl-chart-head"><div><span>{title}</span><strong>{data.length ? `Epoch ${data[data.length - 1]?.epoch}` : "Waiting"}</strong></div><small>{data.length ? `${data.length} persisted epochs` : "No persisted epoch history"}</small></div>
    {!data.length ? <div className="tl-empty-chart">Waiting for the selected model to publish epoch telemetry.</div> : <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 12, right: 16, left: 6, bottom: 8 }}>
        <CartesianGrid stroke={theme.grid} strokeDasharray="4 4" vertical={false} />
        <XAxis dataKey="epoch" stroke={theme.muted} tick={{ fill: theme.muted, fontSize: 11 }} tickLine={false} axisLine={{ stroke: theme.border }} />
        <YAxis stroke={theme.muted} tick={{ fill: theme.muted, fontSize: 11 }} tickLine={false} axisLine={{ stroke: theme.border }} tickFormatter={(v) => formatter(v)} width={68} />
        <Tooltip contentStyle={{ background: theme.card, border: `1px solid ${theme.border}`, color: theme.text, borderRadius: 12 }} labelStyle={{ color: theme.text }} formatter={(value) => formatter(value)} />
        <Line type="monotone" dataKey={field} stroke={color} strokeWidth={3} dot={false} activeDot={{ r: 5, strokeWidth: 2 }} isAnimationActive={false} />
        {best && <ReferenceDot x={best.epoch} y={best[field]} r={5} fill={color} stroke={theme.card} strokeWidth={2} />}
        <Brush dataKey="epoch" height={22} stroke={color} travellerWidth={12} />
      </LineChart>
    </ResponsiveContainer>}
    <div className="tl-chart-foot"><span>Min {data.length ? formatter(Math.min(...data.map(x => Number(x[field] ?? 0)))) : "—"}</span><span>Max {data.length ? formatter(Math.max(...data.map(x => Number(x[field] ?? 0)))) : "—"}</span><span>Latest {data.length ? formatter(data[data.length - 1]?.[field]) : "—"}</span></div>
  </article>;
}

function ActionChart({ data }: { data: Record<string, any>[] }) {
  const theme = readTheme();
  return <article className="tl-chart-card tl-chart-card--wide">
    <div className="tl-chart-head"><div><span>Policy action distribution</span><strong>Dynamic across epochs</strong></div><small>100% normalized per epoch</small></div>
    {!data.length ? <div className="tl-empty-chart">Waiting for action telemetry.</div> : <ResponsiveContainer width="100%" height={320}>
      <AreaChart data={data} stackOffset="expand" margin={{ top: 12, right: 16, left: 6, bottom: 8 }}>
        <CartesianGrid stroke={theme.grid} strokeDasharray="4 4" vertical={false} />
        <XAxis dataKey="epoch" stroke={theme.muted} tick={{ fill: theme.muted, fontSize: 11 }} tickLine={false} axisLine={{ stroke: theme.border }} />
        <YAxis tickFormatter={(v) => `${Math.round(v * 100)}%`} stroke={theme.muted} tick={{ fill: theme.muted, fontSize: 11 }} width={52} />
        <Tooltip contentStyle={{ background: theme.card, border: `1px solid ${theme.border}`, color: theme.text, borderRadius: 12 }} formatter={(value) => `${(Number(value) * 100).toFixed(2)}%`} />
        <Legend wrapperStyle={{ color: theme.text }} />
        <Area type="monotone" dataKey="allow" stackId="1" stroke={theme.allow} fill={theme.allow} fillOpacity={0.72} isAnimationActive={false} />
        <Area type="monotone" dataKey="block" stackId="1" stroke={theme.block} fill={theme.block} fillOpacity={0.72} isAnimationActive={false} />
        <Area type="monotone" dataKey="human_review" stackId="1" stroke={theme.review} fill={theme.review} fillOpacity={0.72} isAnimationActive={false} />
        <Brush dataKey="epoch" height={22} stroke={theme.validation} travellerWidth={12} />
      </AreaChart>
    </ResponsiveContainer>}
  </article>;
}

export function TrainingLive() {
  const navigate = useNavigate();
  const [state, setState] = useState<AuthoritativeTrainingStatus | null>(null);
  const [error, setError] = useState("");
  const [windowSize, setWindowSize] = useState(60);
  const [followLatest, setFollowLatest] = useState(true);
  const [stopping, setStopping] = useState(false);
  const [themeTick, setThemeTick] = useState(0);

  const refresh = useCallback(async () => {
    try { setState(await getAuthoritativeFullTrainingStatus()); setError(""); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }, []);

  useEffect(() => { void refresh(); const id = window.setInterval(() => void refresh(), 2500); return () => window.clearInterval(id); }, [refresh]);
  useEffect(() => {
    const observer = new MutationObserver(() => setThemeTick(x => x + 1));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "class"] });
    return () => observer.disconnect();
  }, []);

  const training = state?.results?.training;
  const history = training?.history ?? [];
  const latest = history.at(-1);
  const runId = state?.results?.run_id;
  const selected = training?.selected_models ?? [];
  const live = (state?.results?.live_inference ?? {}) as any;
  const comparison = state?.results?.comparison as any;
  const theme = useMemo(() => readTheme(), [themeTick]);
  const size = Math.min(Math.max(windowSize, 10), Math.max(history.length, 10));
  const visible = followLatest ? history.slice(-size) : history.slice(0, size);
  const chartData = visible.map((p: any) => ({
    epoch: p.epoch,
    loss: p.loss,
    policy_reward: p.policy_reward ?? p.avg_reward,
    validation_score: p.validation_score,
    reward_efficiency: p.reward_efficiency,
    total_updates: p.total_updates,
  }));
  const actions = visible.map((p: any) => {
    const d = p.action_distribution ?? {};
    const total = Math.max(1, Number(d.allow || 0) + Number(d.block || 0) + Number(d.human_review || 0));
    return { epoch: p.epoch, allow: Number(d.allow || 0) / total, block: Number(d.block || 0) / total, human_review: Number(d.human_review || 0) / total };
  });

  const stop = async () => {
    setStopping(true);
    try { await stopAuthoritativeFullTraining(); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setStopping(false); }
  };

  return <div className="training-live-page">
    <header className="tl-hero">
      <div><div className="tl-kicker">RL CONTROL ROOM · LIVE EXPERIMENT</div><h1>{training?.display_name || training?.model_name || "Training telemetry"}</h1><p>Run-scoped learning telemetry. Every chart belongs to the current selected model and experiment run.</p><div className="tl-run-id">Run {runId || "—"}</div></div>
      <div className="tl-actions"><button onClick={() => navigate("/training")}>Choose models</button><button onClick={() => void refresh()}>Refresh</button>{state?.status === "running" && <button className="danger" disabled={stopping} onClick={() => void stop()}>{stopping ? "Stopping…" : "Stop training"}</button>}</div>
    </header>
    {error && <div className="tl-error">{error}</div>}
    <section className="tl-kpis">
      <div><span>Status</span><strong>{state?.status || "idle"}</strong></div>
      <div><span>Algorithm</span><strong>{training?.display_name || training?.algorithm || "—"}</strong></div>
      <div><span>Epoch</span><strong>{nf.format(training?.actual_epochs ?? latest?.epoch ?? 0)} / {nf.format(training?.epochs ?? 0)}</strong></div>
      <div><span>Updates</span><strong>{nf.format(training?.total_updates_used ?? 0)}</strong></div>
      <div><span>Best epoch</span><strong>{nf.format(training?.best_epoch ?? 0)}</strong></div>
      <div><span>Stop reason</span><strong>{training?.stopping_reason || "learning"}</strong></div>
    </section>
    <section className="tl-stat-grid">
      <div><span>Policy reward</span><strong>{number(training?.policy_reward ?? latest?.policy_reward, 6)}</strong></div>
      <div><span>Validation score</span><strong>{number(training?.validation_score ?? latest?.validation_score, 4)}</strong></div>
      <div><span>Reward efficiency</span><strong>{pct(training?.reward_efficiency ?? latest?.reward_efficiency)}</strong></div>
      <div><span>Live considered</span><strong>{live.alerts_considered ?? 0}</strong></div>
      <div><span>Human review</span><strong>{live.human_review_routed ?? 0}</strong></div>
    </section>
    <section className="tl-toolbar">
      <div><strong>Graph controls</strong><span>{history.length} persisted epochs · actual run {runId || "—"}</span></div>
      <label>Window <input type="range" min={10} max={Math.max(10, history.length)} value={Math.min(size, Math.max(10, history.length || 10))} onChange={e => setWindowSize(Number(e.target.value))} /></label>
      <button className={followLatest ? "active" : ""} onClick={() => setFollowLatest(true)}>Latest</button>
      <button className={!followLatest ? "active" : ""} onClick={() => setFollowLatest(false)}>Start</button>
      <button onClick={() => { setWindowSize(Math.max(10, history.length)); setFollowLatest(true); }}>All</button>
    </section>
    <section className="tl-charts-grid">
      <ChartCard title="Training loss" history={history} data={chartData} field="loss" color={theme.loss} formatter={(v) => number(v, 4)} />
      <ChartCard title="Policy reward" history={history} data={chartData} field="policy_reward" color={theme.reward} formatter={(v) => number(v, 4)} />
      <ChartCard title="Validation score" history={history} data={chartData} field="validation_score" color={theme.validation} formatter={pct} />
      <ChartCard title="Reward efficiency" history={history} data={chartData} field="reward_efficiency" color={theme.efficiency} formatter={pct} />
      <ChartCard title="Cumulative optimizer updates" history={history} data={chartData} field="total_updates" color={theme.updates} formatter={(v) => nf.format(Number(v || 0))} />
      <ActionChart data={actions} />
    </section>
    <section className="tl-bottom-grid">
      <article><span className="tl-panel-label">SELECTED MODELS</span><div className="tl-chips">{selected.length ? selected.map((s: string) => <span key={s}>{s}</span>) : <span>None</span>}</div><span className="tl-panel-label">CHAMPION</span><strong>{comparison?.best?.display_name || comparison?.best?.name || "Pending comparison"}</strong></article>
      <article><span className="tl-panel-label">CURRENT CYCLE</span><div className="tl-cycle-grid"><div><span>Cycle</span><strong>{live.cycle_id || "—"}</strong></div><div><span>Processed</span><strong>{live.alerts_processed ?? 0}</strong></div><div><span>Human review</span><strong>{live.human_review_routed ?? 0}</strong></div></div></article>
    </section>
  </div>;
}
''', encoding="utf-8")

    css = ROOT / "frontend/src/pages/TrainingLive.css"
    css.write_text(''':root{--tl-bg:#f5f7fb;--tl-surface:#fff;--tl-surface-2:#f8fafc;--tl-text:#172033;--tl-muted:#667085;--tl-border:#d9e1ec;--tl-shadow:0 18px 50px rgba(15,23,42,.08);--tl-accent:#245fe6;--tl-danger:#c2410c}.training-live-page{min-height:100%;padding:34px;background:var(--tl-bg);color:var(--tl-text)}[data-theme="dark"],.dark,.theme-dark{--tl-bg:#080d16;--tl-surface:#101826;--tl-surface-2:#121d2d;--tl-text:#e8eef7;--tl-muted:#91a0b7;--tl-border:#263449;--tl-shadow:0 24px 65px rgba(0,0,0,.28);--tl-accent:#72a8ff;--tl-danger:#ff9277}.tl-hero,.tl-kpis,.tl-stat-grid,.tl-toolbar,.tl-charts-grid,.tl-bottom-grid{max-width:1500px;margin:0 auto}.tl-hero{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;margin-bottom:22px}.tl-kicker,.tl-panel-label{font-size:11px;letter-spacing:.14em;font-weight:800;color:var(--tl-muted)}.tl-hero h1{margin:7px 0 8px;font-size:34px;letter-spacing:-.03em}.tl-hero p{margin:0;color:var(--tl-muted);max-width:760px}.tl-run-id{display:inline-flex;margin-top:14px;padding:7px 10px;border:1px solid var(--tl-border);border-radius:999px;background:var(--tl-surface);color:var(--tl-muted);font-size:12px}.tl-actions{display:flex;gap:10px;flex-wrap:wrap}.tl-actions button,.tl-toolbar button{border:1px solid var(--tl-border);background:var(--tl-surface);color:var(--tl-text);padding:10px 14px;border-radius:11px;cursor:pointer;font-weight:700}.tl-actions button:hover,.tl-toolbar button:hover{border-color:var(--tl-accent)}.tl-actions .danger{color:var(--tl-danger)}.tl-error{max-width:1500px;margin:0 auto 18px;padding:13px 15px;border:1px solid #efb6a7;background:#fff2ee;color:#9a3412;border-radius:12px}.tl-kpis,.tl-stat-grid{display:grid;gap:12px;margin-bottom:12px}.tl-kpis{grid-template-columns:repeat(6,minmax(0,1fr))}.tl-stat-grid{grid-template-columns:repeat(5,minmax(0,1fr))}.tl-kpis>div,.tl-stat-grid>div,.tl-bottom-grid article{background:var(--tl-surface);border:1px solid var(--tl-border);border-radius:16px;box-shadow:var(--tl-shadow);padding:17px}.tl-kpis span,.tl-stat-grid span,.tl-cycle-grid span{display:block;color:var(--tl-muted);font-size:12px}.tl-kpis strong,.tl-stat-grid strong{display:block;margin-top:8px;font-size:19px}.tl-toolbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;background:var(--tl-surface);border:1px solid var(--tl-border);padding:14px 16px;border-radius:16px;margin:18px auto}.tl-toolbar>div{display:flex;flex-direction:column;margin-right:auto}.tl-toolbar span{color:var(--tl-muted);font-size:12px}.tl-toolbar label{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--tl-muted)}.tl-toolbar input{accent-color:var(--tl-accent);width:160px}.tl-toolbar .active{background:var(--tl-accent);border-color:var(--tl-accent);color:#fff}.tl-charts-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.tl-chart-card{background:var(--tl-surface);border:1px solid var(--tl-border);border-radius:18px;box-shadow:var(--tl-shadow);padding:16px;min-width:0}.tl-chart-card--wide{grid-column:1/-1}.tl-chart-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;margin-bottom:6px}.tl-chart-head div{display:flex;flex-direction:column}.tl-chart-head span{font-weight:800}.tl-chart-head strong{margin-top:4px;font-size:13px;color:var(--tl-accent)}.tl-chart-head small{color:var(--tl-muted)}.tl-chart-foot{display:flex;justify-content:space-between;color:var(--tl-muted);font-size:11px;padding-top:6px}.tl-empty-chart{height:290px;display:grid;place-items:center;color:var(--tl-muted);border:1px dashed var(--tl-border);border-radius:12px}.tl-bottom-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}.tl-panel-label{display:block;margin-bottom:8px}.tl-panel-label~.tl-panel-label{margin-top:18px}.tl-chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}.tl-chips span{padding:6px 9px;border:1px solid var(--tl-border);border-radius:999px;color:var(--tl-text);background:var(--tl-surface-2);font-size:12px}.tl-cycle-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.tl-cycle-grid strong{display:block;margin-top:5px;word-break:break-word}@media(max-width:1100px){.tl-kpis{grid-template-columns:repeat(3,minmax(0,1fr))}.tl-stat-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:800px){.training-live-page{padding:18px}.tl-hero{flex-direction:column}.tl-charts-grid,.tl-bottom-grid{grid-template-columns:1fr}.tl-chart-card--wide{grid-column:auto}.tl-kpis,.tl-stat-grid{grid-template-columns:1fr 1fr}}@media(max-width:520px){.tl-kpis,.tl-stat-grid,.tl-cycle-grid{grid-template-columns:1fr}.tl-hero h1{font-size:27px}}
''', encoding="utf-8")


def main() -> None:
    print("=" * 72)
    print("RL AGENT — FINAL PROJECT STABILIZATION")
    print("=" * 72)
    files = [
        ROOT / "backend/app/services/authoritative_training_control.py",
        ROOT / "backend/app/rl_agent/trainer.py",
        ROOT / "backend/app/rl_agent/sequential_experiment.py",
        ROOT / "backend/app/services/post_training_service.py",
        ROOT / "backend/app/services/live_alert_service.py",
        ROOT / "frontend/src/pages/TrainingLive.tsx",
        ROOT / "frontend/src/pages/TrainingLive.css",
        ROOT / "frontend/package.json",
    ]
    BACKUP.mkdir(parents=True, exist_ok=True)
    for f in files:
        if f.exists():
            dst = BACKUP / f.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
    print(f"[OK] Backup: {BACKUP}")

    patch_backend()
    patch_frontend()

    print("[OK] Backend lifecycle patched.")
    print("[OK] Run-scoped telemetry patched.")
    print("[OK] Candidate history persistence patched.")
    print("[OK] Duplicate post-training inference disabled.")
    print("[OK] Analyst status telemetry corrected.")
    print("[OK] React charting upgraded to Recharts 3.10.1.")

    run(["npm", "install", "recharts@3.10.1", "react-is@19.1.1", "--save-exact"], ROOT / "frontend")

    print("\n[CHECK] Python syntax")
    py = ROOT / ".venv/bin/python"
    python = str(py if py.exists() else "python3")
    run([python, "-m", "py_compile", "backend/app/services/authoritative_training_control.py", "backend/app/rl_agent/trainer.py", "backend/app/rl_agent/sequential_experiment.py", "backend/app/services/post_training_service.py", "backend/app/services/live_alert_service.py"], ROOT)

    print("\n[CHECK] FastAPI import")
    run([python, "-c", "import sys; sys.path.insert(0, 'backend'); import main; print('[OK] FastAPI import')"], ROOT)

    print("\n[CHECK] Frontend build")
    run(["npm", "run", "build"], ROOT / "frontend")

    print("\n[CHECK] Git diff summary")
    run(["git", "status", "--short"], ROOT, check=False)
    print("\nFINAL STABILIZATION COMPLETE")
    print(f"Backup: {BACKUP}")


if __name__ == "__main__":
    main()
