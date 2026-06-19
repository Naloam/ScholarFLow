// Types for the research-harness API (plan §5.1) + minimal auth.
// Kept intentionally small — this is the ONLY API surface the new UI talks to.

export interface StartRequest {
  idea: string;
  steps?: string;
  /** V2.3 portfolio size (default 3, cap 5). K=1 = legacy single-hypothesis run. */
  portfolio_k?: number;
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
  /** (V2.2) hypothesis-named baselines that were not run. */
  missing_baselines?: string[];
  /** (V2.2) power-analysis underpowering marker, if the seed count was short. */
  underpowered?: {
    underpowered: boolean;
    ran_seeds: number;
    recommended_seeds: number;
    note: string;
  };
  /** (V2.2) reviewer follow-up run merged into these metrics, if any. */
  follow_up?: {
    ran: boolean;
    action?: string;
    description?: string;
    systems_added?: string[];
    reason?: string;
  };
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

export type ClaimCategory = "result" | "spin" | "citation" | "omission" | string;

export interface ClaimVerdict {
  claim_id: string;
  claim: string;
  verdict: "verified" | "unverified";
  category?: ClaimCategory;
  /** Present on citation-category claims — the title/marker that was checked. */
  raw_title?: string;
  marker?: string;
  /** Present on omission-category claims — the material metric that was dropped. */
  metric?: string;
  evidence_refs?: string[];
  reason?: string;
}

export interface ClaimAudit {
  total_claims?: number;
  verified_count?: number;
  unverified_count?: number;
  /** (V2.1) how many of the unverified claims are unmatched citations. */
  citation_unverified_count?: number;
  /** (V2.2) how many unverified claims are omitted material metrics. */
  omission_unverified_count?: number;
  gate?: boolean;
  verdict?: string;
  audited_at?: string;
  claims?: ClaimVerdict[];
  skipped?: boolean;
  reason?: string;
}

// ---- V2.2 hypothesis-anchored honest gate (ledger/anchored_verdict.json) ----

export interface KillCriterion {
  criterion: string;
  tripped: boolean;
  needs_manual: boolean;
  reason: string;
  metric?: string | null;
  value?: number | null;
  threshold?: number | null;
}

export interface CitationGroundingLog {
  unverified_before?: Array<{ title?: string; marker?: string }>;
  revised?: boolean;
  unverified_after?: Array<{ title?: string; marker?: string }>;
  error?: string;
}

export interface AnchoredVerdict {
  verdict?: string;
  base_verdict?: string;
  primary_metric?: string;
  primary_metric_source?: string;
  primary_beats_baseline?: boolean | null;
  kill_criteria?: KillCriterion[];
  downgraded?: boolean;
  downgrade_reasons?: string[];
  missing_baselines?: string[];
  underpowered?: {
    underpowered: boolean;
    ran_seeds: number;
    recommended_seeds: number;
    note: string;
  } | null;
  follow_up?: {
    ran: boolean;
    action?: string;
    description?: string;
    systems_added?: string[];
    reason?: string;
  } | null;
}

// ---- V2.3 portfolio-aware execution (ledger/portfolio.json) ----

export interface PortfolioCandidateRow {
  candidate_id: string;
  title?: string;
  primary_metric?: string | null;
  /** Did the proposed method beat the baseline on this candidate's primary metric. */
  beats_baseline?: boolean | null;
  /** Anchored verdict (evidence.full_verdict) for this candidate. */
  verdict?: string;
  /** Whether any deterministic kill criterion tripped for this candidate. */
  kill_tripped?: boolean;
  /** Whether the verdict was downgraded from the generic-metric base verdict. */
  downgraded?: boolean;
  execution_status?: string;
  feasibility?: string;
  /** True on the portfolio's best (anchored-verdict winner) candidate. */
  is_best?: boolean;
}

export interface PortfolioSummary {
  k?: number;
  /** Honest overall label: `best=<verdict>` | `all_negative` | `mixed_portfolio`. */
  portfolio_verdict?: string;
  best_candidate_id?: string | null;
  best_candidate?: Record<string, unknown> | null;
  rows?: PortfolioCandidateRow[];
  note?: string;
}
