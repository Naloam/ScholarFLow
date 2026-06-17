// Audit ledger card for the Report page. Summarizes the AuditorAgent's per-claim
// verdicts and the overall gate. A failed gate is shown prominently in red — the
// whole point of the V2/V2.1 layer is that a "plausible unsupported success" or a
// hallucinated citation is never silently passed.
//
// V2.1: claims carry a `category` (result | spin | citation) so a human can see
// at a glance WHY the gate failed — an overclaimed metric vs. a reference the
// system couldn't ground in the retrieved literature.
import type { ClaimAudit, ClaimCategory, ClaimVerdict } from "../api/types";

interface AuditLedgerProps {
  audit: ClaimAudit | null;
}

const CATEGORY_LABEL: Record<string, string> = {
  result: "metric",
  spin: "spin",
  citation: "citation",
};

function categoryLabel(category: ClaimCategory | undefined): string {
  if (!category) return "claim";
  return CATEGORY_LABEL[category] ?? category;
}

export function AuditLedger({ audit }: AuditLedgerProps) {
  if (!audit) {
    return null;
  }

  const gate = audit.gate === true;
  const total = audit.total_claims ?? 0;
  const unverified = audit.unverified_count ?? 0;
  const citationUnverified = audit.citation_unverified_count ?? 0;
  const verified = audit.verified_count ?? total - unverified;
  const claims = audit.claims ?? [];

  return (
    <section className="audit" aria-label="Paper audit ledger">
      <h2 className="audit__title">
        Audit ledger
        <span
          className={`audit__gate ${gate ? "audit__gate--pass" : "audit__gate--fail"}`}
          data-testid="audit-gate"
        >
          {audit.skipped ? "skipped" : gate ? "gate passed" : "gate failed"}
        </span>
      </h2>
      <p className="audit__summary">
        {audit.skipped ? (
          <>Audit was not run ({audit.reason ?? "no draft"}).</>
        ) : (
          <>
            <strong>{verified}</strong> / {total} claims verified ·{" "}
            <strong className={unverified > 0 ? "audit__hot" : ""}>{unverified}</strong> unverified
            {citationUnverified > 0 ? (
              <>
                {" "}(<strong className="audit__hot">{citationUnverified}</strong> citation
                {citationUnverified === 1 ? "" : "s"} not in literature)
              </>
            ) : null}
            · experiment verdict: <code>{audit.verdict ?? "—"}</code>
          </>
        )}
      </p>

      {claims.length > 0 ? (
        <ul className="audit__list">
          {claims.map((c) => (
            <ClaimRow key={c.claim_id} claim={c} />
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function ClaimRow({ claim }: { claim: ClaimVerdict }) {
  const isCitation = claim.category === "citation";
  return (
    <li
      className={`audit__claim audit__claim--${claim.verdict}`}
      data-testid="audit-claim"
      data-category={claim.category ?? "result"}
    >
      <div className="audit__verdict">{claim.verdict}</div>
      <div className="audit__body">
        <div className="audit__head">
          <span className={`audit__chip audit__chip--${claim.category ?? "result"}`}>
            {categoryLabel(claim.category)}
          </span>
          {isCitation && claim.marker ? <span className="audit__marker">{claim.marker}</span> : null}
        </div>
        <div className="audit__text">{claim.claim}</div>
        {claim.reason ? <div className="audit__reason">{claim.reason}</div> : null}
      </div>
    </li>
  );
}
