import type { ProjectStatus } from "../../api/types";
import { formatPercent } from "../../utils/format";

const steps = [
  { key: "Phase 2", label: "Search and Evidence" },
  { key: "Phase 3", label: "Execution and Drafts" },
  { key: "Phase 4", label: "Registry and Lineage" },
  { key: "Phase 5", label: "Review and Publish" },
  { key: "Phase 6", label: "Operator Console" },
];

type WizardPanelProps = {
  status: ProjectStatus | null;
};

export function WizardPanel({ status }: WizardPanelProps) {
  const currentPhase = status?.phase ?? "Phase 6";

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Workflow</p>
          <h2 className="panel-title">Research Roadmap</h2>
        </div>
        <span className="badge badge-soft">{status?.status ?? "init"}</span>
      </div>

      <div className="progress-strip">
        <div
          className="progress-fill"
          style={{ width: formatPercent(status?.progress ?? 0) }}
        />
      </div>

      <ul className="timeline">
        {steps.map((step) => (
          <li
            key={step.key}
            className={
              step.key === currentPhase
                ? "timeline-item active"
                : "timeline-item"
            }
          >
            <span className="timeline-dot" />
            <div>
              <strong>{step.key}</strong>
              <p>{step.label}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
