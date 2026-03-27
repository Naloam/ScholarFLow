export type HealthResponse = {
  status: string;
};

export type AuthConfig = {
  auth_required: boolean;
  session_enabled: boolean;
};

export type AuthUser = {
  id: string;
  email: string;
  name?: string | null;
  role: string;
  created_at?: string | null;
};

export type AuthSessionResponse = {
  access_token: string;
  token_type: string;
  expires_at: string;
  user: AuthUser;
};

export type AuthSessionPayload = {
  email: string;
  name?: string;
  role?: "student" | "tutor";
};

export type UsageEvent = {
  source: string;
  operation?: string | null;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  duration_ms: number;
  created_at?: string | null;
};

export type PerformanceSummary = {
  total_events: number;
  llm_calls: number;
  embedding_calls: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  average_latency_ms: number;
  latest_model?: string | null;
  latest_operation?: string | null;
  recent_events: UsageEvent[];
};

export type FeedbackEntry = {
  id: string;
  project_id: string;
  user_id?: string | null;
  rating: number;
  category: string;
  comment: string;
  status: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type BetaSummary = {
  project_id: string;
  performance: PerformanceSummary;
  feedback: FeedbackEntry[];
  feedback_count: number;
  average_rating?: number | null;
};

export type MentorAccessEntry = {
  id: string;
  project_id: string;
  mentor_user_id?: string | null;
  mentor_email: string;
  mentor_name?: string | null;
  invited_by_user_id: string;
  status: string;
  created_at?: string | null;
};

export type MentorFeedbackEntry = {
  id: string;
  project_id: string;
  mentor_user_id: string;
  mentor_email: string;
  mentor_name?: string | null;
  draft_version?: number | null;
  summary: string;
  strengths: string;
  concerns: string;
  next_steps: string;
  created_at?: string | null;
};

export type IdResponse = {
  id: string;
};

export type TemplateMeta = {
  id?: string | null;
  name: string;
  description?: string | null;
};

export type TemplateListResponse = {
  items: TemplateMeta[];
};

export type Project = {
  id: string;
  user_id?: string | null;
  title: string;
  topic?: string | null;
  template_id?: string | null;
  status?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ProjectListItem = Project & {
  access_mode: "owner" | "mentor";
};

export type ProjectStatus = {
  status: string;
  phase?: string | null;
  progress?: number | null;
  message?: string | null;
};

export type ProjectProgressSnapshot = {
  project_id: string;
  status: string;
  phase: string;
  progress: number;
  draft_count: number;
  latest_draft_version?: number | null;
  latest_draft_created_at?: string | null;
  evidence_count: number;
  review_count: number;
  latest_review_id?: string | null;
  latest_review_status?: "pending" | "ready" | null;
  latest_review_created_at?: string | null;
  export_count: number;
  latest_export_id?: string | null;
  latest_export_status?: string | null;
  updated_at: string;
  signature: string;
};

export type DraftClaimRef = {
  claim: string;
  evidence_refs: string[];
  confidence?: number | null;
};

export type Draft = {
  id?: string | null;
  project_id?: string | null;
  version: number;
  section?: string | null;
  content: string;
  claims: DraftClaimRef[];
  created_at?: string | null;
};

export type EvidenceItem = {
  id?: string | null;
  project_id?: string | null;
  draft_version?: number | null;
  claim_text: string;
  paper_id: string;
  chunk_id?: string | null;
  page?: number | null;
  section?: string | null;
  snippet?: string | null;
  confidence?: number | null;
  type?: string | null;
  created_at?: string | null;
};

export type ReviewScore = {
  originality: number;
  importance: number;
  evidence_support: number;
  soundness: number;
  clarity: number;
  value: number;
  contextualization: number;
};

export type ReviewReport = {
  id?: string | null;
  project_id?: string | null;
  draft_version?: number | null;
  scores: ReviewScore;
  suggestions: string[];
  created_at?: string | null;
};

export type ScoreSummary = {
  originality: number;
  importance: number;
  evidence_support: number;
  soundness: number;
  clarity: number;
  value: number;
  contextualization: number;
};

export type AnalysisSummary = {
  project_id: string;
  draft_version?: number | null;
  evidence_coverage: number;
  needs_evidence_count: number;
  review_scores?: ScoreSummary | null;
  chart?: {
    labels: string[];
    values: number[];
  } | null;
  similarity?: {
    checked_paragraphs: number;
    flagged_paragraphs: number;
    max_similarity: number;
    average_similarity: number;
    status: "clear" | "warning" | "high";
    matches: Array<{
      source_type: "evidence_snippet" | "paper_abstract";
      source_label: string;
      paper_id?: string | null;
      paper_title?: string | null;
      similarity: number;
      overlap_units: number;
      draft_excerpt: string;
      source_excerpt: string;
    }>;
  } | null;
};

export type ExportResult = {
  file_id: string;
  format: string;
  status: string;
  file_name?: string | null;
  download_ready: boolean;
  created_at?: string | null;
};

export type CreateProjectPayload = {
  title: string;
  topic?: string;
  template_id?: string;
  status?: string;
};

export type AutoResearchRunStatus =
  | "queued"
  | "running"
  | "done"
  | "failed"
  | "canceled";

export type AutoResearchJobAction = "run" | "resume" | "retry";

export type AutoResearchRunRequest = {
  topic: string;
  task_family_hint?: "text_classification" | "tabular_classification" | "ir_reranking";
  docker_image?: string | null;
  paper_ids?: string[] | null;
  max_rounds?: number;
  candidate_execution_limit?: number | null;
  queue_priority?: "low" | "normal" | "high";
  benchmark?: Record<string, unknown> | null;
  execution_backend?: Record<string, unknown> | null;
  auto_search_literature?: boolean;
  auto_fetch_literature?: boolean;
};

export type AutoResearchRunControlPatch = {
  max_rounds?: number | null;
  candidate_execution_limit?: number | null;
  queue_priority?: "low" | "normal" | "high" | null;
};

export type AutoResearchClaimEvidenceRef = {
  source_kind: "plan" | "portfolio" | "artifact" | "literature" | "attempts";
  label: string;
  detail: string;
  locator?: string | null;
};

export type AutoResearchClaimEvidenceEntry = {
  claim_id: string;
  category: "problem" | "method" | "result" | "context" | "limitation";
  section_hint: string;
  claim: string;
  support_status: "supported" | "partial" | "unsupported";
  evidence: AutoResearchClaimEvidenceRef[];
  gaps: string[];
};

export type AutoResearchClaimEvidenceMatrix = {
  generated_at: string;
  claim_count: number;
  supported_claim_count: number;
  unsupported_claim_count: number;
  entries: AutoResearchClaimEvidenceEntry[];
};

export type AutoResearchPaperPlanSection = {
  section_id: string;
  title: string;
  objective: string;
  claim_ids: string[];
  evidence_focus: string[];
};

export type AutoResearchPaperPlan = {
  generated_at: string;
  title: string;
  narrative_summary: string;
  sections: AutoResearchPaperPlanSection[];
};

export type AutoResearchFigurePlanItem = {
  figure_id: string;
  title: string;
  kind: "table" | "chart" | "diagram";
  source: string;
  caption: string;
  status: "planned" | "ready" | "not_available";
};

export type AutoResearchFigurePlan = {
  generated_at: string;
  items: AutoResearchFigurePlanItem[];
};

export type AutoResearchPaperRevisionState = {
  generated_at: string;
  revision_round: number;
  status: "drafted" | "needs_review" | "revising" | "ready_for_publish";
  open_issues: string[];
  completed_actions: string[];
  focus_sections: string[];
  next_actions: AutoResearchPaperRevisionAction[];
  checkpoints: AutoResearchPaperRevisionCheckpoint[];
};

export type AutoResearchPaperSourceFile = {
  relative_path: string;
  kind: "latex" | "bibtex" | "json" | "markdown" | "shell";
  description: string;
};

export type AutoResearchPaperRevisionAction = {
  action_id: string;
  priority: "high" | "medium" | "low";
  section_title: string;
  detail: string;
  status: "open" | "done";
};

export type AutoResearchPaperRevisionCheckpoint = {
  revision_round: number;
  generated_at: string;
  status: "drafted" | "needs_review" | "revising" | "ready_for_publish";
  summary: string;
  open_issue_count: number;
  open_issue_summaries: string[];
  focus_sections: string[];
  next_action_ids: string[];
  completed_action_titles: string[];
  relative_assets: string[];
};

export type AutoResearchPaperSectionRewritePacket = {
  section_id: string;
  section_title: string;
  revision_round: number;
  focus: boolean;
  objective: string;
  claim_ids: string[];
  evidence_focus: string[];
  action_ids: string[];
  open_issues: string[];
  current_word_count: number;
  relative_path: string;
  source_asset_paths: string[];
};

export type AutoResearchPaperSectionRewriteIndex = {
  generated_at: string;
  revision_round: number;
  packet_count: number;
  focus_packet_count: number;
  packets: AutoResearchPaperSectionRewritePacket[];
};

export type AutoResearchPaperRevisionDiffSection = {
  section_id: string;
  section_title: string;
  status: "initial" | "updated" | "unchanged";
  previous_word_count: number;
  current_word_count: number;
  word_delta: number;
  previous_action_ids: string[];
  current_action_ids: string[];
  resolved_action_ids: string[];
  previous_open_issue_count: number;
  current_open_issue_count: number;
  resolved_issue_summaries: string[];
};

export type AutoResearchPaperRevisionDiff = {
  generated_at: string;
  revision_round: number;
  base_revision_round?: number | null;
  summary: string;
  changed_section_count: number;
  unchanged_section_count: number;
  resolved_action_count: number;
  resolved_issue_count: number;
  sections: AutoResearchPaperRevisionDiffSection[];
};

export type AutoResearchPaperRevisionActionEntry = {
  action_id: string;
  title?: string | null;
  detail: string;
  priority: "high" | "medium" | "low";
  status: "pending" | "completed";
  section_id?: string | null;
  section_title: string;
  first_seen_round: number;
  last_seen_round: number;
  completed_round?: number | null;
  issue_ids: string[];
  claim_ids: string[];
  evidence_focus: string[];
  packet_relative_path?: string | null;
  diff_status: "initial" | "updated" | "unchanged";
  current_word_count: number;
  word_delta: number;
  open_issue_summaries: string[];
  resolved_issue_summaries: string[];
  current_excerpt?: string | null;
};

export type AutoResearchPaperRevisionActionIndex = {
  generated_at: string;
  revision_round: number;
  total_action_count: number;
  pending_action_count: number;
  completed_action_count: number;
  materialized_action_count: number;
  summary: string;
  actions: AutoResearchPaperRevisionActionEntry[];
};

export type AutoResearchPaperSourcesManifest = {
  generated_at: string;
  entrypoint: string;
  bibliography?: string | null;
  compiler_hint: string;
  compile_commands: string[];
  expected_outputs: string[];
  files: AutoResearchPaperSourceFile[];
};

export type AutoResearchPaperCompileReport = {
  generated_at: string;
  entrypoint: string;
  bibliography?: string | null;
  compiler_hint: string;
  compile_commands: string[];
  required_inputs: string[];
  missing_required_inputs: string[];
  expected_outputs: string[];
  materialized_outputs: string[];
  ready_for_compile: boolean;
};

export type AutoResearchRun = {
  id: string;
  project_id: string;
  topic: string;
  status: AutoResearchRunStatus;
  error?: string | null;
  narrative_report_markdown?: string | null;
  narrative_report_path?: string | null;
  claim_evidence_matrix?: AutoResearchClaimEvidenceMatrix | null;
  claim_evidence_matrix_path?: string | null;
  paper_plan?: AutoResearchPaperPlan | null;
  paper_plan_path?: string | null;
  figure_plan?: AutoResearchFigurePlan | null;
  figure_plan_path?: string | null;
  paper_revision_state?: AutoResearchPaperRevisionState | null;
  paper_revision_state_path?: string | null;
  paper_compile_report?: AutoResearchPaperCompileReport | null;
  paper_compile_report_path?: string | null;
  paper_revision_action_index?: AutoResearchPaperRevisionActionIndex | null;
  paper_revision_action_index_path?: string | null;
  paper_revision_diff?: AutoResearchPaperRevisionDiff | null;
  paper_revision_diff_path?: string | null;
  paper_section_rewrite_index?: AutoResearchPaperSectionRewriteIndex | null;
  paper_section_rewrite_index_path?: string | null;
  paper_sources_dir?: string | null;
  paper_section_rewrite_packets_dir?: string | null;
  paper_latex_source?: string | null;
  paper_latex_path?: string | null;
  paper_bibliography_bib?: string | null;
  paper_bibliography_path?: string | null;
  paper_sources_manifest?: AutoResearchPaperSourcesManifest | null;
  paper_sources_manifest_path?: string | null;
  created_at: string;
  updated_at: string;
  [key: string]: unknown;
};

export type AutoResearchExecutionJob = {
  id: string;
  project_id: string;
  run_id: string;
  action: AutoResearchJobAction;
  priority: "low" | "normal" | "high";
  status: "queued" | "leased" | "running" | "succeeded" | "failed" | "canceled";
  lease_id?: string | null;
  detail?: string | null;
  enqueued_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  cancellation_requested_at?: string | null;
  attempt_count: number;
  recovery_count: number;
  last_recovered_at?: string | null;
  worker_id?: string | null;
  error?: string | null;
};

export type AutoResearchWorkerState = {
  worker_id?: string | null;
  status: "idle" | "starting" | "running" | "stopping";
  current_job_id?: string | null;
  current_run_id?: string | null;
  current_lease_id?: string | null;
  heartbeat_at?: string | null;
  processed_jobs: number;
  queue_depth: number;
  recovered_job_count: number;
  last_error?: string | null;
};

export type AutoResearchExecution = {
  project_id: string;
  run_id: string;
  jobs: AutoResearchExecutionJob[];
  active_job_id?: string | null;
  cancel_requested: boolean;
  worker?: AutoResearchWorkerState | null;
};

export type AutoResearchExecutionCommandResponse = {
  run_id: string;
  job_id?: string | null;
  status: "accepted" | "noop";
  execution: AutoResearchExecution;
};

export type AutoResearchRegistryAssetRef = {
  path: string;
  kind: "file" | "directory";
  exists: boolean;
  size_bytes?: number | null;
  sha256?: string | null;
};

export type AutoResearchLineageEdge = {
  source_kind:
    | "run"
    | "program"
    | "portfolio"
    | "candidate"
    | "workspace"
    | "plan"
    | "spec"
    | "attempts"
    | "artifact"
    | "paper"
    | "manifest"
    | "generated_code"
    | "benchmark"
    | "narrative_report"
    | "claim_evidence_matrix"
    | "paper_plan"
    | "figure_plan"
    | "paper_revision_history"
    | "paper_revision_state"
    | "paper_compile_report"
    | "paper_revision_action_index"
    | "paper_revision_diff"
    | "paper_section_rewrite_index"
    | "paper_revision_brief"
    | "paper_sources"
    | "paper_section_rewrite_packets"
    | "paper_build_script"
    | "paper_checkpoint_index"
    | "paper_latex"
    | "paper_bibliography"
    | "paper_sources_manifest";
  source_id: string;
  relation: "owns" | "selected_candidate" | "has_asset" | "materialized_to_run_asset";
  target_kind:
    | "run"
    | "program"
    | "portfolio"
    | "candidate"
    | "workspace"
    | "plan"
    | "spec"
    | "attempts"
    | "artifact"
    | "paper"
    | "manifest"
    | "generated_code"
    | "benchmark"
    | "narrative_report"
    | "claim_evidence_matrix"
    | "paper_plan"
    | "figure_plan"
    | "paper_revision_history"
    | "paper_revision_state"
    | "paper_compile_report"
    | "paper_revision_action_index"
    | "paper_revision_diff"
    | "paper_section_rewrite_index"
    | "paper_revision_brief"
    | "paper_sources"
    | "paper_section_rewrite_packets"
    | "paper_build_script"
    | "paper_checkpoint_index"
    | "paper_latex"
    | "paper_bibliography"
    | "paper_sources_manifest";
  target_id: string;
  target_path?: string | null;
  exists?: boolean | null;
};

export type AutoResearchRunRegistryFiles = {
  root: AutoResearchRegistryAssetRef;
  run_json: AutoResearchRegistryAssetRef;
  program_json?: AutoResearchRegistryAssetRef | null;
  plan_json?: AutoResearchRegistryAssetRef | null;
  spec_json?: AutoResearchRegistryAssetRef | null;
  portfolio_json?: AutoResearchRegistryAssetRef | null;
  artifact_json?: AutoResearchRegistryAssetRef | null;
  benchmark_json?: AutoResearchRegistryAssetRef | null;
  generated_code?: AutoResearchRegistryAssetRef | null;
  paper_markdown?: AutoResearchRegistryAssetRef | null;
  narrative_report_markdown?: AutoResearchRegistryAssetRef | null;
  claim_evidence_matrix_json?: AutoResearchRegistryAssetRef | null;
  paper_plan_json?: AutoResearchRegistryAssetRef | null;
  figure_plan_json?: AutoResearchRegistryAssetRef | null;
  paper_revision_history_markdown?: AutoResearchRegistryAssetRef | null;
  paper_revision_state_json?: AutoResearchRegistryAssetRef | null;
  paper_compile_report_json?: AutoResearchRegistryAssetRef | null;
  paper_revision_action_index_json?: AutoResearchRegistryAssetRef | null;
  paper_revision_diff_json?: AutoResearchRegistryAssetRef | null;
  paper_section_rewrite_index_json?: AutoResearchRegistryAssetRef | null;
  paper_revision_brief_markdown?: AutoResearchRegistryAssetRef | null;
  paper_sources_dir?: AutoResearchRegistryAssetRef | null;
  paper_section_rewrite_packets_dir?: AutoResearchRegistryAssetRef | null;
  paper_build_script?: AutoResearchRegistryAssetRef | null;
  paper_checkpoint_index_json?: AutoResearchRegistryAssetRef | null;
  paper_latex_source?: AutoResearchRegistryAssetRef | null;
  paper_bibliography_bib?: AutoResearchRegistryAssetRef | null;
  paper_sources_manifest_json?: AutoResearchRegistryAssetRef | null;
};

export type AutoResearchCandidateRegistryFiles = {
  workspace: AutoResearchRegistryAssetRef;
  candidate_json?: AutoResearchRegistryAssetRef | null;
  plan_json?: AutoResearchRegistryAssetRef | null;
  spec_json?: AutoResearchRegistryAssetRef | null;
  attempts_json?: AutoResearchRegistryAssetRef | null;
  artifact_json?: AutoResearchRegistryAssetRef | null;
  manifest_json?: AutoResearchRegistryAssetRef | null;
  generated_code?: AutoResearchRegistryAssetRef | null;
  paper_markdown?: AutoResearchRegistryAssetRef | null;
};

export type AutoResearchCandidateManifestCandidate = {
  id: string;
  program_id: string;
  rank: number;
  title: string;
  status: "planned" | "selected" | "running" | "done" | "failed" | "deferred";
  objective_score?: number | null;
  selection_reason?: string | null;
};

export type AutoResearchCandidateManifest = {
  manifest_source: "file" | "generated_fallback";
  candidate: AutoResearchCandidateManifestCandidate;
  decision?: Record<string, unknown> | null;
  files: AutoResearchCandidateRegistryFiles;
};

export type AutoResearchCandidateRegistryEntry = {
  candidate_id: string;
  program_id: string;
  rank: number;
  title: string;
  status: "planned" | "selected" | "running" | "done" | "failed" | "deferred";
  objective_score?: number | null;
  selected: boolean;
  selected_round_index?: number | null;
  attempt_count: number;
  artifact_status?: string | null;
  manifest_source: "file" | "generated_fallback";
  decision_outcome?: "pending" | "running" | "leading" | "promoted" | "eliminated" | "failed" | null;
  decision_reason?: string | null;
  files: AutoResearchCandidateRegistryFiles;
};

export type AutoResearchRunLineage = {
  selected_candidate_id?: string | null;
  top_level_plan_candidate_id?: string | null;
  top_level_spec_candidate_id?: string | null;
  top_level_artifact_candidate_id?: string | null;
  top_level_paper_candidate_id?: string | null;
  edges: AutoResearchLineageEdge[];
};

export type AutoResearchCandidateLineage = {
  selected: boolean;
  decision_outcome?: "pending" | "running" | "leading" | "promoted" | "eliminated" | "failed" | null;
  edges: AutoResearchLineageEdge[];
};

export type AutoResearchRunRegistry = {
  project_id: string;
  run_id: string;
  topic: string;
  status: AutoResearchRunStatus;
  task_family?: "text_classification" | "tabular_classification" | "ir_reranking" | null;
  program_id?: string | null;
  benchmark_name?: string | null;
  portfolio_status?: "planned" | "running" | "done" | "failed" | null;
  selected_candidate_id?: string | null;
  decision_summary?: string | null;
  root_path: string;
  files: AutoResearchRunRegistryFiles;
  lineage: AutoResearchRunLineage;
  candidates: AutoResearchCandidateRegistryEntry[];
};

export type AutoResearchCandidateRegistry = {
  project_id: string;
  run_id: string;
  candidate_id: string;
  selected: boolean;
  root_path: string;
  candidate: Record<string, unknown>;
  decision?: Record<string, unknown> | null;
  manifest: AutoResearchCandidateManifest;
  lineage: AutoResearchCandidateLineage;
};

export type AutoResearchBundleAssetRead = {
  asset_id: string;
  label: string;
  role:
    | "run_json"
    | "program_json"
    | "portfolio_json"
    | "benchmark_json"
    | "run_plan_json"
    | "run_spec_json"
    | "run_artifact_json"
    | "run_generated_code"
    | "run_paper_markdown"
    | "run_narrative_report_markdown"
    | "run_claim_evidence_matrix_json"
    | "run_paper_plan_json"
    | "run_figure_plan_json"
    | "run_paper_revision_history_markdown"
    | "run_paper_revision_brief_markdown"
    | "run_paper_revision_state_json"
    | "run_paper_compile_report_json"
    | "run_paper_revision_action_index_json"
    | "run_paper_revision_diff_json"
    | "run_paper_section_rewrite_index_json"
    | "run_paper_sources_dir"
    | "run_paper_section_rewrite_packets_dir"
    | "run_paper_build_script"
    | "run_paper_checkpoint_index_json"
    | "run_paper_latex_source"
    | "run_paper_bibliography_bib"
    | "run_paper_sources_manifest_json"
    | "workspace"
    | "candidate_json"
    | "plan_json"
    | "spec_json"
    | "attempts_json"
    | "artifact_json"
    | "manifest_json"
    | "generated_code"
    | "paper_markdown";
  candidate_id?: string | null;
  selected: boolean;
  required: boolean;
  ref: AutoResearchRegistryAssetRef;
};

export type AutoResearchBundle = {
  id: string;
  name: string;
  description: string;
  selected_candidate_id?: string | null;
  candidate_ids: string[];
  asset_count: number;
  existing_asset_count: number;
  missing_asset_count: number;
  assets: AutoResearchBundleAssetRead[];
};

export type AutoResearchBundleIndex = {
  project_id: string;
  run_id: string;
  bundles: AutoResearchBundle[];
};

export type AutoResearchRegistryView = {
  id: string;
  label: string;
  description: string;
  candidate_ids: string[];
  count: number;
  entries: AutoResearchCandidateRegistryEntry[];
};

export type AutoResearchRegistryViewCounts = {
  total_candidates: number;
  selected: number;
  eliminated: number;
  failed: number;
  active: number;
};

export type AutoResearchRunRegistryViews = {
  project_id: string;
  run_id: string;
  selected_candidate_id?: string | null;
  counts: AutoResearchRegistryViewCounts;
  views: AutoResearchRegistryView[];
};

export type AutoResearchReviewScores = {
  evidence_support: number;
  statistical_rigor: number;
  contextualization: number;
  reproducibility: number;
  publish_readiness: number;
};

export type AutoResearchReviewEvidence = {
  selected_bundle_id?: string | null;
  literature_count: number;
  candidate_count: number;
  executed_candidate_count: number;
  seed_count: number;
  completed_seed_count: number;
  sweep_count: number;
  significance_test_count: number;
  negative_result_count: number;
  failed_trial_count: number;
  acceptance_passed: number;
  acceptance_total: number;
  citation_marker_count: number;
  missing_required_asset_count: number;
};

export type AutoResearchCitationCoverage = {
  literature_item_count: number;
  citation_marker_count: number;
  cited_literature_count: number;
  invalid_citation_indices: number[];
  sections_without_citations: string[];
  has_related_work_section: boolean;
  has_references_section: boolean;
};

export type AutoResearchRelatedWorkMatch = {
  paper_id?: string | null;
  title: string;
  year?: number | null;
  source?: string | null;
  overlap_score: number;
  shared_terms: string[];
  gap_alignment_terms: string[];
  rationale: string;
};

export type AutoResearchNoveltyAssessment = {
  status: "missing_context" | "grounded" | "incremental" | "weak";
  summary: string;
  compared_paper_count: number;
  strong_match_count: number;
  gap_aligned_paper_count: number;
  covered_claim_count: number;
  total_claim_count: number;
  uncovered_claims: string[];
  top_related_work: AutoResearchRelatedWorkMatch[];
};

export type AutoResearchReviewFinding = {
  id: string;
  severity: "info" | "warning" | "error";
  category: "artifact" | "statistics" | "citation" | "context" | "provenance" | "publish";
  summary: string;
  detail: string;
  supporting_asset_ids: string[];
};

export type AutoResearchRevisionAction = {
  id: string;
  priority: "high" | "medium" | "low";
  title: string;
  detail: string;
  finding_ids: string[];
};

export type AutoResearchRunReview = {
  project_id: string;
  run_id: string;
  generated_at: string;
  selected_candidate_id?: string | null;
  backed_by_bundle_id?: string | null;
  overall_status: "ready" | "needs_revision" | "blocked";
  unsupported_claim_risk: "low" | "medium" | "high";
  summary: string;
  persisted_path?: string | null;
  evidence: AutoResearchReviewEvidence;
  citation_coverage: AutoResearchCitationCoverage;
  novelty_assessment?: AutoResearchNoveltyAssessment | null;
  scores: AutoResearchReviewScores;
  findings: AutoResearchReviewFinding[];
  revision_plan: AutoResearchRevisionAction[];
};

export type AutoResearchReviewLoopRound = {
  round_index: number;
  generated_at: string;
  fingerprint: string;
  overall_status: "ready" | "needs_revision" | "blocked";
  unsupported_claim_risk: "low" | "medium" | "high";
  summary: string;
  review_path?: string | null;
  finding_ids: string[];
  revision_action_ids: string[];
  revision_action_titles: string[];
  blocker_count: number;
};

export type AutoResearchReviewLoopIssue = {
  issue_id: string;
  category: "artifact" | "statistics" | "citation" | "context" | "provenance" | "publish";
  severity: "info" | "warning" | "error";
  summary: string;
  detail: string;
  status: "open" | "resolved";
  first_seen_round: number;
  last_seen_round: number;
  finding_ids: string[];
  action_titles: string[];
  supporting_asset_ids: string[];
};

export type AutoResearchReviewLoopAction = {
  action_id: string;
  priority: "high" | "medium" | "low";
  title: string;
  detail: string;
  status: "pending" | "completed";
  first_seen_round: number;
  last_seen_round: number;
  completed_round?: number | null;
  finding_ids: string[];
  issue_ids: string[];
};

export type AutoResearchReviewLoop = {
  project_id: string;
  run_id: string;
  generated_at: string;
  persisted_path?: string | null;
  current_round: number;
  overall_status: "ready" | "needs_revision" | "blocked";
  unsupported_claim_risk: "low" | "medium" | "high";
  latest_review_path?: string | null;
  latest_review_fingerprint?: string | null;
  rounds: AutoResearchReviewLoopRound[];
  issues: AutoResearchReviewLoopIssue[];
  actions: AutoResearchReviewLoopAction[];
  open_issue_count: number;
  resolved_issue_count: number;
  pending_action_count: number;
  completed_action_count: number;
  pending_revision_actions: string[];
};

export type AutoResearchPublishPackage = {
  project_id: string;
  run_id: string;
  package_id: string;
  generated_at: string;
  selected_candidate_id?: string | null;
  source_bundle_id?: string | null;
  status: "publish_ready" | "revision_required" | "blocked";
  publish_ready: boolean;
  review_bundle_ready: boolean;
  final_publish_ready: boolean;
  completeness_status: "complete" | "incomplete";
  review_path?: string | null;
  manifest_path?: string | null;
  archive_path?: string | null;
  asset_count: number;
  existing_asset_count: number;
  missing_required_asset_count: number;
  missing_final_asset_count: number;
  blocker_count: number;
  final_blocker_count: number;
  revision_count: number;
  blockers: string[];
  final_blockers: string[];
  revision_actions: string[];
  required_assets: AutoResearchBundleAssetRead[];
  final_required_assets: AutoResearchBundleAssetRead[];
  optional_assets: AutoResearchBundleAssetRead[];
};

export type AutoResearchPublishExport = {
  project_id: string;
  run_id: string;
  package_id: string;
  generated_at: string;
  bundle_kind: "review_bundle" | "final_publish_bundle";
  review_bundle_ready: boolean;
  final_publish_ready: boolean;
  file_name: string;
  archive_path: string;
  archive_manifest_path?: string | null;
  download_path: string;
  asset_count: number;
  included_asset_count: number;
  omitted_asset_count: number;
  download_ready: boolean;
};

export type AutoResearchOperatorProjectActions = {
  start_run: boolean;
};

export type AutoResearchOperatorConsoleFilters = {
  search?: string | null;
  status?: AutoResearchRunStatus | null;
  publish_status?: "publish_ready" | "revision_required" | "blocked" | null;
  review_risk?: "low" | "medium" | "high" | null;
  novelty_status?: "missing_context" | "grounded" | "incremental" | "weak" | null;
  budget_status?: "default" | "constrained" | null;
  queue_priority?: "low" | "normal" | "high" | null;
};

export type AutoResearchOperatorRunActions = {
  resume: boolean;
  retry: boolean;
  cancel: boolean;
  rebuild_paper: boolean;
  export_publish: boolean;
  download_publish: boolean;
  update_controls: boolean;
};

export type AutoResearchOperatorRunSummary = {
  run_id: string;
  topic: string;
  status: AutoResearchRunStatus;
  created_at: string;
  updated_at: string;
  selected_candidate_id?: string | null;
  candidate_count: number;
  selected_count: number;
  active_count: number;
  failed_count: number;
  eliminated_count: number;
  latest_job_status?: "queued" | "leased" | "running" | "succeeded" | "failed" | "canceled" | null;
  active_job_id?: string | null;
  cancel_requested: boolean;
  queue_priority: "low" | "normal" | "high";
  budget_status: "default" | "constrained";
  max_rounds: number;
  candidate_execution_limit?: number | null;
  executed_candidate_count: number;
  recovery_count: number;
  publish_status?: "publish_ready" | "revision_required" | "blocked" | null;
  publish_ready: boolean;
  review_risk?: "low" | "medium" | "high" | null;
  novelty_status?: "missing_context" | "grounded" | "incremental" | "weak" | null;
  blocker_count: number;
  revision_count: number;
};

export type AutoResearchOperatorRunDetail = {
  run: AutoResearchRun;
  execution: AutoResearchExecution;
  registry: AutoResearchRunRegistry;
  registry_views: AutoResearchRunRegistryViews;
  review?: AutoResearchRunReview | null;
  publish?: AutoResearchPublishPackage | null;
  actions: AutoResearchOperatorRunActions;
};

export type AutoResearchRunControlUpdate = {
  run: AutoResearchRun;
  execution: AutoResearchExecution;
};

export type AutoResearchOperatorConsole = {
  project_id: string;
  run_count: number;
  filtered_run_count: number;
  latest_run_id?: string | null;
  selected_run_id?: string | null;
  filters: AutoResearchOperatorConsoleFilters;
  actions: AutoResearchOperatorProjectActions;
  runs: AutoResearchOperatorRunSummary[];
  current_run?: AutoResearchOperatorRunDetail | null;
};

export type GenerateDraftPayload = {
  topic?: string;
  scope?: string;
  template_id?: string;
  language?: string;
};

export type UpdateDraftPayload = {
  content: string;
  section?: string | null;
};

export type CreateFeedbackPayload = {
  rating: number;
  category: string;
  comment: string;
};

export type CreateMentorAccessPayload = {
  email: string;
  name?: string;
};

export type CreateMentorFeedbackPayload = {
  draft_version?: number | null;
  summary: string;
  strengths: string;
  concerns: string;
  next_steps: string;
};
