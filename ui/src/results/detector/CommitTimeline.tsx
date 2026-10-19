/**
 * The commit history on a time axis: one tick per commit, taller when it touched more files;
 * commits whose metadata names an AI tool carry an ink dot, unusually large ones are
 * highlighted. Below, the notable commits as a list. Authors are not shown, on purpose.
 */
import type { CSSProperties } from "react";
import styles from "./detector.module.css";
import type { CommitSummary } from "./types";

const dateFormat = new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" });

export function CommitTimeline({ commits, total }: { commits: CommitSummary[]; total: number }) {
  const chronological = [...commits].sort((a, b) => Date.parse(a.date) - Date.parse(b.date));
  const first = Date.parse(chronological[0]?.date ?? "");
  const last = Date.parse(chronological[chronological.length - 1]?.date ?? "");
  const span = Math.max(last - first, 1);
  const maxFiles = Math.max(...commits.map((c) => c.files_changed), 1);
  const notable = commits.filter((c) => c.tools.length || c.large).slice(0, 12);
  const withTools = commits.filter((c) => c.tools.length).length;
  const large = commits.filter((c) => c.large).length;

  return (
    <div className={styles.timeline}>
      <div className={styles.axis}>
        {chronological.map((c) => {
          const x = commits.length === 1 ? 0.5 : (Date.parse(c.date) - first) / span;
          const h = 0.18 + 0.82 * (Math.log1p(c.files_changed) / Math.log1p(maxFiles));
          const kind = c.tools.length ? "tool" : c.large ? "large" : c.merge ? "merge" : "plain";
          return (
            <span
              key={c.sha}
              className={styles.tick}
              data-kind={kind}
              style={{ "--x": x, "--h": h } as CSSProperties}
              title={`${dateFormat.format(new Date(c.date))} · ${c.subject} · ${c.files_changed} files${c.tools.length ? ` · ${c.tools.join(", ")}` : ""}`}
            />
          );
        })}
      </div>
      <div className={styles.axisLabels}>
        <span>{dateFormat.format(new Date(first))}</span>
        <span className={styles.timelineLegend}>
          <span data-kind="tool" /> names an AI tool ({withTools})
          <span data-kind="large" /> large commit ({large})
          <span data-kind="plain" /> other
        </span>
        <span>{dateFormat.format(new Date(last))}</span>
      </div>
      {total > commits.length && (
        <p className="body-s muted">
          Showing the newest {commits.length} of {total} commits.
        </p>
      )}
      {notable.length > 0 && (
        <ul className={styles.notable}>
          {notable.map((c) => (
            <li key={c.sha}>
              <span className={styles.notableDate}>{dateFormat.format(new Date(c.date))}</span>
              <code>{c.sha.slice(0, 7)}</code>
              <span className={styles.notableSubject}>{c.subject}</span>
              <span className={styles.notableTags}>
                {c.tools.map((t) => (
                  <span key={t} className={styles.tagTool}>
                    {t}
                  </span>
                ))}
                {c.large && <span className={styles.tagLarge}>{c.files_changed} files</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
