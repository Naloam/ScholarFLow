import type {
  AnalysisSummary,
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  const raw = await response.text();
  const data = raw ? (JSON.parse(raw) as Record<string, unknown>) : null;
  if (!response.ok) {
    const detail =
      (data && typeof data.detail === "string" && data.detail) || response.statusText;
    throw new Error(detail || "Request failed");
  }
  return data as T;
}

export const api = {
  getHealth(): Promise<HealthResponse> {
    return request("/health");
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
