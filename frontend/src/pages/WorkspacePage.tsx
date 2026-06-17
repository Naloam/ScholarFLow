// Workspace: fixed-layout file tree (left) + selected file content (right).
// Markdown files render; everything else (json/py/csv/log/jsonl/txt) shows raw
// in a <pre>. Defaults to research_report.md. A 404 for a not-yet-generated
// file is shown as a gentle "not generated" hint, not an error.
import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { FileTree } from "../components/FileTree";
import { MarkdownView } from "../components/MarkdownView";
import { Spinner } from "../components/Spinner";
import { ErrorState } from "../components/States";
import { DEFAULT_FILE, WORKSPACE_TREE } from "../lib/workspaceLayout";
import { useWorkspaceStore } from "../stores/workspace";

function isMarkdown(path: string): boolean {
  return path.toLowerCase().endsWith(".md");
}

function prettyIfJson(path: string, content: string): string {
  if (!path.toLowerCase().endsWith(".json")) {
    return content;
  }
  try {
    return JSON.stringify(JSON.parse(content), null, 2);
  } catch {
    return content;
  }
}

export function WorkspacePage() {
  const { projectId = "", "*": splat } = useParams();
  const navigate = useNavigate();
  // URL splat is the single source of truth for the selected file — this keeps
  // the header + render-mode in sync with the tree and makes files deep-linkable.
  const selectedPath = splat ? decodeURIComponent(splat) : DEFAULT_FILE;
  const { content, loading, notFound, error, selectFile } = useWorkspaceStore();

  useEffect(() => {
    if (projectId) {
      void selectFile(projectId, selectedPath);
    }
  }, [projectId, selectedPath, selectFile]);

  if (!projectId) {
    return <ErrorState message="No project selected." />;
  }

  return (
    <div className="page page--workspace">
      <header className="page__head">
        <div>
          <h1 className="page__title">Workspace</h1>
          <p className="page__subtitle">Raw artifacts produced by the run.</p>
        </div>
      </header>

      <div className="workspace">
        <aside className="workspace__tree">
          <FileTree
            nodes={WORKSPACE_TREE}
            selectedPath={selectedPath}
            onSelect={(path) => navigate(`/projects/${projectId}/files/${path}`)}
          />
        </aside>
        <section className="workspace__content" aria-live="polite">
          <div className="workspace__path">{selectedPath}</div>
          {loading ? <Spinner label="Reading file…" /> : null}
          {!loading && error ? <ErrorState message={error} /> : null}
          {!loading && notFound ? (
            <div className="callout">
              <p>
                <code>{selectedPath}</code> has not been generated for this run yet.
              </p>
            </div>
          ) : null}
          {!loading && !error && !notFound && content ? (
            isMarkdown(selectedPath) ? (
              <MarkdownView source={content} />
            ) : (
              <pre className="codeblock">
                <code>{prettyIfJson(selectedPath, content)}</code>
              </pre>
            )
          ) : null}
        </section>
      </div>
    </div>
  );
}
