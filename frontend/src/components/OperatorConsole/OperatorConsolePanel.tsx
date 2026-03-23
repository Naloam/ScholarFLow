import { useEffect, useState } from "react";

import type { AutoResearchOperatorConsole, AutoResearchOperatorConsoleFilters } from "../../api/types";

type OperatorConsolePanelProps = {
  consoleState: AutoResearchOperatorConsole | null;
  filters: AutoResearchOperatorConsoleFilters;
  projectTopic?: string | null;
  disabled: boolean;
  onStartRun: () => void;
  onApplyFilters: (filters: AutoResearchOperatorConsoleFilters) => void;
  onClearFilters: () => void;
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
  filters,
  projectTopic,
  disabled,
  onStartRun,
  onApplyFilters,
  onClearFilters,
  onSelectRun,
  onResume,
  onRetry,
  onCancel,
  onExportPublish,
  onDownloadPublish,
}: OperatorConsolePanelProps) {
  const [draftFilters, setDraftFilters] = useState<AutoResearchOperatorConsoleFilters>(filters);

  useEffect(() => {
    setDraftFilters(filters);
  }, [
    filters.search,
    filters.status,
    filters.publish_status,
    filters.review_risk,
    filters.novelty_status,
    filters.budget_status,
  ]);

  const current = consoleState?.current_run ?? null;
  const review = current?.review ?? null;
  const publish = current?.publish ?? null;
  const candidateEntries = current?.registry?.candidates ?? [];
  const counts = current?.registry_views?.counts;
  const lineage = current?.registry?.lineage;
  const novelty = review?.novelty_assessment ?? null;
  const activeConsole = consoleState;
  const currentSummary =
    activeConsole?.runs.find((run) => run.run_id === current?.run.id) ?? null;
  const hasRuns = Boolean(consoleState && consoleState.run_count > 0);
  const hasFilteredRuns = Boolean(consoleState && consoleState.filtered_run_count > 0);
  const hasActiveFilters = Boolean(
    filters.search ||
      filters.status ||
      filters.publish_status ||
      filters.review_risk ||
      filters.novelty_status ||
      filters.budget_status,
  );

  function updateFilter<K extends keyof AutoResearchOperatorConsoleFilters>(
    key: K,
    value: AutoResearchOperatorConsoleFilters[K],
  ) {
    setDraftFilters((state) => ({
      ...state,
      [key]: value,
    }));
  }

  return (
    <section className="panel" data-testid="operator-console-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Phase 6</p>
          <h2 className="panel-title">Operator Console</h2>
        </div>
        <span className="badge badge-soft">
          {consoleState ? `${consoleState.filtered_run_count}/${consoleState.run_count} shown` : "No runs"}
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

      <form
        className="stack"
        onSubmit={(event) => {
          event.preventDefault();
          onApplyFilters(draftFilters);
        }}
      >
        <p className="inline-title">Run Filters</p>
        <div className="button-row">
          <input
            type="search"
            value={draftFilters.search ?? ""}
            onChange={(event) => updateFilter("search", event.target.value || null)}
            placeholder="Search run id or topic"
            disabled={disabled}
            data-testid="operator-filter-search"
          />
          <select
            value={draftFilters.status ?? ""}
            onChange={(event) =>
              updateFilter(
                "status",
                (event.target.value ? event.target.value : null) as AutoResearchOperatorConsoleFilters["status"],
              )
            }
            disabled={disabled}
            data-testid="operator-filter-status"
          >
            <option value="">All Statuses</option>
            <option value="queued">Queued</option>
            <option value="running">Running</option>
            <option value="done">Done</option>
            <option value="failed">Failed</option>
            <option value="canceled">Canceled</option>
          </select>
          <select
            value={draftFilters.publish_status ?? ""}
            onChange={(event) =>
              updateFilter(
                "publish_status",
                (event.target.value
                  ? event.target.value
                  : null) as AutoResearchOperatorConsoleFilters["publish_status"],
              )
            }
            disabled={disabled}
            data-testid="operator-filter-publish"
          >
            <option value="">All Publish States</option>
            <option value="publish_ready">Publish Ready</option>
            <option value="revision_required">Revision Required</option>
            <option value="blocked">Blocked</option>
          </select>
          <select
            value={draftFilters.review_risk ?? ""}
            onChange={(event) =>
              updateFilter(
                "review_risk",
                (event.target.value
                  ? event.target.value
                  : null) as AutoResearchOperatorConsoleFilters["review_risk"],
              )
            }
            disabled={disabled}
            data-testid="operator-filter-risk"
          >
            <option value="">All Review Risks</option>
            <option value="low">Low Risk</option>
            <option value="medium">Medium Risk</option>
            <option value="high">High Risk</option>
          </select>
          <select
            value={draftFilters.novelty_status ?? ""}
            onChange={(event) =>
              updateFilter(
                "novelty_status",
                (event.target.value
                  ? event.target.value
                  : null) as AutoResearchOperatorConsoleFilters["novelty_status"],
              )
            }
            disabled={disabled}
            data-testid="operator-filter-novelty"
          >
            <option value="">All Novelty States</option>
            <option value="grounded">Grounded</option>
            <option value="incremental">Incremental</option>
            <option value="weak">Weak</option>
            <option value="missing_context">Missing Context</option>
          </select>
          <select
            value={draftFilters.budget_status ?? ""}
            onChange={(event) =>
              updateFilter(
                "budget_status",
                (event.target.value
                  ? event.target.value
                  : null) as AutoResearchOperatorConsoleFilters["budget_status"],
              )
            }
            disabled={disabled}
            data-testid="operator-filter-budget"
          >
            <option value="">All Budget Modes</option>
            <option value="default">Default</option>
            <option value="constrained">Constrained</option>
          </select>
          <button
            type="submit"
            className="ghost-btn"
            disabled={disabled}
            data-testid="operator-apply-filters-button"
          >
            Apply
          </button>
          <button
            type="button"
            className="ghost-btn"
            onClick={onClearFilters}
            disabled={disabled || !hasActiveFilters}
            data-testid="operator-clear-filters-button"
          >
            Clear
          </button>
        </div>
      </form>

      {!hasRuns ? (
        <div className="empty-state">
          <p>No auto-research runs yet.</p>
          <span>
            Start a run for `{projectTopic || "this project"}` to populate execution, candidate, and
            publish inspection state.
          </span>
        </div>
      ) : !hasFilteredRuns ? (
        <div className="empty-state">
          <p>No runs match the current console filters.</p>
          <span>Clear filters or widen the search to resume triage.</span>
        </div>
      ) : (
        <>
          <div className="list-block operator-run-list">
            {activeConsole?.runs.map((run) => (
              <button
                key={run.run_id}
                type="button"
                className={
                  run.run_id === activeConsole.selected_run_id ? "list-item selected" : "list-item"
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
                  <small>
                    risk {run.review_risk ?? "n/a"} / novelty {run.novelty_status ?? "n/a"} / publish{" "}
                    {run.publish_status ?? "n/a"}
                  </small>
                  <small>
                    budget {run.budget_status} / executed {run.executed_candidate_count}
                    {run.candidate_execution_limit ? ` / limit ${run.candidate_execution_limit}` : ""}
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
                  <span className="meta-label">Novelty</span>
                  <strong>{novelty?.status ?? "n/a"}</strong>
                </div>
                <div>
                  <span className="meta-label">Budget</span>
                  <strong>
                    {currentSummary
                      ? `${currentSummary.budget_status} (${currentSummary.executed_candidate_count}${
                          currentSummary.candidate_execution_limit
                            ? `/${currentSummary.candidate_execution_limit}`
                            : ""
                        } candidates, ${currentSummary.max_rounds} rounds)`
                      : "n/a"}
                  </strong>
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

              {novelty ? (
                <div className="meta-block">
                  <span className="meta-label">Novelty Triage</span>
                  <p data-testid="operator-novelty-summary">
                    {novelty.summary} Top matches={novelty.top_related_work.length} uncovered_claims=
                    {novelty.uncovered_claims.length}
                  </p>
                </div>
              ) : null}

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
