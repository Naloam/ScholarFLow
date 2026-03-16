import type { Draft } from "../../api/types";
import { formatDate } from "../../utils/format";

type FileManagerProps = {
  drafts: Draft[];
  selectedDraftVersion: number | null;
  onSelect: (version: number) => void;
};

export function FileManager({ drafts, selectedDraftVersion, onSelect }: FileManagerProps) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Draft Inventory</p>
          <h2 className="panel-title">File Manager</h2>
        </div>
        <span className="badge badge-soft">{drafts.length} drafts</span>
      </div>

      {drafts.length === 0 ? (
        <div className="empty-state">
          <p>No drafts yet.</p>
          <span>Use the Generate Draft action to seed the workspace.</span>
        </div>
      ) : (
        <div className="list-block">
          {drafts.map((draft) => (
            <button
              key={draft.version}
              className={
                draft.version === selectedDraftVersion ? "list-item selected" : "list-item"
              }
              onClick={() => onSelect(draft.version)}
            >
              <span>Draft v{draft.version}</span>
              <small>{formatDate(draft.created_at)}</small>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
