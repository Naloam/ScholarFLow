import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
  const latest = reviews[0];
  const similarity = analysis?.similarity;
  const similarityLabel =
    similarity?.status === "high"
      ? t("review.highOverlap")
      : similarity?.status === "warning"
        ? t("review.needsReview")
        : t("review.clear");

  return (
    <section className="panel" data-testid="review-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{t("review.eyebrow")}</p>
          <h2 className="panel-title">{t("review.title")}</h2>
        </div>
        <span className="badge badge-soft">
          {t("review.reportCount", { count: reviews.length })}
        </span>
      </div>

      <div className="summary-banner">
        <div>
          <span className="meta-label">{t("review.evidenceCoverage")}</span>
          <strong>{formatPercent(analysis?.evidence_coverage)}</strong>
        </div>
        <div>
          <span className="meta-label">{t("review.needsEvidence")}</span>
          <strong>{analysis?.needs_evidence_count ?? 0}</strong>
        </div>
        <div>
          <span className="meta-label">{t("review.similarityScreen")}</span>
          <strong>{similarityLabel}</strong>
        </div>
      </div>

      {similarity ? (
        <div className="inline-card">
          <p className="inline-title">{t("review.overlapScreening")}</p>
          <p className="auth-copy">
            {t("review.overlapDetail", {
              checked: similarity.checked_paragraphs,
              flagged: similarity.flagged_paragraphs,
            })}
          </p>
          {similarity.matches.length > 0 ? (
            <div className="stack">
              {similarity.matches.map((match, index) => (
                <article
                  key={`${match.source_label}-${index}`}
                  className="suggestion-card"
                  data-testid={
                    index === 0 ? "similarity-match-card" : undefined
                  }
                >
                  <strong>
                    {Math.round(match.similarity * 100)}% overlap ·{" "}
                    {match.source_label}
                  </strong>
                  <p>{match.draft_excerpt}</p>
                  <p>{match.source_excerpt}</p>
                </article>
              ))}
            </div>
          ) : (
            <p className="auth-copy">{t("review.noHighOverlap")}</p>
          )}
        </div>
      ) : null}

      {!latest ? (
        <div className="empty-state">
          <p>{t("review.noReviewTitle")}</p>
          <span>{t("review.noReviewDetail")}</span>
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
