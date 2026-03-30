import type {
  AutoResearchDeployment,
  AutoResearchDeploymentList,
} from "../../api/types";

type DeploymentPanelProps = {
  deploymentList: AutoResearchDeploymentList | null;
  deployment: AutoResearchDeployment | null;
  selectedDeploymentId?: string | null;
  disabled: boolean;
  onSelectDeployment: (deploymentId: string) => void;
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

export function DeploymentPanel({
  deploymentList,
  deployment,
  selectedDeploymentId,
  disabled,
  onSelectDeployment,
  onOpenPublication,
}: DeploymentPanelProps) {
  const hasDeployments = Boolean(deploymentList?.deployments.length);

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
          <span>Export a publish package to register a paper/run/code package into a deployment.</span>
        </div>
      ) : (
        <>
          <div className="button-row">
            <select
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
            <span className="auth-copy" data-testid="deployment-selection-summary">
              {deployment
                ? `${deployment.project_count} projects / ${deployment.final_publish_ready_count} final-ready papers`
                : "Select a deployment to inspect publication listings"}
            </span>
          </div>

          {deployment ? (
            <>
              <div className="summary-banner operator-summary-grid">
                <div>
                  <span className="meta-label">Deployment</span>
                  <strong>{deployment.label}</strong>
                </div>
                <div>
                  <span className="meta-label">Publications</span>
                  <strong>{deployment.publication_count}</strong>
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

              <div className="list-block">
                {deployment.publications.map((item) => {
                  const compileOutputCount = item.publication.paper_compile_output_paths.length;
                  return (
                    <div
                      key={item.publication.publication_id}
                      className="evidence-card"
                      data-testid={`deployment-publication-${item.publication.run_id}`}
                    >
                      <strong>{item.publication.paper_title}</strong>
                      <small>
                        project {item.publication.project_title ?? item.publication.project_id} / run{" "}
                        {item.publication.run_id}
                      </small>
                      <small>
                        bundle {item.publication.bundle_kind} / final ready{" "}
                        {item.publication.final_publish_ready ? "yes" : "no"}
                      </small>
                      <small>topic {item.publication.topic}</small>
                      <small>
                        listed {formatTimestamp(item.listed_at)} / updated{" "}
                        {formatTimestamp(item.publication.updated_at)}
                      </small>
                      <small>archive {item.publication.publish_archive_path}</small>
                      <small>paper {item.publication.paper_path ?? "n/a"}</small>
                      <small>
                        compiled {item.publication.compiled_paper_path ?? "n/a"} / outputs{" "}
                        {compileOutputCount}
                      </small>
                      <small>code {item.publication.code_package_path ?? "n/a"}</small>
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
            </>
          ) : null}
        </>
      )}
    </section>
  );
}
