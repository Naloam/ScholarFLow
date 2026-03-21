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
  AutoResearchOperatorConsole,
  AuthConfig,
  AuthUser,
  BetaSummary,
  CreateMentorAccessPayload,
  CreateMentorFeedbackPayload,
  Draft,
  EvidenceItem,
  MentorAccessEntry,
  MentorFeedbackEntry,
  Project,
  ProjectListItem,
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
  availableProjects: [] as ProjectListItem[],
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
  autoResearchConsole: null as AutoResearchOperatorConsole | null,
  analysis: null as AnalysisSummary | null,
  betaSummary: null as BetaSummary | null,
  mentorAccess: [] as MentorAccessEntry[],
  mentorFeedback: [] as MentorFeedbackEntry[],
  working: false,
  notice: "Workspace idle",
};

type WorkspaceState = {
  healthStatus: string;
  templates: TemplateMeta[];
  currentProjectId: string;
  availableProjects: ProjectListItem[];
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
  autoResearchConsole: AutoResearchOperatorConsole | null;
  analysis: AnalysisSummary | null;
  betaSummary: BetaSummary | null;
  mentorAccess: MentorAccessEntry[];
  mentorFeedback: MentorFeedbackEntry[];
  authConfig: AuthConfig | null;
  authState: AuthState;
  authUser: AuthUser | null;
  authBusy: boolean;
  authError: string;
  initializing: boolean;
  working: boolean;
  notice: string;
  bootstrap: () => Promise<void>;
  signIn: (payload: { email: string; name: string; role: "student" | "tutor" }) => Promise<void>;
  signOut: () => Promise<void>;
  createProject: (payload: {
    title: string;
    topic: string;
    templateId: string;
  }) => Promise<void>;
  loadProject: (projectId: string) => Promise<void>;
  refreshProject: () => Promise<void>;
  refreshAutoResearchConsole: (runId?: string) => Promise<void>;
  selectDraft: (version: number) => void;
  selectAutoResearchRun: (runId: string) => Promise<void>;
  setEditorContent: (content: string) => void;
  setFocusedText: (content: string) => void;
  setConnectionState: (state: ConnectionState) => void;
  applyProgressSnapshot: (snapshot: ProjectProgressSnapshot) => void;
  saveDraft: () => Promise<void>;
  generateDraft: () => Promise<void>;
  startAutoResearch: () => Promise<void>;
  resumeAutoResearch: () => Promise<void>;
  retryAutoResearch: () => Promise<void>;
  cancelAutoResearch: () => Promise<void>;
  exportAutoResearchPublish: () => Promise<void>;
  downloadAutoResearchPublish: () => Promise<void>;
  runReview: () => Promise<void>;
  exportDraft: (format: "markdown" | "latex" | "word" | "docx") => Promise<void>;
  downloadLatestExport: () => Promise<void>;
  inviteMentor: (payload: CreateMentorAccessPayload) => Promise<void>;
  submitMentorFeedback: (payload: CreateMentorFeedbackPayload) => Promise<void>;
  submitFeedback: (payload: { rating: number; category: string; comment: string }) => Promise<void>;
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
      let availableProjects: ProjectListItem[] = [];
      let notice =
        healthResult.status === "fulfilled"
          ? "Backend reachable"
          : `Backend unavailable: ${getErrorMessage(healthResult.reason)}`;
      const requiresAuth = authConfig?.auth_required ?? false;

      if (healthResult.status === "fulfilled" && (!requiresAuth || Boolean(getAuthToken()))) {
        const [templateResult, projectListResult] = await Promise.allSettled([
          api.listTemplates(),
          authState === "user" ? api.listProjects() : Promise.resolve([] as ProjectListItem[]),
        ]);
        if (templateResult.status === "fulfilled") {
          templates = templateResult.value.items;
          availableProjects =
            projectListResult.status === "fulfilled" ? projectListResult.value : [];
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
        availableProjects,
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
          role: payload.role,
        });
        setAuthToken(session.access_token);
        const [templateResult, projectListResult] = await Promise.allSettled([
          api.listTemplates(),
          api.listProjects(),
        ]);
        set({
          templates: templateResult.status === "fulfilled" ? templateResult.value.items : [],
          availableProjects:
            projectListResult.status === "fulfilled" ? projectListResult.value : [],
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
        const [projectResult, statusResult, draftsResult, evidenceResult, reviewsResult, consoleResult, analysisResult, betaResult, mentorAccessResult, mentorFeedbackResult, projectListResult] =
          await Promise.allSettled([
            api.getProject(projectId),
            api.getProjectStatus(projectId),
            api.listDrafts(projectId),
            api.listEvidence(projectId),
            api.listReviews(projectId),
            api.getAutoResearchOperatorConsole(projectId),
            api.getAnalysisSummary(projectId),
            api.getBetaSummary(projectId),
            api.listMentorAccess(projectId),
            api.listMentorFeedback(projectId),
            get().authState === "user" ? api.listProjects() : Promise.resolve([] as ProjectListItem[]),
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
          availableProjects:
            projectListResult.status === "fulfilled"
              ? projectListResult.value
              : get().availableProjects,
          project: projectResult.value,
          projectStatus: statusResult.status === "fulfilled" ? statusResult.value : null,
          drafts,
          selectedDraftVersion: selectedVersion,
          editorContent: selectedDraft?.content ?? "",
          isDirty: false,
          focusedText: "",
          evidence: evidenceResult.status === "fulfilled" ? evidenceResult.value : [],
          reviews: reviewsResult.status === "fulfilled" ? reviewsResult.value : [],
          autoResearchConsole: consoleResult.status === "fulfilled" ? consoleResult.value : null,
          analysis: analysisResult.status === "fulfilled" ? analysisResult.value : null,
          betaSummary: betaResult.status === "fulfilled" ? betaResult.value : null,
          mentorAccess: mentorAccessResult.status === "fulfilled" ? mentorAccessResult.value : [],
          mentorFeedback: mentorFeedbackResult.status === "fulfilled" ? mentorFeedbackResult.value : [],
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
        const selectedRunId = get().autoResearchConsole?.selected_run_id ?? undefined;
        const [status, drafts, evidence, reviews, autoResearchConsole, analysis, betaSummary, mentorAccess, mentorFeedback] = await Promise.all([
          api.getProjectStatus(projectId),
          api.listDrafts(projectId),
          api.listEvidence(projectId),
          api.listReviews(projectId),
          api.getAutoResearchOperatorConsole(projectId, selectedRunId),
          api.getAnalysisSummary(projectId),
          api.getBetaSummary(projectId),
          api.listMentorAccess(projectId),
          api.listMentorFeedback(projectId),
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
          autoResearchConsole,
          analysis,
          betaSummary,
          mentorAccess,
          mentorFeedback,
          notice: `Project ${projectId} refreshed`,
        });
      } catch (error) {
        handleActionError(error, "Refresh failed");
      }
    },

    async refreshAutoResearchConsole(runId) {
      const projectId = get().currentProjectId;
      if (!projectId) {
        return;
      }

      try {
        const console = await api.getAutoResearchOperatorConsole(
          projectId,
          runId ?? get().autoResearchConsole?.selected_run_id ?? undefined,
        );
        set({ autoResearchConsole: console });
      } catch (error) {
        handleActionError(error, "Auto-research console refresh failed");
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

    async selectAutoResearchRun(runId) {
      const projectId = get().currentProjectId;
      if (!projectId) {
        return;
      }

      set({ working: true, notice: `Loading auto-research run ${runId}...` });
      try {
        const console = await api.getAutoResearchOperatorConsole(projectId, runId);
        set({
          autoResearchConsole: console,
          notice: `Auto-research run ${runId} loaded`,
        });
      } catch (error) {
        handleActionError(error, "Load auto-research run failed");
      } finally {
        set({ working: false });
      }
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

    async startAutoResearch() {
      const { currentProjectId, project } = get();
      if (!currentProjectId || !project) {
        set({ notice: "Create or open a project before starting auto-research" });
        return;
      }

      set({ working: true, notice: "Starting auto-research run..." });
      try {
        const response = await api.startAutoResearch(currentProjectId, {
          topic: project.topic ?? project.title,
        });
        await sleep(400);
        await get().refreshProject();
        await get().refreshAutoResearchConsole(response.id);
        set({ notice: `Auto-research run ${response.id} queued` });
      } catch (error) {
        handleActionError(error, "Start auto-research failed");
      } finally {
        set({ working: false });
      }
    },

    async resumeAutoResearch() {
      const { currentProjectId, autoResearchConsole } = get();
      const runId = autoResearchConsole?.current_run?.run.id;
      if (!currentProjectId || !runId) {
        set({ notice: "Select an auto-research run before resume" });
        return;
      }

      set({ working: true, notice: `Resuming auto-research run ${runId}...` });
      try {
        await api.resumeAutoResearch(currentProjectId, runId);
        await sleep(400);
        await get().refreshProject();
        await get().refreshAutoResearchConsole(runId);
        set({ notice: `Resume requested for ${runId}` });
      } catch (error) {
        handleActionError(error, "Resume auto-research failed");
      } finally {
        set({ working: false });
      }
    },

    async retryAutoResearch() {
      const { currentProjectId, autoResearchConsole } = get();
      const runId = autoResearchConsole?.current_run?.run.id;
      if (!currentProjectId || !runId) {
        set({ notice: "Select an auto-research run before retry" });
        return;
      }

      set({ working: true, notice: `Retrying auto-research run ${runId}...` });
      try {
        await api.retryAutoResearch(currentProjectId, runId);
        await sleep(400);
        await get().refreshProject();
        await get().refreshAutoResearchConsole(runId);
        set({ notice: `Retry requested for ${runId}` });
      } catch (error) {
        handleActionError(error, "Retry auto-research failed");
      } finally {
        set({ working: false });
      }
    },

    async cancelAutoResearch() {
      const { currentProjectId, autoResearchConsole } = get();
      const runId = autoResearchConsole?.current_run?.run.id;
      if (!currentProjectId || !runId) {
        set({ notice: "Select an auto-research run before cancel" });
        return;
      }

      set({ working: true, notice: `Canceling auto-research run ${runId}...` });
      try {
        await api.cancelAutoResearch(currentProjectId, runId);
        await sleep(400);
        await get().refreshProject();
        await get().refreshAutoResearchConsole(runId);
        set({ notice: `Cancel requested for ${runId}` });
      } catch (error) {
        handleActionError(error, "Cancel auto-research failed");
      } finally {
        set({ working: false });
      }
    },

    async exportAutoResearchPublish() {
      const { currentProjectId, autoResearchConsole } = get();
      const runId = autoResearchConsole?.current_run?.run.id;
      if (!currentProjectId || !runId) {
        set({ notice: "Select an auto-research run before exporting publish assets" });
        return;
      }

      set({ working: true, notice: `Exporting publish package for ${runId}...` });
      try {
        const exportResult = await api.exportAutoResearchPublishPackage(currentProjectId, runId);
        await get().refreshAutoResearchConsole(runId);
        set({ notice: `Publish package ${exportResult.file_name} ready` });
      } catch (error) {
        handleActionError(error, "Publish export failed");
      } finally {
        set({ working: false });
      }
    },

    async downloadAutoResearchPublish() {
      const { currentProjectId, autoResearchConsole } = get();
      const runId = autoResearchConsole?.current_run?.run.id;
      if (!currentProjectId || !runId) {
        set({ notice: "Select an auto-research run before download" });
        return;
      }

      set({ working: true, notice: "Preparing publish bundle download..." });
      try {
        const fileName = await api.downloadAutoResearchPublishPackage(currentProjectId, runId);
        set({ notice: `Downloaded ${fileName}` });
      } catch (error) {
        handleActionError(error, "Publish download failed");
      } finally {
        set({ working: false });
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

    async downloadLatestExport() {
      const { currentProjectId, liveProgress } = get();
      const exportId = liveProgress?.latest_export_id;
      if (!currentProjectId || !exportId || liveProgress?.latest_export_status !== "done") {
        set({ notice: "No completed export is available yet" });
        return;
      }

      set({ working: true, notice: "Preparing export download..." });
      try {
        const fileName = await api.downloadExport(currentProjectId, exportId);
        set({ notice: `Downloaded ${fileName}` });
      } catch (error) {
        handleActionError(error, "Download failed");
      } finally {
        set({ working: false });
      }
    },

    async inviteMentor(payload) {
      const { currentProjectId } = get();
      if (!currentProjectId) {
        set({ notice: "Open a project before inviting a mentor" });
        return;
      }

      set({ working: true, notice: "Granting mentor access..." });
      try {
        await api.createMentorAccess(currentProjectId, payload);
        const mentorAccess = await api.listMentorAccess(currentProjectId);
        set({
          mentorAccess,
          notice: "Mentor access granted",
        });
      } catch (error) {
        handleActionError(error, "Invite mentor failed");
      } finally {
        set({ working: false });
      }
    },

    async submitMentorFeedback(payload) {
      const { currentProjectId } = get();
      if (!currentProjectId) {
        set({ notice: "Open a project before submitting mentor feedback" });
        return;
      }

      set({ working: true, notice: "Submitting mentor feedback..." });
      try {
        await api.createMentorFeedback(currentProjectId, payload);
        const mentorFeedback = await api.listMentorFeedback(currentProjectId);
        set({
          mentorFeedback,
          notice: "Mentor feedback submitted",
        });
      } catch (error) {
        handleActionError(error, "Mentor feedback failed");
      } finally {
        set({ working: false });
      }
    },

    async submitFeedback(payload) {
      const { currentProjectId } = get();
      if (!currentProjectId) {
        set({ notice: "Open a project before sending feedback" });
        return;
      }

      set({ working: true, notice: "Submitting beta feedback..." });
      try {
        await api.createFeedback(currentProjectId, payload);
        const betaSummary = await api.getBetaSummary(currentProjectId);
        set({
          betaSummary,
          notice: "Beta feedback submitted",
        });
      } catch (error) {
        handleActionError(error, "Feedback failed");
      } finally {
        set({ working: false });
      }
    },
  };
});
