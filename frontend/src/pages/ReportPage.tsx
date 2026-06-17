// Report: the headline output. Metric cards (execution_status / verdict /
// significance / abstention) + faithful research_report.md render + reviewer
// weaknesses. The report text is rendered verbatim — negative/null/Mixed
// conclusions are never reframed as positive (honesty gate, goal §避坑 #8).
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getFile } from "../api/client";
import type { MetricsJson, ReviewJson } from "../api/types";
import { ErrorState } from "../components/States";
import { MarkdownView } from "../components/MarkdownView";
import { MetricCards } from "../components/MetricCards";
import { ReviewerWeaknesses } from "../components/ReviewerWeaknesses";
import { Spinner } from "../components/Spinner";

interface ReportData {
  report: string;
  metrics: MetricsJson | null;
  review: ReviewJson | null;
  paperCount: number;
}

async function loadReport(projectId: string): Promise<ReportData> {
  const [reportText, metricsText, reviewText, papersText] = await Promise.all([
    getFile(projectId, "research_report.md").catch(() => ""),
    getFile(projectId, "artifacts/metrics.json").catch(() => ""),
    getFile(projectId, "reviews/review_round_1.json").catch(() => ""),
    getFile(projectId, "literature/papers.jsonl").catch(() => ""),
  ]);

  let metrics: MetricsJson | null = null;
  if (metricsText) {
    try {
      metrics = JSON.parse(metricsText) as MetricsJson;
    } catch {
      metrics = null;
    }
  }
  let review: ReviewJson | null = null;
  if (reviewText) {
    try {
      review = JSON.parse(reviewText) as ReviewJson;
    } catch {
      review = null;
    }
  }
  const paperCount = papersText ? papersText.split("\n").filter((l) => l.trim()).length : 0;

  return { report: reportText, metrics, review, paperCount };
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

      <ReviewerWeaknesses review={data?.review ?? null} />
    </div>
  );
}
