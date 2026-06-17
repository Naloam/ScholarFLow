// Empty + Error state primitives. Keep them small and composable.

interface EmptyStateProps {
  title: string;
  hint?: string;
  action?: React.ReactNode;
}

export function EmptyState({ title, hint, action }: EmptyStateProps) {
  return (
    <div className="state state--empty">
      <div className="state__title">{title}</div>
      {hint ? <div className="state__hint">{hint}</div> : null}
      {action ? <div className="state__action">{action}</div> : null}
    </div>
  );
}

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="state state--error" role="alert">
      <div className="state__title">Something went wrong</div>
      <div className="state__hint">{message}</div>
      {onRetry ? (
        <button type="button" className="btn btn--ghost" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}
