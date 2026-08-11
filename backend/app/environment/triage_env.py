"""Dataset-backed Gymnasium environment for offline triage training."""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from app.data_pipeline.contract import FEATURE_COLUMNS, observations_for_split
from app.reward.outcomes import ACTION_NAMES, historical_outcome_reward, validate_action_mapping


class AlertTriageEnv(gym.Env[np.ndarray, int]):
    """Sequential environment over existing processed incidents.

    This is an offline, dataset-backed RL environment. Each transition uses a
    real row from the processed CSV, and the next state is the next processed
    row in the split. No synthetic alerts are generated.
    """

    metadata = {"render_modes": []}

    def __init__(self, split: str = "train", max_steps: int = 1_000, start_index: int = 0):
        if split not in {"train", "test"}:
            raise ValueError("split must be 'train' or 'test'")
        if max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        self.split = split
        self.observations, self.labels = observations_for_split(split)  # type: ignore[arg-type]
        if self.observations.shape[1] != len(FEATURE_COLUMNS):
            raise ValueError(f"State dimension mismatch: expected {len(FEATURE_COLUMNS)}, got {self.observations.shape[1]}")
        validate_action_mapping(len(ACTION_NAMES))
        self.max_steps = min(int(max_steps), len(self.observations))
        self.default_start_index = start_index % len(self.observations)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(self.observations.shape[1],), dtype=np.float32)
        self.action_space = spaces.Discrete(len(ACTION_NAMES))
        self._index = self.default_start_index
        self._steps = 0
        self._episode_reward = 0.0
        self._episode_actions: list[int] = []

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        start = self.default_start_index
        if options and "start_index" in options:
            start = int(options["start_index"]) % len(self.observations)
        self._index = start
        self._steps = 0
        self._episode_reward = 0.0
        self._episode_actions = []
        return self.observations[self._index].copy(), {"split": self.split, "index": self._index, "feature_columns": list(FEATURE_COLUMNS)}

    def step(self, action: int):
        if not self.action_space.contains(action):
            raise ValueError(f"Invalid action: {action}")
        grade = int(self.labels[self._index])
        reward = historical_outcome_reward(grade, int(action))
        info = {
            "split": self.split,
            "index": self._index,
            "incident_grade": grade,
            "action_name": ACTION_NAMES[int(action)],
        }
        self._steps += 1
        self._episode_reward += float(reward)
        self._episode_actions.append(int(action))
        self._index += 1
        terminated = self._index >= len(self.observations)
        truncated = self._steps >= self.max_steps and not terminated
        next_index = min(self._index, len(self.observations) - 1)
        next_state = self.observations[next_index].copy()
        return next_state, float(reward), terminated, truncated, info

