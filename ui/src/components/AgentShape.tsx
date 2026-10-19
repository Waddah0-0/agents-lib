/**
 * An agent's avatar: its initial inside one of the Material 3 Expressive shapes (cookie,
 * clover, sunny, burst...). Shape and colour are picked from the agent id, so an agent
 * always looks the same, and the shape turns gently on hover.
 */
import styles from "./AgentShape.module.css";

interface ShapeSpec {
  lobes: number;
  depth: number;
  turn: number; // degrees
}

// cookie-4/6/7/9/12, clover, sunny, soft burst
const SHAPES: ShapeSpec[] = [
  { lobes: 4, depth: 0.07, turn: 45 },
  { lobes: 6, depth: 0.07, turn: 0 },
  { lobes: 7, depth: 0.065, turn: 0 },
  { lobes: 9, depth: 0.06, turn: 0 },
  { lobes: 12, depth: 0.045, turn: 0 },
  { lobes: 4, depth: 0.2, turn: 45 },
  { lobes: 8, depth: 0.04, turn: 0 },
  { lobes: 10, depth: 0.08, turn: 0 },
];

const TONES = ["primary", "secondary", "tertiary"] as const;

export function hash(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** SVG path for r(θ) = 1 + depth·cos(lobes·θ), scaled to fit a 100×100 box. */
export function shapePath({ lobes, depth, turn }: ShapeSpec): string {
  const steps = 240;
  const scale = 49 / (1 + depth);
  const offset = (turn * Math.PI) / 180;
  const points: string[] = [];
  for (let i = 0; i < steps; i++) {
    const t = (i / steps) * Math.PI * 2;
    const r = scale * (1 + depth * Math.cos(lobes * t));
    points.push(
      `${(50 + r * Math.cos(t + offset)).toFixed(2)},${(50 + r * Math.sin(t + offset)).toFixed(2)}`,
    );
  }
  return `M${points.join("L")}Z`;
}

export function AgentShape({
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
  const shape = SHAPES[h % SHAPES.length] as ShapeSpec;
  const tone = TONES[(h >>> 8) % TONES.length] as string;
  const initial = (name.trim()[0] ?? "?").toUpperCase();
  return (
    <span
      className={[styles.shape, className].filter(Boolean).join(" ")}
      data-tone={tone}
      style={{ width: size, height: size, fontSize: size * 0.42, viewTransitionName: `agent-${id}` }}
      aria-hidden="true"
    >
      <svg viewBox="0 0 100 100" className={styles.svg} aria-hidden="true">
        <path d={shapePath(shape)} />
      </svg>
      <span className={styles.initial}>{initial}</span>
    </span>
  );
}
