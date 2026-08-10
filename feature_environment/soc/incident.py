from dataclasses import dataclass, field

from .alert import Alert


class IncidentStatus(str):
    OPEN = "open"
    CONTAINED = "contained"
    CLOSED = "closed"


@dataclass
class Incident:
    identifier: int
    alert_ids: list[int] = field(default_factory=list)
    status: str = IncidentStatus.OPEN

    @classmethod
    def from_alert(cls, identifier: int, alert: Alert) -> "Incident":
        return cls(identifier=identifier, alert_ids=[alert.identifier])
