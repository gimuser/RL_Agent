"""Observation space definitions.

Provide a tiny helper describing observation shapes for synthetic envs.
"""

from typing import Tuple


class ObservationSpace:
	def __init__(self, shape: Tuple[int, ...]):
		self.shape = shape

	def sample(self):
		from random import random
		return [random() for _ in range(self.shape[0])]


__all__ = ["ObservationSpace"]

