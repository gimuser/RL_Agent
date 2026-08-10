from dataclasses import dataclass


@dataclass
class Analyst:
    name: str
    capacity: int = 5
    handled_alerts: int = 0
    workload: int = 0

    @property
    def utilization(self) -> float:
        return min(1.0, self.workload / max(1, self.capacity))
