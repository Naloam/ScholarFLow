import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { BetaSummary } from "../../api/types";
import { formatDate } from "../../utils/format";

type BetaPanelProps = {
  summary: BetaSummary | null;
  disabled: boolean;
  onSubmit: (payload: {
    rating: number;
    category: string;
    comment: string;
  }) => Promise<void>;
};

export function BetaPanel({ summary, disabled, onSubmit }: BetaPanelProps) {
  const { t } = useTranslation();
  const [rating, setRating] = useState("5");
  const [category, setCategory] = useState("usability");
  const [comment, setComment] = useState(
    "Flow is coherent and ready for beta testing.",
  );
  const recentEvents = summary?.performance.recent_events ?? [];
  const feedback = summary?.feedback ?? [];
  const canSubmit = !disabled && comment.trim().length >= 4;

  return (
    <section className="panel" data-testid="beta-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{t("beta.eyebrow")}</p>
          <h2 className="panel-title">{t("beta.title")}</h2>
        </div>
        <span className="badge badge-soft" data-testid="beta-feedback-count">
          {summary?.feedback_count ?? 0} feedback
        </span>
      </div>

      <div className="beta-metric-grid">
        <article className="metric-card">
          <span className="meta-label">{t("beta.totalTokens")}</span>
          <strong data-testid="beta-total-tokens">
            {summary?.performance.total_tokens ?? 0}
          </strong>
        </article>
        <article className="metric-card">
          <span className="meta-label">{t("beta.avgLatency")}</span>
          <strong data-testid="beta-average-latency">
            {summary
              ? `${Math.round(summary.performance.average_latency_ms)} ms`
              : "0 ms"}
          </strong>
        </article>
        <article className="metric-card">
          <span className="meta-label">{t("beta.estimatedCost")}</span>
          <strong data-testid="beta-estimated-cost">
            ${summary?.performance.estimated_cost_usd.toFixed(4) ?? "0.0000"}
          </strong>
        </article>
        <article className="metric-card">
          <span className="meta-label">{t("beta.avgRating")}</span>
          <strong data-testid="beta-average-rating">
            {summary?.average_rating
              ? `${summary.average_rating}/5`
              : t("beta.na")}
          </strong>
        </article>
      </div>

      <div className="inline-card">
        <p className="inline-title">{t("beta.submitBetaFeedback")}</p>
        <label className="field">
          <span className="field-label">{t("beta.rating")}</span>
          <select
            id="beta-rating-input"
            name="beta_rating"
            data-testid="beta-rating-input"
            disabled={disabled}
            value={rating}
            onChange={(event) => setRating(event.target.value)}
          >
            <option value="5">{t("beta.rating5")}</option>
            <option value="4">{t("beta.rating4")}</option>
            <option value="3">{t("beta.rating3")}</option>
            <option value="2">{t("beta.rating2")}</option>
            <option value="1">{t("beta.rating1")}</option>
          </select>
        </label>
        <label className="field">
          <span className="field-label">{t("beta.category")}</span>
          <select
            id="beta-category-input"
            name="beta_category"
            data-testid="beta-category-input"
            disabled={disabled}
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            <option value="usability">{t("beta.usability")}</option>
            <option value="quality">{t("beta.quality")}</option>
            <option value="performance">{t("beta.performance")}</option>
            <option value="bug">{t("beta.bug")}</option>
          </select>
        </label>
        <label className="field">
          <span className="field-label">{t("beta.comment")}</span>
          <textarea
            id="beta-comment-input"
            name="beta_comment"
            data-testid="beta-comment-input"
            rows={3}
            disabled={disabled}
            value={comment}
            onChange={(event) => setComment(event.target.value)}
          />
        </label>
        <div className="button-row">
          <button
            className="primary-btn"
            data-testid="beta-submit-button"
            disabled={!canSubmit}
            onClick={() =>
              void onSubmit({
                rating: Number(rating),
                category,
                comment,
              })
            }
          >
            {t("beta.sendFeedback")}
          </button>
        </div>
      </div>

      <div className="stack">
        <div className="inline-card">
          <p className="inline-title">{t("beta.recentEvents")}</p>
          {recentEvents.length === 0 ? (
            <p className="auth-copy">{t("beta.noTelemetry")}</p>
          ) : (
            <div className="stack">
              {recentEvents.map((event, index) => (
                <article
                  key={`${event.model}-${event.created_at ?? index}`}
                  className="feedback-card"
                  data-testid={index === 0 ? "beta-event-card" : undefined}
                >
                  <strong>{event.operation ?? event.source}</strong>
                  <p className="auth-copy">
                    {event.model} · {event.total_tokens} tokens ·{" "}
                    {event.duration_ms} ms
                  </p>
                </article>
              ))}
            </div>
          )}
        </div>

        <div className="inline-card">
          <p className="inline-title">{t("beta.feedbackLog")}</p>
          {feedback.length === 0 ? (
            <p className="auth-copy">{t("beta.noBetaFeedback")}</p>
          ) : (
            <div className="stack">
              {feedback.map((entry, index) => (
                <article
                  key={entry.id}
                  className="feedback-card"
                  data-testid={index === 0 ? "beta-feedback-card" : undefined}
                >
                  <strong>
                    {entry.rating}/5 · {entry.category}
                  </strong>
                  <p>{entry.comment}</p>
                  <small>
                    {formatDate(entry.created_at)} · {entry.status}
                  </small>
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
