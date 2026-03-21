import type { AutoResearchOperatorConsole } from "../../api/types";

type OperatorConsolePanelProps = {
  consoleState: AutoResearchOperatorConsole | null;
  projectTopic?: string | null;
  disabled: boolean;
  onStartRun: () => void;
  onSelectRun: (runId: string) => void;
  onResume: () => void;
  onRetry: () => void;
  onCancel: () => void;
  onExportPublish: () => void;
  onDownloadPublish: () => void;
};

function formatScore(value: unknown): string {
  return typeof value === "number" ? value.toFixed(4) : "n/a";
}

export function OperatorConsolePanel({
  consoleState,
  projectTopic,
  disabled,
  onStartRun,
  onSelectRun,
  onResume,
  onRetry,
  onCancel,
  onExportPublish,
  onDownloadPublish,
}: OperatorConsolePanelProps) {
  const current = consoleState?.current_run ?? null;
  const review = current?.review ?? null;
  const publish = current?.publish ?? null;
  const candidateEntries = current?.registry?.candidates ?? [];
  const counts = current?.registry_views?.counts;
  const lineage = current?.registry?.lineage;

  return (
    <section className="panel" data-testid="operator-console-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Phase 6</p>
          <h2 className="panel-title">Operator Console</h2>
        </div>
        <span className="badge badge-soft">
          {consoleState ? `${consoleState.run_count} runs` : "No runs"}
        </span>
      </div>

      <div className="button-row">
        <button
          type="button"
          className="primary-btn"
          onClick={onStartRun}
          disabled={disabled || !projectTopic}
          data-testid="start-autoresearch-button"
        >
          Start Run
        </button>
        <button
          type="button"
          className="ghost-btn"
          onClick={onResume}
          disabled={disabled || !current?.actions.resume}
          data-testid="resume-autoresearch-button"
        >
          Resume
        </button>
        <button
          type="button"
          className="ghost-btn"
          onClick={onRetry}
          disabled={disabled || !current?.actions.retry}
          data-testid="retry-autoresearch-button"
        >
          Retry
        </button>
        <button
          type="button"
          className="ghost-btn"
          onClick={onCancel}
          disabled={disabled || !current?.actions.cancel}
          data-testid="cancel-autoresearch-button"
        >
          Cancel
        </button>
        <button
          type="button"
          className="ghost-btn"
          onClick={onExportPublish}
          disabled={disabled || !current?.actions.export_publish}
          data-testid="export-publish-button"
        >
          Export Publish
        </button>
        <button
          type="button"
          className="ghost-btn"
          onClick={onDownloadPublish}
          disabled={disabled || !current?.actions.download_publish}
          data-testid="download-publish-button"
        >
          Download Publish
        </button>
      </div>

      {!consoleState || consoleState.run_count === 0 ? (
        <div className="empty-state">
          <p>No auto-research runs yet.</p>
          <span>
            Start a run for `{projectTopic || "this project"}` to populate execution, candidate, and
            publish inspection state.
          </span>
        </div>
      ) : (
        <>
          <div className="list-block operator-run-list">
            {consoleState.runs.map((run) => (
              <button
                key={run.run_id}
                type="button"
                className={
                  run.run_id === consoleState.selected_run_id ? "list-item selected" : "list-item"
                }
                onClick={() => onSelectRun(run.run_id)}
                disabled={disabled}
                data-testid={`operator-run-${run.run_id}`}
              >
                <div>
                  <strong>{run.run_id}</strong>
                  <small>{run.topic}</small>
                </div>
                <div className="operator-run-meta">
                  <span className="badge badge-soft">{run.status}</span>
                  <small>
                    selected {run.selected_count} / failed {run.failed_count} / active {run.active_count}
                  </small>
                </div>
              </button>
            ))}
          </div>

          {current ? (
            <>
              <div className="summary-banner operator-summary-grid">
                <div>
                  <span className="meta-label">Run Status</span>
                  <strong>{current.run.status}</strong>
                </div>
                <div>
                  <span className="meta-label">Selected Candidate</span>
                  <strong>{current.registry.selected_candidate_id ?? "n/a"}</strong>
                </div>
                <div>
                  <span className="meta-label">Execution</span>
                  <strong>{current.execution.active_job_id ?? current.execution.worker?.status ?? "idle"}</strong>
                </div>
                <div>
                  <span className="meta-label">Publish</span>
                  <strong>{publish?.status ?? "not built"}</strong>
                </div>
              </div>

              <div className="summary-banner operator-summary-grid">
                <div>
                  <span className="meta-label">Candidates</span>
                  <strong>{counts?.total_candidates ?? candidateEntries.length}</strong>
                </div>
                <div>
                  <span className="meta-label">Failed Candidates</span>
                  <strong>{counts?.failed ?? 0}</strong>
                </div>
                <div>
                  <span className="meta-label">Review Risk</span>
                  <strong>{review?.unsupported_claim_risk ?? "n/a"}</strong>
                </div>
                <div>
                  <span className="meta-label">Revision Actions</span>
                  <strong>{publish?.revision_count ?? review?.revision_plan.length ?? 0}</strong>
                </div>
              </div>

              <div className="meta-block">
                <span className="meta-label">Lineage</span>
                <code data-testid="operator-lineage-summary">
                  selected={lineage?.selected_candidate_id ?? "n/a"} artifact_from=
                  {lineage?.top_level_artifact_candidate_id ?? "n/a"} paper_from=
                  {lineage?.top_level_paper_candidate_id ?? "n/a"} edges={lineage?.edges.length ?? 0}
                </code>
              </div>

              <div className="stack">
                <p className="inline-title">Candidate Comparison</p>
                {candidateEntries.map((candidate) => (
                  <div key={candidate.candidate_id} className="evidence-card" data-testid={`operator-candidate-${candidate.candidate_id}`}>
                    <div className="panel-header">
                      <div>
                        <strong>{candidate.title}</strong>
                        <p className="auth-copy">
                          {candidate.candidate_id} · {candidate.status}
                          {candidate.selected ? " · selected" : ""}
                        </p>
                      </div>
                      <span className="badge badge-soft">{formatScore(candidate.objective_score)}</span>
                    </div>
                    <p className="auth-copy">
                      outcome={candidate.decision_outcome ?? "n/a"} · attempts={candidate.attempt_count} ·
                      artifact={candidate.artifact_status ?? "n/a"}
                    </p>
                  </div>
                ))}
              </div>

              <div className="stack">
                <p className="inline-title">Top Findings</p>
                {review?.findings?.slice(0, 3).map((finding) => (
                  <div key={finding.id} className="suggestion-card">
                    <strong>
                      {finding.severity.toUpperCase()} · {finding.category}
                    </strong>
                    <p>{finding.summary}</p>
                  </div>
                )) ?? (
                  <div className="empty-state">
                    <p>No review findings yet.</p>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="empty-state">
              <p>No run selected.</p>
              <span>Select a run to inspect execution, lineage, review, and publish state.</span>
            </div>
          )}
        </>
      )}
    </section>
  );
}
