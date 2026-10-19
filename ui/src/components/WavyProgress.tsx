/**
 * Material 3 Expressive linear progress: the active track is a moving wave while work is
 * happening, and flattens into a plain bar when it stops. `value` null = indeterminate.
 */
import type { CSSProperties } from "react";
import styles from "./WavyProgress.module.css";

const WAVELENGTH = 40;
const AMPLITUDE = 3;

function wavePath(length: number): string {
  const mid = 8;
  const parts = [`M0,${mid}`];
  // each half wavelength is one quadratic curve; together they draw a smooth sine
  for (let x = 0; x < length; x += WAVELENGTH / 2) {
    const up = (x / (WAVELENGTH / 2)) % 2 === 0;
    parts.push(
      `Q${x + WAVELENGTH / 4},${mid + (up ? -AMPLITUDE : AMPLITUDE) * 2} ${x + WAVELENGTH / 2},${mid}`,
    );
  }
  return parts.join(" ");
}

const WAVE = wavePath(3200);

export function WavyProgress({
  value,
  active = true,
  label,
}: {
  value: number | null;
  active?: boolean;
  label: string;
}) {
  const indeterminate = value === null;
  const pct = indeterminate ? 0 : Math.max(0, Math.min(1, value)) * 100;
  return (
    <div
      className={styles.track}
      data-active={active}
      data-indeterminate={indeterminate}
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={indeterminate ? undefined : Math.round(pct)}
      style={{ "--pct": `${pct}%` } as CSSProperties}
    >
      <div className={styles.rest} />
      <div className={styles.stop} />
      <div className={styles.active}>
        <svg className={styles.wave} width="3200" height="16" viewBox="0 0 3200 16" aria-hidden="true">
          <path d={WAVE} />
        </svg>
        <div className={styles.flat} />
      </div>
    </div>
  );
}
