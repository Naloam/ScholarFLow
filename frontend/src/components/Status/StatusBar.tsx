type StatusBarProps = {
  notice: string;
  projectId: string;
  selectedDraftVersion: number | null;
  working: boolean;
  connectionState: "disconnected" | "connecting" | "live";
  authLabel: string;
};

export function StatusBar({
  notice,
  projectId,
  selectedDraftVersion,
  working,
  connectionState,
  authLabel,
}: StatusBarProps) {
  return (
    <footer className="status-bar" data-testid="status-bar">
      <span data-testid="status-notice">{notice}</span>
      <span data-testid="status-project">
        {projectId ? `Project ${projectId}` : "No project open"}
      </span>
      <span data-testid="status-draft">
        {selectedDraftVersion ? `Draft v${selectedDraftVersion}` : "No draft selected"}
      </span>
      <span data-testid="status-socket">{`Progress socket: ${connectionState}`}</span>
      <span data-testid="status-auth">{authLabel}</span>
      <span data-testid="status-working">{working ? "Working..." : "Idle"}</span>
    </footer>
  );
}
