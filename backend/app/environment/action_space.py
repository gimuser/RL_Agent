"""Action space definitions.

Provide a minimal DiscreteActionSpace compatible with simple agent code.
"""

from random import randint
from typing import List


class DiscreteActionSpace:
	def __init__(self, n: int = 2, actions: List[str] | None = None):
		self.n = n
		self.actions = actions or [str(i) for i in range(n)]

	def sample(self) -> int:
		return randint(0, self.n - 1)

	def contains(self, action: int) -> bool:
		return 0 <= int(action) < self.n


__all__ = ["DiscreteActionSpace"]

