// Vertical timeline of the 5 agent steps. Shows done/error/running/pending with
// icon + timestamp + per-step duration. Honest: a failed step renders as error,
// never silently promoted to success.
import type { TimelineEntry } from "../api/types";

const STEP_ORDER = ["literature", "idea", "experiment", "review", "report"] as const;

const STEP_LABELS: Record<string, string> = {
  literature: "Literature",
  idea: "Idea",
  experiment: "Experiment",
  review: "Review",
  report: "Report",
};

interface TimelineProps {
  entries: TimelineEntry[];
  currentStep?: string | null;
}

function durationLabel(start?: string | null, end?: string | null): string | null {
  if (!start || !end) {
    return null;
  }
  const ms = Date.parse(end) - Date.parse(start);
  if (!Number.isFinite(ms) || ms < 0) {
    return null;
  }
  if (ms < 60_000) {
    return `${Math.max(1, Math.round(ms / 1000))}s`;
  }
  return `${Math.round(ms / 60000)}m`;
}

export function Timeline({ entries, currentStep }: TimelineProps) {
  // Keep the last status per step (timeline can have duplicates on rerun).
  const byStep = new Map<string, TimelineEntry>();
  for (const entry of entries) {
    byStep.set(entry.step, entry);
  }
  const prevTs: (string | null)[] = [];

  return (
    <ol className="timeline" aria-label="Run timeline">
      {STEP_ORDER.map((step, idx) => {
        const entry = byStep.get(step);
        const status = entry?.status ?? (currentStep === step ? "running" : "pending");
        const startTs = prevTs[idx - 1] ?? null;
        const duration = durationLabel(startTs, entry?.ts ?? null);
        prevTs[idx] = entry?.ts ?? prevTs[idx - 1] ?? null;
        return (
          <li key={step} className={`timeline__item timeline__item--${status}`}>
            <span className="timeline__icon" aria-hidden="true">
              {status === "done" ? "✓" : status === "error" ? "✗" : status === "running" ? "●" : "○"}
            </span>
            <div className="timeline__body">
              <div className="timeline__head">
                <span className="timeline__step">{STEP_LABELS[step] ?? step}</span>
                {duration ? <span className="timeline__duration">{duration}</span> : null}
              </div>
              {entry?.ts ? <time className="timeline__ts">{entry.ts}</time> : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
