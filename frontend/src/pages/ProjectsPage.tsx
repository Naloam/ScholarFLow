// Projects: the entry point. Lists research-harness workspaces + a "New run"
// form (idea → POST start → jump to the Run page). Empty state guides a new
// user so features are discoverable without docs.
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { StatusBadge } from "../components/StatusBadge";
import { EmptyState, ErrorState } from "../components/States";
import { Spinner } from "../components/Spinner";
import { useProjectsStore } from "../stores/projects";

const SAMPLE_IDEA =
  "Citation-Faithful RAG Answer Verification with Evidence-Aware Retrieval and Abstention Calibration";

export function ProjectsPage() {
  const navigate = useNavigate();
  const { projects, loading, error, creating, loadProjects, createRun } = useProjectsStore();
  const [idea, setIdea] = useState("");
  const [portfolioK, setPortfolioK] = useState(3);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = idea.trim();
    if (trimmed.length < 3 || creating) {
      return;
    }
    try {
      const projectId = await createRun(trimmed, portfolioK);
      setIdea("");
      navigate(`/projects/${projectId}`);
    } catch {
      // error surfaced via store
    }
  }

  return (
    <div className="page page--projects">
      <header className="page__head">
        <div>
          <h1 className="page__title">Projects</h1>
          <p className="page__subtitle">Start an autonomous research run from a single idea.</p>
        </div>
      </header>

      <form className="newrun" onSubmit={handleSubmit}>
        <label className="newrun__label" htmlFor="idea">
          New run
        </label>
        <textarea
          id="idea"
          className="newrun__input"
          placeholder="Describe a research idea…"
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          rows={3}
          minLength={3}
          required
        />
        <div className="newrun__row">
          <label className="newrun__k" htmlFor="portfolio-k" title="How many ranked hypothesis candidates to execute (default 3, cap 5). K=1 = single-hypothesis run.">
            <span className="newrun__k-label">Portfolio K</span>
            <input
              id="portfolio-k"
              className="newrun__k-input"
              type="number"
              min={1}
              max={5}
              step={1}
              value={portfolioK}
              onChange={(e) => {
                const v = Number.parseInt(e.target.value, 10);
                if (!Number.isNaN(v)) setPortfolioK(Math.max(1, Math.min(5, v)));
              }}
            />
          </label>
          <button type="button" className="btn btn--ghost" onClick={() => setIdea(SAMPLE_IDEA)}>
            Use sample idea
          </button>
          <button type="submit" className="btn btn--primary" disabled={creating || idea.trim().length < 3}>
            {creating ? "Starting…" : "Start run"}
          </button>
        </div>
      </form>

      <section className="projectlist" aria-label="Projects">
        <h2 className="section__title">Recent runs</h2>
        {loading ? <Spinner label="Loading projects…" /> : null}
        {!loading && error ? <ErrorState message={error} onRetry={() => void loadProjects()} /> : null}
        {!loading && !error && projects.length === 0 ? (
          <EmptyState
            title="No runs yet"
            hint="Enter an idea above and start a run to see it here."
          />
        ) : null}
        {!loading && !error && projects.length > 0 ? (
          <ul className="cards">
            {projects.map((p) => (
              <li key={p.project_id}>
                <Link className="card" to={`/projects/${p.project_id}`}>
                  <div className="card__top">
                    <StatusBadge status={p.status} />
                    <span className="card__ts">{p.last_ts ?? p.updated_at ?? "—"}</span>
                  </div>
                  <div className="card__idea">{p.idea || p.project_id}</div>
                  <div className="card__meta">
                    {(p.steps_done ?? []).length}/5 steps · {p.project_id}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </div>
  );
}
