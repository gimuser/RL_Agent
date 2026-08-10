from dataclasses import dataclass

from feature_environment.gym.action_space import SocAction
from feature_environment.soc.alert import AlertStatus
from feature_environment.soc.incident import Incident, IncidentStatus


@dataclass(frozen=True)
class TransitionResult:
    outcome: str
    resolved: bool


class TransitionEngine:
    def apply(self, simulator, action: SocAction) -> TransitionResult:
        alert = simulator.current_alert
        if alert is None:
            return TransitionResult("no_alert", True)
        if action == SocAction.INVESTIGATE:
            alert.status = AlertStatus.INVESTIGATING
            alert.investigation_count += 1
            return TransitionResult("investigating", False)
        if action == SocAction.CONTAIN:
            alert.status = AlertStatus.CONTAINED
            playbook = next(
                (book for book in simulator.playbooks if book.supports(alert.severity)),
                None,
            )
            containment_succeeds = playbook is not None and simulator.rng.random() < playbook.containment_success
            if alert.is_malicious and containment_succeeds:
                simulator.contained_malicious += 1
            simulator.resolve_current()
            return TransitionResult("contained" if containment_succeeds else "containment_failed", True)
        if action == SocAction.CLOSE_FALSE_POSITIVE:
            alert.status = AlertStatus.CLOSED
            if not alert.is_malicious:
                simulator.closed_false_positives += 1
            simulator.resolve_current()
            return TransitionResult("closed_fp", True)
        if action == SocAction.ESCALATE:
            alert.status = AlertStatus.ESCALATED
            incident = Incident.from_alert(simulator.next_incident_id, alert)
            simulator.next_incident_id += 1
            incident.status = IncidentStatus.OPEN
            simulator.incidents.append(incident)
            simulator.resolve_current()
            return TransitionResult("escalated", True)
        alert.status = AlertStatus.CLOSED
        simulator.resolve_current()
        return TransitionResult("ignored", True)
