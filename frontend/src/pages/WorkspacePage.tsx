import { BetaPanel } from "../components/Beta/BetaPanel";
import { MentorPanel } from "../components/Mentor/MentorPanel";
import { SessionPanel } from "../components/Auth/SessionPanel";
import { ProjectLauncher } from "../components/Projects/ProjectLauncher";
import { WizardPanel } from "../components/Wizard/WizardPanel";
import { FileManager } from "../components/FileManager/FileManager";
import { EditorSurface } from "../components/Editor/EditorSurface";
import { EvidencePanel } from "../components/EvidencePanel/EvidencePanel";
import { OperatorConsolePanel } from "../components/OperatorConsole/OperatorConsolePanel";
import { ReviewPanel } from "../components/ReviewPanel/ReviewPanel";
import { StatusBar } from "../components/Status/StatusBar";
import { VersionDiffPanel } from "../components/VersionDiffPanel/VersionDiffPanel";
import { useWorkspaceStore } from "../stores/workspace";

export function WorkspacePage() {
  const templates = useWorkspaceStore((state) => state.templates);
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const availableProjects = useWorkspaceStore((state) => state.availableProjects);
  const healthStatus = useWorkspaceStore((state) => state.healthStatus);
  const project = useWorkspaceStore((state) => state.project);
  const projectStatus = useWorkspaceStore((state) => state.projectStatus);
  const drafts = useWorkspaceStore((state) => state.drafts);
  const selectedDraftVersion = useWorkspaceStore((state) => state.selectedDraftVersion);
  const editorContent = useWorkspaceStore((state) => state.editorContent);
  const focusedText = useWorkspaceStore((state) => state.focusedText);
  const evidence = useWorkspaceStore((state) => state.evidence);
  const reviews = useWorkspaceStore((state) => state.reviews);
  const autoResearchConsole = useWorkspaceStore((state) => state.autoResearchConsole);
  const autoResearchConsoleFilters = useWorkspaceStore((state) => state.autoResearchConsoleFilters);
  const analysis = useWorkspaceStore((state) => state.analysis);
  const betaSummary = useWorkspaceStore((state) => state.betaSummary);
  const mentorAccess = useWorkspaceStore((state) => state.mentorAccess);
  const mentorFeedback = useWorkspaceStore((state) => state.mentorFeedback);
  const authConfig = useWorkspaceStore((state) => state.authConfig);
  const authState = useWorkspaceStore((state) => state.authState);
  const authUser = useWorkspaceStore((state) => state.authUser);
  const authBusy = useWorkspaceStore((state) => state.authBusy);
  const authError = useWorkspaceStore((state) => state.authError);
  const initializing = useWorkspaceStore((state) => state.initializing);
  const working = useWorkspaceStore((state) => state.working);
  const notice = useWorkspaceStore((state) => state.notice);
  const connectionState = useWorkspaceStore((state) => state.connectionState);
  const liveProgress = useWorkspaceStore((state) => state.liveProgress);
  const signIn = useWorkspaceStore((state) => state.signIn);
  const signOut = useWorkspaceStore((state) => state.signOut);
  const createProject = useWorkspaceStore((state) => state.createProject);
  const loadProject = useWorkspaceStore((state) => state.loadProject);
  const applyAutoResearchConsoleFilters = useWorkspaceStore((state) => state.applyAutoResearchConsoleFilters);
  const clearAutoResearchConsoleFilters = useWorkspaceStore((state) => state.clearAutoResearchConsoleFilters);
  const selectDraft = useWorkspaceStore((state) => state.selectDraft);
  const setEditorContent = useWorkspaceStore((state) => state.setEditorContent);
  const setFocusedText = useWorkspaceStore((state) => state.setFocusedText);
  const saveDraft = useWorkspaceStore((state) => state.saveDraft);
  const generateDraft = useWorkspaceStore((state) => state.generateDraft);
  const startAutoResearch = useWorkspaceStore((state) => state.startAutoResearch);
  const selectAutoResearchRun = useWorkspaceStore((state) => state.selectAutoResearchRun);
  const resumeAutoResearch = useWorkspaceStore((state) => state.resumeAutoResearch);
  const retryAutoResearch = useWorkspaceStore((state) => state.retryAutoResearch);
  const cancelAutoResearch = useWorkspaceStore((state) => state.cancelAutoResearch);
  const updateAutoResearchRunControls = useWorkspaceStore((state) => state.updateAutoResearchRunControls);
  const exportAutoResearchPublish = useWorkspaceStore((state) => state.exportAutoResearchPublish);
  const downloadAutoResearchPublish = useWorkspaceStore((state) => state.downloadAutoResearchPublish);
  const runReview = useWorkspaceStore((state) => state.runReview);
  const exportDraft = useWorkspaceStore((state) => state.exportDraft);
  const downloadLatestExport = useWorkspaceStore((state) => state.downloadLatestExport);
  const inviteMentor = useWorkspaceStore((state) => state.inviteMentor);
  const submitMentorFeedback = useWorkspaceStore((state) => state.submitMentorFeedback);
  const submitFeedback = useWorkspaceStore((state) => state.submitFeedback);
  const authLocked = Boolean(authConfig?.auth_required) && authState === "anonymous";
  const projectReadOnly = Boolean(project?.user_id && authUser?.id && project.user_id !== authUser.id);
  const workspaceBusy = initializing || authBusy || working;
  const betaBusy = workspaceBusy || !currentProjectId || authLocked || projectReadOnly;
  const authLabel =
    authUser?.email
      ? `Auth: ${authUser.email}`
      : authState === "service"
        ? "Auth: service token"
        : authLocked
          ? "Auth: sign-in required"
          : authState === "checking"
            ? "Auth: checking"
            : "Auth: anonymous";

  return (
    <div className="app-shell" data-testid="workspace-page">
      <header className="app-header">
        <div>
          <p className="eyebrow">ScholarFlow</p>
          <h1>Operator Console Workspace</h1>
        </div>
        <div className="header-meta">
          <span className="meta-chip" data-testid="header-phase-chip">
            {projectStatus?.phase ?? "Phase 6"}
          </span>
          <span className="meta-chip" data-testid="header-project-chip">
            {project?.title ?? "No active project"}
          </span>
          <span className="meta-chip" data-testid="header-user-chip">
            {authUser?.email ?? (authState === "service" ? "Service token" : "Anonymous")}
          </span>
        </div>
      </header>

      <main className="workspace-grid">
        <aside className="workspace-column workspace-column-left">
          <SessionPanel
            authConfig={authConfig}
            authState={authState}
            authUser={authUser}
            authBusy={authBusy}
            authError={authError}
            workspaceBusy={workspaceBusy}
            onSignIn={signIn}
            onSignOut={signOut}
          />
          <MentorPanel
            projectId={currentProjectId}
            projectOwnerId={project?.user_id}
            selectedDraftVersion={selectedDraftVersion}
            authUser={authUser}
            mentorAccess={mentorAccess}
            mentorFeedback={mentorFeedback}
            disabled={workspaceBusy}
            onInvite={inviteMentor}
            onSubmitFeedback={submitMentorFeedback}
          />
          <ProjectLauncher
            templates={templates}
            currentProjectId={currentProjectId}
            availableProjects={availableProjects}
            healthStatus={healthStatus}
            working={workspaceBusy}
            authLocked={authLocked}
            onCreate={createProject}
            onOpen={loadProject}
          />
          <WizardPanel status={projectStatus} />
          <FileManager
            drafts={drafts}
            selectedDraftVersion={selectedDraftVersion}
            latestExportId={liveProgress?.latest_export_id}
            latestExportStatus={liveProgress?.latest_export_status}
            downloading={workspaceBusy}
            onSelect={selectDraft}
            onDownloadLatestExport={downloadLatestExport}
          />
        </aside>

        <section className="workspace-column workspace-column-center">
          <OperatorConsolePanel
            consoleState={autoResearchConsole}
            filters={autoResearchConsoleFilters}
            projectTopic={project?.topic ?? project?.title}
            disabled={workspaceBusy || authLocked}
            onStartRun={startAutoResearch}
            onApplyFilters={applyAutoResearchConsoleFilters}
            onClearFilters={clearAutoResearchConsoleFilters}
            onSelectRun={selectAutoResearchRun}
            onResume={resumeAutoResearch}
            onRetry={retryAutoResearch}
            onCancel={cancelAutoResearch}
            onExportPublish={exportAutoResearchPublish}
            onDownloadPublish={downloadAutoResearchPublish}
            onUpdateControls={updateAutoResearchRunControls}
          />
          <EditorSurface
            content={editorContent}
            canEdit={Boolean(currentProjectId) && !projectReadOnly}
            working={working}
            onChange={setEditorContent}
            onFocusText={setFocusedText}
            onSave={saveDraft}
            onGenerate={generateDraft}
            onReview={runReview}
            onExport={exportDraft}
          />
          <VersionDiffPanel
            drafts={drafts}
            selectedDraftVersion={selectedDraftVersion}
            currentContent={editorContent}
          />
        </section>

        <aside className="workspace-column workspace-column-right">
          <EvidencePanel evidence={evidence} focusedText={focusedText} />
          <ReviewPanel reviews={reviews} analysis={analysis} />
          <BetaPanel summary={betaSummary} disabled={betaBusy} onSubmit={submitFeedback} />
        </aside>
      </main>

      <StatusBar
        notice={notice}
        projectId={currentProjectId}
        selectedDraftVersion={selectedDraftVersion}
        working={workspaceBusy}
        connectionState={connectionState}
        authLabel={authLabel}
      />
    </div>
  );
}
