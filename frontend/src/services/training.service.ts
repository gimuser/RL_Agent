import { apiRequest } from "./api";
import type { ExperimentStatus, TrainingCheckpoints, TrainingHistory, TrainingStatus } from "../types/domain";

export const trainingService = {
  getStatus: () => apiRequest<TrainingStatus>("/api/training/status"),
  getHistory: () => apiRequest<TrainingHistory>("/api/training/history"),
  getCheckpoints: () => apiRequest<TrainingCheckpoints>("/api/training/checkpoints"),
  getMetrics: () => apiRequest<{ metrics: { epoch: number; loss: number; timestamp?: string }[] }> ("/api/training/metrics"),
  start: () => apiRequest<{ message: string }> ("/api/training/start", { method: "POST" }),
  stop: () => apiRequest<{ message: string }> ("/api/training/stop", { method: "POST" }),
  startExperiment: (models: any) => apiRequest<any>("/api/training/experiment", { method: "POST", body: JSON.stringify(models) }),
  stopExperiment: (runId: string) => apiRequest<any>(`/api/training/experiment/${runId}/stop`, { method: "POST" }),
  getExperimentStatus: (runId: string) => apiRequest<ExperimentStatus>(`/api/training/experiment/${runId}/status`),
};
