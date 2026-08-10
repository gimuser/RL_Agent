from feature_environment.gym.action_space import SocAction
from feature_environment.soc.alert import Alert


class RewardEngine:
    """Encodes SOC goals: resolve true incidents, avoid misses and reduce backlog."""

    def reward(self, action: SocAction, alert: Alert | None, outcome: str, backlog: int) -> float:
        if alert is None:
            return -0.15
        severity = float(alert.severity)
        if outcome == "contained":
            score = 2.0 * severity if alert.is_malicious else -1.5 * severity
        elif outcome == "containment_failed":
            score = -2.25 * severity if alert.is_malicious else -0.75 * severity
        elif outcome == "escalated":
            score = 1.25 * severity if alert.is_malicious else -0.25 * severity
        elif outcome == "investigating":
            score = 0.20 * severity if alert.is_malicious else -0.10
        elif outcome == "closed_fp":
            score = 1.0 if not alert.is_malicious else -2.5 * severity
        elif outcome == "ignored":
            score = -2.0 * severity if alert.is_malicious else 0.05
        else:
            score = -0.5
        return float(score - 0.04 * backlog)
