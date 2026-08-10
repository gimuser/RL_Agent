"""State-building helpers.

This module contains a tiny helper to construct a numeric state vector from a
source event (like an alert). The real project would build rich features;
here we implement a safe, deterministic fallback for testing and integration.
"""

from typing import Any, Dict, List


def build_state_from_event(event: Dict[str, Any], state_size: int = 8) -> List[float]:
	"""Build a fixed-size numeric vector from an event dictionary.

	The function extracts a few numeric-ish fields when present and fills the
	remainder with hashed values to ensure consistent length.
	"""
	values: List[float] = []

	# Pull numeric fields if present
	for key in ("severity", "incident_score", "latency_ms"):
		if key in event and isinstance(event[key], (int, float)):
			values.append(float(event[key]))

	# Use string fields hashed into floats for the rest
	def _hash_str(s: str) -> float:
		return float(abs(hash(s)) % 1000) / 1000.0

	for key in ("source", "category", "threat_family"):
		if key in event:
			values.append(_hash_str(str(event[key])))

	# Pad or trim to required size
	if len(values) >= state_size:
		return values[:state_size]

	while len(values) < state_size:
		values.append(0.0)

	return values


__all__ = ["build_state_from_event"]

