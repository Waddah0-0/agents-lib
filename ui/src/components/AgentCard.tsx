import { Link } from "react-router";
import type { AgentInfo } from "../api/client";
import styles from "./AgentCard.module.css";
import { AgentShape } from "./AgentShape";
import { Icon } from "./Icon";

export function AgentCard({ agent }: { agent: AgentInfo }) {
  return (
    <Link to={`/agents/${agent.id}`} className={styles.card} viewTransition>
      <div className={styles.top}>
        <AgentShape id={agent.id} name={agent.name} size={56} />
        <Icon name="arrow_outward" className={styles.arrow} />
      </div>
      <h3 className="title-l">{agent.name}</h3>
      <p className={`body-m muted ${styles.description}`}>{agent.description}</p>
      <div className={styles.chips}>
        <span className={styles.chip}>v{agent.version}</span>
        {agent.uses_llm && (
          <span className={styles.chip}>
            <Icon name="neurology" size={16} />
            Uses a model
          </span>
        )}
      </div>
    </Link>
  );
}
