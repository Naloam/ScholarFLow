import { useEffect, useState } from "react";

import type {
  AutoResearchDeployment,
  AutoResearchDeploymentFilters,
  AutoResearchDeploymentList,
} from "../../api/types";

type DeploymentPanelProps = {
  deploymentList: AutoResearchDeploymentList | null;
  deployment: AutoResearchDeployment | null;
  selectedDeploymentId?: string | null;
  filters: AutoResearchDeploymentFilters;
  disabled: boolean;
  onSelectDeployment: (deploymentId: string) => void;
  onApplyFilters: (filters: AutoResearchDeploymentFilters) => void;
  onClearFilters: () => void;
  onOpenPublication: (projectId: string, runId: string) => void;
};

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

function formatTaskFamily(value: string | null | undefined): string {
  if (!value) {
    return "n/a";
  }
  return value.replaceAll("_", " ");
}

export function DeploymentPanel({
  deploymentList,
  deployment,
  selectedDeploymentId,
  filters,
  disabled,
  onSelectDeployment,
  onApplyFilters,
  onClearFilters,
  onOpenPublication,
}: DeploymentPanelProps) {
  const [draftFilters, setDraftFilters] =
    useState<AutoResearchDeploymentFilters>(filters);
  const hasDeployments = Boolean(deploymentList?.deployments.length);
  const hasActiveFilters = Boolean(
    filters.search ||
    (filters.final_publish_ready !== null &&
      filters.final_publish_ready !== undefined) ||
    filters.bundle_kind ||
    filters.task_family,
  );

  useEffect(() => {
    setDraftFilters(filters);
  }, [
    filters.search,
    filters.final_publish_ready,
    filters.bundle_kind,
    filters.task_family,
  ]);

  function updateFilter<K extends keyof AutoResearchDeploymentFilters>(
    key: K,
    value: AutoResearchDeploymentFilters[K],
  ) {
    setDraftFilters((state) => ({
      ...state,
      [key]: value,
    }));
  }

  return (
    <section className="panel" data-testid="deployment-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Workstream E</p>
          <h2 className="panel-title">Deployments</h2>
        </div>
        <span className="badge badge-soft">
          {deploymentList
            ? `${deploymentList.deployment_count} deployments / ${deploymentList.publication_count} publications`
            : "No deployments"}
        </span>
      </div>

      {!hasDeployments ? (
        <div className="empty-state">
          <p>No publish deployments yet.</p>
          <span>
            Export a publish package to register a paper/run/code package into a
            deployment.
          </span>
        </div>
      ) : (
        <>
          <div className="button-row">
            <select
              id="deployment-select"
              name="deployment_select"
              value={selectedDeploymentId ?? ""}
              onChange={(event) => onSelectDeployment(event.target.value)}
              disabled={disabled}
              data-testid="deployment-select"
            >
              {deploymentList?.deployments.map((item) => (
                <option key={item.deployment_id} value={item.deployment_id}>
                  {item.label} ({item.publication_count})
                </option>
              ))}
            </select>
            <span
              className="auth-copy"
              data-testid="deployment-selection-summary"
            >
              {deployment
                ? `${deployment.filtered_publication_count}/${deployment.publication_count} shown across ${deployment.project_count} projects`
                : "Select a deployment to inspect publication listings"}
            </span>
          </div>

          {deployment ? (
            <>
              <div className="button-row">
                <input
                  id="deployment-search-input"
                  name="deployment_search_input"
                  type="search"
                  value={draftFilters.search ?? ""}
                  onChange={(event) =>
                    updateFilter("search", event.target.value || null)
                  }
                  placeholder="Search publication, topic, run, benchmark"
                  disabled={disabled}
                  data-testid="deployment-search-input"
                />
                <select
                  id="deployment-final-ready-filter"
                  name="deployment_final_ready_filter"
                  value={
                    draftFilters.final_publish_ready === null ||
                    draftFilters.final_publish_ready === undefined
                      ? ""
                      : String(draftFilters.final_publish_ready)
                  }
                  onChange={(event) =>
                    updateFilter(
                      "final_publish_ready",
                      event.target.value === ""
                        ? null
                        : event.target.value === "true",
                    )
                  }
                  disabled={disabled}
                  data-testid="deployment-final-ready-filter"
                >
                  <option value="">All readiness</option>
                  <option value="true">Final ready only</option>
                  <option value="false">Needs final work</option>
                </select>
                <select
                  id="deployment-bundle-kind-filter"
                  name="deployment_bundle_kind_filter"
                  value={draftFilters.bundle_kind ?? ""}
                  onChange={(event) =>
                    updateFilter(
                      "bundle_kind",
                      event.target.value === ""
                        ? null
                        : (event.target
                            .value as AutoResearchDeploymentFilters["bundle_kind"]),
                    )
                  }
                  disabled={disabled}
                  data-testid="deployment-bundle-kind-filter"
                >
                  <option value="">All bundles</option>
                  <option value="review_bundle">Review bundle</option>
                  <option value="final_publish_bundle">
                    Final publish bundle
                  </option>
                </select>
                <select
                  id="deployment-task-family-filter"
                  name="deployment_task_family_filter"
                  value={draftFilters.task_family ?? ""}
                  onChange={(event) =>
                    updateFilter(
                      "task_family",
                      event.target.value === ""
                        ? null
                        : (event.target
                            .value as AutoResearchDeploymentFilters["task_family"]),
                    )
                  }
                  disabled={disabled}
                  data-testid="deployment-task-family-filter"
                >
                  <option value="">All task families</option>
                  <option value="text_classification">
                    Text classification
                  </option>
                  <option value="tabular_classification">
                    Tabular classification
                  </option>
                  <option value="ir_reranking">IR reranking</option>
                </select>
                <button
                  type="button"
                  className="ghost-btn"
                  onClick={() => onApplyFilters(draftFilters)}
                  disabled={disabled}
                  data-testid="deployment-apply-filters-button"
                >
                  Apply Filters
                </button>
                <button
                  type="button"
                  className="ghost-btn"
                  onClick={onClearFilters}
                  disabled={disabled || !hasActiveFilters}
                  data-testid="deployment-clear-filters-button"
                >
                  Clear Filters
                </button>
              </div>

              <div className="summary-banner operator-summary-grid">
                <div>
                  <span className="meta-label">Deployment</span>
                  <strong>{deployment.label}</strong>
                </div>
                <div>
                  <span className="meta-label">Showing</span>
                  <strong>
                    {deployment.filtered_publication_count}/
                    {deployment.publication_count}
                  </strong>
                </div>
                <div>
                  <span className="meta-label">Projects</span>
                  <strong>{deployment.project_count}</strong>
                </div>
                <div>
                  <span className="meta-label">Final Ready</span>
                  <strong>{deployment.final_publish_ready_count}</strong>
                </div>
                <div>
                  <span className="meta-label">Created</span>
                  <strong>{formatTimestamp(deployment.created_at)}</strong>
                </div>
                <div>
                  <span className="meta-label">Updated</span>
                  <strong>{formatTimestamp(deployment.updated_at)}</strong>
                </div>
              </div>

              {deployment.publications.length === 0 ? (
                <div
                  className="empty-state"
                  data-testid="deployment-empty-filtered"
                >
                  <p>No publications match the current filters.</p>
                  <span>
                    Clear filters or widen the search to inspect the full
                    deployment.
                  </span>
                </div>
              ) : (
                <div className="list-block">
                  {deployment.publications.map((item) => {
                    const compileOutputCount =
                      item.publication.paper_compile_output_paths.length;
                    return (
                      <div
                        key={item.publication.publication_id}
                        className="evidence-card"
                        data-testid={`deployment-publication-${item.publication.run_id}`}
                      >
                        <strong>{item.publication.paper_title}</strong>
                        <small>
                          project{" "}
                          {item.publication.project_title ??
                            item.publication.project_id}{" "}
                          / run {item.publication.run_id}
                        </small>
                        <small>
                          task {formatTaskFamily(item.publication.task_family)}{" "}
                          / bundle {item.publication.bundle_kind} / final ready{" "}
                          {item.publication.final_publish_ready ? "yes" : "no"}
                        </small>
                        <small>topic {item.publication.topic}</small>
                        <small>
                          benchmark {item.publication.benchmark_name}
                        </small>
                        <small>
                          listed {formatTimestamp(item.listed_at)} / updated{" "}
                          {formatTimestamp(item.publication.updated_at)}
                        </small>
                        <small>
                          archive {item.publication.publish_archive_path}
                        </small>
                        <small>
                          paper {item.publication.paper_path ?? "n/a"}
                        </small>
                        <small>
                          compiled{" "}
                          {item.publication.compiled_paper_path ?? "n/a"} /
                          outputs {compileOutputCount}
                        </small>
                        <small>
                          code {item.publication.code_package_path ?? "n/a"}
                        </small>
                        <button
                          type="button"
                          className="ghost-btn"
                          onClick={() =>
                            onOpenPublication(
                              item.publication.project_id,
                              item.publication.run_id,
                            )
                          }
                          disabled={disabled}
                          data-testid={`deployment-open-${item.publication.run_id}`}
                        >
                          Open Publication
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          ) : null}
        </>
      )}
    </section>
  );
}
