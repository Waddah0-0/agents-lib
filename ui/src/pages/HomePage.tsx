import { useAgents, useRuns } from "../api/hooks";
import { AgentCard } from "../components/AgentCard";
import { AgentDeck } from "../components/AgentDeck";
import { LinkButton } from "../components/Button";
import { Launcher } from "../components/Launcher";
import { LoadingIndicator } from "../components/Loading";
import { RunList } from "../components/RunList";
import { ErrorState } from "../components/States";
import styles from "./pages.module.css";

export function HomePage() {
  const agents = useAgents();
  const runs = useRuns(5);
  const list = agents.data?.agents ?? [];

  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heroText}>
          {list.length > 0 && (
            <span className={styles.eyebrow}>
              <b>{list.length}</b>
              {list.length === 1 ? "agent installed" : "agents installed"}
            </span>
          )}
          <h1 className={styles.headline}>
            Agents that <span className="marker">show their work</span>
          </h1>
          <p className={styles.lede}>
            A library of small, focused agents. Give one a job and it answers with findings, each with the
            evidence behind it, so you can check its work instead of taking its word.
          </p>
          <div className={styles.launcherSlot}>
            {agents.loading && !agents.data ? (
              <div className={styles.skeletonPill}>
                <LoadingIndicator size={36} label="Loading agents" />
              </div>
            ) : list.length > 0 ? (
              <Launcher agents={list} />
            ) : null}
          </div>
        </div>
        <div className={styles.heroArt}>
          <AgentDeck agents={list} />
        </div>
      </section>

      {agents.error && <ErrorState error={agents.error} onRetry={agents.reload} />}

      {list.length > 0 && (
        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <h2>Agents</h2>
            <LinkButton variant="text" to="/agents" trailingIcon="forward" viewTransition>
              All agents
            </LinkButton>
          </div>
          <div className={styles.grid}>
            {list.map((agent) => (
              <AgentCard key={agent.id} agent={agent} />
            ))}
          </div>
        </section>
      )}

      {runs.data && runs.data.length > 0 && (
        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <h2>Recent runs</h2>
            <LinkButton variant="text" to="/runs" trailingIcon="forward" viewTransition>
              All runs
            </LinkButton>
          </div>
          <RunList runs={runs.data} agents={list} />
        </section>
      )}
    </div>
  );
}
