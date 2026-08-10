import { apiRequest } from "./api";
import type { Decision } from "../types/domain";

export const decisionsService = {
  getDecisions: (skip = 0, limit = 100) =>
    apiRequest<Decision[]>(`/api/decisions?skip=${skip}&limit=${limit}`),
};
