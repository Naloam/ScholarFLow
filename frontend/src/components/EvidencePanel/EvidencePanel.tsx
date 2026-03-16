import type { EvidenceItem } from "../../api/types";

type EvidencePanelProps = {
  evidence: EvidenceItem[];
  focusedText: string;
};

function scoreEvidence(item: EvidenceItem, focusedText: string): number {
  if (!focusedText.trim()) {
    return 0;
  }
  const snippet = `${item.claim_text} ${item.snippet ?? ""}`.toLowerCase();
  return focusedText
    .toLowerCase()
    .split(/\s+/)
    .filter((token) => token && snippet.includes(token)).length;
}

export function EvidencePanel({ evidence, focusedText }: EvidencePanelProps) {
  const sortedEvidence = [...evidence].sort(
    (left, right) => scoreEvidence(right, focusedText) - scoreEvidence(left, focusedText),
  );

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Evidence Trace</p>
          <h2 className="panel-title">Evidence Panel</h2>
        </div>
        <span className="badge badge-soft">{evidence.length} items</span>
      </div>

      {focusedText ? (
        <div className="inline-card">
          <p className="inline-title">Focused passage</p>
          <p className="focus-copy">{focusedText}</p>
        </div>
      ) : null}

      {evidence.length === 0 ? (
        <div className="empty-state">
          <p>No evidence linked yet.</p>
          <span>Once a draft claim is mapped to chunks, the support trail will appear here.</span>
        </div>
      ) : (
        <div className="stack">
          {sortedEvidence.slice(0, 8).map((item, index) => (
            <article key={`${item.claim_text}-${index}`} className="evidence-card">
              <strong>{item.claim_text}</strong>
              <p>{item.snippet || "No snippet captured"}</p>
              <small>
                Paper {item.paper_id}
                {item.section ? ` | ${item.section}` : ""}
                {item.page !== null && item.page !== undefined ? ` | p.${item.page}` : ""}
              </small>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
