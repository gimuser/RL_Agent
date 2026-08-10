from dataclasses import dataclass, field
from enum import IntEnum


class Severity(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class AlertStatus(str):
    QUEUED = "queued"
    INVESTIGATING = "investigating"
    CONTAINED = "contained"
    CLOSED = "closed"
    ESCALATED = "escalated"


@dataclass
class Alert:
    """A SIEM alert, including a hidden ground-truth label for simulation."""

    identifier: int
    severity: Severity
    is_malicious: bool
    confidence: float
    age: int = 0
    status: str = AlertStatus.QUEUED
    investigation_count: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def risk(self) -> float:
        return float(self.severity) * self.confidence
