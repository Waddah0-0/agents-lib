/**
 * Files: a tree coloured by each file's likelihood (unscored files greyed out), and the
 * selected file with its excerpt, marked lines, the model's verdict and the signals.
 */
import { type CSSProperties, Fragment, useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "../../components/Icon";
import { WeightBar } from "../GenericResult";
import styles from "./detector.module.css";
import {
  ancestors,
  buildTree,
  fileScore,
  probabilityColor,
  REASON_LABEL,
  SIDE_LABEL,
  type TreeFolder,
  type TreeNode,
} from "./logic";
import type { DetectorData, Excerpt, ExcerptMark, FileScore } from "./types";

export interface Selection {
  path: string;
  line?: number;
  at: number; // when it was picked, so picking the same line again scrolls again
}

function Dot({ p, byModel = true }: { p: number | null; byModel?: boolean }) {
  return (
    <span
      className={styles.dot}
      data-unscored={p === null}
      data-signals={p !== null && !byModel}
      style={p === null ? undefined : ({ "--c": probabilityColor(p) } as CSSProperties)}
    />
  );
}

function TreeRows({
  folder,
  depth,
  open,
  toggle,
  selected,
  onSelect,
}: {
  folder: TreeFolder;
  depth: number;
  open: Set<string>;
  toggle: (path: string) => void;
  selected: string | undefined;
  onSelect: (path: string) => void;
}) {
  return (
    <>
      {folder.children.map((node: TreeNode) => {
        const indent = { "--depth": depth } as CSSProperties;
        if (node.kind === "folder") {
          const isOpen = open.has(node.path);
          return (
            <Fragment key={node.path}>
              <button
                type="button"
                className={styles.treeRow}
                style={indent}
                onClick={() => toggle(node.path)}
                aria-expanded={isOpen}
              >
                <Icon name="chevronRight" size={14} className={styles.treeChevron} />
                <span className={styles.treeName}>{node.name}/</span>
              </button>
              {isOpen && (
                <TreeRows
                  folder={node}
                  depth={depth + 1}
                  open={open}
                  toggle={toggle}
                  selected={selected}
                  onSelect={onSelect}
                />
              )}
            </Fragment>
          );
        }
        const unscored = node.probability === null;
        return (
          <button
            key={node.path}
            type="button"
            className={styles.treeRow}
            style={indent}
            data-file
            data-unscored={unscored}
            aria-current={node.path === selected || undefined}
            disabled={unscored}
            title={unscored ? `Not scored: ${REASON_LABEL[node.reason ?? ""] ?? node.reason}` : node.path}
            onClick={() => onSelect(node.path)}
          >
            <Dot p={node.probability} byModel={node.byModel} />
            <span className={styles.treeName}>{node.name}</span>
            {node.hasExcerpt && <span className={styles.treeFlag} title="Has marked lines" />}
            <span className={styles.treeScore}>
              {unscored ? (REASON_LABEL[node.reason ?? ""] ?? node.reason) : node.probability?.toFixed(2)}
            </span>
          </button>
        );
      })}
    </>
  );
}

function marksEndingAt(marks: ExcerptMark[], line: number) {
  return marks.filter((m) => m.line_end === line);
}

function markOf(marks: ExcerptMark[], line: number): ExcerptMark | undefined {
  // "for" wins over "against" over "context" when spans overlap
  const order = { for: 0, against: 1, context: 2 } as const;
  return marks
    .filter((m) => m.line_start <= line && line <= m.line_end)
    .sort((a, b) => order[a.side] - order[b.side])[0];
}

function Code({ excerpt, focusLine, focusAt }: { excerpt: Excerpt; focusLine?: number; focusAt?: number }) {
  const focusRef = useRef<HTMLTableRowElement>(null);
  // biome-ignore lint/correctness/useExhaustiveDependencies: scroll again whenever a line is picked
  useEffect(() => {
    focusRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focusLine, focusAt]);

  return (
    <div className={styles.code}>
      <table>
        <tbody>
          {excerpt.hunks.map((hunk, h) => {
            const previousEnd =
              h > 0 ? (excerpt.hunks[h - 1]?.start_line ?? 0) + (excerpt.hunks[h - 1]?.lines.length ?? 0) : 1;
            const gap = hunk.start_line - previousEnd;
            return (
              <Fragment key={hunk.start_line}>
                {gap > 0 && (
                  <tr className={styles.gap}>
                    <td colSpan={2}>
                      {h === 0 ? `lines 1–${hunk.start_line - 1}` : `${gap} line${gap === 1 ? "" : "s"}`} not
                      shown
                    </td>
                  </tr>
                )}
                {hunk.lines.map((text, i) => {
                  const line = hunk.start_line + i;
                  const mark = markOf(excerpt.marks, line);
                  const notes = marksEndingAt(excerpt.marks, line);
                  return (
                    <Fragment key={line}>
                      <tr
                        ref={line === focusLine ? focusRef : undefined}
                        data-side={mark?.side}
                        data-focus={line === focusLine || undefined}
                      >
                        <td className={styles.lineNo}>{line}</td>
                        <td className={styles.lineText}>{text || " "}</td>
                      </tr>
                      {notes.map((m) => (
                        <tr key={`${m.source}-${m.line_start}-${m.note}`} className={styles.noteRow}>
                          <td />
                          <td>
                            <span className={styles.note} data-side={m.side}>
                              <b>{SIDE_LABEL[m.side]}</b>
                              <span className={styles.noteSource}>
                                {m.source === "judge" ? "model" : m.source}
                              </span>
                              {m.note}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </Fragment>
                  );
                })}
              </Fragment>
            );
          })}
        </tbody>
      </table>
      {excerpt.truncated && (
        <p className={styles.truncated}>Some marked lines were left out to keep the report small.</p>
      )}
    </div>
  );
}

function FileView({
  file,
  excerpt,
  selection,
}: {
  file: FileScore;
  excerpt?: Excerpt;
  selection: Selection | null;
}) {
  const focusLine = selection?.path === file.path ? selection.line : undefined;
  return (
    <article className={styles.fileView}>
      <header className={styles.fileHead}>
        <div className={styles.filePath}>
          <code>{file.path}</code>
          <span className="body-s muted">
            {file.language ?? "unknown language"} · {file.lines} lines of code
            {file.is_test ? " · test file" : ""}
          </span>
        </div>
        <span className={styles.fileScores}>
          <span
            className={styles.fileScore}
            style={{ "--c": probabilityColor(fileScore(file).value) } as CSSProperties}
          >
            {fileScore(file).value.toFixed(2)}
          </span>
          <span className="body-s muted">{file.judge ? "the model's verdict" : "signals only"}</span>
          {file.judge && <span className="body-s muted">signals {file.probability.toFixed(2)}</span>}
        </span>
      </header>

      {file.ai_commit_touches > 0 && (
        <p className={styles.touch}>
          <Icon name="checkCircle" size={16} />
          Changed by {file.ai_commit_touches} commit{file.ai_commit_touches === 1 ? "" : "s"} whose metadata
          names an AI tool.
        </p>
      )}

      {file.judge && (
        <div className={styles.verdict}>
          <div>
            <p className="label-m muted">The model read this file</p>
            <p className="title-m">
              Likelihood {file.judge.likelihood_ai.toFixed(2)}
              <span className="body-m muted"> · its confidence {file.judge.confidence.toFixed(2)}</span>
            </p>
          </div>
          {file.judge.uncertainty_notes && (
            <p className={styles.uncertainty}>“{file.judge.uncertainty_notes}”</p>
          )}
        </div>
      )}

      {excerpt ? (
        <Code excerpt={excerpt} focusLine={focusLine} focusAt={selection?.at} />
      ) : (
        <p className={styles.noExcerpt}>
          No code excerpt: the model did not read this file, and no signal pointed at specific lines.
        </p>
      )}

      {file.signals.length > 0 && (
        <div className={styles.signals}>
          <p className="label-m muted">Signals that fired (+ reads AI-like, − reads human-like)</p>
          <ul>
            {file.signals.map((s) => (
              <li key={`${s.signal_id}-${s.explanation}`}>
                <span className={styles.signalId}>{s.signal_id.replaceAll("_", " ")}</span>
                <span className={styles.signalText}>{s.explanation}</span>
                <WeightBar weight={s.strength} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}

export function FilesExplorer({
  data,
  selection,
  onSelect,
}: {
  data: DetectorData;
  selection: Selection | null;
  onSelect: (selection: Selection) => void;
}) {
  const [query, setQuery] = useState("");
  const [showUnscored, setShowUnscored] = useState(false);
  const [order, setOrder] = useState<"tree" | "score">("tree");
  const excerpts = useMemo(() => new Map(data.excerpts.map((e) => [e.path, e])), [data]);
  const files = useMemo(() => new Map(data.files.map((f) => [f.path, f])), [data]);
  const tree = useMemo(
    () => buildTree(data, { includeUnscored: showUnscored, query }),
    [data, showUnscored, query],
  );

  // start on the most likely file that has marked code, else the most likely file
  const initial =
    [...data.files]
      .filter((f) => excerpts.has(f.path) && !f.is_test)
      .sort(
        (a, b) =>
          Number(Boolean(b.judge)) - Number(Boolean(a.judge)) || fileScore(b).value - fileScore(a).value,
      )[0] ?? data.files[0];
  const current = selection?.path ?? initial?.path;
  const [open, setOpen] = useState<Set<string>>(() => {
    const start = new Set<string>();
    for (const child of tree.children) if (child.kind === "folder") start.add(child.path);
    for (const a of ancestors(current ?? "")) start.add(a);
    return start;
  });

  useEffect(() => {
    if (!selection) return;
    setOpen((o) => new Set([...o, ...ancestors(selection.path)]));
  }, [selection]);

  const toggle = (path: string) =>
    setOpen((o) => {
      const next = new Set(o);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  const select = (path: string) => onSelect({ path, at: Date.now() });
  const file = current ? files.get(current) : undefined;
  const ranked = useMemo(
    () =>
      data.files
        .filter((f) => !query || f.path.toLowerCase().includes(query.toLowerCase()))
        .sort((a, b) => fileScore(b).value - fileScore(a).value),
    [data, query],
  );

  if (!data.files.length) {
    return <p className="body-m muted">No file could be scored.</p>;
  }

  return (
    <div className={styles.explorer}>
      <div className={styles.treePane}>
        <div className={styles.treeTools}>
          <label className={styles.search}>
            <Icon name="search" size={16} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter files"
              spellCheck={false}
            />
          </label>
          <div className={styles.toggles}>
            <button type="button" aria-pressed={order === "tree"} onClick={() => setOrder("tree")}>
              Folders
            </button>
            <button type="button" aria-pressed={order === "score"} onClick={() => setOrder("score")}>
              By score
            </button>
            {order === "tree" && (
              <button
                type="button"
                aria-pressed={showUnscored}
                onClick={() => setShowUnscored(!showUnscored)}
              >
                Unscored
              </button>
            )}
          </div>
        </div>
        <div className={styles.tree}>
          {order === "tree" ? (
            <TreeRows
              folder={tree}
              depth={0}
              open={query ? new Set(allFolders(tree)) : open}
              toggle={toggle}
              selected={current}
              onSelect={select}
            />
          ) : (
            ranked.map((f) => (
              <button
                key={f.path}
                type="button"
                className={styles.treeRow}
                data-file
                aria-current={f.path === current || undefined}
                onClick={() => select(f.path)}
                style={{ "--depth": 0 } as CSSProperties}
              >
                <Dot p={fileScore(f).value} byModel={fileScore(f).byModel} />
                <span className={styles.treeName} title={f.path}>
                  {f.path}
                </span>
                {excerpts.has(f.path) && <span className={styles.treeFlag} title="Has marked lines" />}
                <span className={styles.treeScore}>{fileScore(f).value.toFixed(2)}</span>
              </button>
            ))
          )}
        </div>
        <p className={styles.legend}>
          <Dot p={0} /> human-like <Dot p={1} /> AI-like <Dot p={0.5} byModel={false} /> signals only
          <Dot p={null} /> not scored <span className={styles.treeFlag} /> marked lines
        </p>
      </div>
      {file ? (
        <FileView file={file} excerpt={excerpts.get(file.path)} selection={selection} />
      ) : (
        <p className="body-m muted">Pick a file.</p>
      )}
    </div>
  );
}

function allFolders(folder: TreeFolder): string[] {
  return folder.children.flatMap((c) => (c.kind === "folder" ? [c.path, ...allFolders(c)] : []));
}
