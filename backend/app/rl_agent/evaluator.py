from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from .offline_algorithms import build_model
from .triage_env import ACTIONS, FEATURES, INCIDENT_ID, TARGET, LABELS, REWARD_TABLE, sort_incidents


def evaluate(test_csv: str, model_path: str = "models/real_dqn_agent.pt"):
    df = pd.read_csv(test_csv, low_memory=False); df, timestamp_col = sort_incidents(df)
    checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
    algorithm = str(checkpoint.get("algorithm", "double_dqn"))
    model = build_model(algorithm, input_dim=len(FEATURES), n_actions=len(ACTIONS), learning_rate=1e-3, gamma=float(checkpoint.get("gamma", 0.95)), hidden_dim=128)
    model.load(model_path)

    total_reward = optimal_reward = 0.0
    action_counts = {name: 0 for name in ACTIONS.values()}
    class_stats = {int(label): {"rows": 0, "reward": 0.0, "optimal_reward": 0.0} for label in LABELS}
    predictions = []
    start = time.perf_counter()
    for incident_id, group in df.groupby(INCIDENT_ID, sort=False):
        rows = group.reset_index(drop=True); states = rows[FEATURES].astype(np.float32).values; labels = rows[TARGET].astype(int).values
        q_values = model.q_values(states); actions = np.asarray(model.act(states), dtype=np.int64)
        for i in range(len(rows)):
            label = int(labels[i]); action = int(actions[i]); rewards = REWARD_TABLE.get(label, REWARD_TABLE[3]); reward = float(rewards[action]); optimal = float(max(rewards.values()))
            total_reward += reward; optimal_reward += optimal; action_name = ACTIONS[action]; action_counts[action_name] += 1
            class_stats[label]["rows"] += 1; class_stats[label]["reward"] += reward; class_stats[label]["optimal_reward"] += optimal
            predictions.append({"IncidentId": str(incident_id), "step": i, "label": label, "label_name": LABELS.get(label, "Unknown"), "action": action, "action_name": action_name, "algorithm": algorithm, "reward": reward, "optimal_reward": optimal, "q_allow": float(q_values[i][0]), "q_block": float(q_values[i][1]), "q_human_review": float(q_values[i][2]), "done": i == len(rows) - 1})
    elapsed = time.perf_counter() - start; n = len(predictions); avg_reward = total_reward / n if n else 0.0; regret = optimal_reward - total_reward; efficiency = total_reward / optimal_reward if optimal_reward else 0.0; optimality = sum(1 for p in predictions if p["reward"] == p["optimal_reward"]) / n if n else 0.0
    per_class = {}
    for label, stats in class_stats.items():
        n_class = stats["rows"]
        per_class[LABELS.get(label, "Unknown")] = {"rows": n_class, "average_reward": stats["reward"] / n_class if n_class else 0.0, "optimality": stats["reward"] / stats["optimal_reward"] if stats["optimal_reward"] else 0.0}
    root = Path(__file__).resolve().parents[3]
    predictions_path = root / "models" / "test_predictions.csv"
    pd.DataFrame(predictions).to_csv(predictions_path, index=False)
    return {"algorithm": algorithm, "test_rows": n, "rows": n, "test_incidents": int(df[INCIDENT_ID].astype(str).nunique()), "average_reward": avg_reward, "oracle_average_reward": optimal_reward / n if n else 0.0, "reward_efficiency": efficiency, "policy_optimality": optimality, "reward_regret": regret, "throughput_rows_per_second": n / elapsed if elapsed else 0.0, "action_distribution": action_counts, "per_class": per_class, "unseen_incidents": True, "synthetic_data": False, "predictions_path": str(predictions_path), "timestamp_column": timestamp_col}
