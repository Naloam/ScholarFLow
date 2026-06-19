// V2.2 hypothesis-anchored honest-gate cards (goal_session8.md).
//
// Surfaces the signals that stop a "plausible unsupported success": the verdict
// anchored to the hypothesis's OWN primary metric (not a cherry-picked generic
// one), tripped kill criteria, named baselines that were never run, an
// underpowered seed count, and whether a reviewer follow-up was merged.
//
// HONESTY CONTRACT: data comes verbatim from ledger/anchored_verdict.json (written
// by the backend from evidence.full_verdict). The frontend never re-derives the
// verdict, and never reframes a downgrade as success. No signal → render nothing.
import type { AnchoredVerdict, KillCriterion } from "../api/types";

interface HonestGateCardsProps {
  anchored: AnchoredVerdict | null;
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

function Card({
  label,
  tone = "neutral",
  children,
}: {
  label: string;
  tone?: Tone;
  children: React.ReactNode;
}) {
  return (
    <div className={`metric metric--${tone}`}>
      <div className="metric__label">{label}</div>
      <div className="metric__value">{children}</div>
    </div>
  );
}

function KillCriteria({ criteria }: { criteria: KillCriterion[] }) {
  if (criteria.length === 0) {
    return null;
  }
  return (
    <ul className="hgate__kills">
      {criteria.map((kc, i) => {
        const tone = kc.tripped ? "tripped" : kc.needs_manual ? "manual" : "ok";
        const badge = kc.tripped ? "tripped" : kc.needs_manual ? "needs review" : "not tripped";
        return (
          <li key={i} className={`hgate__kill hgate__kill--${tone}`}>
            <span className={`chip chip--${tone}`}>{badge}</span>
            <span className="hgate__kill-text">{kc.criterion}</span>
            {kc.reason ? <span className="hgate__kill-reason">{kc.reason}</span> : null}
          </li>
        );
      })}
    </ul>
  );
}

export function HonestGateCards({ anchored }: HonestGateCardsProps) {
  if (!anchored) {
    return null;
  }

  const verdict = anchored.verdict;
  const tone = toneFor(verdict);
  const downgraded = anchored.downgraded === true;
  const tripped = (anchored.kill_criteria ?? []).filter((k) => k.tripped);
  const manual = (anchored.kill_criteria ?? []).filter((k) => k.needs_manual && !k.tripped);
  const missing = anchored.missing_baselines ?? [];
  const underpowered = anchored.underpowered;
  const followUp = anchored.follow_up;
  // Anything to show beyond the bare verdict?
  const hasDetail =
    downgraded ||
    tripped.length > 0 ||
    manual.length > 0 ||
    missing.length > 0 ||
    Boolean(underpowered) ||
    Boolean(followUp);

  return (
    <section className="hgate" aria-label="Hypothesis-anchored honest gate">
      <div className={`hgate__banner hgate__banner--${tone}`}>
        <div className="hgate__banner-label">Anchored verdict</div>
        <div className="hgate__banner-value">
          <strong>{verdictLabel(verdict)}</strong>
          {downgraded ? (
            <span className="hgate__downgrade">
              {" "}· downgraded from {verdictLabel(anchored.base_verdict)}
            </span>
          ) : null}
        </div>
        <div className="hgate__banner-detail">
          primary metric: <code>{anchored.primary_metric ?? "—"}</code>{" "}
          (source: {anchored.primary_metric_source ?? "—"}; beats baseline:{" "}
          <span className={anchored.primary_beats_baseline === false ? "warn" : ""}>
            {String(anchored.primary_beats_baseline ?? "—")}
          </span>
          )
        </div>
      </div>

      {hasDetail ? (
        <div className="hgate__grid">
          {(anchored.kill_criteria ?? []).length > 0 ? (
            <Card label="Kill criteria" tone={tripped.length > 0 ? "negative" : "neutral"}>
              <KillCriteria criteria={anchored.kill_criteria ?? []} />
            </Card>
          ) : null}

          {missing.length > 0 ? (
            <Card label="Missing baselines" tone="negative">
              <p className="hgate__note">
                Named in the hypothesis but NOT run:
              </p>
              <div className="hgate__chips">
                {missing.map((b) => (
                  <span key={b} className="chip chip--tripped">{b}</span>
                ))}
              </div>
            </Card>
          ) : null}

          {underpowered ? (
            <Card label="Statistical power" tone="mixed">
              <p className="hgate__note">{underpowered.note}</p>
            </Card>
          ) : null}

          {followUp ? (
            <Card label="Reviewer follow-up" tone={followUp.ran ? "positive" : "neutral"}>
              {followUp.ran ? (
                <span>
                  ran · added: {(followUp.systems_added ?? []).join(", ") || "—"}
                </span>
              ) : (
                <span>not run{followUp.reason ? ` (${followUp.reason})` : ""}</span>
              )}
            </Card>
          ) : null}
        </div>
      ) : null}

      {downgraded && (anchored.downgrade_reasons ?? []).length > 0 ? (
        <ul className="hgate__reasons">
          {anchored.downgrade_reasons!.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
