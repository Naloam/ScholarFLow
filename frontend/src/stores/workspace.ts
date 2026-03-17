import { create } from "zustand";

import {
  api,
  clearAuthToken,
  getAuthToken,
  getStoredAuthToken,
  isApiError,
  setAuthToken,
} from "../api/client";
import type {
  AnalysisSummary,
  AuthConfig,
  AuthUser,
  Draft,
  EvidenceItem,
  Project,
  ProjectProgressSnapshot,
  ProjectStatus,
  ReviewReport,
  TemplateMeta,
} from "../api/types";

const sleep = (ms: number) =>
  new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms);
  });

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Unexpected error";
}

function isUnauthorizedError(error: unknown): boolean {
  return isApiError(error) && error.status === 401;
}

type ConnectionState = "disconnected" | "connecting" | "live";
type AuthState = "checking" | "anonymous" | "user" | "service";

const emptyWorkspaceSlice = {
  currentProjectId: "",
  project: null as Project | null,
  projectStatus: null as ProjectStatus | null,
  liveProgress: null as ProjectProgressSnapshot | null,
  connectionState: "disconnected" as ConnectionState,
  lastProgressSignature: "",
  drafts: [] as Draft[],
  selectedDraftVersion: null as number | null,
  editorContent: "",
  isDirty: false,
  focusedText: "",
  evidence: [] as EvidenceItem[],
  reviews: [] as ReviewReport[],
  analysis: null as AnalysisSummary | null,
  working: false,
  notice: "Workspace idle",
};

type WorkspaceState = {
  healthStatus: string;
  templates: TemplateMeta[];
  currentProjectId: string;
  project: Project | null;
  projectStatus: ProjectStatus | null;
  liveProgress: ProjectProgressSnapshot | null;
  connectionState: ConnectionState;
  lastProgressSignature: string;
  drafts: Draft[];
  selectedDraftVersion: number | null;
  editorContent: string;
  isDirty: boolean;
  focusedText: string;
  evidence: EvidenceItem[];
  reviews: ReviewReport[];
  analysis: AnalysisSummary | null;
  authConfig: AuthConfig | null;
  authState: AuthState;
  authUser: AuthUser | null;
  authBusy: boolean;
  authError: string;
  initializing: boolean;
  working: boolean;
  notice: string;
  bootstrap: () => Promise<void>;
  signIn: (payload: { email: string; name: string }) => Promise<void>;
  signOut: () => Promise<void>;
  createProject: (payload: {
    title: string;
    topic: string;
    templateId: string;
  }) => Promise<void>;
  loadProject: (projectId: string) => Promise<void>;
  refreshProject: () => Promise<void>;
  selectDraft: (version: number) => void;
  setEditorContent: (content: string) => void;
  setFocusedText: (content: string) => void;
  setConnectionState: (state: ConnectionState) => void;
  applyProgressSnapshot: (snapshot: ProjectProgressSnapshot) => void;
  saveDraft: () => Promise<void>;
  generateDraft: () => Promise<void>;
  runReview: () => Promise<void>;
  exportDraft: (format: "markdown" | "latex" | "word" | "docx") => Promise<void>;
};

