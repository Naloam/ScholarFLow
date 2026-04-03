import type { Draft } from "../../api/types";
import { formatDate } from "../../utils/format";

type FileManagerProps = {
  drafts: Draft[];
  selectedDraftVersion: number | null;
  latestExportId?: string | null;
  latestExportStatus?: string | null;
  downloading: boolean;
  onSelect: (version: number) => void;
  onDownloadLatestExport: () => Promise<void>;
};

export function FileManager({
  drafts,
  selectedDraftVersion,
  latestExportId,
  latestExportStatus,
  downloading,
  onSelect,
  onDownloadLatestExport,
}: FileManagerProps) {
  const latestExportReady =
    Boolean(latestExportId) && latestExportStatus === "done";

  return (
    <section className="panel" data-testid="file-manager">
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
              data-testid={`draft-item-v${draft.version}`}
              className={
                draft.version === selectedDraftVersion
                  ? "list-item selected"
                  : "list-item"
              }
              onClick={() => onSelect(draft.version)}
            >
              <span>Draft v{draft.version}</span>
              <small>{formatDate(draft.created_at)}</small>
            </button>
          ))}
        </div>
      )}

      <div className="inline-card" data-testid="export-center">
        <p className="inline-title">Export Center</p>
        <p className="auth-copy" data-testid="latest-export-status">
          {latestExportReady
            ? `Latest export ${latestExportId} is ready`
            : latestExportStatus
              ? `Latest export status: ${latestExportStatus}`
              : "No completed export yet."}
        </p>
        <div className="button-row">
          <button
            className="ghost-btn"
            data-testid="download-latest-export-button"
            disabled={!latestExportReady || downloading}
            onClick={() => void onDownloadLatestExport()}
          >
            Download Latest Export
          </button>
        </div>
      </div>
    </section>
  );
}
