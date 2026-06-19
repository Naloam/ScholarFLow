// V2.3 portfolio summary card (goal_session9.md Step 7).
//
// Renders the honest portfolio: one row per executed candidate, each independently
// gated by the full V2.2 honest gate. Columns: candidate / primary_metric / beats
// baseline / verdict (tone-coloured) / kill tripped / downgraded. The best candidate
// (anchored-verdict winner) row is highlighted.
//
// HONESTY CONTRACT: data comes verbatim from ledger/portfolio.json (written by the
// backend from evidence.full_verdict per candidate + portfolio.aggregate_portfolio).
// The frontend never re-derives a verdict and never reframes an all-negative /
// mixed portfolio as positive. No portfolio.json → render nothing (additive).
import type { PortfolioSummary } from "../api/types";

interface PortfolioCardProps {
  portfolio: PortfolioSummary | null;
}

type Tone = "positive" | "mixed" | "negative" | "neutral";

const VERDICT_TONE: Record<string, Tone> = {
  positive_significant: "positive",
  positive_not_significant: "mixed",
  mixed: "mixed",
  negative: "negative",
  no_comparison: "neutral",
  execution_failed: "neutral",
};

function toneFor(verdict: string | undefined): Tone {
  return (verdict && VERDICT_TONE[verdict]) || "neutral";
}

function verdictLabel(verdict: string | undefined): string {
  if (!verdict) return "—";
  return verdict.replace(/_/g, " ");
}

function beatsLabel(beats: boolean | null | undefined): string {
  if (beats === null || beats === undefined) return "—";
  return beats ? "yes" : "no";
}

function PortfolioVerdictBadge({ verdict }: { verdict: string | undefined }) {
  // Portfolio-level label: all_negative / mixed_portfolio / best=<v>. Tone it so a
  // glance conveys honesty (all_negative reads red, mixed reads amber, best=positive green).
  const v = verdict ?? "";
  let tone: Tone = "neutral";
  if (v === "all_negative") tone = "negative";
  else if (v === "mixed_portfolio") tone = "mixed";
  else if (v.startsWith("best=positive_significant")) tone = "positive";
  else if (v.startsWith("best=")) tone = "mixed";
  return <span className={`chip chip--${tone}`}>{v || "—"}</span>;
}

export function PortfolioCard({ portfolio }: PortfolioCardProps) {
  if (!portfolio || !portfolio.rows || portfolio.rows.length === 0) {
    return null;
  }

  const { rows, portfolio_verdict: portfolioVerdict, best_candidate_id: bestId, k, note } = portfolio;

  return (
    <section className="portfolio" aria-label="Portfolio summary">
      <div className="portfolio__head">
        <h2 className="section__title">Portfolio</h2>
        <p className="portfolio__sub">
          {k ? `K=${k} candidates ran · ` : ""}each independently gated by the V2.2 honest gate.
        </p>
      </div>

      <div className="portfolio__verdict">
        <span className="portfolio__verdict-label">Portfolio verdict</span>
        <PortfolioVerdictBadge verdict={portfolioVerdict} />
        {bestId ? (
          <span className="portfolio__best">best: <code>{bestId}</code></span>
        ) : null}
      </div>

      <div className="portfolio__table-wrap">
        <table className="portfolio__table">
          <caption className="portfolio__caption">
            One row per executed research hypothesis; the best candidate (★) is the
            anchored-verdict winner this report is built on.
          </caption>
          <thead>
            <tr>
              <th scope="col">Candidate</th>
              <th scope="col">Primary metric</th>
              <th scope="col">Beats baseline</th>
              <th scope="col">Verdict</th>
              <th scope="col">Kill tripped</th>
              <th scope="col">Downgraded</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const tone = toneFor(row.verdict);
              const isBest = row.is_best === true || row.candidate_id === bestId;
              const title = row.title || row.candidate_id;
              return (
                <tr key={row.candidate_id} className={`portfolio__row portfolio__row--${tone}${isBest ? " portfolio__row--best" : ""}`}>
                  <th scope="row" className="portfolio__candidate">
                    {isBest ? <span className="portfolio__star" aria-label="best candidate">★</span> : null}
                    <span className="portfolio__title">{title}</span>
                    <code className="portfolio__cid">{row.candidate_id}</code>
                  </th>
                  <td><code>{row.primary_metric || "—"}</code></td>
                  <td>{beatsLabel(row.beats_baseline)}</td>
                  <td><span className={`chip chip--${tone}`}>{verdictLabel(row.verdict)}</span></td>
                  <td>{row.kill_tripped ? <span className="chip chip--tripped">yes</span> : "—"}</td>
                  <td>{row.downgraded ? <span className="chip chip--manual">yes</span> : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {note ? <p className="portfolio__note">{note}</p> : null}
      <p className="portfolio__foot">
        Per-candidate detail lives in <code>candidates/&lt;id&gt;/</code>; the report below is
        the best candidate&rsquo;s full run.
      </p>
    </section>
  );
}
