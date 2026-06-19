// Report: the headline output. Metric cards (execution_status / verdict /
// significance / abstention) + faithful research_report.md render + reviewer
// weaknesses. The report text is rendered verbatim — negative/null/Mixed
// conclusions are never reframed as positive (honesty gate, goal §避坑 #8).
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getFile } from "../api/client";
import type {
  AnchoredVerdict,
  CitationGroundingLog,
  ClaimAudit,
  MetricsJson,
  ReviewJson,
} from "../api/types";
import { ErrorState } from "../components/States";
import { MarkdownView } from "../components/MarkdownView";
import { MetricCards } from "../components/MetricCards";
import { PaperDraft } from "../components/PaperDraft";
import { AuditLedger } from "../components/AuditLedger";
import { HonestGateCards } from "../components/HonestGateCards";
import { ReviewerWeaknesses } from "../components/ReviewerWeaknesses";
import { Spinner } from "../components/Spinner";

interface ReportData {
  report: string;
  metrics: MetricsJson | null;
  review: ReviewJson | null;
  paperCount: number;
  draft: string;
  audit: ClaimAudit | null;
  anchored: AnchoredVerdict | null;
  grounding: CitationGroundingLog | null;
}

async function loadReport(projectId: string): Promise<ReportData> {
  const [
    reportText, metricsText, reviewText, papersText, draftText, auditText,
    anchoredText, groundingText,
  ] = await Promise.all([
    getFile(projectId, "research_report.md").catch(() => ""),
    getFile(projectId, "artifacts/metrics.json").catch(() => ""),
    getFile(projectId, "reviews/review_round_1.json").catch(() => ""),
    getFile(projectId, "literature/papers.jsonl").catch(() => ""),
    getFile(projectId, "paper/draft.md").catch(() => ""),
    getFile(projectId, "ledger/claim_audit.json").catch(() => ""),
    getFile(projectId, "ledger/anchored_verdict.json").catch(() => ""),
    getFile(projectId, "paper/citation_grounding_log.json").catch(() => ""),
  ]);

  const parse = <T,>(text: string): T | null => {
    if (!text) return null;
    try {
      return JSON.parse(text) as T;
    } catch {
      return null;
    }
  };

  const metrics = parse<MetricsJson>(metricsText);
  const review = parse<ReviewJson>(reviewText);
  const audit = parse<ClaimAudit>(auditText);
  const anchored = parse<AnchoredVerdict>(anchoredText);
  const grounding = parse<CitationGroundingLog>(groundingText);
  const paperCount = papersText ? papersText.split("\n").filter((l) => l.trim()).length : 0;

  return { report: reportText, metrics, review, paperCount, draft: draftText, audit, anchored, grounding };
}

export function ReportPage() {
  const { projectId = "" } = useParams();
  const [data, setData] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) {
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    loadReport(projectId)
      .then((result) => {
        if (!cancelled) {
          setData(result);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load report");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  if (!projectId) {
    return <ErrorState message="No project selected." />;
  }
  if (loading) {
    return <Spinner label="Loading report…" />;
  }
  if (error) {
    return <ErrorState message={error} />;
  }

  const hasReport = Boolean(data?.report);

  return (
    <div className="page page--report">
      <header className="page__head">
        <div>
          <h1 className="page__title">Report</h1>
          <p className="page__subtitle">
            {data?.paperCount ? `${data.paperCount} papers retrieved · ` : ""}honest conclusion, rendered verbatim.
          </p>
        </div>
      </header>

      <MetricCards metrics={data?.metrics ?? null} review={data?.review ?? null} />

      <HonestGateCards anchored={data?.anchored ?? null} />

      <section className="report__body">
        <h2 className="section__title">research_report.md</h2>
        {hasReport ? (
          <MarkdownView source={data?.report ?? ""} />
        ) : (
          <div className="callout">
            <p>No report yet. A report is generated once the run completes.</p>
            <Link className="btn btn--ghost" to={`/projects/${projectId}`}>
              View run progress
            </Link>
          </div>
        )}
      </section>

      {data?.draft ? (
        <section className="report__paper" aria-label="Paper draft">
          <details open>
            <summary className="section__title">Paper draft (paper/draft.md)</summary>
            <p className="report__paper-note">
              Written by the WriterAgent from the experiment record (one bounded revision
              pass fixes numbers the evidence doesn't support), then gated by the
              AuditorAgent. Claims with no supporting metric, and citations not found in the
              retrieved literature, are marked{" "}
              <mark className="unverified">[UNVERIFIED]</mark> inline.
            </p>
            <PaperDraft source={data.draft} />
          </details>
        </section>
      ) : null}

      {data?.audit || data?.draft ? (
        <AuditLedger audit={data?.audit ?? null} grounding={data?.grounding ?? null} />
      ) : null}

      <ReviewerWeaknesses review={data?.review ?? null} />
    </div>
  );
}
