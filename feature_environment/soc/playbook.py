from dataclasses import dataclass
from typing import Iterable

from .alert import Severity


@dataclass(frozen=True)
class Playbook:
    name: str
    supported_severities: tuple[Severity, ...]
    containment_success: float = 0.85

    def supports(self, severity: Severity) -> bool:
        return severity in self.supported_severities


DEFAULT_PLAYBOOKS: tuple[Playbook, ...] = (
    Playbook("malware-containment", (Severity.HIGH, Severity.CRITICAL), 0.90),
    Playbook("phishing-triage", (Severity.LOW, Severity.MEDIUM, Severity.HIGH), 0.82),
)
