"""Reward wrapper helpers.

Small utilities to compute or normalize reward values coming from the
environment/decision pipeline.
"""

from typing import Dict, Any


def compute_reward_value(decision: Dict[str, Any], metrics: Dict[str, Any]) -> float:
	"""Compute a simple scalar reward from a decision and metrics.

	This is intentionally tiny: combine a provided reward_value if present,
	otherwise synthesize a small value from simple metrics.
	"""
	if "reward_value" in metrics:
		return float(metrics["reward_value"])

	# fallback: positive reward for reduced latency, negative for increases
	latency = float(metrics.get("latency_reduction", 0.0))
	fp_penalty = float(metrics.get("false_positive_penalty", 0.0))

	return max(-10.0, min(10.0, latency * 10.0 - fp_penalty))


__all__ = ["compute_reward_value"]

