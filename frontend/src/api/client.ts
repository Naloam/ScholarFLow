// Typed client for the research-harness API + minimal auth.
// Talks ONLY to the 5 research-harness endpoints + /api/auth/{config,session}.
// The old ~60 autoresearch endpoints are intentionally NOT migrated (FROZEN).

import type {
  AuthConfig,
  AuthSessionResponse,
  DeploymentStatus,
  ProjectSummary,
  PublishBundleManifest,
  ReauditResponse,
  RunStatus,
  SaveDraftResponse,
  StartRequest,
  StartResponse,
  TimelineEntry,
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
  // Vite dev (5173) / preview (4173, 4174) → backend on :8000.
  if (port === "5173" || port === "4173" || port === "4174") {
    return `${protocol}//${hostname}:8000`;
  }
  return origin.replace(/\/$/, "");
}

export const API_BASE_URL = inferApiBaseUrl();
const STATIC_API_TOKEN = import.meta.env.VITE_API_TOKEN?.trim() ?? "";
const ACCESS_TOKEN_STORAGE_KEY = "scholarflow.access_token";

export class ApiError extends Error {
  readonly status: number;

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

export function storeAuthToken(token: string | null): void {
  if (typeof window === "undefined") {
    return;
  }
  if (token) {
    window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, token);
  } else {
    window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
  }
}

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const bearer = getStoredAuthToken();
  if (bearer) {
    headers.Authorization = `Bearer ${bearer}`;
  } else if (STATIC_API_TOKEN) {
    headers.Authorization = `Bearer ${STATIC_API_TOKEN}`;
  }
  return headers;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...authHeaders(),
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...(init?.headers ?? {}),
      },
    });
  } catch (err) {
    throw new ApiError(0, err instanceof Error ? err.message : "Network error");
  }

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body && typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // Non-JSON error body — keep the status text.
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

// ---- research-harness endpoints ----

export function startRun(
  projectId: string,
  payload: StartRequest,
): Promise<StartResponse> {
  return request<StartResponse>(
    `/api/research-harness/projects/${encodeURIComponent(projectId)}/start`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function getStatus(projectId: string, runId = projectId): Promise<RunStatus> {
  return request<RunStatus>(
    `/api/research-harness/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/status`,
  );
}

export function getTimeline(
  projectId: string,
  runId = projectId,
): Promise<TimelineEntry[]> {
  return request<TimelineEntry[]>(
    `/api/research-harness/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/timeline`,
  );
}

export async function getFile(
  projectId: string,
  filePath: string,
  runId = projectId,
): Promise<string> {
  const response = await fetch(
    `${API_BASE_URL}/api/research-harness/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/files/${encodeURI(filePath)}`,
    { headers: { ...authHeaders() } },
  );
  if (!response.ok) {
    throw new ApiError(response.status, `${response.status} ${response.statusText}`);
  }
  return response.text();
}

export function listProjects(): Promise<ProjectSummary[]> {
  return request<ProjectSummary[]>("/api/research-harness/projects");
}

// ---- V3 editable paper (Session 11) ----

export function savePaperDraft(
  projectId: string,
  content: string,
): Promise<SaveDraftResponse> {
  return request<SaveDraftResponse>(
    `/api/research-harness/projects/${encodeURIComponent(projectId)}/paper/draft`,
    { method: "PUT", body: JSON.stringify({ content }) },
  );
}

export function reauditPaper(projectId: string): Promise<ReauditResponse> {
  return request<ReauditResponse>(
    `/api/research-harness/projects/${encodeURIComponent(projectId)}/paper/reaudit`,
    { method: "POST" },
  );
}

// ---- Session 14: publish-bundle + deployment listing ----

export function getPublishBundle(projectId: string): Promise<PublishBundleManifest> {
  return request<PublishBundleManifest>(
    `/api/research-harness/projects/${encodeURIComponent(projectId)}/publish-bundle`,
  );
}

/**
 * Direct .zip download URL (browser-handled, not a JSON request). Append as an
 * <a href> / window.location — the browser streams the binary attachment.
 */
export function publishBundleDownloadUrl(projectId: string): string {
  return `${API_BASE_URL}/api/research-harness/projects/${encodeURIComponent(projectId)}/publish-bundle?download=1`;
}

export function getDeployments(projectId: string): Promise<DeploymentStatus> {
  return request<DeploymentStatus>(
    `/api/research-harness/projects/${encodeURIComponent(projectId)}/deployments`,
  );
}

export interface HarnessConfig {
  llm_model: string;
  llm_writer_model: string;
  llm_api_base: string;
  sandbox_backend: string;
}

export function getHarnessConfig(): Promise<HarnessConfig> {
  return request<HarnessConfig>("/api/research-harness/config");
}

// ---- auth ----

export function getAuthConfig(): Promise<AuthConfig> {
  return request<AuthConfig>("/api/auth/config");
}

export function createSession(email: string, name?: string): Promise<AuthSessionResponse> {
  return request<AuthSessionResponse>("/api/auth/session", {
    method: "POST",
    body: JSON.stringify({ email, name }),
  });
}
