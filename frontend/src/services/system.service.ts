import { apiRequest } from "./api";
import type { ApiComponent } from "../types/domain";

export const systemService = {
  getApis: () => apiRequest<{ components: ApiComponent[] }>("/api/system/apis"),
};
