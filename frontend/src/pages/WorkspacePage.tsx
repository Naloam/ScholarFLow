import { useTranslation } from "react-i18next";

import { BetaPanel } from "../components/Beta/BetaPanel";
import { MentorPanel } from "../components/Mentor/MentorPanel";
import { SessionPanel } from "../components/Auth/SessionPanel";
import { ProjectLauncher } from "../components/Projects/ProjectLauncher";
import { WizardPanel } from "../components/Wizard/WizardPanel";
import { FileManager } from "../components/FileManager/FileManager";
import { EditorSurface } from "../components/Editor/EditorSurface";
import { EvidencePanel } from "../components/EvidencePanel/EvidencePanel";
import { DeploymentPanel } from "../components/DeploymentPanel/DeploymentPanel";
import { OperatorConsolePanel } from "../components/OperatorConsole/OperatorConsolePanel";
import { ReviewPanel } from "../components/ReviewPanel/ReviewPanel";
import { StatusBar } from "../components/Status/StatusBar";
import { VersionDiffPanel } from "../components/VersionDiffPanel/VersionDiffPanel";
import { LanguageSwitcher } from "../components/LanguageSwitcher/LanguageSwitcher";
import { CollapsiblePanel } from "../components/shared/CollapsiblePanel";
import { useWorkspaceStore } from "../stores/workspace";

