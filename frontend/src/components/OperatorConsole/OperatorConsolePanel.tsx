import { useEffect, useState } from "react";

import type {
  AutoResearchBridgeImportRequest,
  AutoResearchOperatorConsole,
  AutoResearchOperatorConsoleFilters,
  AutoResearchPublicationManifest,
  AutoResearchRunRequest,
} from "../../api/types";

type OperatorConsolePanelProps = {
  consoleState: AutoResearchOperatorConsole | null;
  publicationManifest: AutoResearchPublicationManifest | null;
  filters: AutoResearchOperatorConsoleFilters;
  projectTopic?: string | null;
  disabled: boolean;
  onStartRun: (payload?: Partial<AutoResearchRunRequest>) => void;
  onApplyFilters: (filters: AutoResearchOperatorConsoleFilters) => void;
  onClearFilters: () => void;
  onSelectRun: (runId: string) => void;
  onResume: () => void;
  onRetry: () => void;
  onCancel: () => void;
  onRefreshBridge: () => void;
  onRefreshReview: () => void;
  onImportBridgeResult: (payload: AutoResearchBridgeImportRequest) => void;
  onApplyReviewActions: () => void;
  onRebuildPaper: () => void;
  onExportPublish: (payload?: {
    deployment_id?: string | null;
    deployment_label?: string | null;
  }) => void;
  onDownloadPublish: () => void;
  onDownloadPaper: () => void;
  onDownloadCompiledPaper: () => void;
  onDownloadCodePackage: () => void;
  onUpdateControls: (payload: {
    max_rounds?: number | null;
    candidate_execution_limit?: number | null;
    queue_priority?: "low" | "normal" | "high" | null;
  }) => void;
};

function formatScore(value: unknown): string {
  return typeof value === "number" ? value.toFixed(4) : "n/a";
}

