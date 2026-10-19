import type { ReactNode } from "react";
import { API_URL, ApiUnreachable } from "../api/client";
import { shapePath } from "./AgentShape";
import { Button } from "./Button";
import { CopyButton } from "./CopyButton";
import { Icon } from "./Icon";
import type { IconName } from "./icons";
import styles from "./States.module.css";

const BLOB = shapePath({ lobes: 9, depth: 0.06, turn: 0 });

/** A calm, centred message with an icon inside a soft shape. */
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
        <svg viewBox="0 0 100 100" aria-hidden="true">
          <path d={BLOB} />
        </svg>
        <Icon name={icon} size={36} />
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
      <EmptyState icon="cloud_off" title="Can't reach the API" action={retry}>
        <p>
          The UI talks to the agents-lib API at <code className="mono">{API_URL}</code>. Start it from the
          repository:
        </p>
        <div className={styles.command}>
          <code>uv run agents-api</code>
          <CopyButton text="uv run agents-api" label="Copy command" />
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
