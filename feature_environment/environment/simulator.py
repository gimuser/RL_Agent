from collections import deque
import numpy as np

from feature_environment.soc.alert import Alert, AlertStatus, Severity
from feature_environment.soc.analyst import Analyst
from feature_environment.soc.incident import Incident
from feature_environment.soc.playbook import DEFAULT_PLAYBOOKS


class SOCSimulator:
    """Small stochastic model of incoming SIEM alerts and SOC workload."""

    queue_capacity = 20
    max_alert_age = 20

    def __init__(self, max_steps: int = 100, initial_alerts: int = 4):
        self.max_steps, self.initial_alerts = max_steps, initial_alerts
        self.episode_alert_budget = max_steps + initial_alerts
        self.rng = np.random.default_rng()
        self.reset()

    def reset(self, seed: int | None = None) -> None:
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self.queue = deque()
        self.current_alert = None
        self.incidents: list[Incident] = []
        self.playbooks = DEFAULT_PLAYBOOKS
        self.analyst = Analyst("SOC analyst")
        self.step_count = self.total_alerts_seen = 0
        self.contained_malicious = self.closed_false_positives = 0
        self.total_malicious = self.total_benign = 0
        self.next_alert_id = self.next_incident_id = 1
        for _ in range(self.initial_alerts):
            self.enqueue_alert()
        self.select_next_alert()

    def enqueue_alert(self) -> None:
        if len(self.queue) >= self.queue_capacity:
            return
        severity = Severity(int(self.rng.integers(1, 5)))
        malicious_probability = 0.08 + 0.18 * float(severity)
        malicious = bool(self.rng.random() < malicious_probability)
        base_confidence = 0.62 if malicious else 0.38
        confidence = float(np.clip(self.rng.normal(base_confidence, 0.18), 0.01, 0.99))
        alert = Alert(self.next_alert_id, severity, malicious, confidence)
        self.next_alert_id += 1
        self.total_alerts_seen += 1
        self.total_malicious += int(malicious)
        self.total_benign += int(not malicious)
        self.queue.append(alert)

    def select_next_alert(self) -> None:
        self.current_alert = self.queue.popleft() if self.queue else None
        self.analyst.workload = len(self.queue) + int(self.current_alert is not None)

    def resolve_current(self) -> None:
        self.analyst.handled_alerts += 1
        self.current_alert = None
        self.select_next_alert()

    def advance_time(self) -> None:
        self.step_count += 1
        for alert in self.queue:
            alert.age += 1
        if self.current_alert is not None:
            self.current_alert.age += 1
        # One incoming SIEM alert per decision keeps queue pressure meaningful.
        self.enqueue_alert()
        if self.current_alert is None:
            self.select_next_alert()

    @property
    def open_incident_count(self) -> int:
        return sum(incident.status == "open" for incident in self.incidents)

    @property
    def containment_rate(self) -> float:
        return self.contained_malicious / max(1, self.total_malicious)

    @property
    def false_positive_rate(self) -> float:
        return self.closed_false_positives / max(1, self.total_benign)
