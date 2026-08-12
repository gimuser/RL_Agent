from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd
import torch

from .dqn import DoubleDQN
from .triage_env import (
    ACTIONS,
    FEATURES,
    INCIDENT_ID,
    LABELS,
    REWARD_TABLE,
    TARGET,
    sort_incidents,
)


class TrainingStopped(Exception):
    """Raised when a managed training process receives a stop request."""


def prepare_transitions(df: pd.DataFrame):
    df, timestamp_col = sort_incidents(df)
    states, next_states, labels, dones = [], [], [], []
    incident_ids, steps = [], []

    for incident_id, group in df.groupby(INCIDENT_ID, sort=False):
        rows = group.reset_index(drop=True)
        x = rows[FEATURES].astype(np.float32).values
        y = rows[TARGET].astype(int).values
        for i in range(len(rows)):
            states.append(x[i])
            next_states.append(x[i + 1] if i + 1 < len(rows) else x[i])
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


def _counterfactual_rewards(labels: np.ndarray) -> np.ndarray:
    matrix = np.zeros((len(labels), len(ACTIONS)), dtype=np.float32)
    for i, label in enumerate(labels):
        row = REWARD_TABLE.get(int(label), REWARD_TABLE[3])
        for action in ACTIONS:
            matrix[i, action] = float(row[action])
    return matrix


def evaluate_policy(model: DoubleDQN, csv_path: str) -> dict:
    """Evaluate the current policy against held-out incidents."""
    df = pd.read_csv(csv_path, low_memory=False)
    df, _ = sort_incidents(df)

    total_reward = 0.0
    optimal_reward = 0.0
    optimal_actions = 0
    rows = 0
    action_counts = {name: 0 for name in ACTIONS.values()}
    class_stats: dict[int, dict[str, float]] = {}

    start = time.perf_counter()

    for _, group in df.groupby(INCIDENT_ID, sort=False):
        batch = group.reset_index(drop=True)
        states = batch[FEATURES].astype(np.float32).values
        labels = batch[TARGET].astype(int).values
        q_values = model.q_values(states)
        actions = np.argmax(q_values, axis=1)

        for label, action in zip(labels, actions):
            label = int(label)
            action = int(action)
            rewards = REWARD_TABLE.get(label, REWARD_TABLE[3])
            reward = float(rewards[action])
            best = float(max(rewards.values()))

            total_reward += reward
            optimal_reward += best
            optimal_actions += int(reward == best)
            rows += 1
            action_counts[ACTIONS[action]] += 1

            stats = class_stats.setdefault(label, {"rows": 0.0, "reward": 0.0, "optimal": 0.0})
            stats["rows"] += 1
            stats["reward"] += reward
            stats["optimal"] += best

    elapsed = time.perf_counter() - start
    average_reward = total_reward / rows if rows else 0.0
    reward_efficiency = total_reward / optimal_reward if optimal_reward else 0.0
    policy_optimality = optimal_actions / rows if rows else 0.0

    per_class: dict[str, dict] = {}
    for label, stats in class_stats.items():
        n = int(stats["rows"])
        per_class[LABELS.get(label, "Unknown")] = {
            "rows": n,
            "average_reward": stats["reward"] / n if n else 0.0,
            "optimality": stats["reward"] / stats["optimal"] if stats["optimal"] else 0.0,
        }

    return {
        "rows": rows,
        "incidents": int(df[INCIDENT_ID].astype(str).nunique()),
        "total_reward": total_reward,
        "average_reward": average_reward,
        "oracle_average_reward": optimal_reward / rows if rows else 0.0,
        "reward_efficiency": reward_efficiency,
        "policy_optimality": policy_optimality,
        "action_distribution": action_counts,
        "evaluation_time_seconds": elapsed,
        "per_class": per_class,
    }


