/**
 * M3 Expressive loading indicator: a shape that turns while morphing between soft
 * polygons. All the shapes have the same number of points, so CSS can morph their paths.
 */
import { shapePath } from "./AgentShape";
import styles from "./Loading.module.css";

const FRAMES = [
  { lobes: 7, depth: 0.08, turn: 0 },
  { lobes: 4, depth: 0.2, turn: 45 },
  { lobes: 9, depth: 0.07, turn: 0 },
  { lobes: 5, depth: 0.1, turn: 0 },
].map(shapePath);

const KEYFRAMES = `@keyframes loading-morph {
${FRAMES.map((d, i) => `  ${(i * 100) / FRAMES.length}% { d: path("${d}"); }`).join("\n")}
  100% { d: path("${FRAMES[0]}"); }
}`;

export function LoadingIndicator({ size = 48, label = "Loading" }: { size?: number; label?: string }) {
  return (
    <span className={styles.wrap} role="progressbar" aria-label={label} style={{ width: size, height: size }}>
      <style>{KEYFRAMES}</style>
      <svg viewBox="0 0 100 100" className={styles.svg} aria-hidden="true">
        <path
          d={FRAMES[0]}
          className={styles.path}
          style={{ animation: "loading-morph 4.4s var(--ease-emphasized) infinite" }}
        />
      </svg>
    </span>
  );
}

/** A whole-page loading state, centred. */
export function PageLoading({ label }: { label?: string }) {
  return (
    <div className={styles.page}>
      <LoadingIndicator size={56} label={label} />
    </div>
  );
}
