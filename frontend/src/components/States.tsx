import type { ReactNode } from "react";
import { AlertTriangle, Inbox } from "lucide-react";
import "./components.css";

export function Loader({ label = "Loading data…" }: { label?: string }) {
  return (
    <div className="loader" role="status">
      <div className="loader__spinner" aria-hidden />
      <span>{label}</span>
    </div>
  );
}

interface EmptyStateProps {
  title?: string;
  message?: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
}

export function EmptyState({ title = "Nothing here yet", message, icon, action }: EmptyStateProps) {
  return (
    <div className="state-block">
      <div className="state-block__icon" aria-hidden>
        {icon ?? <Inbox size={30} />}
      </div>
      <div className="state-block__title">{title}</div>
      {message ? <div className="state-block__message">{message}</div> : null}
      {action ? <div>{action}</div> : null}
    </div>
  );
}

interface ErrorStateProps {
  message: ReactNode;
  title?: string;
  onRetry?: () => void;
  action?: ReactNode;
}

export function ErrorState({ message, title = "Something went wrong", onRetry, action }: ErrorStateProps) {
  return (
    <div className="state-block state-block--error" role="alert">
      <div className="state-block__icon" aria-hidden>
        <AlertTriangle size={30} />
      </div>
      <div className="state-block__title">{title}</div>
      <div className="state-block__message">{message}</div>
      {onRetry ? (
        <button type="button" className="btn" onClick={onRetry}>
          Try again
        </button>
      ) : null}
      {action ? <div>{action}</div> : null}
    </div>
  );
}
