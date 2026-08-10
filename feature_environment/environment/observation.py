from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Observation:
    """Normalized vector consumed by an RL policy."""

    values: np.ndarray

    def as_array(self) -> np.ndarray:
        return self.values.astype(np.float32, copy=False)
