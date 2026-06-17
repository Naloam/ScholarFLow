// Audit ledger card for the Report page. Summarizes the AuditorAgent's per-claim
// verdicts and the overall gate. A failed gate is shown prominently in red — the
// whole point of the V2 layer is that a "plausible unsupported success" is never
// silently passed.
import type { ClaimAudit } from "../api/types";

interface AuditLedgerProps {
  audit: ClaimAudit | null;
}

export function AuditLedger({ audit }: AuditLedgerProps) {
  if (!audit) {
    return null;
  }

  const gate = audit.gate === true;
  const total = audit.total_claims ?? 0;
  const unverified = audit.unverified_count ?? 0;
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
            <strong className={unverified > 0 ? "audit__hot" : ""}>{unverified}</strong> unverified ·
            experiment verdict: <code>{audit.verdict ?? "—"}</code>
          </>
        )}
      </p>

      {claims.length > 0 ? (
        <ul className="audit__list">
          {claims.map((c) => (
            <li
              key={c.claim_id}
              className={`audit__claim audit__claim--${c.verdict}`}
              data-testid="audit-claim"
            >
              <div className="audit__verdict">{c.verdict}</div>
              <div className="audit__body">
                <div className="audit__text">{c.claim}</div>
                {c.reason ? <div className="audit__reason">{c.reason}</div> : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
