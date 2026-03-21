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
  benchmark?: Record<string, unknown> | null;
  execution_backend?: Record<string, unknown> | null;
  auto_search_literature?: boolean;
  auto_fetch_literature?: boolean;
};

export type AutoResearchRun = {
  id: string;
  project_id: string;
  topic: string;
  status: AutoResearchRunStatus;
  error?: string | null;
  created_at: string;
  updated_at: string;
  [key: string]: unknown;
};

export type AutoResearchExecutionJob = {
  id: string;
  project_id: string;
  run_id: string;
  action: AutoResearchJobAction;
  status: "queued" | "leased" | "running" | "succeeded" | "failed" | "canceled";
  detail?: string | null;
  enqueued_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  cancellation_requested_at?: string | null;
  attempt_count: number;
  worker_id?: string | null;
  error?: string | null;
};

export type AutoResearchWorkerState = {
  worker_id?: string | null;
  status: "idle" | "starting" | "running" | "stopping";
  current_job_id?: string | null;
  current_run_id?: string | null;
  heartbeat_at?: string | null;
  processed_jobs: number;
  queue_depth: number;
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
