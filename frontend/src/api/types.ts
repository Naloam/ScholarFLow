// Types for the research-harness API (plan §5.1) + minimal auth.
// Kept intentionally small — this is the ONLY API surface the new UI talks to.

export interface StartRequest {
  idea: string;
  steps?: string;
}

export interface StartResponse {
  run_id: string;
  project_id: string;
}

export type StepStatus = "done" | "error" | "running";

export interface TimelineEntry {
  step: string;
  status: string;
  ts?: string | null;
  output_files?: string[];
}

export type RunStatusKind =
  | "running"
  | "done"
  | "error"
  | "partial"
  | "pending";

export interface RunStatus {
  run_id: string;
  project_id: string;
  idea: string;
  status: RunStatusKind;
  steps: TimelineEntry[];
  current_step?: string | null;
  started_at?: string | null;
  updated_at?: string | null;
  execution_status?: string | null;
}

export interface ProjectSummary {
  project_id: string;
  idea: string;
  status: RunStatusKind;
  created_at?: string | null;
  updated_at?: string | null;
  steps_done?: string[];
  last_ts?: string | null;
}

export interface AuthConfig {
  auth_required: boolean;
  api_protected: boolean;
  session_enabled: boolean;
}

export interface AuthUser {
  id: string;
  email: string;
  name?: string | null;
  role?: string | null;
}

export interface AuthSessionResponse {
  access_token: string;
  expires_at?: string | null;
  user: AuthUser;
}

// ---- metrics.json shapes (Report metric cards) — only the fields we render ----

export interface BaselineDataset {
  dataset: string;
  baseline_system: string;
  baseline_metric: number;
  proposed_system: string;
  proposed_metric: number;
  delta: number;
  beats_baseline: boolean;
  n_seeds_baseline?: number;
  n_seeds_proposed?: number;
}

export interface BaselineComparison {
  metric_name?: string;
  direction?: string;
  overall_beats_baseline?: boolean;
  datasets?: BaselineDataset[];
}

export interface SignificanceTest {
  metric?: string;
  candidate?: string;
  comparator?: string;
  p_value?: number;
  adjusted_p_value?: number;
  adjusted_alpha?: number;
  effect_size?: number;
  adequately_powered?: boolean;
  scope?: string;
  dataset?: string;
}

export interface MetricsJson {
  execution_status?: string;
  dataset?: string;
  results?: Array<Record<string, unknown>>;
  baseline_comparison?: BaselineComparison;
  abstention_metrics?: Record<string, Record<string, Record<string, number>>>;
  statistics?: {
    seed_count?: number;
    significance_tests?: SignificanceTest[];
  };
  attempts_used?: number;
  repair_attempts?: number;
  returncode?: number;
}

export interface ReviewWeakness {
  issue: string;
  severity?: "major" | "minor" | string;
  evidence?: string;
}

export interface ReviewJson {
  overall_assessment?: string;
  summary?: string;
  publish_gate?: string;
  strengths?: string[];
  weaknesses?: ReviewWeakness[];
  required_experiments?: Array<{ action?: string; description?: string; priority?: string }>;
}

// ---- paper + audit (V2 Writer + Auditor layer) ----

export type ClaimCategory = "result" | "spin" | "citation" | string;

export interface ClaimVerdict {
  claim_id: string;
  claim: string;
  verdict: "verified" | "unverified";
  category?: ClaimCategory;
  /** Present on citation-category claims — the title/marker that was checked. */
  raw_title?: string;
  marker?: string;
  evidence_refs?: string[];
  reason?: string;
}

export interface ClaimAudit {
  total_claims?: number;
  verified_count?: number;
  unverified_count?: number;
  /** (V2.1) how many of the unverified claims are unmatched citations. */
  citation_unverified_count?: number;
  gate?: boolean;
  verdict?: string;
  audited_at?: string;
  claims?: ClaimVerdict[];
  skipped?: boolean;
  reason?: string;
}
