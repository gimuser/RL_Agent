"""Offline-RL algorithm registry and capability checks.

CQL can be trained with the current counterfactual reward matrix.
IQL/BCQ require logged behavior actions; this project currently has none.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AlgorithmSpec:
    name: str
    display_name: str
    family: str
    requires_logged_actions: bool
    description: str


ALGORITHMS = {
    "double_dqn": AlgorithmSpec(
        "double_dqn", "Double DQN", "value-based", False,
        "Current incident-level counterfactual Q-learning baseline.",
    ),
    "cql": AlgorithmSpec(
        "cql", "Conservative Q-Learning", "offline-value", False,
        "Conservative Q-learning variant suitable for the current counterfactual action setup.",
    ),
    "iql": AlgorithmSpec(
        "iql", "Implicit Q-Learning", "offline-value", True,
        "Requires a logged behavior action for each transition.",
    ),
    "bcq": AlgorithmSpec(
        "bcq", "Batch-Constrained Q-Learning", "offline-value", True,
        "Requires logged behavior actions to learn the dataset action support.",
    ),
}


def get_algorithm(name: str) -> AlgorithmSpec:
    key = name.strip().lower()
    try:
        return ALGORITHMS[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported offline-RL algorithm: {name}") from exc


def available_for_dataset(columns: list[str] | tuple[str, ...]) -> list[AlgorithmSpec]:
    cols = {str(c) for c in columns}
    has_logged_action = bool(
        cols.intersection({"Action", "action", "AgentAction", "agent_action"})
    )
    return [
        spec
        for spec in ALGORITHMS.values()
        if (not spec.requires_logged_actions) or has_logged_action
    ]


def capability_report(columns: list[str] | tuple[str, ...]) -> dict:
    cols = {str(c) for c in columns}
    has_logged_action = bool(
        cols.intersection({"Action", "action", "AgentAction", "agent_action"})
    )
    return {
        "logged_behavior_actions": has_logged_action,
        "algorithms": {
            name: {
                "available": (not spec.requires_logged_actions) or has_logged_action,
                "requires_logged_actions": spec.requires_logged_actions,
                "description": spec.description,
            }
            for name, spec in ALGORITHMS.items()
        },
    }
