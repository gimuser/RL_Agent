from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd
import torch

from .dqn import DoubleDQN
from .triage_env import (
    ACTIONS,
    FEATURES,
    INCIDENT_ID,
    TARGET,
    REWARD_TABLE,
    sort_incidents,
)


class TrainingStopped(Exception):
    """Raised when an in-progress training run receives a stop request."""


def prepare_transitions(df: pd.DataFrame):

    df, timestamp_col = sort_incidents(df)

    states = []
    next_states = []
    labels = []
    dones = []
    incident_ids = []
    steps = []

    for incident_id, group in df.groupby(
        INCIDENT_ID,
        sort=False,
    ):

        rows = group.reset_index(drop=True)

        x = rows[FEATURES].astype(np.float32).values
        y = rows[TARGET].astype(int).values

        for i in range(len(rows)):
            states.append(x[i])

            if i + 1 < len(rows):
                next_states.append(x[i + 1])
            else:
                next_states.append(x[i])

            labels.append(y[i])
            dones.append(i == len(rows) - 1)
            incident_ids.append(str(incident_id))
            steps.append(i)

    return (
        np.asarray(states, dtype=np.float32),
        np.asarray(next_states, dtype=np.float32),
        np.asarray(labels, dtype=np.int64),
        np.asarray(dones, dtype=np.float32),
        incident_ids,
        np.asarray(steps, dtype=np.int64),
        timestamp_col,
    )


def _persist_metrics(output_path: Path, config: dict, metrics: list[dict]) -> None:
    output_path.write_text(
        json.dumps(
            {"config": config, "metrics": metrics},
            indent=2,
        )
    )


def train(
    train_csv: str,
    epochs: int = 10,
    batch_size: int = 512,
    learning_rate: float = 1e-3,
    gamma: float = 0.95,
    target_update: int = 1,
    seed: int = 42,
    stop_event: Optional[object] = None,
):

    np.random.seed(seed)
    torch.manual_seed(seed)

    df = pd.read_csv(train_csv)

    (
        states,
        next_states,
        labels,
        dones,
        incident_ids,
        steps,
        timestamp_col,
    ) = prepare_transitions(df)

    n_rows = len(states)

    print()
    print("=" * 70)
    print("INCIDENT-LEVEL OFFLINE RL TRAINING")
    print("=" * 70)
    print(f"Dataset          : {train_csv}")
    print(f"Rows             : {n_rows:,}")
    print(f"Incidents        : {df[INCIDENT_ID].astype(str).nunique():,}")
    print(f"Features         : {len(FEATURES)}")
    print(f"Actions          : {len(ACTIONS)}")
    print(f"Epochs           : {epochs}")
    print(f"Batch size       : {batch_size}")
    print(f"Learning rate    : {learning_rate}")
    print(f"Gamma            : {gamma}")
    print(f"Timestamp column : {timestamp_col}")
    print("Synthetic data   : NO")
    print("Real data        : YES")
    print("IncidentId state : NO")
    print("IncidentId episode: YES")

    model = DoubleDQN(
        input_dim=len(FEATURES),
        n_actions=len(ACTIONS),
        learning_rate=learning_rate,
        gamma=gamma,
    )

    metrics: list[dict] = []

    ROOT = Path(__file__).resolve().parents[3]
    MODELS = ROOT / "models"
    MODELS.mkdir(parents=True, exist_ok=True)
    metrics_path = MODELS / "training_metrics.json"
    model_path = MODELS / "real_dqn_agent.pt"

    config = {
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "gamma": gamma,
        "features": FEATURES,
        "actions": ACTIONS,
        "incident_id": INCIDENT_ID,
        "target": TARGET,
        "synthetic_data": False,
        "real_data": True,
        "incident_level_episodes": True,
    }

    # Clear stale metrics at the start of a fresh run so the UI never shows
    # the previous training run as the current one.
    _persist_metrics(metrics_path, config, metrics)

    for epoch in range(1, epochs + 1):

        start = time.perf_counter()
        indices = np.random.permutation(n_rows)
        total_loss = 0.0
        updates = 0
        action_counts = {name: 0 for name in ACTIONS.values()}
        reward_sum = 0.0
        stopped = False

        for start_idx in range(0, n_rows, batch_size):

            if stop_event is not None and getattr(stop_event, "is_set", lambda: False)():
                stopped = True
                break

            batch_idx = indices[start_idx:start_idx + batch_size]
            batch_states = states[batch_idx]
            batch_next = next_states[batch_idx]
            batch_labels = labels[batch_idx]
            batch_dones = dones[batch_idx]

            reward_matrix = np.asarray(
                [
                    [
                        REWARD_TABLE.get(
                            int(label),
                            REWARD_TABLE[3],
                        )[action]
                        for action in ACTIONS
                    ]
                    for label in batch_labels
                ],
                dtype=np.float32,
            )

            loss = model.update_counterfactual(
                batch_states,
                reward_matrix,
                batch_next,
                batch_dones,
            )

            total_loss += loss
            updates += 1

            actions = np.argmax(reward_matrix, axis=1).astype(np.int64)
            chosen_rewards = reward_matrix[
                np.arange(len(actions)),
                actions,
            ]
            reward_sum += float(chosen_rewards.sum())

            for action in actions:
                action_counts[ACTIONS[int(action)]] += 1

        if stopped:
            # Preserve the last completed epoch and persist the partial state.
            model.save(str(model_path))
            _persist_metrics(metrics_path, config, metrics)
            raise TrainingStopped(
                f"Training stop requested after {len(metrics)} completed epoch(s)."
            )

        if target_update > 0 and epoch % target_update == 0:
            model.update_target()

        elapsed = time.perf_counter() - start
        avg_loss = total_loss / max(1, updates)
        avg_reward = reward_sum / n_rows

        row = {
            "epoch": epoch,
            "rows": n_rows,
            "incidents": int(df[INCIDENT_ID].astype(str).nunique()),
            "updates": updates,
            "loss": avg_loss,
            "average_reward": avg_reward,
            "action_counts": action_counts,
            "time_seconds": elapsed,
        }

        metrics.append(row)
        _persist_metrics(metrics_path, config, metrics)

        print(
            f"Epoch {epoch:03d}/{epochs:03d} | "
            f"rows={n_rows:,} | incidents={row['incidents']:,} | "
            f"updates={updates} | loss={avg_loss:.6f} | "
            f"avg_reward={avg_reward:.6f} | time={elapsed:.2f}s"
        )
        print(f"    actions: {action_counts}")

    model.save(str(model_path))

    print()
    print("=" * 70)
    print("[OK] INCIDENT-LEVEL TRAINING COMPLETE")
    print("=" * 70)
    print(f"Rows used       : {n_rows:,}")
    print(f"Incidents used  : {df[INCIDENT_ID].astype(str).nunique():,}")
    print(f"Model           : {model_path}")

    return model
