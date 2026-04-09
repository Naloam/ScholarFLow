import { create } from "zustand";

import i18next from "i18next";

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
  AutoResearchBridgeImportRequest,
  AutoResearchDeployment,
  AutoResearchDeploymentFilters,
  AutoResearchDeploymentList,
  AutoResearchOperatorConsole,
  AutoResearchOperatorConsoleFilters,
  AutoResearchPublishExportRequest,
  AutoResearchPublicationManifest,
  AutoResearchRunRequest,
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

function normalizeConsoleFilters(
  filters: AutoResearchOperatorConsoleFilters,
): AutoResearchOperatorConsoleFilters {
  const search = filters.search?.trim();
  return {
    search: search ? search : null,
    status: filters.status ?? null,
    publish_status: filters.publish_status ?? null,
    review_risk: filters.review_risk ?? null,
    novelty_status: filters.novelty_status ?? null,
    budget_status: filters.budget_status ?? null,
    queue_priority: filters.queue_priority ?? null,
  };
}

function normalizeDeploymentFilters(
  filters: AutoResearchDeploymentFilters,
): AutoResearchDeploymentFilters {
  const search = filters.search?.trim();
  return {
    search: search ? search : null,
    final_publish_ready: filters.final_publish_ready ?? null,
    bundle_kind: filters.bundle_kind ?? null,
    task_family: filters.task_family ?? null,
  };
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
  autoResearchConsoleFilters: {} as AutoResearchOperatorConsoleFilters,
  autoResearchDeploymentList: null as AutoResearchDeploymentList | null,
  selectedAutoResearchDeploymentId: "",
  autoResearchDeploymentFilters: {} as AutoResearchDeploymentFilters,
  autoResearchDeployment: null as AutoResearchDeployment | null,
  autoResearchPublicationManifest:
    null as AutoResearchPublicationManifest | null,
  analysis: null as AnalysisSummary | null,
  betaSummary: null as BetaSummary | null,
  mentorAccess: [] as MentorAccessEntry[],
  mentorFeedback: [] as MentorFeedbackEntry[],
  working: false,
  notice: i18next.t("notices.workspaceIdle"),
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
  autoResearchConsoleFilters: AutoResearchOperatorConsoleFilters;
  autoResearchDeploymentList: AutoResearchDeploymentList | null;
  selectedAutoResearchDeploymentId: string;
  autoResearchDeploymentFilters: AutoResearchDeploymentFilters;
  autoResearchDeployment: AutoResearchDeployment | null;
  autoResearchPublicationManifest: AutoResearchPublicationManifest | null;
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
  signIn: (payload: {
    email: string;
    name: string;
    role: "student" | "tutor";
  }) => Promise<void>;
  signOut: () => Promise<void>;
  createProject: (payload: {
    title: string;
    topic: string;
    templateId: string;
  }) => Promise<void>;
  loadProject: (projectId: string) => Promise<void>;
  refreshProject: () => Promise<void>;
  refreshAutoResearchConsole: (runId?: string) => Promise<void>;
  refreshAutoResearchDeployments: (deploymentId?: string) => Promise<void>;
  applyAutoResearchConsoleFilters: (
    filters: AutoResearchOperatorConsoleFilters,
  ) => Promise<void>;
  clearAutoResearchConsoleFilters: () => Promise<void>;
  applyAutoResearchDeploymentFilters: (
    filters: AutoResearchDeploymentFilters,
  ) => Promise<void>;
  clearAutoResearchDeploymentFilters: () => Promise<void>;
  updateAutoResearchRunControls: (payload: {
    max_rounds?: number | null;
    candidate_execution_limit?: number | null;
    queue_priority?: "low" | "normal" | "high" | null;
  }) => Promise<void>;
  selectDraft: (version: number) => void;
  selectAutoResearchRun: (runId: string) => Promise<void>;
  selectAutoResearchDeployment: (deploymentId: string) => Promise<void>;
  openAutoResearchPublication: (
    projectId: string,
    runId: string,
  ) => Promise<void>;
  refreshAutoResearchReviewLoop: () => Promise<void>;
  refreshAutoResearchBridge: () => Promise<void>;
  applyAutoResearchReviewActions: () => Promise<void>;
  setEditorContent: (content: string) => void;
  setFocusedText: (content: string) => void;
  setConnectionState: (state: ConnectionState) => void;
  applyProgressSnapshot: (snapshot: ProjectProgressSnapshot) => void;
  saveDraft: () => Promise<void>;
  generateDraft: () => Promise<void>;
  startAutoResearch: (
    payload?: Partial<AutoResearchRunRequest>,
  ) => Promise<void>;
  resumeAutoResearch: () => Promise<void>;
  retryAutoResearch: () => Promise<void>;
  cancelAutoResearch: () => Promise<void>;
  rebuildAutoResearchPaper: () => Promise<void>;
  importAutoResearchBridgeResult: (
    payload: AutoResearchBridgeImportRequest,
  ) => Promise<void>;
  exportAutoResearchPublish: (
    payload?: AutoResearchPublishExportRequest,
  ) => Promise<void>;
  downloadAutoResearchPublish: () => Promise<void>;
  downloadAutoResearchPaper: () => Promise<void>;
  downloadAutoResearchCompiledPaper: () => Promise<void>;
  downloadAutoResearchCodePackage: () => Promise<void>;
  runReview: () => Promise<void>;
  exportDraft: (
    format: "markdown" | "latex" | "word" | "docx",
  ) => Promise<void>;
  downloadLatestExport: () => Promise<void>;
  inviteMentor: (payload: CreateMentorAccessPayload) => Promise<void>;
  submitMentorFeedback: (payload: CreateMentorFeedbackPayload) => Promise<void>;
  submitFeedback: (payload: {
    rating: number;
    category: string;
    comment: string;
  }) => Promise<void>;
};

