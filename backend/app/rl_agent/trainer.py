from __future__ import annotations

import gc
import json
import math
import os
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd
import torch

from .offline_algorithms import algorithm_metadata, build_model, train_step
from .triage_env import ACTIONS, FEATURES, INCIDENT_ID, LABELS, REWARD_TABLE, TARGET, sort_incidents


class TrainingStopped(Exception):
    """Raised when a managed training process receives a stop request."""


def prepare_transitions(df: pd.DataFrame):
    df, timestamp_col = sort_incidents(df)
    states, next_states, labels, dones = [], [], [], []
    incident_ids, steps = [], []
    for incident_id, group in df.groupby(INCIDENT_ID, sort=False):
        rows = group.reset_index(drop=True)
        x = rows[FEATURES].astype(np.float32).to_numpy(copy=True)
        y = rows[TARGET].astype(int).to_numpy(copy=True)
        for i in range(len(rows)):
            states.append(x[i])
            next_states.append(x[i + 1] if i + 1 < len(rows) else x[i])
            labels.append(y[i])
            dones.append(i == len(rows) - 1)
            incident_ids.append(str(incident_id)); steps.append(i)
    return np.asarray(states, dtype=np.float32), np.asarray(next_states, dtype=np.float32), np.asarray(labels, dtype=np.int64), np.asarray(dones, dtype=np.float32), incident_ids, np.asarray(steps, dtype=np.int64), timestamp_col


def _counterfactual_rewards(labels: np.ndarray) -> np.ndarray:
    matrix = np.zeros((len(labels), len(ACTIONS)), dtype=np.float32)
    for i, label in enumerate(labels):
        row = REWARD_TABLE.get(int(label), REWARD_TABLE[3])
        for action in ACTIONS:
            matrix[i, action] = float(row[action])
    return matrix


def evaluate_policy(model, csv_path: str) -> dict:
    df = pd.read_csv(csv_path, low_memory=False)
    df, _ = sort_incidents(df)
    total_reward = optimal_reward = 0.0
    optimal_actions = rows = 0
    action_counts = {name: 0 for name in ACTIONS.values()}
    class_stats: dict[int, dict[str, float]] = {}
    start = time.perf_counter()
    for _, group in df.groupby(INCIDENT_ID, sort=False):
        batch = group.reset_index(drop=True)
        states = batch[FEATURES].astype(np.float32).to_numpy(copy=True)
        labels = batch[TARGET].astype(int).to_numpy(copy=True)
        actions = np.asarray(model.act(states), dtype=np.int64)
        for label, action in zip(labels, actions):
            label = int(label); action = int(action)
            rewards = REWARD_TABLE.get(label, REWARD_TABLE[3])
            reward = float(rewards[action]); best = float(max(rewards.values()))
            total_reward += reward; optimal_reward += best; optimal_actions += int(reward == best); rows += 1
            action_counts[ACTIONS[action]] += 1
            stats = class_stats.setdefault(label, {"rows": 0.0, "reward": 0.0, "optimal": 0.0})
            stats["rows"] += 1; stats["reward"] += reward; stats["optimal"] += best
    elapsed = time.perf_counter() - start
    per_class = {}
    for label, stats in class_stats.items():
        n = int(stats["rows"])
        per_class[LABELS.get(label, "Unknown")] = {"rows": n, "average_reward": stats["reward"] / n if n else 0.0, "optimality": stats["reward"] / stats["optimal"] if stats["optimal"] else 0.0}
    return {"rows": rows, "incidents": int(df[INCIDENT_ID].astype(str).nunique()), "total_reward": total_reward, "average_reward": total_reward / rows if rows else 0.0, "oracle_average_reward": optimal_reward / rows if rows else 0.0, "reward_efficiency": total_reward / optimal_reward if optimal_reward else 0.0, "policy_optimality": optimal_actions / rows if rows else 0.0, "action_distribution": action_counts, "evaluation_time_seconds": elapsed, "per_class": per_class}


def _checkpoint(model, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); model.save(str(path))