def train(
    train_csv: str,
    epochs: int = 4000,
    batch_size: int = 512,
    learning_rate: float = 1e-3,
    gamma: float = 0.95,
    target_update: int = 1,
    seed: int = 42,
    stop_event: Optional[object] = None,
    validation_csv: str | None = None,
    min_epochs: int = 20,
    patience: int = 10,
    min_delta: float = 1e-3,
    stability_window: int = 6,
    stability_tolerance: float = 0.002,
    checkpoint_path: str | None = None,
    progress_callback: Optional[Callable[[dict], None]] = None,
    max_total_updates: int | None = None,
):
    np.random.seed(seed)
    torch.manual_seed(seed)

    df = pd.read_csv(train_csv, low_memory=False)
    states, next_states, labels, dones, _, _, timestamp_col = prepare_transitions(df)
    n_rows = len(states)
    updates_per_epoch = math.ceil(n_rows / batch_size) if n_rows else 0
    automatic_update_budget = max(1, updates_per_epoch * max(1, epochs))
    update_budget = int(max_total_updates) if max_total_updates else automatic_update_budget

    model = DoubleDQN(
        input_dim=len(FEATURES),
        n_actions=len(ACTIONS),
        learning_rate=learning_rate,
        gamma=gamma,
    )

    metrics: list[dict] = []
    best_score = -float("inf")
    best_epoch = 0
    best_validation: dict | None = None
    epochs_without_improvement = 0
    total_updates_used = 0
    stopping_reason = "max_epochs"

    root = Path(__file__).resolve().parents[3]
    models_dir = root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = models_dir / "training_metrics.json"
    candidate_checkpoint = Path(checkpoint_path) if checkpoint_path else None
    if candidate_checkpoint:
        candidate_checkpoint.parent.mkdir(parents=True, exist_ok=True)

    config = {
        "epochs": epochs,
        "max_epochs": epochs,
        "min_epochs": min_epochs,
        "patience": patience,
        "min_delta": min_delta,
        "stability_window": stability_window,
        "stability_tolerance": stability_tolerance,
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
        "early_stopping": validation_csv is not None,
        "timestamp_column": timestamp_col,
        "updates_per_epoch": updates_per_epoch,
        "max_total_updates": update_budget,
        "update_budget_mode": "automatic_from_dataset_size_and_epoch_ceiling",
        "stopping_mode": "best_validation_plus_convergence_plus_persistent_decline",
    }
    metrics_path.write_text(json.dumps({"config": config, "metrics": []}, indent=2), encoding="utf-8")

    print("=" * 70)
    print("INCIDENT-LEVEL OFFLINE RL TRAINING")
    print("=" * 70)
    print(f"Rows             : {n_rows:,}")
    print(f"Incidents        : {df[INCIDENT_ID].astype(str).nunique():,}")
    print(f"Max epochs       : {epochs}")
    print(f"Min epochs       : {min_epochs}")
    print(f"Patience         : {patience}")
    print(f"Min delta        : {min_delta}")
    print(f"Stability window : {stability_window}")
    print(f"Stability tol.   : {stability_tolerance}")
    print(f"Batch size       : {batch_size}")
    print(f"Updates / epoch  : {updates_per_epoch}")
    print(f"Update budget    : {update_budget}")
    print(f"Learning rate    : {learning_rate}")
    print(f"Validation data  : {validation_csv or 'disabled'}")

    for epoch in range(1, epochs + 1):
        if stop_event is not None and getattr(stop_event, "is_set", lambda: False)():
            stopping_reason = "manual_stop"
            raise TrainingStopped(f"Training stopped before epoch {epoch}.")
        if total_updates_used >= update_budget:
            stopping_reason = "update_budget"
            break

        epoch_start = time.perf_counter()
        indices = np.random.permutation(n_rows)
        total_loss = 0.0
        updates = 0
        policy_reward_sum = 0.0
        oracle_reward_sum = 0.0
        action_counts = {name: 0 for name in ACTIONS.values()}

        for start_idx in range(0, n_rows, batch_size):
            if stop_event is not None and getattr(stop_event, "is_set", lambda: False)():
                stopping_reason = "manual_stop"
                raise TrainingStopped(f"Training stopped during epoch {epoch}.")
            if total_updates_used >= update_budget:
                break

            batch_idx = indices[start_idx:start_idx + batch_size]
            batch_states = states[batch_idx]
            batch_next = next_states[batch_idx]
            batch_labels = labels[batch_idx]
            batch_dones = dones[batch_idx]

            reward_matrix = _counterfactual_rewards(batch_labels)
            loss = model.update_counterfactual(batch_states, reward_matrix, batch_next, batch_dones)
            total_loss += loss
            updates += 1
            total_updates_used += 1

            q_values = model.q_values(batch_states)
            policy_actions = np.argmax(q_values, axis=1).astype(np.int64)
            policy_rewards = reward_matrix[np.arange(len(policy_actions)), policy_actions]
            oracle_rewards = reward_matrix.max(axis=1)
            policy_reward_sum += float(policy_rewards.sum())
            oracle_reward_sum += float(oracle_rewards.sum())
            for action in policy_actions:
                action_counts[ACTIONS[int(action)]] += 1

        if target_update > 0 and epoch % target_update == 0:
            model.update_target()

        elapsed = time.perf_counter() - epoch_start
        average_loss = total_loss / max(updates, 1)
        average_policy_reward = policy_reward_sum / n_rows if n_rows else 0.0
        average_oracle_reward = oracle_reward_sum / n_rows if n_rows else 0.0
        policy_reward_efficiency = average_policy_reward / average_oracle_reward if average_oracle_reward else 0.0
        validation = evaluate_policy(model, validation_csv) if validation_csv else None

        if validation:
            validation_score = 0.70 * validation["policy_optimality"] + 0.30 * validation["reward_efficiency"]
            improved = validation_score > best_score + min_delta
            if improved:
                best_score = validation_score
                best_epoch = epoch
                best_validation = validation
                epochs_without_improvement = 0
                if candidate_checkpoint:
                    model.save(str(candidate_checkpoint))
            else:
                epochs_without_improvement += 1
        else:
            validation_score = None
            improved = False

        row = {
            "epoch": epoch,
            "rows": n_rows,
            "incidents": int(df[INCIDENT_ID].astype(str).nunique()),
            "updates": updates,
            "total_updates": total_updates_used,
            "updates_per_epoch": updates_per_epoch,
            "loss": average_loss,
            "average_reward": average_policy_reward,
            "policy_reward": average_policy_reward,
            "oracle_average_reward": average_oracle_reward,
            "reward_efficiency": policy_reward_efficiency,
            "action_counts": action_counts,
            "time_seconds": elapsed,
            "validation": validation,
            "validation_score": validation_score,
            "best_epoch": best_epoch,
            "patience_used": epochs_without_improvement,
            "improved": improved,
            "stopping_reason": None,
        }
        metrics.append(row)

        convergence_detected = False
        persistent_decline = False
        if validation and epoch >= min_epochs:
            recent = [
                r.get("validation_score")
                for r in metrics[-stability_window:]
                if isinstance(r.get("validation_score"), (int, float))
            ]
            recent_rewards = [
                r.get("policy_reward")
                for r in metrics[-stability_window:]
                if isinstance(r.get("policy_reward"), (int, float))
            ]
            if len(recent) == stability_window and len(recent_rewards) == stability_window:
                validation_flat = max(recent) - min(recent) <= stability_tolerance
                reward_span = max(recent_rewards) - min(recent_rewards)
                reward_reference = max(abs(float(np.mean(recent_rewards))), 1.0)
                reward_flat = reward_span <= max(stability_tolerance, reward_reference * 0.0025)
                no_recent_improvement = all(
                    float(score) <= best_score + min_delta for score in recent
                )
                convergence_detected = validation_flat and reward_flat and no_recent_improvement

            if len(recent) == stability_window:
                persistent_decline = (
                    recent[-1] < best_score - min_delta
                    and all(recent[i] <= recent[i - 1] + (min_delta * 0.25) for i in range(1, len(recent)))
                )

        if convergence_detected:
            stopping_reason = "validation_and_policy_converged"
            row["stopping_reason"] = stopping_reason
        elif persistent_decline:
            stopping_reason = "persistent_validation_decline"
            row["stopping_reason"] = stopping_reason
        elif validation and epoch >= min_epochs and epochs_without_improvement >= patience:
            stopping_reason = "validation_patience_exhausted"
            row["stopping_reason"] = stopping_reason

        payload = {
            "config": config,
            "metrics": metrics,
            "best_epoch": best_epoch,
            "actual_epochs": epoch,
            "stopping_reason": stopping_reason if row["stopping_reason"] else None,
        }
        metrics_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        print(
            f"Epoch {epoch:04d}/{epochs:04d} | updates={updates} | total_updates={total_updates_used} | "
            f"loss={average_loss:.6f} | policy_reward={average_policy_reward:.6f} | "
            f"oracle_reward={average_oracle_reward:.6f} | efficiency={policy_reward_efficiency:.4f}"
        )

        if validation:
            print(
                f"    validation: optimality={validation['policy_optimality']:.4f} "
                f"efficiency={validation['reward_efficiency']:.4f} "
                f"score={validation_score:.4f} patience={epochs_without_improvement}/{patience}"
            )

        if progress_callback:
            progress_callback(row)

        if row["stopping_reason"]:
            print(
                f"[EARLY STOP] reason={row['stopping_reason']} "
                f"at epoch={epoch}; best_epoch={best_epoch}."
            )
            break

        if total_updates_used >= update_budget:
            stopping_reason = "update_budget"
            print(f"[UPDATE BUDGET] Automatic update budget reached at {total_updates_used:,} updates.")
            break

    if candidate_checkpoint and candidate_checkpoint.exists():
        model.load(str(candidate_checkpoint))

    final_epoch = metrics[-1]["epoch"] if metrics else 0
    result = {
        "config": config,
        "metrics": metrics,
        "best_epoch": best_epoch,
        "best_validation": best_validation,
        "actual_epochs": final_epoch,
        "total_updates_used": total_updates_used,
        "updates_per_epoch": updates_per_epoch,
        "max_total_updates": update_budget,
        "stopping_reason": stopping_reason,
    }
    metrics_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    return model, result
