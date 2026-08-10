"""Severity-based reward logic."""
"""
backend/app/reward/severity_reward.py

Calcul de la récompense principale selon :

- IncidentGrade
- Action choisie par l'agent

Action :
    0 -> Close / Ignore
    1 -> Escalate
"""

from dataclasses import dataclass
from typing import Dict, Any

from .reward_config import reward_config


@dataclass
class SeverityReward:
    """
    Reward basé sur la sévérité réelle
    de l'incident.
    """

    config = reward_config

    def compute(
        self,
        incident: Dict[str, Any],
        action: int
    ) -> float:

        grade = str(
            incident.get(
                "IncidentGrade",
                ""
            )
        ).strip()

        # ---------------------------------------------------
        # TRUE POSITIVE
        # ---------------------------------------------------

        if grade == "TruePositive":

            # Bonne décision
            if action == 1:

                return self.config.true_positive_reward

            # False Negative
            return self.config.missed_true_positive_penalty

        # ---------------------------------------------------
        # FALSE POSITIVE
        # ---------------------------------------------------

        elif grade == "FalsePositive":

            # Bonne décision
            if action == 0:

                return self.config.false_positive_reward

            # Escalade inutile
            return self.config.false_positive_escalation_penalty

        # ---------------------------------------------------
        # BENIGN POSITIVE
        # ---------------------------------------------------

        elif grade == "BenignPositive":

            # Bonne décision
            if action == 0:

                return self.config.benign_positive_reward

            # Escalade inutile
            return self.config.wrong_benign_penalty

        # ---------------------------------------------------
        # UNKNOWN INCIDENT
        # ---------------------------------------------------

        return 0.0
