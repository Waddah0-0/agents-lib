import type { CSSProperties } from "react";
import type { Evidence, Finding } from "../api/client";
import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import type { IconName } from "../components/icons";
import { download, duration } from "../lib/format";
import styles from "./GenericResult.module.css";
import { JsonTree } from "./JsonTree";
import { toMarkdown } from "./markdown";
import type { ResultViewProps } from "./registry";

function ScoreMeter({ value }: { value: number }) {
  const unit = value >= 0 && value <= 1;
  return (
    <span className={styles.score} title={`Score ${value}`}>
      {unit && (
        <span className={styles.meter} style={{ "--v": value } as CSSProperties}>
          <span />
        </span>
      )}
      <span className={styles.scoreText}>{unit ? value.toFixed(2) : value}</span>
    </span>
  );
}

/** A weight in [-1, 1] as a bar growing left (against) or right (for) from the centre. */
function WeightBar({ weight }: { weight: number }) {
  const clamped = Math.max(-1, Math.min(1, weight));
  return (
    <span
      className={styles.weight}
      data-sign={clamped >= 0 ? "pos" : "neg"}
      style={{ "--w": Math.abs(clamped) } as CSSProperties}
      title={`Weight ${weight >= 0 ? "+" : ""}${weight.toFixed(2)}`}
    >
      <span className={styles.weightBar} />
      <span className={styles.weightText}>
        {weight >= 0 ? "+" : "−"}
        {Math.abs(weight).toFixed(2)}
      </span>
    </span>
  );
}

function EvidenceRow({ evidence }: { evidence: Evidence }) {
  return (
    <li className={styles.evidence}>
      <span className={styles.kind}>{evidence.kind}</span>
      <div className={styles.evidenceBody}>
        {evidence.location && <code className={styles.location}>{evidence.location}</code>}
        <p>{evidence.detail}</p>
      </div>
      {evidence.weight !== null && evidence.weight !== undefined && <WeightBar weight={evidence.weight} />}
    </li>
  );
}

function FindingCard({ finding, open }: { finding: Finding; open: boolean }) {
  const evidence = finding.evidence ?? [];
  return (
    <details className={styles.finding} open={open || undefined}>
      <summary className={styles.findingHead}>
        <div className={styles.findingTitle}>
          <h3 className="title-m">{finding.title}</h3>
          <p className="body-m muted">{finding.summary}</p>
        </div>
        {finding.severity_or_score !== null && finding.severity_or_score !== undefined && (
          <ScoreMeter value={finding.severity_or_score} />
        )}
        {evidence.length > 0 && (
          <span className={styles.evidenceCount}>
            {evidence.length} {evidence.length === 1 ? "piece" : "pieces"} of evidence
            <Icon name="expand" className={styles.chevron} />
          </span>
        )}
      </summary>
      {evidence.length > 0 && (
        <ul className={styles.evidenceList}>
          {evidence.map((ev, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: a fixed list that never reorders
            <EvidenceRow key={`${ev.kind}-${ev.location}-${i}`} evidence={ev} />
          ))}
        </ul>
      )}
    </details>
  );
}

const BANNER = {
  partial: {
    icon: "warning",
    title: "Partial result",
    text: "Some of the work was skipped. The warnings below say what.",
  },
  error: { icon: "error", title: "The run failed", text: "" },
} as const;

/** The viewer every agent gets: summary, findings with evidence, warnings, metadata, raw data. */
export function GenericResult({ run, result }: ResultViewProps) {
  const findings = result.findings ?? [];
  const warnings = result.warnings ?? [];
  const meta = result.metadata;
  const usage = meta?.usage;
  const base = `${result.agent_id}-${run.run_id.slice(0, 8)}`;
  const banner = result.status === "ok" ? undefined : BANNER[result.status];

  const details: [IconName, string, string][] = [];
  if (meta?.duration_s !== null && meta?.duration_s !== undefined)
    details.push(["timer", "Duration", duration(meta.duration_s)]);
  if (meta?.model) details.push(["model", "Model", meta.model]);
  if (usage?.llm_calls) {
    details.push(["modelCalls", "Model calls", String(usage.llm_calls)]);
    details.push(["tokens", "Tokens in / out", `${usage.input_tokens} / ${usage.output_tokens}`]);
    if (usage.cost_usd) details.push(["cost", "Estimated cost", `$${usage.cost_usd.toFixed(4)}`]);
  }
  details.push(["package", "Agent version", result.agent_version]);

  return (
    <div className={styles.result}>
      {banner && (
        <div className={styles.banner} data-status={result.status} role="status">
          <Icon name={banner.icon} />
          <div>
            <p className="title-m">{banner.title}</p>
            <p className="body-m">{result.status === "error" ? result.error : banner.text}</p>
          </div>
        </div>
      )}

      <section className={styles.summary}>
        <p className="label-l muted">Summary</p>
        <p className={`headline-s ${styles.summaryText}`}>{result.summary}</p>
        <div className={styles.exports}>
          <Button
            variant="outlined"
            size="s"
            icon="download"
            onClick={() =>
              download(`${base}.json`, `${JSON.stringify(result, null, 2)}\n`, "application/json")
            }
          >
            JSON
          </Button>
          <Button
            variant="outlined"
            size="s"
            icon="download"
            onClick={() => download(`${base}.md`, toMarkdown(result), "text/markdown")}
          >
            Markdown
          </Button>
          <Button
            variant="text"
            size="s"
            icon="copy"
            onClick={() => navigator.clipboard?.writeText(toMarkdown(result))}
          >
            Copy as Markdown
          </Button>
        </div>
      </section>

      {findings.length > 0 && (
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>
            Findings <span className={styles.badge}>{findings.length}</span>
          </h2>
          <div className={styles.findings}>
            {findings.map((f, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: a fixed list that never reorders
              <FindingCard key={`${f.title}-${i}`} finding={f} open={findings.length <= 2} />
            ))}
          </div>
        </section>
      )}

      {warnings.length > 0 && (
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>
            Warnings <span className={styles.badge}>{warnings.length}</span>
          </h2>
          <ul className={styles.warnings}>
            {warnings.map((w, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: a fixed list that never reorders
              <li key={`${i}-${w}`}>
                <Icon name="info" size={20} />
                <span>{w}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Run details</h2>
        <dl className={styles.details}>
          {details.map(([icon, label, value]) => (
            <div key={label} className={styles.detail}>
              <Icon name={icon} className={styles.detailIcon} />
              <dt className="body-s muted">{label}</dt>
              <dd className="title-m">{value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className={styles.section}>
        <details className={styles.raw}>
          <summary className={styles.rawHead}>
            <Icon name="code" />
            <span className="title-m">Raw result</span>
            <span className="body-m muted">Everything the agent returned, as JSON</span>
            <Icon name="expand" className={styles.chevron} />
          </summary>
          <div className={styles.rawBody}>
            <JsonTree value={result} openDepth={1} />
          </div>
        </details>
      </section>
    </div>
  );
}
