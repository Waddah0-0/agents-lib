import { Link } from "react-router";
import type { AgentInfo } from "../api/client";
import { AgentAvatar } from "./AgentAvatar";
import styles from "./AgentCard.module.css";
import { Icon } from "./Icon";

export function AgentCard({ agent }: { agent: AgentInfo }) {
  return (
    <Link to={`/agents/${agent.id}`} className={styles.card} viewTransition>
      <div className={styles.top}>
        <AgentAvatar id={agent.id} name={agent.name} size={56} />
        <Icon name="open" className={styles.arrow} />
      </div>
      <h3 className="headline-s">{agent.name}</h3>
      <p className={`body-m muted ${styles.description}`}>{agent.description}</p>
      <div className={styles.chips}>
        <span className={styles.chip}>v{agent.version}</span>
        {agent.uses_llm && (
          <span className={styles.chip}>
            <Icon name="model" size={16} />
            Uses a model
          </span>
        )}
      </div>
    </Link>
  );
}
