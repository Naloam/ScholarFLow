import type {
  AutoResearchBundleIndex,
  AutoResearchCandidateRegistry,
  AnalysisSummary,
  AutoResearchExecution,
  AutoResearchExecutionCommandResponse,
  AutoResearchPublishExport,
  AutoResearchPublishPackage,
  AutoResearchRun,
  AutoResearchRunReview,
  AutoResearchRunRegistry,
  AutoResearchRunRegistryViews,
  AutoResearchRunRequest,
  AuthConfig,
  AuthSessionPayload,
  AuthSessionResponse,
  AuthUser,
  BetaSummary,
  CreateFeedbackPayload,
  CreateMentorAccessPayload,
  CreateMentorFeedbackPayload,
  CreateProjectPayload,
  Draft,
  ExportResult,
  GenerateDraftPayload,
  HealthResponse,
  IdResponse,
  MentorAccessEntry,
  MentorFeedbackEntry,
  Project,
  ProjectListItem,
  ProjectStatus,
  ReviewReport,
  TemplateListResponse,
  UpdateDraftPayload,
  EvidenceItem,
} from "./types";

function inferApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim();
  if (configured) {
    return configured.replace(/\/$/, "");
  }
  if (typeof window === "undefined") {
    return "http://127.0.0.1:8000";
  }
  const { origin, protocol, hostname, port } = window.location;
  if (port === "5173" || port === "4173" || port === "4174") {
    return `${protocol}//${hostname}:8000`;
  }
  return origin.replace(/\/$/, "");
}

export const API_BASE_URL = inferApiBaseUrl();
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

function parseDownloadFilename(contentDisposition: string | null, fallback: string): string {
  if (!contentDisposition) {
    return fallback;
  }
  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1]);
  }
  const plainMatch = contentDisposition.match(/filename="?([^"]+)"?/i);
  if (plainMatch?.[1]) {
    return plainMatch[1];
  }
  return fallback;
}

async function download(path: string, fallbackName: string): Promise<string> {
  const authToken = getAuthToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
    },
  });

  if (!response.ok) {
    let detail = response.statusText || "Download failed";
    const raw = await response.text();
    if (raw) {
      try {
        const parsed = JSON.parse(raw) as Record<string, unknown>;
        if (typeof parsed.detail === "string" && parsed.detail) {
          detail = parsed.detail;
        }
      } catch {
        detail = raw;
      }
    }
    throw new ApiError(response.status, detail);
  }

  const blob = await response.blob();
  const fileName = parseDownloadFilename(
    response.headers.get("content-disposition"),
    fallbackName,
  );
  const objectUrl = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = fileName;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(objectUrl);
  return fileName;
}

export const api = {
  getHealth(): Promise<HealthResponse> {
    return request("/health");
  },

  getAuthConfig(): Promise<AuthConfig> {
    return request("/api/auth/config");
  },

  createSession(payload: AuthSessionPayload): Promise<AuthSessionResponse> {
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

  listProjects(): Promise<ProjectListItem[]> {
    return request("/api/projects");
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

  getBetaSummary(projectId: string): Promise<BetaSummary> {
    return request(`/api/projects/${projectId}/beta/summary`);
  },

  createFeedback(projectId: string, payload: CreateFeedbackPayload) {
    return request(`/api/projects/${projectId}/beta/feedback`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listMentorAccess(projectId: string): Promise<MentorAccessEntry[]> {
    return request(`/api/projects/${projectId}/mentor/access`);
  },

  createMentorAccess(projectId: string, payload: CreateMentorAccessPayload): Promise<MentorAccessEntry> {
    return request(`/api/projects/${projectId}/mentor/access`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listMentorFeedback(projectId: string): Promise<MentorFeedbackEntry[]> {
    return request(`/api/projects/${projectId}/mentor/feedback`);
  },

  createMentorFeedback(projectId: string, payload: CreateMentorFeedbackPayload): Promise<MentorFeedbackEntry> {
    return request(`/api/projects/${projectId}/mentor/feedback`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
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

  downloadExport(projectId: string, fileId: string): Promise<string> {
    return download(
      `/api/projects/${projectId}/export/${fileId}/download`,
      `${fileId}.bin`,
    );
  },

  startAutoResearch(projectId: string, payload: AutoResearchRunRequest): Promise<IdResponse> {
    return request(`/api/projects/${projectId}/auto-research/run`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getAutoResearchRun(projectId: string, runId: string): Promise<AutoResearchRun> {
    return request(`/api/projects/${projectId}/auto-research/${runId}`);
  },

  getAutoResearchExecution(projectId: string, runId: string): Promise<AutoResearchExecution> {
    return request(`/api/projects/${projectId}/auto-research/${runId}/execution`);
  },

  getAutoResearchRegistry(projectId: string, runId: string): Promise<AutoResearchRunRegistry> {
    return request(`/api/projects/${projectId}/auto-research/${runId}/registry`);
  },

  getAutoResearchCandidateRegistry(
    projectId: string,
    runId: string,
    candidateId: string,
  ): Promise<AutoResearchCandidateRegistry> {
    return request(
      `/api/projects/${projectId}/auto-research/${runId}/registry/candidates/${candidateId}`,
    );
  },

  getAutoResearchBundleIndex(projectId: string, runId: string): Promise<AutoResearchBundleIndex> {
    return request(`/api/projects/${projectId}/auto-research/${runId}/registry/bundles`);
  },

  getAutoResearchRegistryViews(projectId: string, runId: string): Promise<AutoResearchRunRegistryViews> {
    return request(`/api/projects/${projectId}/auto-research/${runId}/registry/views`);
  },

  getAutoResearchRunReview(projectId: string, runId: string): Promise<AutoResearchRunReview> {
    return request(`/api/projects/${projectId}/auto-research/${runId}/review`);
  },

  getAutoResearchPublishPackage(projectId: string, runId: string): Promise<AutoResearchPublishPackage> {
    return request(`/api/projects/${projectId}/auto-research/${runId}/publish`);
  },

  exportAutoResearchPublishPackage(
    projectId: string,
    runId: string,
  ): Promise<AutoResearchPublishExport> {
    return request(`/api/projects/${projectId}/auto-research/${runId}/publish/export`, {
      method: "POST",
    });
  },

  downloadAutoResearchPublishPackage(projectId: string, runId: string): Promise<string> {
    return download(
      `/api/projects/${projectId}/auto-research/${runId}/publish/download`,
      `${runId}-publish_bundle.zip`,
    );
  },

  resumeAutoResearch(
    projectId: string,
    runId: string,
  ): Promise<AutoResearchExecutionCommandResponse> {
    return request(`/api/projects/${projectId}/auto-research/${runId}/resume`, {
      method: "POST",
    });
  },

  retryAutoResearch(
    projectId: string,
    runId: string,
  ): Promise<AutoResearchExecutionCommandResponse> {
    return request(`/api/projects/${projectId}/auto-research/${runId}/retry`, {
      method: "POST",
    });
  },

  cancelAutoResearch(
    projectId: string,
    runId: string,
  ): Promise<AutoResearchExecutionCommandResponse> {
    return request(`/api/projects/${projectId}/auto-research/${runId}/cancel`, {
      method: "POST",
    });
  },
};
