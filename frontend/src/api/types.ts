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

export type AutoResearchDomainId =
  | "claim_evidence_retrieval"
  | "rag_citation_faithfulness"
  | "lightweight_ml_nlp_benchmark"
  | "unsupported";

export type AutoResearchDomainEvidenceStatus = "blocked" | "limited" | "ready";

export type AutoResearchExperimentExecutionRoute =
  | "deterministic_replay"
  | "local_command"
  | "docker"
  | "external_import"
  | "bridge_import";

export type AutoResearchExperimentExecutionApprovalState =
  | "not_required"
  | "needs_approval"
  | "approved"
  | "rejected";

export type AutoResearchExperimentExecutionJobStatus =
  | "planned"
  | "needs_approval"
  | "blocked"
  | "running"
  | "succeeded"
  | "failed"
  | "imported";

export type AutoResearchExperimentExecutionPlanStatus =
  | "planned"
  | "blocked"
  | "needs_approval"
  | "ready";

export type AutoResearchOperatorAction =
  | "approve"
  | "reject"
  | "retry"
  | "resume"
  | "cancel";

export type AutoResearchOperatorControlState =
  | "not_started"
  | "pending"
  | "running"
  | "blocked"
  | "failed"
  | "canceled"
  | "completed"
  | "needs_approval"
  | "stale";

export type AutoResearchExternalCapabilityState =
  | "disabled"
  | "not_configured"
  | "unavailable"
  | "approval_required"
  | "ready"
  | "blocked_by_policy"
  | "failed_validation";

export type AutoResearchExternalCapabilityId =
  | "network"
  | "literature_connectors"
  | "full_text_extraction"
  | "citation_context_extraction"
  | "benchmark_dataset_ingestion"
  | "local_command_execution"
  | "docker_execution"
  | "bridge_execution"
  | "external_artifact_import"
  | "budget_policy"
  | "approval_policy"
  | "sandbox_policy";

export type AutoResearchEvidenceOrigin =
  | "fixture"
  | "toy"
  | "local_smoke"
  | "deterministic_replay"
  | "stale_cache"
  | "fresh_cache"
  | "imported_real_artifact"
  | "frozen_snapshot"
  | "live_source"
  | "docker_execution"
  | "bridge_execution";

export type AutoResearchCacheFreshness =
  | "fresh"
  | "stale"
  | "unknown"
  | "not_applicable";

export type AutoResearchExperimentExecutionResultStatus =
  | "succeeded"
  | "failed"
  | "blocked"
  | "needs_approval";

export type AutoResearchExperimentExecutionFailureClass =
  | "none"
  | "missing_baseline"
  | "missing_ablation"
  | "insufficient_statistics"
  | "runtime_failure"
  | "missing_output"
  | "bad_json"
  | "bad_metric_schema"
  | "benchmark_mismatch"
  | "environment_mismatch"
  | "budget_approval_required"
  | "unsupported_execution_backend"
  | "external_import_required";

export type AutoResearchExperimentExecutionRepairAction =
  | "none"
  | "execute_now"
  | "requires_approval"
  | "requires_imported_artifact"
  | "requires_benchmark_or_protocol_change"
  | "blocked_by_deterministic_offline_policy"
  | "downgrade_claim"
  | "terminal_blocker";

export type AutoResearchBenchmarkKind =
  | "builtin"
  | "remote_csv"
  | "remote_jsonl"
  | "remote_json"
  | "huggingface_file"
  | "openml_file"
  | "beir_json"
  | "scifact_json";

export type AutoResearchBenchmarkSource = {
  kind?: AutoResearchBenchmarkKind;
  name?: string | null;
  url?: string | null;
  dataset_id?: string | null;
  revision?: string | null;
  license?: string | null;
  file_path?: string | null;
  subset?: string | null;
  task_family_hint?: AutoResearchTaskFamily | null;
  text_field?: string | null;
  label_field?: string | null;
  feature_fields?: string[];
  split_field?: string | null;
  train_split_values?: string[];
  test_split_values?: string[];
  test_ratio?: number;
  limit_rows?: number | null;
  query_field?: string | null;
  candidates_field?: string | null;
  candidate_text_field?: string | null;
  candidate_id_field?: string | null;
  relevant_ids_field?: string | null;
};

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
  benchmark?: AutoResearchBenchmarkSource | null;
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
  sha256?: string | null;
  size_bytes?: number | null;
  required: boolean;
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
  status: "pending" | "running" | "completed" | "failed" | "blocked";
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
  file_count: number;
  missing_files: string[];
  reconstructable: boolean;
  source_package_ready: boolean;
  external_artifact_count: number;
  missing_external_artifacts: string[];
  external_artifacts_complete: boolean;
  artifact_index?: string | null;
  claim_evidence_index?: string | null;
  manuscript_context?: string | null;
  figures_tables_metadata?: string | null;
  source_fingerprints: Record<string, string>;
  manifest_fingerprint?: string | null;
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
  experiment_execution_plan?: AutoResearchExperimentExecutionPlan | null;
  experiment_execution_plan_path?: string | null;
  experiment_execution_result?: AutoResearchExperimentExecutionResult | null;
  experiment_execution_result_path?: string | null;
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

