import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { startAuthoritativeFullTraining, type AuthoritativeTrainingStatus } from "../services/training.service";

const MODELS = [
  { name: "dqn_lr_0005", title: "Double DQN · Conservative", lr: "0.0005", detail: "Smaller learning steps; stability-first candidate.", tag: "STABLE" },
  { name: "dqn_lr_001", title: "Double DQN · Balanced", lr: "0.001", detail: "Baseline candidate for balanced learning speed and stability.", tag: "BASELINE" },
  { name: "dqn_lr_002", title: "Double DQN · Fast", lr: "0.002", detail: "Faster updates; included to test whether learning accelerates without degrading validation.", tag: "FAST" },
];

export function TrainingLauncher() {
  const navigate = useNavigate();
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const allSelected = selected.length === MODELS.length;
  const selectionLabel = useMemo(() => selected.length === 0 ? "No model selected" : `${selected.length} candidate${selected.length === 1 ? "" : "s"} selected`, [selected.length]);

  function toggle(name: string) {
    setSelected((current) => current.includes(name) ? current.filter((item) => item !== name) : [...current, name]);
  }

  function toggleAll() {
    setSelected(allSelected ? [] : MODELS.map((item) => item.name));
  }

  async function start() {
    if (!selected.length) {
      setError("Select at least one model candidate before starting training.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await startAuthoritativeFullTraining(selected);
      navigate("/training/live");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <div className="lux-training">
      <section className="lux-hero">
        <div>
          <div className="lux-kicker">RL CONTROL ROOM · EXPERIMENT SETUP</div>
          <h1>Choose the models to train</h1>
          <p>Select exactly which candidates should participate in this experiment. There is no hidden automatic model choice. Each selected candidate trains with adaptive stopping, then receives its own fresh 40-alert live cycle.</p>
        </div>
        <div className="lux-hero-actions">
          <button className="lux-button lux-button--ghost" onClick={toggleAll}>{allSelected ? "Clear selection" : "Select all 3"}</button>
          <button className="lux-button lux-button--primary" disabled={busy || !selected.length} onClick={() => void start()}>{busy ? "Launching…" : "Train selected models"}</button>
        </div>
      </section>

      {error && <div className="lux-alert">{error}</div>}

      <section className="lux-card">
        <div className="lux-card-head">
          <div><div className="lux-card-label">MODEL SELECTION</div><h2>{selectionLabel}</h2></div>
          <span className="lux-pill">Training starts only after selection</span>
        </div>
        <div className="lux-model-selector-grid">
          {MODELS.map((model) => {
            const active = selected.includes(model.name);
            return (
              <button key={model.name} type="button" className={`lux-model-choice ${active ? "lux-model-choice--selected" : ""}`} onClick={() => toggle(model.name)}>
                <div className="lux-model-choice__top">
                  <span className="lux-model-choice__tag">{model.tag}</span>
                  <span className="lux-model-choice__check">{active ? "✓" : ""}</span>
                </div>
                <strong>{model.title}</strong>
                <span className="lux-model-choice__lr">Learning rate {model.lr}</span>
                <p>{model.detail}</p>
                <small>{active ? "Selected for this run" : "Click to include"}</small>
              </button>
            );
          })}
        </div>
      </section>

      <section className="lux-main-grid">
        <article className="lux-card">
          <div className="lux-card-label">AUTOMATIC TRAINING RULES</div>
          <h2>What happens after you choose</h2>
          <div className="lux-rule"><b>01</b><div><strong>Adaptive epochs</strong><p>4,000 is only the safety ceiling. Training stops early when validation and policy behavior stabilize or validation persistently declines.</p></div></div>
          <div className="lux-rule"><b>02</b><div><strong>Best checkpoint</strong><p>The best validation checkpoint is restored before the candidate is evaluated live.</p></div></div>
          <div className="lux-rule"><b>03</b><div><strong>Fresh live cycle</strong><p>Every completed candidate receives all 40 isolated alerts as a new MongoDB decision cycle.</p></div></div>
        </article>
        <article className="lux-card">
          <div className="lux-card-label">CURRENT SCOPE</div>
          <h2>Runnable candidates</h2>
          <p className="lux-muted">These three candidates are currently wired into the sequential Double-DQN experiment runner.</p>
          <div className="lux-mini-grid" style={{ marginTop: 14 }}>
            <div><span>Candidate pool</span><strong>3 Double DQN</strong></div>
            <div><span>Minimum</span><strong>1 selected</strong></div>
            <div><span>Maximum</span><strong>3 selected</strong></div>
            <div><span>Live holdout</span><strong>40 alerts / candidate</strong></div>
          </div>
          <div className="lux-explain"><strong>CQL / IQL / BCQ</strong><p>Their experimental adapters exist separately, but they are not silently mixed into this run until their data requirements are satisfied and their trainers are explicitly wired into the same experiment contract.</p></div>
        </article>
      </section>
    </div>
  );
}

export default TrainingLauncher;
