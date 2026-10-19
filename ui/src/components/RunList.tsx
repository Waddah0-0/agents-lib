import { Link } from "react-router";
import type { AgentInfo, RunView } from "../api/client";
import { duration, secondsBetween, shortId, timeAgo } from "../lib/format";
import { AgentShape } from "./AgentShape";
import { Icon } from "./Icon";
import styles from "./RunList.module.css";
import { StatusChip } from "./StatusChip";

export function RunList({ runs, agents }: { runs: RunView[]; agents: AgentInfo[] }) {
  const names = new Map(agents.map((a) => [a.id, a.name]));
  return (
    <ul className={styles.list}>
      {runs.map((run) => {
        const name = names.get(run.agent_id) ?? run.agent_id;
        const took = secondsBetween(run.started_at, run.finished_at);
        return (
          <li key={run.run_id}>
            <Link to={`/runs/${run.run_id}`} className={styles.row} viewTransition>
              <AgentShape id={run.agent_id} name={name} size={40} />
              <span className={styles.main}>
                <span className="title-m">{name}</span>
                <span className="body-m muted">
                  {run.result?.summary ?? run.progress?.message ?? "Waiting to start"}
                </span>
              </span>
              <span className={styles.meta}>
                <StatusChip run={run} />
                <span className="body-s muted">
                  {timeAgo(run.created_at)}
                  {took !== null && run.finished_at ? ` · ${duration(took)}` : ""}
                  {" · "}
                  <span className="mono">{shortId(run.run_id)}</span>
                </span>
              </span>
              <Icon name="chevron_right" className={styles.chevron} />
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
