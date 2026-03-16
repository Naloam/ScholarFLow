import { create } from "zustand";

import { api } from "../api/client";
import type {
  AnalysisSummary,
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

type WorkspaceState = {
  healthStatus: string;
  templates: TemplateMeta[];
  currentProjectId: string;
  project: Project | null;
  projectStatus: ProjectStatus | null;
  liveProgress: ProjectProgressSnapshot | null;
  connectionState: "disconnected" | "connecting" | "live";
  lastProgressSignature: string;
  drafts: Draft[];
  selectedDraftVersion: number | null;
  editorContent: string;
  isDirty: boolean;
  focusedText: string;
  evidence: EvidenceItem[];
  reviews: ReviewReport[];
  analysis: AnalysisSummary | null;
  initializing: boolean;
  working: boolean;
  notice: string;
  bootstrap: () => Promise<void>;
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
  setConnectionState: (state: "disconnected" | "connecting" | "live") => void;
  applyProgressSnapshot: (snapshot: ProjectProgressSnapshot) => void;
  saveDraft: () => Promise<void>;
  generateDraft: () => Promise<void>;
  runReview: () => Promise<void>;
  exportDraft: (format: "markdown" | "latex" | "word" | "docx") => Promise<void>;
};

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  healthStatus: "checking",
  templates: [],
  currentProjectId: "",
  project: null,
  projectStatus: null,
  liveProgress: null,
  connectionState: "disconnected",
  lastProgressSignature: "",
  drafts: [],
  selectedDraftVersion: null,
  editorContent: "",
  isDirty: false,
  focusedText: "",
  evidence: [],
  reviews: [],
  analysis: null,
  initializing: false,
  working: false,
  notice: "Workspace idle",

  async bootstrap() {
    set({ initializing: true, notice: "Loading workspace..." });
    const [healthResult, templatesResult] = await Promise.allSettled([
      api.getHealth(),
      api.listTemplates(),
    ]);

    set({
      initializing: false,
      healthStatus: healthResult.status === "fulfilled" ? healthResult.value.status : "offline",
      templates:
        templatesResult.status === "fulfilled" ? templatesResult.value.items : [],
      notice:
        healthResult.status === "fulfilled"
          ? "Backend reachable"
          : `Backend unavailable: ${getErrorMessage(healthResult.reason)}`,
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
      set({ notice: `Create project failed: ${getErrorMessage(error)}` });
    } finally {
      set({ working: false });
    }
  },

  async loadProject(projectId) {
    set({ working: true, currentProjectId: projectId, notice: "Loading project..." });
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

      const drafts =
        draftsResult.status === "fulfilled" ? draftsResult.value : [];
      const selectedVersion =
        drafts.length > 0 ? drafts[0].version : null;
      const selectedDraft =
        selectedVersion !== null
          ? drafts.find((draft) => draft.version === selectedVersion) ?? null
          : null;

      set({
        project: projectResult.status === "fulfilled" ? projectResult.value : null,
        projectStatus: statusResult.status === "fulfilled" ? statusResult.value : null,
        drafts,
        selectedDraftVersion: selectedVersion,
        editorContent: selectedDraft?.content ?? "",
        isDirty: false,
        focusedText: "",
        evidence: evidenceResult.status === "fulfilled" ? evidenceResult.value : [],
        reviews: reviewsResult.status === "fulfilled" ? reviewsResult.value : [],
        analysis: analysisResult.status === "fulfilled" ? analysisResult.value : null,
        notice:
          projectResult.status === "fulfilled"
            ? `Project ${projectId} loaded`
            : `Load project failed: ${getErrorMessage(projectResult.reason)}`,
      });
    } catch (error) {
      set({ notice: `Load project failed: ${getErrorMessage(error)}` });
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
      set({ notice: `Refresh failed: ${getErrorMessage(error)}` });
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
      set({ notice: `Save failed: ${getErrorMessage(error)}` });
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
      set({ notice: `Generate draft failed: ${getErrorMessage(error)}` });
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
      set({ notice: `Run review failed: ${getErrorMessage(error)}` });
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
      set({ notice: `Export failed: ${getErrorMessage(error)}` });
    } finally {
      set({ working: false });
    }
  },
}));
