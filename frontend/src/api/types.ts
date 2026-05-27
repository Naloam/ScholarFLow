export type HealthResponse = {
  status: string;
};

export type AuthConfig = {
  auth_required: boolean;
  api_protected: boolean;
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
  access_mode: "owner" | "mentor" | "anonymous";
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

export type AutoResearchTaskFamily =
  | "text_classification"
  | "tabular_classification"
  | "ir_reranking"
  | "llm_evaluation";

export type AutoResearchBenchmarkKind =
  | "builtin"
  | "remote_csv"
  | "remote_jsonl"
  | "remote_json"
  | "huggingface_file"
  | "openml_file"
  | "beir_json";

export type AutoResearchAcceptanceStatistic =
  | "mean"
  | "std"
  | "confidence_interval";

export type AutoResearchExecutionProfile = "exploratory" | "publication";

export type AutoResearchPublicationTier =
  | "exploratory"
  | "review_ready"
  | "publish_candidate"
  | "publish_ready";

export type AutoResearchPaperTier =
  | "technical_report"
  | "workshop_candidate"
  | "conference_candidate"
  | "strong_conference_candidate";

export type AutoResearchReadinessCategory =
  | "benchmark"
  | "literature"
  | "statistics"
  | "evidence"
  | "reproducibility"
  | "paper";

export type AutoResearchJobAction = "run" | "resume" | "retry";

export type AutoResearchExperimentBridgeNotificationHook = {
  channel: "console" | "file";
  target?: string | null;
  events: Array<
    | "session_created"
    | "result_imported"
    | "resume_enqueued"
    | "run_completed"
    | "run_failed"
    | "run_canceled"
  >;
};

export type AutoResearchExperimentBridgeConfig = {
  enabled: boolean;
  mode: "manual_async";
  target_kind: "manual" | "external_repo" | "gpu_server" | "workspace";
  target_label: string;
  auto_resume_on_result: boolean;
  notification_hooks: AutoResearchExperimentBridgeNotificationHook[];
};

export type AutoResearchRunRequest = {
  topic: string;
  task_family_hint?: AutoResearchTaskFamily;
  docker_image?: string | null;
  language?: string;
  paper_ids?: string[] | null;
  max_rounds?: number;
  candidate_execution_limit?: number | null;
  queue_priority?: "low" | "normal" | "high";
  benchmark?: Record<string, unknown> | null;
  execution_backend?: Record<string, unknown> | null;
  experiment_bridge?: AutoResearchExperimentBridgeConfig | null;
  auto_search_literature?: boolean;
  auto_fetch_literature?: boolean;
  execution_profile?: AutoResearchExecutionProfile;
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

export type AutoResearchPaperParagraphEvidence = {
  paragraph_id: string;
  section_id: string;
  section_title: string;
  paragraph_index: number;
  excerpt: string;
  claim_ids: string[];
  evidence_kinds: Array<"artifact" | "statistic" | "literature" | "negative">;
  evidence_refs: AutoResearchClaimEvidenceRef[];
  missing_evidence_kinds: Array<"artifact" | "statistic" | "literature" | "negative">;
  support_status: "supported" | "partial" | "unsupported";
};

export type AutoResearchPaperClaimLedgerEntry = {
  claim_id: string;
  claim: string;
  category: "problem" | "method" | "result" | "context" | "limitation";
  section_ids: string[];
  paragraph_ids: string[];
  support_status: "supported" | "partial" | "unsupported";
  evidence_kinds: Array<"artifact" | "statistic" | "literature" | "negative">;
  evidence_count: number;
  strong: boolean;
};

export type AutoResearchPaperUnregisteredClaim = {
  claim_id: string;
  section_id: string;
  section_title: string;
  excerpt: string;
  reason: string;
};

export type AutoResearchPaperContradiction = {
  contradiction_id: string;
  section_id: string;
  section_title: string;
  severity: "warning" | "blocker";
  claim_id?: string | null;
  summary: string;
  detail: string;
};

export type AutoResearchPaperCompileReport = {
  generated_at: string;
  entrypoint: string;
  bibliography?: string | null;
  compiler_hint: string;
  compile_commands: string[];
  required_inputs: string[];
  missing_required_inputs: string[];
  required_source_files: string[];
  missing_required_source_files: string[];
  expected_outputs: string[];
  materialized_outputs: string[];
  source_package_complete: boolean;
  all_expected_outputs_materialized: boolean;
  ready_for_compile: boolean;
  paper_tier: AutoResearchPaperTier;
  evidence_bound_paragraph_count: number;
  evidence_unbound_paragraph_count: number;
  strong_claim_count: number;
  registered_strong_claim_count: number;
  unregistered_claim_count: number;
  contradiction_count: number;
  blocker_count: number;
  paragraph_evidence: AutoResearchPaperParagraphEvidence[];
  claim_ledger: AutoResearchPaperClaimLedgerEntry[];
  unregistered_claims: AutoResearchPaperUnregisteredClaim[];
  contradictions: AutoResearchPaperContradiction[];
  evidence_blockers: string[];
  evidence_warnings: string[];
  evidence_compiler_fingerprint?: string | null;
};

export type AutoResearchRun = {
  id: string;
  project_id: string;
  topic: string;
  status: AutoResearchRunStatus;
  brief_id?: string | null;
  hypothesis_id?: string | null;
  direction_selection_reason?: string | null;
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
  experiment_factory_plan?: AutoResearchExperimentFactoryPlan | null;
  experiment_factory_plan_path?: string | null;
  experiment_factory_environment_manifest?: AutoResearchExperimentFactoryEnvironmentManifest | null;
  experiment_factory_environment_manifest_path?: string | null;
  experiment_factory_materialized_jobs: AutoResearchExperimentFactoryMaterializedJob[];
  experiment_factory_materialized_jobs_path?: string | null;
  evidence_ledger?: AutoResearchEvidenceLedger | null;
  evidence_ledger_path?: string | null;
  experiment_factory_repair_plan?: AutoResearchExperimentFactoryRepairPlan | null;
  experiment_factory_repair_plan_path?: string | null;
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
  lease_expires_at?: string | null;
  last_started_at?: string | null;
  last_completed_at?: string | null;
  last_recovered_at?: string | null;
  processed_jobs: number;
  queue_depth: number;
  recovered_job_count: number;
  stale: boolean;
  last_error?: string | null;
};

export type AutoResearchQueueTelemetry = {
  queue_depth: number;
  total_jobs: number;
  queued_jobs: number;
  leased_jobs: number;
  running_jobs: number;
  succeeded_jobs: number;
  failed_jobs: number;
  canceled_jobs: number;
  worker_count: number;
  active_workers: number;
  idle_workers: number;
  stale_workers: number;
  total_processed_jobs: number;
  total_recovered_jobs: number;
  last_recovered_at?: string | null;
  last_job_started_at?: string | null;
  last_job_finished_at?: string | null;
};

export type AutoResearchExecution = {
  project_id: string;
  run_id: string;
  jobs: AutoResearchExecutionJob[];
  active_job_id?: string | null;
  cancel_requested: boolean;
  queue?: AutoResearchQueueTelemetry | null;
  worker?: AutoResearchWorkerState | null;
  workers: AutoResearchWorkerState[];
};

export type AutoResearchExecutionCommandResponse = {
  run_id: string;
  job_id?: string | null;
  status: "accepted" | "noop";
  execution: AutoResearchExecution;
};

export type AutoResearchReviewLoopApplyRequest = {
  expected_round: number;
  expected_review_fingerprint: string;
};

export type AutoResearchDeploymentRef = {
  deployment_id: string;
  label: string;
  listed_at: string;
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
    | "benchmark_card"
    | "narrative_report"
    | "claim_evidence_matrix"
    | "experiment_design"
    | "failure_analysis"
    | "research_replan"
    | "research_protocol"
    | "methodology_audit"
    | "publication_readiness"
    | "contribution_assessment"
    | "literature_graph"
    | "novelty_validation"
    | "revision_dossier"
    | "publication_evidence_index"
    | "artifact_integrity_audit"
    | "publication_repair_plan"
    | "publication_repair_execution"
    | "reviewer_simulation"
    | "experiment_factory_plan"
    | "evidence_ledger"
    | "experiment_factory_repair_plan"
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
    | "paper_sources_manifest"
    | "paper_compiled_pdf"
    | "paper_bibliography_output";
  source_id: string;
  relation:
    | "owns"
    | "selected_candidate"
    | "has_asset"
    | "materialized_to_run_asset"
    | "derived_from";
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
    | "benchmark_card"
    | "narrative_report"
    | "claim_evidence_matrix"
    | "experiment_design"
    | "failure_analysis"
    | "research_replan"
    | "research_protocol"
    | "methodology_audit"
    | "publication_readiness"
    | "contribution_assessment"
    | "literature_graph"
    | "novelty_validation"
    | "revision_dossier"
    | "publication_evidence_index"
    | "artifact_integrity_audit"
    | "publication_repair_plan"
    | "publication_repair_execution"
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
    | "paper_sources_manifest"
    | "paper_compiled_pdf"
    | "paper_bibliography_output";
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
  benchmark_card_json?: AutoResearchRegistryAssetRef | null;
  generated_code?: AutoResearchRegistryAssetRef | null;
  paper_markdown?: AutoResearchRegistryAssetRef | null;
  narrative_report_markdown?: AutoResearchRegistryAssetRef | null;
  claim_evidence_matrix_json?: AutoResearchRegistryAssetRef | null;
  experiment_design_json?: AutoResearchRegistryAssetRef | null;
  failure_analysis_json?: AutoResearchRegistryAssetRef | null;
  research_replan_json?: AutoResearchRegistryAssetRef | null;
  research_protocol_json?: AutoResearchRegistryAssetRef | null;
  methodology_audit_json?: AutoResearchRegistryAssetRef | null;
  publication_readiness_json?: AutoResearchRegistryAssetRef | null;
  contribution_assessment_json?: AutoResearchRegistryAssetRef | null;
  literature_graph_json?: AutoResearchRegistryAssetRef | null;
  novelty_validation_json?: AutoResearchRegistryAssetRef | null;
  revision_dossier_json?: AutoResearchRegistryAssetRef | null;
  publication_evidence_index_json?: AutoResearchRegistryAssetRef | null;
  artifact_integrity_audit_json?: AutoResearchRegistryAssetRef | null;
  publication_repair_plan_json?: AutoResearchRegistryAssetRef | null;
  publication_repair_execution_json?: AutoResearchRegistryAssetRef | null;
  reviewer_simulation_json?: AutoResearchRegistryAssetRef | null;
  experiment_factory_plan_json?: AutoResearchRegistryAssetRef | null;
  experiment_factory_environment_manifest_json?: AutoResearchRegistryAssetRef | null;
  experiment_factory_materialized_jobs_json?: AutoResearchRegistryAssetRef | null;
  evidence_ledger_json?: AutoResearchRegistryAssetRef | null;
  experiment_factory_repair_plan_json?: AutoResearchRegistryAssetRef | null;
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
  paper_compiled_pdf?: AutoResearchRegistryAssetRef | null;
  paper_bibliography_output_bbl?: AutoResearchRegistryAssetRef | null;
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
  decision_outcome?:
    | "pending"
    | "running"
    | "leading"
    | "promoted"
    | "eliminated"
    | "failed"
    | null;
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
  decision_outcome?:
    | "pending"
    | "running"
    | "leading"
    | "promoted"
    | "eliminated"
    | "failed"
    | null;
  edges: AutoResearchLineageEdge[];
};

export type AutoResearchRunRegistry = {
  project_id: string;
  run_id: string;
  topic: string;
  status: AutoResearchRunStatus;
  task_family?: AutoResearchTaskFamily | null;
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
    | "run_benchmark_card_json"
    | "run_plan_json"
    | "run_spec_json"
    | "run_artifact_json"
    | "run_generated_code"
    | "run_paper_markdown"
    | "run_narrative_report_markdown"
    | "run_claim_evidence_matrix_json"
    | "run_experiment_design_json"
    | "run_failure_analysis_json"
    | "run_research_replan_json"
    | "run_research_protocol_json"
    | "run_methodology_audit_json"
    | "run_publication_readiness_json"
    | "run_contribution_assessment_json"
    | "run_literature_graph_json"
    | "run_novelty_validation_json"
    | "run_revision_dossier_json"
    | "run_publication_evidence_index_json"
    | "run_artifact_integrity_audit_json"
    | "run_publication_repair_plan_json"
    | "run_publication_repair_execution_json"
    | "run_reviewer_simulation_json"
    | "run_experiment_factory_plan_json"
    | "run_experiment_factory_environment_manifest_json"
    | "run_experiment_factory_materialized_jobs_json"
    | "run_evidence_ledger_json"
    | "run_experiment_factory_repair_plan_json"
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
    | "run_paper_compiled_pdf"
    | "run_paper_bibliography_output_bbl"
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
  real_literature_count: number;
  synthetic_literature_count: number;
  publication_grade_benchmark: boolean;
};

export type AutoResearchReadinessCheck = {
  check_id: string;
  category: AutoResearchReadinessCategory;
  passed: boolean;
  required_for_final_publish: boolean;
  summary: string;
  detail: string;
};

export type AutoResearchPublicationReadiness = {
  generated_at: string;
  tier: AutoResearchPublicationTier;
  score: number;
  summary: string;
  final_publish_ready: boolean;
  publication_grade_benchmark: boolean;
  real_literature_count: number;
  synthetic_literature_count: number;
  completed_seed_count: number;
  requested_seed_count: number;
  significance_test_count: number;
  planned_ablation_count: number;
  observed_ablation_count: number;
  unsupported_claim_count: number;
  checks: AutoResearchReadinessCheck[];
  blockers: string[];
  warnings: string[];
};

export type AutoResearchBenchmarkCard = {
  generated_at: string;
  card_id: string;
  topic?: string | null;
  task_family?: AutoResearchTaskFamily | null;
  benchmark_name?: string | null;
  benchmark_description?: string | null;
  dataset_name?: string | null;
  dataset_description?: string | null;
  train_size: number;
  test_size: number;
  total_examples: number;
  label_space: string[];
  input_fields: string[];
  source_kind?: AutoResearchBenchmarkKind | null;
  source_url?: string | null;
  source_dataset_id?: string | null;
  source_revision?: string | null;
  source_license?: string | null;
  source_fingerprint?: string | null;
  publication_grade: boolean;
  provenance_complete: boolean;
  checks: AutoResearchReadinessCheck[];
  limitations: string[];
  recommended_use: string[];
  blockers: string[];
  warnings: string[];
  card_fingerprint: string;
};

export type AutoResearchEvidenceIndexCategory =
  | "run"
  | "benchmark"
  | "protocol"
  | "design"
  | "failure"
  | "replan"
  | "methodology"
  | "readiness"
  | "contribution"
  | "novelty"
  | "revision"
  | "claims"
  | "paper"
  | "code"
  | "review"
  | "lineage"
  | "package";

export type AutoResearchEvidenceIndexItem = {
  evidence_id: string;
  label: string;
  category: AutoResearchEvidenceIndexCategory;
  role?: AutoResearchBundleAssetRead["role"] | null;
  path?: string | null;
  exists: boolean;
  size_bytes?: number | null;
  sha256?: string | null;
  required_for_final_publish: boolean;
  supports: string[];
  status: "present" | "missing";
};

export type AutoResearchPublicationEvidenceIndex = {
  generated_at: string;
  index_id: string;
  project_id: string;
  run_id: string;
  selected_candidate_id?: string | null;
  review_round: number;
  review_fingerprint?: string | null;
  publication_tier: AutoResearchPublicationTier;
  publication_readiness_score: number;
  evidence_item_count: number;
  required_evidence_count: number;
  present_required_evidence_count: number;
  missing_required_evidence_count: number;
  missing_required_evidence_ids: string[];
  evidence_items: AutoResearchEvidenceIndexItem[];
  blockers: string[];
  warnings: string[];
  complete: boolean;
  evidence_index_fingerprint: string;
};

export type AutoResearchArtifactIntegrityIssue = {
  issue_id: string;
  severity: "error" | "warning";
  category: "registry" | "bundle" | "lineage" | "identity";
  summary: string;
  detail: string;
  asset_id?: string | null;
  role?: AutoResearchBundleAssetRead["role"] | null;
  path?: string | null;
};

export type AutoResearchArtifactIntegrityAudit = {
  generated_at: string;
  audit_id: string;
  project_id: string;
  run_id: string;
  selected_candidate_id?: string | null;
  registry_asset_count: number;
  existing_registry_asset_count: number;
  missing_registry_asset_count: number;
  bundle_count: number;
  selected_bundle_asset_count: number;
  selected_bundle_missing_required_count: number;
  lineage_edge_count: number;
  missing_lineage_target_count: number;
  untraced_existing_asset_count: number;
  issue_count: number;
  blocker_count: number;
  warning_count: number;
  issues: AutoResearchArtifactIntegrityIssue[];
  blockers: string[];
  warnings: string[];
  complete: boolean;
  audit_fingerprint: string;
};

export type AutoResearchRepairActionKind =
  | "rebuild_paper_sources"
  | "repair_claim_evidence"
  | "refresh_literature"
  | "rerun_experiments"
  | "repair_experiment_design"
  | "research_replan"
  | "update_benchmark_provenance"
  | "rebuild_publish_package"
  | "manual_review";

export type AutoResearchRepairActionSource =
  | "review_finding"
  | "revision_action"
  | "revision_dossier"
  | "evidence_index"
  | "artifact_integrity_audit"
  | "readiness"
  | "contribution_assessment"
  | "novelty_validation"
  | "experiment_design"
  | "failure_analysis"
  | "research_replan";

export type AutoResearchPublicationRepairAction = {
  action_id: string;
  kind: AutoResearchRepairActionKind;
  source: AutoResearchRepairActionSource;
  source_ids: string[];
  priority: "high" | "medium" | "low";
  title: string;
  detail: string;
  status: "pending" | "blocked" | "not_needed";
  auto_applicable: boolean;
  expected_outputs: string[];
  supporting_asset_ids: string[];
  blockers: string[];
};

export type AutoResearchPublicationRepairPlan = {
  generated_at: string;
  plan_id: string;
  project_id: string;
  run_id: string;
  selected_candidate_id?: string | null;
  review_round: number;
  review_fingerprint?: string | null;
  publication_tier: AutoResearchPublicationTier;
  publication_readiness_score: number;
  action_count: number;
  pending_action_count: number;
  blocked_action_count: number;
  auto_applicable_action_count: number;
  next_action_ids: string[];
  actions: AutoResearchPublicationRepairAction[];
  complete: boolean;
  blockers: string[];
  repair_plan_fingerprint: string;
};

export type AutoResearchRepairExecutionActionStatus =
  | "executed"
  | "partial"
  | "blocked"
  | "skipped";

export type AutoResearchPublicationRepairExecutionAction = {
  action_id: string;
  kind: AutoResearchRepairActionKind;
  title: string;
  status: AutoResearchRepairExecutionActionStatus;
  auto_applicable: boolean;
  expected_output_asset_ids: string[];
  materialized_output_asset_ids: string[];
  missing_output_asset_ids: string[];
  detail: string;
};

export type AutoResearchPublicationRepairExecution = {
  generated_at: string;
  execution_id: string;
  project_id: string;
  run_id: string;
  selected_candidate_id?: string | null;
  repair_plan_fingerprint?: string | null;
  review_round_before: number;
  review_fingerprint_before?: string | null;
  review_round_after: number;
  review_fingerprint_after?: string | null;
  attempted_action_count: number;
  executed_action_count: number;
  partial_action_count: number;
  blocked_action_count: number;
  materialized_output_asset_ids: string[];
  missing_output_asset_ids: string[];
  action_results: AutoResearchPublicationRepairExecutionAction[];
  success: boolean;
  execution_fingerprint: string;
};

export type AutoResearchExperimentBaselineType =
  | "naive"
  | "strong_conventional"
  | "candidate_method";

export type AutoResearchStatisticalTestChoice =
  | "paired_t_test"
  | "bootstrap"
  | "permutation_test";

export type AutoResearchExperimentDesignCompleteness =
  | "complete"
  | "partial"
  | "blocked";

export type AutoResearchExperimentBaselinePlan = {
  name: string;
  baseline_type: AutoResearchExperimentBaselineType;
  required: boolean;
  present_in_spec: boolean;
  present_in_results: boolean;
  fair_comparison: boolean;
  rationale: string;
};

export type AutoResearchExperimentAblationPlan = {
  component_id: string;
  component: string;
  ablation_name?: string | null;
  planned: boolean;
  observed: boolean;
  rationale: string;
};

export type AutoResearchExperimentSeedPlan = {
  planned_seeds: number[];
  planned_seed_count: number;
  minimum_completed_seed_count: number;
  completed_seed_count: number;
  sufficient_for_profile: boolean;
  rationale: string;
};

export type AutoResearchExperimentSweepPlan = {
  planned_sweeps: string[];
  planned_sweep_count: number;
  observed_sweeps: string[];
  covers_search_space: boolean;
  rationale: string;
};

export type AutoResearchExperimentStatisticalTestPlan = {
  primary_metric?: string | null;
  recommended_test: AutoResearchStatisticalTestChoice;
  comparison_unit: "seed" | "example" | "aggregate";
  requires_confidence_interval: boolean;
  requires_effect_size: boolean;
  requires_power_note: boolean;
  planned_statistic_count: number;
  observed_significance_test_count: number;
  complete: boolean;
  rationale: string;
};

export type AutoResearchExperimentFailureMode = {
  mode_id: string;
  category:
    | "performance_failure"
    | "baseline_fairness_failure"
    | "ablation_coverage_failure"
    | "statistical_power_failure"
    | "artifact_failure";
  trigger: string;
  planned_response: string;
  severity: "low" | "medium" | "high";
};

export type AutoResearchExperimentDesign = {
  generated_at: string;
  design_id: string;
  project_id: string;
  run_id: string;
  execution_profile: AutoResearchExecutionProfile;
  baseline_plan: AutoResearchExperimentBaselinePlan[];
  ablation_plan: AutoResearchExperimentAblationPlan[];
  seed_plan: AutoResearchExperimentSeedPlan;
  sweep_plan: AutoResearchExperimentSweepPlan;
  statistical_test_plan: AutoResearchExperimentStatisticalTestPlan;
  failure_mode_analysis: AutoResearchExperimentFailureMode[];
  naive_baseline_present: boolean;
  strong_baseline_present: boolean;
  candidate_method_present: boolean;
  fair_baseline_count: number;
  ablation_coverage: number;
  completeness_score: number;
  completeness: AutoResearchExperimentDesignCompleteness;
  blockers: string[];
  warnings: string[];
  design_fingerprint: string;
};

export type AutoResearchFailureType =
  | "performance_failure"
  | "baseline_insufficient"
  | "ablation_unsupported_claim"
  | "statistical_not_significant"
  | "novelty_insufficient"
  | "artifact_incomplete";

export type AutoResearchResearchActionKind =
  | "modify_hypothesis"
  | "adjust_task_scope"
  | "add_baseline"
  | "add_ablation"
  | "downgrade_contribution_claim"
  | "abandon_direction"
  | "repair_experiment_design"
  | "rerun_plan";

export type AutoResearchFailureFinding = {
  failure_id: string;
  failure_type: AutoResearchFailureType;
  severity: "low" | "medium" | "high";
  summary: string;
  detail: string;
  trigger: string;
  evidence_refs: string[];
  recommended_action: AutoResearchResearchActionKind;
  blocks_publication: boolean;
};

export type AutoResearchFailureAnalysis = {
  generated_at: string;
  analysis_id: string;
  project_id: string;
  run_id: string;
  selected_candidate_id?: string | null;
  finding_count: number;
  high_severity_count: number;
  publication_blocker_count: number;
  performance_failure_count: number;
  baseline_failure_count: number;
  ablation_failure_count: number;
  statistical_failure_count: number;
  novelty_failure_count: number;
  artifact_failure_count: number;
  findings: AutoResearchFailureFinding[];
  complete: boolean;
  blockers: string[];
  warnings: string[];
  analysis_fingerprint: string;
};

export type AutoResearchResearchReplanAction = {
  action_id: string;
  action_kind: AutoResearchResearchActionKind;
  priority: "high" | "medium" | "low";
  title: string;
  rationale: string;
  target?: string | null;
  source_failure_ids: string[];
  expected_outputs: string[];
};

export type AutoResearchResearchReplan = {
  generated_at: string;
  replan_id: string;
  project_id: string;
  run_id: string;
  selected_candidate_id?: string | null;
  hypothesis_update?: string | null;
  task_scope_update?: string | null;
  actions: AutoResearchResearchReplanAction[];
  action_count: number;
  rerun_required: boolean;
  abandon_recommended: boolean;
  claim_downgrade_required: boolean;
  experiment_design_repair_required: boolean;
  complete: boolean;
  blockers: string[];
  warnings: string[];
  replan_fingerprint: string;
};

export type AutoResearchResearchProtocol = {
  generated_at: string;
  protocol_id: string;
  execution_profile: AutoResearchExecutionProfile;
  topic?: string | null;
  title?: string | null;
  task_family?: AutoResearchTaskFamily | null;
  benchmark_name?: string | null;
  benchmark_publication_grade: boolean;
  dataset_source_kind?: AutoResearchBenchmarkKind | null;
  dataset_source_url?: string | null;
  dataset_source_dataset_id?: string | null;
  dataset_fingerprint?: string | null;
  hypothesis?: string | null;
  research_questions: string[];
  primary_metric?: string | null;
  baseline_systems: string[];
  ablation_systems: string[];
  planned_seed_count: number;
  minimum_completed_seed_count: number;
  planned_sweep_count: number;
  acceptance_rule_count: number;
  acceptance_rule_ids: string[];
  required_statistics: AutoResearchAcceptanceStatistic[];
  significance_required: boolean;
  power_analysis_required: boolean;
  literature_minimum: number;
  evidence_requirements: string[];
  reproducibility_requirements: string[];
  threat_model: string[];
  checks: AutoResearchReadinessCheck[];
  complete: boolean;
  blockers: string[];
  warnings: string[];
  protocol_fingerprint: string;
};

export type AutoResearchMethodologyAudit = {
  generated_at: string;
  audit_id: string;
  protocol_fingerprint?: string | null;
  audit_fingerprint: string;
  execution_profile: AutoResearchExecutionProfile;
  primary_metric?: string | null;
  planned_seed_count: number;
  completed_seed_count: number;
  minimum_completed_seed_count: number;
  planned_sweep_labels: string[];
  observed_sweep_labels: string[];
  planned_ablation_systems: string[];
  observed_ablation_systems: string[];
  acceptance_rule_ids: string[];
  satisfied_acceptance_rule_ids: string[];
  required_statistics: AutoResearchAcceptanceStatistic[];
  observed_statistics: AutoResearchAcceptanceStatistic[];
  significance_test_count: number;
  adequately_powered_test_count: number;
  power_analysis_reported_count: number;
  real_literature_count: number;
  synthetic_literature_count: number;
  literature_minimum: number;
  unsupported_claim_count: number;
  partial_claim_count: number;
  compile_ready: boolean;
  paper_source_package_complete: boolean;
  checks: AutoResearchReadinessCheck[];
  score: number;
  compliant: boolean;
  blockers: string[];
  warnings: string[];
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

export type AutoResearchContributionType =
  | "new_method"
  | "new_system"
  | "experimental_finding"
  | "new_benchmark"
  | "analysis_framework";

export type AutoResearchClaimStrength =
  | "unsupported"
  | "weakly_supported"
  | "artifact_supported"
  | "statistically_supported"
  | "literature_positioned";

export type AutoResearchNoveltyRiskSeverity = "low" | "medium" | "high";

export type AutoResearchContributionClaim = {
  claim_id: string;
  text: string;
  contribution_type: AutoResearchContributionType;
  claim_strength: AutoResearchClaimStrength;
  core: boolean;
  evidence_sources: string[];
  rationale: string;
};

export type AutoResearchContributionNoveltyRisk = {
  risk_id: string;
  risk_type:
    | "duplicate_risk"
    | "incremental_risk"
    | "evidence_gap"
    | "literature_gap"
    | "claim_overreach";
  severity: AutoResearchNoveltyRiskSeverity;
  summary: string;
  detail: string;
  evidence_refs: string[];
};

export type AutoResearchContributionAssessment = {
  generated_at: string;
  assessment_id: string;
  contribution_claims: AutoResearchContributionClaim[];
  novelty_risks: AutoResearchContributionNoveltyRisk[];
  publishability_score: number;
  clear_contribution_count: number;
  strong_core_claim_count: number;
  artifact_supported_claim_count: number;
  statistically_supported_claim_count: number;
  literature_positioned_claim_count: number;
  complete: boolean;
  blockers: string[];
  warnings: string[];
  assessment_fingerprint: string;
};

export type AutoResearchLiteratureGraphNodeKind =
  | "paper"
  | "method"
  | "dataset"
  | "metric"
  | "claim";

export type AutoResearchLiteratureGraphRelation =
  | "mentions_method"
  | "evaluates_dataset"
  | "reports_metric"
  | "supports_claim"
  | "similar_to"
  | "identifies_gap";

export type AutoResearchNoveltyRiskLevel = "low" | "medium" | "high";
export type AutoResearchReviewerRole =
  | "novelty_reviewer"
  | "methodology_reviewer"
  | "reproducibility_reviewer"
  | "writing_reviewer"
  | "skeptical_reviewer";
export type AutoResearchReviewerDecision =
  | "accept"
  | "weak_accept"
  | "borderline"
  | "weak_reject"
  | "reject";
export type AutoResearchReviewerResponseActionKind =
  | "experiment"
  | "evidence"
  | "paper"
  | "research_replan";
export type AutoResearchResearchActionRecommendation =
  | "refresh_review"
  | "repair_experiment_design"
  | "rerun_experiments"
  | "research_replan"
  | "rebuild_paper"
  | "export_publish"
  | "meta_analyze"
  | "system_evaluate"
  | "wait_for_execution";
export type AutoResearchIdeaBudgetLabel = "toy" | "standard" | "publication";
export type AutoResearchConclusionStability =
  | "stable"
  | "conditional"
  | "unreproducible";
export type AutoResearchMetaAnalysisComparisonAxis =
  | "topic_hypothesis"
  | "method_dataset"
  | "dataset_method";
export type AutoResearchEvaluationTaskKind =
  | "toy_task"
  | "medium_benchmark_task"
  | "literature_heavy_task"
  | "ablation_heavy_task"
  | "failed_hypothesis_task";
export type AutoResearchGapValidityStatus = "valid" | "weak" | "invalid" | "missing";

export type AutoResearchLiteratureGraphNode = {
  node_id: string;
  node_type: AutoResearchLiteratureGraphNodeKind;
  label: string;
  source_paper_id?: string | null;
  synthetic: boolean;
  attributes: Record<string, unknown>;
};

export type AutoResearchLiteratureGraphEdge = {
  source_id: string;
  relation: AutoResearchLiteratureGraphRelation;
  target_id: string;
  evidence: string;
  weight: number;
};

export type AutoResearchLiteratureGraphMatch = {
  match_id: string;
  match_type: "method" | "task" | "benchmark";
  paper_id?: string | null;
  paper_title: string;
  overlap_score: number;
  shared_terms: string[];
  rationale: string;
};

export type AutoResearchKnownSota = {
  paper_id?: string | null;
  paper_title: string;
  method?: string | null;
  dataset?: string | null;
  metric?: string | null;
  score?: string | null;
  evidence: string;
};

export type AutoResearchLiteratureGraph = {
  generated_at: string;
  graph_id: string;
  project_id: string;
  run_id: string;
  paper_nodes: AutoResearchLiteratureGraphNode[];
  method_nodes: AutoResearchLiteratureGraphNode[];
  dataset_nodes: AutoResearchLiteratureGraphNode[];
  metric_nodes: AutoResearchLiteratureGraphNode[];
  claim_nodes: AutoResearchLiteratureGraphNode[];
  edges: AutoResearchLiteratureGraphEdge[];
  similar_methods: AutoResearchLiteratureGraphMatch[];
  similar_tasks: AutoResearchLiteratureGraphMatch[];
  similar_benchmarks: AutoResearchLiteratureGraphMatch[];
  known_sota: AutoResearchKnownSota[];
  real_paper_count: number;
  synthetic_paper_count: number;
  graph_fingerprint: string;
};

export type AutoResearchGapValidation = {
  gap_id: string;
  description: string;
  literature_evidence: string[];
  experimentally_testable: boolean;
  validation_target?: string | null;
  status: AutoResearchGapValidityStatus;
  blockers: string[];
};

export type AutoResearchNoveltyValidation = {
  generated_at: string;
  validation_id: string;
  project_id: string;
  run_id: string;
  duplicate_risk: AutoResearchNoveltyRiskLevel;
  incremental_risk: AutoResearchNoveltyRiskLevel;
  gap_validity: AutoResearchGapValidityStatus;
  experiment_coverage_risk: AutoResearchNoveltyRiskLevel;
  duplicate_risk_detail: string;
  incremental_risk_detail: string;
  experiment_coverage_detail: string;
  recommendation:
    | "proceed"
    | "reframe_positioning"
    | "change_research_question"
    | "change_experiment_design"
    | "attach_literature";
  gap_validations: AutoResearchGapValidation[];
  blockers: string[];
  warnings: string[];
  complete: boolean;
  validation_fingerprint: string;
};

export type AutoResearchReviewFinding = {
  id: string;
  severity: "info" | "warning" | "error";
  category:
    | "artifact"
    | "benchmark"
    | "statistics"
    | "citation"
    | "context"
    | "provenance"
    | "publish";
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
  literature_graph?: AutoResearchLiteratureGraph | null;
  literature_graph_path?: string | null;
  novelty_validation?: AutoResearchNoveltyValidation | null;
  novelty_validation_path?: string | null;
  experiment_design?: AutoResearchExperimentDesign | null;
  experiment_design_path?: string | null;
  failure_analysis?: AutoResearchFailureAnalysis | null;
  failure_analysis_path?: string | null;
  research_replan?: AutoResearchResearchReplan | null;
  research_replan_path?: string | null;
  benchmark_card?: AutoResearchBenchmarkCard | null;
  benchmark_card_path?: string | null;
  research_protocol?: AutoResearchResearchProtocol | null;
  research_protocol_path?: string | null;
  methodology_audit?: AutoResearchMethodologyAudit | null;
  methodology_audit_path?: string | null;
  publication_readiness?: AutoResearchPublicationReadiness | null;
  publication_readiness_path?: string | null;
  contribution_assessment?: AutoResearchContributionAssessment | null;
  contribution_assessment_path?: string | null;
  revision_dossier?: AutoResearchRevisionDossier | null;
  revision_dossier_path?: string | null;
  publication_evidence_index?: AutoResearchPublicationEvidenceIndex | null;
  publication_evidence_index_path?: string | null;
  reviewer_simulation?: AutoResearchReviewerSimulation | null;
  reviewer_simulation_path?: string | null;
  artifact_integrity_audit?: AutoResearchArtifactIntegrityAudit | null;
  artifact_integrity_audit_path?: string | null;
  publication_repair_plan?: AutoResearchPublicationRepairPlan | null;
  publication_repair_plan_path?: string | null;
  publication_repair_execution?: AutoResearchPublicationRepairExecution | null;
  publication_repair_execution_path?: string | null;
  scores: AutoResearchReviewScores;
  findings: AutoResearchReviewFinding[];
  revision_plan: AutoResearchRevisionAction[];
};

export type AutoResearchReviewerSimulationReview = {
  review_id: string;
  role: AutoResearchReviewerRole;
  summary: string;
  strengths: string[];
  weaknesses: string[];
  questions: string[];
  score: number;
  confidence: number;
  decision: AutoResearchReviewerDecision;
  reject_reason?: string | null;
};

export type AutoResearchReviewerResponseAction = {
  action_id: string;
  reviewer_role: AutoResearchReviewerRole;
  action_kind: AutoResearchReviewerResponseActionKind;
  priority: "high" | "medium" | "low";
  title: string;
  detail: string;
  maps_to: string;
  source_review_ids: string[];
};

export type AutoResearchReviewerSimulation = {
  generated_at: string;
  simulation_id: string;
  project_id: string;
  run_id: string;
  selected_candidate_id?: string | null;
  reviews: AutoResearchReviewerSimulationReview[];
  average_score: number;
  minimum_score: number;
  minimum_decision: AutoResearchReviewerDecision;
  weak_reject_or_worse_count: number;
  confidence_mean: number;
  publication_blocker_count: number;
  response_plan: AutoResearchReviewerResponseAction[];
  response_plan_action_count: number;
  complete: boolean;
  blockers: string[];
  warnings: string[];
  simulation_fingerprint: string;
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
  category:
    | "artifact"
    | "statistics"
    | "citation"
    | "context"
    | "provenance"
    | "publish";
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

export type AutoResearchRevisionDossierItem = {
  item_id: string;
  finding_id?: string | null;
  issue_id?: string | null;
  severity: "info" | "warning" | "error";
  category:
    | "artifact"
    | "benchmark"
    | "statistics"
    | "citation"
    | "context"
    | "provenance"
    | "publish";
  summary: string;
  response: string;
  status: "resolved" | "action_required" | "blocked";
  required_for_final_publish: boolean;
  action_ids: string[];
  action_titles: string[];
  supporting_asset_ids: string[];
};

export type AutoResearchRevisionDossier = {
  generated_at: string;
  dossier_id: string;
  review_round: number;
  review_fingerprint?: string | null;
  review_path?: string | null;
  overall_status: "ready" | "needs_revision" | "blocked";
  publication_tier: AutoResearchPublicationTier;
  publication_readiness_score: number;
  methodology_audit_score: number;
  methodology_audit_compliant: boolean;
  open_issue_count: number;
  resolved_issue_count: number;
  pending_action_count: number;
  completed_action_count: number;
  blocker_count: number;
  final_blocker_count: number;
  required_action_titles: string[];
  items: AutoResearchRevisionDossierItem[];
  complete: boolean;
  dossier_fingerprint: string;
};

export type AutoResearchReviewLoopApply = {
  run: AutoResearchRun;
  review: AutoResearchRunReview;
  review_loop: AutoResearchReviewLoop;
};

export type AutoResearchResearchReplanApply = {
  run: AutoResearchRun;
  review: AutoResearchRunReview;
  review_loop: AutoResearchReviewLoop;
  repair_execution?: AutoResearchPublicationRepairExecution | null;
  applied_action_ids: string[];
  queued_rerun_required: boolean;
};

export type AutoResearchBridgeImportedArtifact = {
  imported_at: string;
  source: "inline" | "file";
  artifact_path: string;
  summary: string;
  primary_metric: string;
  objective_score?: number | null;
};

export type AutoResearchBridgeSession = {
  session_id: string;
  created_at: string;
  updated_at: string;
  status:
    | "waiting_result"
    | "result_imported"
    | "completed"
    | "failed"
    | "canceled";
  candidate_id: string;
  candidate_title: string;
  round_index: number;
  goal: string;
  strategy: string;
  handoff_dir: string;
  manifest_path: string;
  instructions_path: string;
  code_path: string;
  benchmark_path?: string | null;
  result_path: string;
  last_polled_at?: string | null;
  external_status?: string | null;
  last_error?: string | null;
  imported_artifact?: AutoResearchBridgeImportedArtifact | null;
};

export type AutoResearchBridgeCheckpoint = {
  checkpoint_id: string;
  created_at: string;
  kind:
    | "session_created"
    | "status_polled"
    | "result_imported"
    | "resume_enqueued"
    | "run_completed"
    | "run_failed"
    | "run_canceled";
  summary: string;
  detail?: string | null;
  session_id?: string | null;
};

export type AutoResearchBridgeNotification = {
  notification_id: string;
  created_at: string;
  event:
    | "session_created"
    | "result_imported"
    | "resume_enqueued"
    | "run_completed"
    | "run_failed"
    | "run_canceled";
  channel: "console" | "file";
  status: "sent" | "failed" | "skipped";
  target?: string | null;
  message: string;
  delivered_at?: string | null;
  error?: string | null;
};

export type AutoResearchExperimentBridge = {
  project_id: string;
  run_id: string;
  enabled: boolean;
  config?: AutoResearchExperimentBridgeConfig | null;
  persisted_path?: string | null;
  status:
    | "inactive"
    | "waiting_result"
    | "result_imported"
    | "completed"
    | "failed"
    | "canceled";
  active_session_id?: string | null;
  latest_session_id?: string | null;
  open_session_count: number;
  imported_session_count: number;
  session_count: number;
  checkpoint_count: number;
  notification_count: number;
  current_session?: AutoResearchBridgeSession | null;
  sessions: AutoResearchBridgeSession[];
  checkpoints: AutoResearchBridgeCheckpoint[];
  notifications: AutoResearchBridgeNotification[];
};

export type AutoResearchBridgeImportRequest = {
  session_id?: string | null;
  summary: string;
  objective_score: number;
  primary_metric: string;
  objective_system: string;
  baseline_system: string;
  baseline_score?: number | null;
  key_findings: string[];
  notes?: string | null;
};

export type AutoResearchBridgeUpdate = {
  bridge: AutoResearchExperimentBridge;
  run: AutoResearchRun;
  execution: AutoResearchExecution;
  imported: boolean;
  resumed: boolean;
  source: "none" | "inline" | "file";
};

export type AutoResearchPublicationManifest = {
  publication_id: string;
  project_id: string;
  project_title?: string | null;
  run_id: string;
  topic: string;
  paper_title: string;
  paper_summary?: string | null;
  generated_at: string;
  updated_at: string;
  selected_candidate_id?: string | null;
  benchmark_name?: string | null;
  task_family?: AutoResearchTaskFamily | null;
  package_id: string;
  package_fingerprint?: string | null;
  bundle_kind: "review_bundle" | "final_publish_bundle";
  review_bundle_ready: boolean;
  final_publish_ready: boolean;
  publication_tier: AutoResearchPublicationTier;
  publication_readiness_score: number;
  benchmark_card_path?: string | null;
  benchmark_card_sha256?: string | null;
  research_protocol_path?: string | null;
  research_protocol_sha256?: string | null;
  methodology_audit_path?: string | null;
  methodology_audit_sha256?: string | null;
  publication_readiness_path?: string | null;
  publication_readiness_sha256?: string | null;
  experiment_design_path?: string | null;
  experiment_design_sha256?: string | null;
  failure_analysis_path?: string | null;
  failure_analysis_sha256?: string | null;
  research_replan_path?: string | null;
  research_replan_sha256?: string | null;
  contribution_assessment_path?: string | null;
  contribution_assessment_sha256?: string | null;
  literature_graph_path?: string | null;
  literature_graph_sha256?: string | null;
  novelty_validation_path?: string | null;
  novelty_validation_sha256?: string | null;
  revision_dossier_path?: string | null;
  revision_dossier_sha256?: string | null;
  publication_evidence_index_path?: string | null;
  publication_evidence_index_sha256?: string | null;
  artifact_integrity_audit_path?: string | null;
  artifact_integrity_audit_sha256?: string | null;
  reviewer_simulation_path?: string | null;
  reviewer_simulation_sha256?: string | null;
  publication_repair_plan_path?: string | null;
  publication_repair_plan_sha256?: string | null;
  publication_repair_execution_path?: string | null;
  publication_repair_execution_sha256?: string | null;
  archive_ready: boolean;
  archive_current: boolean;
  review_round: number;
  review_fingerprint?: string | null;
  publication_manifest_path: string;
  publish_manifest_path: string;
  publish_archive_path: string;
  paper_path?: string | null;
  compiled_paper_path?: string | null;
  compiled_paper_sha256?: string | null;
  paper_compile_output_paths: string[];
  code_package_path?: string | null;
  code_package_sha256?: string | null;
  run_api_path: string;
  registry_api_path: string;
  publish_api_path: string;
  publish_download_path: string;
  paper_download_path?: string | null;
  compiled_paper_download_path?: string | null;
  code_package_download_path?: string | null;
  deployments: AutoResearchDeploymentRef[];
};

export type AutoResearchDeploymentPublication = {
  deployment_id: string;
  listed_at: string;
  publication: AutoResearchPublicationManifest;
};

export type AutoResearchDeploymentFilters = {
  search?: string | null;
  final_publish_ready?: boolean | null;
  bundle_kind?: "review_bundle" | "final_publish_bundle" | null;
  task_family?: AutoResearchTaskFamily | null;
};

export type AutoResearchDeploymentSummary = {
  deployment_id: string;
  label: string;
  created_at: string;
  updated_at: string;
  publication_count: number;
  project_count: number;
  final_publish_ready_count: number;
  latest_publication_id?: string | null;
  latest_run_id?: string | null;
};

export type AutoResearchDeployment = {
  deployment_id: string;
  label: string;
  created_at: string;
  updated_at: string;
  publication_count: number;
  filtered_publication_count: number;
  project_count: number;
  final_publish_ready_count: number;
  latest_publication_id?: string | null;
  latest_run_id?: string | null;
  filters: AutoResearchDeploymentFilters;
  publications: AutoResearchDeploymentPublication[];
};

export type AutoResearchDeploymentList = {
  deployment_count: number;
  publication_count: number;
  deployments: AutoResearchDeploymentSummary[];
};

export type AutoResearchPublishExportRequest = {
  deployment_id?: string | null;
  deployment_label?: string | null;
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
  publication_tier: AutoResearchPublicationTier;
  publication_readiness_score: number;
  completeness_status: "complete" | "incomplete";
  review_path?: string | null;
  benchmark_card_path?: string | null;
  experiment_design_path?: string | null;
  failure_analysis_path?: string | null;
  research_replan_path?: string | null;
  research_protocol_path?: string | null;
  methodology_audit_path?: string | null;
  revision_dossier_path?: string | null;
  publication_evidence_index_path?: string | null;
  artifact_integrity_audit_path?: string | null;
  reviewer_simulation_path?: string | null;
  publication_repair_plan_path?: string | null;
  publication_repair_execution_path?: string | null;
  publication_readiness_path?: string | null;
  contribution_assessment_path?: string | null;
  literature_graph_path?: string | null;
  novelty_validation_path?: string | null;
  manifest_path?: string | null;
  archive_path?: string | null;
  archive_manifest_path?: string | null;
  publication_id?: string | null;
  publication_manifest_path?: string | null;
  code_package_path?: string | null;
  deployment_ids: string[];
  package_fingerprint?: string | null;
  review_round: number;
  review_fingerprint?: string | null;
  archive_status: "missing" | "stale" | "current";
  archive_ready: boolean;
  archive_current: boolean;
  archive_generated_at?: string | null;
  archive_bundle_kind?: "review_bundle" | "final_publish_bundle" | null;
  archive_review_round?: number | null;
  archive_review_fingerprint?: string | null;
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
  publication_id?: string | null;
  publication_manifest_path?: string | null;
  deployment_id?: string | null;
  deployment_label?: string | null;
  bundle_kind: "review_bundle" | "final_publish_bundle";
  review_bundle_ready: boolean;
  final_publish_ready: boolean;
  file_name: string;
  archive_path: string;
  archive_manifest_path?: string | null;
  code_package_path?: string | null;
  code_package_download_path?: string | null;
  package_fingerprint?: string | null;
  review_round: number;
  review_fingerprint?: string | null;
  download_path: string;
  asset_count: number;
  included_asset_count: number;
  omitted_asset_count: number;
  download_ready: boolean;
};

export type AutoResearchOperatorProjectActions = {
  start_run: boolean;
  create_idea_brief: boolean;
  create_run_from_brief: boolean;
  build_meta_analysis: boolean;
  build_system_evaluation: boolean;
};

export type AutoResearchIdeaResourceBudget = {
  budget_label: AutoResearchIdeaBudgetLabel;
  max_rounds: number;
  candidate_execution_limit?: number | null;
  max_literature_queries: number;
  max_experiment_minutes?: number | null;
  allow_gpu: boolean;
};

export type AutoResearchIdeaRequest = {
  idea: string;
  domain?: string | null;
  resource_budget?: AutoResearchIdeaResourceBudget | AutoResearchIdeaBudgetLabel;
  target_tier?: AutoResearchPaperTier;
  allow_web?: boolean;
  allow_experiments?: boolean;
  task_family_hint?: AutoResearchTaskFamily | null;
  benchmark?: Record<string, unknown> | null;
  execution_backend?: Record<string, unknown> | null;
  experiment_bridge?: AutoResearchExperimentBridgeConfig | null;
  queue_priority?: "low" | "normal" | "high";
  execution_profile?: AutoResearchExecutionProfile;
};

export type AutoResearchLiteratureScoutSource =
  | "fixture"
  | "arxiv"
  | "semantic_scholar"
  | "crossref";

export type AutoResearchLiteratureScoutRequest = {
  sources?: AutoResearchLiteratureScoutSource[] | null;
  limit_per_source?: number;
  cache_enabled?: boolean;
  allow_network?: boolean | null;
};

export type AutoResearchIdeaFeasibilityAssessment = {
  score: number;
  level: "low" | "medium" | "high";
  summary: string;
  blockers: string[];
  warnings: string[];
};

export type AutoResearchResearchDirection = {
  direction_id: string;
  title: string;
  research_question: string;
  hypothesis: string;
  task_family: AutoResearchTaskFamily;
  target_task: string;
  candidate_dataset: string;
  primary_metric: string;
  candidate_metrics: string[];
  required_baselines: string[];
  required_ablations: string[];
  method_sketch: string;
  expected_evidence: string[];
  expected_contribution_type: AutoResearchContributionType;
  novelty_risk: "low" | "medium" | "high";
  feasibility_score: number;
  estimated_cost: string;
  publish_potential: AutoResearchPaperTier;
  kill_criteria: string[];
  rationale: string;
  run_topic: string;
};

export type AutoResearchHypothesisBankEntry = {
  hypothesis_id: string;
  direction_id: string;
  rank: number;
  research_question: string;
  hypothesis: string;
  method_sketch: string;
  expected_evidence: string[];
  required_baselines: string[];
  required_ablations: string[];
  required_datasets: string[];
  required_metrics: string[];
  novelty_risk: "low" | "medium" | "high";
  feasibility_score: number;
  evidence_requirements: string[];
  estimated_cost: string;
  publish_potential: AutoResearchPaperTier;
  kill_criteria: string[];
  selection_score: number;
  selector_factors: Record<string, number>;
  selection_reason?: string | null;
  run_topic: string;
};

export type AutoResearchRejectedDirection = {
  hypothesis_id: string;
  direction_id: string;
  rank: number;
  selection_score: number;
  reasons: string[];
};

export type AutoResearchDirectionSelection = {
  selected_hypothesis_id?: string | null;
  selected_direction_id?: string | null;
  selection_score: number;
  selection_reason?: string | null;
  criteria_weights: Record<string, number>;
  rejected_directions: AutoResearchRejectedDirection[];
};

export type AutoResearchLiteratureScoutPaper = {
  paper_id: string;
  title: string;
  source: string;
  authors: string[];
  year?: number | null;
  venue?: string | null;
  abstract?: string | null;
  url?: string | null;
  doi?: string | null;
  arxiv_id?: string | null;
  method?: string | null;
  methods: string[];
  datasets: string[];
  metrics: string[];
  reported_results: string[];
  known_sota?: string | null;
  extraction_level: "metadata" | "abstract" | "full_text";
  full_text_available: boolean;
  full_text_excerpt?: string | null;
  relevance_score: number;
  novelty_risk_signal: "low" | "medium" | "high";
  overlap_score: number;
  shared_terms: string[];
  source_query?: string | null;
  cache_status: "offline" | "fixture" | "cache_hit" | "network";
  evidence: string;
};

export type AutoResearchLiteratureScoutSourceStatus = {
  source: string;
  query_count: number;
  cache_hit_count: number;
  network_request_count: number;
  paper_count: number;
  error_count: number;
  errors: string[];
};

export type AutoResearchGapCandidate = {
  gap_id: string;
  description: string;
  literature_evidence: string[];
  experimentally_testable: boolean;
  validation_target?: string | null;
  recommended_direction_id?: string | null;
  recommended_hypothesis_id?: string | null;
  recommendation: "proceed" | "change_research_question" | "change_experiment_design";
  rationale: string;
};

export type AutoResearchLiteratureScout = {
  scout_id: string;
  project_id: string;
  brief_id: string;
  generated_at: string;
  search_queries: string[];
  similar_papers: AutoResearchLiteratureScoutPaper[];
  source_statuses: AutoResearchLiteratureScoutSourceStatus[];
  source_counts: Record<string, number>;
  cache_hit_count: number;
  network_enabled: boolean;
  connector_errors: string[];
  methods: string[];
  datasets: string[];
  metrics: string[];
  known_sota: string[];
  scout_fingerprint: string;
};

export type AutoResearchGapMiner = {
  miner_id: string;
  project_id: string;
  brief_id: string;
  generated_at: string;
  idea_duplicate_risk: "low" | "medium" | "high";
  idea_is_existing_method_restatement: boolean;
  change_research_question: boolean;
  change_experiment_design: boolean;
  recommended_narrower_gap?: string | null;
  gap_candidates: AutoResearchGapCandidate[];
  warnings: string[];
  blockers: string[];
  miner_fingerprint: string;
};

export type AutoResearchResearchBrief = {
  brief_id: string;
  project_id: string;
  generated_at: string;
  updated_at: string;
  status: "drafted" | "ready_for_selection";
  original_idea: string;
  polished_idea: string;
  domain?: string | null;
  idea_too_generic: boolean;
  specificity_assessment: "too_generic" | "broad_but_actionable" | "scoped";
  scope_narrowing_recommendation: string;
  research_questions: string[];
  candidate_hypotheses: string[];
  expected_contribution_types: AutoResearchContributionType[];
  target_tasks: string[];
  candidate_datasets: string[];
  candidate_metrics: string[];
  candidate_baselines: string[];
  novelty_search_plan: string[];
  feasibility_assessment: AutoResearchIdeaFeasibilityAssessment;
  resource_assumptions: string[];
  kill_criteria: string[];
  publish_potential: AutoResearchPaperTier;
  research_directions: AutoResearchResearchDirection[];
  direction_count: number;
  hypothesis_bank: AutoResearchHypothesisBankEntry[];
  hypothesis_count: number;
  literature_scout?: AutoResearchLiteratureScout | null;
  gap_miner?: AutoResearchGapMiner | null;
  selected_direction_id?: string | null;
  selected_hypothesis_id?: string | null;
  selection_reason?: string | null;
  direction_selection?: AutoResearchDirectionSelection | null;
  next_action: "build_hypothesis_bank" | "select_direction" | "create_run";
  allow_web: boolean;
  allow_experiments: boolean;
  target_tier: AutoResearchPaperTier;
  resource_budget: AutoResearchIdeaResourceBudget;
  brief_fingerprint?: string | null;
  brief_path?: string | null;
};

export type AutoResearchResearchBriefList = {
  items: AutoResearchResearchBrief[];
};

export type AutoResearchHypothesisBank = {
  brief_id: string;
  project_id: string;
  hypothesis_count: number;
  hypotheses: AutoResearchHypothesisBankEntry[];
  selected_hypothesis_id?: string | null;
  direction_selection?: AutoResearchDirectionSelection | null;
};

export type AutoResearchLiteratureScoutResult = {
  brief_id: string;
  project_id: string;
  literature_scout: AutoResearchLiteratureScout;
  gap_miner: AutoResearchGapMiner;
  updated_brief: AutoResearchResearchBrief;
};

export type AutoResearchIdeaRunCreateRequest = {
  hypothesis_id?: string | null;
  max_rounds?: number | null;
  candidate_execution_limit?: number | null;
  queue_priority?: "low" | "normal" | "high" | null;
  execution_profile?: AutoResearchExecutionProfile | null;
};

export type AutoResearchExperimentFactoryJobKind =
  | "baseline"
  | "candidate_method"
  | "ablation"
  | "seed"
  | "sweep";

export type AutoResearchExperimentFactoryJobStatus =
  | "planned"
  | "done"
  | "failed";

export type AutoResearchExperimentFactoryExecutorMode =
  | "toy"
  | "local"
  | "docker"
  | "bridge"
  | "external_import";

export type AutoResearchExperimentFactoryRepairAction =
  | "none"
  | "add_missing_baseline"
  | "add_missing_ablation"
  | "increase_seed_count"
  | "rerun_failed_job";

export type AutoResearchExperimentFactoryRetryPolicy = {
  max_retries: number;
  retry_on: string[];
};

export type AutoResearchExperimentFactoryResourceEstimate = {
  backend: "auto" | "local" | "docker" | "docker_gpu" | "command";
  cpu_seconds: number;
  memory_mb: number;
  gpu_required: boolean;
};

export type AutoResearchExperimentFactoryJob = {
  job_id: string;
  job_kind: AutoResearchExperimentFactoryJobKind;
  command: string;
  config: Record<string, unknown>;
  inputs: string[];
  expected_outputs: string[];
  dependencies: string[];
  retry_policy: AutoResearchExperimentFactoryRetryPolicy;
  resource_estimate: AutoResearchExperimentFactoryResourceEstimate;
  failure_handling: string;
  status: AutoResearchExperimentFactoryJobStatus;
};

export type AutoResearchExperimentFactoryPlan = {
  plan_id: string;
  project_id: string;
  brief_id?: string | null;
  hypothesis_id?: string | null;
  run_id?: string | null;
  generated_at: string;
  execution_backend: Record<string, unknown>;
  selected_direction_id?: string | null;
  selected_hypothesis?: string | null;
  jobs: AutoResearchExperimentFactoryJob[];
  job_count: number;
  baseline_job_count: number;
  candidate_job_count: number;
  ablation_job_count: number;
  seed_job_count: number;
  sweep_job_count: number;
  expected_artifacts: string[];
  bridge_ready: boolean;
  toy_backend_supported: boolean;
  blockers: string[];
  warnings: string[];
  factory_fingerprint: string;
};

export type AutoResearchExperimentFactoryEnvironmentManifest = {
  manifest_id: string;
  generated_at: string;
  executor_mode: AutoResearchExperimentFactoryExecutorMode;
  backend: "auto" | "local" | "docker" | "docker_gpu" | "command";
  docker_image?: string | null;
  gpu_required: boolean;
  runtime: Record<string, unknown>;
  manifest_fingerprint: string;
};

export type AutoResearchExperimentFactoryMaterializedJob = {
  job_id: string;
  job_kind: AutoResearchExperimentFactoryJobKind;
  executor_mode: AutoResearchExperimentFactoryExecutorMode;
  backend: "auto" | "local" | "docker" | "docker_gpu" | "command";
  command: string;
  dependencies: string[];
  expected_outputs: string[];
  output_refs: string[];
  environment_manifest_id: string;
  repair_classification: AutoResearchExperimentFactoryRepairAction;
  status: AutoResearchExperimentFactoryJobStatus;
};

export type AutoResearchExperimentFactoryImportRequest = {
  summary: string;
  primary_metric?: string;
  objective_system?: string;
  objective_score?: number | null;
  baseline_system?: string | null;
  baseline_score?: number | null;
  key_findings?: string[];
  ablation_scores?: Record<string, number>;
  seed_count?: number;
  significance_p_value?: number | null;
  notes?: string | null;
};

export type AutoResearchExperimentFactoryMaterializeRequest = {
  executor_mode: "local" | "docker" | "bridge";
};

export type AutoResearchEvidenceLedgerEntry = {
  evidence_id: string;
  source_job_id?: string | null;
  evidence_kind: "metric" | "baseline" | "ablation" | "seed" | "sweep" | "artifact";
  claim: string;
  artifact_ref: string;
  metric?: string | null;
  value?: number | null;
  support_status: "supported" | "partial" | "missing";
};

export type AutoResearchEvidenceLedger = {
  ledger_id: string;
  project_id: string;
  run_id?: string | null;
  brief_id?: string | null;
  hypothesis_id?: string | null;
  generated_at: string;
  entries: AutoResearchEvidenceLedgerEntry[];
  entry_count: number;
  complete: boolean;
  blockers: string[];
  ledger_fingerprint: string;
};

export type AutoResearchExperimentFactoryRepairPlan = {
  repair_id: string;
  project_id: string;
  run_id?: string | null;
  brief_id?: string | null;
  generated_at: string;
  actions: AutoResearchExperimentFactoryRepairAction[];
  action_reasons: string[];
  rerun_plan?: AutoResearchExperimentFactoryPlan | null;
  complete: boolean;
  repair_fingerprint: string;
};

export type AutoResearchResultArtifact = {
  status: "queued" | "running" | "done" | "failed";
  summary: string;
  key_findings: string[];
  primary_metric: string;
  best_system?: string | null;
  system_results: Array<Record<string, unknown>>;
  aggregate_system_results: Array<Record<string, unknown>>;
  per_seed_results: Array<Record<string, unknown>>;
  sweep_results: Array<Record<string, unknown>>;
  significance_tests: Array<Record<string, unknown>>;
  acceptance_checks: Array<Record<string, unknown>>;
  tables: Array<Record<string, unknown>>;
  logs?: string | null;
  environment: Record<string, unknown>;
  outputs: Record<string, unknown>;
  objective_system?: string | null;
  objective_score?: number | null;
  [key: string]: unknown;
};

export type AutoResearchExperimentFactoryExecution = {
  project_id: string;
  run_id?: string | null;
  brief_id?: string | null;
  hypothesis_id?: string | null;
  generated_at: string;
  execution_plan: AutoResearchExperimentFactoryPlan;
  environment_manifest?: AutoResearchExperimentFactoryEnvironmentManifest | null;
  materialized_jobs: AutoResearchExperimentFactoryMaterializedJob[];
  result_artifact: AutoResearchResultArtifact;
  evidence_ledger: AutoResearchEvidenceLedger;
  repair_plan?: AutoResearchExperimentFactoryRepairPlan | null;
};

export type AutoResearchOperatorConsoleFilters = {
  search?: string | null;
  status?: AutoResearchRunStatus | null;
  publish_status?: "publish_ready" | "revision_required" | "blocked" | null;
  publication_tier?: AutoResearchPublicationTier | null;
  review_risk?: "low" | "medium" | "high" | null;
  novelty_status?:
    | "missing_context"
    | "grounded"
    | "incremental"
    | "weak"
    | null;
  budget_status?: "default" | "constrained" | null;
  queue_priority?: "low" | "normal" | "high" | null;
};

export type AutoResearchOperatorRunActions = {
  resume: boolean;
  retry: boolean;
  cancel: boolean;
  refresh_bridge: boolean;
  import_bridge_result: boolean;
  refresh_review: boolean;
  apply_review_actions: boolean;
  rebuild_paper: boolean;
  export_publish: boolean;
  download_publish: boolean;
  replan_research: boolean;
  update_controls: boolean;
};

export type AutoResearchOperatorRunSummary = {
  run_id: string;
  topic: string;
  status: AutoResearchRunStatus;
  created_at: string;
  updated_at: string;
  task_family?: AutoResearchTaskFamily | null;
  benchmark_name?: string | null;
  selected_candidate_id?: string | null;
  candidate_count: number;
  selected_count: number;
  active_count: number;
  failed_count: number;
  eliminated_count: number;
  latest_job_status?:
    | "queued"
    | "leased"
    | "running"
    | "succeeded"
    | "failed"
    | "canceled"
    | null;
  active_job_id?: string | null;
  cancel_requested: boolean;
  queue_priority: "low" | "normal" | "high";
  budget_status: "default" | "constrained";
  max_rounds: number;
  candidate_execution_limit?: number | null;
  execution_profile: AutoResearchExecutionProfile;
  executed_candidate_count: number;
  recovery_count: number;
  bridge_status?:
    | "inactive"
    | "waiting_result"
    | "result_imported"
    | "completed"
    | "failed"
    | "canceled"
    | null;
  bridge_target_label?: string | null;
  bridge_session_status?:
    | "waiting_result"
    | "result_imported"
    | "completed"
    | "failed"
    | "canceled"
    | null;
  bridge_session_count: number;
  review_round: number;
  open_issue_count: number;
  pending_action_count: number;
  completed_action_count: number;
  publish_status?: "publish_ready" | "revision_required" | "blocked" | null;
  publish_ready: boolean;
  review_bundle_ready: boolean;
  final_publish_ready: boolean;
  publication_tier?: AutoResearchPublicationTier | null;
  publication_readiness_score: number;
  research_protocol_complete: boolean;
  research_protocol_blocker_count: number;
  research_protocol_blockers: string[];
  methodology_audit_score: number;
  methodology_audit_compliant: boolean;
  methodology_audit_blocker_count: number;
  methodology_audit_blockers: string[];
  methodology_audit_checks_passed: number;
  methodology_audit_checks_total: number;
  revision_dossier_complete: boolean;
  revision_dossier_blocker_count: number;
  revision_dossier_required_actions: string[];
  benchmark_card_publication_grade: boolean;
  benchmark_card_provenance_complete: boolean;
  benchmark_card_total_examples: number;
  benchmark_card_blocker_count: number;
  benchmark_card_blockers: string[];
  publication_evidence_index_complete: boolean;
  publication_evidence_index_missing_count: number;
  publication_evidence_index_blockers: string[];
  reviewer_simulation_complete: boolean;
  reviewer_simulation_average_score: number;
  reviewer_simulation_minimum_score: number;
  reviewer_simulation_minimum_decision?: AutoResearchReviewerDecision | null;
  reviewer_simulation_weak_reject_or_worse_count: number;
  reviewer_simulation_publication_blocker_count: number;
  reviewer_simulation_response_plan_action_count: number;
  reviewer_simulation_blockers: string[];
  weakest_reviewer_role?: AutoResearchReviewerRole | null;
  contribution_score: number;
  novelty_duplicate_risk?: AutoResearchNoveltyRiskLevel | null;
  novelty_incremental_risk?: AutoResearchNoveltyRiskLevel | null;
  experiment_design_completeness?: AutoResearchExperimentDesignCompleteness | null;
  next_research_action?: AutoResearchResearchActionRecommendation | null;
  next_research_action_detail?: string | null;
  artifact_integrity_audit_complete: boolean;
  artifact_integrity_audit_blocker_count: number;
  artifact_integrity_audit_warning_count: number;
  artifact_integrity_audit_untraced_asset_count: number;
  artifact_integrity_audit_missing_lineage_target_count: number;
  artifact_integrity_audit_blockers: string[];
  publication_repair_plan_complete: boolean;
  publication_repair_plan_pending_count: number;
  publication_repair_plan_blocked_count: number;
  publication_repair_plan_auto_applicable_count: number;
  publication_repair_plan_next_actions: string[];
  publication_repair_execution_success: boolean;
  publication_repair_execution_attempted_count: number;
  publication_repair_execution_executed_count: number;
  publication_repair_execution_partial_count: number;
  publication_repair_execution_blocked_count: number;
  publication_repair_execution_missing_outputs: string[];
  publication_grade_benchmark: boolean;
  publication_blocker_count: number;
  publication_blockers: string[];
  readiness_checks_passed: number;
  readiness_checks_total: number;
  archive_ready: boolean;
  review_risk?: "low" | "medium" | "high" | null;
  novelty_status?:
    | "missing_context"
    | "grounded"
    | "incremental"
    | "weak"
    | null;
  blocker_count: number;
  final_blocker_count: number;
  revision_count: number;
  revision_actions: string[];
};

export type AutoResearchOperatorRunDetail = {
  run: AutoResearchRun;
  execution: AutoResearchExecution;
  bridge?: AutoResearchExperimentBridge | null;
  registry: AutoResearchRunRegistry;
  registry_views: AutoResearchRunRegistryViews;
  review?: AutoResearchRunReview | null;
  review_loop?: AutoResearchReviewLoop | null;
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
  brief_count: number;
  latest_brief_id?: string | null;
  latest_brief_status?: string | null;
  latest_brief_original_idea?: string | null;
  latest_brief_hypothesis_count: number;
  latest_brief_selected_direction_id?: string | null;
  latest_brief_selected_hypothesis_id?: string | null;
  latest_brief_next_action?: string | null;
  latest_brief_literature_scout_ready: boolean;
  latest_brief_gap_count: number;
  latest_brief_recommended_gap?: string | null;
  filtered_run_count: number;
  latest_run_id?: string | null;
  selected_run_id?: string | null;
  filters: AutoResearchOperatorConsoleFilters;
  actions: AutoResearchOperatorProjectActions;
  queue?: AutoResearchQueueTelemetry | null;
  workers: AutoResearchWorkerState[];
  meta_analysis?: AutoResearchCrossRunMetaAnalysis | null;
  system_evaluation?: AutoResearchSystemEvaluation | null;
  runs: AutoResearchOperatorRunSummary[];
  current_run?: AutoResearchOperatorRunDetail | null;
};

export type AutoResearchMetaAnalysisRunSummary = {
  run_id: string;
  topic: string;
  hypothesis?: string | null;
  method?: string | null;
  dataset?: string | null;
  primary_metric?: string | null;
  objective_score?: number | null;
  seed_count: number;
  significant_result_count: number;
  contribution_score: number;
  novelty_risk: AutoResearchNoveltyRiskLevel;
  publication_tier?: AutoResearchPublicationTier | null;
  final_publish_ready: boolean;
};

export type AutoResearchMetaAnalysisComparison = {
  comparison_id: string;
  axis: AutoResearchMetaAnalysisComparisonAxis;
  label: string;
  run_ids: string[];
  best_run_id?: string | null;
  metric?: string | null;
  score_range: number[];
  stability: AutoResearchConclusionStability;
  rationale: string;
};

export type AutoResearchStableConclusion = {
  conclusion_id: string;
  text: string;
  stability: AutoResearchConclusionStability;
  supporting_run_ids: string[];
  scope: string;
  caveats: string[];
};

export type AutoResearchCrossRunMetaAnalysis = {
  generated_at: string;
  analysis_id: string;
  project_id: string;
  topic_key?: string | null;
  run_count: number;
  comparable_run_count: number;
  publication_ready_run_count: number;
  run_summaries: AutoResearchMetaAnalysisRunSummary[];
  comparisons: AutoResearchMetaAnalysisComparison[];
  stable_conclusions: AutoResearchStableConclusion[];
  project_level_paper_recommended: boolean;
  recommended_run_ids: string[];
  blockers: string[];
  warnings: string[];
  analysis_fingerprint: string;
};

export type AutoResearchProjectPaperDecision =
  | "do_not_write"
  | "technical_report"
  | "workshop_candidate"
  | "conference_candidate";

export type AutoResearchProjectPaperSourceStrategy =
  | "no_paper"
  | "single_run_report"
  | "project_level_paper";

export type AutoResearchProjectConclusionKind =
  | "stable"
  | "conditional"
  | "negative"
  | "failed_hypothesis"
  | "limitation";

export type AutoResearchProjectClaimTraceStatus =
  | "supported"
  | "partial"
  | "unsupported";

export type AutoResearchProjectConclusionEntry = {
  conclusion_id: string;
  kind: AutoResearchProjectConclusionKind;
  text: string;
  supporting_run_ids: string[];
  evidence_refs: string[];
  caveats: string[];
  paper_claim_allowed: boolean;
};

export type AutoResearchProjectConclusionLedger = {
  ledger_id: string;
  project_id: string;
  stable_conclusions: AutoResearchProjectConclusionEntry[];
  conditional_conclusions: AutoResearchProjectConclusionEntry[];
  negative_findings: AutoResearchProjectConclusionEntry[];
  failed_hypotheses: AutoResearchProjectConclusionEntry[];
  limitations: AutoResearchProjectConclusionEntry[];
  conclusion_count: number;
  ledger_fingerprint: string;
};

export type AutoResearchProjectClaimTrace = {
  claim_id: string;
  claim: string;
  source_conclusion_id: string;
  support_status: AutoResearchProjectClaimTraceStatus;
  supporting_run_ids: string[];
  evidence_refs: string[];
  unsupported_reasons: string[];
  strong_claim: boolean;
};

export type AutoResearchProjectPaperOrchestration = {
  generated_at: string;
  orchestrator_id: string;
  project_id: string;
  brief_count: number;
  latest_brief_id?: string | null;
  latest_brief_selected_hypothesis_id?: string | null;
  candidate_run_count: number;
  selected_run_ids: string[];
  selected_run_count: number;
  meta_analysis: AutoResearchCrossRunMetaAnalysis;
  conclusion_ledger: AutoResearchProjectConclusionLedger;
  claim_traces: AutoResearchProjectClaimTrace[];
  core_claim_count: number;
  supported_core_claim_count: number;
  unsupported_core_claim_count: number;
  reviewer_simulation_count: number;
  reviewer_average_score: number;
  should_write_paper: boolean;
  project_level_paper_allowed: boolean;
  paper_decision: AutoResearchProjectPaperDecision;
  paper_tier: AutoResearchPaperTier;
  source_strategy: AutoResearchProjectPaperSourceStrategy;
  project_publish_gate_passed: boolean;
  blockers: string[];
  warnings: string[];
  next_actions: string[];
  orchestration_fingerprint: string;
};

export type AutoResearchSystemEvaluationTask = {
  task_id: string;
  task_kind: AutoResearchEvaluationTaskKind;
  title: string;
  description: string;
  target_capabilities: string[];
  required_artifacts: string[];
  mapped_run_ids: string[];
  score: number;
  blockers: string[];
};

export type AutoResearchSystemEvaluationMetric = {
  metric_id: string;
  label: string;
  score: number;
  numerator: number;
  denominator: number;
  rationale: string;
};

export type AutoResearchEvaluationCaseTrace = {
  idea: string;
  brief_id?: string | null;
  selected_hypothesis_id?: string | null;
  experiment_plan_id?: string | null;
  evidence_ledger_id?: string | null;
  paper_decision: AutoResearchProjectPaperDecision;
  steps_completed: string[];
  direction_count: number;
  hypothesis_count: number;
  experiment_job_count: number;
  evidence_entry_count: number;
  evidence_complete: boolean;
  paper_review_package_ready: boolean;
  blockers: string[];
};

export type AutoResearchEvaluationCase = {
  case_id: string;
  task_kind: AutoResearchEvaluationTaskKind;
  idea: string;
  expected_brief_quality: string;
  expected_novelty_risks: string[];
  expected_experiment_design_requirements: string[];
  expected_failure_replan_behavior: string;
  expected_paper_tier: AutoResearchPaperTier;
  mapped_run_ids: string[];
  trace?: AutoResearchEvaluationCaseTrace | null;
  score: number;
  blockers: string[];
  warnings: string[];
};

export type AutoResearchEvaluationCaseSuite = {
  generated_at: string;
  suite_id: string;
  project_id: string;
  case_count: number;
  completed_case_count: number;
  cases: AutoResearchEvaluationCase[];
  metrics: AutoResearchSystemEvaluationMetric[];
  scholarflow_paper_materials: string[];
  toy_end_to_end_ready: boolean;
  blockers: string[];
  warnings: string[];
  suite_fingerprint: string;
};

export type AutoResearchSystemEvaluation = {
  generated_at: string;
  evaluation_id: string;
  project_id: string;
  task_count: number;
  completed_task_count: number;
  overall_score: number;
  tasks: AutoResearchSystemEvaluationTask[];
  metrics: AutoResearchSystemEvaluationMetric[];
  scholarflow_paper_materials: string[];
  blockers: string[];
  warnings: string[];
  evaluation_fingerprint: string;
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
