"""Gym-compatible environment interface.

This module provides a very small, custom environment class with the
`reset()` and `step(action)` methods that resemble gym.Env. The goal is not
to be a full simulator but to give other modules a predictable interface to
exercise training and integration code during development and tests.
"""

import random
from typing import Tuple, Any


class SimpleEnv:
	"""A minimal environment with a small discrete action space.

	Observations are fixed-size lists of floats. Actions are integers
	between 0 and (action_space-1).
	"""

	def __init__(self, state_size: int = 8, action_space: int = 3, max_steps: int = 50):
		self.state_size = state_size
		self.action_space = action_space
		self.max_steps = max_steps
		self._step_count = 0

	def reset(self) -> list[float]:
		self._step_count = 0
		return [random.random() for _ in range(self.state_size)]

	def step(self, action: int) -> Tuple[list[float], float, bool, dict]:
		"""Apply an action and return (next_state, reward, done, info)."""
		self._step_count += 1

		# simple reward: +1 for action 0, 0 otherwise (toy example)
		reward = 1.0 if action == 0 else 0.0

		next_state = [random.random() for _ in range(self.state_size)]
		done = self._step_count >= self.max_steps
		info = {"step": self._step_count}

		return next_state, reward, done, info


__all__ = ["SimpleEnv"]

