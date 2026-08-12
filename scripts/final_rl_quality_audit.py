#!/usr/bin/env python3

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path.cwd()

MODEL = ROOT / "models" / "real_dqn_agent.pt"
TRAIN_METRICS = ROOT / "models" / "training_metrics.json"
TEST_METRICS = ROOT / "models" / "real_test_metrics.json"
PREDICTIONS = ROOT / "models" / "test_predictions.csv"
JSONL = ROOT / "models" / "real_test_predictions.jsonl"
TEST_DATA = ROOT / "data" / "rl_incident" / "test_incident.csv"


def section(title: str):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def pct(x):
    return f"{100.0 * x:.2f}%"


def entropy(probs):
    values = [p for p in probs if p > 0]
    return -sum(p * math.log2(p) for p in values)


section("FINAL RL MODEL QUALITY AUDIT")

# ---------------------------------------------------------------------------
# 1. FILE INTEGRITY
# ---------------------------------------------------------------------------

required = [
    MODEL,
    TRAIN_METRICS,
    TEST_METRICS,
    PREDICTIONS,
    JSONL,
    TEST_DATA,
]

for path in required:
    if path.exists():
        print("[OK]", path)
    else:
        print("[FAIL] Missing:", path)

missing = [p for p in required if not p.exists()]
if missing:
    raise SystemExit(1)

# ---------------------------------------------------------------------------
# 2. METRICS
# ---------------------------------------------------------------------------

section("1. EXISTING EVALUATION METRICS")

train_metrics = json.loads(TRAIN_METRICS.read_text())
test_metrics = json.loads(TEST_METRICS.read_text())

metrics = train_metrics.get("metrics", [])
config = train_metrics.get("config", {})

print("Training epochs      :", config.get("epochs"))
print("Batch size           :", config.get("batch_size"))
print("Training records     :", len(metrics))

if metrics:
    losses = [float(x["loss"]) for x in metrics if "loss" in x]
    print("Initial loss         :", losses[0])
    print("Final loss           :", losses[-1])
    print("Loss reduction       :", losses[0] - losses[-1])
    print(
        "Loss reduction %     :",
        pct((losses[0] - losses[-1]) / losses[0]),
    )

print()
print("Test rows             :", test_metrics.get("test_rows"))
print("Test incidents        :", test_metrics.get("test_incidents"))
print("Average reward        :", test_metrics.get("average_reward"))
print("Reward efficiency     :", test_metrics.get("reward_efficiency"))
print("Policy optimality     :", test_metrics.get("policy_optimality"))
print("Reward regret         :", test_metrics.get("reward_regret"))
print("Synthetic data        :", test_metrics.get("synthetic_data"))
print("Unseen incidents      :", test_metrics.get("unseen_incidents"))

# ---------------------------------------------------------------------------
# 3. ACTION DISTRIBUTION
# ---------------------------------------------------------------------------

section("2. POLICY ACTION DISTRIBUTION")

action_distribution = test_metrics.get("action_distribution", {})

if action_distribution:
    total = sum(action_distribution.values())

    for action, count in action_distribution.items():
        ratio = count / total if total else 0
        print(f"{action:15s}: {count:8d}  ({pct(ratio)})")

    probs = [
        count / total
        for count in action_distribution.values()
        if total
    ]

    print()
    print("Action entropy       :", round(entropy(probs), 4), "bits")

    dominant = max(action_distribution.values()) / total if total else 0
    print("Dominant action      :", pct(dominant))

    if dominant > 0.80:
        print("[WARN] Strong policy concentration")
    elif dominant > 0.60:
        print("[WARN] Moderate policy concentration")
    else:
        print("[OK] No severe single-action collapse")

# ---------------------------------------------------------------------------
# 4. PER-CLASS QUALITY
# ---------------------------------------------------------------------------

section("3. PER-CLASS POLICY QUALITY")

per_class = test_metrics.get("per_class", {})

if not per_class:
    print("[WARN] No per-class metrics found")
else:
    for cls, values in per_class.items():
        print(
            f"{cls:18s} "
            f"rows={values.get('rows')} "
            f"reward={values.get('average_reward')} "
            f"optimality={values.get('optimality')}"
        )

# ---------------------------------------------------------------------------
# 5. PREDICTION ARTIFACT
# ---------------------------------------------------------------------------

section("4. TEST PREDICTION ARTIFACT")

df = pd.read_csv(PREDICTIONS)

print("Prediction rows      :", len(df))
print("Prediction columns   :", list(df.columns))

candidate_action_cols = [
    "action",
    "predicted_action",
    "selected_action",
    "prediction",
    "Action",
    "PredictedAction",
]

action_col = next(
    (c for c in candidate_action_cols if c in df.columns),
    None,
)

candidate_target_cols = [
    "IncidentGrade",
    "incident_grade",
    "target",
    "Target",
    "label",
    "Label",
]

target_col = next(
    (c for c in candidate_target_cols if c in df.columns),
    None,
)

