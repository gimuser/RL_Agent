from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .dqn import DoubleDQN
from .triage_env import (
    ACTIONS,
    FEATURES,
    INCIDENT_ID,
    TARGET,
    LABELS,
    REWARD_TABLE,
    sort_incidents,
)


def evaluate(
    test_csv: str,
    model_path: str = "models/real_dqn_agent.pt",
):

    df = pd.read_csv(test_csv)

    overlap_path = Path(
        "data/rl_incident/train_incidents.txt"
    )

    df, timestamp_col = sort_incidents(df)

    model = DoubleDQN(
        input_dim=len(FEATURES),
        n_actions=len(ACTIONS),
        gamma=0.95,
    )

    model.load(model_path)

    total_reward = 0.0
    optimal_reward = 0.0

    action_counts = {
        name: 0
        for name in ACTIONS.values()
    }

    class_stats = {
        int(label): {
            "rows": 0,
            "reward": 0.0,
            "optimal_reward": 0.0,
        }
        for label in LABELS
    }

    predictions = []

    start = time.perf_counter()

    for incident_id, group in df.groupby(
        INCIDENT_ID,
        sort=False,
    ):

        rows = group.reset_index(drop=True)

        states = rows[
            FEATURES
        ].astype(
            np.float32
        ).values

        labels = rows[
            TARGET
        ].astype(
            int
        ).values

        q_values = model.q_values(
            states
        )

        actions = np.argmax(
            q_values,
            axis=1,
        )

        for i in range(len(rows)):

            label = int(labels[i])
            action = int(actions[i])

            rewards = REWARD_TABLE.get(
                label,
                REWARD_TABLE[3],
            )

            reward = float(
                rewards[action]
            )

            optimal = float(
                max(rewards.values())
            )

            total_reward += reward
            optimal_reward += optimal

            action_name = ACTIONS[action]

            action_counts[
                action_name
            ] += 1

            class_stats[
                label
            ]["rows"] += 1

            class_stats[
                label
            ]["reward"] += reward

            class_stats[
                label
            ]["optimal_reward"] += optimal

            predictions.append(
                {
                    "IncidentId": str(
                        incident_id
                    ),
                    "step": i,
                    "label": label,
                    "label_name": LABELS.get(
                        label,
                        "Unknown",
                    ),
                    "action": action,
                    "action_name": action_name,
                    "reward": reward,
                    "optimal_reward": optimal,
                    "q_allow": float(
                        q_values[i][0]
                    ),
                    "q_block": float(
                        q_values[i][1]
                    ),
                    "q_human_review": float(
                        q_values[i][2]
                    ),
                    "done": (
                        i == len(rows) - 1
                    ),
                }
            )

    elapsed = (
        time.perf_counter()
        - start
    )

    n = len(predictions)

    avg_reward = (
        total_reward / n
        if n
        else 0.0
    )

    regret = (
        optimal_reward
        - total_reward
    )

    efficiency = (
        total_reward / optimal_reward
        if optimal_reward
        else 0.0
    )

    # Policy optimality:
    optimal_actions = 0

    for p in predictions:

        label = int(
            p["label"]
        )

        action = int(
            p["action"]
        )

        rewards = REWARD_TABLE.get(
            label,
            REWARD_TABLE[3],
        )

        if p["reward"] == max(
            rewards.values()
        ):
            optimal_actions += 1

    policy_optimality = (
        optimal_actions / n
        if n
        else 0.0
    )

    latency_ms = (
        elapsed / n * 1000
        if n
        else 0.0
    )

    throughput = (
        n / elapsed
        if elapsed
        else 0.0
    )

    class_results = {}

    for label, stats in class_stats.items():

        rows = stats["rows"]

        class_results[
            LABELS.get(
                label,
                "Unknown",
            )
        ] = {
            "rows": rows,
            "average_reward": (
                stats["reward"] / rows
                if rows
                else 0.0
            ),
            "optimality": (
                stats["reward"]
                /
                stats["optimal_reward"]
                if stats[
                    "optimal_reward"
                ]
                else 0.0
            ),
        }

    metrics = {
        "test_rows": n,
        "test_incidents": int(
            df[INCIDENT_ID]
            .astype(str)
            .nunique()
        ),
        "total_reward": total_reward,
        "average_reward": avg_reward,
        "optimal_possible_reward": optimal_reward,
        "reward_regret": regret,
        "reward_efficiency": efficiency,
        "policy_optimality": policy_optimality,
        "evaluation_time_seconds": elapsed,
        "average_latency_ms_per_row": latency_ms,
        "throughput_rows_per_second": throughput,
        "action_distribution": action_counts,
        "per_class": class_results,
        "timestamp_column": timestamp_col,
        "synthetic_data": False,
        "unseen_incidents": True,
    }

    (Path(__file__).resolve().parents[3] / "models" / "real_test_metrics.json").write_text(
        json.dumps(
            metrics,
            indent=2,
        )
    )

    pd.DataFrame(
        predictions
    ).to_csv(
        str(Path(__file__).resolve().parents[3] / "models" / "test_predictions.csv"),
        index=False,
    )

    print()
    print("=" * 70)
    print("REAL UNSEEN-INCIDENT TEST EVALUATION")
    print("=" * 70)

    print(
        f"Test rows              : {n:,}"
    )

    print(
        f"Test incidents         : "
        f"{metrics['test_incidents']:,}"
    )

    print(
        f"Total reward           : "
        f"{total_reward:.6f}"
    )

    print(
        f"Average reward         : "
        f"{avg_reward:.6f}"
    )

    print(
        f"Optimal possible       : "
        f"{optimal_reward:.6f}"
    )

    print(
        f"Reward regret          : "
        f"{regret:.6f}"
    )

    print(
        f"Reward efficiency      : "
        f"{efficiency:.6f}"
    )

    print(
        f"Policy optimality      : "
        f"{policy_optimality:.6f}"
    )

    print(
        f"Evaluation time        : "
        f"{elapsed:.4f}s"
    )

    print(
        f"Average latency        : "
        f"{latency_ms:.6f} ms/row"
    )

    print(
        f"Throughput             : "
        f"{throughput:.2f} rows/s"
    )

    print()
    print("ACTION DISTRIBUTION")

    for name, count in action_counts.items():

        pct = (
            count / n * 100
            if n
            else 0.0
        )

        print(
            f"  {name:<35}"
            f"{count:>10,} "
            f"{pct:>7.3f}%"
        )

    print()
    print("PER-CLASS RESULTS")

    for name, result in class_results.items():

        print(
            f"  {name:<20}"
            f"rows={result['rows']:,} "
            f"reward={result['average_reward']:+.6f} "
            f"optimality={result['optimality']:.4f}"
        )

    print()
    print(
        "[OK] Test contains unseen incidents only"
    )

    print(
        "[OK] Predictions saved:"
    )

    print(
        "    models/test_predictions.csv"
    )

    print(
        "[OK] Metrics saved:"
    )

    print(
        "    models/real_test_metrics.json"
    )

    predictions_path = Path(
        "models/real_test_predictions.jsonl"
    )

    predictions_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with predictions_path.open(
        "w",
        encoding="utf-8",
    ) as prediction_file:
        for prediction in predictions:
            prediction_file.write(
                json.dumps(
                    prediction,
                    ensure_ascii=False,
                )
                + "\n"
            )

    print("[OK] Real predictions saved:")
    print(f"    {predictions_path}")

    return metrics
