import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import type {
  AutoResearchBridgeImportRequest,
  AutoResearchOperatorConsole,
  AutoResearchOperatorConsoleFilters,
  AutoResearchPublicationManifest,
  AutoResearchRunRequest,
} from "../../api/types";

type TabKey = "overview" | "controls" | "execution" | "review";

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
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
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

  const bridgePayload: AutoResearchBridgeImportRequest = {
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
  };

  const bridgeLaunchPayload: Partial<AutoResearchRunRequest> = {
    max_rounds: 1,
    candidate_execution_limit: 1,
    experiment_bridge: {
      enabled: true,
      mode: "manual_async",
      target_kind: "manual",
      target_label: launchDraft.targetLabel.trim() || "external-environment",
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
  };

  const tabs: { key: TabKey; label: string }[] = [
    { key: "overview", label: t("operator.tabOverview") },
    { key: "controls", label: t("operator.tabControls") },
    { key: "execution", label: t("operator.tabExecution") },
    { key: "review", label: t("operator.tabReviewPublish") },
  ];

  return (
    <section className="panel" data-testid="operator-console-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{t("operator.eyebrow")}</p>
          <h2 className="panel-title">{t("operator.title")}</h2>
        </div>
        <span className="badge badge-soft">
          {consoleState
            ? `${consoleState.filtered_run_count}/${consoleState.run_count} shown`
            : t("operator.noRuns")}
        </span>
      </div>

      <div className="tab-bar">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={`tab ${activeTab === tab.key ? "active" : ""}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Overview Tab ── */}
      {activeTab === "overview" && (
        <>
          <div className="button-row">
            <button
              type="button"
              className="primary-btn"
              onClick={() =>
                onStartRun(
                  launchDraft.mode === "bridge"
                    ? bridgeLaunchPayload
                    : undefined,
                )
              }
              disabled={
                disabled ||
                !projectTopic ||
                (launchDraft.mode === "bridge" &&
                  !launchDraft.targetLabel.trim())
              }
              data-testid="start-autoresearch-button"
            >
              {t("operator.startRun")}
            </button>
            <button
              type="button"
              className="ghost-btn"
              onClick={onResume}
              disabled={disabled || !current?.actions.resume}
              data-testid="resume-autoresearch-button"
            >
              {t("operator.resume")}
            </button>
            <button
              type="button"
              className="ghost-btn"
              onClick={onRetry}
              disabled={disabled || !current?.actions.retry}
              data-testid="retry-autoresearch-button"
            >
              {t("operator.retry")}
            </button>
            <button
              type="button"
              className="ghost-btn"
              onClick={onCancel}
              disabled={disabled || !current?.actions.cancel}
              data-testid="cancel-autoresearch-button"
            >
              {t("operator.cancel")}
            </button>
          </div>

          {!hasRuns ? (
            <div className="empty-state">
              <p>{t("operator.noRunsTitle")}</p>
              <span>
                {t("operator.noRunsDetail", {
                  topic: projectTopic || "this project",
                })}
              </span>
            </div>
          ) : !hasFilteredRuns ? (
            <div className="empty-state">
              <p>{t("operator.noFilteredTitle")}</p>
              <span>{t("operator.noFilteredDetail")}</span>
            </div>
          ) : (
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
                      selected {run.selected_count} / failed {run.failed_count}{" "}
                      / active {run.active_count}
                    </small>
                    <small>
                      risk {run.review_risk ?? "n/a"} / novelty{" "}
                      {run.novelty_status ?? "n/a"} / publish{" "}
                      {run.publish_status ?? "n/a"}
                    </small>
                    <small>
                      benchmark {run.benchmark_name ?? "n/a"} / family{" "}
                      {formatTaskFamily(run.task_family)}
                    </small>
                    <small>
                      priority {run.queue_priority} / rounds {run.max_rounds}
                    </small>
                  </div>
                </button>
              ))}
            </div>
          )}

          {current && (
            <div className="summary-banner operator-summary-grid">
              <div>
                <span className="meta-label">{t("operator.runStatus")}</span>
                <strong>{current.run.status}</strong>
              </div>
              <div>
                <span className="meta-label">{t("operator.benchmark")}</span>
                <strong data-testid="operator-current-benchmark">
                  {currentSummary?.benchmark_name ??
                    current.registry.benchmark_name ??
                    "n/a"}
                </strong>
              </div>
              <div>
                <span className="meta-label">{t("operator.taskFamily")}</span>
                <strong data-testid="operator-current-task-family">
                  {formatTaskFamily(
                    currentSummary?.task_family ?? current.registry.task_family,
                  )}
                </strong>
              </div>
              <div>
                <span className="meta-label">
                  {t("operator.selectedCandidate")}
                </span>
                <strong>
                  {current.registry.selected_candidate_id ?? "n/a"}
                </strong>
              </div>
              <div>
                <span className="meta-label">{t("operator.bridge")}</span>
                <strong data-testid="operator-bridge-summary">
                  {bridge
                    ? `${bridge.status}${bridge.current_session ? ` / ${bridge.current_session.status}` : ""}`
                    : t("operator.disabled")}
                </strong>
              </div>
              <div>
                <span className="meta-label">{t("operator.publish")}</span>
                <strong>{publish?.status ?? t("operator.notBuilt")}</strong>
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Controls Tab ── */}
      {activeTab === "controls" && (
        <>
          <form
            className="stack"
            onSubmit={(event) => {
              event.preventDefault();
              onStartRun(
                launchDraft.mode === "bridge" ? bridgeLaunchPayload : undefined,
              );
            }}
          >
            <p className="inline-title">{t("operator.launchProfile")}</p>
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
                <option value="inline">{t("operator.inlineExecution")}</option>
                <option value="bridge">{t("operator.bridgeHandoff")}</option>
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
                placeholder={t("operator.bridgeTargetPlaceholder")}
                data-testid="operator-launch-bridge-target"
              />
              <span
                className="auth-copy"
                data-testid="operator-launch-profile-detail"
              >
                {launchDraft.mode === "bridge"
                  ? t("operator.bridgeDetail", {
                      target: launchDraft.targetLabel || "external-environment",
                    })
                  : t("operator.inlineDetail")}
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
            <p className="inline-title">{t("operator.runFilters")}</p>
            <div className="button-row">
              <input
                id="operator-filter-search"
                name="operator_filter_search"
                type="search"
                value={draftFilters.search ?? ""}
                onChange={(event) =>
                  updateFilter("search", event.target.value || null)
                }
                placeholder={t("operator.filterPlaceholder")}
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
                <option value="">{t("operator.allStatuses")}</option>
                <option value="queued">{t("operator.queued")}</option>
                <option value="running">{t("operator.running")}</option>
                <option value="done">{t("operator.done")}</option>
                <option value="failed">{t("operator.failed")}</option>
                <option value="canceled">{t("operator.canceled")}</option>
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
                <option value="">{t("operator.allPublishStates")}</option>
                <option value="publish_ready">
                  {t("operator.publishReady")}
                </option>
                <option value="revision_required">
                  {t("operator.revisionRequired")}
                </option>
                <option value="blocked">{t("operator.blocked")}</option>
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
                <option value="">{t("operator.allReviewRisks")}</option>
                <option value="low">{t("operator.lowRisk")}</option>
                <option value="medium">{t("operator.mediumRisk")}</option>
                <option value="high">{t("operator.highRisk")}</option>
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
                <option value="">{t("operator.allNoveltyStates")}</option>
                <option value="grounded">{t("operator.grounded")}</option>
                <option value="incremental">{t("operator.incremental")}</option>
                <option value="weak">{t("operator.weak")}</option>
                <option value="missing_context">
                  {t("operator.missingContext")}
                </option>
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
                <option value="">{t("operator.allBudgetModes")}</option>
                <option value="default">{t("operator.defaultBudget")}</option>
                <option value="constrained">
                  {t("operator.constrainedBudget")}
                </option>
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
                <option value="">{t("operator.allPriorities")}</option>
                <option value="high">{t("operator.highPriority")}</option>
                <option value="normal">{t("operator.normalPriority")}</option>
                <option value="low">{t("operator.lowPriority")}</option>
              </select>
              <button
                type="submit"
                className="ghost-btn"
                disabled={disabled}
                data-testid="operator-apply-filters-button"
              >
                {t("operator.apply")}
              </button>
              <button
                type="button"
                className="ghost-btn"
                onClick={onClearFilters}
                disabled={disabled || !hasActiveFilters}
                data-testid="operator-clear-filters-button"
              >
                {t("operator.clear")}
              </button>
            </div>
          </form>

          {current && (
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
              <p className="inline-title">{t("operator.runControls")}</p>
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
                  <option value="high">{t("operator.highPriority")}</option>
                  <option value="normal">{t("operator.normalPriority")}</option>
                  <option value="low">{t("operator.lowPriority")}</option>
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
                  placeholder={t("operator.maxRoundsPlaceholder")}
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
                  placeholder={t("operator.candidateLimitPlaceholder")}
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
                  {t("operator.applyControls")}
                </button>
              </div>
            </form>
          )}

          {current && (
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
              <p className="inline-title">{t("operator.publishDeployment")}</p>
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
                  placeholder={t("operator.deploymentIdPlaceholder")}
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
                  placeholder={t("operator.deploymentLabelPlaceholder")}
                  data-testid="publish-deployment-label"
                />
                <span
                  className="auth-copy"
                  data-testid="publish-deployment-summary"
                >
                  {!finalPublishReady
                    ? t("operator.publishNotReady")
                    : publish?.deployment_ids?.length
                      ? t("operator.publishRegistered", {
                          deployments: publish.deployment_ids.join(", "),
                        })
                      : t("operator.publishExportDetail")}
                </span>
              </div>
            </form>
          )}
        </>
      )}

      {/* ── Execution Tab ── */}
      {activeTab === "execution" && (
        <>
          {activeConsole ? (
            <>
              <div
                className="summary-banner operator-summary-grid"
                data-testid="operator-queue-summary"
              >
                <div>
                  <span className="meta-label">{t("operator.queueDepth")}</span>
                  <strong>{queueTelemetry?.queue_depth ?? 0}</strong>
                </div>
                <div>
                  <span className="meta-label">{t("operator.activeJobs")}</span>
                  <strong>
                    {(queueTelemetry?.leased_jobs ?? 0) +
                      (queueTelemetry?.running_jobs ?? 0)}
                  </strong>
                </div>
                <div>
                  <span className="meta-label">
                    {t("operator.queuedRunning")}
                  </span>
                  <strong>
                    {queueTelemetry?.queued_jobs ?? 0} /{" "}
                    {queueTelemetry?.running_jobs ?? 0}
                  </strong>
                </div>
                <div>
                  <span className="meta-label">{t("operator.doneFailed")}</span>
                  <strong>
                    {queueTelemetry?.succeeded_jobs ?? 0} /{" "}
                    {queueTelemetry?.failed_jobs ?? 0}
                  </strong>
                </div>
                <div>
                  <span className="meta-label">{t("operator.workers")}</span>
                  <strong>
                    {queueTelemetry?.worker_count ?? 0} total /{" "}
                    {queueTelemetry?.active_workers ?? 0} active
                  </strong>
                </div>
                <div>
                  <span className="meta-label">{t("operator.idleStale")}</span>
                  <strong>
                    {queueTelemetry?.idle_workers ?? 0} /{" "}
                    {queueTelemetry?.stale_workers ?? 0}
                  </strong>
                </div>
                <div>
                  <span className="meta-label">
                    {t("operator.processedRecovered")}
                  </span>
                  <strong>
                    {queueTelemetry?.total_processed_jobs ?? 0} /{" "}
                    {queueTelemetry?.total_recovered_jobs ?? 0}
                  </strong>
                </div>
                <div>
                  <span className="meta-label">
                    {t("operator.lastRecovery")}
                  </span>
                  <strong>
                    {formatTimestamp(queueTelemetry?.last_recovered_at)}
                  </strong>
                </div>
                <div>
                  <span className="meta-label">{t("operator.lastFinish")}</span>
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
                        {worker.stale ? t("operator.staleLabel") : ""}
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
                    <p>{t("operator.noWorkersTitle")}</p>
                    <span>{t("operator.noWorkersDetail")}</span>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="empty-state">
              <p>{t("operator.noRunsTitle")}</p>
              <span>
                {t("operator.noRunsDetail", {
                  topic: projectTopic || "this project",
                })}
              </span>
            </div>
          )}

          {current && bridge && (
            <div className="meta-block">
              <span className="meta-label">{t("operator.bridgeState")}</span>
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
          )}

          {current && (
            <>
              <div className="button-row">
                <button
                  type="button"
                  className="ghost-btn"
                  onClick={onRefreshBridge}
                  disabled={disabled || !current.actions.refresh_bridge}
                  data-testid="refresh-bridge-button"
                >
                  {t("operator.refreshBridge")}
                </button>
                <button
                  type="button"
                  className="ghost-btn"
                  onClick={() => onImportBridgeResult(bridgePayload)}
                  disabled={disabled || !current.actions.import_bridge_result}
                  data-testid="import-bridge-result-button"
                >
                  {t("operator.importBridgeResult")}
                </button>
              </div>

              {current.actions.import_bridge_result ? (
                <form
                  className="stack"
                  onSubmit={(event) => {
                    event.preventDefault();
                    onImportBridgeResult(bridgePayload);
                  }}
                >
                  <p className="inline-title">{t("operator.bridgeImport")}</p>
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
                      placeholder={t("operator.resultSummaryPlaceholder")}
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
                      placeholder={t("operator.objectiveScorePlaceholder")}
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
                      placeholder={t("operator.primaryMetricPlaceholder")}
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
                      placeholder={t("operator.objectiveSystemPlaceholder")}
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
                      placeholder={t("operator.baselineSystemPlaceholder")}
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
                      placeholder={t("operator.baselineScorePlaceholder")}
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
                    placeholder={t("operator.findingsPlaceholder")}
                    data-testid="bridge-import-findings"
                  />
                </form>
              ) : null}
            </>
          )}
        </>
      )}

      {/* ── Review & Publish Tab ── */}
      {activeTab === "review" && (
        <>
          {!current ? (
            <div className="empty-state">
              <p>{t("operator.noRunSelectedTitle")}</p>
              <span>{t("operator.noRunSelectedDetail")}</span>
            </div>
          ) : (
            <>
              <div className="button-row">
                <button
                  type="button"
                  className="ghost-btn"
                  onClick={onRefreshReview}
                  disabled={disabled || !current.actions.refresh_review}
                  data-testid="refresh-review-button"
                >
                  {t("operator.refreshReview")}
                </button>
                <button
                  type="button"
                  className="ghost-btn"
                  onClick={onApplyReviewActions}
                  disabled={disabled || !current.actions.apply_review_actions}
                  data-testid="apply-review-actions-button"
                >
                  {t("operator.applyReviewActions")}
                </button>
                <button
                  type="button"
                  className="ghost-btn"
                  onClick={onRebuildPaper}
                  disabled={disabled || !current.actions.rebuild_paper}
                  data-testid="rebuild-paper-button"
                >
                  {t("operator.rebuildPaper")}
                </button>
                <button
                  type="button"
                  className="ghost-btn"
                  onClick={() =>
                    onExportPublish({
                      deployment_id: publishDraft.deployment_id.trim() || null,
                      deployment_label:
                        publishDraft.deployment_label.trim() || null,
                    })
                  }
                  disabled={disabled || !current.actions.export_publish}
                  data-testid="export-publish-button"
                >
                  {t("operator.exportFinalPublish")}
                </button>
                <button
                  type="button"
                  className="ghost-btn"
                  onClick={onDownloadPublish}
                  disabled={disabled || !current.actions.download_publish}
                  data-testid="download-publish-button"
                >
                  {t("operator.downloadFinalPublish")}
                </button>
              </div>

              <div className="summary-banner operator-summary-grid">
                <div>
                  <span className="meta-label">{t("operator.candidates")}</span>
                  <strong>
                    {counts?.total_candidates ?? candidateEntries.length}
                  </strong>
                </div>
                <div>
                  <span className="meta-label">
                    {t("operator.failedCandidates")}
                  </span>
                  <strong>{counts?.failed ?? 0}</strong>
                </div>
                <div>
                  <span className="meta-label">{t("operator.reviewRisk")}</span>
                  <strong>{review?.unsupported_claim_risk ?? "n/a"}</strong>
                </div>
                <div>
                  <span className="meta-label">{t("operator.novelty")}</span>
                  <strong>{novelty?.status ?? "n/a"}</strong>
                </div>
                <div>
                  <span className="meta-label">{t("operator.budget")}</span>
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
                  <span className="meta-label">{t("operator.reviewLoop")}</span>
                  <strong data-testid="operator-review-loop-summary">
                    {reviewLoop
                      ? `r${reviewLoop.current_round} / open ${reviewLoop.open_issue_count} / pending ${reviewLoop.pending_action_count}`
                      : "n/a"}
                  </strong>
                </div>
                <div>
                  <span className="meta-label">
                    {t("operator.completedActions")}
                  </span>
                  <strong>{reviewLoop?.completed_action_count ?? 0}</strong>
                </div>
              </div>

              {currentPublication ? (
                <>
                  <div
                    className="summary-banner operator-summary-grid"
                    data-testid="operator-publication-summary"
                  >
                    <div>
                      <span className="meta-label">
                        {t("operator.publication")}
                      </span>
                      <strong>{currentPublication.publication_id}</strong>
                    </div>
                    <div>
                      <span className="meta-label">{t("operator.bundle")}</span>
                      <strong>{currentPublication.bundle_kind}</strong>
                    </div>
                    <div>
                      <span className="meta-label">
                        {t("operator.paperAsset")}
                      </span>
                      <strong>
                        {currentPublication.paper_path
                          ? t("operator.available")
                          : t("operator.missing")}
                      </strong>
                    </div>
                    <div>
                      <span className="meta-label">
                        {t("operator.compiledPdf")}
                      </span>
                      <strong>
                        {currentPublication.compiled_paper_path
                          ? t("operator.available")
                          : t("operator.missing")}
                      </strong>
                    </div>
                    <div>
                      <span className="meta-label">
                        {t("operator.finalReady")}
                      </span>
                      <strong>
                        {currentPublication.final_publish_ready
                          ? t("operator.yes")
                          : t("operator.no")}
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
                      {t("operator.downloadPaper")}
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
                      {t("operator.downloadCompiledPdf")}
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
                      {t("operator.downloadCodePackage")}
                    </button>
                  </div>
                </>
              ) : (
                <div
                  className="empty-state"
                  data-testid="operator-publication-empty"
                >
                  <p>{t("operator.noPublicationTitle")}</p>
                  <span>
                    {!finalPublishReady
                      ? t("operator.noPublicationNotReady")
                      : publish?.publication_id
                        ? t("operator.noPublicationRefresh")
                        : t("operator.noPublicationExport")}
                  </span>
                </div>
              )}

              <div className="meta-block">
                <span className="meta-label">{t("operator.lineage")}</span>
                <code data-testid="operator-lineage-summary">
                  selected={lineage?.selected_candidate_id ?? "n/a"}{" "}
                  artifact_from=
                  {lineage?.top_level_artifact_candidate_id ?? "n/a"}{" "}
                  paper_from=
                  {lineage?.top_level_paper_candidate_id ?? "n/a"} edges=
                  {lineage?.edges.length ?? 0}
                </code>
              </div>

              {novelty ? (
                <div className="meta-block">
                  <span className="meta-label">
                    {t("operator.noveltyTriage")}
                  </span>
                  <p data-testid="operator-novelty-summary">
                    {novelty.summary} Top matches=
                    {novelty.top_related_work.length} uncovered_claims=
                    {novelty.uncovered_claims.length}
                  </p>
                </div>
              ) : null}

              {reviewLoop ? (
                <div className="meta-block">
                  <span className="meta-label">{t("operator.reviewLoop")}</span>
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
                <p className="inline-title">
                  {t("operator.candidateComparison")}
                </p>
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
                          {candidate.selected
                            ? ` · ${t("operator.selected")}`
                            : ""}
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
                <p className="inline-title">{t("operator.topFindings")}</p>
                {review?.findings?.slice(0, 3).map((finding) => (
                  <div key={finding.id} className="suggestion-card">
                    <strong>
                      {finding.severity.toUpperCase()} · {finding.category}
                    </strong>
                    <p>{finding.summary}</p>
                  </div>
                )) ?? (
                  <div className="empty-state">
                    <p>{t("operator.noReviewFindings")}</p>
                  </div>
                )}
              </div>

              <div className="stack">
                <p className="inline-title">{t("operator.revisionActions")}</p>
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
                    <p>{t("operator.noRevisionActions")}</p>
                  </div>
                )}
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
}
