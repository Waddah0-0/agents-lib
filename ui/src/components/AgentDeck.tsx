/**
 * The home page illustration: a card catalogue with one index card per installed agent.
 * The front card changes every few seconds (paused while hovered or focused, and off when
 * the visitor prefers reduced motion), so the page shows the whole library, not one agent.
 */
import { type CSSProperties, useEffect, useState } from "react";
import { Link } from "react-router";
import type { AgentInfo } from "../api/client";
import { humanize } from "../form/schema";
import { AgentAvatar } from "./AgentAvatar";
import styles from "./AgentDeck.module.css";
import { Icon } from "./Icon";
import { Minimap } from "./Minimap";

const VISIBLE = 4;
const INTERVAL_MS = 5000;

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

export function AgentDeck({ agents }: { agents: AgentInfo[] }) {
  const [front, setFront] = useState(0);
  const [paused, setPaused] = useState(false);
  const count = agents.length;

  useEffect(() => {
    if (count < 2 || paused || prefersReducedMotion()) return;
    const timer = setInterval(() => setFront((f) => (f + 1) % count), INTERVAL_MS);
    return () => clearInterval(timer);
  }, [count, paused]);

  if (!count) return null;
  const shown = Array.from({ length: Math.min(count, VISIBLE) }, (_, pos) => ({
    agent: agents[(front + pos) % count] as AgentInfo,
    pos,
  }));

  return (
    <figure
      className={styles.deck}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      aria-label="Installed agents"
    >
      <div className={styles.stack}>
        {shown.map(({ agent, pos }) => (
          <Link
            key={agent.id}
            to={`/agents/${agent.id}`}
            className={styles.card}
            data-pos={pos}
            style={{ "--pos": pos, zIndex: VISIBLE - pos } as CSSProperties}
            tabIndex={pos === 0 ? 0 : -1}
            aria-hidden={pos !== 0}
            viewTransition
          >
            <div className={styles.cardInner}>
              <div className={styles.head}>
                <AgentAvatar id={agent.id} name={agent.name} size={44} />
                <div className={styles.titles}>
                  <span className={styles.name}>{agent.name}</span>
                  <span className={styles.meta}>
                    v{agent.version}
                    {agent.uses_llm ? " · uses a model" : " · no model needed"}
                  </span>
                </div>
              </div>
              <p className={styles.description}>{agent.description}</p>
              <Minimap seed={agent.id} rows={5} highlights={[1]} className={styles.lines} />
              <div className={styles.foot}>
                {agent.primary_input && (
                  <span className={styles.input}>
                    takes <b>{humanize(agent.primary_input).toLowerCase()}</b>
                  </span>
                )}
                <span className={styles.open}>
                  Open <Icon name="forward" size={14} />
                </span>
              </div>
            </div>
          </Link>
        ))}
      </div>
      {count > 1 && (
        <div className={styles.pager}>
          {agents.map((a, i) => (
            <button
              key={a.id}
              type="button"
              className={styles.dash}
              aria-label={`Show ${a.name}`}
              aria-current={i === front || undefined}
              onClick={() => setFront(i)}
            />
          ))}
          <span className={styles.counter}>
            {front + 1} / {count}
          </span>
        </div>
      )}
    </figure>
  );
}
