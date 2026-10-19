/**
 * The AI Code Detector's `data` (its DetectorOutput model), as the detector view uses it.
 * Results come from the API as untyped JSON, so `asDetectorData` checks the shape first;
 * anything unexpected (an older detector, a failed run) falls back to the generic viewer.
 */

export type Side = "for" | "against" | "context";

export interface EvidenceItem {
  kind: string;
  location?: string | null;
  detail: string;
  weight?: number | null;
}

export interface SignalHit {
  signal_id: string;
  family: string;
  strength: number;
  explanation: string;
  evidence: EvidenceItem[];
}

export interface Quote {
  line_start: number;
  line_end: number;
  quote: string;
  why: string;
}

export interface JudgeVerdict {
  likelihood_ai: number;
  confidence: number;
  evidence_for: Quote[];
  evidence_against: Quote[];
  uncertainty_notes: string;
}

export interface FileScore {
  path: string;
  language: string | null;
  lines: number;
  is_test: boolean;
  probability: number;
  signals: SignalHit[];
  judge: JudgeVerdict | null;
  ai_commit_touches: number;
}

export interface ExcerptMark {
  line_start: number;
  line_end: number;
  side: Side;
  source: string;
  note: string;
}

export interface Excerpt {
  path: string;
  hunks: { start_line: number; lines: string[] }[];
  marks: ExcerptMark[];
  truncated: boolean;
}

export interface CommitSummary {
  sha: string;
  date: string;
  subject: string;
  files_changed: number;
  merge: boolean;
  tools: string[];
  large: boolean;
}

export interface MetadataMarker {
  kind: string;
  tool: string;
  location: string;
  detail: string;
}

export interface DetectorData {
  methodology_version: string;
  estimate: number;
  estimate_range: [number, number];
  confidence: "low" | "medium" | "high";
  confidence_reasons: string[];
  metadata_markers: MetadataMarker[];
  repo_signals: SignalHit[];
  files: FileScore[];
  files_analyzed: number;
  files_skipped: number;
  languages: Record<string, number>;
  unsupported_languages: Record<string, number>;
  excerpts: Excerpt[];
  commits: CommitSummary[];
  commits_total: number;
  unscored_files: { path: string; reason: string }[];
  unscored_truncated: boolean;
}

const isNumber = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

/** The detector data, or null when `data` doesn't look like it. */
export function asDetectorData(data: unknown): DetectorData | null {
  if (!data || typeof data !== "object") return null;
  const d = data as Record<string, unknown>;
  const range = d.estimate_range;
  if (
    !isNumber(d.estimate) ||
    !Array.isArray(range) ||
    range.length !== 2 ||
    !range.every(isNumber) ||
    typeof d.confidence !== "string" ||
    !Array.isArray(d.files)
  ) {
    return null;
  }
  // fields added after the first release default to empty, so older results still render
  return {
    confidence_reasons: [],
    metadata_markers: [],
    repo_signals: [],
    languages: {},
    unsupported_languages: {},
    excerpts: [],
    commits: [],
    commits_total: 0,
    unscored_files: [],
    unscored_truncated: false,
    files_analyzed: (d.files as unknown[]).length,
    files_skipped: 0,
    methodology_version: "",
    ...(d as object),
  } as unknown as DetectorData;
}

/** "a.py:10-12" -> { path: "a.py", line: 10 } */
export function splitLocation(location: string | null | undefined): { path: string; line?: number } | null {
  if (!location) return null;
  const match = /^(.+?):(\d+)(?:-\d+)?$/.exec(location);
  if (match?.[1] && match[2]) return { path: match[1], line: Number(match[2]) };
  return { path: location };
}
