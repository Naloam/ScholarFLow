// Session 14 — P3 publication surface card (goal_session13_14.md §Session 14).
//
// Renders the publish-bundle manifest for a project: honest verdict banner, audit
// gate + unverified count, metric summary, provenance, and a Download .zip button.
//
// HONESTY CONTRACT: the backend decides `publishable` (false when the audit gate
// failed or the verdict is negative/all_negative/execution_failed/no_comparison).
// When `publishable` is false the Download button is DISABLED and the reason is
// shown prominently — the publish surface never lets a gate-failed artifact ship.
// The full honest verdict + unverified count are always shown (transparency).
import { useEffect, useState } from "react";

import { getPublishBundle, publishBundleDownloadUrl } from "../api/client";
import type { PublishBundleManifest } from "../api/types";
import { Spinner } from "./Spinner";

interface PublishCardProps {
  projectId: string;
}

function verdictTone(verdict: string | undefined): string {
  if (!verdict) return "neutral";
  if (verdict.startsWith("positive")) return "positive";
  if (verdict === "mixed") return "mixed";
  if (verdict === "negative") return "negative";
  return "neutral";
}

function metricText(m: PublishBundleManifest["metric_summary"]): string {
  if (!m) return "—";
  const parts: string[] = [];
  if (m.primary_metric) parts.push(m.primary_metric);
  if (typeof m.overall_beats_baseline === "boolean") {
    parts.push(m.overall_beats_baseline ? "beats baseline" : "does NOT beat baseline");
  }
  if (typeof m.any_significant === "boolean" && m.any_significant) parts.push("significant");
  if (typeof m.seed_count === "number") parts.push(`${m.seed_count} seeds`);
  return parts.length ? parts.join(" · ") : "—";
}

export function PublishCard({ projectId }: PublishCardProps) {
  const [manifest, setManifest] = useState<PublishBundleManifest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getPublishBundle(projectId)
      .then((result) => {
        if (!cancelled) {
          setManifest(result);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load publish bundle");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  if (loading) {
    return <Spinner label="Loading publish bundle…" />;
  }
  if (error || !manifest) {
    return (
      <section className="report__publish">
        <h2 className="section__title">Publish</h2>
        <div className="callout">
          <p>Publish bundle unavailable{error ? `: ${error}` : "."}</p>
        </div>
      </section>
    );
  }

  const verdict = (manifest.honest_verdict as { verdict?: string } | undefined)?.verdict;
  const gate = manifest.audit_gate?.gate ?? false;
  const publishable = manifest.publishable;
  const reason = manifest.publishable_reason || "";
  const provenance = manifest.provenance;

  return (
    <section className="report__publish" aria-label="Publish bundle">
      <h2 className="section__title">Publish</h2>

      <div className={`publish__banner publish__banner--${publishable ? "ok" : "gated"}`}>
        <div className="publish__banner-headline">
          {publishable ? "Publishable" : "Not publishable"}
        </div>
        <div className="publish__banner-reason">
          {publishable
            ? "Audit gate passed and verdict is a publishable positive result."
            : reason || "Audit gate failed or verdict is not a publishable result."}
        </div>
      </div>

      <div className="publish__grid">
        <div className={`metric metric--${verdictTone(verdict)}`}>
          <div className="metric__label">Honest verdict</div>
          <div className="metric__value">{verdict ? verdict.replace(/_/g, " ") : "—"}</div>
        </div>
        <div className={`metric metric--${gate ? "positive" : "negative"}`}>
          <div className="metric__label">Audit gate</div>
          <div className="metric__value">
            {gate ? "passed" : "failed"}
            {manifest.audit_gate && typeof manifest.audit_gate.unverified_count === "number" && (
              <span className="metric__sub">
                {" "}({manifest.audit_gate.unverified_count} unverified)
              </span>
            )}
          </div>
        </div>
        <div className="metric metric--neutral">
          <div className="metric__label">Metric summary</div>
          <div className="metric__value publish__metric-summary">
            {metricText(manifest.metric_summary)}
          </div>
        </div>
        <div className="metric metric--neutral">
          <div className="metric__label">Provenance</div>
          <div className="metric__value publish__provenance">
            {provenance && provenance.datasets && provenance.datasets.length > 0
              ? provenance.datasets.join(", ")
              : "—"}
            {provenance && typeof provenance.candidate_count === "number"
              ? ` · ${provenance.candidate_count} candidate(s)`
              : ""}
            {manifest.portfolio_verdict ? ` · ${manifest.portfolio_verdict}` : ""}
          </div>
        </div>
      </div>

      <div className="publish__actions">
        <a
          className={`btn ${publishable ? "btn--ghost" : "btn--ghost is-disabled"}`}
          href={publishable ? publishBundleDownloadUrl(projectId) : undefined}
          aria-disabled={!publishable}
          onClick={publishable ? undefined : (e) => e.preventDefault()}
        >
          ⬇ Download publish_bundle.zip
        </a>
        {!publishable ? (
          <span className="publish__disabled-note">
            Download disabled — not publishable (audit gate failed or negative verdict).
          </span>
        ) : (
          <span className="publish__bundle-files">
            bundle: manifest.json · paper/draft.md · code/experiment.py · evidence ledger
          </span>
        )}
      </div>
    </section>
  );
}