function formatTaskFamily(value: string | null | undefined): string {
  if (!value) {
    return "n/a";
  }
  return value.replaceAll("_", " ");
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "n/a";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

export function OperatorConsolePanel({
  consoleState,
  publicationManifest,
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
  onRefreshBridge,
  onRefreshReview,
  onImportBridgeResult,
  onApplyReviewActions,
  onRebuildPaper,
  onExportPublish,
  onDownloadPublish,
  onDownloadPaper,
  onDownloadCompiledPaper,
  onDownloadCodePackage,
  onUpdateControls,
}: OperatorConsolePanelProps) {
  const [draftFilters, setDraftFilters] =
    useState<AutoResearchOperatorConsoleFilters>(filters);
  const [controlDraft, setControlDraft] = useState({
    queue_priority: "normal" as "low" | "normal" | "high",
    max_rounds: "3",
    candidate_execution_limit: "",
  });
  const [launchDraft, setLaunchDraft] = useState({
    mode: "inline" as "inline" | "bridge",
    targetLabel: "external-environment",
  });
  const [bridgeImportDraft, setBridgeImportDraft] = useState({
    summary: "Imported bridge result from external environment",
    objective_score: "0.78",
    primary_metric: "macro_f1",
    objective_system: "candidate_system",
    baseline_system: "baseline",
    baseline_score: "0.70",
    key_findings: "Imported execution preserved benchmark-aligned metrics",
    notes: "",
  });
  const [publishDraft, setPublishDraft] = useState({
    deployment_id: "local_default",
    deployment_label: "Local Deployment",
  });

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
  const bridge = current?.bridge ?? null;
  const review = current?.review ?? null;
  const reviewLoop = current?.review_loop ?? null;
  const publish = current?.publish ?? null;
  const finalPublishReady = Boolean(publish?.final_publish_ready);
  const candidateEntries = current?.registry?.candidates ?? [];
  const counts = current?.registry_views?.counts;
  const lineage = current?.registry?.lineage;
  const novelty = review?.novelty_assessment ?? null;
  const activeConsole = consoleState;
  const currentPublication =
    current && publicationManifest?.run_id === current.run.id
      ? publicationManifest
      : null;
  const queueTelemetry =
    activeConsole?.queue ?? current?.execution.queue ?? null;
  const workerFleet =
    activeConsole?.workers ?? current?.execution.workers ?? [];
  const currentSummary =
    activeConsole?.runs.find((run) => run.run_id === current?.run.id) ?? null;
  const hasRuns = Boolean(consoleState && consoleState.run_count > 0);
  const hasFilteredRuns = Boolean(
    consoleState && consoleState.filtered_run_count > 0,
  );
  const hasActiveFilters = Boolean(
    filters.search ||
    filters.status ||
    filters.publish_status ||
    filters.review_risk ||
    filters.novelty_status ||
    filters.budget_status ||
    filters.queue_priority,
  );

  useEffect(() => {
    if (!currentSummary) {
      setControlDraft({
        queue_priority: "normal",
        max_rounds: "3",
        candidate_execution_limit: "",
      });
      return;
    }
    setControlDraft({
      queue_priority: currentSummary.queue_priority,
      max_rounds: String(currentSummary.max_rounds),
      candidate_execution_limit:
        currentSummary.candidate_execution_limit !== null &&
        currentSummary.candidate_execution_limit !== undefined
          ? String(currentSummary.candidate_execution_limit)
          : "",
    });
  }, [
    currentSummary?.run_id,
    currentSummary?.queue_priority,
    currentSummary?.max_rounds,
    currentSummary?.candidate_execution_limit,
  ]);

  useEffect(() => {
    const currentDeploymentId = publish?.deployment_ids?.[0] ?? "local_default";
    setPublishDraft((state) => ({
      deployment_id: currentDeploymentId,
      deployment_label:
        state.deployment_id === currentDeploymentId
          ? state.deployment_label
          : currentDeploymentId === "local_default"
            ? "Local Deployment"
            : currentDeploymentId.replaceAll("_", " "),
    }));
  }, [publish?.deployment_ids]);

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
          {consoleState
            ? `${consoleState.filtered_run_count}/${consoleState.run_count} shown`
            : "No runs"}
        </span>
      </div>

      <div className="button-row">
        <button
          type="button"
          className="primary-btn"
          onClick={() =>
            onStartRun(
              launchDraft.mode === "bridge"
                ? {
                    max_rounds: 1,
                    candidate_execution_limit: 1,
                    experiment_bridge: {
                      enabled: true,
                      mode: "manual_async",
                      target_kind: "manual",
                      target_label:
                        launchDraft.targetLabel.trim() ||
                        "external-environment",
                      auto_resume_on_result: true,
                      notification_hooks: [
                        {
                          channel: "console",
                          target: null,
                          events: [
                            "session_created",
                            "result_imported",
                            "resume_enqueued",
                            "run_completed",
                            "run_failed",
                            "run_canceled",
                          ],
                        },
                      ],
                    },
                  }
                : undefined,
            )
          }
          disabled={
            disabled ||
            !projectTopic ||
            (launchDraft.mode === "bridge" && !launchDraft.targetLabel.trim())
          }
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
          onClick={onRefreshBridge}
          disabled={disabled || !current?.actions.refresh_bridge}
          data-testid="refresh-bridge-button"
        >
          Refresh Bridge
        </button>
        <button
          type="button"
          className="ghost-btn"
          onClick={onRefreshReview}
          disabled={disabled || !current?.actions.refresh_review}
          data-testid="refresh-review-button"
        >
          Refresh Review
        </button>
        <button
          type="button"
          className="ghost-btn"
          onClick={() =>
            onImportBridgeResult({
              session_id: bridge?.current_session?.session_id ?? null,
              summary: bridgeImportDraft.summary,
              objective_score: Number(bridgeImportDraft.objective_score),
              primary_metric: bridgeImportDraft.primary_metric,
              objective_system: bridgeImportDraft.objective_system,
              baseline_system: bridgeImportDraft.baseline_system,
              baseline_score: bridgeImportDraft.baseline_score
                ? Number(bridgeImportDraft.baseline_score)
                : null,
              key_findings: bridgeImportDraft.key_findings
                .split("\n")
                .map((item) => item.trim())
                .filter(Boolean),
              notes: bridgeImportDraft.notes || null,
            })
          }
          disabled={disabled || !current?.actions.import_bridge_result}
          data-testid="import-bridge-result-button"
        >
          Import Bridge Result
        </button>
        <button
          type="button"
          className="ghost-btn"
          onClick={onApplyReviewActions}
          disabled={disabled || !current?.actions.apply_review_actions}
          data-testid="apply-review-actions-button"
        >
          Apply Review Actions
        </button>
        <button
          type="button"
          className="ghost-btn"
          onClick={onRebuildPaper}
          disabled={disabled || !current?.actions.rebuild_paper}
          data-testid="rebuild-paper-button"
        >
          Rebuild Paper
        </button>
        <button
          type="button"
          className="ghost-btn"
          onClick={() =>
            onExportPublish({
              deployment_id: publishDraft.deployment_id.trim() || null,
              deployment_label: publishDraft.deployment_label.trim() || null,
            })
          }
          disabled={disabled || !current?.actions.export_publish}
          data-testid="export-publish-button"
        >
          Export Final Publish
        </button>
        <button
          type="button"
          className="ghost-btn"
          onClick={onDownloadPublish}
          disabled={disabled || !current?.actions.download_publish}
          data-testid="download-publish-button"
        >
          Download Final Publish
        </button>
      </div>

      <form
        className="stack"
        onSubmit={(event) => {
          event.preventDefault();
          onStartRun(
            launchDraft.mode === "bridge"
              ? {
                  max_rounds: 1,
                  candidate_execution_limit: 1,
                  experiment_bridge: {
                    enabled: true,
                    mode: "manual_async",
                    target_kind: "manual",
                    target_label:
                      launchDraft.targetLabel.trim() || "external-environment",
                    auto_resume_on_result: true,
                    notification_hooks: [
                      {
                        channel: "console",
                        target: null,
                        events: [
                          "session_created",
                          "result_imported",
                          "resume_enqueued",
                          "run_completed",
                          "run_failed",
                          "run_canceled",
                        ],
                      },
                    ],
                  },
                }
              : undefined,
          );
        }}
      >
        <p className="inline-title">Launch Profile</p>
        <div className="button-row">
          <select
            id="operator-launch-mode"
            name="operator_launch_mode"
            value={launchDraft.mode}
            onChange={(event) =>
              setLaunchDraft((state) => ({
                ...state,
                mode: event.target.value as "inline" | "bridge",
              }))
            }
            disabled={disabled}
            data-testid="operator-launch-mode"
          >
            <option value="inline">Inline Execution</option>
            <option value="bridge">Bridge Handoff</option>
          </select>
          <input
            id="operator-launch-bridge-target"
            name="operator_launch_bridge_target"
            type="text"
            value={launchDraft.targetLabel}
            onChange={(event) =>
              setLaunchDraft((state) => ({
                ...state,
                targetLabel: event.target.value,
              }))
            }
            disabled={disabled || launchDraft.mode !== "bridge"}
            placeholder="Bridge target label"
            data-testid="operator-launch-bridge-target"
          />
          <span
            className="auth-copy"
            data-testid="operator-launch-profile-detail"
          >
            {launchDraft.mode === "bridge"
              ? `Manual async bridge to ${launchDraft.targetLabel || "external-environment"}`
              : "Run attempts inline inside the local execution plane"}
          </span>
        </div>
      </form>

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
            id="operator-filter-search"
            name="operator_filter_search"
            type="search"
            value={draftFilters.search ?? ""}
            onChange={(event) =>
              updateFilter("search", event.target.value || null)
            }
            placeholder="Search run id or topic"
            disabled={disabled}
            data-testid="operator-filter-search"
          />
          <select
            id="operator-filter-status"
            name="operator_filter_status"
            value={draftFilters.status ?? ""}
            onChange={(event) =>
              updateFilter(
                "status",
                (event.target.value
                  ? event.target.value
                  : null) as AutoResearchOperatorConsoleFilters["status"],
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
            id="operator-filter-publish"
            name="operator_filter_publish"
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
            id="operator-filter-risk"
            name="operator_filter_risk"
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
            id="operator-filter-novelty"
            name="operator_filter_novelty"
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
            id="operator-filter-budget"
            name="operator_filter_budget"
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
          <select
            id="operator-filter-priority"
            name="operator_filter_priority"
            value={draftFilters.queue_priority ?? ""}
            onChange={(event) =>
              updateFilter(
                "queue_priority",
                (event.target.value
                  ? event.target.value
                  : null) as AutoResearchOperatorConsoleFilters["queue_priority"],
              )
            }
            disabled={disabled}
            data-testid="operator-filter-priority"
          >
            <option value="">All Priorities</option>
            <option value="high">High</option>
            <option value="normal">Normal</option>
            <option value="low">Low</option>
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

      {activeConsole ? (
        <>
          <div
            className="summary-banner operator-summary-grid"
            data-testid="operator-queue-summary"
          >
            <div>
              <span className="meta-label">Queue Depth</span>
              <strong>{queueTelemetry?.queue_depth ?? 0}</strong>
            </div>
            <div>
              <span className="meta-label">Active Jobs</span>
              <strong>
                {(queueTelemetry?.leased_jobs ?? 0) +
                  (queueTelemetry?.running_jobs ?? 0)}
              </strong>
            </div>
            <div>
              <span className="meta-label">Queued / Running</span>
              <strong>
                {queueTelemetry?.queued_jobs ?? 0} /{" "}
                {queueTelemetry?.running_jobs ?? 0}
              </strong>
            </div>
            <div>
              <span className="meta-label">Done / Failed</span>
              <strong>
                {queueTelemetry?.succeeded_jobs ?? 0} /{" "}
                {queueTelemetry?.failed_jobs ?? 0}
              </strong>
            </div>
            <div>
              <span className="meta-label">Workers</span>
              <strong>
                {queueTelemetry?.worker_count ?? 0} total /{" "}
                {queueTelemetry?.active_workers ?? 0} active
              </strong>
            </div>
            <div>
              <span className="meta-label">Idle / Stale</span>
              <strong>
                {queueTelemetry?.idle_workers ?? 0} /{" "}
                {queueTelemetry?.stale_workers ?? 0}
              </strong>
            </div>
            <div>
              <span className="meta-label">Processed / Recovered</span>
              <strong>
                {queueTelemetry?.total_processed_jobs ?? 0} /{" "}
                {queueTelemetry?.total_recovered_jobs ?? 0}
              </strong>
            </div>
            <div>
              <span className="meta-label">Last Recovery</span>
              <strong>
                {formatTimestamp(queueTelemetry?.last_recovered_at)}
              </strong>
            </div>
            <div>
              <span className="meta-label">Last Finish</span>
              <strong>
                {formatTimestamp(queueTelemetry?.last_job_finished_at)}
              </strong>
            </div>
          </div>

          <div className="list-block" data-testid="operator-worker-fleet">
            {workerFleet.length ? (
              workerFleet.map((worker) => (
                <div
                  key={worker.worker_id ?? "worker-unknown"}
                  className="evidence-card"
                  data-testid={`operator-worker-${worker.worker_id ?? "unknown"}`}
                >
                  <strong>
                    {worker.worker_id ?? "worker-unknown"}{" "}
                    {worker.stale ? "(stale)" : ""}
                  </strong>
                  <small>
                    status {worker.status} / queue {worker.queue_depth} /
                    processed {worker.processed_jobs} / recovered{" "}
                    {worker.recovered_job_count}
                  </small>
                  <small>
                    job {worker.current_job_id ?? "idle"} / run{" "}
                    {worker.current_run_id ?? "n/a"}
                  </small>
                  <small>
                    heartbeat {formatTimestamp(worker.heartbeat_at)} / lease
                    expires {formatTimestamp(worker.lease_expires_at)}
                  </small>
                  <small>
                    started {formatTimestamp(worker.last_started_at)} /
                    completed {formatTimestamp(worker.last_completed_at)} /
                    recovered {formatTimestamp(worker.last_recovered_at)}
                  </small>
                  <small>lease {worker.current_lease_id ?? "n/a"}</small>
                  <small>error {worker.last_error ?? "n/a"}</small>
                </div>
              ))
            ) : (
              <div className="empty-state">
                <p>No execution workers registered yet.</p>
                <span>
                  The queue will populate worker telemetry after the first
                  execution lease.
                </span>
              </div>
            )}
          </div>
        </>
      ) : null}

      {!hasRuns ? (
        <div className="empty-state">
          <p>No auto-research runs yet.</p>
          <span>
            Start a run for `{projectTopic || "this project"}` to populate
            execution, candidate, and publish inspection state.
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
                  run.run_id === activeConsole.selected_run_id
                    ? "list-item selected"
                    : "list-item"
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
                    selected {run.selected_count} / failed {run.failed_count} /
                    active {run.active_count}
                  </small>
                  <small>
                    risk {run.review_risk ?? "n/a"} / novelty{" "}
                    {run.novelty_status ?? "n/a"} / publish{" "}
                    {run.publish_status ?? "n/a"}
                  </small>
                  <small>
                    review r{run.review_round} / open {run.open_issue_count} /
                    pending {run.pending_action_count}
                  </small>
                  <small>
                    benchmark {run.benchmark_name ?? "n/a"} / family{" "}
                    {formatTaskFamily(run.task_family)}
                  </small>
                  <small>
                    budget {run.budget_status} / executed{" "}
                    {run.executed_candidate_count}
                    {run.candidate_execution_limit
                      ? ` / limit ${run.candidate_execution_limit}`
                      : ""}
                  </small>
                  <small>
                    priority {run.queue_priority} / rounds {run.max_rounds}
                  </small>
                  <small>
                    bridge {run.bridge_status ?? "n/a"}
                    {run.bridge_target_label
                      ? ` / ${run.bridge_target_label}`
                      : ""}
                  </small>
                  <small>recoveries {run.recovery_count}</small>
                </div>
              </button>
            ))}
          </div>

          {current ? (
            <>
              <form
                className="stack"
                onSubmit={(event) => {
                  event.preventDefault();
                  onUpdateControls({
                    queue_priority: controlDraft.queue_priority,
                    max_rounds: Number(controlDraft.max_rounds),
                    candidate_execution_limit:
                      controlDraft.candidate_execution_limit
                        ? Number(controlDraft.candidate_execution_limit)
                        : null,
                  });
                }}
              >
                <p className="inline-title">Run Controls</p>
                <div className="button-row">
                  <select
                    id="operator-control-priority"
                    name="operator_control_priority"
                    value={controlDraft.queue_priority}
                    onChange={(event) =>
                      setControlDraft((state) => ({
                        ...state,
                        queue_priority: event.target.value as
                          | "low"
                          | "normal"
                          | "high",
                      }))
                    }
                    disabled={disabled || !current.actions.update_controls}
                    data-testid="operator-control-priority"
                  >
                    <option value="high">High Priority</option>
                    <option value="normal">Normal Priority</option>
                    <option value="low">Low Priority</option>
                  </select>
                  <input
                    id="operator-control-rounds"
                    name="operator_control_rounds"
                    type="number"
                    min={1}
                    step={1}
                    value={controlDraft.max_rounds}
                    onChange={(event) =>
                      setControlDraft((state) => ({
                        ...state,
                        max_rounds: event.target.value,
                      }))
                    }
                    disabled={disabled || !current.actions.update_controls}
                    placeholder="Max rounds"
                    data-testid="operator-control-rounds"
                  />
                  <input
                    id="operator-control-candidate-limit"
                    name="operator_control_candidate_limit"
                    type="number"
                    min={1}
                    step={1}
                    value={controlDraft.candidate_execution_limit}
                    onChange={(event) =>
                      setControlDraft((state) => ({
                        ...state,
                        candidate_execution_limit: event.target.value,
                      }))
                    }
                    disabled={disabled || !current.actions.update_controls}
                    placeholder="Candidate limit"
                    data-testid="operator-control-candidate-limit"
                  />
                  <button
                    type="submit"
                    className="ghost-btn"
                    disabled={
                      disabled ||
                      !current.actions.update_controls ||
                      !controlDraft.max_rounds
                    }
                    data-testid="operator-apply-controls-button"
                  >
                    Apply Controls
                  </button>
                </div>
              </form>

              <form
                className="stack"
                onSubmit={(event) => {
                  event.preventDefault();
                  onExportPublish({
                    deployment_id: publishDraft.deployment_id.trim() || null,
                    deployment_label:
                      publishDraft.deployment_label.trim() || null,
                  });
                }}
              >
                <p className="inline-title">Publish Deployment</p>
                <div className="button-row">
                  <input
                    id="publish-deployment-id"
                    name="publish_deployment_id"
                    type="text"
                    value={publishDraft.deployment_id}
                    onChange={(event) =>
                      setPublishDraft((state) => ({
                        ...state,
                        deployment_id: event.target.value,
                      }))
                    }
                    disabled={disabled || !current.actions.export_publish}
                    placeholder="Deployment id"
                    data-testid="publish-deployment-id"
                  />
                  <input
                    id="publish-deployment-label"
                    name="publish_deployment_label"
                    type="text"
                    value={publishDraft.deployment_label}
                    onChange={(event) =>
                      setPublishDraft((state) => ({
                        ...state,
                        deployment_label: event.target.value,
                      }))
                    }
                    disabled={disabled || !current.actions.export_publish}
                    placeholder="Deployment label"
                    data-testid="publish-deployment-label"
                  />
                  <span
                    className="auth-copy"
                    data-testid="publish-deployment-summary"
                  >
                    {!finalPublishReady
                      ? "Resolve review loop and citation blockers before final publish export is enabled."
                      : publish?.deployment_ids?.length
                        ? `Registered in ${publish.deployment_ids.join(", ")}`
                        : "Final export will register the current paper/run/code package into a deployment"}
                  </span>
                </div>
              </form>

              {currentPublication ? (
                <>
                  <div
                    className="summary-banner operator-summary-grid"
                    data-testid="operator-publication-summary"
                  >
                    <div>
                      <span className="meta-label">Publication</span>
                      <strong>{currentPublication.publication_id}</strong>
                    </div>
                    <div>
                      <span className="meta-label">Bundle</span>
                      <strong>{currentPublication.bundle_kind}</strong>
                    </div>
                    <div>
                      <span className="meta-label">Paper Asset</span>
                      <strong>
                        {currentPublication.paper_path
                          ? "available"
                          : "missing"}
                      </strong>
                    </div>
                    <div>
                      <span className="meta-label">Compiled PDF</span>
                      <strong>
                        {currentPublication.compiled_paper_path
                          ? "available"
                          : "missing"}
                      </strong>
                    </div>
                    <div>
                      <span className="meta-label">Compile Outputs</span>
                      <strong>
                        {currentPublication.paper_compile_output_paths.length}
                      </strong>
                    </div>
                    <div>
                      <span className="meta-label">Code Package</span>
                      <strong>
                        {currentPublication.code_package_path
                          ? "available"
                          : "missing"}
                      </strong>
                    </div>
                    <div>
                      <span className="meta-label">Archive</span>
                      <strong>
                        {currentPublication.archive_current
                          ? "current"
                          : "stale"}
                      </strong>
                    </div>
                    <div>
                      <span className="meta-label">Final Ready</span>
                      <strong>
                        {currentPublication.final_publish_ready ? "yes" : "no"}
                      </strong>
                    </div>
                    <div>
                      <span className="meta-label">Updated</span>
                      <strong>
                        {formatTimestamp(currentPublication.updated_at)}
                      </strong>
                    </div>
                  </div>

                  <div className="button-row">
                    <button
                      type="button"
                      className="ghost-btn"
                      onClick={onDownloadPaper}
                      disabled={disabled || !currentPublication.paper_path}
                      data-testid="download-paper-button"
                    >
                      Download Paper
                    </button>
                    <button
                      type="button"
                      className="ghost-btn"
                      onClick={onDownloadCompiledPaper}
                      disabled={
                        disabled || !currentPublication.compiled_paper_path
                      }
                      data-testid="download-compiled-paper-button"
                    >
                      Download Compiled PDF
                    </button>
                    <button
                      type="button"
                      className="ghost-btn"
                      onClick={onDownloadCodePackage}
                      disabled={
                        disabled || !currentPublication.code_package_path
                      }
                      data-testid="download-code-package-button"
                    >
                      Download Code Package
                    </button>
                  </div>

                  <div className="meta-block">
                    <span className="meta-label">Publication Assets</span>
                    <code data-testid="operator-publication-assets">
                      archive={currentPublication.publish_archive_path} | paper=
                      {currentPublication.paper_path ?? "n/a"} | compiled=
                      {currentPublication.compiled_paper_path ?? "n/a"} | code=
                      {currentPublication.code_package_path ?? "n/a"}
                    </code>
                  </div>

                  <div className="meta-block">
                    <span className="meta-label">Compile Outputs</span>
                    <code data-testid="operator-compile-output-paths">
                      {currentPublication.paper_compile_output_paths.length
                        ? currentPublication.paper_compile_output_paths.join(
                            " | ",
                          )
                        : "n/a"}
                    </code>
                  </div>
                </>
              ) : (
                <div
                  className="empty-state"
                  data-testid="operator-publication-empty"
                >
                  <p>No publication manifest for the current run.</p>
                  <span>
                    {!finalPublishReady
                      ? "Final publish remains unavailable until the run is citation-grounded and the review loop is clear."
                      : publish?.publication_id
                        ? "Refresh the run or export publish again if paper assets were changed."
                        : "Export Final Publish to materialize a publication manifest and paper assets."}
                  </span>
                </div>
              )}

              <div className="summary-banner operator-summary-grid">
                <div>
                  <span className="meta-label">Run Status</span>
                  <strong>{current.run.status}</strong>
                </div>
                <div>
                  <span className="meta-label">Benchmark</span>
                  <strong data-testid="operator-current-benchmark">
                    {currentSummary?.benchmark_name ??
                      current.registry.benchmark_name ??
                      "n/a"}
                  </strong>
                </div>
                <div>
                  <span className="meta-label">Task Family</span>
                  <strong data-testid="operator-current-task-family">
                    {formatTaskFamily(
                      currentSummary?.task_family ??
                        current.registry.task_family,
                    )}
                  </strong>
                </div>
                <div>
                  <span className="meta-label">Selected Candidate</span>
                  <strong>
                    {current.registry.selected_candidate_id ?? "n/a"}
                  </strong>
                </div>
                <div>
                  <span className="meta-label">Execution</span>
                  <strong>
                    {current.execution.active_job_id ??
                      current.execution.worker?.status ??
                      "idle"}
                  </strong>
                </div>
                <div>
                  <span className="meta-label">Bridge</span>
                  <strong data-testid="operator-bridge-summary">
                    {bridge
                      ? `${bridge.status}${bridge.current_session ? ` / ${bridge.current_session.status}` : ""}`
                      : "disabled"}
                  </strong>
                </div>
                <div>
                  <span className="meta-label">Bridge Target</span>
                  <strong>{bridge?.config?.target_label ?? "n/a"}</strong>
                </div>
                <div>
                  <span className="meta-label">Publish</span>
                  <strong>{publish?.status ?? "not built"}</strong>
                </div>
                <div>
                  <span className="meta-label">Archive</span>
                  <strong data-testid="operator-publish-archive-detail">
                    {publish
                      ? `${publish.archive_status} / review r${publish.review_round}${
                          publish.archive_review_round !== null &&
                          publish.archive_review_round !== undefined
                            ? ` / export r${publish.archive_review_round}`
                            : ""
                        }`
                      : "n/a"}
                  </strong>
                </div>
              </div>

              <div className="summary-banner operator-summary-grid">
                <div>
                  <span className="meta-label">Candidates</span>
                  <strong>
                    {counts?.total_candidates ?? candidateEntries.length}
                  </strong>
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
                <div>
                  <span className="meta-label">Priority</span>
                  <strong>{currentSummary?.queue_priority ?? "normal"}</strong>
                </div>
                <div>
                  <span className="meta-label">Recoveries</span>
                  <strong>{currentSummary?.recovery_count ?? 0}</strong>
                </div>
                <div>
                  <span className="meta-label">Review Loop</span>
                  <strong data-testid="operator-review-loop-summary">
                    {reviewLoop
                      ? `r${reviewLoop.current_round} / open ${reviewLoop.open_issue_count} / pending ${reviewLoop.pending_action_count}`
                      : "n/a"}
                  </strong>
                </div>
                <div>
                  <span className="meta-label">Completed Actions</span>
                  <strong>{reviewLoop?.completed_action_count ?? 0}</strong>
                </div>
              </div>

              <div className="meta-block">
                <span className="meta-label">Lineage</span>
                <code data-testid="operator-lineage-summary">
                  selected={lineage?.selected_candidate_id ?? "n/a"}{" "}
                  artifact_from=
                  {lineage?.top_level_artifact_candidate_id ?? "n/a"}{" "}
                  paper_from=
                  {lineage?.top_level_paper_candidate_id ?? "n/a"} edges=
                  {lineage?.edges.length ?? 0}
                </code>
              </div>

              {bridge ? (
                <div className="meta-block">
                  <span className="meta-label">Bridge State</span>
                  <p data-testid="operator-bridge-detail">
                    status={bridge.status} sessions={bridge.session_count} open=
                    {bridge.open_session_count} imported=
                    {bridge.imported_session_count} checkpoints=
                    {bridge.checkpoint_count} notifications=
                    {bridge.notification_count}
                    {bridge.current_session
                      ? ` current=${bridge.current_session.session_id} round=${bridge.current_session.round_index} target=${bridge.config?.target_label ?? "n/a"}`
                      : ""}
                  </p>
                  {bridge.current_session ? (
                    <code data-testid="operator-bridge-session-paths">
                      handoff={bridge.current_session.handoff_dir} result=
                      {bridge.current_session.result_path}
                    </code>
                  ) : null}
                </div>
              ) : null}

              {current.actions.import_bridge_result ? (
                <form
                  className="stack"
                  onSubmit={(event) => {
                    event.preventDefault();
                    onImportBridgeResult({
                      session_id: bridge?.current_session?.session_id ?? null,
                      summary: bridgeImportDraft.summary,
                      objective_score: Number(
                        bridgeImportDraft.objective_score,
                      ),
                      primary_metric: bridgeImportDraft.primary_metric,
                      objective_system: bridgeImportDraft.objective_system,
                      baseline_system: bridgeImportDraft.baseline_system,
                      baseline_score: bridgeImportDraft.baseline_score
                        ? Number(bridgeImportDraft.baseline_score)
                        : null,
                      key_findings: bridgeImportDraft.key_findings
                        .split("\n")
                        .map((item) => item.trim())
                        .filter(Boolean),
                      notes: bridgeImportDraft.notes || null,
                    });
                  }}
                >
                  <p className="inline-title">Bridge Import</p>
                  <div className="button-row">
                    <input
                      id="bridge-import-summary"
                      name="bridge_import_summary"
                      type="text"
                      value={bridgeImportDraft.summary}
                      onChange={(event) =>
                        setBridgeImportDraft((state) => ({
                          ...state,
                          summary: event.target.value,
                        }))
                      }
                      disabled={
                        disabled || !current.actions.import_bridge_result
                      }
                      placeholder="Result summary"
                      data-testid="bridge-import-summary"
                    />
                    <input
                      id="bridge-import-score"
                      name="bridge_import_score"
                      type="number"
                      step="0.0001"
                      value={bridgeImportDraft.objective_score}
                      onChange={(event) =>
                        setBridgeImportDraft((state) => ({
                          ...state,
                          objective_score: event.target.value,
                        }))
                      }
                      disabled={
                        disabled || !current.actions.import_bridge_result
                      }
                      placeholder="Objective score"
                      data-testid="bridge-import-score"
                    />
                    <input
                      id="bridge-import-metric"
                      name="bridge_import_metric"
                      type="text"
                      value={bridgeImportDraft.primary_metric}
                      onChange={(event) =>
                        setBridgeImportDraft((state) => ({
                          ...state,
                          primary_metric: event.target.value,
                        }))
                      }
                      disabled={
                        disabled || !current.actions.import_bridge_result
                      }
                      placeholder="Primary metric"
                      data-testid="bridge-import-metric"
                    />
                  </div>
                  <div className="button-row">
                    <input
                      id="bridge-import-system"
                      name="bridge_import_system"
                      type="text"
                      value={bridgeImportDraft.objective_system}
                      onChange={(event) =>
                        setBridgeImportDraft((state) => ({
                          ...state,
                          objective_system: event.target.value,
                        }))
                      }
                      disabled={
                        disabled || !current.actions.import_bridge_result
                      }
                      placeholder="Objective system"
                      data-testid="bridge-import-system"
                    />
                    <input
                      id="bridge-import-baseline"
                      name="bridge_import_baseline"
                      type="text"
                      value={bridgeImportDraft.baseline_system}
                      onChange={(event) =>
                        setBridgeImportDraft((state) => ({
                          ...state,
                          baseline_system: event.target.value,
                        }))
                      }
                      disabled={
                        disabled || !current.actions.import_bridge_result
                      }
                      placeholder="Baseline system"
                      data-testid="bridge-import-baseline"
                    />
                    <input
                      id="bridge-import-baseline-score"
                      name="bridge_import_baseline_score"
                      type="number"
                      step="0.0001"
                      value={bridgeImportDraft.baseline_score}
                      onChange={(event) =>
                        setBridgeImportDraft((state) => ({
                          ...state,
                          baseline_score: event.target.value,
                        }))
                      }
                      disabled={
                        disabled || !current.actions.import_bridge_result
                      }
                      placeholder="Baseline score"
                      data-testid="bridge-import-baseline-score"
                    />
                  </div>
                  <textarea
                    id="bridge-import-findings"
                    name="bridge_import_findings"
                    value={bridgeImportDraft.key_findings}
                    onChange={(event) =>
                      setBridgeImportDraft((state) => ({
                        ...state,
                        key_findings: event.target.value,
                      }))
                    }
                    disabled={disabled || !current.actions.import_bridge_result}
                    placeholder="One key finding per line"
                    data-testid="bridge-import-findings"
                  />
                </form>
              ) : null}

              {novelty ? (
                <div className="meta-block">
                  <span className="meta-label">Novelty Triage</span>
                  <p data-testid="operator-novelty-summary">
                    {novelty.summary} Top matches=
                    {novelty.top_related_work.length} uncovered_claims=
                    {novelty.uncovered_claims.length}
                  </p>
                </div>
              ) : null}

              {reviewLoop ? (
                <div className="meta-block">
                  <span className="meta-label">Review Loop</span>
                  <p data-testid="operator-review-loop-detail">
                    fingerprint={reviewLoop.latest_review_fingerprint ?? "n/a"}{" "}
                    rounds=
                    {reviewLoop.rounds.length} open=
                    {reviewLoop.open_issue_count} resolved=
                    {reviewLoop.resolved_issue_count} pending=
                    {reviewLoop.pending_action_count} completed=
                    {reviewLoop.completed_action_count}
                  </p>
                </div>
              ) : null}

              <div className="stack">
                <p className="inline-title">Candidate Comparison</p>
                {candidateEntries.map((candidate) => (
                  <div
                    key={candidate.candidate_id}
                    className="evidence-card"
                    data-testid={`operator-candidate-${candidate.candidate_id}`}
                  >
                    <div className="panel-header">
                      <div>
                        <strong>{candidate.title}</strong>
                        <p className="auth-copy">
                          {candidate.candidate_id} · {candidate.status}
                          {candidate.selected ? " · selected" : ""}
                        </p>
                      </div>
                      <span className="badge badge-soft">
                        {formatScore(candidate.objective_score)}
                      </span>
                    </div>
                    <p className="auth-copy">
                      outcome={candidate.decision_outcome ?? "n/a"} · attempts=
                      {candidate.attempt_count} · artifact=
                      {candidate.artifact_status ?? "n/a"}
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

              <div className="stack">
                <p className="inline-title">Revision Actions</p>
                {reviewLoop && reviewLoop.actions.length > 0 ? (
                  reviewLoop.actions.slice(0, 4).map((action) => (
                    <div
                      key={action.action_id}
                      className="suggestion-card"
                      data-testid={`operator-review-action-${action.action_id}`}
                    >
                      <strong>
                        {action.status.toUpperCase()} · {action.priority} ·{" "}
                        {action.title}
                      </strong>
                      <p>
                        round {action.first_seen_round} {"->"}{" "}
                        {action.completed_round ?? action.last_seen_round} ·
                        issues=
                        {action.issue_ids.length}
                      </p>
                    </div>
                  ))
                ) : (
                  <div className="empty-state">
                    <p>No revision actions yet.</p>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="empty-state">
              <p>No run selected.</p>
              <span>
                Select a run to inspect execution, lineage, review, and publish
                state.
              </span>
            </div>
          )}
        </>
      )}
    </section>
  );
}
