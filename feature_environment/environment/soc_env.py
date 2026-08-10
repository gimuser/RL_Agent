from typing import Any
import gymnasium as gym

from feature_environment.gym.action_space import SocAction, make_action_space
from feature_environment.gym.observation_space import make_observation_space
from .reward_engine import RewardEngine
from .simulator import SOCSimulator
from .state_builder import StateBuilder
from .transition import TransitionEngine


class SOCEnv(gym.Env):
    """Gymnasium environment for autonomous SOAR alert-triage policies.

    Actions are ``IGNORE``, ``INVESTIGATE``, ``CONTAIN``, ``CLOSE_FALSE_POSITIVE``
    and ``ESCALATE`` (see :class:`gym.action_space.SocAction`).
    """

    metadata = {"render_modes": ["human"], "render_fps": 4}

    def __init__(self, max_steps: int = 100, initial_alerts: int = 4, render_mode: str | None = None):
        super().__init__()
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        if initial_alerts < 0:
            raise ValueError("initial_alerts cannot be negative")
        if render_mode not in (None, "human"):
            raise ValueError("render_mode must be None or 'human'")
        self.max_steps = max_steps
        self.render_mode = render_mode
        self.simulator = SOCSimulator(max_steps=max_steps, initial_alerts=initial_alerts)
        self.action_space = make_action_space()
        self.observation_space = make_observation_space()
        self.state_builder, self.reward_engine, self.transition_engine = StateBuilder(), RewardEngine(), TransitionEngine()

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        self.simulator.reset(seed=seed)
        observation = self.state_builder.build(self.simulator).as_array()
        return observation, self._info("reset")

    def step(self, action: int):
        if not self.action_space.contains(action):
            raise ValueError(f"Invalid SOC action: {action}")
        alert = self.simulator.current_alert
        result = self.transition_engine.apply(self.simulator, SocAction(action))
        self.simulator.advance_time()
        reward = self.reward_engine.reward(SocAction(action), alert, result.outcome, len(self.simulator.queue))
        # Reaching the time horizon is a truncation, not a terminal SOC state.
        # This distinction lets Gymnasium RL algorithms bootstrap correctly.
        terminated = False
        truncated = self.simulator.step_count >= self.max_steps
        observation = self.state_builder.build(self.simulator).as_array()
        info = self._info(result.outcome)
        if self.render_mode == "human":
            self.render()
        return observation, reward, terminated, truncated, info

    def _info(self, outcome: str) -> dict[str, Any]:
        alert = self.simulator.current_alert
        return {
            "outcome": outcome,
            "queue_size": len(self.simulator.queue),
            "open_incidents": self.simulator.open_incident_count,
            "current_alert_id": None if alert is None else alert.identifier,
            "containment_rate": self.simulator.containment_rate,
        }

    def render(self):
        alert = self.simulator.current_alert
        return f"step={self.simulator.step_count} queue={len(self.simulator.queue)} alert={alert} incidents={self.simulator.open_incident_count}"