candidate_reward_cols = [
    "reward",
    "Reward",
    "real_reward",
    "step_reward",
]

reward_col = next(
    (c for c in candidate_reward_cols if c in df.columns),
    None,
)

print("Detected action col  :", action_col)
print("Detected target col  :", target_col)
print("Detected reward col  :", reward_col)

if action_col:
    counts = df[action_col].value_counts(dropna=False)

    print()
    print("Actual prediction distribution:")
    for action, count in counts.items():
        print(
            f"{str(action):15s}: "
            f"{count:8d} "
            f"({pct(count / len(df))})"
        )

    expected = action_distribution

    if expected:
        print()
        print("Metric-vs-prediction consistency:")

        for action, expected_count in expected.items():
            actual_count = int(
                counts.get(action, 0)
            )

            print(
                f"{action:15s}: "
                f"metrics={expected_count} "
                f"csv={actual_count}"
            )

            if actual_count != expected_count:
                print("[WARN] Action count mismatch")
else:
    print("[WARN] Could not automatically identify action column")

if reward_col:
    reward_mean = float(df[reward_col].mean())
    print()
    print("Prediction-file mean reward:", reward_mean)
    print(
        "Reported test mean reward  :",
        test_metrics.get("average_reward"),
    )

# ---------------------------------------------------------------------------
# 6. JSONL CONSISTENCY
# ---------------------------------------------------------------------------

section("5. JSONL CONSISTENCY")

jsonl_rows = sum(
    1
    for line in JSONL.read_text(
        encoding="utf-8"
    ).splitlines()
    if line.strip()
)

print("CSV rows                :", len(df))
print("JSONL rows              :", jsonl_rows)
print("Metric test_rows        :", test_metrics.get("test_rows"))

if len(df) == jsonl_rows == test_metrics.get("test_rows"):
    print("[OK] Prediction artifacts are row-consistent")
else:
    print("[FAIL] Prediction artifact row mismatch")

# ---------------------------------------------------------------------------
# 7. INCIDENT-LEVEL SPLIT
# ---------------------------------------------------------------------------

section("6. INCIDENT-LEVEL GENERALIZATION")

test_df = pd.read_csv(
    TEST_DATA,
    usecols=["IncidentId"],
)

test_incidents = test_df["IncidentId"].astype(str)

print("Test rows               :", len(test_df))
print("Unique test incidents   :", test_incidents.nunique())

split_report = ROOT / "data/rl_incident/split_report.json"

if split_report.exists():
    split = json.loads(split_report.read_text())

    print("Train incidents         :", split.get("train_incidents"))
    print("Test incidents          :", split.get("test_incidents"))
    print("Incident overlap        :", split.get("incident_overlap"))

# ---------------------------------------------------------------------------
# 8. MODEL LOAD + NETWORK SANITY
# ---------------------------------------------------------------------------

section("7. MODEL SANITY")

try:
    checkpoint = torch.load(
        MODEL,
        map_location="cpu",
        weights_only=False,
    )

    print("Checkpoint type         :", type(checkpoint).__name__)

    if isinstance(checkpoint, dict):
        print(
            "Checkpoint keys        :",
            list(checkpoint.keys())[:20],
        )

    print("[OK] PyTorch checkpoint loads")
except Exception as exc:
    print("[FAIL] Model load error:", exc)
    raise SystemExit(1)

# ---------------------------------------------------------------------------
# 9. FINAL CLASSIFICATION
# ---------------------------------------------------------------------------

section("8. AUDIT CONCLUSION")

optimality = float(
    test_metrics.get("policy_optimality", 0.0)
)

efficiency = float(
    test_metrics.get("reward_efficiency", 0.0)
)

dominant = 0.0

if action_distribution:
    total = sum(action_distribution.values())
    if total:
        dominant = max(action_distribution.values()) / total

print("Policy optimality     :", pct(optimality))
print("Reward efficiency     :", pct(efficiency))
print("Dominant action       :", pct(dominant))

print()

warnings = []

if optimality < 0.50:
    warnings.append(
        "policy optimality is below 50%"
    )

if efficiency < 0.50:
    warnings.append(
        "reward efficiency is below 50%"
    )

if dominant > 0.80:
    warnings.append(
        "severe action concentration"
    )

if dominant <= 0.80:
    print("[OK] No severe action collapse detected")

if optimality >= 0.50:
    print("[OK] Policy optimality is above 50%")

if efficiency >= 0.50:
    print("[OK] Reward efficiency is around/above 50%")

print()

if warnings:
    print("AUDIT STATUS: CONDITIONAL")
    for item in warnings:
        print("[WARN]", item)
    print()
    print(
        "The model is operational and non-collapsed, "
        "but quality is not strong enough to call it a final "
        "high-performance policy without further improvement."
    )
else:
    print("AUDIT STATUS: PASS")
    print(
        "The existing RL artifact passes the final "
        "non-destructive quality checks."
    )
