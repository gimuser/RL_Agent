"""Dataset-backed DQN trainer for the processed CSV contract."""

from __future__ import annotations

from collections.abc import Callable
from threading import Event
from time import perf_counter

import torch

from app.config.settings import settings
from app.data_pipeline.contract import FEATURE_COLUMNS
from app.environment.triage_env import AlertTriageEnv
from app.reward.outcomes import ACTION_NAMES, expected_action, validate_action_mapping
from app.rl_agent.dqn import DQNAgent
from app.rl_agent.utils import set_seed


class Trainer:
    """Reinforcement Learning Trainer."""

    def __init__(self, algorithm="dqn", state_dim: int | None = None, action_dim: int | None = None, agent_config: dict | None = None):
        self.algorithm = algorithm.lower()
        if self.algorithm != "dqn":
            raise ValueError("Only the validated DQN training path is currently supported")
        self.agent_config = agent_config or {}
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.agent: DQNAgent | None = None

    def _resolve_dimensions(self, env: AlertTriageEnv) -> tuple[int, int]:
        state_dim = int(env.observation_space.shape[0])
        action_dim = int(env.action_space.n)
        if self.state_dim is None:
            self.state_dim = state_dim
        if self.action_dim is None:
            self.action_dim = action_dim
        if self.state_dim != state_dim:
            raise ValueError(f"Configured state_dim {self.state_dim} does not match environment state_dim {state_dim}")
        if self.action_dim != action_dim:
            raise ValueError(f"Configured action_dim {self.action_dim} does not match environment action_dim {action_dim}")
        validate_action_mapping(action_dim)
        return self.state_dim, self.action_dim

    def train(
        self,
        *,
        training_passes: int | None,
        max_steps: int,
        seed: int,
        stop_event: Event | None = None,
        on_episode: Callable[[dict], None] | None = None,
        on_progress: Callable[[dict], None] | None = None,
    ) -> dict:
        """Train by traversing the real training split one pass at a time."""
        if max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        set_seed(seed)
        env = AlertTriageEnv(split="train", max_steps=10**9)
        state_dim, action_dim = self._resolve_dimensions(env)
        total_rows = int(len(env.observations))
        effective_max_steps = min(total_rows, int(max_steps))
        if training_passes is None:
            training_passes = int(getattr(settings, "training_passes", 1))
        training_passes = int(training_passes)
        if training_passes < 1:
            raise ValueError("training_passes must be >= 1")
        self.agent = DQNAgent(state_dim=state_dim, action_dim=action_dim, **self.agent_config)
        self.on_progress = on_progress
        episode_records: list[dict] = []
        stopped = False
        environment_steps = 0
        gradient_updates = 0
        start_time = perf_counter()
        progress_interval = max(1, int(getattr(settings, "training_progress_interval", 1000)))
        for pass_idx in range(training_passes):
            if stop_event and stop_event.is_set():
                stopped = True
                break
            env_pass = AlertTriageEnv(split="train", max_steps=effective_max_steps)
            state, _ = env_pass.reset(seed=seed, options={"start_index": 0})
            total_reward = 0.0
            losses: list[float] = []
            steps = 0
            while True:
                if stop_event and stop_event.is_set():
                    stopped = True
                    break
                action = self.agent.act(state)
                next_state, reward, terminated, truncated, _ = env_pass.step(action)
                self.agent.remember(state, action, reward, next_state, terminated or truncated)
                loss = self.agent.update()
                if loss is not None:
                    losses.append(float(loss))
                    gradient_updates += 1
                total_reward += float(reward)
                steps += 1
                environment_steps += 1
                if (environment_steps % progress_interval) == 0 and (on_progress or getattr(self, "on_progress", None)):
                    prog = {
                        "pass": pass_idx + 1,
                        "environment_steps": int(environment_steps),
                        "dataset_rows": int(total_rows),
                        "gradient_updates": int(gradient_updates),
                        "last_loss": float(losses[-1]) if losses else None,
                        "last_reward": float(total_reward / steps) if steps else None,
                        "replay_size": int(len(self.agent.memory)),
                        "replay_capacity": int(self.agent.memory.buffer.maxlen),
                        "epsilon": float(self.agent.policy.epsilon),
                    }
                    try:
                        if callable(getattr(self, "on_progress", None)):
                            self.on_progress(prog)
                    except Exception:
                        pass
                state = next_state
                if terminated or truncated:
                    break
            record = {
                "pass": pass_idx + 1,
                "steps": steps,
                "total_reward": total_reward,
                "average_reward": total_reward / steps if steps else None,
                "loss": sum(losses) / len(losses) if losses else None,
                "epsilon": float(self.agent.policy.epsilon),
                "replay_buffer_size": len(self.agent.memory),
                "replay_capacity": int(self.agent.memory.buffer.maxlen),
            }
            episode_records.append(record)
            if on_episode:
                on_episode(record)
            if stopped:
                break
        elapsed = perf_counter() - start_time
        return {
            "training_passes": int(training_passes),
            "episodes": len(episode_records),
            "stopped": stopped,
            "passes": episode_records,
            "state_dim": int(state_dim),
            "action_dim": int(action_dim),
            "feature_columns": list(FEATURE_COLUMNS),
            "dataset_rows": int(total_rows),
            "environment_steps": int(environment_steps),
            "gradient_updates": int(gradient_updates),
            "elapsed_seconds": float(elapsed),
            "action_names": ACTION_NAMES,
        }

    def evaluate(self, max_steps: int | None = None) -> dict:
        if max_steps is None:
            env = AlertTriageEnv(split="test", max_steps=10**9)
        else:
            env = AlertTriageEnv(split="test", max_steps=min(int(max_steps), len(AlertTriageEnv(split="test", max_steps=10**9).observations)))
        state, _ = env.reset(options={"start_index": 0})
        if self.agent is None:
            raise RuntimeError("Trainer must be trained before evaluation")
        predictions: list[int] = []
        expected: list[int] = []
        rewards: list[float] = []
        latencies: list[float] = []
        action_counts: dict[int, int] = {idx: 0 for idx in ACTION_NAMES}
        correct = 0
        total_reward = 0.0
        samples = 0
        with torch.no_grad():
            while True:
                q_values = self.agent.model(torch.as_tensor(state, dtype=torch.float32).unsqueeze(0))
                start = perf_counter()
                action = int(torch.argmax(q_values, dim=1).item())
                latencies.append((perf_counter() - start) * 1000.0)
                next_state, reward, terminated, truncated, info = env.step(action)
                target_action = expected_action(int(info["incident_grade"]))
                predictions.append(action)
                expected.append(target_action)
                rewards.append(float(reward))
                action_counts[action] = action_counts.get(action, 0) + 1
                correct += int(action == target_action)
                total_reward += float(reward)
                samples += 1
                state = next_state
                if terminated or truncated:
                    break
        confusion_matrix = {action: {target: 0 for target in ACTION_NAMES} for action in ACTION_NAMES}
        for pred, target in zip(predictions, expected, strict=False):
            confusion_matrix[pred][target] += 1
        precision_values: list[float] = []
        recall_values: list[float] = []
        f1_values: list[float] = []
        for label in ACTION_NAMES:
            tp = confusion_matrix[label][label]
            fp = sum(confusion_matrix[other][label] for other in ACTION_NAMES if other != label)
            fn = sum(confusion_matrix[label][other] for other in ACTION_NAMES if other != label)
            precision = tp / (tp + fp) if (tp + fp) else 0.0
            recall = tp / (tp + fn) if (tp + fn) else 0.0
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
            precision_values.append(precision)
            recall_values.append(recall)
            f1_values.append(f1)
        return {
            "split": "test",
            "samples": int(samples),
            "test_rows": int(len(env.observations)),
            "policy_action_accuracy": correct / samples if samples else None,
            "average_historical_reward": total_reward / samples if samples else None,
            "total_historical_reward": total_reward,
            "action_distribution": action_counts,
            "confusion_matrix": confusion_matrix,
            "precision": sum(precision_values) / len(precision_values) if precision_values else None,
            "recall": sum(recall_values) / len(recall_values) if recall_values else None,
            "f1": sum(f1_values) / len(f1_values) if f1_values else None,
            "inference_latency_mean": float(sum(latencies) / len(latencies)) if latencies else None,
            "inference_latency_p95": float(torch.tensor(latencies).quantile(0.95).item()) if latencies else None,
        }
