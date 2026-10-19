/**
 * An agent's avatar: its initial, set in Fraunces on a tinted tile, with a highlighter stroke
 * through the lower half. Tint and stroke angle come from the agent id, so an agent always
 * looks the same. The stroke re-swipes when the avatar's card or link is hovered.
 */
import type { CSSProperties } from "react";
import styles from "./AgentAvatar.module.css";

const TONES = ["ink", "sage", "paper"] as const;

export function hash(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export function AgentAvatar({
  id,
  name,
  size = 48,
  className,
}: {
  id: string;
  name: string;
  size?: number;
  className?: string;
}) {
  const h = hash(id);
  const tone = TONES[h % TONES.length];
  const tilt = ((h >>> 4) % 9) - 4; // -4..4 degrees, so each stroke looks hand-drawn
  const initial = (name.trim()[0] ?? "?").toUpperCase();
  return (
    <span
      className={[styles.avatar, className].filter(Boolean).join(" ")}
      data-tone={tone}
      style={
        {
          width: size,
          height: size,
          fontSize: size * 0.56,
          viewTransitionName: `agent-${id}`,
          "--tilt": `${tilt}deg`,
        } as CSSProperties
      }
      aria-hidden="true"
    >
      <span className={styles.initial}>{initial}</span>
    </span>
  );
}
