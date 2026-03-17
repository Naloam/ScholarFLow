import type { AnalysisSummary, ReviewReport } from "../../api/types";
import { formatPercent } from "../../utils/format";

type ReviewPanelProps = {
  reviews: ReviewReport[];
  analysis: AnalysisSummary | null;
};

const scoreOrder: Array<keyof ReviewReport["scores"]> = [
  "originality",
  "importance",
  "evidence_support",
  "soundness",
  "clarity",
  "value",
  "contextualization",
];

export function ReviewPanel({ reviews, analysis }: ReviewPanelProps) {
  const latest = reviews[0];

  return (
    <section className="panel" data-testid="review-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Virtual Advisor</p>
          <h2 className="panel-title">Review Panel</h2>
        </div>
        <span className="badge badge-soft">{reviews.length} reports</span>
      </div>

      <div className="summary-banner">
        <div>
          <span className="meta-label">Evidence coverage</span>
          <strong>{formatPercent(analysis?.evidence_coverage)}</strong>
        </div>
        <div>
          <span className="meta-label">Needs evidence</span>
          <strong>{analysis?.needs_evidence_count ?? 0}</strong>
        </div>
      </div>

      {!latest ? (
        <div className="empty-state">
          <p>No review report yet.</p>
          <span>Use Run Review after generating a draft.</span>
        </div>
      ) : (
        <>
          <div className="score-grid">
            {scoreOrder.map((key) => (
              <article key={key} className="score-card">
                <span>{key.replace(/_/g, " ")}</span>
                <strong>{latest.scores[key]}</strong>
              </article>
            ))}
          </div>

          <div className="stack">
            {latest.suggestions.map((suggestion) => (
              <article key={suggestion} className="suggestion-card">
                {suggestion}
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
