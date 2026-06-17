// Reviewer weaknesses list for the bottom of the Report page. Surfaces major
// issues with their concrete evidence so the human sees the honest critique.
import type { ReviewJson } from "../api/types";

interface ReviewerWeaknessesProps {
  review: ReviewJson | null;
}

export function ReviewerWeaknesses({ review }: ReviewerWeaknessesProps) {
  const weaknesses = review?.weaknesses ?? [];
  if (weaknesses.length === 0) {
    return null;
  }
  const major = weaknesses.filter((w) => (w.severity ?? "minor") === "major");

  return (
    <section className="reviewer" aria-label="Reviewer critique">
      <h2 className="reviewer__title">
        Reviewer weaknesses
        <span className="reviewer__count">
          {major.length} major · {weaknesses.length - major.length} minor
        </span>
      </h2>
      <ul className="reviewer__list">
        {weaknesses.map((w, idx) => (
          <li key={idx} className={`reviewer__item reviewer__item--${w.severity ?? "minor"}`}>
            <div className="reviewer__severity">{w.severity ?? "minor"}</div>
            <div className="reviewer__body">
              <div className="reviewer__issue">{w.issue}</div>
              {w.evidence ? <div className="reviewer__evidence">{w.evidence}</div> : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
