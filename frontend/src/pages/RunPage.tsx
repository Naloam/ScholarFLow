// Run: status badge + live step timeline for one project. Polls status/timeline
// every few seconds while the run is in flight and stops once it reaches a
// terminal state. One screen, one task — progress only.
import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";

import { ErrorState } from "../components/States";
import { Spinner } from "../components/Spinner";
import { StatusBadge } from "../components/StatusBadge";
import { Timeline } from "../components/Timeline";
import { useRunStore } from "../stores/run";

const POLL_MS = 6000;
const IN_FLIGHT = new Set(["running", "partial", "pending"]);

export function RunPage() {
  const { projectId = "" } = useParams();
  const { status, timeline, loading, error, load, refresh } = useRunStore();

  useEffect(() => {
    if (!projectId) {
      return;
    }
    void load(projectId);
  }, [projectId, load]);

  useEffect(() => {
    if (!projectId || !status) {
      return;
    }
    if (!IN_FLIGHT.has(status.status)) {
      return;
    }
    const handle = window.setInterval(() => {
      void refresh(projectId);
    }, POLL_MS);
    return () => window.clearInterval(handle);
  }, [projectId, status, refresh]);

  if (!projectId) {
    return <ErrorState message="No project selected." />;
  }
  if (loading && !status) {
    return <Spinner label="Loading run…" />;
  }
  if (error && !status) {
    return <ErrorState message={error} onRetry={() => void load(projectId)} />;
  }

  const isPending = status?.status === "pending" && timeline.length === 0;

  return (
    <div className="page page--run">
      <header className="page__head">
        <div>
          <h1 className="page__title">Run</h1>
          <p className="page__subtitle">{status?.idea || projectId}</p>
        </div>
        {status ? <StatusBadge status={status.status} /> : null}
      </header>

      {isPending ? (
        <div className="callout">
          <p>No run started for this project yet.</p>
          <Link className="btn btn--primary" to="/">
            Start a run from Projects
          </Link>
        </div>
      ) : (
        <section className="runboard">
          <div className="runboard__meta">
            {status?.current_step ? (
              <span className="runboard__current">Working on: {status.current_step}…</span>
            ) : null}
            {status?.execution_status ? (
              <span className="runboard__exec">execution: {status.execution_status}</span>
            ) : null}
          </div>
          <Timeline entries={timeline} currentStep={status?.current_step ?? null} />
        </section>
      )}
    </div>
  );
}
