from enum import IntEnum

from gymnasium import spaces


class SocAction(IntEnum):
    IGNORE = 0
    INVESTIGATE = 1
    CONTAIN = 2
    CLOSE_FALSE_POSITIVE = 3
    ESCALATE = 4


def make_action_space() -> spaces.Discrete:
    return spaces.Discrete(len(SocAction))
