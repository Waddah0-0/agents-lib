import { useLocation, useParams } from "react-router";
import { useAgents } from "../api/hooks";
import { AgentAvatar } from "../components/AgentAvatar";
import { LinkButton } from "../components/Button";
import { Icon } from "../components/Icon";
import { PageLoading } from "../components/Loading";
import { EmptyState, ErrorState } from "../components/States";
import { SchemaForm } from "../form/SchemaForm";
import type { FormValues } from "../form/schema";
import { agentIntroFor } from "../results/registry";
import styles from "./pages.module.css";

export function AgentPage() {
  const { agentId = "" } = useParams();
  const location = useLocation();
  const agents = useAgents();
  const agent = agents.data?.agents.find((a) => a.id === agentId);
  const loadError = agents.data?.load_errors?.[agentId];
  const Intro = agentIntroFor(agentId);

  if (agents.loading && !agents.data) return <PageLoading label="Loading agent" />;
  if (agents.error) {
    return (
      <div className={styles.page}>
        <ErrorState error={agents.error} onRetry={agents.reload} />
      </div>
    );
  }
  if (!agent) {
    return (
      <div className={styles.page}>
        <EmptyState
          icon={loadError ? "error" : "search"}
          tone={loadError ? "error" : "neutral"}
          title={loadError ? `${agentId} failed to load` : `No agent called “${agentId}”`}
          action={
            <LinkButton variant="tonal" to="/agents" icon="widgets">
              See all agents
            </LinkButton>
          }
        >
          {loadError && <p>{loadError}</p>}
        </EmptyState>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.agentLayout}>
        <aside className={styles.agentIntro}>
          <LinkButton variant="text" to="/agents" icon="back" className={styles.back} viewTransition>
            Agents
          </LinkButton>
          <AgentAvatar id={agent.id} name={agent.name} size={104} morph />
          <h1>{agent.name}</h1>
          <p className="body-l muted">{agent.description}</p>
          <div className={styles.chips}>
            <span className={styles.chip}>
              <Icon name="package" size={18} />v{agent.version}
            </span>
            {agent.uses_llm && (
              <span className={styles.chip} title="Runs one at a time, because a local model has one GPU">
                <Icon name="model" size={18} />
                Uses a model
              </span>
            )}
            <span className={`${styles.chip} mono`}>{agent.id}</span>
          </div>
          {Intro && <Intro agent={agent} />}
        </aside>
        <section className={styles.formPanel}>
          <h2>New run</h2>
          <SchemaForm
            key={agent.id}
            agent={agent}
            initial={(location.state as FormValues | null) ?? undefined}
          />
        </section>
      </div>
    </div>
  );
}
