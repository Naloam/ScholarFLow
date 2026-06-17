// Headline metric cards for the Report page. Surfaced so a human can judge at a
// glance: "did this system really run experiments, and is the conclusion
// Mixed / Negative / Positive?"
//
// HONESTY CONTRACT (goal_session5 §避坑 #8): we never reframe a negative or null
// result as "promising". overall_beats_baseline=false renders as Mixed/Negative,
// full stop. execution_status != success renders as "No results".
import type { MetricsJson, ReviewJson, SignificanceTest } from "../api/types";

interface MetricCardsProps {
  metrics: MetricsJson | null;
  review: ReviewJson | null;
}

type Tone = "positive" | "mixed" | "negative" | "neutral";

function isSignificant(test: SignificanceTest): boolean {
  return (
    typeof test.adjusted_p_value === "number" &&
    typeof test.adjusted_alpha === "number" &&
    test.adjusted_p_value <= test.adjusted_alpha
  );
}

function deriveVerdict(
  metrics: MetricsJson | null,
  anySig: boolean,
): { label: string; tone: Tone; detail: string } {
  const exec = metrics?.execution_status;
  if (exec !== "success") {
    return {
      label: exec === "failed_after_repair" ? "Execution failed" : "No results",
      tone: "neutral",
      detail: "Experiments did not complete successfully — no conclusion is drawn.",
    };
  }
  const beats = metrics?.baseline_comparison?.overall_beats_baseline;
  if (beats === true && anySig) {
    return {
      label: "Positive",
      tone: "positive",
      detail: "Beats baseline across compared datasets with at least one significant comparison.",
    };
  }
  if (beats === true) {
    return {
      label: "Mixed",
      tone: "mixed",
      detail: "Beats baseline on aggregate, but not all comparisons reached significance.",
    };
  }
  return {
    label: "Mixed / Negative",
    tone: "negative",
    detail: "Did not beat the baseline on every dataset. Reported as a negative result.",
  };
}

function Card({
  label,
  value,
  tone,
  detail,
}: {
  label: string;
  value: string;
  tone?: Tone;
  detail?: string;
}) {
  return (
    <div className={`metric metric--${tone ?? "neutral"}`}>
      <div className="metric__label">{label}</div>
      <div className="metric__value">{value}</div>
      {detail ? <div className="metric__detail">{detail}</div> : null}
    </div>
  );
}

function fmt(n: number | undefined): string {
  return typeof n === "number" && Number.isFinite(n) ? n.toFixed(3) : "—";
}

export function MetricCards({ metrics, review }: MetricCardsProps) {
  const sigTests = metrics?.statistics?.significance_tests ?? [];
  const sigCount = sigTests.filter(isSignificant).length;
  const anySig = sigCount > 0;

  const verdict = deriveVerdict(metrics, anySig);
  const execLabel = metrics?.execution_status ?? "unknown";
  const seedCount = metrics?.statistics?.seed_count;
  const datasets = metrics?.baseline_comparison?.datasets ?? [];
  const abstention = metrics?.abstention_metrics ?? {};
  const spearman = abstention.spearman_consistency_vs_label ?? {};
  const errorAtAbstain = abstention.error_rate_at_20pct_abstain ?? {};

  return (
    <section className="metrics" aria-label="Headline metrics">
      <Card
        label="Execution"
        value={execLabel === "success" ? "Succeeded" : execLabel}
        tone={execLabel === "success" ? "positive" : "negative"}
        detail={
          execLabel === "success"
            ? "Real experiment ran and produced metrics."
            : "No valid experimental results."
        }
      />
      <Card
        label="Verdict"
        value={verdict.label}
        tone={verdict.tone}
        detail={verdict.detail}
      />
      <Card
        label="Significance"
        value={`${sigCount} / ${sigTests.length}`}
        tone={anySig ? "positive" : "neutral"}
        detail={`comparisons reaching adjusted-α${seedCount ? ` · ${seedCount} seeds` : ""}`}
      />
      <Card
        label="Publish gate"
        value={review?.publish_gate ?? "—"}
        tone={review?.publish_gate === "publishable" ? "positive" : "neutral"}
        detail={review?.overall_assessment ? `Reviewer: ${review.overall_assessment}` : undefined}
      />

      {datasets.length > 0 ? (
        <div className="metric metric--wide">
          <div className="metric__label">Baseline vs proposed (per dataset)</div>
          <table className="metric__table">
            <thead>
              <tr>
                <th>Dataset</th>
                <th>Baseline</th>
                <th>Proposed</th>
                <th>Δ</th>
                <th>Beats</th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((d) => (
                <tr key={d.dataset}>
                  <td>{d.dataset}</td>
                  <td>{fmt(d.baseline_metric)}</td>
                  <td>{fmt(d.proposed_metric)}</td>
                  <td>{d.delta >= 0 ? "+" : ""}{fmt(d.delta)}</td>
                  <td className={d.beats_baseline ? "ok" : "warn"}>
                    {d.beats_baseline ? "yes" : "no"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {Object.keys(spearman).length > 0 ? (
        <div className="metric metric--wide">
          <div className="metric__label">Abstention calibration (spearman / error@20% abstain)</div>
          <table className="metric__table">
            <thead>
              <tr>
                <th>Dataset</th>
                <th>Baseline spearman</th>
                <th>Proposed spearman</th>
                <th>Baseline err@abstain</th>
                <th>Proposed err@abstain</th>
              </tr>
            </thead>
            <tbody>
              {Object.keys(spearman).map((ds) => {
                const baselineSys = Object.keys(spearman[ds] ?? {}).find((s) =>
                  s.startsWith("baseline"),
                );
                const proposedSys = Object.keys(spearman[ds] ?? {}).find((s) =>
                  s.startsWith("proposed"),
                );
                return (
                  <tr key={ds}>
                    <td>{ds}</td>
                    <td>{fmt(spearman[ds]?.[baselineSys ?? ""])}</td>
                    <td>{fmt(spearman[ds]?.[proposedSys ?? ""])}</td>
                    <td>{fmt(errorAtAbstain[ds]?.[baselineSys ?? ""])}</td>
                    <td>{fmt(errorAtAbstain[ds]?.[proposedSys ?? ""])}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
