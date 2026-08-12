import { apiRequest } from "./api";
import type { ExperimentStatus, TrainingCheckpoints, TrainingHistory, TrainingStatus } from "../types/domain";

export const trainingService = {
  getStatus: () => apiRequest<TrainingStatus>("/api/training/status"),
  getHistory: () => apiRequest<TrainingHistory>("/api/training/history"),
  getCheckpoints: () => apiRequest<TrainingCheckpoints>("/api/training/checkpoints"),
  getMetrics: () => apiRequest<TrainingMetricsResponse>("/api/training/metrics"),
  start: () => apiRequest<{ message: string }>("/api/training/start", { method: "POST" }),
  stop: () => apiRequest<{ message: string }>("/api/training/stop", { method: "POST" }),
  startExperiment: (models: unknown) => apiRequest<unknown>("/api/training/experiment", { method: "POST", body: JSON.stringify(models) }),
  stopExperiment: (runId: string) => apiRequest<unknown>(`/api/training/experiment/${runId}/stop`, { method: "POST" }),
  getExperimentStatus: (runId: string) => apiRequest<ExperimentStatus>(`/api/training/experiment/${runId}/status`),
};

export type TrainingMetricRow = {
  epoch: number;
  rows?: number;
  incidents?: number;
  updates?: number;
  total_updates?: number;
  updates_per_epoch?: number;
  loss: number;
  average_reward?: number;
  policy_reward?: number;
  oracle_average_reward?: number;
  reward_efficiency?: number;
  action_counts?: Record<string, number>;
  time_seconds?: number;
  validation?: Record<string, unknown> | null;
  validation_score?: number | null;
  patience_used?: number;
  best_epoch?: number;
};

export type TrainingMetricsResponse = {
  metrics: {
    config?: Record<string, unknown>;
    metrics: TrainingMetricRow[];
  };
};

export type AuthoritativeHistoryPoint = {
  epoch: number;
  loss: number;
  avg_reward?: number | null;
  average_reward?: number | null;
  policy_reward?: number | null;
  oracle_average_reward?: number | null;
  reward_efficiency?: number | null;
  updates?: number | null;
  total_updates?: number | null;
  updates_per_epoch?: number | null;
  rows?: number | null;
  incidents?: number | null;
  action_distribution?: Record<string, number> | null;
  time_seconds?: number | null;
  validation?: Record<string, unknown> | null;
  validation_score?: number | null;
  patience_used?: number | null;
  best_epoch?: number | null;
};

export type AuthoritativeResults = {
  source?: string;
  status?: string;
  dataset?: {
    name?: string;
    train_rows?: number | null;
    validation_rows?: number | null;
    test_rows?: number | null;
    train_incidents?: number | null;
    validation_incidents?: number | null;
    test_incidents?: number | null;
    incident_overlap?: number | null;
    feature_count?: number | null;
    synthetic_data?: boolean | null;
    unseen_incidents?: boolean | null;
  };
  training?: {
    model_name?: string | null;
    candidate_index?: number | null;
    candidate_count?: number | null;
    learning_rate?: number | null;
    epochs?: number | null;
    actual_epochs?: number | null;
    min_epochs?: number | null;
    patience?: number | null;
    min_delta?: number | null;
    batch_size?: number | null;
    updates_per_epoch?: number | null;
    max_total_updates?: number | null;
    total_updates_used?: number | null;
    final_epoch?: number | null;
    final_loss?: number | null;
    final_avg_reward?: number | null;
    policy_reward?: number | null;
    oracle_average_reward?: number | null;
    reward_efficiency?: number | null;
    action_distribution?: Record<string, number> | null;
    validation?: Record<string, unknown> | null;
    validation_score?: number | null;
    patience_used?: number | null;
    best_epoch?: number | null;
    history?: AuthoritativeHistoryPoint[];
  };
  comparison?: {
    status?: string;
    selection_rule?: string;
    test_used_for_selection?: boolean;
    candidates?: Array<Record<string, unknown>>;
    best?: Record<string, unknown> | null;
  } | null;
  evaluation?: {
    samples?: number | null;
    throughput_rows_per_second?: number | null;
    average_reward?: number | null;
    oracle_average_reward?: number | null;
    policy_optimality?: number | null;
    reward_efficiency?: number | null;
    reward_regret?: number | null;
    action_distribution?: Record<string, number> | null;
    per_class?: Record<string, { rows?: number; average_reward?: number; optimality?: number }> | null;
  };
  model?: {
    path?: string | null;
    exists?: boolean;
    size_bytes?: number | null;
    modified_at?: string | null;
  };
};

export type AuthoritativeTrainingStatus = {
  status: string;
  message?: string;
  started_at?: string | null;
  pid?: number | null;
  results?: AuthoritativeResults | null;
};

export const getAuthoritativeFullTrainingStatus = () =>
  apiRequest<AuthoritativeTrainingStatus>("/api/training-control");

export const startAuthoritativeFullTraining = () =>
  apiRequest<{ status: string; message?: string }>("/api/training-control", { method: "POST" });

export const stopAuthoritativeFullTraining = () =>
  apiRequest<{ status: string; message?: string }>("/api/training-control/stop", { method: "POST" });
