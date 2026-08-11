"""Public Gymnasium environment exports.

`SimpleEnv` used to fabricate random alerts and rewards. It has deliberately
been replaced by the dataset-backed environment; callers must select a split
of the repository's real processed data.
"""

from .triage_env import AlertTriageEnv

SimpleEnv = AlertTriageEnv  # backwards-compatible import name; no synthetic behavior

__all__ = ["AlertTriageEnv", "SimpleEnv"]
