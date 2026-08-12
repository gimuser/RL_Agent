import { useCallback, useEffect, useState } from "react";
import {
  getAuthoritativeFullTrainingStatus,
  type AuthoritativeTrainingStatus,
} from "../services/training.service";
import { apiRequest } from "../services/api";

type AlertRecord = {
  id: string | number;
  title: string;
  severity: string;
  source: string;
};

type DecisionRecord = {
  id: string | number;
  incident_id: string | number;
  action: string;
  timestamp: string;
};

type RewardRecord = {
  id: string | number;
  decision_id: string | number;
  reward_value: number;
  timestamp: string;
};

const fmt = (v: unknown) =>
  typeof v === "number"
    ? new Intl.NumberFormat("en-US", {
        maximumFractionDigits: 4,
      }).format(v)
    : "—";

const fmtInt = (v: unknown) =>
  typeof v === "number"
    ? new Intl.NumberFormat("en-US", {
        maximumFractionDigits: 0,
      }).format(v)
    : "—";

const fmtDate = (v: unknown) => {
  if (typeof v !== "string" || !v) return "—";

  const d = new Date(v);
  return Number.isNaN(d.getTime())
    ? v
    : new Intl.DateTimeFormat("en-GB", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(d);
};

function Detail({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

export function HistoryPage() {
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [decisions, setDecisions] = useState<DecisionRecord[]>([]);
  const [rewards, setRewards] = useState<RewardRecord[]>([]);

  const [training, setTraining] =
    useState<AuthoritativeTrainingStatus | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      setError("");

      const [
        alertData,
        decisionData,
        rewardData,
        trainingData,
      ] = await Promise.all([
        apiRequest<AlertRecord[]>("/api/alerts?skip=0&limit=100"),
        apiRequest<DecisionRecord[]>("/api/decisions?skip=0&limit=100"),
        apiRequest<RewardRecord[]>("/api/rewards?skip=0&limit=100"),
        getAuthoritativeFullTrainingStatus(),
      ]);

      setAlerts(alertData);
      setDecisions(decisionData);
      setRewards(rewardData);
      setTraining(trainingData);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : String(err),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();

    const timer = window.setInterval(
      refresh,
      5000,
    );

    return () => window.clearInterval(timer);
  }, [refresh]);

  const r = training?.results ?? null;
  const d = r?.dataset;
  const t = r?.training;
  const e = r?.evaluation;
  const m = r?.model;

  return (
    <>
      <header className="page-header">
        <div>
          <p className="eyebrow">SYSTEM RECORDS</p>
          <h1>History</h1>
          <p className="page-header__description">
            Live operational records plus the persisted
            authoritative RL training run. Training values
            come directly from the real training artifacts.
          </p>
        </div>

        <div className="page-header__actions">
          <button
            className="button"
            type="button"
            onClick={refresh}
          >
            Refresh
          </button>
        </div>
      </header>

      {error && (
        <section className="panel" role="alert">
          <strong>History API error</strong>
          <p>{error}</p>
        </section>
      )}

      {loading ? (
        <section className="panel">
          Loading history...
        </section>
      ) : (
        <>
          <section className="panel">
            <div className="panel__header">
              <div>
                <p className="eyebrow">
                  AUTHORITATIVE RL RUN
                </p>
                <h2>Latest real training result</h2>
              </div>
            </div>

            <dl className="detail-list">
              <Detail
                label="Status"
                value={training?.status ?? "—"}
              />

              <Detail
                label="Dataset"
                value={d?.name ?? "—"}
              />

              <Detail
                label="Epochs"
                value={fmtInt(t?.epochs)}
              />

              <Detail
                label="Batch size"
                value={fmtInt(t?.batch_size)}
              />

              <Detail
                label="Train rows"
                value={fmtInt(d?.train_rows)}
              />

              <Detail
                label="Test rows"
                value={fmtInt(d?.test_rows)}
              />

              <Detail
                label="Train incidents"
                value={fmtInt(d?.train_incidents)}
              />

              <Detail
                label="Test incidents"
                value={fmtInt(d?.test_incidents)}
              />

              <Detail
                label="Incident overlap"
                value={fmtInt(d?.incident_overlap)}
              />

              <Detail
                label="Feature count"
                value={fmtInt(d?.feature_count)}
              />

              <Detail
                label="Final loss"
                value={fmt(t?.final_loss)}
              />

              <Detail
                label="Test average reward"
                value={fmt(e?.average_reward)}
              />

              <Detail
                label="Policy optimality"
                value={
                  typeof e?.policy_optimality === "number"
                    ? `${(e.policy_optimality * 100).toFixed(2)}%`
                    : "—"
                }
              />

              <Detail
                label="Reward efficiency"
                value={
                  typeof e?.reward_efficiency === "number"
                    ? `${(e.reward_efficiency * 100).toFixed(2)}%`
                    : "—"
                }
              />

              <Detail
                label="Test throughput"
                value={
                  typeof e?.throughput_rows_per_second === "number"
                    ? `${fmt(e.throughput_rows_per_second)} rows/sec`
                    : "—"
                }
              />

              <Detail
                label="Model"
                value={
                  m?.exists
                    ? m.path ?? "Available"
                    : "—"
                }
              />
            </dl>
          </section>

          <section className="split-grid">
            <article className="panel">
              <div className="panel__header">
                <div>
                  <p className="eyebrow">
                    TRAINING POLICY
                  </p>
                  <h2>Final action distribution</h2>
                </div>
              </div>

              <dl className="detail-list">
                {t?.action_distribution ? (
                  Object.entries(
                    t.action_distribution,
                  ).map(([name, count]) => (
                    <Detail
                      key={name}
                      label={name}
                      value={fmtInt(count)}
                    />
                  ))
                ) : (
                  <Detail
                    label="Training actions"
                    value="—"
                  />
                )}
              </dl>
            </article>

            <article className="panel">
              <div className="panel__header">
                <div>
                  <p className="eyebrow">
                    UNSEEN TEST SET
                  </p>
                  <h2>Evaluation actions</h2>
                </div>
              </div>

              <dl className="detail-list">
                {e?.action_distribution ? (
                  Object.entries(
                    e.action_distribution,
                  ).map(([name, count]) => (
                    <Detail
                      key={name}
                      label={name}
                      value={fmtInt(count)}
                    />
                  ))
                ) : (
                  <Detail
                    label="Evaluation actions"
                    value="—"
                  />
                )}
              </dl>
            </article>
          </section>

          <section className="history-grid">
            <article className="panel">
              <div className="panel__header">
                <div>
                  <p className="eyebrow">
                    PERSISTED DATA
                  </p>
                  <h2>Alert history</h2>
                </div>
              </div>

              {alerts.length === 0 ? (
                <p className="muted">
                  No alert records available.
                </p>
              ) : (
                <ul className="record-list">
                  {alerts.map((alert) => (
                    <li key={alert.id}>
                      <strong>{alert.title}</strong>
                      <span>
                        {alert.severity} · {alert.source}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </article>

            <article className="panel">
              <div className="panel__header">
                <div>
                  <p className="eyebrow">
                    PERSISTED DATA
                  </p>
                  <h2>Decision history</h2>
                </div>
              </div>

              {decisions.length === 0 ? (
                <p className="muted">
                  No decision records available.
                </p>
              ) : (
                <ul className="record-list">
                  {decisions.map((decision) => (
                    <li key={decision.id}>
                      <strong>
                        {decision.action}
                      </strong>
                      <span>
                        Alert #{decision.incident_id} ·{" "}
                        {fmtDate(decision.timestamp)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </article>

            <article className="panel">
              <div className="panel__header">
                <div>
                  <p className="eyebrow">
                    PERSISTED DATA
                  </p>
                  <h2>Reward history</h2>
                </div>
              </div>

              {rewards.length === 0 ? (
                <p className="muted">
                  No reward records available.
                </p>
              ) : (
                <ul className="record-list">
                  {rewards.map((reward) => (
                    <li key={reward.id}>
                      <strong
                        className={
                          reward.reward_value >= 0
                            ? "positive"
                            : "negative"
                        }
                      >
                        {reward.reward_value >= 0
                          ? "+"
                          : ""}
                        {fmt(reward.reward_value)}
                      </strong>
                      <span>
                        Decision #{reward.decision_id} ·{" "}
                        {fmtDate(reward.timestamp)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </article>
          </section>

          <section className="panel">
            <div className="panel__header">
              <div>
                <p className="eyebrow">
                  IMPORTANT DISTINCTION
                </p>
                <h2>Real records only</h2>
              </div>
            </div>

            <p className="muted">
              The training result above is taken from the
              authoritative real-data pipeline. Alert,
              decision, and reward records below remain the
              records returned by their respective APIs.
              No synthetic decision or reward records are
              created merely to populate this page.
            </p>
          </section>
        </>
      )}
    </>
  );
}

export default HistoryPage;
