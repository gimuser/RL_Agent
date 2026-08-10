import numpy as np

from .observation import Observation


class StateBuilder:
    """Maps rich simulator state to a fixed-size, policy-safe observation."""

    def build(self, simulator) -> Observation:
        alert = simulator.current_alert
        if alert is None:
            alert_values = [0.0, 0.0, 0.0, 0.0]
        else:
            alert_values = [
                float(alert.severity) / 4.0,
                float(alert.confidence),
                min(alert.age / simulator.max_alert_age, 1.0),
                min(alert.investigation_count / 2.0, 1.0),
            ]
        values = np.array(
            alert_values
            + [
                min(len(simulator.queue) / simulator.queue_capacity, 1.0),
                simulator.analyst.utilization,
                min(simulator.open_incident_count / simulator.queue_capacity, 1.0),
                min(simulator.total_alerts_seen / simulator.episode_alert_budget, 1.0),
                simulator.containment_rate,
                simulator.false_positive_rate,
                min(simulator.step_count / simulator.max_steps, 1.0),
            ],
            dtype=np.float32,
        )
        return Observation(values)
