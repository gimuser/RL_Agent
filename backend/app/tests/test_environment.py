"""Tests for the dataset-backed RL environment."""

import numpy as np

from app.environment.triage_env import AlertTriageEnv
from app.data_pipeline.contract import FEATURE_COLUMNS, observations_for_split


def test_environment_uses_processed_rows_and_real_dimensions():
    env = AlertTriageEnv(split="train", max_steps=5)
    obs, _ = env.reset(options={"start_index": 0})
    assert obs.shape == (len(FEATURE_COLUMNS),)
    assert env.observation_space.shape == (len(FEATURE_COLUMNS),)
    assert env.action_space.n == 3
    assert env.max_steps == 5


def test_environment_step_uses_real_row_indices():
    env = AlertTriageEnv(split="train", max_steps=3)
    _, info = env.reset(options={"start_index": 0})
    next_state, reward, terminated, truncated, info = env.step(0)
    assert info["index"] == 0
    assert next_state.shape == (len(FEATURE_COLUMNS),)
    assert isinstance(reward, (int, float))
    assert terminated is False
    assert truncated is False
    assert info["action_name"] in {"close_recommendation", "escalate_for_human_review", "request_human_validation"}


def test_observations_match_processed_dataset_shape():
    obs, labels = observations_for_split("train")
    assert obs.shape[0] > 0
    assert obs.shape[1] == len(FEATURE_COLUMNS)
    assert labels.shape[0] == obs.shape[0]
    assert np.isfinite(obs).all()
