from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Dict

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

        x = rows[FEATURES].astype(
            np.float32
        ).values

        y = rows[TARGET].astype(
            int
        ).values

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


def train(
    train_csv: str,
    epochs: int = 10,
    batch_size: int = 512,
    learning_rate: float = 1e-3,
    gamma: float = 0.95,
    target_update: int = 1,
    seed: int = 42,
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
    print(
        f"Incidents        : "
        f"{df[INCIDENT_ID].astype(str).nunique():,}"
    )
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

    metrics = []

    for epoch in range(1, epochs + 1):

        start = time.perf_counter()

        indices = np.random.permutation(
            n_rows
        )

        total_loss = 0.0
        updates = 0

        action_counts = {
            name: 0
            for name in ACTIONS.values()
        }

        reward_sum = 0.0

        for start_idx in range(
            0,
            n_rows,
            batch_size,
        ):

            batch_idx = indices[
                start_idx:
                start_idx + batch_size
            ]

            batch_states = states[batch_idx]
            batch_next = next_states[batch_idx]
            batch_labels = labels[batch_idx]
            batch_dones = dones[batch_idx]

            # Counterfactual offline RL:
            # every state has a real reward for every valid action.
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

            # Monitoring only:
            # action with the highest real counterfactual reward.
            actions = np.argmax(
                reward_matrix,
                axis=1,
            ).astype(np.int64)

            chosen_rewards = reward_matrix[
                np.arange(len(actions)),
                actions,
            ]

            reward_sum += float(
                chosen_rewards.sum()
            )

            for action in actions:
                action_counts[
                    ACTIONS[int(action)]
                ] += 1

        if (
            target_update > 0
            and epoch % target_update == 0
        ):
            model.update_target()

        elapsed = (
            time.perf_counter()
            - start
        )

        avg_loss = (
            total_loss / max(1, updates)
        )

        avg_reward = (
            reward_sum / n_rows
        )

        row = {
            "epoch": epoch,
            "rows": n_rows,
            "incidents": int(
                df[INCIDENT_ID]
                .astype(str)
                .nunique()
            ),
            "updates": updates,
            "loss": avg_loss,
            "average_reward": avg_reward,
            "action_counts": action_counts,
            "time_seconds": elapsed,
        }

        metrics.append(row)

        print(
            f"Epoch {epoch:03d}/{epochs:03d} | "
            f"rows={n_rows:,} | "
            f"incidents={row['incidents']:,} | "
            f"updates={updates} | "
            f"loss={avg_loss:.6f} | "
            f"avg_reward={avg_reward:.6f} | "
            f"time={elapsed:.2f}s"
        )

        print(
            f"    actions: {action_counts}"
        )

    ROOT = Path(__file__).resolve().parents[3]
    MODELS = ROOT / "models"
    MODELS.mkdir(parents=True, exist_ok=True)

    model_path = (
        str(MODELS / "real_dqn_agent.pt")
    )

    model.save(model_path)

    output = {
        "config": {
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
        },
        "metrics": metrics,
    }

    Path(
        str(MODELS / "training_metrics.json")
    ).write_text(
        json.dumps(
            output,
            indent=2,
        )
    )

    print()
    print("=" * 70)
    print("[OK] INCIDENT-LEVEL TRAINING COMPLETE")
    print("=" * 70)

    print(
        f"Rows used       : {n_rows:,}"
    )

    print(
        f"Incidents used  : "
        f"{df[INCIDENT_ID].astype(str).nunique():,}"
    )

    print(
        f"Model           : {model_path}"
    )

    return model


# ==========================================================================
# BACKWARD-COMPATIBLE APPLICATION TRAINER
# ==========================================================================
#
# Existing FastAPI/service code imports:
#
#     from app.rl_agent.trainer import Trainer
#
# The authoritative training implementation remains the module-level
# train() function above.
# ==========================================================================

class _CompatibilityAgent:
    """Minimal application compatibility object."""

    def __init__(self):
        self.model = None


class Trainer:
    """
    Compatibility facade around the authoritative real-data trainer.

    It preserves the application-layer interface without replacing
    the actual training implementation.
    """

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

        self.config = (
            kwargs.get("agent_config")
            or kwargs.get("config")
            or {}
        )

        self.agent = _CompatibilityAgent()

        self.model = None
        self.result = None

    def train(self, *args, **kwargs):
        """
        Delegate to the authoritative module-level train() function.
        """

        import inspect
        from pathlib import Path

        # Prefer explicit train_csv.
        train_csv = kwargs.get("train_csv")

        if train_csv is None:
            train_csv = kwargs.get("dataset")
        
        if train_csv is None:
            train_csv = kwargs.get("path")

        if train_csv is None:
            # Application services historically use the project's
            # real train dataset.
            root = Path(__file__).resolve().parents[3]
            train_csv = (
                root
                / "data"
                / "rl_incident"
                / "train_incident.csv"
            )

            # Fallback if the incident split does not yet exist.
            if not train_csv.exists():
                train_csv = (
                    root
                    / "data"
                    / "processed"
                    / "train_processed.csv"
                )

        sig = inspect.signature(train)

        call_kwargs = {}

        if "train_csv" in sig.parameters:
            call_kwargs["train_csv"] = str(train_csv)

        # Pull configuration from known application forms.
        cfg = {}

        if isinstance(self.config, dict):
            cfg.update(self.config)

        cfg.update(kwargs)

        if "epochs" in sig.parameters:
            call_kwargs["epochs"] = int(
                cfg.get(
                    "epochs",
                    cfg.get(
                        "training_passes",
                        1,
                    ),
                )
            )

        if "batch_size" in sig.parameters:
            call_kwargs["batch_size"] = int(
                cfg.get("batch_size", 512)
            )

        if "learning_rate" in sig.parameters:
            call_kwargs["learning_rate"] = float(
                cfg.get("learning_rate", 1e-3)
            )

        if "gamma" in sig.parameters:
            call_kwargs["gamma"] = float(
                cfg.get("gamma", 0.95)
            )

        if "target_update" in sig.parameters:
            call_kwargs["target_update"] = int(
                cfg.get("target_update", 1)
            )

        if "seed" in sig.parameters:
            call_kwargs["seed"] = int(
                cfg.get("seed", 42)
            )

        # The authoritative train() already expects the train_csv path.
        if "train_csv" in sig.parameters:
            result = train(**call_kwargs)
        else:
            # Compatibility fallback.
            result = train(str(train_csv))

        self.model = result
        self.agent.model = result
        self.result = result

        return result

    def run(self, *args, **kwargs):
        return self.train(*args, **kwargs)

    def fit(self, *args, **kwargs):
        return self.train(*args, **kwargs)

    def evaluate(self, *args, **kwargs):
        """
        Evaluation is handled by evaluator.py.
        Keep this method for application compatibility.
        """
        return None