export const useWorkspaceStore = create<WorkspaceState>((set, get) => {
  const workspaceRequiresToken = (authConfig: AuthConfig | null): boolean =>
    Boolean(authConfig?.api_protected);
  const resolveSelectedRunId = (
    consoleState: AutoResearchOperatorConsole | null,
  ): string | null =>
    consoleState?.selected_run_id ?? consoleState?.current_run?.run.id ?? null;
  const shouldLoadPublicationManifest = (
    consoleState: AutoResearchOperatorConsole | null,
  ): boolean => {
    const publish = consoleState?.current_run?.publish;
    return Boolean(
      publish && publish.final_publish_ready && publish.archive_ready,
    );
  };
  const loadPublicationManifest = async (
    projectId: string,
    consoleState: AutoResearchOperatorConsole | null,
  ): Promise<AutoResearchPublicationManifest | null> => {
    const runId = resolveSelectedRunId(consoleState);
    if (!shouldLoadPublicationManifest(consoleState) || !runId) {
      return null;
    }
    if (!runId) {
      return null;
    }
    try {
      return await api.getAutoResearchPublicationManifest(projectId, runId);
    } catch (error) {
      if (isApiError(error) && error.status === 404) {
        return null;
      }
      console.error(`Could not load publication manifest for ${runId}`, error);
      return null;
    }
  };
  const loadWorkspaceBootstrapData = async (): Promise<
    [
      PromiseSettledResult<{ items: TemplateMeta[] }>,
      PromiseSettledResult<ProjectListItem[]>,
      PromiseSettledResult<AutoResearchDeploymentList>,
    ]
  > => {
    let lastResults:
      | [
          PromiseSettledResult<{ items: TemplateMeta[] }>,
          PromiseSettledResult<ProjectListItem[]>,
          PromiseSettledResult<AutoResearchDeploymentList>,
        ]
      | null = null;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      const results = await Promise.allSettled([
        api.listTemplates(),
        api.listProjects(),
        api.listAutoResearchDeployments(),
      ]);
      lastResults = results;
      const hasRetryableFailure = results.some(
        (result) =>
          result.status === "rejected" && !isUnauthorizedError(result.reason),
      );
      if (!hasRetryableFailure || attempt === 2) {
        return results;
      }
      await sleep(500 * (attempt + 1));
    }
    return lastResults as [
      PromiseSettledResult<{ items: TemplateMeta[] }>,
      PromiseSettledResult<ProjectListItem[]>,
      PromiseSettledResult<AutoResearchDeploymentList>,
    ];
  };

  const expireSession = (message: string) => {
    clearAuthToken();
    const nextAuthState: AuthState = getAuthToken() ? "service" : "anonymous";
    set((state) => ({
      ...emptyWorkspaceSlice,
      templates:
        workspaceRequiresToken(state.authConfig) &&
        nextAuthState === "anonymous"
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
      expireSession(i18next.t("notices.sessionExpired"));
      return;
    }
    set({
      notice: i18next.t("notices.actionFailed", {
        prefix,
        error: getErrorMessage(error),
      }),
    });
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
        notice: i18next.t("notices.loadingWorkspace"),
      });

      const [healthResult, authConfigResult] = await Promise.allSettled([
        api.getHealth(),
        api.getAuthConfig(),
      ]);

      const authConfig =
        authConfigResult.status === "fulfilled" ? authConfigResult.value : null;
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
          authError = i18next.t("notices.sessionExpired");
        } else {
          clearAuthToken();
          authState = getAuthToken() ? "service" : "anonymous";
          authError = i18next.t("notices.couldNotRestoreSession", {
            error: getErrorMessage(currentUserResult.reason),
          });
        }
      }

      let templates: TemplateMeta[] = [];
      let availableProjects: ProjectListItem[] = [];
      let autoResearchDeploymentList: AutoResearchDeploymentList | null = null;
      let notice =
        healthResult.status === "fulfilled"
          ? i18next.t("notices.backendReachable")
          : i18next.t("notices.backendUnavailable", {
              error: getErrorMessage(healthResult.reason),
            });
      const requiresAuth = workspaceRequiresToken(authConfig);

      if (
        healthResult.status === "fulfilled" &&
        (!requiresAuth || Boolean(getAuthToken()))
      ) {
        const [templateResult, projectListResult, deploymentListResult] =
          await loadWorkspaceBootstrapData();
        if (templateResult.status === "fulfilled") {
          templates = templateResult.value.items;
          availableProjects =
            projectListResult.status === "fulfilled"
              ? projectListResult.value
              : [];
          autoResearchDeploymentList =
            deploymentListResult.status === "fulfilled"
              ? deploymentListResult.value
              : null;
          if (authState === "user" && authUser) {
            notice = i18next.t("notices.signedInAs", { email: authUser.email });
          } else if (authState === "service") {
            notice = i18next.t("notices.workspaceReadyService");
          }
        } else {
          if (
            isUnauthorizedError(templateResult.reason) &&
            getStoredAuthToken()
          ) {
            clearAuthToken();
            authState = getAuthToken() ? "service" : "anonymous";
            authUser = null;
            authError = i18next.t("notices.sessionExpired");
          }
          notice = i18next.t("notices.workspaceBootstrapFailed", {
            error: getErrorMessage(templateResult.reason),
          });
        }
      } else if (requiresAuth) {
        notice = authConfig?.session_enabled
          ? i18next.t("notices.signInToAccess")
          : i18next.t("notices.workspaceLocked");
      }

      set({
        initializing: false,
        healthStatus:
          healthResult.status === "fulfilled"
            ? healthResult.value.status
            : "offline",
        templates,
        authConfig,
        authState,
        authUser,
        availableProjects,
        autoResearchDeploymentList,
        selectedAutoResearchDeploymentId:
          autoResearchDeploymentList?.deployments[0]?.deployment_id ?? "",
        autoResearchDeploymentFilters: {},
        autoResearchDeployment: null,
        authError,
        notice,
      });
    },

    async signIn(payload) {
      const email = payload.email.trim();
      const name = payload.name.trim();
      if (!email) {
        set({ authError: i18next.t("notices.emailRequired") });
        return;
      }
      if (!get().authConfig?.session_enabled) {
        set({
          authError: i18next.t("notices.sessionNotEnabled"),
        });
        return;
      }

      set({
        authBusy: true,
        authError: "",
        notice: i18next.t("notices.signingIn"),
      });
      try {
        const session = await api.createSession({
          email,
          name: name || undefined,
          role: payload.role,
        });
        setAuthToken(session.access_token);
        const [templateResult, projectListResult, deploymentListResult] =
          await loadWorkspaceBootstrapData();
        set({
          templates:
            templateResult.status === "fulfilled"
              ? templateResult.value.items
              : [],
          availableProjects:
            projectListResult.status === "fulfilled"
              ? projectListResult.value
              : [],
          autoResearchDeploymentList:
            deploymentListResult.status === "fulfilled"
              ? deploymentListResult.value
              : null,
          selectedAutoResearchDeploymentId:
            deploymentListResult.status === "fulfilled"
              ? (deploymentListResult.value.deployments[0]?.deployment_id ?? "")
              : "",
          autoResearchDeployment: null,
          authState: "user",
          authUser: session.user,
          authBusy: false,
          authError: "",
          notice:
            templateResult.status === "fulfilled"
              ? i18next.t("notices.signedInAs", { email: session.user.email })
              : `${i18next.t("notices.signedInAs", { email: session.user.email })} (template bootstrap failed)`,
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
          notice: i18next.t("notices.signInFailed", {
            error: getErrorMessage(error),
          }),
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
          : workspaceRequiresToken(get().authConfig)
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
        set((state) => {
          const accessMode =
            state.authState === "user" || state.authState === "service"
              ? "owner"
              : "anonymous";
          const optimisticProject: Project = {
            id: response.id,
            title: payload.title,
            topic: payload.topic,
            template_id: payload.templateId || null,
            status: "init",
          };
          const optimisticProjectList: ProjectListItem = {
            ...optimisticProject,
            access_mode: accessMode,
          };
          const availableProjects = [
            optimisticProjectList,
            ...state.availableProjects.filter(
              (item) => item.id !== response.id,
            ),
          ];
          return {
            currentProjectId: response.id,
            project: optimisticProject,
            availableProjects,
            notice: `Project ${response.id} created. Loading details...`,
          };
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
        const [
          projectResult,
          statusResult,
          draftsResult,
          evidenceResult,
          reviewsResult,
          consoleResult,
          deploymentListResult,
          deploymentDetailResult,
          analysisResult,
          betaResult,
          mentorAccessResult,
          mentorFeedbackResult,
          projectListResult,
        ] = await Promise.allSettled([
          api.getProject(projectId),
          api.getProjectStatus(projectId),
          api.listDrafts(projectId),
          api.listEvidence(projectId),
          api.listReviews(projectId),
          api.getAutoResearchOperatorConsole(projectId, {}),
          api.listAutoResearchDeployments(),
          get().selectedAutoResearchDeploymentId
            ? api.getAutoResearchDeployment(
                get().selectedAutoResearchDeploymentId,
                normalizeDeploymentFilters(get().autoResearchDeploymentFilters),
              )
            : Promise.resolve(null),
          api.getAnalysisSummary(projectId),
          api.getBetaSummary(projectId),
          api.listMentorAccess(projectId),
          api.listMentorFeedback(projectId),
          !workspaceRequiresToken(get().authConfig) || Boolean(getAuthToken())
            ? api.listProjects()
            : Promise.resolve([] as ProjectListItem[]),
        ]);

        if (projectResult.status !== "fulfilled") {
          throw projectResult.reason;
        }

        const drafts =
          draftsResult.status === "fulfilled" ? draftsResult.value : [];
        const autoResearchConsole =
          consoleResult.status === "fulfilled" ? consoleResult.value : null;
        const autoResearchPublicationManifest = await loadPublicationManifest(
          projectId,
          autoResearchConsole,
        );
        const selectedVersion = drafts.length > 0 ? drafts[0].version : null;
        const selectedDraft =
          selectedVersion !== null
            ? (drafts.find((draft) => draft.version === selectedVersion) ??
              null)
            : null;

        set({
          currentProjectId: projectId,
          availableProjects:
            projectListResult.status === "fulfilled"
              ? projectListResult.value
              : get().availableProjects,
          project: projectResult.value,
          projectStatus:
            statusResult.status === "fulfilled" ? statusResult.value : null,
          drafts,
          selectedDraftVersion: selectedVersion,
          editorContent: selectedDraft?.content ?? "",
          isDirty: false,
          focusedText: "",
          evidence:
            evidenceResult.status === "fulfilled" ? evidenceResult.value : [],
          reviews:
            reviewsResult.status === "fulfilled" ? reviewsResult.value : [],
          autoResearchConsole,
          autoResearchConsoleFilters: autoResearchConsole?.filters ?? {},
          autoResearchDeploymentList:
            deploymentListResult.status === "fulfilled"
              ? deploymentListResult.value
              : null,
          selectedAutoResearchDeploymentId:
            deploymentDetailResult.status === "fulfilled" &&
            deploymentDetailResult.value
              ? deploymentDetailResult.value.deployment_id
              : deploymentListResult.status === "fulfilled"
                ? (deploymentListResult.value.deployments[0]?.deployment_id ??
                  "")
                : "",
          autoResearchDeploymentFilters:
            deploymentDetailResult.status === "fulfilled" &&
            deploymentDetailResult.value
              ? deploymentDetailResult.value.filters
              : normalizeDeploymentFilters(get().autoResearchDeploymentFilters),
          autoResearchDeployment:
            deploymentDetailResult.status === "fulfilled"
              ? deploymentDetailResult.value
              : null,
          autoResearchPublicationManifest,
          analysis:
            analysisResult.status === "fulfilled" ? analysisResult.value : null,
          betaSummary:
            betaResult.status === "fulfilled" ? betaResult.value : null,
          mentorAccess:
            mentorAccessResult.status === "fulfilled"
              ? mentorAccessResult.value
              : [],
          mentorFeedback:
            mentorFeedbackResult.status === "fulfilled"
              ? mentorFeedbackResult.value
              : [],
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
        const selectedRunId =
          get().autoResearchConsole?.selected_run_id ?? undefined;
        const filters = normalizeConsoleFilters(
          get().autoResearchConsoleFilters,
        );
        const deploymentFilters = normalizeDeploymentFilters(
          get().autoResearchDeploymentFilters,
        );
        const [
          status,
          drafts,
          evidence,
          reviews,
          autoResearchConsole,
          autoResearchDeploymentList,
          autoResearchDeployment,
          analysis,
          betaSummary,
          mentorAccess,
          mentorFeedback,
        ] = await Promise.all([
          api.getProjectStatus(projectId),
          api.listDrafts(projectId),
          api.listEvidence(projectId),
          api.listReviews(projectId),
          api.getAutoResearchOperatorConsole(projectId, {
            runId: selectedRunId,
            ...filters,
          }),
          api.listAutoResearchDeployments(),
          get().selectedAutoResearchDeploymentId
            ? api
                .getAutoResearchDeployment(
                  get().selectedAutoResearchDeploymentId,
                  deploymentFilters,
                )
                .catch(() => null)
            : Promise.resolve(null),
          api.getAnalysisSummary(projectId),
          api.getBetaSummary(projectId),
          api.listMentorAccess(projectId),
          api.listMentorFeedback(projectId),
        ]);

        const selectedDraftVersion = get().selectedDraftVersion;
        const fallbackVersion =
          selectedDraftVersion &&
          drafts.some((draft) => draft.version === selectedDraftVersion)
            ? selectedDraftVersion
            : (drafts[0]?.version ?? null);
        const selectedDraft =
          fallbackVersion !== null
            ? (drafts.find((draft) => draft.version === fallbackVersion) ??
              null)
            : null;
        const preserveDirty =
          get().isDirty &&
          fallbackVersion !== null &&
          fallbackVersion === selectedDraftVersion;
        const autoResearchPublicationManifest = await loadPublicationManifest(
          projectId,
          autoResearchConsole,
        );

        set({
          projectStatus: status,
          drafts,
          selectedDraftVersion: fallbackVersion,
          editorContent: preserveDirty
            ? get().editorContent
            : (selectedDraft?.content ?? ""),
          evidence,
          reviews,
          autoResearchConsole,
          autoResearchConsoleFilters: autoResearchConsole.filters,
          autoResearchDeploymentList,
          selectedAutoResearchDeploymentId:
            autoResearchDeployment?.deployment_id ??
            autoResearchDeploymentList.deployments[0]?.deployment_id ??
            "",
          autoResearchDeploymentFilters:
            autoResearchDeployment?.filters ?? deploymentFilters,
          autoResearchDeployment,
          autoResearchPublicationManifest,
          analysis,
          betaSummary,
          mentorAccess,
          mentorFeedback,
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
        const filters = normalizeConsoleFilters(
          get().autoResearchConsoleFilters,
        );
        const console = await api.getAutoResearchOperatorConsole(projectId, {
          runId:
            runId ?? get().autoResearchConsole?.selected_run_id ?? undefined,
          ...filters,
        });
        const autoResearchPublicationManifest = await loadPublicationManifest(
          projectId,
          console,
        );
        set({
          autoResearchConsole: console,
          autoResearchConsoleFilters: console.filters,
          autoResearchPublicationManifest,
        });
      } catch (error) {
        handleActionError(error, "Auto-research console refresh failed");
      }
    },

    async refreshAutoResearchDeployments(deploymentId) {
      try {
        const filters = normalizeDeploymentFilters(
          get().autoResearchDeploymentFilters,
        );
        const deploymentList = await api.listAutoResearchDeployments();
        const nextDeploymentId =
          deploymentId ??
          get().selectedAutoResearchDeploymentId ??
          deploymentList.deployments[0]?.deployment_id ??
          "";
        const deployment = nextDeploymentId
          ? await api
              .getAutoResearchDeployment(nextDeploymentId, filters)
              .catch(() => null)
          : null;
        set({
          autoResearchDeploymentList: deploymentList,
          selectedAutoResearchDeploymentId:
            deployment?.deployment_id ?? nextDeploymentId,
          autoResearchDeploymentFilters: deployment?.filters ?? filters,
          autoResearchDeployment: deployment,
        });
      } catch (error) {
        handleActionError(error, "Auto-research deployment refresh failed");
      }
    },

    async applyAutoResearchConsoleFilters(filters) {
      const projectId = get().currentProjectId;
      if (!projectId) {
        return;
      }

      const nextFilters = normalizeConsoleFilters(filters);
      set({
        working: true,
        notice: "Applying auto-research console filters...",
      });
      try {
        const console = await api.getAutoResearchOperatorConsole(projectId, {
          runId: get().autoResearchConsole?.selected_run_id ?? undefined,
          ...nextFilters,
        });
        const autoResearchPublicationManifest = await loadPublicationManifest(
          projectId,
          console,
        );
        set({
          autoResearchConsole: console,
          autoResearchConsoleFilters: console.filters,
          autoResearchPublicationManifest,
          notice: `Auto-research console filtered to ${console.filtered_run_count}/${console.run_count} runs`,
        });
      } catch (error) {
        handleActionError(error, "Apply auto-research console filters failed");
      } finally {
        set({ working: false });
      }
    },

    async clearAutoResearchConsoleFilters() {
      return get().applyAutoResearchConsoleFilters({});
    },

    async applyAutoResearchDeploymentFilters(filters) {
      const nextFilters = normalizeDeploymentFilters(filters);
      set({ working: true, notice: "Applying deployment filters..." });
      try {
        const deploymentList = await api.listAutoResearchDeployments();
        const deploymentId =
          get().selectedAutoResearchDeploymentId ||
          deploymentList.deployments[0]?.deployment_id ||
          "";
        const deployment = deploymentId
          ? await api
              .getAutoResearchDeployment(deploymentId, nextFilters)
              .catch(() => null)
          : null;
        set({
          autoResearchDeploymentList: deploymentList,
          selectedAutoResearchDeploymentId:
            deployment?.deployment_id ?? deploymentId,
          autoResearchDeploymentFilters: deployment?.filters ?? nextFilters,
          autoResearchDeployment: deployment,
          notice: deployment
            ? `Deployment filtered to ${deployment.filtered_publication_count}/${deployment.publication_count} publications`
            : "No deployments available",
        });
      } catch (error) {
        handleActionError(error, "Apply deployment filters failed");
      } finally {
        set({ working: false });
      }
    },

    async clearAutoResearchDeploymentFilters() {
      return get().applyAutoResearchDeploymentFilters({});
    },

    async updateAutoResearchRunControls(payload) {
      const { currentProjectId, autoResearchConsole } = get();
      const runId = autoResearchConsole?.current_run?.run.id;
      if (!currentProjectId || !runId) {
        set({ notice: "Select an auto-research run before updating controls" });
        return;
      }

      set({
        working: true,
        notice: `Updating auto-research controls for ${runId}...`,
      });
      try {
        await api.updateAutoResearchRunControls(
          currentProjectId,
          runId,
          payload,
        );
        await get().refreshAutoResearchConsole(runId);
        set({ notice: `Auto-research controls updated for ${runId}` });
      } catch (error) {
        handleActionError(error, "Update auto-research controls failed");
      } finally {
        set({ working: false });
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
        const console = await api.getAutoResearchOperatorConsole(projectId, {
          runId,
          ...normalizeConsoleFilters(get().autoResearchConsoleFilters),
        });
        const autoResearchPublicationManifest = await loadPublicationManifest(
          projectId,
          console,
        );
        set({
          autoResearchConsole: console,
          autoResearchConsoleFilters: console.filters,
          autoResearchPublicationManifest,
          notice: `Auto-research run ${runId} loaded`,
        });
      } catch (error) {
        handleActionError(error, "Load auto-research run failed");
      } finally {
        set({ working: false });
      }
    },

    async selectAutoResearchDeployment(deploymentId) {
      set({ working: true, notice: `Loading deployment ${deploymentId}...` });
      try {
        const [deploymentList, deployment] = await Promise.all([
          api.listAutoResearchDeployments(),
          api.getAutoResearchDeployment(
            deploymentId,
            normalizeDeploymentFilters(get().autoResearchDeploymentFilters),
          ),
        ]);
        set({
          autoResearchDeploymentList: deploymentList,
          selectedAutoResearchDeploymentId: deployment.deployment_id,
          autoResearchDeploymentFilters: deployment.filters,
          autoResearchDeployment: deployment,
          notice: `Deployment ${deploymentId} loaded`,
        });
      } catch (error) {
        handleActionError(error, "Load deployment failed");
      } finally {
        set({ working: false });
      }
    },

    async openAutoResearchPublication(projectId, runId) {
      set({ working: true, notice: `Opening publication ${runId}...` });
      try {
        await get().loadProject(projectId);
        await get().selectAutoResearchRun(runId);
        set({ notice: `Publication ${runId} loaded` });
      } catch (error) {
        handleActionError(error, "Open publication failed");
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
        (snapshot.draft_count !== current.drafts.length ||
          snapshot.evidence_count !== current.evidence.length ||
          snapshot.review_count !== current.reviews.length ||
          snapshot.latest_draft_version !== latestLocalDraftVersion ||
          snapshot.latest_review_status !==
            liveProgress?.latest_review_status ||
          snapshot.latest_export_status !== liveProgress?.latest_export_status);

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

    async startAutoResearch(payload) {
      const { currentProjectId, project } = get();
      if (!currentProjectId || !project) {
        set({
          notice: "Create or open a project before starting auto-research",
        });
        return;
      }

      set({ working: true, notice: "Starting auto-research run..." });
      try {
        const response = await api.startAutoResearch(currentProjectId, {
          topic: project.topic ?? project.title,
          language: "en",
          auto_search_literature: true,
          ...payload,
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

    async rebuildAutoResearchPaper() {
      const { currentProjectId, autoResearchConsole } = get();
      const runId = autoResearchConsole?.current_run?.run.id;
      if (!currentProjectId || !runId) {
        set({
          notice: "Select an auto-research run before rebuilding paper assets",
        });
        return;
      }

      set({ working: true, notice: `Rebuilding paper assets for ${runId}...` });
      try {
        await api.rebuildAutoResearchPaper(currentProjectId, runId);
        await sleep(400);
        await get().refreshProject();
        await get().refreshAutoResearchConsole(runId);
        set({ notice: `Paper assets rebuilt for ${runId}` });
      } catch (error) {
        handleActionError(error, "Rebuild paper pipeline failed");
      } finally {
        set({ working: false });
      }
    },

    async refreshAutoResearchReviewLoop() {
      const { currentProjectId, autoResearchConsole } = get();
      const runId = autoResearchConsole?.current_run?.run.id;
      if (!currentProjectId || !runId) {
        set({
          notice: "Select an auto-research run before refreshing review state",
        });
        return;
      }

      set({ working: true, notice: `Refreshing review loop for ${runId}...` });
      try {
        await api.refreshAutoResearchReviewLoop(currentProjectId, runId);
        await get().refreshAutoResearchConsole(runId);
        set({ notice: `Review loop refreshed for ${runId}` });
      } catch (error) {
        handleActionError(error, "Refresh review loop failed");
      } finally {
        set({ working: false });
      }
    },

    async refreshAutoResearchBridge() {
      const { currentProjectId, autoResearchConsole } = get();
      const runId = autoResearchConsole?.current_run?.run.id;
      if (!currentProjectId || !runId) {
        set({
          notice: "Select an auto-research run before refreshing bridge state",
        });
        return;
      }

      set({ working: true, notice: `Refreshing bridge state for ${runId}...` });
      try {
        const update = await api.refreshAutoResearchBridge(
          currentProjectId,
          runId,
        );
        await sleep(400);
        await get().refreshProject();
        await get().refreshAutoResearchConsole(runId);
        set({
          notice: update.imported
            ? update.resumed
              ? `Bridge result imported and resume queued for ${runId}`
              : `Bridge result imported for ${runId}`
            : `Bridge state refreshed for ${runId}`,
        });
      } catch (error) {
        handleActionError(error, "Refresh bridge state failed");
      } finally {
        set({ working: false });
      }
    },

    async applyAutoResearchReviewActions() {
      const { currentProjectId, autoResearchConsole } = get();
      const currentRun = autoResearchConsole?.current_run;
      const runId = currentRun?.run.id;
      const reviewLoop = currentRun?.review_loop;
      if (!currentProjectId || !runId || !reviewLoop) {
        set({
          notice:
            "Select an auto-research run with review actions before applying revisions",
        });
        return;
      }
      if (reviewLoop.pending_action_count < 1) {
        set({ notice: "Current review loop has no pending revision actions" });
        return;
      }
      if (!reviewLoop.latest_review_fingerprint) {
        set({
          notice: "Refresh review state before applying revision actions",
        });
        return;
      }

      set({ working: true, notice: `Applying review actions for ${runId}...` });
      try {
        await api.applyAutoResearchReviewLoop(currentProjectId, runId, {
          expected_round: reviewLoop.current_round,
          expected_review_fingerprint: reviewLoop.latest_review_fingerprint,
        });
        await sleep(400);
        await get().refreshProject();
        await get().refreshAutoResearchConsole(runId);
        set({ notice: `Review actions applied for ${runId}` });
      } catch (error) {
        handleActionError(error, "Apply review actions failed");
      } finally {
        set({ working: false });
      }
    },

    async importAutoResearchBridgeResult(payload) {
      const { currentProjectId, autoResearchConsole } = get();
      const runId = autoResearchConsole?.current_run?.run.id;
      if (!currentProjectId || !runId) {
        set({
          notice:
            "Select an auto-research run before importing a bridge result",
        });
        return;
      }

      set({ working: true, notice: `Importing bridge result for ${runId}...` });
      try {
        const update = await api.importAutoResearchBridgeResult(
          currentProjectId,
          runId,
          payload,
        );
        await sleep(400);
        await get().refreshProject();
        await get().refreshAutoResearchConsole(runId);
        set({
          notice: update.resumed
            ? `Bridge result imported and resume queued for ${runId}`
            : `Bridge result imported for ${runId}`,
        });
      } catch (error) {
        handleActionError(error, "Import bridge result failed");
      } finally {
        set({ working: false });
      }
    },

    async exportAutoResearchPublish(payload) {
      const { currentProjectId, autoResearchConsole } = get();
      const runId = autoResearchConsole?.current_run?.run.id;
      if (!currentProjectId || !runId) {
        set({
          notice: "Select an auto-research run before exporting publish assets",
        });
        return;
      }

      set({
        working: true,
        notice: `Exporting publish package for ${runId}...`,
      });
      try {
        const exportResult = await api.exportAutoResearchPublishPackage(
          currentProjectId,
          runId,
          payload,
        );
        await get().refreshAutoResearchConsole(runId);
        await get().refreshAutoResearchDeployments(
          exportResult.deployment_id ?? undefined,
        );
        set({
          notice: exportResult.deployment_id
            ? `Publish package ${exportResult.file_name} ready in deployment ${exportResult.deployment_id}`
            : `Publish package ${exportResult.file_name} ready`,
        });
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
        const fileName = await api.downloadAutoResearchPublishPackage(
          currentProjectId,
          runId,
        );
        set({ notice: `Downloaded ${fileName}` });
      } catch (error) {
        handleActionError(error, "Publish download failed");
      } finally {
        set({ working: false });
      }
    },

    async downloadAutoResearchPaper() {
      const {
        currentProjectId,
        autoResearchConsole,
        autoResearchPublicationManifest,
      } = get();
      const runId = autoResearchConsole?.current_run?.run.id;
      if (
        !currentProjectId ||
        !runId ||
        !autoResearchPublicationManifest?.paper_path
      ) {
        set({
          notice: "Current run does not have a published paper asset yet",
        });
        return;
      }

      set({ working: true, notice: "Preparing paper download..." });
      try {
        const fileName = await api.downloadAutoResearchPaper(
          currentProjectId,
          runId,
        );
        set({ notice: `Downloaded ${fileName}` });
      } catch (error) {
        handleActionError(error, "Paper download failed");
      } finally {
        set({ working: false });
      }
    },

    async downloadAutoResearchCompiledPaper() {
      const {
        currentProjectId,
        autoResearchConsole,
        autoResearchPublicationManifest,
      } = get();
      const runId = autoResearchConsole?.current_run?.run.id;
      if (
        !currentProjectId ||
        !runId ||
        !autoResearchPublicationManifest?.compiled_paper_path
      ) {
        set({ notice: "Current run does not have a compiled paper PDF yet" });
        return;
      }

      set({ working: true, notice: "Preparing compiled paper download..." });
      try {
        const fileName = await api.downloadAutoResearchCompiledPaper(
          currentProjectId,
          runId,
        );
        set({ notice: `Downloaded ${fileName}` });
      } catch (error) {
        handleActionError(error, "Compiled paper download failed");
      } finally {
        set({ working: false });
      }
    },

    async downloadAutoResearchCodePackage() {
      const {
        currentProjectId,
        autoResearchConsole,
        autoResearchPublicationManifest,
      } = get();
      const runId = autoResearchConsole?.current_run?.run.id;
      if (
        !currentProjectId ||
        !runId ||
        !autoResearchPublicationManifest?.code_package_path
      ) {
        set({
          notice: "Current run does not have a published code package yet",
        });
        return;
      }

      set({ working: true, notice: "Preparing code package download..." });
      try {
        const fileName = await api.downloadAutoResearchCodePackage(
          currentProjectId,
          runId,
        );
        set({ notice: `Downloaded ${fileName}` });
      } catch (error) {
        handleActionError(error, "Code package download failed");
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

      set({
        working: true,
        notice: `Saving draft v${selectedDraftVersion}...`,
      });
      try {
        const updated = await api.updateDraft(
          currentProjectId,
          selectedDraftVersion,
          {
            content: editorContent,
          },
        );
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
      const { currentProjectId, selectedDraftVersion, drafts, reviews } = get();
      const draftVersion = selectedDraftVersion ?? drafts[0]?.version;
      if (!currentProjectId || draftVersion === undefined) {
        set({ notice: "Generate a draft before review" });
        return;
      }

      set({
        working: true,
        notice: `Running review for draft v${draftVersion}...`,
      });
      try {
        const previousReviewCount = reviews.length;
        await api.runReview(currentProjectId, draftVersion);
        let reviewReady = false;
        for (let attempt = 0; attempt < 6; attempt += 1) {
          await sleep(800);
          await get().refreshProject();
          if (get().reviews.length > previousReviewCount) {
            reviewReady = true;
            break;
          }
        }
        set({ notice: reviewReady ? "Review ready" : "Review queued" });
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
      if (
        !currentProjectId ||
        !exportId ||
        liveProgress?.latest_export_status !== "done"
      ) {
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
