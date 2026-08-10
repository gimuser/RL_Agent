import { apiRequest } from "./api";
import type { TrainingCheckpoints, TrainingHistory, TrainingStatus } from "../types/domain";

export const trainingService = {
  getStatus: () => apiRequest<TrainingStatus>("/api/training/status"),
  getHistory: () => apiRequest<TrainingHistory>("/api/training/history"),
  getCheckpoints: () => apiRequest<TrainingCheckpoints>("/api/training/checkpoints"),
  start: () => apiRequest<{ message: string }>("/api/training/start", { method: "POST" }),
  stop: () => apiRequest<{ message: string }>("/api/training/stop", { method: "POST" }),
};
