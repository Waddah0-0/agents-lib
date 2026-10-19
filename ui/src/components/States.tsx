import type { ReactNode } from "react";
import { API_LABEL, ApiUnreachable } from "../api/client";
import { Button } from "./Button";
import { CopyButton } from "./CopyButton";
import { Icon } from "./Icon";
import type { IconName } from "./icons";
import styles from "./States.module.css";

/** A calm, centred message with its icon on a small tilted sheet. */
export function EmptyState({
  icon,
  title,
  children,
  action,
  tone = "neutral",
}: {
  icon: IconName;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  tone?: "neutral" | "error";
}) {
  return (
    <div className={styles.empty} data-tone={tone}>
      <span className={styles.badge}>
        <Icon name={icon} size={34} />
      </span>
      <h2 className="headline-s">{title}</h2>
      {children && <div className={`body-l muted ${styles.body}`}>{children}</div>}
      {action && <div className={styles.action}>{action}</div>}
    </div>
  );
}

/** What to show when a request failed: a hint to start the API, or the error itself. */
export function ErrorState({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  const retry = onRetry && (
    <Button variant="tonal" icon="refresh" onClick={onRetry}>
      Try again
    </Button>
  );
  if (error instanceof ApiUnreachable) {
    return (
      <EmptyState icon="offline" title="Can't reach the API" action={retry}>
        <p>
          The UI talks to the margin API at <code className="mono">{API_LABEL}</code>. Start it from the
          repository:
        </p>
        <div className={styles.command}>
          <code>uv run margin-api</code>
          <CopyButton text="uv run margin-api" label="Copy command" />
        </div>
      </EmptyState>
    );
  }
  return (
    <EmptyState icon="error" title="Something went wrong" tone="error" action={retry}>
      <p>{error.message}</p>
    </EmptyState>
  );
}