export type AutoResearchReviewLoopAutoApplyRequest = {
  max_rounds?: number;
  expected_review_fingerprint?: string | null;
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
    | "experiment_factory_environment_manifest"
    | "experiment_factory_materialized_jobs"
    | "experiment_execution_plan"
    | "experiment_execution_result"
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
  experiment_execution_plan_json?: AutoResearchRegistryAssetRef | null;
  experiment_execution_result_json?: AutoResearchRegistryAssetRef | null;
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
    | "run_experiment_execution_plan_json"
    | "run_experiment_execution_result_json"
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
  sample_count: number;
  split_count: number;
  supports_claim_verification: boolean;
  verification_label_space: string[];
  label_space: string[];
  input_fields: string[];
  source_kind?: AutoResearchBenchmarkKind | null;
  source_url?: string | null;
  source_dataset_id?: string | null;
  source_revision?: string | null;
  source_license?: string | null;
  source_fingerprint?: string | null;
  source_content_origin?: string | null;
  source_content_note?: string | null;
  source_class?: string | null;
  publication_grade_eligibility: Record<string, unknown>;
  publication_grade_blockers: string[];
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
  | "claim_evidence_vertical_task"
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

export type AutoResearchReviewLoopActionKind =
  | "paper_revision"
  | "experiment_repair"
  | "claim_downgrade"
  | "literature_refresh"
  | "publish_package"
  | "re_review"
  | "manual_review";

export type AutoResearchReviewLoopExecutionRoute =
  | "paper_rebuild"
  | "research_replan"
  | "experiment_rerun"
  | "literature_refresh"
  | "publish_rebuild"
  | "manual_review"
  | "re_review";

export type AutoResearchReviewLoopAction = {
  action_id: string;
  action_kind: AutoResearchReviewLoopActionKind;
  repair_kind?: AutoResearchRepairActionKind | null;
  execution_route: AutoResearchReviewLoopExecutionRoute;
  priority: "high" | "medium" | "low";
  title: string;
  detail: string;
  status: "pending" | "running" | "completed" | "failed" | "blocked";
  first_seen_round: number;
  last_seen_round: number;
  completed_round?: number | null;
  finding_ids: string[];
  issue_ids: string[];
  auto_applicable: boolean;
  expected_output_asset_ids: string[];
  terminal_condition: string;
  requires_rereview: boolean;
  max_auto_rounds: number;
  started_at_step?: number | null;
  completed_at_step?: number | null;
  input_artifact_refs: string[];
  output_artifact_refs: string[];
  failure_classification?: string | null;
  rereview_result?: Record<string, unknown> | null;
  residual_blockers: string[];
};

export type AutoResearchAutonomousRevisionActionKind =
  | "manuscript_text_revision"
  | "claim_downgrade"
  | "claim_removal"
  | "experiment_repair_request"
  | "literature_followup_request"
  | "benchmark_provenance_followup_request"
  | "reproducibility_followup_request"
  | "no_action_with_rationale";

export type AutoResearchAutonomousRevisionActionScope =
  | "manuscript"
  | "claim_evidence_index"
  | "experiment_repair"
  | "literature"
  | "benchmark"
  | "readiness";

export type AutoResearchAutonomousRevisionActionStatus =
  | "pending"
  | "executed"
  | "blocked"
  | "needs_approval"
  | "requires_import"
  | "requires_external_evidence"
  | "terminal_failed"
  | "no_action";

export type AutoResearchRevisionExecutionStatus =
  | "executed"
  | "blocked"
  | "needs_approval"
  | "requires_import"
  | "requires_external_evidence"
  | "terminal_failed"
  | "no_action";

export type AutoResearchReviewerResponseStatus =
  | "resolved"
  | "partially_resolved"
  | "unresolved"
  | "blocked"
  | "no_action";

export type AutoResearchReReviewResolutionStatus =
  | "resolved"
  | "partially_resolved"
  | "unresolved"
  | "regressed"
  | "superseded_by_blocker";

export type AutoResearchAutonomousRevisionAction = {
  action_id: string;
  project_id: string;
  run_id?: string | null;
  review_round: number;
  source_finding_ids: string[];
  source_finding_fingerprint?: string | null;
  action_kind: AutoResearchAutonomousRevisionActionKind;
  scope: AutoResearchAutonomousRevisionActionScope;
  evidence_requirement: string;
  can_execute_now: boolean;
  approval_required: boolean;
  approval_state: string;
  expected_outputs: string[];
  lineage_parent_refs: string[];
  claim_ids: string[];
  artifact_refs: string[];
  terminal_condition: string;
  max_attempts: number;
  attempt_count: number;
  status: AutoResearchAutonomousRevisionActionStatus;
  blockers: string[];
  rationale: string;
  source_review_loop_action_id?: string | null;
};

export type AutoResearchRevisionActionPlan = {
  generated_at: string;
  plan_id: string;
  project_id: string;
  run_id?: string | null;
  review_round: number;
  review_fingerprint?: string | null;
  source_review_findings_path?: string | null;
  action_count: number;
  executable_action_count: number;
  blocked_action_count: number;
  no_action_count: number;
  actions: AutoResearchAutonomousRevisionAction[];
  complete: boolean;
  blockers: string[];
  capability_audit: Record<string, unknown>;
  plan_fingerprint: string;
};

export type AutoResearchRevisionActionExecution = {
  action_id: string;
  status: AutoResearchRevisionExecutionStatus;
  attempt_count: number;
  started_at_step?: number | null;
  completed_at_step?: number | null;
  revised_artifact_refs: string[];
  evidence_refs_used: string[];
  claim_ids_changed: string[];
  blockers: string[];
  detail: string;
};

export type AutoResearchReviewerResponseItem = {
  source_finding_id: string;
  original_finding_summary: string;
  action_id?: string | null;
  action_taken: string;
  revised_artifact_refs: string[];
  evidence_refs_used: string[];
  claim_ids_changed: string[];
  status: AutoResearchReviewerResponseStatus;
  limitation_or_blocker?: string | null;
  final_publish_impact: string;
  no_action_rationale?: string | null;
};

export type AutoResearchReviewerResponseDossier = {
  generated_at: string;
  dossier_id: string;
  project_id: string;
  run_id?: string | null;
  review_round: number;
  review_fingerprint?: string | null;
  item_count: number;
  covered_finding_count: number;
  unresolved_count: number;
  blocked_count: number;
  items: AutoResearchReviewerResponseItem[];
  complete: boolean;
  dossier_fingerprint: string;
};

export type AutoResearchReReviewFinding = {
  source_finding_id: string;
  action_id?: string | null;
  resolution_status: AutoResearchReReviewResolutionStatus;
  revised_artifact_refs: string[];
  evidence_refs_used: string[];
  residual_blockers: string[];
  new_findings: string[];
  rationale: string;
};

export type AutoResearchRevisionRound = {
  generated_at: string;
  round_id: string;
  project_id: string;
  run_id?: string | null;
  review_round: number;
  revision_round: number;
  original_review_fingerprint?: string | null;
  revised_review_fingerprint?: string | null;
  original_manuscript_ref?: string | null;
  original_manuscript_fingerprint?: string | null;
  revised_manuscript_ref?: string | null;
  revised_manuscript_fingerprint?: string | null;
  original_claim_evidence_index_ref?: string | null;
  revised_claim_evidence_index_ref?: string | null;
  action_plan?: AutoResearchRevisionActionPlan | null;
  action_executions: AutoResearchRevisionActionExecution[];
  reviewer_response_dossier?: AutoResearchReviewerResponseDossier | null;
  rereview_findings: AutoResearchReReviewFinding[];
  resolved_count: number;
  partially_resolved_count: number;
  unresolved_count: number;
  regressed_count: number;
  new_finding_count: number;
  pending_action_count: number;
  terminal_status: "ready" | "needs_revision" | "blocked";
  readiness_impact: string;
  unresolved_blockers: string[];
  round_fingerprint: string;
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
  paper_revision_action_count: number;
  experiment_repair_action_count: number;
  claim_downgrade_action_count: number;
  literature_refresh_action_count: number;
  re_review_action_count: number;
  manual_review_action_count: number;
  next_review_required: boolean;
  auto_revision_round_limit: number;
  auto_revision_rounds_remaining: number;
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
  repair_execution?: AutoResearchPublicationRepairExecution | null;
  applied_action_ids: string[];
  queued_rerun_required: boolean;
};

export type AutoResearchReviewLoopAutoApplyStepStatus =
  | "applied"
  | "rerun_required"
  | "repair_incomplete"
  | "blocked"
  | "round_limit_reached"
  | "no_pending_actions";

export type AutoResearchReviewLoopAutoApplyStep = {
  round_before: number;
  review_fingerprint_before?: string | null;
  status: AutoResearchReviewLoopAutoApplyStepStatus;
  detail: string;
  applied_action_ids: string[];
  repair_execution?: AutoResearchPublicationRepairExecution | null;
  queued_rerun_required: boolean;
};

export type AutoResearchReviewLoopAutoApply = {
  run: AutoResearchRun;
  review: AutoResearchRunReview;
  review_loop: AutoResearchReviewLoop;
  steps: AutoResearchReviewLoopAutoApplyStep[];
  step_count: number;
  applied_action_ids: string[];
  completed: boolean;
  blocked: boolean;
  queued_rerun_required: boolean;
  stop_reason: string;
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
  submission_manifest_path?: string | null;
  submission_manifest_sha256?: string | null;
  reproducibility_checklist_path?: string | null;
  reproducibility_checklist_sha256?: string | null;
  reviewer_response_path?: string | null;
  reviewer_response_sha256?: string | null;
  claim_evidence_index_path?: string | null;
  claim_evidence_index_sha256?: string | null;
  lineage_archive_path?: string | null;
  lineage_archive_sha256?: string | null;
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
  submission_manifest_path?: string | null;
  reproducibility_checklist_path?: string | null;
  reviewer_response_path?: string | null;
  claim_evidence_index_path?: string | null;
  lineage_archive_path?: string | null;
  submission_ready: boolean;
  submission_asset_count: number;
  reproducibility_checklist_complete: boolean;
  reviewer_response_complete: boolean;
  claim_evidence_index_complete: boolean;
  lineage_archive_complete: boolean;
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
  benchmark?: AutoResearchBenchmarkSource | null;
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

export type AutoResearchMemoryItemType =
  | "paper"
  | "method"
  | "dataset"
  | "metric"
  | "benchmark"
  | "reported_result"
  | "implementation"
  | "negative_finding"
  | "blocker"
  | "project_conclusion"
  | "reviewer_finding"
  | "compliance_release_caveat";

export type AutoResearchMemoryEvidenceGrade =
  | "unsupported"
  | "weak"
  | "review_only"
  | "artifact_supported"
  | "publication_candidate";

export type AutoResearchMemorySourceClass =
  | "literature"
  | "experiment"
  | "benchmark"
  | "project"
  | "review"
  | "runbook"
  | "compliance"
  | "release";

export type AutoResearchMemoryExtractionLevel =
  | "metadata"
  | "abstract"
  | "full_text"
  | "artifact"
  | "ledger"
  | "project_summary";

export type AutoResearchMemoryCurrentness =
  | "fresh"
  | "aging"
  | "stale"
  | "unknown"
  | "revoked";

export type AutoResearchMemoryReusePolicy =
  | "discovery_only"
  | "requires_current_project_revalidation"
  | "internal_only"
  | "blocked"
  | "expired";

export type AutoResearchMemoryPrivacyPolicy =
  | "public"
  | "internal"
  | "private"
  | "revoked";

export type AutoResearchMemoryRetentionPolicy =
  | "retain"
  | "expire_on_source_revocation"
  | "delete_after_project"
  | "review_required";

export type AutoResearchMemoryNegativeStatus =
  | "none"
  | "negative_finding"
  | "blocker"
  | "policy_blocked"
  | "revoked";

export type AutoResearchMemorySourceRef = {
  source_project_id: string;
  source_run_id?: string | null;
  source_branch_id?: string | null;
  source_artifact_ref: string;
  source_fingerprint: string;
  source_date_version?: string | null;
};

export type AutoResearchMemoryItem = {
  memory_id: string;
  schema_version: string;
  item_type: AutoResearchMemoryItemType;
  title: string;
  summary: string;
  source: AutoResearchMemorySourceRef;
  extraction_timestamp: string;
  evidence_grade: AutoResearchMemoryEvidenceGrade;
  source_class: AutoResearchMemorySourceClass;
  extraction_level: AutoResearchMemoryExtractionLevel;
  currentness: AutoResearchMemoryCurrentness;
  limitations: string[];
  reuse_policy: AutoResearchMemoryReusePolicy;
  privacy_policy: AutoResearchMemoryPrivacyPolicy;
  retention_policy: AutoResearchMemoryRetentionPolicy;
  negative_status: AutoResearchMemoryNegativeStatus;
  domains: string[];
  methods: string[];
  datasets: string[];
  metrics: string[];
  benchmarks: string[];
  paper_source_ids: string[];
  claim_result_types: string[];
  blocker_failure_types: string[];
  tags: string[];
  text_fingerprint: string;
};

export type AutoResearchMemoryIndex = {
  index_id: string;
  schema_version: string;
  project_id: string;
  rebuilt_at: string;
  item_count: number;
  item_ids: string[];
  domains: Record<string, string[]>;
  methods: Record<string, string[]>;
  datasets: Record<string, string[]>;
  metrics: Record<string, string[]>;
  benchmarks: Record<string, string[]>;
  paper_source_ids: Record<string, string[]>;
  claim_result_types: Record<string, string[]>;
  blocker_failure_types: Record<string, string[]>;
  evidence_grades: Record<string, string[]>;
  currentness: Record<string, string[]>;
  reuse_eligibility: Record<string, string[]>;
  source_projects: Record<string, string[]>;
  store_path?: string | null;
  index_path?: string | null;
  store_fingerprint?: string | null;
  index_fingerprint?: string | null;
};

export type AutoResearchMemoryHint = {
  hint_id: string;
  memory_id: string;
  item_type: AutoResearchMemoryItemType;
  source_project_id: string;
  source_run_id?: string | null;
  source_branch_id?: string | null;
  source_artifact_ref: string;
  source_fingerprint: string;
  title: string;
  summary: string;
  source_refs: string[];
  currentness: AutoResearchMemoryCurrentness;
  limitations: string[];
  reuse_policy: AutoResearchMemoryReusePolicy;
  reuse_requirements: string[];
  required_current_project_validation_actions: string[];
  evidence_grade: AutoResearchMemoryEvidenceGrade;
  source_class: AutoResearchMemorySourceClass;
  extraction_level: AutoResearchMemoryExtractionLevel;
  negative_status: AutoResearchMemoryNegativeStatus;
  relevance_score: number;
  matched_terms: string[];
  memory_hint_only: boolean;
};

export type AutoResearchMemoryQueryRequest = {
  query?: string | null;
  domain?: string | null;
  methods?: string[];
  datasets?: string[];
  metrics?: string[];
  benchmarks?: string[];
  source_project_ids?: string[] | null;
  exclude_project_ids?: string[];
  item_types?: AutoResearchMemoryItemType[] | null;
  include_stale?: boolean;
  include_internal?: boolean;
  include_private?: boolean;
  include_revoked?: boolean;
  limit?: number;
};

export type AutoResearchMemoryQueryResult = {
  query_id: string;
  project_id: string;
  generated_at: string;
  query: AutoResearchMemoryQueryRequest;
  hints: AutoResearchMemoryHint[];
  hint_count: number;
  policy_notes: string[];
  blocked_memory_ids: string[];
  result_fingerprint: string;
};

export type AutoResearchMemoryStore = {
  store_id: string;
  schema_version: string;
  project_id: string;
  rebuilt_at: string;
  items: AutoResearchMemoryItem[];
  item_count: number;
  store_path?: string | null;
  store_fingerprint?: string | null;
};

export type AutoResearchMemoryRebuild = {
  project_id: string;
  rebuilt_at: string;
  store: AutoResearchMemoryStore;
  index: AutoResearchMemoryIndex;
  extracted_count: number;
  deduped_count: number;
  blocked_count: number;
  policy_notes: string[];
};

export type AutoResearchMemoryExport = {
  export_id: string;
  schema_version: string;
  project_id: string;
  exported_at: string;
  items: AutoResearchMemoryItem[];
  item_count: number;
  store_fingerprint?: string | null;
  export_fingerprint: string;
};

export type AutoResearchMemoryImportRequest = {
  items?: AutoResearchMemoryItem[];
  replace?: boolean;
};

export type AutoResearchMemoryImport = {
  project_id: string;
  imported_at: string;
  imported_count: number;
  skipped_count: number;
  store: AutoResearchMemoryStore;
  index: AutoResearchMemoryIndex;
  policy_notes: string[];
};

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

export type AutoResearchDomainDecision = {
  domain_id: AutoResearchDomainId;
  domain_label: string;
  confidence: number;
  matched_signals: string[];
  unsupported_reason?: string | null;
  required_capabilities: string[];
  evidence_policy: string[];
  publish_readiness_policy: string[];
  default_blockers: string[];
  template_id?: string | null;
  template_version?: string | null;
  is_supported: boolean;
};

export type AutoResearchDomainTemplate = {
  domain_id: AutoResearchDomainId;
  domain_label: string;
  template_id: string;
  template_version: string;
  research_brief_template: string;
  literature_query_plan: string[];
  benchmark_resolver_policy: string[];
  method_baseline_ladder: string[];
  metric_schema: string[];
  experiment_factory_protocol: string[];
  evidence_ledger_schema: string[];
  paper_section_requirements: string[];
  publish_readiness_constraints: string[];
  negative_evidence_taxonomy: string[];
  required_package_artifacts: string[];
  task_family: AutoResearchTaskFamily;
  benchmark_name: string;
  template_complete: boolean;
  blockers: string[];
};

export type AutoResearchDomainLiteratureStrategy = {
  strategy_id: string;
  domain_id: AutoResearchDomainId;
  template_id?: string | null;
  template_version?: string | null;
  query_strings: string[];
  required_source_classes: string[];
  minimum_real_source_count: number;
  related_system_coverage_expectations: string[];
  novelty_risk_extraction: string[];
  known_method_extraction: string[];
  known_dataset_extraction: string[];
  known_metric_extraction: string[];
  known_sota_extraction: string[];
  fixture_only_limitation_policy: string;
  final_publish_literature_blockers: string[];
  required_followups: string[];
  kill_criteria: string[];
  strategy_fingerprint: string;
};

export type AutoResearchDomainRelatedSystemCoverage = {
  expectation: string;
  matched_paper_ids: string[];
  matched_terms: string[];
  covered: boolean;
  limitation?: string | null;
};

export type AutoResearchDomainLiteratureResult = {
  result_id: string;
  strategy_id: string;
  domain_id: AutoResearchDomainId;
  status: AutoResearchDomainEvidenceStatus;
  source_counts: Record<string, number>;
  source_class_counts: Record<string, number>;
  real_source_count: number;
  real_source_types: string[];
  required_source_classes: string[];
  required_source_classes_present: string[];
  source_sufficiency_policy: Record<string, unknown>;
  source_sufficiency_ready: boolean;
  fixture_only: boolean;
  related_system_coverage: AutoResearchDomainRelatedSystemCoverage[];
  related_system_coverage_complete: boolean;
  known_methods: string[];
  known_datasets: string[];
  known_metrics: string[];
  known_sota: string[];
  novelty_risks: string[];
  limitations: string[];
  extraction_limitations: string[];
  final_publish_blockers: string[];
  blockers: string[];
  required_followups: string[];
  kill_criteria: string[];
  evidence_refs: string[];
  result_fingerprint: string;
};

export type AutoResearchDomainBenchmarkResolver = {
  resolver_id: string;
  domain_id: AutoResearchDomainId;
  status: AutoResearchDomainEvidenceStatus;
  benchmark_name?: string | null;
  task_family?: AutoResearchTaskFamily | null;
  source_kind?: AutoResearchBenchmarkKind | null;
  source_class?: string | null;
  source_locator?: string | null;
  dataset_id?: string | null;
  revision?: string | null;
  license?: string | null;
  source_fingerprint?: string | null;
  sample_count: number;
  train_split_count: number;
  test_split_count: number;
  label_schema_coverage: Record<string, unknown>;
  query_document_evidence_schema_coverage: Record<string, unknown>;
  source_observation_coverage: Record<string, unknown>;
  benchmark_provenance_complete: boolean;
  publication_grade_eligible: boolean;
  final_candidate_eligible: boolean;
  source_independence_audit: Record<string, unknown>;
  benchmark_payload_ref?: string | null;
  blockers: string[];
  limitations: string[];
  required_followups: string[];
  kill_criteria: string[];
  evidence_refs: string[];
  resolver_fingerprint: string;
};

export type AutoResearchDomainExperimentProtocol = {
  protocol_id: string;
  domain_id: AutoResearchDomainId;
  status: AutoResearchDomainEvidenceStatus;
  method_baseline_ladder: string[];
  metric_schema: string[];
  expected_outputs: string[];
  runtime_contract: Record<string, unknown>;
  deterministic_execution_route: string;
  import_replay_route: string;
  evidence_ledger_schema: string[];
  negative_evidence_categories: string[];
  repair_routing_policy: Record<string, string>;
  readiness_blockers: string[];
  final_publish_limitations: string[];
  benchmark_resolver_id?: string | null;
  benchmark_resolver_status: AutoResearchDomainEvidenceStatus;
  protocol_complete: boolean;
  blockers: string[];
  limitations: string[];
  required_followups: string[];
  kill_criteria: string[];
  evidence_refs: string[];
  protocol_fingerprint: string;
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
  source_id?: string | null;
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
  cache_key?: string | null;
  cache_timestamp?: string | null;
  cache_freshness: AutoResearchCacheFreshness;
  retrieved_at?: string | null;
  connector_provider?: string | null;
  source_observation_fingerprint?: string | null;
  fingerprint?: string | null;
  extraction_status: "limited_metadata" | "metadata_only" | "abstract_only" | "full_text";
  extraction_limitations: string[];
  source_sufficiency_status?: string | null;
  related_system_coverage: string[];
  contradiction_signals: string[];
  claim_ceiling?: string | null;
  evidence: string;
};

export type AutoResearchLiteratureScoutSourceStatus = {
  source: string;
  query_count: number;
  cache_hit_count: number;
  cache_miss_count: number;
  network_request_count: number;
  paper_count: number;
  error_count: number;
  availability_status: "available" | "cache_miss" | "unavailable" | "unsupported" | "error";
  unavailable_reason?: string | null;
  cache_freshness_counts: Record<string, number>;
  stale_cache_count: number;
  freshness_policy?: string | null;
  availability_blockers: string[];
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
  domain_literature_strategy?: AutoResearchDomainLiteratureStrategy | null;
  domain_literature_result?: AutoResearchDomainLiteratureResult | null;
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
  memory_hints: AutoResearchMemoryHint[];
  memory_policy_notes: string[];
  memory_risks: string[];
  memory_required_followups: string[];
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
  memory_risks: string[];
  memory_required_followups: string[];
  miner_fingerprint: string;
};

export type AutoResearchResearchBrief = {
  brief_id: string;
  project_id: string;
  generated_at: string;
  updated_at: string;
  status: "drafted" | "ready_for_selection" | "blocked";
  original_idea: string;
  polished_idea: string;
  domain?: string | null;
  domain_decision?: AutoResearchDomainDecision | null;
  domain_template?: AutoResearchDomainTemplate | null;
  domain_blockers: string[];
  domain_literature_strategy?: AutoResearchDomainLiteratureStrategy | null;
  domain_literature_result?: AutoResearchDomainLiteratureResult | null;
  domain_benchmark_resolver?: AutoResearchDomainBenchmarkResolver | null;
  domain_experiment_protocol?: AutoResearchDomainExperimentProtocol | null;
  domain_readiness_status: AutoResearchDomainEvidenceStatus;
  domain_required_followups: string[];
  domain_kill_criteria: string[];
  domain_claim_ceiling?: string | null;
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
  memory_hints: AutoResearchMemoryHint[];
  memory_policy_notes: string[];
  memory_required_followups: string[];
  memory_validation_actions: string[];
  selected_direction_id?: string | null;
  selected_hypothesis_id?: string | null;
  selection_reason?: string | null;
  direction_selection?: AutoResearchDirectionSelection | null;
  next_action: "build_hypothesis_bank" | "select_direction" | "create_run" | "blocked";
  allow_web: boolean;
  allow_experiments: boolean;
  target_tier: AutoResearchPaperTier;
  resource_budget: AutoResearchIdeaResourceBudget;
  benchmark_source?: AutoResearchBenchmarkSource | null;
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
  domain_decision?: AutoResearchDomainDecision | null;
  domain_benchmark_resolver?: AutoResearchDomainBenchmarkResolver | null;
  domain_experiment_protocol?: AutoResearchDomainExperimentProtocol | null;
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
  runtime_contract: Record<string, unknown>;
  started_at_step: number;
  completed_at_step?: number | null;
  environment_manifest_id: string;
  repair_classification: AutoResearchExperimentFactoryRepairAction;
  failure_classification: string;
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
  failed_job_ids?: string[];
  failed_job_kinds?: AutoResearchExperimentFactoryJobKind[];
  runtime_failure_notes?: string[];
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
  evidence_type?: string | null;
  evidence_origin?: AutoResearchEvidenceOrigin | null;
  metric_values: Record<string, number>;
  sample_counts: Record<string, number>;
  baseline_comparisons: Record<string, unknown>;
  ablation_status?: string | null;
  statistical_sufficiency?: string | null;
  failure_classifications: string[];
  limitations: string[];
  claim_ceiling?: string | null;
  lineage_parent_refs: string[];
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
  domain_benchmark_resolver?: AutoResearchDomainBenchmarkResolver | null;
  domain_experiment_protocol?: AutoResearchDomainExperimentProtocol | null;
  environment_manifest?: AutoResearchExperimentFactoryEnvironmentManifest | null;
  materialized_jobs: AutoResearchExperimentFactoryMaterializedJob[];
  result_artifact: AutoResearchResultArtifact;
  evidence_ledger: AutoResearchEvidenceLedger;
  repair_plan?: AutoResearchExperimentFactoryRepairPlan | null;
};

export type AutoResearchExperimentExecutionBlocker = {
  blocker_id: string;
  scope: string;
  reason: string;
  failure_classification: AutoResearchExperimentExecutionFailureClass;
  required_action: AutoResearchExperimentExecutionRepairAction;
  evidence_refs: string[];
  prevents_execution: boolean;
  terminal: boolean;
};

export type AutoResearchExperimentRuntimeContract = {
  contract_id: string;
  execution_route: AutoResearchExperimentExecutionRoute;
  deterministic: boolean;
  allowed_command: boolean;
  required_inputs: string[];
  expected_outputs: string[];
  metric_schema: string[];
  benchmark_resolver_ref?: string | null;
  domain_id?: AutoResearchDomainId | null;
  timeout_seconds: number;
  requires_live_network: boolean;
  requires_paid_llm: boolean;
  requires_gpu: boolean;
  requires_docker_daemon: boolean;
  environment_requirements: Record<string, unknown>;
  capability_refs: string[];
  blockers: string[];
};

export type AutoResearchExperimentOutputValidation = {
  output_ref: string;
  exists: boolean;
  content_type?: string | null;
  sha256?: string | null;
  schema_version?: string | null;
  metric_names: string[];
  metric_value_types: Record<string, string>;
  sample_counts: Record<string, number>;
  split_counts: Record<string, number>;
  baseline_references: string[];
  ablation_references: string[];
  evidence_origin?: AutoResearchEvidenceOrigin | null;
  validation_status: "passed" | "failed" | "blocked";
  blockers: string[];
};

export type AutoResearchExperimentEnvironmentManifest = {
  manifest_id: string;
  generated_at: string;
  execution_route: AutoResearchExperimentExecutionRoute;
  backend: "auto" | "local" | "docker" | "docker_gpu" | "command";
  command?: string | null;
  cwd?: string | null;
  timeout_seconds: number;
  python_version?: string | null;
  platform?: string | null;
  environment: Record<string, unknown>;
  docker_image_digest?: string | null;
  bridge_target?: string | null;
  bridge_version?: string | null;
  bridge_session_id?: string | null;
  stdout_ref?: string | null;
  stderr_ref?: string | null;
  output_hashes: Record<string, string>;
  requirements_recorded: boolean;
  manifest_fingerprint: string;
};

export type AutoResearchExperimentExecutionJob = {
  job_id: string;
  project_id: string;
  run_id?: string | null;
  brief_id?: string | null;
  domain_id: AutoResearchDomainId;
  protocol_id: string;
  benchmark_resolver_ref?: string | null;
  method_ref?: string | null;
  baseline_ref?: string | null;
  job_kind: AutoResearchExperimentFactoryJobKind;
  execution_route: AutoResearchExperimentExecutionRoute;
  command: string[];
  import_spec?: Record<string, unknown> | null;
  replay_spec?: Record<string, unknown> | null;
  expected_input_artifacts: string[];
  expected_output_artifacts: string[];
  metric_schema: string[];
  runtime_contract: AutoResearchExperimentRuntimeContract;
  environment_requirements: Record<string, unknown>;
  budget_class: "free" | "bounded" | "approval_required";
  approval_required: boolean;
  approval_state: AutoResearchExperimentExecutionApprovalState;
  lineage_parent_refs: string[];
  claim_ceiling?: string | null;
  blockers: AutoResearchExperimentExecutionBlocker[];
  warnings: string[];
  status: AutoResearchExperimentExecutionJobStatus;
};

export type AutoResearchExperimentExecutionPlanRequest = {
  execution_route?: AutoResearchExperimentExecutionRoute | null;
  budget_class?: "free" | "bounded" | "approval_required";
  approval_state?: AutoResearchExperimentExecutionApprovalState;
  docker_available?: boolean;
  bridge_available?: boolean;
};

export type AutoResearchExperimentExecutionPlan = {
  plan_id: string;
  project_id: string;
  run_id?: string | null;
  brief_id?: string | null;
  hypothesis_id?: string | null;
  generated_at: string;
  status: AutoResearchExperimentExecutionPlanStatus;
  domain_id?: AutoResearchDomainId | null;
  protocol_id?: string | null;
  benchmark_resolver_ref?: string | null;
  source_factory_plan_id?: string | null;
  queue_worker_boundary: string;
  jobs: AutoResearchExperimentExecutionJob[];
  job_count: number;
  blockers: AutoResearchExperimentExecutionBlocker[];
  warnings: string[];
  claim_ceiling?: string | null;
  plan_fingerprint: string;
};

export type AutoResearchExperimentExecutionImportRequest = {
  summary?: string;
  artifact_package?: Record<string, unknown>;
  source_package_ref?: string | null;
  schema_version?: string;
  provenance?: Record<string, unknown>;
};

export type AutoResearchExperimentExecutionResult = {
  result_id: string;
  project_id: string;
  run_id?: string | null;
  brief_id?: string | null;
  hypothesis_id?: string | null;
  generated_at: string;
  plan_id: string;
  status: AutoResearchExperimentExecutionResultStatus;
  job_results: AutoResearchExperimentExecutionJob[];
  execution_profile: Record<string, unknown>;
  evidence_origin?: AutoResearchEvidenceOrigin | null;
  environment_manifest?: AutoResearchExperimentEnvironmentManifest | null;
  runtime_contract_results: AutoResearchExperimentRuntimeContract[];
  output_validation: AutoResearchExperimentOutputValidation[];
  failure_classification: AutoResearchExperimentExecutionFailureClass;
  repair_recommendation: AutoResearchExperimentExecutionRepairAction;
  repair_reasons: string[];
  lineage_refs: string[];
  output_artifact_refs: string[];
  output_hashes: Record<string, string>;
  negative_evidence: Record<string, unknown>[];
  result_artifact?: AutoResearchResultArtifact | null;
  evidence_ledger?: AutoResearchEvidenceLedger | null;
  package_manifest_fragment: Record<string, unknown>;
  claim_ceiling?: string | null;
  blockers: AutoResearchExperimentExecutionBlocker[];
  warnings: string[];
  deterministic_fingerprint?: string | null;
  result_fingerprint: string;
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

export type AutoResearchOperatorPolicyError = {
  action: AutoResearchOperatorAction;
  current_state: string;
  reason: string;
  blocker_code: string;
  recoverable: boolean;
  required_next_action?: string | null;
  related_refs: string[];
};

export type AutoResearchOperatorActionPolicy = {
  action: AutoResearchOperatorAction;
  allowed: boolean;
  reason: string;
  blocker_code?: string | null;
  recoverable: boolean;
  required_next_action?: string | null;
  related_refs: string[];
};

export type AutoResearchExternalCapabilityRecord = {
  capability_id: AutoResearchExternalCapabilityId;
  provider?: string | null;
  source?: string | null;
  config_source: string;
  checked_at: string;
  policy_version: string;
  approval_required: boolean;
  budget_class: "free" | "bounded" | "approval_required" | "blocked";
  sandbox_constraints: string[];
  known_blockers: string[];
  related_artifact_refs: string[];
  operator_action_policy?: AutoResearchOperatorActionPolicy | null;
  state: AutoResearchExternalCapabilityState;
};

export type AutoResearchExternalCapabilityManifest = {
  schema_version: string;
  project_id: string;
  generated_at: string;
  policy_version: string;
  records: AutoResearchExternalCapabilityRecord[];
  record_count: number;
  blockers: string[];
  deterministic: boolean;
  manifest_fingerprint: string;
  manifest_path?: string | null;
  unavailable_count: number;
  approval_required_count: number;
  ready_count: number;
};

export type AutoResearchOperatorActionRequest = {
  action: AutoResearchOperatorAction;
  target_id?: string | null;
  approval_id?: string | null;
  operator_id?: string | null;
  reason?: string | null;
  expected_artifact_fingerprints?: Record<string, string>;
};

export type AutoResearchOperatorDecisionEvidence = {
  evidence_id: string;
  action: AutoResearchOperatorAction;
  created_at: string;
  reason: string;
  terminal: boolean;
  blocker_code?: string | null;
  related_refs: string[];
};

export type AutoResearchOperatorActionRecord = {
  action_id: string;
  project_id: string;
  run_id: string;
  action: AutoResearchOperatorAction;
  requested_at: string;
  status: "accepted" | "rejected" | "noop" | "blocked";
  operator_id?: string | null;
  target_id?: string | null;
  reason?: string | null;
  job_id?: string | null;
  attempt_number: number;
  parent_attempt_id?: string | null;
  preserved_artifact_refs: string[];
  failure_evidence_refs: string[];
  negative_evidence_refs: string[];
  terminal_blocker?: AutoResearchOperatorPolicyError | null;
  decision_evidence?: AutoResearchOperatorDecisionEvidence | null;
  related_refs: string[];
};

export type AutoResearchOperatorActionLog = {
  schema_version: string;
  project_id: string;
  run_id: string;
  generated_at: string;
  action_log_path?: string | null;
  action_log_sha256?: string | null;
  records: AutoResearchOperatorActionRecord[];
  record_count: number;
};

export type AutoResearchOperatorStateAuditItem = {
  state_id: string;
  category:
    | "run_queue"
    | "typed_execution_job"
    | "bridge_import"
    | "approval_budget"
    | "repair_revision"
    | "package_final_gate"
    | "artifact_lineage"
    | "evaluation_artifact";
  state_source: "database" | "repository_artifact" | "queue_file" | "derived";
  state_owner: string;
  current_state: string;
  reconstructable_after_restart: boolean;
  allowed_transitions: AutoResearchOperatorAction[];
  known_blockers: string[];
  missing_operator_controls: string[];
  related_artifact_refs: string[];
  source_path?: string | null;
};

export type AutoResearchOperatorStateAudit = {
  schema_version: string;
  project_id: string;
  generated_at: string;
  audit_artifact_path?: string | null;
  audit_artifact_sha256?: string | null;
  deterministic: boolean;
  state_items: AutoResearchOperatorStateAuditItem[];
  state_item_count: number;
  case_coverage: string[];
  blockers: string[];
  conclusion: string;
};

export type AutoResearchOperatorApproval = {
  approval_id: string;
  project_id: string;
  run_id: string;
  job_id?: string | null;
  required: boolean;
  status: "not_required" | "pending" | "approved" | "rejected";
  reason?: string | null;
  blockers: string[];
  related_refs: string[];
  actions: Record<string, AutoResearchOperatorActionPolicy>;
};

export type AutoResearchOperatorBudget = {
  project_id: string;
  run_id: string;
  mode: "default" | "bounded" | "approval_required" | "exhausted";
  queue_priority: "low" | "normal" | "high";
  max_rounds: number;
  candidate_execution_limit?: number | null;
  approval_required: boolean;
  exhausted: boolean;
  blockers: string[];
};

export type AutoResearchOperatorJobStatus = {
  job_id: string;
  project_id: string;
  run_id: string;
  job_source: "execution_queue" | "typed_experiment_execution";
  action?: string | null;
  job_kind?: string | null;
  execution_route?: AutoResearchExperimentExecutionRoute | null;
  status: string;
  approval_state?: AutoResearchExperimentExecutionApprovalState | null;
  budget_class?: string | null;
  detail?: string | null;
  worker_id?: string | null;
  enqueued_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  attempt_count: number;
  recovery_count: number;
  blockers: string[];
  lineage_parent_refs: string[];
  output_artifact_refs: string[];
  negative_evidence_refs: string[];
  policy_actions: Record<string, AutoResearchOperatorActionPolicy>;
};

export type AutoResearchOperatorRepairQueueItem = {
  repair_id: string;
  source:
    | "publication_repair_plan"
    | "review_loop"
    | "typed_execution_result"
    | "operator_decision";
  title: string;
  status: string;
  detail?: string | null;
  blockers: string[];
  required_action?: string | null;
  related_refs: string[];
};

export type AutoResearchOperatorRepairQueue = {
  project_id: string;
  run_id: string;
  item_count: number;
  pending_count: number;
  blocked_count: number;
  failed_execution_count: number;
  items: AutoResearchOperatorRepairQueueItem[];
};

export type AutoResearchOperatorArtifactLineage = {
  project_id: string;
  run_id: string;
  selected_artifact_id?: string | null;
  root_path?: string | null;
  artifact_refs: AutoResearchRegistryAssetRef[];
  lineage_edges: AutoResearchLineageEdge[];
  package_refs: string[];
  final_gate_refs: string[];
  negative_evidence_refs: string[];
  missing_refs: string[];
  stale_refs: string[];
};

export type AutoResearchOperatorPackageStatus = {
  project_id: string;
  run_id: string;
  publish_status?: "publish_ready" | "revision_required" | "blocked" | null;
  publish_ready: boolean;
  review_bundle_ready: boolean;
  final_publish_ready: boolean;
  publication_tier?: AutoResearchPublicationTier | null;
  archive_ready: boolean;
  archive_current: boolean;
  archive_status?: string | null;
  package_fingerprint?: string | null;
  package_path?: string | null;
  final_archive_download_allowed: boolean;
  blockers: string[];
  related_refs: string[];
};

export type AutoResearchOperatorFinalGateStatus = {
  project_id: string;
  run_id: string;
  final_publish_ready: boolean;
  review_bundle_ready: boolean;
  paper_tier?: AutoResearchPaperTier | null;
  policy_version?: string | null;
  final_publish_decision_path?: string | null;
  failed_check_ids: string[];
  blockers: string[];
  required_followups: string[];
  kill_criteria: string[];
  claim_ceiling?: string | null;
  evidence_refs: string[];
  final_archive_download_allowed: boolean;
};

export type AutoResearchLongRunningArtifactStatus =
  | "active"
  | "stale"
  | "superseded"
  | "missing"
  | "migration_needed"
  | "fingerprint_mismatch";

export type AutoResearchLongRunningArtifactState = {
  artifact_id: string;
  artifact_kind: string;
  artifact_ref: string;
  owning_service: string;
  status: AutoResearchLongRunningArtifactStatus;
  schema_version?: string | null;
  expected_schema_version?: string | null;
  fingerprint?: string | null;
  expected_fingerprint?: string | null;
  parent_refs: string[];
  supersedes: string[];
  superseded_by?: string | null;
  reconstructable_after_restart: boolean;
  migration_status: string;
  final_gate_relevance: boolean;
  evidence_origin?: AutoResearchEvidenceOrigin | null;
  blockers: string[];
};

export type AutoResearchLongRunningRepairCandidate = {
  repair_id: string;
  artifact_ref: string;
  workflow:
    | "revalidate"
    | "migrate"
    | "rerun"
    | "reimport"
    | "downgrade_claim"
    | "terminal_blocker";
  reason: string;
  required_action: string;
  status: "pending" | "blocked" | "completed";
  blockers: string[];
  related_refs: string[];
};

export type AutoResearchLongRunningMigrationRecord = {
  migration_id: string;
  artifact_ref: string;
  source_schema_version?: string | null;
  target_schema_version: string;
  supported: boolean;
  status: string;
  hash_before?: string | null;
  hash_after?: string | null;
  migration_artifact_refs: string[];
  policy_version: string;
  operator_visible: boolean;
  reviewer_visible: boolean;
  blockers: string[];
};

export type AutoResearchProjectStateManifest = {
  manifest_id: string;
  schema_version: string;
  project_id: string;
  run_id: string;
  rebuilt_at: string;
  policy_version: string;
  active_artifacts: AutoResearchLongRunningArtifactState[];
  stale_artifacts: AutoResearchLongRunningArtifactState[];
  superseded_artifacts: AutoResearchLongRunningArtifactState[];
  missing_artifacts: AutoResearchLongRunningArtifactState[];
  migration_needed_artifacts: AutoResearchLongRunningArtifactState[];
  unsafe_resume_blockers: string[];
  current_final_gate_state?: AutoResearchOperatorFinalGateStatus | null;
  current_package_state?: AutoResearchOperatorPackageStatus | null;
  repair_candidates: AutoResearchLongRunningRepairCandidate[];
  migration_records: AutoResearchLongRunningMigrationRecord[];
  manifest_path?: string | null;
  manifest_fingerprint?: string | null;
};

export type AutoResearchProjectTimelineEvent = {
  event_id: string;
  event_type: string;
  timestamp: string;
  actor: string;
  source: string;
  artifact_refs: string[];
  parent_event_refs: string[];
  policy_version: string;
  summary: string;
  status: string;
  blockers: string[];
  risks: string[];
};

export type AutoResearchProjectTimeline = {
  timeline_id: string;
  schema_version: string;
  project_id: string;
  run_id: string;
  rebuilt_at: string;
  policy_version: string;
  events: AutoResearchProjectTimelineEvent[];
  event_count: number;
  timeline_path?: string | null;
  timeline_fingerprint?: string | null;
};

export type AutoResearchProjectRunbook = {
  runbook_id: string;
  schema_version: string;
  project_id: string;
  run_id: string;
  rebuilt_at: string;
  policy_version: string;
  next_actions: string[];
  required_approvals: string[];
  blocked_actions: string[];
  repair_candidates: AutoResearchLongRunningRepairCandidate[];
  claim_ceiling?: string | null;
  package_status?: AutoResearchOperatorPackageStatus | null;
  final_gate_status?: AutoResearchOperatorFinalGateStatus | null;
  kill_criteria: string[];
  stale_artifacts: string[];
  migration_needed_artifacts: string[];
  owner_refs: string[];
  source_refs: string[];
  memory_hints: AutoResearchMemoryHint[];
  memory_policy_notes: string[];
  memory_risks: string[];
  memory_required_followups: string[];
  blockers: string[];
  runbook_path?: string | null;
  runbook_fingerprint?: string | null;
};

export type AutoResearchLongRunningAttemptRecord = {
  attempt_id: string;
  parent_attempt_id?: string | null;
  branch_id?: string | null;
  action: string;
  job_id?: string | null;
  trigger: string;
  decision?: string | null;
  approval_state?: "not_required" | "pending" | "approved" | "rejected" | null;
  budget_state?: "default" | "bounded" | "approval_required" | "exhausted" | null;
  capability_state_snapshot: Record<string, string>;
  inputs: string[];
  outputs: string[];
  failure_classification?: string | null;
  repair_action?: string | null;
  artifact_refs: string[];
  negative_evidence_refs: string[];
  stale_detection: string[];
  status:
    | "queued"
    | "running"
    | "succeeded"
    | "failed"
    | "blocked"
    | "canceled"
    | "rejected"
    | "timeout"
    | "noop";
  terminal: boolean;
  timestamp: string;
  operator_id?: string | null;
  blockers: string[];
};

export type AutoResearchLongRunningAttemptLedger = {
  ledger_id: string;
  schema_version: string;
  project_id: string;
  run_id: string;
  rebuilt_at: string;
  policy_version: string;
  attempts: AutoResearchLongRunningAttemptRecord[];
  attempt_count: number;
  terminal_attempt_count: number;
  negative_evidence_refs: string[];
  ledger_path?: string | null;
  ledger_fingerprint?: string | null;
};

export type AutoResearchProjectBranch = {
  branch_id: string;
  parent_branch_id?: string | null;
  parent_hypothesis_id?: string | null;
  selected_direction_refs: string[];
  inherited_evidence_scope: string[];
  invalidated_evidence: string[];
  branch_specific_artifacts: string[];
  branch_readiness: "active" | "selected" | "blocked" | "superseded";
  claim_ceiling?: string | null;
  final_gate_blockers: string[];
  comparison_summary?: string | null;
};

export type AutoResearchProjectBranchState = {
  branch_state_id: string;
  schema_version: string;
  project_id: string;
  run_id: string;
  rebuilt_at: string;
  policy_version: string;
  selected_branch_id: string;
  branches: AutoResearchProjectBranch[];
  comparison: Record<string, unknown>[];
  branch_state_path?: string | null;
  branch_state_fingerprint?: string | null;
};

export type AutoResearchOperatorRunStatus = {
  project_id: string;
  run_id: string;
  run_status: AutoResearchRunStatus;
  control_state: AutoResearchOperatorControlState;
  persisted_reconstructable: boolean;
  current_attempt: number;
  blockers: string[];
  stale_refs: string[];
  missing_refs: string[];
  timeline: Record<string, unknown>[];
  action_policy: Record<string, AutoResearchOperatorActionPolicy>;
  jobs: AutoResearchOperatorJobStatus[];
  approvals: AutoResearchOperatorApproval[];
  budget: AutoResearchOperatorBudget;
  repair_queue: AutoResearchOperatorRepairQueue;
  artifact_lineage: AutoResearchOperatorArtifactLineage;
  package_status: AutoResearchOperatorPackageStatus;
  final_gate_status: AutoResearchOperatorFinalGateStatus;
  external_capability_manifest?: AutoResearchExternalCapabilityManifest | null;
  action_log?: AutoResearchOperatorActionLog | null;
  state_manifest?: AutoResearchProjectStateManifest | null;
  runbook?: AutoResearchProjectRunbook | null;
  timeline_state?: AutoResearchProjectTimeline | null;
  attempt_ledger?: AutoResearchLongRunningAttemptLedger | null;
  branch_state?: AutoResearchProjectBranchState | null;
  audit_artifact_ref?: string | null;
};

export type AutoResearchOperatorActionResult = {
  project_id: string;
  run_id: string;
  action: AutoResearchOperatorAction;
  accepted: boolean;
  status: "accepted" | "rejected" | "noop" | "blocked";
  job_id?: string | null;
  action_record?: AutoResearchOperatorActionRecord | null;
  policy_error?: AutoResearchOperatorPolicyError | null;
  execution?: AutoResearchExecution | null;
  run_status?: AutoResearchOperatorRunStatus | null;
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
  operator_status?: AutoResearchOperatorRunStatus | null;
  state_manifest?: AutoResearchProjectStateManifest | null;
  runbook?: AutoResearchProjectRunbook | null;
  timeline_state?: AutoResearchProjectTimeline | null;
  attempt_ledger?: AutoResearchLongRunningAttemptLedger | null;
  branch_state?: AutoResearchProjectBranchState | null;
};

export type AutoResearchRunControlUpdate = {
  run: AutoResearchRun;
  execution: AutoResearchExecution;
};

export type AutoResearchOperatorPublicationCase = {
  status: "not_started" | "review_ready" | "final_publish_ready" | "blocked";
  domain_decision?: AutoResearchDomainDecision | null;
  domain_template?: AutoResearchDomainTemplate | null;
  domain_literature_strategy?: AutoResearchDomainLiteratureStrategy | null;
  domain_literature_result?: AutoResearchDomainLiteratureResult | null;
  domain_benchmark_resolver?: AutoResearchDomainBenchmarkResolver | null;
  domain_experiment_protocol?: AutoResearchDomainExperimentProtocol | null;
  domain_readiness_status: AutoResearchDomainEvidenceStatus;
  domain_claim_ceiling?: string | null;
  review_bundle_ready: boolean;
  final_publish_ready: boolean;
  submission_bundle_kind?: string | null;
  submission_asset_count: number;
  missing_asset_roles: string[];
  blocked_asset_count: number;
  blocked_asset_roles: string[];
  final_publish_blocking_asset_roles: string[];
  package_asset_statuses: Record<string, unknown>[];
  submission_archive_manifest_path?: string | null;
  submission_archive_path?: string | null;
  submission_archive_complete: boolean;
  submission_archive_current: boolean;
  submission_archive_ready_for_final_download: boolean;
  submission_archive_entry_count: number;
  submission_archive_missing_required_entry_count: number;
  submission_archive_hash_mismatch_entry_count: number;
  submission_archive_stale_entry_count: number;
  reproducibility_checklist_json_path?: string | null;
  reproducibility_checklist_complete: boolean;
  reproducibility_checklist_missing_required_count: number;
  reproducibility_checklist_partial_required_count: number;
  artifact_integrity_audit_path?: string | null;
  artifact_integrity_audit_complete: boolean;
  artifact_integrity_unresolved_issue_count: number;
  final_publish_decision_path?: string | null;
  final_publish_policy_version?: string | null;
  final_publish_failed_check_ids: string[];
  evidence_origin_policy: Record<string, unknown>;
  external_capability_manifest?: AutoResearchExternalCapabilityManifest | null;
  repair_action_status_counts: Record<string, number>;
  repair_action_recommendations: Record<string, string>;
  review_finding_count: number;
  review_findings_path?: string | null;
  execution_source_counts: Record<string, number>;
  imported_replay_run_ids: string[];
  materialized_execution_run_ids: string[];
  literature_source_counts: Record<string, number>;
  real_literature_count: number;
  benchmark_provenance_ready: boolean;
  benchmark_publication_ready: boolean;
  statistics_claim_ceiling?: string | null;
  statistics_complete: boolean;
  negative_evidence_count: number;
  negative_evidence_blocking_count: number;
  phase6_negative_evidence_categories: string[];
  phase6_negative_evidence_missing_categories: string[];
  phase6_negative_evidence_required_categories: string[];
  phase6_negative_evidence_coverage_complete: boolean;
  phase6_negative_evidence_runtime_failure_observed: boolean;
  final_publish_package_artifacts_complete: boolean;
  final_publish_engineering_gap_count: number;
  final_publish_scientific_evidence_gap_count: number;
  final_publish_engineering_gaps: Record<string, unknown>[];
  final_publish_scientific_evidence_gaps: Record<string, unknown>[];
  final_publish_blocker_classification: Record<string, unknown>[];
  final_publish_phase1_blocked_requirement_ids: string[];
  benchmark_schema_coverage_complete: boolean;
  benchmark_schema_coverage_blockers: string[];
  benchmark_source_observation_coverage_complete: boolean;
  benchmark_source_observation_blockers: string[];
  benchmark_final_publish_candidate_coverage_complete: boolean;
  benchmark_final_publish_candidate_blockers: string[];
  benchmark_source_independence_ready: boolean;
  benchmark_source_independence_blockers: string[];
  benchmark_snapshot_artifact_materialized: boolean;
  benchmark_snapshot_artifact_record_count: number;
  benchmark_snapshot_artifact_materialized_count: number;
  benchmark_snapshot_artifact_all_required_materialized: boolean;
  benchmark_snapshot_artifact_unmaterialized_run_ids: string[];
  rereview_complete: boolean;
  rereview_recommendations: Record<string, string>;
  publish_blockers: string[];
  required_followups: string[];
  kill_criteria: string[];
  offline_publication_case_path?: string | null;
  offline_publication_audit_path?: string | null;
  submission_manifest_path?: string | null;
  publication_readiness_report_path?: string | null;
  statistics_report_path?: string | null;
  negative_evidence_report_path?: string | null;
};

export type AutoResearchOperatorConsole = {
  project_id: string;
  run_count: number;
  brief_count: number;
  latest_brief_id?: string | null;
  latest_brief_status?: string | null;
  latest_brief_original_idea?: string | null;
  latest_brief_domain_id?: string | null;
  latest_brief_domain_label?: string | null;
  latest_brief_domain_confidence: number;
  latest_brief_domain_supported: boolean;
  latest_brief_domain_blockers: string[];
  latest_brief_domain_literature_status: AutoResearchDomainEvidenceStatus;
  latest_brief_domain_benchmark_status: AutoResearchDomainEvidenceStatus;
  latest_brief_domain_protocol_status: AutoResearchDomainEvidenceStatus;
  latest_brief_domain_claim_ceiling?: string | null;
  latest_brief_domain_required_followups: string[];
  latest_brief_domain_kill_criteria: string[];
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
  publication_case?: AutoResearchOperatorPublicationCase | null;
  operator_audit?: AutoResearchOperatorStateAudit | null;
  external_capability_manifest?: AutoResearchExternalCapabilityManifest | null;
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

export type AutoResearchSubmissionArchiveEntry = {
  logical_id: string;
  archive_path: string;
  source_artifact_ref: string;
  source_path: string;
  sha256?: string | null;
  size_bytes?: number | null;
  content_type: string;
  generated_by?: string | null;
  required_for_final_publish: boolean;
  validation_status: "present" | "missing" | "hash_mismatch" | "stale";
  blockers: string[];
};

export type AutoResearchSubmissionArchiveManifest = {
  manifest_id: string;
  schema_version: string;
  project_id: string;
  generated_at: string;
  bundle_kind: "review_bundle" | "final_publish_bundle";
  archive_path: string;
  archive_sha256?: string | null;
  archive_size_bytes?: number | null;
  source_package_fingerprint?: string | null;
  source_package_manifest_ref?: string | null;
  entry_count: number;
  required_entry_count: number;
  present_required_entry_count: number;
  missing_required_entry_count: number;
  hash_mismatch_entry_count: number;
  stale_entry_count: number;
  complete: boolean;
  current: boolean;
  ready_for_final_download: boolean;
  entries: AutoResearchSubmissionArchiveEntry[];
  blockers: string[];
  warnings: string[];
  manifest_fingerprint: string;
};

export type AutoResearchReproducibilityChecklistItem = {
  item_id: string;
  category: string;
  label: string;
  status: "complete" | "partial" | "missing" | "not_applicable";
  required_for_final_publish: boolean;
  evidence_refs: string[];
  artifact_refs: string[];
  blockers: string[];
  limitations: string[];
  details: Record<string, unknown>;
};

export type AutoResearchReproducibilityChecklist = {
  checklist_id: string;
  schema_version: string;
  project_id: string;
  generated_at: string;
  complete: boolean;
  missing_required_count: number;
  partial_required_count: number;
  external_requirement_blocker_count: number;
  claim_ceiling?: string | null;
  items: AutoResearchReproducibilityChecklistItem[];
  blockers: string[];
  limitations: string[];
  checklist_fingerprint: string;
};

export type AutoResearchProjectArtifactIntegrityAudit = {
  audit_id: string;
  project_id: string;
  generated_at: string;
  complete: boolean;
  archive_current: boolean;
  unresolved_issue_count: number;
  missing_required_artifact_count: number;
  hash_mismatch_count: number;
  stale_entry_count: number;
  issues: Record<string, unknown>[];
  blockers: string[];
  warnings: string[];
  audit_fingerprint: string;
};

export type AutoResearchFinalPublishCheck = {
  check_id: string;
  passed: boolean;
  required_for_final_publish: boolean;
  evidence_refs: string[];
  blockers: string[];
  warnings: string[];
  details: Record<string, unknown>;
};

export type AutoResearchFinalPublishDecision = {
  decision_id: string;
  project_id: string;
  final_publish_ready: boolean;
  paper_tier: AutoResearchPaperTier;
  policy_version: string;
  checked_at: string;
  passed_checks: AutoResearchFinalPublishCheck[];
  failed_checks: AutoResearchFinalPublishCheck[];
  warnings: string[];
  blockers: string[];
  required_followups: string[];
  claim_ceiling?: string | null;
  evidence_refs: string[];
  archive_manifest_ref?: string | null;
  readiness_manifest_ref?: string | null;
  policy_exceptions: Record<string, unknown>[];
  decision_fingerprint: string;
};

export type AutoResearchSubmissionPackage = {
  package_id: string;
  project_id: string;
  generated_at: string;
  bundle_kind: "review_bundle" | "final_publish_bundle";
  review_bundle_ready: boolean;
  final_publish_ready: boolean;
  submission_manifest_path?: string | null;
  archive_manifest_path?: string | null;
  archive_path?: string | null;
  reproducibility_checklist_path?: string | null;
  reproducibility_checklist_json_path?: string | null;
  artifact_integrity_audit_path?: string | null;
  final_publish_decision_path?: string | null;
  archive_manifest?: AutoResearchSubmissionArchiveManifest | null;
  reproducibility_checklist?: AutoResearchReproducibilityChecklist | null;
  artifact_integrity_audit?: AutoResearchProjectArtifactIntegrityAudit | null;
  final_publish_decision?: AutoResearchFinalPublishDecision | null;
  blockers: string[];
  required_followups: string[];
  package_fingerprint: string;
};

export type AutoResearchProjectPaperOrchestration = {
  generated_at: string;
  orchestrator_id: string;
  project_id: string;
  brief_count: number;
  latest_brief_id?: string | null;
  latest_brief_domain_decision?: AutoResearchDomainDecision | null;
  latest_brief_domain_template?: AutoResearchDomainTemplate | null;
  latest_brief_domain_blockers: string[];
  latest_brief_domain_literature_strategy?: AutoResearchDomainLiteratureStrategy | null;
  latest_brief_domain_literature_result?: AutoResearchDomainLiteratureResult | null;
  latest_brief_domain_benchmark_resolver?: AutoResearchDomainBenchmarkResolver | null;
  latest_brief_domain_experiment_protocol?: AutoResearchDomainExperimentProtocol | null;
  latest_brief_domain_readiness_status: AutoResearchDomainEvidenceStatus;
  latest_brief_domain_claim_ceiling?: string | null;
  latest_brief_domain_required_followups: string[];
  latest_brief_domain_kill_criteria: string[];
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
  project_paper_path?: string | null;
  project_paper_markdown?: string | null;
  project_paper_sections: string[];
  project_paper_missing_sections: string[];
  project_paper_ready: boolean;
  project_paper_sources_dir?: string | null;
  project_paper_sources_manifest?: AutoResearchPaperSourcesManifest | null;
  project_paper_sources_manifest_path?: string | null;
  project_manuscript_context_path?: string | null;
  project_manuscript_context_complete: boolean;
  project_manuscript_context_fingerprint?: string | null;
  project_paper_compile_report?: AutoResearchPaperCompileReport | null;
  project_paper_compile_report_path?: string | null;
  project_paper_latex_path?: string | null;
  project_paper_bibliography_path?: string | null;
  project_paper_build_script_path?: string | null;
  project_paper_latex_source?: string | null;
  project_paper_bibliography_bib?: string | null;
  project_paper_revision_actions: AutoResearchReviewLoopAction[];
  project_paper_revision_action_count: number;
  project_paper_revision_pending_action_count: number;
  project_paper_revision_completed_action_count: number;
  project_paper_claim_downgrade_action_count: number;
  project_paper_retrieval_repair_action_count: number;
  project_paper_revision_action_index?: AutoResearchPaperRevisionActionIndex | null;
  project_paper_revision_action_index_path?: string | null;
  project_paper_revision_actions_markdown_path?: string | null;
  project_paper_revised_path?: string | null;
  project_paper_revision_application_path?: string | null;
  project_paper_rereview_report_path?: string | null;
  project_paper_revision_application?: Record<string, unknown> | null;
  project_paper_rereview_report?: Record<string, unknown> | null;
  project_paper_rereview_complete: boolean;
  project_review_findings?: Record<string, unknown> | null;
  project_revision_action_plan?: AutoResearchRevisionActionPlan | null;
  project_revision_action_plan_path?: string | null;
  project_revision_response_dossier?: AutoResearchReviewerResponseDossier | null;
  project_revision_response_dossier_path?: string | null;
  project_revision_round?: AutoResearchRevisionRound | null;
  project_revision_round_path?: string | null;
  project_submission_dir?: string | null;
  project_submission_package?: AutoResearchSubmissionPackage | null;
  project_submission_manifest?: Record<string, unknown> | null;
  project_submission_manifest_path?: string | null;
  project_submission_archive_manifest?: AutoResearchSubmissionArchiveManifest | null;
  project_submission_archive_manifest_path?: string | null;
  project_submission_archive_path?: string | null;
  project_reproducibility_checklist_path?: string | null;
  project_reproducibility_checklist?: AutoResearchReproducibilityChecklist | null;
  project_reproducibility_checklist_json_path?: string | null;
  project_reviewer_response_path?: string | null;
  project_review_findings_path?: string | null;
  project_repair_execution_log_path?: string | null;
  project_claim_evidence_index_path?: string | null;
  project_retrieval_evidence_ledger_path?: string | null;
  project_lineage_archive_path?: string | null;
  project_literature_support_index_path?: string | null;
  project_paper_compiler_evidence_path?: string | null;
  project_publication_evidence_index_path?: string | null;
  project_publication_readiness_report_path?: string | null;
  project_supplemental_artifacts_path?: string | null;
  project_revision_application_path?: string | null;
  project_revision_rereview_path?: string | null;
  project_code_package_path?: string | null;
  project_benchmark_card_path?: string | null;
  project_benchmark_provenance_manifest_path?: string | null;
  project_benchmark_provenance_repair_index_path?: string | null;
  project_statistics_report_path?: string | null;
  project_experiment_repair_index_path?: string | null;
  project_negative_evidence_report_path?: string | null;
  project_limitations_appendix_path?: string | null;
  project_artifact_integrity_audit?: AutoResearchProjectArtifactIntegrityAudit | null;
  project_artifact_integrity_audit_path?: string | null;
  project_final_publish_decision?: AutoResearchFinalPublishDecision | null;
  project_final_publish_decision_path?: string | null;
  project_offline_publication_case_path?: string | null;
  project_offline_publication_audit_path?: string | null;
  project_publication_manifest_path?: string | null;
  project_review_bundle_ready: boolean;
  project_final_publish_ready: boolean;
  project_submission_ready: boolean;
  project_submission_asset_count: number;
  project_submission_blockers: string[];
  project_reviewer_response_complete: boolean;
  project_review_findings_complete: boolean;
  project_repair_execution_log_complete: boolean;
  project_claim_evidence_index_complete: boolean;
  project_retrieval_evidence_ledger_complete: boolean;
  project_lineage_archive_complete: boolean;
  project_literature_support_index_complete: boolean;
  project_paper_compiler_evidence_complete: boolean;
  project_publication_evidence_index_complete: boolean;
  project_publication_readiness_report_complete: boolean;
  project_supplemental_artifacts_complete: boolean;
  project_revision_application_complete: boolean;
  project_revision_rereview_complete: boolean;
  project_code_package_complete: boolean;
  project_benchmark_card_complete: boolean;
  project_benchmark_provenance_manifest_complete: boolean;
  project_benchmark_provenance_repair_index_complete: boolean;
  project_statistics_report_complete: boolean;
  project_experiment_repair_index_complete: boolean;
  project_negative_evidence_report_complete: boolean;
  project_limitations_appendix_complete: boolean;
  project_submission_archive_manifest_complete: boolean;
  project_submission_archive_complete: boolean;
  project_reproducibility_checklist_json_complete: boolean;
  project_artifact_integrity_audit_complete: boolean;
  project_final_publish_decision_complete: boolean;
  project_offline_publication_case_complete: boolean;
  project_offline_publication_audit_complete: boolean;
  project_publication_manifest_complete: boolean;
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

export type AutoResearchEvaluationStageStatus =
  | "succeeded"
  | "blocked"
  | "skipped_by_policy"
  | "failed";

export type AutoResearchSystemClaimSupportStatus =
  | "supported"
  | "partial"
  | "unsupported"
  | "future_work";

export type AutoResearchEvaluationStageTrace = {
  stage_id: string;
  status: AutoResearchEvaluationStageStatus;
  deterministic_order: number;
  input_refs: string[];
  output_refs: string[];
  artifact_refs: string[];
  evidence_refs: string[];
  negative_evidence: Record<string, unknown>[];
  blockers: string[];
  warnings: string[];
  claim_ceiling_impact?: string | null;
  deterministic_labels: string[];
  reproducibility_constraints: string[];
};

export type AutoResearchEvaluationTimelineEvent = {
  event_id: string;
  stage_id: string;
  status: AutoResearchEvaluationStageStatus;
  deterministic_order: number;
  summary: string;
  artifact_refs: string[];
  evidence_refs: string[];
  negative_evidence: Record<string, unknown>[];
  blockers: string[];
  claim_ceiling_impact?: string | null;
  package_ready?: boolean | null;
  final_publish_ready?: boolean | null;
};

export type AutoResearchEvaluationCaseAuditEntry = {
  case_id: string;
  task_kind: AutoResearchEvaluationTaskKind;
  idea: string;
  domain: string;
  expected_path: string;
  covered_stages: string[];
  missing_stages: string[];
  artifact_refs: string[];
  evidence_refs: string[];
  expected_blockers: string[];
  observed_blockers: string[];
  claim_ceiling?: string | null;
  deterministic_labels: string[];
  audit_conclusion: string;
};

export type AutoResearchEvaluationCaseAudit = {
  generated_at: string;
  audit_id: string;
  project_id: string;
  audited_files: string[];
  required_case_classes: string[];
  missing_case_classes: string[];
  entries: AutoResearchEvaluationCaseAuditEntry[];
  audit_artifact_path?: string | null;
  audit_artifact_sha256?: string | null;
  audit_fingerprint: string;
};

export type AutoResearchSystemPaperClaim = {
  claim_id: string;
  claim: string;
  support_status: AutoResearchSystemClaimSupportStatus;
  evidence_refs: string[];
  metric_refs: string[];
  case_ids: string[];
  limitations: string[];
};

export type AutoResearchSystemPaperSection = {
  section_id: string;
  title: string;
  content: string;
  evidence_refs: string[];
  case_ids: string[];
};

export type AutoResearchSystemPaperMaterial = {
  generated_at: string;
  material_id: string;
  project_id: string;
  label: string;
  abstract: string;
  intro: string;
  sections: AutoResearchSystemPaperSection[];
  system_claims: AutoResearchSystemPaperClaim[];
  limitations: string[];
  threats_to_validity: string[];
  reproducibility_appendix: string[];
  aris_fars_comparison: Record<string, unknown>[];
  future_work: string[];
  evidence_refs: string[];
  material_artifact_path?: string | null;
  material_artifact_sha256?: string | null;
  material_fingerprint: string;
};

export type AutoResearchEvaluationCaseTrace = {
  trace_schema_version: string;
  case_id?: string | null;
  trace_artifact_path?: string | null;
  trace_artifact_sha256?: string | null;
  trace_fingerprint?: string | null;
  idea: string;
  brief_id?: string | null;
  domain_decision?: AutoResearchDomainDecision | null;
  domain_template?: AutoResearchDomainTemplate | null;
  domain_blockers: string[];
  domain_literature_strategy?: AutoResearchDomainLiteratureStrategy | null;
  domain_literature_result?: AutoResearchDomainLiteratureResult | null;
  domain_benchmark_resolver?: AutoResearchDomainBenchmarkResolver | null;
  domain_experiment_protocol?: AutoResearchDomainExperimentProtocol | null;
  domain_readiness_status: AutoResearchDomainEvidenceStatus;
  domain_claim_ceiling?: string | null;
  selected_hypothesis_id?: string | null;
  experiment_plan_id?: string | null;
  experiment_execution_plan_id?: string | null;
  experiment_execution_job_count: number;
  experiment_execution_routes: AutoResearchExperimentExecutionRoute[];
  experiment_execution_status?: AutoResearchExperimentExecutionResultStatus | null;
  experiment_execution_budget_class?: string | null;
  experiment_execution_approval_states: AutoResearchExperimentExecutionApprovalState[];
  experiment_execution_output_validation: AutoResearchExperimentOutputValidation[];
  experiment_execution_failure_classification?: AutoResearchExperimentExecutionFailureClass | null;
  experiment_execution_repair_recommendation?: AutoResearchExperimentExecutionRepairAction | null;
  experiment_execution_blockers: string[];
  experiment_execution_claim_ceiling?: string | null;
  experiment_execution_package_manifest_fragment: Record<string, unknown>;
  evidence_ledger_id?: string | null;
  result_artifact_status?: string | null;
  primary_metric?: string | null;
  objective_score?: number | null;
  paper_decision: AutoResearchProjectPaperDecision;
  steps_completed: string[];
  direction_count: number;
  hypothesis_count: number;
  experiment_job_count: number;
  evidence_entry_count: number;
  repair_action_count: number;
  literature_cache_hit_count: number;
  real_literature_count: number;
  literature_source_counts: Record<string, number>;
  literature_source_sufficiency_ready: boolean;
  literature_connector_availability: Record<string, unknown>[];
  literature_extraction_limitations: string[];
  literature_network_enabled: boolean;
  evidence_complete: boolean;
  paper_review_package_ready: boolean;
  project_paper_path?: string | null;
  project_submission_manifest_path?: string | null;
  project_publication_manifest_path?: string | null;
  project_publication_readiness_report_path?: string | null;
  project_experiment_repair_index_path?: string | null;
  project_statistics_report_path?: string | null;
  project_repair_execution_log_path?: string | null;
  project_review_findings_path?: string | null;
  project_retrieval_evidence_ledger_path?: string | null;
  project_negative_evidence_report_path?: string | null;
  project_offline_publication_case_path?: string | null;
  project_offline_publication_audit_path?: string | null;
  project_submission_archive_manifest_path?: string | null;
  project_submission_archive_path?: string | null;
  project_reproducibility_checklist_json_path?: string | null;
  project_artifact_integrity_audit_path?: string | null;
  project_final_publish_decision_path?: string | null;
  project_paper_sources_manifest_path?: string | null;
  project_paper_sources_reconstructable: boolean;
  project_paper_source_package_ready: boolean;
  project_paper_missing_source_files: string[];
  project_paper_missing_external_artifacts: string[];
  project_manuscript_context_path?: string | null;
  project_manuscript_context_complete: boolean;
  project_manuscript_context_fingerprint?: string | null;
  project_review_bundle_ready: boolean;
  project_final_publish_ready: boolean;
  project_revision_action_count: number;
  project_review_finding_count: number;
  project_review_findings_mapped_to_actions: boolean;
  project_revision_action_plan_path?: string | null;
  project_revision_response_dossier_path?: string | null;
  project_revision_round_path?: string | null;
  project_revision_selected_action_ids: string[];
  project_revision_paper_only_action_ids: string[];
  project_revision_blocked_evidence_action_ids: string[];
  project_revision_response_item_count: number;
  project_revision_rereview_resolved_count: number;
  project_revision_rereview_partially_resolved_count: number;
  project_revision_rereview_unresolved_count: number;
  project_revision_rereview_regressed_count: number;
  project_revision_terminal_status: "ready" | "needs_revision" | "blocked";
  project_revision_readiness_impact?: string | null;
  project_submission_blockers: string[];
  project_submission_bundle_kind?: string | null;
  project_submission_asset_roles: string[];
  project_submission_missing_asset_roles: string[];
  project_submission_required_roles_present: boolean;
  project_submission_archive_complete: boolean;
  project_submission_archive_current: boolean;
  project_submission_archive_ready_for_final_download: boolean;
  project_submission_archive_entry_count: number;
  project_submission_archive_missing_required_entry_count: number;
  project_submission_archive_hash_mismatch_entry_count: number;
  project_submission_archive_stale_entry_count: number;
  project_reproducibility_checklist_complete: boolean;
  project_reproducibility_checklist_missing_required_count: number;
  project_reproducibility_checklist_partial_required_count: number;
  project_artifact_integrity_audit_complete: boolean;
  project_artifact_integrity_unresolved_issue_count: number;
  project_final_publish_policy_version?: string | null;
  project_final_publish_failed_check_ids: string[];
  project_experiment_execution_source_counts: Record<string, number>;
  project_imported_replay_run_ids: string[];
  project_materialized_execution_run_ids: string[];
  project_paper_section_coverage_complete: boolean;
  project_paper_present_sections: string[];
  project_paper_missing_sections: string[];
  project_claim_support_complete: boolean;
  project_supported_core_claim_count: number;
  project_partial_or_unsupported_core_claim_count: number;
  project_claim_ceiling?: string | null;
  project_negative_evidence_coverage_complete: boolean;
  project_negative_evidence_count: number;
  project_phase6_negative_evidence_categories: string[];
  project_phase6_negative_evidence_missing_categories: string[];
  project_phase6_negative_evidence_required_categories: string[];
  project_phase6_negative_evidence_category_counts: Record<string, number>;
  project_phase6_negative_evidence_coverage_complete: boolean;
  project_phase6_negative_evidence_runtime_failure_observed: boolean;
  project_final_publish_package_artifacts_complete: boolean;
  project_final_publish_engineering_gap_count: number;
  project_final_publish_scientific_evidence_gap_count: number;
  project_final_publish_engineering_gaps: Record<string, unknown>[];
  project_final_publish_scientific_evidence_gaps: Record<string, unknown>[];
  project_final_publish_blocker_classification: Record<string, unknown>[];
  project_final_publish_phase1_blocked_requirement_ids: string[];
  project_benchmark_schema_coverage_complete: boolean;
  project_benchmark_schema_coverage_blockers: string[];
  project_benchmark_source_observation_coverage_complete: boolean;
  project_benchmark_source_observation_blockers: string[];
  project_benchmark_final_publish_candidate_coverage_complete: boolean;
  project_benchmark_final_publish_candidate_blockers: string[];
  project_benchmark_source_independence_ready: boolean;
  project_benchmark_source_independence_blockers: string[];
  project_benchmark_snapshot_artifact_materialized: boolean;
  project_benchmark_snapshot_artifact_record_count: number;
  project_benchmark_snapshot_artifact_materialized_count: number;
  project_benchmark_snapshot_artifact_all_required_materialized: boolean;
  project_benchmark_snapshot_artifact_unmaterialized_run_ids: string[];
  project_kill_criteria: string[];
  project_required_followups: string[];
  end_to_end_package_ready: boolean;
  stage_timeline: AutoResearchEvaluationStageTrace[];
  readiness_timeline: AutoResearchEvaluationTimelineEvent[];
  failure_timeline: AutoResearchEvaluationTimelineEvent[];
  artifact_refs: string[];
  evidence_refs: string[];
  negative_evidence: Record<string, unknown>[];
  deterministic_labels: string[];
  reproducibility_constraints: string[];
  architecture_materials: string[];
  case_study_materials: string[];
  failure_analysis_materials: string[];
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
  executed_case_count: number;
  completed_case_count: number;
  evaluation_artifact_count: number;
  cases: AutoResearchEvaluationCase[];
  metrics: AutoResearchSystemEvaluationMetric[];
  evaluation_case_audit?: AutoResearchEvaluationCaseAudit | null;
  evaluation_case_audit_path?: string | null;
  trace_artifact_paths: Record<string, string>;
  metrics_artifact_path?: string | null;
  system_paper_material?: AutoResearchSystemPaperMaterial | null;
  system_paper_material_path?: string | null;
  readiness_timeline: AutoResearchEvaluationTimelineEvent[];
  failure_timeline: AutoResearchEvaluationTimelineEvent[];
  scholarflow_paper_materials: string[];
  architecture_materials: string[];
  case_study_materials: string[];
  failure_analysis_materials: string[];
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
  evaluation_suite_artifact_path?: string | null;
  evaluation_case_audit_path?: string | null;
  system_paper_material_path?: string | null;
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
