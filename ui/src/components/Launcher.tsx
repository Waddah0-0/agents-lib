/**
 * The home page's pill-shaped launcher: pick an agent, type its main input, go. Agents
 * without a main input (or anyone wanting more options) continue on the agent's page.
 */
import { type FormEvent, useEffect, useId, useRef, useState } from "react";
import { useNavigate } from "react-router";
import type { AgentInfo } from "../api/client";
import { startRun } from "../form/SchemaForm";
import { fieldsFromSchema } from "../form/schema";
import { AgentShape } from "./AgentShape";
import { IconButton } from "./Button";
import { Icon } from "./Icon";
import styles from "./Launcher.module.css";

export function Launcher({ agents }: { agents: AgentInfo[] }) {
  const navigate = useNavigate();
  const [agentId, setAgentId] = useState(() => (agents.find((a) => a.uses_llm) ?? agents[0])?.id);
  const [text, setText] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const menuId = useId();
  const pickerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const agent = agents.find((a) => a.id === agentId);
  const primary = agent
    ? fieldsFromSchema(agent.input_schema, agent.primary_input).find((f) => f.primary)
    : undefined;

  // The menu is a popover: it lives in the top layer (no clipping by the hero) and the
  // browser closes it on Escape or a click outside. It is placed under the picker on open.
  useEffect(() => {
    const menu = menuRef.current;
    if (!menu) return;
    const onToggle = (e: Event) => {
      const open = (e as ToggleEvent).newState === "open";
      setMenuOpen(open);
      const rect = pickerRef.current?.getBoundingClientRect();
      if (open && rect) {
        menu.style.top = `${rect.bottom + 14}px`;
        menu.style.left = `${Math.max(8, rect.left - 8)}px`;
      }
    };
    menu.addEventListener("beforetoggle", onToggle);
    return () => menu.removeEventListener("beforetoggle", onToggle);
  });

  if (!agent) return null;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!primary) {
      navigate(`/agents/${agent.id}`, { viewTransition: true });
      return;
    }
    if (!text.trim()) {
      inputRef.current?.focus();
      return;
    }
    setBusy(true);
    setError(undefined);
    try {
      const runId = await startRun(agent.id, { [primary.name]: text.trim() });
      navigate(`/runs/${runId}`, { viewTransition: true });
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <div className={styles.wrap}>
      <div className={styles.glow} aria-hidden="true" />
      <form className={styles.pill} onSubmit={submit}>
        <div className={styles.picker}>
          <button
            ref={pickerRef}
            type="button"
            className={styles.pickerButton}
            popoverTarget={menuId}
            aria-haspopup="listbox"
            aria-expanded={menuOpen}
          >
            <AgentShape id={agent.id} name={agent.name} size={32} />
            <span className={styles.pickerName}>{agent.name}</span>
            <Icon name="unfold_more" size={20} />
          </button>
          <div
            ref={menuRef}
            id={menuId}
            popover="auto"
            className={styles.menu}
            role="listbox"
            aria-label="Agent"
          >
            {agents.map((a) => (
              <button
                key={a.id}
                type="button"
                role="option"
                aria-selected={a.id === agent.id}
                className={styles.option}
                onClick={() => {
                  setAgentId(a.id);
                  menuRef.current?.hidePopover();
                  setError(undefined);
                  inputRef.current?.focus();
                }}
              >
                <AgentShape id={a.id} name={a.name} size={36} />
                <span className={styles.optionText}>
                  <span className="title-s">{a.name}</span>
                  <span className="body-s muted">{a.description}</span>
                </span>
                {a.id === agent.id && <Icon name="check" size={20} />}
              </button>
            ))}
          </div>
        </div>
        <span className={styles.divider} />
        {primary ? (
          <input
            ref={inputRef}
            className={styles.input}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={
              primary.placeholder ? `Try ${primary.placeholder}` : (primary.description ?? primary.label)
            }
            aria-label={primary.label}
            spellCheck={false}
            autoComplete="off"
          />
        ) : (
          <span className={`${styles.input} ${styles.placeholder}`}>This agent has no single main input</span>
        )}
        <IconButton
          type="button"
          icon="tune"
          label="More options"
          onClick={() =>
            navigate(`/agents/${agent.id}`, {
              viewTransition: true,
              state: primary && text.trim() ? { [primary.name]: text.trim() } : undefined,
            })
          }
        />
        <IconButton
          type="submit"
          icon={busy ? "progress_activity" : "arrow_forward"}
          label={primary ? "Run" : "Open"}
          variant="filled"
          disabled={busy}
          className={styles.go}
        />
      </form>
      {error && (
        <p className={styles.error} role="alert">
          <Icon name="error" size={18} /> {error}
        </p>
      )}
    </div>
  );
}
