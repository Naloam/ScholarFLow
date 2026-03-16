type StatusBarProps = {
  notice: string;
  projectId: string;
  selectedDraftVersion: number | null;
  working: boolean;
  connectionState: "disconnected" | "connecting" | "live";
};

export function StatusBar({
  notice,
  projectId,
  selectedDraftVersion,
  working,
  connectionState,
}: StatusBarProps) {
  return (
    <footer className="status-bar">
      <span>{notice}</span>
      <span>{projectId ? `Project ${projectId}` : "No project open"}</span>
      <span>{selectedDraftVersion ? `Draft v${selectedDraftVersion}` : "No draft selected"}</span>
      <span>{`Progress socket: ${connectionState}`}</span>
      <span>{working ? "Working..." : "Idle"}</span>
    </footer>
  );
}
