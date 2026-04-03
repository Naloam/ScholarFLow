import type { Draft } from "../../api/types";

type DiffRow = {
  type: "same" | "added" | "removed";
  text: string;
};

type VersionDiffPanelProps = {
  drafts: Draft[];
  selectedDraftVersion: number | null;
  currentContent: string;
};

function buildDiffRows(
  previousContent: string,
  currentContent: string,
): DiffRow[] {
  const previousLines = previousContent.split("\n");
  const currentLines = currentContent.split("\n");

  let prefix = 0;
  while (
    prefix < previousLines.length &&
    prefix < currentLines.length &&
    previousLines[prefix] === currentLines[prefix]
  ) {
    prefix += 1;
  }

  let suffix = 0;
  while (
    suffix < previousLines.length - prefix &&
    suffix < currentLines.length - prefix &&
    previousLines[previousLines.length - 1 - suffix] ===
      currentLines[currentLines.length - 1 - suffix]
  ) {
    suffix += 1;
  }

  const rows: DiffRow[] = [];

  previousLines.slice(0, prefix).forEach((line) => {
    rows.push({ type: "same", text: line });
  });

  previousLines
    .slice(prefix, previousLines.length - suffix)
    .forEach((line) => rows.push({ type: "removed", text: line }));

  currentLines
    .slice(prefix, currentLines.length - suffix)
    .forEach((line) => rows.push({ type: "added", text: line }));

  previousLines
    .slice(previousLines.length - suffix)
    .forEach((line) => rows.push({ type: "same", text: line }));

  return rows;
}

export function VersionDiffPanel({
  drafts,
  selectedDraftVersion,
  currentContent,
}: VersionDiffPanelProps) {
  if (selectedDraftVersion === null) {
    return (
      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Versioning</p>
            <h2 className="panel-title">Draft Diff</h2>
          </div>
        </div>
        <div className="empty-state">
          <p>No draft selected.</p>
          <span>Generate a draft first to inspect version changes.</span>
        </div>
      </section>
    );
  }

  const sortedDrafts = [...drafts].sort(
    (left, right) => right.version - left.version,
  );
  const currentDraft =
    sortedDrafts.find((draft) => draft.version === selectedDraftVersion) ??
    null;
  const previousDraft =
    [...sortedDrafts]
      .reverse()
      .filter((draft) => draft.version < selectedDraftVersion)
      .pop() ?? null;

  if (!currentDraft || !previousDraft) {
    return (
      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Versioning</p>
            <h2 className="panel-title">Draft Diff</h2>
          </div>
          <span className="badge badge-soft">v{selectedDraftVersion}</span>
        </div>
        <div className="empty-state">
          <p>No earlier version to compare.</p>
          <span>
            Generate another draft version to unlock side-by-side review
            history.
          </span>
        </div>
      </section>
    );
  }

  const rows = buildDiffRows(previousDraft.content, currentContent);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Versioning</p>
          <h2 className="panel-title">Draft Diff</h2>
        </div>
        <span className="badge badge-soft">
          {`v${previousDraft.version} -> v${selectedDraftVersion}`}
        </span>
      </div>

      <div className="diff-stack">
        {rows.slice(0, 80).map((row, index) => (
          <article
            key={`${row.type}-${index}-${row.text}`}
            className={`diff-row diff-${row.type}`}
          >
            <span className="diff-prefix">
              {row.type === "added" ? "+" : row.type === "removed" ? "-" : "="}
            </span>
            <pre>{row.text || " "}</pre>
          </article>
        ))}
      </div>
    </section>
  );
}
