import type { RunStatusKind } from "../api/types";

const LABELS: Record<RunStatusKind, string> = {
  running: "Running",
  done: "Done",
  error: "Error",
  partial: "In progress",
  pending: "Pending",
};

interface StatusBadgeProps {
  status: RunStatusKind | string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const kind = (status as RunStatusKind) in LABELS ? (status as RunStatusKind) : "pending";
  return <span className={`badge badge--${kind}`} data-testid="status-badge">{LABELS[kind]}</span>;
}