export function WorkspacePage() {
  const { t } = useTranslation();
  const templates = useWorkspaceStore((state) => state.templates);
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const availableProjects = useWorkspaceStore(
    (state) => state.availableProjects,
  );
  const healthStatus = useWorkspaceStore((state) => state.healthStatus);
  const project = useWorkspaceStore((state) => state.project);
  const projectStatus = useWorkspaceStore((state) => state.projectStatus);
  const drafts = useWorkspaceStore((state) => state.drafts);
  const selectedDraftVersion = useWorkspaceStore(
    (state) => state.selectedDraftVersion,
  );
  const editorContent = useWorkspaceStore((state) => state.editorContent);
  const focusedText = useWorkspaceStore((state) => state.focusedText);
  const evidence = useWorkspaceStore((state) => state.evidence);
  const reviews = useWorkspaceStore((state) => state.reviews);
  const autoResearchConsole = useWorkspaceStore(
    (state) => state.autoResearchConsole,
  );
  const autoResearchConsoleFilters = useWorkspaceStore(
    (state) => state.autoResearchConsoleFilters,
  );
  const autoResearchDeploymentList = useWorkspaceStore(
    (state) => state.autoResearchDeploymentList,
  );
  const selectedAutoResearchDeploymentId = useWorkspaceStore(
    (state) => state.selectedAutoResearchDeploymentId,
  );
  const autoResearchDeploymentFilters = useWorkspaceStore(
    (state) => state.autoResearchDeploymentFilters,
  );
  const autoResearchDeployment = useWorkspaceStore(
    (state) => state.autoResearchDeployment,
  );
  const autoResearchPublicationManifest = useWorkspaceStore(
    (state) => state.autoResearchPublicationManifest,
  );
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
  const applyAutoResearchConsoleFilters = useWorkspaceStore(
    (state) => state.applyAutoResearchConsoleFilters,
  );
  const clearAutoResearchConsoleFilters = useWorkspaceStore(
    (state) => state.clearAutoResearchConsoleFilters,
  );
  const applyAutoResearchDeploymentFilters = useWorkspaceStore(
    (state) => state.applyAutoResearchDeploymentFilters,
  );
  const clearAutoResearchDeploymentFilters = useWorkspaceStore(
    (state) => state.clearAutoResearchDeploymentFilters,
  );
  const selectDraft = useWorkspaceStore((state) => state.selectDraft);
  const setEditorContent = useWorkspaceStore((state) => state.setEditorContent);
  const setFocusedText = useWorkspaceStore((state) => state.setFocusedText);
  const saveDraft = useWorkspaceStore((state) => state.saveDraft);
  const generateDraft = useWorkspaceStore((state) => state.generateDraft);
  const startAutoResearch = useWorkspaceStore(
    (state) => state.startAutoResearch,
  );
  const selectAutoResearchRun = useWorkspaceStore(
    (state) => state.selectAutoResearchRun,
  );
  const selectAutoResearchDeployment = useWorkspaceStore(
    (state) => state.selectAutoResearchDeployment,
  );
  const openAutoResearchPublication = useWorkspaceStore(
    (state) => state.openAutoResearchPublication,
  );
  const resumeAutoResearch = useWorkspaceStore(
    (state) => state.resumeAutoResearch,
  );
  const retryAutoResearch = useWorkspaceStore(
    (state) => state.retryAutoResearch,
  );
  const cancelAutoResearch = useWorkspaceStore(
    (state) => state.cancelAutoResearch,
  );
  const refreshAutoResearchBridge = useWorkspaceStore(
    (state) => state.refreshAutoResearchBridge,
  );
  const refreshAutoResearchReviewLoop = useWorkspaceStore(
    (state) => state.refreshAutoResearchReviewLoop,
  );
  const applyAutoResearchReviewActions = useWorkspaceStore(
    (state) => state.applyAutoResearchReviewActions,
  );
  const rebuildAutoResearchPaper = useWorkspaceStore(
    (state) => state.rebuildAutoResearchPaper,
  );
  const updateAutoResearchRunControls = useWorkspaceStore(
    (state) => state.updateAutoResearchRunControls,
  );
  const importAutoResearchBridgeResult = useWorkspaceStore(
    (state) => state.importAutoResearchBridgeResult,
  );
  const exportAutoResearchPublish = useWorkspaceStore(
    (state) => state.exportAutoResearchPublish,
  );
  const downloadAutoResearchPublish = useWorkspaceStore(
    (state) => state.downloadAutoResearchPublish,
  );
  const downloadAutoResearchPaper = useWorkspaceStore(
    (state) => state.downloadAutoResearchPaper,
  );
  const downloadAutoResearchCompiledPaper = useWorkspaceStore(
    (state) => state.downloadAutoResearchCompiledPaper,
  );
  const downloadAutoResearchCodePackage = useWorkspaceStore(
    (state) => state.downloadAutoResearchCodePackage,
  );
  const runReview = useWorkspaceStore((state) => state.runReview);
  const exportDraft = useWorkspaceStore((state) => state.exportDraft);
  const downloadLatestExport = useWorkspaceStore(
    (state) => state.downloadLatestExport,
  );
  const inviteMentor = useWorkspaceStore((state) => state.inviteMentor);
  const submitMentorFeedback = useWorkspaceStore(
    (state) => state.submitMentorFeedback,
  );
  const submitFeedback = useWorkspaceStore((state) => state.submitFeedback);
  const authLocked =
    Boolean(authConfig?.api_protected) && authState === "anonymous";
  const projectReadOnly = Boolean(
    project?.user_id && authUser?.id && project.user_id !== authUser.id,
  );
  const workspaceBusy = initializing || authBusy || working;
  const launcherBusy = authBusy || working;
  const betaBusy =
    authBusy || !currentProjectId || authLocked || projectReadOnly;
  const authLabel = authUser?.email
    ? `Auth: ${authUser.email}`
    : authState === "service"
      ? "Auth: service token"
      : authLocked
        ? authConfig?.session_enabled
          ? "Auth: sign-in required"
          : "Auth: bearer token required"
        : authState === "checking"
          ? "Auth: checking"
          : "Auth: anonymous";

  return (
    <div className="app-shell" data-testid="workspace-page">
      <header className="app-header">
        <div>
          <p className="eyebrow">{t("header.eyebrow")}</p>
          <h1>{t("header.title")}</h1>
        </div>
        <div className="header-meta">
          <span className="meta-chip" data-testid="header-phase-chip">
            {projectStatus?.phase ?? t("header.phase")}
          </span>
          <span className="meta-chip" data-testid="header-project-chip">
            {project?.title ?? t("header.noProject")}
          </span>
          <span className="meta-chip" data-testid="header-user-chip">
            {authUser?.email ??
              (authState === "service"
                ? t("header.serviceToken")
                : t("header.anonymous"))}
          </span>
          <LanguageSwitcher />
        </div>
      </header>

      <main className="workspace-grid">
        <aside className="workspace-column workspace-column-left">
          <CollapsiblePanel
            eyebrow={t("session.eyebrow")}
            title={t("session.title")}
            defaultOpen={authState !== "user" && authState !== "service"}
            data-testid="collapsible-session"
          >
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
          </CollapsiblePanel>
          <CollapsiblePanel
            eyebrow={t("mentor.eyebrow")}
            title={t("mentor.title")}
            defaultOpen={false}
            data-testid="collapsible-mentor"
          >
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
          </CollapsiblePanel>
          <CollapsiblePanel
            eyebrow={t("project.eyebrow")}
            title={t("project.title")}
            defaultOpen={!currentProjectId}
            data-testid="collapsible-project"
          >
            <ProjectLauncher
              templates={templates}
              currentProjectId={currentProjectId}
              availableProjects={availableProjects}
              healthStatus={healthStatus}
              working={launcherBusy}
              authLocked={authLocked}
              onCreate={createProject}
              onOpen={loadProject}
            />
          </CollapsiblePanel>
          <CollapsiblePanel
            eyebrow={t("wizard.eyebrow")}
            title={t("wizard.title")}
            defaultOpen={false}
            data-testid="collapsible-wizard"
          >
            <WizardPanel status={projectStatus} />
          </CollapsiblePanel>
          <CollapsiblePanel
            eyebrow={t("fileManager.eyebrow")}
            title={t("fileManager.title")}
            defaultOpen={true}
            data-testid="collapsible-files"
          >
            <FileManager
              drafts={drafts}
              selectedDraftVersion={selectedDraftVersion}
              latestExportId={liveProgress?.latest_export_id}
              latestExportStatus={liveProgress?.latest_export_status}
              downloading={workspaceBusy}
              onSelect={selectDraft}
              onDownloadLatestExport={downloadLatestExport}
            />
          </CollapsiblePanel>
        </aside>

        <section className="workspace-column workspace-column-center">
          <OperatorConsolePanel
            consoleState={autoResearchConsole}
            publicationManifest={autoResearchPublicationManifest}
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
            onRefreshBridge={refreshAutoResearchBridge}
            onRefreshReview={refreshAutoResearchReviewLoop}
            onImportBridgeResult={importAutoResearchBridgeResult}
            onApplyReviewActions={applyAutoResearchReviewActions}
            onRebuildPaper={rebuildAutoResearchPaper}
            onExportPublish={exportAutoResearchPublish}
            onDownloadPublish={downloadAutoResearchPublish}
            onDownloadPaper={downloadAutoResearchPaper}
            onDownloadCompiledPaper={downloadAutoResearchCompiledPaper}
            onDownloadCodePackage={downloadAutoResearchCodePackage}
            onUpdateControls={updateAutoResearchRunControls}
          />
          <CollapsiblePanel
            eyebrow={t("editor.eyebrow")}
            title={t("editor.title")}
            defaultOpen={true}
            data-testid="collapsible-editor"
          >
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
          </CollapsiblePanel>
          <CollapsiblePanel
            eyebrow={t("versionDiff.eyebrow")}
            title={t("versionDiff.title")}
            defaultOpen={false}
            data-testid="collapsible-diff"
          >
            <VersionDiffPanel
              drafts={drafts}
              selectedDraftVersion={selectedDraftVersion}
              currentContent={editorContent}
            />
          </CollapsiblePanel>
        </section>

        <aside className="workspace-column workspace-column-right">
          <CollapsiblePanel
            eyebrow={t("deployment.eyebrow")}
            title={t("deployment.title")}
            defaultOpen={false}
            data-testid="collapsible-deployment"
          >
            <DeploymentPanel
              deploymentList={autoResearchDeploymentList}
              deployment={autoResearchDeployment}
              selectedDeploymentId={selectedAutoResearchDeploymentId}
              filters={autoResearchDeploymentFilters}
              disabled={workspaceBusy || authLocked}
              onSelectDeployment={selectAutoResearchDeployment}
              onApplyFilters={applyAutoResearchDeploymentFilters}
              onClearFilters={clearAutoResearchDeploymentFilters}
              onOpenPublication={openAutoResearchPublication}
            />
          </CollapsiblePanel>
          <CollapsiblePanel
            eyebrow={t("evidence.eyebrow")}
            title={t("evidence.title")}
            defaultOpen={true}
            data-testid="collapsible-evidence"
          >
            <EvidencePanel evidence={evidence} focusedText={focusedText} />
          </CollapsiblePanel>
          <CollapsiblePanel
            eyebrow={t("review.eyebrow")}
            title={t("review.title")}
            defaultOpen={true}
            data-testid="collapsible-review"
          >
            <ReviewPanel reviews={reviews} analysis={analysis} />
          </CollapsiblePanel>
          <CollapsiblePanel
            eyebrow={t("beta.eyebrow")}
            title={t("beta.title")}
            defaultOpen={false}
            data-testid="collapsible-beta"
          >
            <BetaPanel
              summary={betaSummary}
              disabled={betaBusy}
              onSubmit={submitFeedback}
            />
          </CollapsiblePanel>
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
