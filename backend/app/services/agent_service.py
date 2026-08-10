"""Agent service logic.

This module exposes tiny helpers to interact with an agent from API handlers.
The real project likely uses more advanced orchestration; here we provide a
safe, dependency-free surface for the frontend and tests.
"""

import random
from typing import Dict, Any


AGENT_STATE = {"status": "idle", "last_action": None}


def get_agent_status() -> Dict[str, Any]:
	return {"status": AGENT_STATE["status"], "last_action": AGENT_STATE["last_action"]}


def act_on_event(event: Dict[str, Any]) -> Dict[str, Any]:
	"""Decide on an action for the incoming event and persist a tiny state.

	This deterministic placeholder returns a simple action selected at
	random from a small action set to allow end-to-end flows to run.
	"""
	action = random.choice(["ignore", "investigate", "block"])
	AGENT_STATE["last_action"] = action
	AGENT_STATE["status"] = "active"

	return {"action": action, "reason": "placeholder-policy"}


__all__ = ["get_agent_status", "act_on_event"]

