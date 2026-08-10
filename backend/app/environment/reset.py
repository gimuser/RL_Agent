"""Reset helpers for the environment.

Provide convenience functions to initialize environment state objects used by
the `SimpleEnv` implementation and related helpers.
"""

from typing import List


def reset_state(state_size: int = 8) -> List[float]:
	"""Return a fresh initial observation/state vector."""
	from random import random

	return [random() for _ in range(state_size)]


__all__ = ["reset_state"]

