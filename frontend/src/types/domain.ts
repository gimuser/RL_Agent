export type ApiHealth = "online" | "offline" | "unknown";

export interface Alert {
  id: string | number;
  title: string;
  severity: string;
  source: string;
}

export interface Decision {
  id: number;
  incident_id: number;
  action: string;
  timestamp: string;
}

export interface Reward {
  id: number;
  decision_id: number;
  reward_value: number;
  metrics: Record<string, unknown>;
  timestamp: string;
}

export interface DashboardSummary {
  total_alerts: number;
  processed_alerts: number;
  total_decisions: number;
  total_rewards: number;
  average_reward: number;
  average_latency: number;
  accuracy: number;
  database_status: string;
  training_status: string;
  current_episode: number;
}

export interface SystemHealth {
  status: string;
}

export interface TrainingStatus {
  status: string;
  current_epoch: number;
}

export interface TrainingHistoryPoint {
  epoch: number;
  loss: number;
}

export interface TrainingHistory {
  history: TrainingHistoryPoint[];
}

export interface TrainingCheckpoints {
  checkpoints: string[];
}

export interface PipelineStats {
  total_rows: number;
  total_columns: number;
  missing_values: number;
}

export interface PipelineStatus {
  status: string;
  last_run: string;
}

export interface DatabaseHealth {
  status: string;
  database: string;
}

export interface DatabaseStatistics {
  collections_count: number;
  total_objects: number;
}

export interface RewardStatistics {
  mean_reward: number;
  max_reward: number;
  min_reward: number;
}

export interface ToastMessage {
  id: number;
  tone: "success" | "error" | "info";
  title: string;
  description?: string;
}
