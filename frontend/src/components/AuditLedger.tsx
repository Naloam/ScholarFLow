// Audit ledger card for the Report page. Summarizes the AuditorAgent's per-claim
// verdicts and the overall gate. A failed gate is shown prominently in red — the
// whole point of the V2/V2.1 layer is that a "plausible unsupported success" or a
// hallucinated citation is never silently passed.
//
// V2.1: claims carry a `category` (result | spin | citation) so a human can see
// at a glance WHY the gate failed — an overclaimed metric vs. a reference the
// system couldn't ground in the retrieved literature.
import type { CitationGroundingLog, ClaimAudit, ClaimCategory, ClaimVerdict } from "../api/types";

interface AuditLedgerProps {
  audit: ClaimAudit | null;
  grounding?: CitationGroundingLog | null;
}

const CATEGORY_LABEL: Record<string, string> = {
  result: "metric",
  spin: "spin",
  citation: "citation",
  omission: "omitted metric",
};

function categoryLabel(category: ClaimCategory | undefined): string {
  if (!category) return "claim";
  return CATEGORY_LABEL[category] ?? category;
}

export function AuditLedger({ audit, grounding }: AuditLedgerProps) {
  if (!audit) {
    return null;
  }

  const gate = audit.gate === true;
  const total = audit.total_claims ?? 0;
  const unverified = audit.unverified_count ?? 0;
  const citationUnverified = audit.citation_unverified_count ?? 0;
  const omissionUnverified = audit.omission_unverified_count ?? 0;
  const verified = audit.verified_count ?? total - unverified;
  const claims = audit.claims ?? [];
  const groundingRan = grounding?.revised === true;

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
            {omissionUnverified > 0 ? (
              <>
                {" "}· <strong className="audit__hot">{omissionUnverified}</strong> omitted material
                metric{omissionUnverified === 1 ? "" : "s"}
              </>
            ) : null}
            · experiment verdict: <code>{audit.verdict ?? "—"}</code>
          </>
        )}
      </p>

      {grounding ? (
        <p className="audit__grounding">
          Citation grounding: {groundingRan ? (
            <>
              removed/re-anchored {(grounding.unverified_before ?? []).length} unverified citation
              {(grounding.unverified_before ?? []).length === 1 ? "" : "s"}
              {" "}→ {(grounding.unverified_after ?? []).length} remaining
            </>
          ) : (grounding.unverified_before ?? []).length > 0 ? (
            <>no revision (still {(grounding.unverified_after ?? []).length} unverified)</>
          ) : (
            <>none needed — all citations resolved</>
          )}
          {grounding.error ? <span className="warn"> · error: {grounding.error}</span> : null}
        </p>
      ) : null}

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
