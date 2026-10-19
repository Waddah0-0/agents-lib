import { useState } from "react";
import { Icon } from "../components/Icon";
import styles from "./JsonTree.module.css";

const PAGE = 100;

function Scalar({ value }: { value: unknown }) {
  if (value === null) return <span className={styles.null}>null</span>;
  if (typeof value === "string") return <span className={styles.string}>"{value}"</span>;
  if (typeof value === "number") return <span className={styles.number}>{value}</span>;
  if (typeof value === "boolean") return <span className={styles.boolean}>{String(value)}</span>;
  return <span>{String(value)}</span>;
}

function Node({
  name,
  value,
  depth,
  openDepth,
}: {
  name?: string;
  value: unknown;
  depth: number;
  openDepth: number;
}) {
  const isArray = Array.isArray(value);
  const isObject = value !== null && typeof value === "object";
  const [open, setOpen] = useState(depth < openDepth);
  const [limit, setLimit] = useState(PAGE);

  const key = name !== undefined && <span className={styles.key}>{name}</span>;
  if (!isObject) {
    return (
      <div className={styles.row}>
        {key}
        {key && <span className={styles.punct}>: </span>}
        <Scalar value={value} />
      </div>
    );
  }

  const entries: [string, unknown][] = isArray
    ? (value as unknown[]).map((v, i) => [String(i), v])
    : Object.entries(value as Record<string, unknown>);
  const [openB, closeB] = isArray ? ["[", "]"] : ["{", "}"];
  const size = isArray ? `${entries.length} items` : `${entries.length} keys`;

  if (!entries.length) {
    return (
      <div className={styles.row}>
        {key}
        {key && <span className={styles.punct}>: </span>}
        <span className={styles.punct}>{openB + closeB}</span>
      </div>
    );
  }

  return (
    <div>
      <button type="button" className={styles.toggle} onClick={() => setOpen(!open)} aria-expanded={open}>
        <Icon name="chevron_right" size={18} className={styles.chevron} />
        {key}
        {key && <span className={styles.punct}>: </span>}
        <span className={styles.punct}>{openB}</span>
        {!open && (
          <>
            <span className={styles.size}>{size}</span>
            <span className={styles.punct}>{closeB}</span>
          </>
        )}
      </button>
      {open && (
        <div className={styles.children}>
          {entries.slice(0, limit).map(([k, v]) => (
            <Node key={k} name={isArray ? undefined : k} value={v} depth={depth + 1} openDepth={openDepth} />
          ))}
          {entries.length > limit && (
            <button type="button" className={styles.more} onClick={() => setLimit(limit + PAGE)}>
              Show {Math.min(PAGE, entries.length - limit)} more of {entries.length - limit}
            </button>
          )}
          <span className={styles.punct}>{closeB}</span>
        </div>
      )}
    </div>
  );
}

/** A collapsible view of any JSON value; large arrays load in pages. */
export function JsonTree({ value, openDepth = 1 }: { value: unknown; openDepth?: number }) {
  return (
    <div className={styles.tree}>
      <Node value={value} depth={0} openDepth={openDepth} />
    </div>
  );
}
