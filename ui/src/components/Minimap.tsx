/**
 * A "minimap" of code: rounded bars standing in for lines, indented like real code, with some
 * lines highlighted as evidence. `reading` moves a highlight down line by line, the way an
 * agent works through a file. Purely decorative.
 */
import type { CSSProperties } from "react";
import { hash } from "./AgentAvatar";
import styles from "./Minimap.module.css";

interface Line {
  indent: number;
  width: number;
}

/** Deterministic pseudo-random lines, so a given seed always draws the same "file". */
export function linesFor(seed: string, rows: number): (Line | null)[] {
  let state = hash(seed) || 1;
  const next = () => {
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    return (state >>> 0) / 4294967296;
  };
  const lines: (Line | null)[] = [];
  let indent = 0;
  for (let i = 0; i < rows; i++) {
    const r = next();
    if (i > 0 && r < 0.1 && lines[i - 1] !== null) {
      lines.push(null); // a blank line
      indent = 0;
      continue;
    }
    if (r > 0.7 && indent < 3) indent++;
    else if (r < 0.3 && indent > 0) indent--;
    lines.push({ indent, width: 26 + Math.round(next() * 52) });
  }
  return lines;
}

export function Minimap({
  seed,
  rows = 14,
  highlights = [],
  reading = false,
  className,
}: {
  seed: string;
  rows?: number;
  highlights?: number[];
  reading?: boolean;
  className?: string;
}) {
  const lines = linesFor(seed, rows);
  return (
    <div
      className={[styles.map, className].filter(Boolean).join(" ")}
      data-reading={reading}
      style={{ "--rows": rows } as CSSProperties}
      aria-hidden="true"
    >
      {reading && <span className={styles.cursor} />}
      {lines.map((line, i) => {
        const order = highlights.indexOf(i);
        return (
          <span
            // biome-ignore lint/suspicious/noArrayIndexKey: lines are fixed for a given seed
            key={i}
            className={styles.row}
            data-highlight={order >= 0}
            style={{ "--order": order } as CSSProperties}
          >
            {line && (
              <span
                className={styles.bar}
                style={{ marginLeft: `${line.indent * 8}%`, width: `${line.width}%` }}
              />
            )}
          </span>
        );
      })}
    </div>
  );
}
