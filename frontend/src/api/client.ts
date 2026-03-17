import type {
  AnalysisSummary,
  AuthConfig,
  AuthSessionResponse,
  AuthUser,
  CreateProjectPayload,
  Draft,
  ExportResult,
  GenerateDraftPayload,
  HealthResponse,
  IdResponse,
  Project,
  ProjectStatus,
  ReviewReport,
  TemplateListResponse,
  UpdateDraftPayload,
  EvidenceItem,
} from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";
const API_TOKEN = import.meta.env.VITE_API_TOKEN?.trim();
const ACCESS_TOKEN_STORAGE_KEY = "scholarflow.access_token";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function getStoredAuthToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY);
}

export function getAuthToken(): string | null {
  return getStoredAuthToken() || API_TOKEN || null;
}

export function setAuthToken(token: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, token);
}

export function clearAuthToken(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const authToken = getAuthToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      ...(init?.headers ?? {}),
    },
  });

  const raw = await response.text();
  const data = raw ? (JSON.parse(raw) as Record<string, unknown>) : null;
  if (!response.ok) {
    const detail =
      (data && typeof data.detail === "string" && data.detail) || response.statusText;
    throw new ApiError(response.status, detail || "Request failed");
  }
  return data as T;
}

export const api = {
  getHealth(): Promise<HealthResponse> {
    return request("/health");
  },

  getAuthConfig(): Promise<AuthConfig> {
    return request("/api/auth/config");
  },

  createSession(payload: { email: string; name?: string }): Promise<AuthSessionResponse> {
    return request("/api/auth/session", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getCurrentUser(): Promise<AuthUser> {
    return request("/api/auth/me");
  },

  listTemplates(): Promise<TemplateListResponse> {
    return request("/api/templates");
  },

  createProject(payload: CreateProjectPayload): Promise<IdResponse> {
    return request("/api/projects", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getProject(projectId: string): Promise<Project> {
    return request(`/api/projects/${projectId}`);
  },

  getProjectStatus(projectId: string): Promise<ProjectStatus> {
    return request(`/api/projects/${projectId}/status`);
  },

  listDrafts(projectId: string): Promise<Draft[]> {
    return request(`/api/projects/${projectId}/drafts`);
  },

  updateDraft(projectId: string, version: number, payload: UpdateDraftPayload): Promise<Draft> {
    return request(`/api/projects/${projectId}/drafts/${version}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  generateDraft(projectId: string, payload: GenerateDraftPayload): Promise<IdResponse> {
    return request(`/api/projects/${projectId}/drafts/generate`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listEvidence(projectId: string): Promise<EvidenceItem[]> {
    return request(`/api/projects/${projectId}/evidence`);
  },

  listReviews(projectId: string): Promise<ReviewReport[]> {
    return request(`/api/projects/${projectId}/review`);
  },

  runReview(projectId: string, draftVersion: number): Promise<IdResponse> {
    return request(`/api/projects/${projectId}/review`, {
      method: "POST",
      body: JSON.stringify({ draft_version: draftVersion }),
    });
  },

  getAnalysisSummary(projectId: string): Promise<AnalysisSummary> {
    return request(`/api/projects/${projectId}/analysis/summary`);
  },

  exportDraft(projectId: string, format: "markdown" | "latex" | "word" | "docx"): Promise<IdResponse> {
    return request(`/api/projects/${projectId}/export`, {
      method: "POST",
      body: JSON.stringify({ format }),
    });
  },

  getExport(projectId: string, fileId: string): Promise<ExportResult> {
    return request(`/api/projects/${projectId}/export/${fileId}`);
  },
};