export const useWorkspaceStore = create<WorkspaceState>((set, get) => {
  const expireSession = (message: string) => {
    clearAuthToken();
    const nextAuthState: AuthState = getAuthToken() ? "service" : "anonymous";
    set((state) => ({
      ...emptyWorkspaceSlice,
      templates:
        state.authConfig?.auth_required && nextAuthState === "anonymous"
          ? []
          : state.templates,
      authUser: null,
      authState: nextAuthState,
      authBusy: false,
      authError: message,
      notice: message,
    }));
  };

  const handleActionError = (error: unknown, prefix: string) => {
    if (isUnauthorizedError(error) && getStoredAuthToken()) {
      expireSession("Session expired. Sign in again.");
      return;
    }
    set({ notice: `${prefix}: ${getErrorMessage(error)}` });
  };

  return {
    healthStatus: "checking",
    templates: [],
    authConfig: null,
    authState: "checking",
    authUser: null,
    authBusy: false,
    authError: "",
    initializing: false,
    ...emptyWorkspaceSlice,

    async bootstrap() {
      set({
        initializing: true,
        authState: "checking",
        authError: "",
        notice: "Loading workspace...",
      });

      const [healthResult, authConfigResult] = await Promise.allSettled([
        api.getHealth(),
        api.getAuthConfig(),
      ]);

      const authConfig = authConfigResult.status === "fulfilled" ? authConfigResult.value : null;
      let authState: AuthState = getAuthToken() ? "service" : "anonymous";
      let authUser: AuthUser | null = null;
      let authError = "";

      if (getStoredAuthToken()) {
        const meResult = await Promise.allSettled([api.getCurrentUser()]);
        const currentUserResult = meResult[0];
        if (currentUserResult.status === "fulfilled") {
          authState = "user";
          authUser = currentUserResult.value;
        } else if (isUnauthorizedError(currentUserResult.reason)) {
          clearAuthToken();
          authState = getAuthToken() ? "service" : "anonymous";
          authError = "Session expired. Sign in again.";
        } else {
          clearAuthToken();
          authState = getAuthToken() ? "service" : "anonymous";
          authError = `Could not restore session: ${getErrorMessage(currentUserResult.reason)}`;
        }
      }

      let templates: TemplateMeta[] = [];
      let notice =
        healthResult.status === "fulfilled"
          ? "Backend reachable"
          : `Backend unavailable: ${getErrorMessage(healthResult.reason)}`;
      const requiresAuth = authConfig?.auth_required ?? false;

      if (healthResult.status === "fulfilled" && (!requiresAuth || Boolean(getAuthToken()))) {
        const templatesResult = await Promise.allSettled([api.listTemplates()]);
        const templateResult = templatesResult[0];
        if (templateResult.status === "fulfilled") {
          templates = templateResult.value.items;
          if (authState === "user" && authUser) {
            notice = `Signed in as ${authUser.email}`;
          } else if (authState === "service") {
            notice = "Workspace ready with service token";
          }
        } else {
          if (isUnauthorizedError(templateResult.reason) && getStoredAuthToken()) {
            clearAuthToken();
            authState = getAuthToken() ? "service" : "anonymous";
            authUser = null;
            authError = "Session expired. Sign in again.";
          }
          notice = `Workspace bootstrap failed: ${getErrorMessage(templateResult.reason)}`;
        }
      } else if (requiresAuth) {
        notice = authConfig?.session_enabled
          ? "Sign in to access the workspace"
          : "Workspace access is locked until an API token is configured";
      }

      set({
        initializing: false,
        healthStatus: healthResult.status === "fulfilled" ? healthResult.value.status : "offline",
        templates,
        authConfig,
        authState,
        authUser,
        authError,
        notice,
      });
    },

    async signIn(payload) {
      const email = payload.email.trim();
      const name = payload.name.trim();
      if (!email) {
        set({ authError: "Email is required" });
        return;
      }
      if (!get().authConfig?.session_enabled) {
        set({ authError: "Session login is not enabled on this server" });
        return;
      }

      set({ authBusy: true, authError: "", notice: "Signing in..." });
      try {
        const session = await api.createSession({
          email,
          name: name || undefined,
        });
        setAuthToken(session.access_token);
        const templatesResult = await Promise.allSettled([api.listTemplates()]);
        const templateResult = templatesResult[0];
        set({
          templates: templateResult.status === "fulfilled" ? templateResult.value.items : [],
          authState: "user",
          authUser: session.user,
          authBusy: false,
          authError: "",
          notice:
            templateResult.status === "fulfilled"
              ? `Signed in as ${session.user.email}`
              : `Signed in as ${session.user.email}, but template bootstrap failed`,
        });
        if (templateResult.status !== "fulfilled") {
          set({ authError: getErrorMessage(templateResult.reason) });
        }
      } catch (error) {
        clearAuthToken();
        set({
          authBusy: false,
          authUser: null,
          authState: getAuthToken() ? "service" : "anonymous",
          authError: getErrorMessage(error),
          notice: `Sign in failed: ${getErrorMessage(error)}`,
        });
      }
    },

    async signOut() {
      set({
        ...emptyWorkspaceSlice,
        authBusy: true,
        authUser: null,
        authError: "",
        notice: "Signing out...",
      });
      clearAuthToken();
      await get().bootstrap();
      const nextNotice =
        get().authState === "service"
          ? "User session cleared. Service token remains active"
          : get().authConfig?.auth_required
            ? "Signed out. Sign in to continue."
            : "Signed out";
      set({
        authBusy: false,
        notice: nextNotice,
      });
    },

    async createProject(payload) {
      set({ working: true, notice: "Creating project..." });
      try {
        const response = await api.createProject({
          title: payload.title,
          topic: payload.topic,
          template_id: payload.templateId || undefined,
          status: "init",
        });
        await get().loadProject(response.id);
        set({ notice: `Project ${response.id} ready` });
      } catch (error) {
        handleActionError(error, "Create project failed");
      } finally {
        set({ working: false });
      }
    },

    async loadProject(projectId) {
      set({ working: true, notice: "Loading project..." });
      try {
        const [projectResult, statusResult, draftsResult, evidenceResult, reviewsResult, analysisResult] =
          await Promise.allSettled([
            api.getProject(projectId),
            api.getProjectStatus(projectId),
            api.listDrafts(projectId),
            api.listEvidence(projectId),
            api.listReviews(projectId),
            api.getAnalysisSummary(projectId),
          ]);

        if (projectResult.status !== "fulfilled") {
          throw projectResult.reason;
        }

        const drafts = draftsResult.status === "fulfilled" ? draftsResult.value : [];
        const selectedVersion = drafts.length > 0 ? drafts[0].version : null;
        const selectedDraft =
          selectedVersion !== null
            ? drafts.find((draft) => draft.version === selectedVersion) ?? null
            : null;

        set({
          currentProjectId: projectId,
          project: projectResult.value,
          projectStatus: statusResult.status === "fulfilled" ? statusResult.value : null,
          drafts,
          selectedDraftVersion: selectedVersion,
          editorContent: selectedDraft?.content ?? "",
          isDirty: false,
          focusedText: "",
          evidence: evidenceResult.status === "fulfilled" ? evidenceResult.value : [],
          reviews: reviewsResult.status === "fulfilled" ? reviewsResult.value : [],
          analysis: analysisResult.status === "fulfilled" ? analysisResult.value : null,
          notice: `Project ${projectId} loaded`,
        });
      } catch (error) {
        handleActionError(error, "Load project failed");
      } finally {
        set({ working: false });
      }
    },

    async refreshProject() {
      const projectId = get().currentProjectId;
      if (!projectId) {
        return;
      }

      try {
        const [status, drafts, evidence, reviews, analysis] = await Promise.all([
          api.getProjectStatus(projectId),
          api.listDrafts(projectId),
          api.listEvidence(projectId),
          api.listReviews(projectId),
          api.getAnalysisSummary(projectId),
        ]);

        const selectedDraftVersion = get().selectedDraftVersion;
        const fallbackVersion =
          selectedDraftVersion && drafts.some((draft) => draft.version === selectedDraftVersion)
            ? selectedDraftVersion
            : drafts[0]?.version ?? null;
        const selectedDraft =
          fallbackVersion !== null
            ? drafts.find((draft) => draft.version === fallbackVersion) ?? null
            : null;
        const preserveDirty =
          get().isDirty &&
          fallbackVersion !== null &&
          fallbackVersion === selectedDraftVersion;

        set({
          projectStatus: status,
          drafts,
          selectedDraftVersion: fallbackVersion,
          editorContent: preserveDirty ? get().editorContent : selectedDraft?.content ?? "",
          evidence,
          reviews,
          analysis,
          notice: `Project ${projectId} refreshed`,
        });
      } catch (error) {
        handleActionError(error, "Refresh failed");
      }
    },

    selectDraft(version) {
      const draft = get().drafts.find((item) => item.version === version);
      if (!draft) {
        return;
      }
      set({
        selectedDraftVersion: version,
        editorContent: draft.content,
        isDirty: false,
        focusedText: "",
        notice: `Draft v${version} selected`,
      });
    },

    setEditorContent(content) {
      set((state) => ({
        editorContent: content,
        isDirty: content !== state.editorContent ? true : state.isDirty,
      }));
    },

    setFocusedText(content) {
      set({ focusedText: content });
    },

    setConnectionState(state) {
      set({ connectionState: state });
    },

    applyProgressSnapshot(snapshot) {
      const current = get();
      const latestLocalDraftVersion = current.drafts[0]?.version ?? null;
      const liveProgress = current.liveProgress;
      const shouldRefresh =
        snapshot.signature !== current.lastProgressSignature &&
        (
          snapshot.draft_count !== current.drafts.length ||
          snapshot.evidence_count !== current.evidence.length ||
          snapshot.review_count !== current.reviews.length ||
          snapshot.latest_draft_version !== latestLocalDraftVersion ||
          snapshot.latest_review_status !== liveProgress?.latest_review_status ||
          snapshot.latest_export_status !== liveProgress?.latest_export_status
        );

      set({
        liveProgress: snapshot,
        lastProgressSignature: snapshot.signature,
        projectStatus: {
          status: snapshot.status,
          phase: snapshot.phase,
          progress: snapshot.progress,
          message: current.projectStatus?.message ?? null,
        },
        notice:
          snapshot.latest_export_status === "done"
            ? "Latest export finished"
            : current.notice,
      });

      if (shouldRefresh) {
        void get().refreshProject();
      }
    },

    async saveDraft() {
      const { currentProjectId, selectedDraftVersion, editorContent } = get();
      if (!currentProjectId || selectedDraftVersion === null) {
        set({ notice: "No draft selected" });
        return;
      }

      set({ working: true, notice: `Saving draft v${selectedDraftVersion}...` });
      try {
        const updated = await api.updateDraft(currentProjectId, selectedDraftVersion, {
          content: editorContent,
        });
        const drafts = get().drafts.map((draft) =>
          draft.version === selectedDraftVersion ? updated : draft,
        );
        set({
          drafts,
          editorContent: updated.content,
          isDirty: false,
          notice: `Draft v${selectedDraftVersion} saved`,
        });
      } catch (error) {
        handleActionError(error, "Save failed");
      } finally {
        set({ working: false });
      }
    },

    async generateDraft() {
      const { currentProjectId, project } = get();
      if (!currentProjectId || !project) {
        set({ notice: "Create or open a project first" });
        return;
      }

      set({ working: true, notice: "Generating draft..." });
      try {
        await api.generateDraft(currentProjectId, {
          topic: project.topic ?? project.title,
          template_id: project.template_id ?? undefined,
          language: "zh",
        });
        await sleep(600);
        await get().refreshProject();
        set({ notice: "Draft generation requested" });
      } catch (error) {
        handleActionError(error, "Generate draft failed");
      } finally {
        set({ working: false });
      }
    },

    async runReview() {
      const { currentProjectId, selectedDraftVersion, drafts } = get();
      const draftVersion = selectedDraftVersion ?? drafts[0]?.version;
      if (!currentProjectId || draftVersion === undefined) {
        set({ notice: "Generate a draft before review" });
        return;
      }

      set({ working: true, notice: `Running review for draft v${draftVersion}...` });
      try {
        await api.runReview(currentProjectId, draftVersion);
        await sleep(800);
        await get().refreshProject();
        set({ notice: "Review queued" });
      } catch (error) {
        handleActionError(error, "Run review failed");
      } finally {
        set({ working: false });
      }
    },

    async exportDraft(format) {
      const { currentProjectId } = get();
      if (!currentProjectId) {
        set({ notice: "Open a project before export" });
        return;
      }

      set({ working: true, notice: `Exporting ${format}...` });
      try {
        await api.exportDraft(currentProjectId, format);
        set({ notice: `${format} export queued` });
      } catch (error) {
        handleActionError(error, "Export failed");
      } finally {
        set({ working: false });
      }
    },
  };
});
