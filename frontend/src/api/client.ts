const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export const api = {
  // Health
  health: () => request<import("../types/api").HealthResponse>("/health"),

  // Runs
  createRun: (data: import("../types/api").PayoutRunCreate) =>
    request<import("../types/api").PayoutRunResponse>("/runs", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getRun: (id: number) =>
    request<import("../types/api").PayoutRunResponse>(`/runs/${id}`),

  listRuns: (skip = 0, limit = 50) =>
    request<import("../types/api").PayoutRunResponse[]>(
      `/runs?skip=${skip}&limit=${limit}`
    ),

  uploadFile: (runId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<import("../types/api").PayoutRunResponse>(`/runs/${runId}/upload`, {
      method: "POST",
      body: formData,
      headers: {}, // Let browser set Content-Type with boundary
    });
  },

  uploadText: (runId: number, text: string) =>
    request<import("../types/api").PayoutRunResponse>(`/runs/${runId}/text`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  getRunItems: (runId: number) =>
    request<import("../types/api").PayoutItemResponse[]>(`/runs/${runId}/items`),

  setItemDecision: (runId: number, itemId: number, decision: import("../types/api").HumanDecision) =>
    request<import("../types/api").PayoutItemResponse>(`/runs/${runId}/items/${itemId}/decision`, {
      method: "POST",
      body: JSON.stringify({ human_decision: decision }),
    }),

  approveAllPending: (runId: number) =>
    request<import("../types/api").PayoutRunResponse>(`/runs/${runId}/approve-all`, {
      method: "POST",
    }),

  executeRun: (runId: number) =>
    request<import("../types/api").PayoutRunResponse>(`/runs/${runId}/execute`, {
      method: "POST",
    }),

  getAuditSummary: (runId: number) =>
    request<import("../types/api").AuditSummary>(`/runs/${runId}/audit`),
};

// Query keys for TanStack Query
export const queryKeys = {
  health: ["health"] as const,
  runs: (skip: number, limit: number) => ["runs", skip, limit] as const,
  run: (id: number) => ["run", id] as const,
  runItems: (runId: number) => ["runItems", runId] as const,
  auditSummary: (runId: number) => ["auditSummary", runId] as const,
};