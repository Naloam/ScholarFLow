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
  const similarity = analysis?.similarity;
  const similarityLabel =
    similarity?.status === "high"
      ? "High overlap"
      : similarity?.status === "warning"
        ? "Needs review"
        : "Clear";

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
        <div>
          <span className="meta-label">Similarity screen</span>
          <strong>{similarityLabel}</strong>
        </div>
      </div>

      {similarity ? (
        <div className="inline-card">
          <p className="inline-title">Overlap screening</p>
          <p className="auth-copy">
            Checked {similarity.checked_paragraphs} paragraphs against project evidence snippets and
            paper abstracts. {similarity.flagged_paragraphs} passages need manual review.
          </p>
          {similarity.matches.length > 0 ? (
            <div className="stack">
              {similarity.matches.map((match, index) => (
                <article
                  key={`${match.source_label}-${index}`}
                  className="suggestion-card"
                  data-testid={index === 0 ? "similarity-match-card" : undefined}
                >
                  <strong>{Math.round(match.similarity * 100)}% overlap · {match.source_label}</strong>
                  <p>{match.draft_excerpt}</p>
                  <p>{match.source_excerpt}</p>
                </article>
              ))}
            </div>
          ) : (
            <p className="auth-copy">
              No high-overlap passages were flagged by the local similarity screen.
            </p>
          )}
        </div>
      ) : null}

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
