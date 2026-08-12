import { useCallback, useEffect, useState } from "react";
import {
  getAuthoritativeFullTrainingStatus,
  startAuthoritativeFullTraining,
  type AuthoritativeTrainingStatus,
} from "../services/training.service";

const numberFmt = new Intl.NumberFormat("en-US");

function num(value: unknown) {
  return typeof value === "number"
    ? numberFmt.format(value)
    : "—";
}

function decimal(value: unknown) {
  return typeof value === "number"
    ? value.toFixed(6)
    : "—";
}

function pct(value: unknown) {
  return typeof value === "number"
    ? `${(value * 100).toFixed(2)}%`
    : "—";
}

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

export function TrainingPage() {
  const [response, setResponse] =
    useState<AuthoritativeTrainingStatus | null>(null);

  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const value =
        await getAuthoritativeFullTrainingStatus();

      setResponse(value);
      setError("");
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : String(e),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();

    const timer = window.setInterval(
      refresh,
      3000,
    );

    return () => window.clearInterval(timer);
  }, [refresh]);

  const start = async () => {
    const confirmed = window.confirm(
      "Start the complete real-data RL training pipeline?",
    );

    if (!confirmed) return;

    try {
      setStarting(true);
      setError("");

      await startAuthoritativeFullTraining();

      await refresh();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : String(e),
      );
    } finally {
      setStarting(false);
    }
  };

  const r = response?.results ?? null;
  const d = r?.dataset;
  const t = r?.training;
  const e = r?.evaluation;
  const m = r?.model;

  const history = t?.history ?? [];
  const latestHistory = history.length
    ? history[history.length - 1]
    : null;

  const liveAverageReward =
    t?.final_avg_reward ??
    latestHistory?.avg_reward ??
    latestHistory?.average_reward ??
    null;

  const liveActionDistribution =
    t?.action_distribution ??
    latestHistory?.action_distribution ??
    null;

  return (
    <>
      <header className="page-header">
        <div>
          <p className="eyebrow">MODEL TRAINING</p>

          <h1>Training control</h1>

          <p className="page-header__description">
            Authoritative real-data incident-level RL
            pipeline. Every displayed number comes from
            persisted authoritative training results.
            Missing values are shown as —.
          </p>
        </div>

        <div className="page-header__actions">
          <button
            className="button button--primary"
            type="button"
            disabled={
              starting ||
              response?.status === "running"
            }
            onClick={start}
          >
            {starting ||
            response?.status === "running"
              ? "Full training running..."
              : "Full training on real dataset"}
          </button>

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
          <strong>Training API error</strong>
          <p>{error}</p>
        </section>
      )}

      {loading ? (
        <section className="panel">
          Loading authoritative training results...
        </section>
      ) : (
        <>
          <section className="kpi-grid kpi-grid--four">
            <article className="kpi-card">
              <span>Training status</span>
              <strong>{response?.status ?? "—"}</strong>
              <p>Authoritative pipeline</p>
            </article>

            <article className="kpi-card">
              <span>Epochs</span>
              <strong>{num(t?.epochs)}</strong>
              <p>Persisted epochs</p>
            </article>

            <article className="kpi-card">
              <span>Final loss</span>
              <strong>{decimal(t?.final_loss)}</strong>
              <p>Last recorded epoch</p>
            </article>

            <article className="kpi-card">
              <span>Mean reward</span>
              <strong>{decimal(liveAverageReward)}</strong>
              <p>Last recorded epoch</p>
            </article>
          </section>

          <section className="panel">
            <div className="panel__header">
              <div>
                <p className="eyebrow">
                  AUTHORITATIVE PIPELINE
                </p>
                <h2>Training data</h2>
              </div>
            </div>

            <dl className="detail-list">
              <Detail
                label="Dataset"
                value={d?.name ?? "—"}
              />

              <Detail
                label="Feature count"
                value={num(d?.feature_count)}
              />

              <Detail
                label="Train rows"
                value={num(d?.train_rows)}
              />

              <Detail
                label="Test rows"
                value={num(d?.test_rows)}
              />

              <Detail
                label="Train incidents"
                value={num(d?.train_incidents)}
              />

              <Detail
                label="Test incidents"
                value={num(d?.test_incidents)}
              />

              <Detail
                label="Incident overlap"
                value={num(d?.incident_overlap)}
              />

              <Detail
                label="Batch size"
                value={num(t?.batch_size)}
              />

              <Detail
                label="Final epoch"
                value={num(t?.final_epoch)}
              />

              <Detail
                label="Updates / epoch"
                value={num(t?.updates_per_epoch)}
              />

              <Detail
                label="Synthetic data"
                value={
                  typeof d?.synthetic_data === "boolean"
                    ? String(d.synthetic_data)
                    : "—"
                }
              />

              <Detail
                label="Unseen incidents"
                value={
                  typeof d?.unseen_incidents === "boolean"
                    ? String(d.unseen_incidents)
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
                    MODEL
                  </p>
                  <h2>Current model</h2>
                </div>
              </div>

              <dl className="detail-list">
                <Detail
                  label="Exists"
                  value={
                    typeof m?.exists === "boolean"
                      ? String(m.exists)
                      : "—"
                  }
                />

                <Detail
                  label="Path"
                  value={m?.path ?? "—"}
                />

                <Detail
                  label="Size"
                  value={
                    typeof m?.size_bytes === "number"
                      ? `${num(m.size_bytes)} bytes`
                      : "—"
                  }
                />

                <Detail
                  label="Modified"
                  value={m?.modified_at ?? "—"}
                />
              </dl>
            </article>

            <article className="panel">
              <div className="panel__header">
                <div>
                  <p className="eyebrow">
                    FINAL TRAINING POLICY
                  </p>
                  <h2>Action distribution</h2>
                </div>
              </div>

              <dl className="detail-list">
                {t?.action_distribution
                  ? Object.entries(
                      t.action_distribution,
                    ).map(([name, value]) => (
                      <Detail
                        key={name}
                        label={name}
                        value={num(value)}
                      />
                    ))
                  : (
                    <Detail
                      label="Actions"
                      value="—"
                    />
                  )}
              </dl>
            </article>
          </section>

          <section className="panel">
            <div className="panel__header">
              <div>
                <p className="eyebrow">
                  UNSEEN-INCIDENT EVALUATION
                </p>
                <h2>Test results</h2>
              </div>
            </div>

            <dl className="detail-list">
              <Detail
                label="Evaluation samples"
                value={num(e?.samples)}
              />

              <Detail
                label="Throughput"
                value={
                  typeof e?.throughput_rows_per_second ===
                  "number"
                    ? `${e.throughput_rows_per_second.toFixed(
                        2,
                      )} rows/sec`
                    : "—"
                }
              />
            </dl>

            <div className="divider" />

            <h3>Test action distribution</h3>

            <dl className="detail-list">
              {e?.action_distribution
                ? Object.entries(
                    e.action_distribution,
                  ).map(([name, value]) => (
                    <Detail
                      key={name}
                      label={name}
                      value={num(value)}
                    />
                  ))
                : (
                  <Detail
                    label="Actions"
                    value="—"
                  />
                )}
            </dl>

            {e?.per_class && (
              <>
                <div className="divider" />

                <h3>
                  Per-class evaluation
                </h3>

                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Class</th>
                        <th>Rows</th>
                        <th>
                          Average reward
                        </th>
                        <th>
                          Optimality
                        </th>
                      </tr>
                    </thead>

                    <tbody>
                      {Object.entries(
                        e.per_class,
                      ).map(
                        ([name, value]) => (
                          <tr key={name}>
                            <td>{name}</td>
                            <td>
                              {num(value.rows)}
                            </td>
                            <td>
                              {decimal(
                                value.average_reward,
                              )}
                            </td>
                            <td>
                              {pct(
                                value.optimality,
                              )}
                            </td>
                          </tr>
                        ),
                      )}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </section>

          <section className="panel">
            <div className="panel__header">
              <div>
                <p className="eyebrow">
                  LOSS CURVE
                </p>
                <h2>
                  Authoritative epoch history
                </h2>
              </div>
            </div>

            {history.length === 0 ? (
              <p className="muted">
                No persisted epoch history
                available.
              </p>
            ) : (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Epoch</th>
                      <th>Loss</th>
                      <th>Average reward</th>
                      <th>Updates</th>
                    </tr>
                  </thead>

                  <tbody>
                    {history.map((row) => (
                      <tr key={row.epoch}>
                        <td>
                          {num(row.epoch)}
                        </td>
                        <td>
                          {decimal(row.loss)}
                        </td>
                        <td>
                          {decimal(
                            row.avg_reward,
                          )}
                        </td>
                        <td>
                          {num(row.updates)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </>
  );
}

export default TrainingPage;