def _finite(value: float) -> float:
    try:
        value = float(value); return value if math.isfinite(value) else 0.0
    except Exception:
        return 0.0


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
    algorithm: str = "double_dqn",
    hidden_dim: int = 128,
):
    np.random.seed(seed); torch.manual_seed(seed)
    threads = max(1, min(int(os.getenv("RL_TORCH_THREADS", "2")), os.cpu_count() or 2))
    try: torch.set_num_threads(threads)
    except RuntimeError: pass

    algorithm_info = algorithm_metadata(algorithm)
    df = pd.read_csv(train_csv, low_memory=False)
    states, next_states, labels, dones, _, _, timestamp_col = prepare_transitions(df)
    n_rows = len(states)
    updates_per_epoch = math.ceil(n_rows / batch_size) if n_rows else 0
    update_budget = int(max_total_updates) if max_total_updates else max(1, updates_per_epoch * max(1, epochs))
    model = build_model(algorithm, input_dim=len(FEATURES), n_actions=len(ACTIONS), learning_rate=learning_rate, gamma=gamma, hidden_dim=hidden_dim)

    metrics_path = Path(__file__).resolve().parents[3] / "models" / "training_metrics.json"
    best_path = Path(checkpoint_path) if checkpoint_path else metrics_path.with_name("best_candidate.pt")
    metrics: list[dict] = []
    best_score = -float("inf"); best_epoch = 0; best_validation = None
    epochs_without_improvement = 0; total_updates_used = 0; stopping_reason = "max_epochs_reached"

    config = {
        **algorithm_info, "model_name": algorithm_info["display_name"], "algorithm": algorithm_info["algorithm"],
        "epochs": epochs, "max_epochs": epochs, "min_epochs": min_epochs, "patience": patience, "min_delta": min_delta,
        "stability_window": stability_window, "stability_tolerance": stability_tolerance, "batch_size": batch_size,
        "learning_rate": learning_rate, "gamma": gamma, "hidden_dim": hidden_dim, "features": FEATURES, "actions": ACTIONS,
        "incident_id": INCIDENT_ID, "target": TARGET, "synthetic_data": False, "real_data": True, "incident_level_episodes": True,
        "early_stopping": validation_csv is not None, "timestamp_column": timestamp_col, "updates_per_epoch": updates_per_epoch,
        "max_total_updates": update_budget, "threads": threads,
    }
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps({"config": config, "metrics": []}, indent=2), encoding="utf-8")

    for epoch in range(1, epochs + 1):
        if stop_event is not None and getattr(stop_event, "is_set", lambda: False)():
            raise TrainingStopped("Training stopped by user.")
        if total_updates_used >= update_budget:
            stopping_reason = "update_budget_reached"; break
        epoch_start = time.perf_counter(); indices = np.random.permutation(n_rows)
        total_loss = 0.0; updates = 0; policy_reward_sum = 0.0; oracle_reward_sum = 0.0
        action_counts = {name: 0 for name in ACTIONS.values()}

        for start_idx in range(0, n_rows, batch_size):
            if stop_event is not None and getattr(stop_event, "is_set", lambda: False)():
                raise TrainingStopped("Training stopped by user.")
            if total_updates_used >= update_budget: break
            batch_idx = indices[start_idx:start_idx + batch_size]
            batch_states = states[batch_idx]; batch_next = next_states[batch_idx]; batch_labels = labels[batch_idx]; batch_dones = dones[batch_idx]
            reward_matrix = _counterfactual_rewards(batch_labels)
            total_loss += _finite(train_step(model, algorithm, batch_states, reward_matrix, batch_next, batch_dones))
            updates += 1; total_updates_used += 1
            policy_actions = np.asarray(model.act(batch_states), dtype=np.int64)
            policy_reward_sum += float(reward_matrix[np.arange(len(policy_actions)), policy_actions].sum())
            oracle_reward_sum += float(reward_matrix.max(axis=1).sum())
            for action in policy_actions: action_counts[ACTIONS[int(action)]] += 1

        if target_update > 0 and epoch % target_update == 0: model.update_target()
        elapsed = time.perf_counter() - epoch_start
        loss_value = total_loss / max(updates, 1); policy_reward = policy_reward_sum / n_rows if n_rows else 0.0
        oracle_reward = oracle_reward_sum / n_rows if n_rows else 0.0; efficiency = policy_reward / oracle_reward if oracle_reward else 0.0
        validation = evaluate_policy(model, validation_csv) if validation_csv else None
        validation_score = None; improved = False
        if validation:
            validation_score = 0.70 * validation["policy_optimality"] + 0.30 * validation["reward_efficiency"]
            improved = validation_score > best_score + min_delta
            if improved:
                best_score = validation_score; best_epoch = epoch; best_validation = validation; epochs_without_improvement = 0; _checkpoint(model, best_path)
            else: epochs_without_improvement += 1

        row = {
            "epoch": epoch, "rows": n_rows, "incidents": int(df[INCIDENT_ID].astype(str).nunique()), "updates": updates,
            "total_updates": total_updates_used, "updates_per_epoch": updates_per_epoch, "loss": loss_value,
            "average_reward": policy_reward, "policy_reward": policy_reward, "oracle_average_reward": oracle_reward,
            "reward_efficiency": efficiency, "action_counts": action_counts, "action_distribution": action_counts,
            "time_seconds": elapsed, "validation": validation, "validation_score": validation_score, "best_epoch": best_epoch,
            "patience_used": epochs_without_improvement, "improved": improved, "algorithm": algorithm_info["algorithm"],
            "behavior_action_mode": algorithm_info["behavior_action_mode"], "stopping_reason": None,
        }
        metrics.append(row)

        convergence = False; persistent_decline = False
        if validation and epoch >= min_epochs:
            recent = [r.get("validation_score") for r in metrics[-stability_window:] if isinstance(r.get("validation_score"), (int, float))]
            recent_rewards = [r.get("policy_reward") for r in metrics[-stability_window:] if isinstance(r.get("policy_reward"), (int, float))]
            if len(recent) == stability_window and len(recent_rewards) == stability_window:
                score_flat = max(recent) - min(recent) <= stability_tolerance
                reward_ref = max(abs(float(np.mean(recent_rewards))), 1.0)
                reward_flat = max(recent_rewards) - min(recent_rewards) <= max(stability_tolerance, reward_ref * 0.0025)
                no_new_best = all(float(v) <= best_score + min_delta for v in recent)
                convergence = score_flat and reward_flat and no_new_best
                persistent_decline = recent[-1] < best_score - min_delta and all(recent[i] <= recent[i - 1] + min_delta * 0.25 for i in range(1, len(recent)))
            if persistent_decline: stopping_reason = "persistent_validation_decline"
            elif convergence: stopping_reason = "validation_and_policy_converged"
            elif epochs_without_improvement >= patience: stopping_reason = "validation_patience_exhausted"
            if stopping_reason != "max_epochs_reached": row["stopping_reason"] = stopping_reason

        metrics_path.write_text(json.dumps({"config": config, "metrics": metrics, "best_epoch": best_epoch, "actual_epochs": epoch, "best_validation": best_validation, "total_updates_used": total_updates_used, "updates_per_epoch": updates_per_epoch, "max_total_updates": update_budget, "stopping_reason": row["stopping_reason"]}, indent=2, default=str), encoding="utf-8")
        if progress_callback: progress_callback(row)
        if row["stopping_reason"]: break
        if total_updates_used >= update_budget: stopping_reason = "update_budget_reached"; break
        gc.collect()

    if best_path.exists() and best_epoch:
        try: model.load(str(best_path))
        except Exception: pass
    final_epoch = metrics[-1]["epoch"] if metrics else 0
    result = {"config": config, "metrics": metrics, "best_epoch": best_epoch, "best_validation": best_validation, "actual_epochs": final_epoch, "total_updates_used": total_updates_used, "updates_per_epoch": updates_per_epoch, "max_total_updates": update_budget, "stopping_reason": stopping_reason}
    metrics_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return model, result
