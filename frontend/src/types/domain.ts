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
  total_alerts: number | null;
  processed_alerts: number | null;
  total_decisions: number | null;
  total_rewards: number | null;
  average_reward: number | null;
  average_latency: number | null;
  accuracy: number | null;
  database_status: string;
  training_status: string;
  current_episode: number | null;
}

export interface SystemHealth {
  status: string;
}

export interface ApiComponent {
  name: string;
  prefix: string;
  status: string;
  last_seen?: number | null;
  request_count?: number;
}

export interface TrainingStatus {
  status: string;
  current_epoch: number;
}

export interface ExperimentStatus {
  run_id?: string;
  status?: string;
  current_model?: string;
  model_index?: number;
  total_models?: number;
  training?: Record<string, unknown>;
  evaluation?: Record<string, unknown>;
  checkpoint?: string;
  best?: Record<string, unknown>;
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
  last_run: string | null;
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
  mean_reward: number | null;
  max_reward: number | null;
  min_reward: number | null;
}

export interface ToastMessage {
  id: number;
  tone: "success" | "error" | "info";
  title: string;
  description?: string;
}
