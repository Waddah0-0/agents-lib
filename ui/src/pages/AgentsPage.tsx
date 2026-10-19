import { useAgents } from "../api/hooks";
import { AgentCard } from "../components/AgentCard";
import { Icon } from "../components/Icon";
import { PageLoading } from "../components/Loading";
import { EmptyState, ErrorState } from "../components/States";
import styles from "./pages.module.css";

export function AgentsPage() {
  const agents = useAgents();
  const list = agents.data?.agents ?? [];
  const failed = Object.entries(agents.data?.load_errors ?? {});

  return (
    <div className={styles.page}>
      <header className={styles.pageHead}>
        <h1>Agents</h1>
        <p className="body-l muted">
          Every agent installed alongside the API. Each one takes typed input and returns a result with its
          evidence.
        </p>
      </header>

      {agents.loading && !agents.data && <PageLoading label="Loading agents" />}
      {agents.error && <ErrorState error={agents.error} onRetry={agents.reload} />}

      {failed.map(([id, reason]) => (
        <div key={id} className={styles.loadError} role="alert">
          <Icon name="error" />
          <div>
            <p className="title-s">{id} failed to load</p>
            <p className="body-m">{reason}</p>
          </div>
        </div>
      ))}

      {agents.data && list.length === 0 && (
        <EmptyState icon="widgets" title="No agents installed">
          <p>Agents are Python packages registered under the agents_lib.agents entry point.</p>
        </EmptyState>
      )}

      {list.length > 0 && (
        <div className={styles.grid}>
          {list.map((agent) => (
            <AgentCard key={agent.id} agent={agent} />
          ))}
        </div>
      )}
    </div>
  );
}
