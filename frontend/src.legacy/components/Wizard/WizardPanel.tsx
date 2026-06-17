import { useTranslation } from "react-i18next";

import type { ProjectStatus } from "../../api/types";
import { formatPercent } from "../../utils/format";

type Step = {
  key: string;
  labelKey: string;
};

const steps: Step[] = [
  { key: "Phase 2", labelKey: "wizard.phase2Label" },
  { key: "Phase 3", labelKey: "wizard.phase3Label" },
  { key: "Phase 4", labelKey: "wizard.phase4Label" },
  { key: "Phase 5", labelKey: "wizard.phase5Label" },
  { key: "Phase 6", labelKey: "wizard.phase6Label" },
];

type WizardPanelProps = {
  status: ProjectStatus | null;
};

export function WizardPanel({ status }: WizardPanelProps) {
  const { t } = useTranslation();

  const currentPhase = status?.phase ?? "Phase 6";

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{t("wizard.eyebrow")}</p>
          <h2 className="panel-title">{t("wizard.title")}</h2>
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
              <p>{t(step.labelKey)}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
