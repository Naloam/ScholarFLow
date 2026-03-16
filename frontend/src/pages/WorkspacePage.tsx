import { ProjectLauncher } from "../components/Projects/ProjectLauncher";
import { WizardPanel } from "../components/Wizard/WizardPanel";
import { FileManager } from "../components/FileManager/FileManager";
import { EditorSurface } from "../components/Editor/EditorSurface";
import { EvidencePanel } from "../components/EvidencePanel/EvidencePanel";
import { ReviewPanel } from "../components/ReviewPanel/ReviewPanel";
import { StatusBar } from "../components/Status/StatusBar";
import { VersionDiffPanel } from "../components/VersionDiffPanel/VersionDiffPanel";
import { useWorkspaceStore } from "../stores/workspace";

export function WorkspacePage() {
  const templates = useWorkspaceStore((state) => state.templates);
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const healthStatus = useWorkspaceStore((state) => state.healthStatus);
  const project = useWorkspaceStore((state) => state.project);
  const projectStatus = useWorkspaceStore((state) => state.projectStatus);
  const drafts = useWorkspaceStore((state) => state.drafts);
  const selectedDraftVersion = useWorkspaceStore((state) => state.selectedDraftVersion);
  const editorContent = useWorkspaceStore((state) => state.editorContent);
  const focusedText = useWorkspaceStore((state) => state.focusedText);
  const evidence = useWorkspaceStore((state) => state.evidence);
  const reviews = useWorkspaceStore((state) => state.reviews);
  const analysis = useWorkspaceStore((state) => state.analysis);
  const working = useWorkspaceStore((state) => state.working);
  const notice = useWorkspaceStore((state) => state.notice);
  const connectionState = useWorkspaceStore((state) => state.connectionState);
  const createProject = useWorkspaceStore((state) => state.createProject);
  const loadProject = useWorkspaceStore((state) => state.loadProject);
  const selectDraft = useWorkspaceStore((state) => state.selectDraft);
  const setEditorContent = useWorkspaceStore((state) => state.setEditorContent);
  const setFocusedText = useWorkspaceStore((state) => state.setFocusedText);
  const saveDraft = useWorkspaceStore((state) => state.saveDraft);
  const generateDraft = useWorkspaceStore((state) => state.generateDraft);
  const runReview = useWorkspaceStore((state) => state.runReview);
  const exportDraft = useWorkspaceStore((state) => state.exportDraft);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">ScholarFlow</p>
          <h1>Phase 5 Workspace</h1>
        </div>
        <div className="header-meta">
          <span className="meta-chip">{projectStatus?.phase ?? "Phase 5"}</span>
          <span className="meta-chip">{project?.title ?? "No active project"}</span>
        </div>
      </header>

      <main className="workspace-grid">
        <aside className="workspace-column workspace-column-left">
          <ProjectLauncher
            templates={templates}
            currentProjectId={currentProjectId}
            healthStatus={healthStatus}
            working={working}
            onCreate={createProject}
            onOpen={loadProject}
          />
          <WizardPanel status={projectStatus} />
          <FileManager
            drafts={drafts}
            selectedDraftVersion={selectedDraftVersion}
            onSelect={selectDraft}
          />
        </aside>

        <section className="workspace-column workspace-column-center">
          <EditorSurface
            content={editorContent}
            canEdit={Boolean(currentProjectId)}
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
        </aside>
      </main>

      <StatusBar
        notice={notice}
        projectId={currentProjectId}
        selectedDraftVersion={selectedDraftVersion}
        working={working}
        connectionState={connectionState}
      />
    </div>
  );
}
