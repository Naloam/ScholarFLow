import { useTranslation } from "react-i18next";

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
  const { t } = useTranslation();

  return (
    <footer className="status-bar" data-testid="status-bar">
      <span data-testid="status-notice">{notice}</span>
      <span data-testid="status-project">
        {projectId ? `Project ${projectId}` : t("status.noProject")}
      </span>
      <span data-testid="status-draft">
        {selectedDraftVersion
          ? `Draft v${selectedDraftVersion}`
          : t("status.noDraft")}
      </span>
      <span data-testid="status-socket">
        {`Progress socket: ${connectionState}`}
      </span>
      <span data-testid="status-auth">{authLabel}</span>
      <span data-testid="status-working">
        {working ? t("status.working") : t("status.idle")}
      </span>
    </footer>
  );
}
