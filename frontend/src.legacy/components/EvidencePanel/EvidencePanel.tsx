import { useTranslation } from "react-i18next";

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
  const { t } = useTranslation();

  const sortedEvidence = [...evidence].sort(
    (left, right) =>
      scoreEvidence(right, focusedText) - scoreEvidence(left, focusedText),
  );

  return (
    <section className="panel" data-testid="evidence-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{t("evidence.eyebrow")}</p>
          <h2 className="panel-title">{t("evidence.title")}</h2>
        </div>
        <span className="badge badge-soft">{evidence.length} items</span>
      </div>

      {focusedText ? (
        <div className="inline-card">
          <p className="inline-title">{t("evidence.focusedPassage")}</p>
          <p className="focus-copy">{focusedText}</p>
        </div>
      ) : null}

      {evidence.length === 0 ? (
        <div className="empty-state">
          <p>{t("evidence.noEvidenceTitle")}</p>
          <span>{t("evidence.noEvidenceDetail")}</span>
        </div>
      ) : (
        <div className="stack">
          {sortedEvidence.slice(0, 8).map((item, index) => (
            <article
              key={`${item.claim_text}-${index}`}
              className="evidence-card"
            >
              <strong>{item.claim_text}</strong>
              <p>{item.snippet || t("evidence.noSnippet")}</p>
              <small>
                Paper {item.paper_id}
                {item.section ? ` | ${item.section}` : ""}
                {item.page !== null && item.page !== undefined
                  ? ` | p.${item.page}`
                  : ""}
              </small>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
