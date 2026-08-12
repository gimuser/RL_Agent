"""Authoritative real-data incident-level offline RL pipeline."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

# ----------------------------------------------------------------------
# PROJECT PATHS
# ----------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]

TRAIN_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "train_processed.csv"
)

TEST_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "test_processed.csv"
)

MODEL_PATH = (
    PROJECT_ROOT
    / "models"
    / "real_dqn_agent.pt"
)

TRAIN_METRICS_PATH = (
    PROJECT_ROOT
    / "models"
    / "training_metrics.json"
)

TEST_METRICS_PATH = (
    PROJECT_ROOT
    / "models"
    / "real_test_metrics.json"
)

RL_DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "rl_incident"
)

MODELS_DIR = (
    PROJECT_ROOT
    / "models"
)

RL_DATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

MODELS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

from .triage_env import (
    ACTIONS,
    FEATURES,
    INCIDENT_ID,
    LABELS,
    TARGET,
    incident_split,
    save_split_report,
)

from .trainer import train
from .evaluator import evaluate


PROJECT = Path(
    "/home/oualid/Desktop/RL_AGENT"
)

PROCESSED = (
    PROJECT / "data" / "processed"
)

RL_DATA = (
    PROJECT / "data" / "rl_incident"
)

MODELS = (
    PROJECT / "models"
)


def locate_source_dataset():

    candidates = [
        PROCESSED / "Microsoft_SOC_Dataset.csv",
        PROCESSED / "microsoft_soc_dataset.csv",
        PROCESSED / "soc_dataset.csv",
        PROCESSED / "full_processed.csv",
        PROCESSED / "processed.csv",
        PROCESSED / "all_processed.csv",
    ]

    for p in candidates:
        if p.exists():
            return p

    # If the complete source isn't explicitly named,
    # search CSVs and choose the largest one containing IncidentId.
    csvs = list(
        PROCESSED.glob("*.csv")
    )

    valid = []

    for p in csvs:

        try:
            columns = pd.read_csv(
                p,
                nrows=0,
            ).columns

            if (
                INCIDENT_ID in columns
                and TARGET in columns
            ):
                valid.append(p)

        except Exception:
            continue

    if not valid:
        raise FileNotFoundError(
            "Could not find a complete CSV containing "
            "IncidentId and IncidentGrade in data/processed/"
        )

    valid.sort(
        key=lambda x: x.stat().st_size,
        reverse=True,
    )

    return valid[0]


def build_incident_split():

    source = locate_source_dataset()

    print()
    print("=" * 70)
    print("BUILDING INCIDENT-LEVEL DATA SPLIT")
    print("=" * 70)

    print(
        f"Source dataset : {source}"
    )

    df = pd.read_csv(
        source
    )

    print(
        f"Source rows    : {len(df):,}"
    )

    print(
        f"Source columns : {len(df.columns)}"
    )

    if INCIDENT_ID not in df.columns:
        raise RuntimeError(
            "IncidentId is required for incident-level RL."
        )

    if TARGET not in df.columns:
        raise RuntimeError(
            "IncidentGrade is required."
        )

    train_df, test_df = incident_split(
        df,
        train_ratio=float(
            os.getenv(
                "REAL_RL_TRAIN_RATIO",
                "0.80",
            )
        ),
        seed=int(
            os.getenv(
                "REAL_RL_SEED",
                "42",
            )
        ),
    )

    overlap = (
        set(
            train_df[
                INCIDENT_ID
            ].astype(str)
        )
        &
        set(
            test_df[
                INCIDENT_ID
            ].astype(str)
        )
    )

    if overlap:
        raise RuntimeError(
            f"FATAL: {len(overlap)} incident IDs overlap."
        )

    train_path = (
        RL_DATA /
        "train_incident.csv"
    )

    test_path = (
        RL_DATA /
        "test_incident.csv"
    )

    RL_DATA.mkdir(
        parents=True,
        exist_ok=True,
    )

    train_df.to_csv(
        train_path,
        index=False,
    )

    test_df.to_csv(
        test_path,
        index=False,
    )

    # Explicit incident ID files
    (
        RL_DATA /
        "train_incidents.txt"
    ).write_text(
        "\n".join(
            sorted(
                train_df[
                    INCIDENT_ID
                ].astype(str).unique()
            )
        )
    )

    (
        RL_DATA /
        "test_incidents.txt"
    ).write_text(
        "\n".join(
            sorted(
                test_df[
                    INCIDENT_ID
                ].astype(str).unique()
            )
        )
    )

    save_split_report(
        train_df,
        test_df,
        str(
            RL_DATA /
            "split_report.json"
        ),
    )

    print()
    print("NEW INCIDENT-LEVEL SPLIT")

    print(
        f"TRAIN rows      : {len(train_df):,}"
    )

    print(
        f"TEST rows       : {len(test_df):,}"
    )

    print(
        f"TRAIN incidents : "
        f"{train_df[INCIDENT_ID].astype(str).nunique():,}"
    )

    print(
        f"TEST incidents  : "
        f"{test_df[INCIDENT_ID].astype(str).nunique():,}"
    )

    print(
        f"OVERLAP         : {len(overlap):,}"
    )

    if len(overlap) != 0:
        raise RuntimeError(
            "FATAL: train/test incident overlap."
        )

    print()
    print(
        "[OK] ZERO INCIDENT OVERLAP"
    )

    print()
    print(
        f"Train file: {train_path}"
    )

    print(
        f"Test file : {test_path}"
    )

    return (
        str(train_path),
        str(test_path),
    )


def main():

    print()
    print("=" * 70)
    print("COMPLETE INCIDENT-LEVEL OFFLINE RL PIPELINE")
    print("=" * 70)

    train_csv, test_csv = (
        build_incident_split()
    )

    epochs = int(
        os.getenv(
            "REAL_RL_EPOCHS",
            "10",
        )
    )

    batch_size = int(
        os.getenv(
            "REAL_RL_BATCH_SIZE",
            "512",
        )
    )

    gamma = float(
        os.getenv(
            "REAL_RL_GAMMA",
            "0.95",
        )
    )

    learning_rate = float(
        os.getenv(
            "REAL_RL_LR",
            "0.001",
        )
    )

    train(
        train_csv=train_csv,
        epochs=epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
        gamma=gamma,
    )

    evaluate(
        test_csv=test_csv,
        model_path=str(
            MODELS /
            "real_dqn_agent.pt"
        ),
    )

    print()
    print("=" * 70)
    print("FULL INCIDENT-LEVEL RL PIPELINE FINISHED")
    print("=" * 70)

    print()
    print(
        "TRAIN:"
    )
    print(
        f"  {train_csv}"
    )

    print()
    print(
        "TEST:"
    )
    print(
        f"  {test_csv}"
    )

    print()
    print(
        "MODEL:"
    )
    print(
        "  models/real_dqn_agent.pt"
    )

    print()
    print(
        "TRAIN METRICS:"
    )
    print(
        "  models/training_metrics.json"
    )

    print()
    print(
        "TEST METRICS:"
    )
    print(
        "  models/real_test_metrics.json"
    )

    print()
    print(
        "TEST PREDICTIONS:"
    )
    print(
        "  models/test_predictions.csv"
    )

    print()
    print(
        "SPLIT REPORT:"
    )
    print(
        "  data/rl_incident/split_report.json"
    )

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()

# ==========================================================================
# APPLICATION / ENVIRONMENT COMPATIBILITY API
# ==========================================================================
#
# These helpers preserve the public API expected by the older application
# environment while the accepted real-data RL pipeline remains authoritative.
# ==========================================================================

import numpy as _compat_np
import pandas as _compat_pd


def load_dataset(path):
    """
    Load real processed/incident data and produce the accepted 13-feature
    RL state.

    Returns:
        dataframe, states, labels
    """

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(path)

    df = _compat_pd.read_csv(path)

    missing = [
        c for c in list(FEATURES) + [TARGET]
        if c not in df.columns
    ]

    if missing:
        raise RuntimeError(
            f"{path} missing required columns: {missing}"
        )

    states = (
        df[list(FEATURES)]
        .apply(_compat_pd.to_numeric, errors="raise")
        .astype(_compat_np.float32)
        .to_numpy()
    )

    labels = (
        _compat_pd.to_numeric(
            df[TARGET],
            errors="raise",
        )
        .astype(_compat_np.int64)
        .to_numpy()
    )

    if not _compat_np.isfinite(states).all():
        raise RuntimeError(
            f"{path} contains non-finite state values"
        )

    return df, states, labels


def _compat_reward_matrix(labels):
    from .triage_env import REWARD_TABLE

    rewards = _compat_np.zeros(
        (len(labels), 3),
        dtype=_compat_np.float32,
    )

    for i, label in enumerate(labels):
        row = REWARD_TABLE.get(
            int(label),
            REWARD_TABLE[3],
        )

        rewards[i, 0] = float(row[0])
        rewards[i, 1] = float(row[1])
        rewards[i, 2] = float(row[2])

    return rewards


def reward_vector(labels):
    """
    Canonical counterfactual rewards:
        0 = allow
        1 = block
        2 = human_review
    """
    return _compat_reward_matrix(labels)


def reward_matrix(labels):
    """
    Backward-compatible alias of reward_vector().
    """
    return _compat_reward_matrix(labels)


def apply_normalization(states, normalization=None):
    """
    Apply the accepted pipeline normalization to real state vectors.

    Supports:
      - normalization=None
      - {"mean": [...], "std": [...]}
      - (mean, std)

    Returns float32 normalized states.
    """

    x = _compat_np.asarray(
        states,
        dtype=_compat_np.float32,
    )

    if normalization is None:
        return x

    if isinstance(normalization, dict):
        mean = normalization.get("mean")
        std = normalization.get("std")
    else:
        mean, std = normalization

    if mean is None or std is None:
        return x

    mean = _compat_np.asarray(
        mean,
        dtype=_compat_np.float32,
    )

    std = _compat_np.asarray(
        std,
        dtype=_compat_np.float32,
    )

    std = _compat_np.where(
        _compat_np.abs(std) < 1e-8,
        1.0,
        std,
    )

    if x.shape[-1] != len(mean):
        raise ValueError(
            f"Normalization dimension mismatch: "
            f"state={x.shape[-1]}, mean={len(mean)}"
        )

    return ((x - mean) / std).astype(
        _compat_np.float32
    )


def normalize_observations(states):
    """
    Compute train-data normalization and return:
        normalized_states, metadata
    """

    x = _compat_np.asarray(
        states,
        dtype=_compat_np.float32,
    )

    mean = x.mean(axis=0)
    std = x.std(axis=0)

    std = _compat_np.where(
        std < 1e-8,
        1.0,
        std,
    )

    normalized = (
        (x - mean) / std
    ).astype(_compat_np.float32)

    metadata = {
        "mean": mean.astype(float).tolist(),
        "std": std.astype(float).tolist(),
    }

    return normalized, metadata


# ==========================================================================
# BACKWARD-COMPATIBILITY fit_normalization API
# ==========================================================================

def fit_normalization(states):
    """
    Fit normalization parameters from real training states.

    Returns a dictionary compatible with apply_normalization():

        {
            "mean": [...],
            "std": [...]
        }

    This does NOT use labels, IncidentId, or test data.
    """

    x = _compat_np.asarray(
        states,
        dtype=_compat_np.float32,
    )

    if x.ndim != 2:
        raise ValueError(
            f"Expected 2D state matrix, got shape={x.shape}"
        )

    mean = x.mean(axis=0)
    std = x.std(axis=0)

    std = _compat_np.where(
        std < 1e-8,
        1.0,
        std,
    )

    return {
        "mean": mean.astype(float).tolist(),
        "std": std.astype(float).tolist(),
    }


