from pydantic import BaseModel, ConfigDict

class DashboardSummary(BaseModel):
    total_alerts: int
    processed_alerts: int
    total_decisions: int
    total_rewards: int
    average_reward: float
    average_latency: float
    accuracy: float
    database_status: str
    training_status: str
    current_episode: int

    model_config = ConfigDict(from_attributes=True)