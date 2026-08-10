from gymnasium import spaces
import numpy as np


# Alert severity, confidence, age, queue/SOC indicators and recent outcome metrics.
OBSERVATION_SIZE = 11


def make_observation_space() -> spaces.Box:
    return spaces.Box(low=0.0, high=1.0, shape=(OBSERVATION_SIZE,), dtype=np.float32)
