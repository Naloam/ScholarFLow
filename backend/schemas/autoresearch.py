from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


TaskFamily = Literal["text_classification", "tabular_classification", "ir_reranking", "llm_evaluation"]
AutoResearchLiteratureScoutSource = Literal["fixture", "arxiv", "semantic_scholar", "crossref"]
AutoResearchExecutionProfile = Literal["exploratory", "publication"]
AutoResearchPublicationTier = Literal["exploratory", "review_ready", "publish_candidate", "publish_ready"]
AutoResearchPaperTier = Literal[
    "technical_report",
    "workshop_candidate",
    "conference_candidate",
    "strong_conference_candidate",
]
AutoResearchReadinessCategory = Literal[
    "benchmark",
    "literature",
    "statistics",
    "evidence",
    "reproducibility",
    "paper",
]
BenchmarkKind = Literal[
    "builtin",
    "remote_csv",
    "remote_jsonl",
    "remote_json",
    "huggingface_file",
    "openml_file",
    "beir_json",
]
ExecutionBackendKind = Literal["auto", "local", "docker", "docker_gpu", "command"]
AutoResearchExperimentBridgeMode = Literal["manual_async"]
AutoResearchExperimentBridgeTargetKind = Literal["manual", "external_repo", "gpu_server", "workspace"]
AutoResearchJobAction = Literal["run", "resume", "retry"]
AutoResearchJobStatus = Literal["queued", "leased", "running", "succeeded", "failed", "canceled"]
AutoResearchWorkerStatus = Literal["idle", "starting", "running", "stopping"]
AutoResearchQueuePriority = Literal["low", "normal", "high"]
AutoResearchCommandStatus = Literal["accepted", "noop"]
AutoResearchRunStatus = Literal["queued", "running", "done", "failed", "canceled"]
AutoResearchRegistryAssetKind = Literal["file", "directory"]
AutoResearchManifestSource = Literal["file", "generated_fallback"]
AutoResearchBundleAssetRole = Literal[
    "run_json",
    "program_json",
    "portfolio_json",
    "benchmark_json",
    "run_benchmark_card_json",
    "run_plan_json",
    "run_spec_json",
    "run_artifact_json",
    "run_generated_code",
    "run_paper_markdown",
    "run_narrative_report_markdown",
    "run_claim_evidence_matrix_json",
    "run_experiment_design_json",
    "run_failure_analysis_json",
    "run_research_replan_json",
    "run_research_protocol_json",
    "run_methodology_audit_json",
    "run_publication_readiness_json",
    "run_contribution_assessment_json",
    "run_literature_graph_json",
    "run_novelty_validation_json",
    "run_revision_dossier_json",
    "run_publication_evidence_index_json",
    "run_artifact_integrity_audit_json",
    "run_publication_repair_plan_json",
    "run_publication_repair_execution_json",
    "run_reviewer_simulation_json",
    "run_experiment_factory_plan_json",
    "run_experiment_factory_environment_manifest_json",
    "run_experiment_factory_materialized_jobs_json",
    "run_evidence_ledger_json",
    "run_experiment_factory_repair_plan_json",
    "run_paper_plan_json",
    "run_figure_plan_json",
    "run_paper_revision_history_markdown",
    "run_paper_revision_brief_markdown",
    "run_paper_revision_state_json",
    "run_paper_compile_report_json",
    "run_paper_revision_diff_json",
    "run_paper_revision_action_index_json",
    "run_paper_section_rewrite_index_json",
    "run_paper_sources_dir",
    "run_paper_section_rewrite_packets_dir",
    "run_paper_build_script",
    "run_paper_checkpoint_index_json",
    "run_paper_latex_source",
    "run_paper_bibliography_bib",
    "run_paper_sources_manifest_json",
    "run_paper_compiled_pdf",
    "run_paper_bibliography_output_bbl",
    "workspace",
    "candidate_json",
    "plan_json",
    "spec_json",
    "attempts_json",
    "artifact_json",
    "manifest_json",
    "generated_code",
    "paper_markdown",
]
AutoResearchLineageNodeKind = Literal[
    "run",
    "program",
    "portfolio",
    "candidate",
    "workspace",
    "plan",
    "spec",
    "attempts",
    "artifact",
    "paper",
    "manifest",
    "generated_code",
    "benchmark",
    "benchmark_card",
    "narrative_report",
    "claim_evidence_matrix",
    "experiment_design",
    "failure_analysis",
    "research_replan",
    "research_protocol",
    "methodology_audit",
    "publication_readiness",
    "contribution_assessment",
    "literature_graph",
    "novelty_validation",
    "revision_dossier",
    "publication_evidence_index",
    "artifact_integrity_audit",
    "publication_repair_plan",
    "publication_repair_execution",
    "reviewer_simulation",
    "experiment_factory_plan",
    "experiment_factory_environment_manifest",
    "experiment_factory_materialized_jobs",
    "evidence_ledger",
    "experiment_factory_repair_plan",
    "paper_plan",
    "figure_plan",
    "paper_revision_history",
    "paper_revision_state",
    "paper_compile_report",
    "paper_revision_diff",
    "paper_revision_action_index",
    "paper_section_rewrite_index",
    "paper_revision_brief",
    "paper_sources",
    "paper_section_rewrite_packets",
    "paper_build_script",
    "paper_checkpoint_index",
    "paper_latex",
    "paper_bibliography",
    "paper_sources_manifest",
    "paper_compiled_pdf",
    "paper_bibliography_output",
]
AutoResearchLineageRelation = Literal[
    "owns",
    "selected_candidate",
    "has_asset",
    "materialized_to_run_asset",
    "derived_from",
]
AutoResearchReviewSeverity = Literal["info", "warning", "error"]
AutoResearchReviewCategory = Literal[
    "artifact",
    "benchmark",
    "statistics",
    "citation",
    "context",
    "provenance",
    "publish",
]
AutoResearchReviewStatus = Literal["ready", "needs_revision", "blocked"]
AutoResearchUnsupportedClaimRisk = Literal["low", "medium", "high"]
AutoResearchRevisionPriority = Literal["high", "medium", "low"]
AutoResearchReviewLoopIssueStatus = Literal["open", "resolved"]
AutoResearchReviewLoopActionStatus = Literal["pending", "completed"]
AutoResearchRevisionDossierItemStatus = Literal["resolved", "action_required", "blocked"]
AutoResearchPublishStatus = Literal["publish_ready", "revision_required", "blocked"]
AutoResearchPublishCompletenessStatus = Literal["complete", "incomplete"]
AutoResearchPublishBundleKind = Literal["review_bundle", "final_publish_bundle"]
AutoResearchPublishArchiveStatus = Literal["missing", "stale", "current"]
AutoResearchBridgeStatus = Literal["inactive", "waiting_result", "result_imported", "completed", "failed", "canceled"]
AutoResearchBridgeSessionStatus = Literal["waiting_result", "result_imported", "completed", "failed", "canceled"]
AutoResearchBridgeCheckpointKind = Literal[
    "session_created",
    "status_polled",
    "result_imported",
    "resume_enqueued",
    "run_completed",
    "run_failed",
    "run_canceled",
]
AutoResearchBridgeNotificationChannel = Literal["console", "file"]
AutoResearchBridgeNotificationStatus = Literal["sent", "failed", "skipped"]
AutoResearchBridgeNotificationEvent = Literal[
    "session_created",
    "result_imported",
    "resume_enqueued",
    "run_completed",
    "run_failed",
    "run_canceled",
]
AutoResearchNoveltyStatus = Literal["missing_context", "grounded", "incremental", "weak"]
AutoResearchLiteratureGraphNodeKind = Literal["paper", "method", "dataset", "metric", "claim"]
AutoResearchLiteratureGraphRelation = Literal[
    "mentions_method",
    "evaluates_dataset",
    "reports_metric",
    "supports_claim",
    "similar_to",
    "identifies_gap",
]
AutoResearchNoveltyRiskLevel = Literal["low", "medium", "high"]
AutoResearchGapValidityStatus = Literal["valid", "weak", "invalid", "missing"]
AutoResearchBudgetStatus = Literal["default", "constrained"]
AutoResearchClaimSupportStatus = Literal["supported", "partial", "unsupported"]
AutoResearchClaimCategory = Literal["problem", "method", "result", "context", "limitation"]
AutoResearchEvidenceSourceKind = Literal["plan", "portfolio", "artifact", "literature", "attempts"]
AutoResearchPaperEvidenceKind = Literal["artifact", "statistic", "literature", "negative"]
AutoResearchExperimentBaselineType = Literal["naive", "strong_conventional", "candidate_method"]
AutoResearchStatisticalTestChoice = Literal["paired_t_test", "bootstrap", "permutation_test"]
AutoResearchExperimentDesignCompleteness = Literal["complete", "partial", "blocked"]
AutoResearchFailureType = Literal[
    "performance_failure",
    "baseline_insufficient",
    "ablation_unsupported_claim",
    "statistical_not_significant",
    "novelty_insufficient",
    "artifact_incomplete",
]
AutoResearchResearchActionKind = Literal[
    "modify_hypothesis",
    "adjust_task_scope",
    "add_baseline",
    "add_ablation",
    "downgrade_contribution_claim",
    "abandon_direction",
    "repair_experiment_design",
    "rerun_plan",
]
AutoResearchContributionType = Literal[
    "new_method",
    "new_system",
    "experimental_finding",
    "new_benchmark",
    "analysis_framework",
]
AutoResearchClaimStrength = Literal[
    "unsupported",
    "weakly_supported",
    "artifact_supported",
    "statistically_supported",
    "literature_positioned",
]
AutoResearchNoveltyRiskSeverity = Literal["low", "medium", "high"]
AutoResearchFigureAssetKind = Literal["table", "chart", "diagram"]
AutoResearchFigureStatus = Literal["planned", "ready", "not_available"]
AutoResearchPaperRevisionStatus = Literal["drafted", "needs_review", "revising", "ready_for_publish"]
AutoResearchPaperRevisionDiffStatus = Literal["initial", "updated", "unchanged"]
AutoResearchPaperRevisionActionMaterializationStatus = Literal["pending", "completed"]
AutoResearchPaperSourceKind = Literal["latex", "bibtex", "json", "markdown", "shell"]
AutoResearchPaperRevisionActionStatus = Literal["open", "done"]
AutoResearchReviewerRole = Literal[
    "novelty_reviewer",
    "methodology_reviewer",
    "reproducibility_reviewer",
    "writing_reviewer",
    "skeptical_reviewer",
]
AutoResearchReviewerDecision = Literal["accept", "weak_accept", "borderline", "weak_reject", "reject"]
AutoResearchReviewerResponseActionKind = Literal["experiment", "evidence", "paper", "research_replan"]
AutoResearchMetaAnalysisComparisonAxis = Literal["topic_hypothesis", "method_dataset", "dataset_method"]
AutoResearchConclusionStability = Literal["stable", "conditional", "unreproducible"]
AutoResearchProjectPaperDecision = Literal[
    "do_not_write",
    "technical_report",
    "workshop_candidate",
    "conference_candidate",
]
AutoResearchProjectPaperSourceStrategy = Literal[
    "no_paper",
    "single_run_report",
    "project_level_paper",
]
AutoResearchProjectConclusionKind = Literal[
    "stable",
    "conditional",
    "negative",
    "failed_hypothesis",
    "limitation",
]
AutoResearchProjectClaimTraceStatus = Literal["supported", "partial", "unsupported"]
AutoResearchEvaluationTaskKind = Literal[
    "toy_task",
    "medium_benchmark_task",
    "literature_heavy_task",
    "claim_evidence_vertical_task",
    "ablation_heavy_task",
    "failed_hypothesis_task",
]
AutoResearchResearchActionRecommendation = Literal[
    "refresh_review",
    "repair_experiment_design",
    "rerun_experiments",
    "research_replan",
    "rebuild_paper",
    "export_publish",
    "meta_analyze",
    "system_evaluate",
    "wait_for_execution",
]
AutoResearchExperimentFactoryJobKind = Literal["baseline", "candidate_method", "ablation", "seed", "sweep"]
AutoResearchExperimentFactoryJobStatus = Literal["planned", "done", "failed"]
AutoResearchExperimentFactoryExecutorMode = Literal["toy", "local", "docker", "bridge", "external_import"]
AutoResearchExperimentFactoryRepairAction = Literal[
    "none",
    "add_missing_baseline",
    "add_missing_ablation",
    "increase_seed_count",
    "rerun_failed_job",
]
HypothesisCandidateStatus = Literal["planned", "selected", "running", "done", "failed", "deferred"]
PortfolioStatus = Literal["planned", "running", "done", "failed"]
PortfolioDecisionOutcome = Literal[
    "pending",
    "running",
    "leading",
    "promoted",
    "eliminated",
    "failed",
]
AcceptanceRuleKind = Literal[
    "objective_metric_comparison",
    "seed_coverage",
    "aggregate_metric_reporting",
    "significance_test_reporting",
    "custom",
]
AcceptanceRuleTarget = Literal["objective_system", "best_system"]
AcceptanceComparison = Literal["gt", "gte", "lt", "lte", "eq", "ne"]
AcceptanceStatistic = Literal["mean", "std", "confidence_interval"]
ConfidenceIntervalMethod = Literal["student_t_95"]
SweepStatus = Literal["done", "partial", "failed"]
FailureCategory = Literal[
    "code_failure",
    "environment_failure",
    "data_failure",
    "metric_failure",
    "runtime_contract_failure",
    "unknown_failure",
]
FailureScope = Literal["seed", "sweep"]
NegativeResultScope = Literal["system", "sweep", "comparison"]
SignificanceComparisonScope = Literal["system", "sweep"]
SignificanceAlternative = Literal["greater", "less", "two_sided"]
SignificanceTestMethod = Literal["paired_sign_flip_exact", "paired_sign_flip_monte_carlo"]
MultipleComparisonCorrection = Literal["holm_bonferroni"]


def _rule_slug(text: str, *, fallback: str) -> str:
    slug = "".join(character.lower() if character.isalnum() else "_" for character in text).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or fallback


class ExecutionBackendSpec(BaseModel):
    kind: ExecutionBackendKind = "auto"
    docker_image: str | None = None
    timeout_seconds: int = 300
    gpu_required: bool = False
    command_prefix: list[str] = Field(default_factory=list)


class AutoResearchExperimentBridgeNotificationHook(BaseModel):
    channel: AutoResearchBridgeNotificationChannel = "console"
    target: str | None = None
    events: list[AutoResearchBridgeNotificationEvent] = Field(
        default_factory=lambda: [
            "session_created",
            "result_imported",
            "resume_enqueued",
            "run_completed",
            "run_failed",
            "run_canceled",
        ]
    )


class AutoResearchExperimentBridgeConfig(BaseModel):
    enabled: bool = False
    mode: AutoResearchExperimentBridgeMode = "manual_async"
    target_kind: AutoResearchExperimentBridgeTargetKind = "manual"
    target_label: str = "external-environment"
    auto_resume_on_result: bool = True
    notification_hooks: list[AutoResearchExperimentBridgeNotificationHook] = Field(
        default_factory=lambda: [AutoResearchExperimentBridgeNotificationHook(channel="console")]
    )

    @field_validator("target_label")
    @classmethod
    def validate_target_label(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("target_label must not be empty")
        return cleaned


class BenchmarkSource(BaseModel):
    kind: BenchmarkKind = "builtin"
    name: str | None = None
    url: str | None = None
    dataset_id: str | None = None
    revision: str | None = None
    license: str | None = None
    file_path: str | None = None
    subset: str | None = None
    task_family_hint: TaskFamily | None = None
    text_field: str | None = None
    label_field: str | None = None
    feature_fields: list[str] = Field(default_factory=list)
    split_field: str | None = None
    train_split_values: list[str] = Field(default_factory=lambda: ["train"])
    test_split_values: list[str] = Field(default_factory=lambda: ["test", "validation", "dev"])
    test_ratio: float = 0.3
    limit_rows: int | None = None
    query_field: str | None = None
    candidates_field: str | None = None
    candidate_text_field: str | None = None
    candidate_id_field: str | None = None
    relevant_ids_field: str | None = None


class AutoResearchRunRequest(BaseModel):
    topic: str
    task_family_hint: TaskFamily | None = None
    docker_image: str | None = None
    language: str = "en"
    paper_ids: list[str] | None = None
    max_rounds: int = 3
    candidate_execution_limit: int | None = None
    queue_priority: AutoResearchQueuePriority = "normal"
    benchmark: BenchmarkSource | None = None
    execution_backend: ExecutionBackendSpec | None = None
    experiment_bridge: AutoResearchExperimentBridgeConfig | None = None
    auto_search_literature: bool = False
    auto_fetch_literature: bool = False
    execution_mode: str = "portfolio"  # portfolio | hill_climbing
    hill_climb_time_budget_minutes: int = 10
    hill_climb_max_iterations: int = 30
    execution_profile: AutoResearchExecutionProfile = "exploratory"

    @field_validator("candidate_execution_limit")
    @classmethod
    def validate_candidate_execution_limit(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("candidate_execution_limit must be at least 1")
        return value


class AutoResearchRunConfig(BaseModel):
    task_family_hint: TaskFamily | None = None
    paper_ids: list[str] | None = None
    language: str = "en"
    max_rounds: int = 3
    candidate_execution_limit: int | None = None
    queue_priority: AutoResearchQueuePriority = "normal"
    benchmark: BenchmarkSource | None = None
    execution_backend: ExecutionBackendSpec | None = None
    experiment_bridge: AutoResearchExperimentBridgeConfig | None = None
    auto_search_literature: bool = False
    auto_fetch_literature: bool = False
    docker_image: str | None = None
    execution_mode: str = "portfolio"
    hill_climb_time_budget_minutes: int = 10
    hill_climb_max_iterations: int = 30
    execution_profile: AutoResearchExecutionProfile = "exploratory"

    @field_validator("candidate_execution_limit")
    @classmethod
    def validate_candidate_execution_limit(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("candidate_execution_limit must be at least 1")
        return value

    @classmethod
    def from_request(cls, payload: AutoResearchRunRequest) -> "AutoResearchRunConfig":
        return cls(
            task_family_hint=payload.task_family_hint,
            paper_ids=payload.paper_ids,
            language=payload.language,
            max_rounds=payload.max_rounds,
            candidate_execution_limit=payload.candidate_execution_limit,
            queue_priority=payload.queue_priority,
            benchmark=payload.benchmark,
            execution_backend=payload.execution_backend,
            experiment_bridge=payload.experiment_bridge,
            auto_search_literature=payload.auto_search_literature,
            auto_fetch_literature=payload.auto_fetch_literature,
            docker_image=payload.docker_image,
            execution_mode=payload.execution_mode,
            hill_climb_time_budget_minutes=payload.hill_climb_time_budget_minutes,
            hill_climb_max_iterations=payload.hill_climb_max_iterations,
            execution_profile=payload.execution_profile,
        )


class AutoResearchIdeaResourceBudget(BaseModel):
    budget_label: Literal["toy", "standard", "publication"] = "standard"
    max_rounds: int = 3
    candidate_execution_limit: int | None = None
    max_literature_queries: int = 5
    max_experiment_minutes: int | None = None
    allow_gpu: bool = False

    @field_validator("max_rounds", "max_literature_queries")
    @classmethod
    def validate_positive_budget(cls, value: int) -> int:
        if value < 1:
            raise ValueError("budget value must be at least 1")
        return value

    @field_validator("candidate_execution_limit", "max_experiment_minutes")
    @classmethod
    def validate_optional_positive_budget(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("budget value must be at least 1")
        return value


class AutoResearchIdeaRequest(BaseModel):
    idea: str
    domain: str | None = None
    resource_budget: AutoResearchIdeaResourceBudget = Field(default_factory=AutoResearchIdeaResourceBudget)
    target_tier: AutoResearchPaperTier = "workshop_candidate"
    allow_web: bool = False
    allow_experiments: bool = True
    task_family_hint: TaskFamily | None = None
    benchmark: BenchmarkSource | None = None
    execution_backend: ExecutionBackendSpec | None = None
    experiment_bridge: AutoResearchExperimentBridgeConfig | None = None
    queue_priority: AutoResearchQueuePriority = "normal"
    execution_profile: AutoResearchExecutionProfile = "exploratory"

    @field_validator("resource_budget", mode="before")
    @classmethod
    def normalize_resource_budget(cls, value: Any) -> Any:
        if isinstance(value, str):
            return {"budget_label": value}
        return value

    @field_validator("idea")
    @classmethod
    def validate_idea(cls, value: str) -> str:
        cleaned = " ".join(value.split()).strip()
        if not cleaned:
            raise ValueError("idea must not be empty")
        return cleaned

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split()).strip()
        return cleaned or None


class AutoResearchIdeaFeasibilityAssessmentRead(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    level: Literal["low", "medium", "high"] = "medium"
    summary: str
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AutoResearchResearchDirectionRead(BaseModel):
    direction_id: str
    title: str
    research_question: str
    hypothesis: str
    task_family: TaskFamily
    target_task: str
    candidate_dataset: str
    primary_metric: str
    candidate_metrics: list[str] = Field(default_factory=list)
    required_baselines: list[str] = Field(default_factory=list)
    required_ablations: list[str] = Field(default_factory=list)
    method_sketch: str
    expected_evidence: list[str] = Field(default_factory=list)
    expected_contribution_type: AutoResearchContributionType = "experimental_finding"
    novelty_risk: AutoResearchNoveltyRiskLevel = "medium"
    feasibility_score: float = Field(default=0.5, ge=0.0, le=1.0)
    estimated_cost: str
    publish_potential: AutoResearchPaperTier = "technical_report"
    kill_criteria: list[str] = Field(default_factory=list)
    rationale: str
    run_topic: str


class AutoResearchHypothesisBankEntryRead(BaseModel):
    hypothesis_id: str
    direction_id: str
    rank: int
    research_question: str
    hypothesis: str
    method_sketch: str
    expected_evidence: list[str] = Field(default_factory=list)
    required_baselines: list[str] = Field(default_factory=list)
    required_ablations: list[str] = Field(default_factory=list)
    required_datasets: list[str] = Field(default_factory=list)
    required_metrics: list[str] = Field(default_factory=list)
    novelty_risk: AutoResearchNoveltyRiskLevel = "medium"
    feasibility_score: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_requirements: list[str] = Field(default_factory=list)
    estimated_cost: str
    publish_potential: AutoResearchPaperTier = "technical_report"
    kill_criteria: list[str] = Field(default_factory=list)
    selection_score: float = Field(default=0.0, ge=0.0, le=1.0)
    selector_factors: dict[str, float] = Field(default_factory=dict)
    selection_reason: str | None = None
    run_topic: str


class AutoResearchRejectedDirectionRead(BaseModel):
    hypothesis_id: str
    direction_id: str
    rank: int
    selection_score: float = Field(default=0.0, ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)


class AutoResearchDirectionSelectionRead(BaseModel):
    selected_hypothesis_id: str | None = None
    selected_direction_id: str | None = None
    selection_score: float = Field(default=0.0, ge=0.0, le=1.0)
    selection_reason: str | None = None
    criteria_weights: dict[str, float] = Field(default_factory=dict)
    rejected_directions: list[AutoResearchRejectedDirectionRead] = Field(default_factory=list)


class AutoResearchLiteratureScoutPaperRead(BaseModel):
    paper_id: str
    title: str
    source: str = "offline_project_context"
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    abstract: str | None = None
    url: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    method: str | None = None
    methods: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    reported_results: list[str] = Field(default_factory=list)
    known_sota: str | None = None
    extraction_level: Literal["metadata", "abstract", "full_text"] = "metadata"
    full_text_available: bool = False
    full_text_excerpt: str | None = None
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    novelty_risk_signal: AutoResearchNoveltyRiskLevel = "medium"
    overlap_score: int = 0
    shared_terms: list[str] = Field(default_factory=list)
    source_query: str | None = None
    cache_status: Literal["offline", "fixture", "cache_hit", "network"] = "offline"
    evidence: str


class AutoResearchLiteratureScoutSourceStatusRead(BaseModel):
    source: str
    query_count: int = 0
    cache_hit_count: int = 0
    network_request_count: int = 0
    paper_count: int = 0
    error_count: int = 0
    errors: list[str] = Field(default_factory=list)


class AutoResearchGapCandidateRead(BaseModel):
    gap_id: str
    description: str
    literature_evidence: list[str] = Field(default_factory=list)
    experimentally_testable: bool = False
    validation_target: str | None = None
    recommended_direction_id: str | None = None
    recommended_hypothesis_id: str | None = None
    recommendation: Literal["proceed", "change_research_question", "change_experiment_design"] = "proceed"
    rationale: str


class AutoResearchLiteratureScoutRead(BaseModel):
    scout_id: str = "literature_scout_v1"
    project_id: str
    brief_id: str
    generated_at: datetime
    search_queries: list[str] = Field(default_factory=list)
    similar_papers: list[AutoResearchLiteratureScoutPaperRead] = Field(default_factory=list)
    source_statuses: list[AutoResearchLiteratureScoutSourceStatusRead] = Field(default_factory=list)
    source_counts: dict[str, int] = Field(default_factory=dict)
    cache_hit_count: int = 0
    network_enabled: bool = False
    connector_errors: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    known_sota: list[str] = Field(default_factory=list)
    scout_fingerprint: str


class AutoResearchGapMinerRead(BaseModel):
    miner_id: str = "gap_miner_v1"
    project_id: str
    brief_id: str
    generated_at: datetime
    idea_duplicate_risk: AutoResearchNoveltyRiskLevel = "medium"
    idea_is_existing_method_restatement: bool = False
    change_research_question: bool = False
    change_experiment_design: bool = False
    recommended_narrower_gap: str | None = None
    gap_candidates: list[AutoResearchGapCandidateRead] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    miner_fingerprint: str


class AutoResearchResearchBriefRead(BaseModel):
    brief_id: str
    project_id: str
    generated_at: datetime
    updated_at: datetime
    status: Literal["drafted", "ready_for_selection"] = "ready_for_selection"
    original_idea: str
    polished_idea: str
    domain: str | None = None
    idea_too_generic: bool = False
    specificity_assessment: Literal["too_generic", "broad_but_actionable", "scoped"] = "scoped"
    scope_narrowing_recommendation: str
    research_questions: list[str] = Field(default_factory=list)
    candidate_hypotheses: list[str] = Field(default_factory=list)
    expected_contribution_types: list[AutoResearchContributionType] = Field(default_factory=list)
    target_tasks: list[str] = Field(default_factory=list)
    candidate_datasets: list[str] = Field(default_factory=list)
    candidate_metrics: list[str] = Field(default_factory=list)
    candidate_baselines: list[str] = Field(default_factory=list)
    novelty_search_plan: list[str] = Field(default_factory=list)
    feasibility_assessment: AutoResearchIdeaFeasibilityAssessmentRead
    resource_assumptions: list[str] = Field(default_factory=list)
    kill_criteria: list[str] = Field(default_factory=list)
    publish_potential: AutoResearchPaperTier = "technical_report"
    research_directions: list[AutoResearchResearchDirectionRead] = Field(default_factory=list)
    direction_count: int = 0
    hypothesis_bank: list[AutoResearchHypothesisBankEntryRead] = Field(default_factory=list)
    hypothesis_count: int = 0
    literature_scout: AutoResearchLiteratureScoutRead | None = None
    gap_miner: AutoResearchGapMinerRead | None = None
    selected_direction_id: str | None = None
    selected_hypothesis_id: str | None = None
    selection_reason: str | None = None
    direction_selection: AutoResearchDirectionSelectionRead | None = None
    next_action: Literal["build_hypothesis_bank", "select_direction", "create_run"] = "build_hypothesis_bank"
    allow_web: bool = False
    allow_experiments: bool = True
    target_tier: AutoResearchPaperTier = "workshop_candidate"
    resource_budget: AutoResearchIdeaResourceBudget = Field(default_factory=AutoResearchIdeaResourceBudget)
    brief_fingerprint: str | None = None
    brief_path: str | None = None


class AutoResearchResearchBriefList(BaseModel):
    items: list[AutoResearchResearchBriefRead] = Field(default_factory=list)


class AutoResearchHypothesisBankRead(BaseModel):
    brief_id: str
    project_id: str
    hypothesis_count: int = 0
    hypotheses: list[AutoResearchHypothesisBankEntryRead] = Field(default_factory=list)
    selected_hypothesis_id: str | None = None
    direction_selection: AutoResearchDirectionSelectionRead | None = None


class AutoResearchLiteratureScoutRequest(BaseModel):
    sources: list[AutoResearchLiteratureScoutSource] | None = None
    limit_per_source: int = Field(default=3, ge=1, le=10)
    cache_enabled: bool = True
    allow_network: bool | None = None

    @field_validator("sources")
    @classmethod
    def normalize_sources(
        cls,
        value: list[AutoResearchLiteratureScoutSource] | None,
    ) -> list[AutoResearchLiteratureScoutSource] | None:
        if value is None:
            return None
        deduped: list[AutoResearchLiteratureScoutSource] = []
        seen: set[str] = set()
        for item in value:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped or None


class AutoResearchLiteratureScoutResultRead(BaseModel):
    brief_id: str
    project_id: str
    literature_scout: AutoResearchLiteratureScoutRead
    gap_miner: AutoResearchGapMinerRead
    updated_brief: AutoResearchResearchBriefRead


class AutoResearchIdeaRunCreateRequest(BaseModel):
    hypothesis_id: str | None = None
    max_rounds: int | None = None
    candidate_execution_limit: int | None = None
    queue_priority: AutoResearchQueuePriority | None = None
    execution_profile: AutoResearchExecutionProfile | None = None

    @field_validator("max_rounds")
    @classmethod
    def validate_max_rounds(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("max_rounds must be at least 1")
        return value

    @field_validator("candidate_execution_limit")
    @classmethod
    def validate_candidate_execution_limit(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("candidate_execution_limit must be at least 1")
        return value


class AutoResearchExperimentFactoryRetryPolicyRead(BaseModel):
    max_retries: int = 1
    retry_on: list[str] = Field(default_factory=lambda: ["runtime_contract_failure", "missing_output"])


class AutoResearchExperimentFactoryResourceEstimateRead(BaseModel):
    backend: ExecutionBackendKind = "auto"
    cpu_seconds: int = 30
    memory_mb: int = 512
    gpu_required: bool = False


class AutoResearchExperimentFactoryJobRead(BaseModel):
    job_id: str
    job_kind: AutoResearchExperimentFactoryJobKind
    command: str
    config: dict[str, Any] = Field(default_factory=dict)
    inputs: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    retry_policy: AutoResearchExperimentFactoryRetryPolicyRead = Field(default_factory=AutoResearchExperimentFactoryRetryPolicyRead)
    resource_estimate: AutoResearchExperimentFactoryResourceEstimateRead = Field(default_factory=AutoResearchExperimentFactoryResourceEstimateRead)
    failure_handling: str
    status: AutoResearchExperimentFactoryJobStatus = "planned"


class AutoResearchExperimentFactoryPlanRead(BaseModel):
    plan_id: str = "experiment_factory_v1"
    project_id: str
    brief_id: str | None = None
    hypothesis_id: str | None = None
    run_id: str | None = None
    generated_at: datetime
    execution_backend: ExecutionBackendSpec = Field(default_factory=ExecutionBackendSpec)
    selected_direction_id: str | None = None
    selected_hypothesis: str | None = None
    jobs: list[AutoResearchExperimentFactoryJobRead] = Field(default_factory=list)
    job_count: int = 0
    baseline_job_count: int = 0
    candidate_job_count: int = 0
    ablation_job_count: int = 0
    seed_job_count: int = 0
    sweep_job_count: int = 0
    expected_artifacts: list[str] = Field(default_factory=list)
    bridge_ready: bool = False
    toy_backend_supported: bool = True
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    factory_fingerprint: str


class AutoResearchExperimentFactoryEnvironmentManifestRead(BaseModel):
    manifest_id: str = "experiment_factory_environment_v1"
    generated_at: datetime
    executor_mode: AutoResearchExperimentFactoryExecutorMode = "toy"
    backend: ExecutionBackendKind = "auto"
    docker_image: str | None = None
    gpu_required: bool = False
    runtime: dict[str, Any] = Field(default_factory=dict)
    manifest_fingerprint: str


class AutoResearchExperimentFactoryMaterializedJobRead(BaseModel):
    job_id: str
    job_kind: AutoResearchExperimentFactoryJobKind
    executor_mode: AutoResearchExperimentFactoryExecutorMode = "toy"
    backend: ExecutionBackendKind = "auto"
    command: str
    dependencies: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    output_refs: list[str] = Field(default_factory=list)
    environment_manifest_id: str = "experiment_factory_environment_v1"
    repair_classification: AutoResearchExperimentFactoryRepairAction = "none"
    status: AutoResearchExperimentFactoryJobStatus = "planned"


class AutoResearchExperimentFactoryImportRequest(BaseModel):
    summary: str
    primary_metric: str = "primary_metric"
    objective_system: str = "candidate_method"
    objective_score: float | None = None
    baseline_system: str | None = None
    baseline_score: float | None = None
    key_findings: list[str] = Field(default_factory=list)
    ablation_scores: dict[str, float] = Field(default_factory=dict)
    seed_count: int = Field(default=1, ge=1)
    significance_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    failed_job_ids: list[str] = Field(default_factory=list)
    failed_job_kinds: list[AutoResearchExperimentFactoryJobKind] = Field(default_factory=list)
    runtime_failure_notes: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("failed_job_ids", "runtime_failure_notes")
    @classmethod
    def dedupe_import_failure_text(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for item in value:
            cleaned = " ".join(str(item).split()).strip()
            key = cleaned.lower()
            if not cleaned or key in seen:
                continue
            seen.add(key)
            deduped.append(cleaned)
        return deduped

    @field_validator("failed_job_kinds")
    @classmethod
    def dedupe_failed_job_kinds(
        cls,
        value: list[AutoResearchExperimentFactoryJobKind],
    ) -> list[AutoResearchExperimentFactoryJobKind]:
        deduped: list[AutoResearchExperimentFactoryJobKind] = []
        for item in value:
            if item not in deduped:
                deduped.append(item)
        return deduped


class AutoResearchExperimentFactoryMaterializeRequest(BaseModel):
    executor_mode: AutoResearchExperimentFactoryExecutorMode = "local"

    @field_validator("executor_mode")
    @classmethod
    def validate_executor_mode(
        cls,
        value: AutoResearchExperimentFactoryExecutorMode,
    ) -> AutoResearchExperimentFactoryExecutorMode:
        if value in {"toy", "external_import"}:
            raise ValueError("executor_mode must be local, docker, or bridge for materialization")
        return value


class AutoResearchEvidenceLedgerEntryRead(BaseModel):
    evidence_id: str
    source_job_id: str | None = None
    evidence_kind: Literal["metric", "baseline", "ablation", "seed", "sweep", "artifact"] = "artifact"
    claim: str
    artifact_ref: str
    metric: str | None = None
    value: float | None = None
    support_status: Literal["supported", "partial", "missing"] = "supported"


class AutoResearchEvidenceLedgerRead(BaseModel):
    ledger_id: str = "experiment_evidence_ledger_v1"
    project_id: str
    run_id: str | None = None
    brief_id: str | None = None
    hypothesis_id: str | None = None
    generated_at: datetime
    entries: list[AutoResearchEvidenceLedgerEntryRead] = Field(default_factory=list)
    entry_count: int = 0
    complete: bool = False
    blockers: list[str] = Field(default_factory=list)
    ledger_fingerprint: str


class AutoResearchExperimentFactoryRepairPlanRead(BaseModel):
    repair_id: str = "experiment_factory_repair_v1"
    project_id: str
    run_id: str | None = None
    brief_id: str | None = None
    generated_at: datetime
    actions: list[AutoResearchExperimentFactoryRepairAction] = Field(default_factory=list)
    action_reasons: list[str] = Field(default_factory=list)
    rerun_plan: AutoResearchExperimentFactoryPlanRead | None = None
    complete: bool = False
    repair_fingerprint: str


class AutoResearchExperimentFactoryExecutionRead(BaseModel):
    project_id: str
    run_id: str | None = None
    brief_id: str | None = None
    hypothesis_id: str | None = None
    generated_at: datetime
    execution_plan: AutoResearchExperimentFactoryPlanRead
    environment_manifest: AutoResearchExperimentFactoryEnvironmentManifestRead | None = None
    materialized_jobs: list[AutoResearchExperimentFactoryMaterializedJobRead] = Field(default_factory=list)
    result_artifact: ResultArtifact
    evidence_ledger: AutoResearchEvidenceLedgerRead
    repair_plan: AutoResearchExperimentFactoryRepairPlanRead | None = None


class AutoResearchRunControlPatch(BaseModel):
    max_rounds: int | None = None
    candidate_execution_limit: int | None = None
    queue_priority: AutoResearchQueuePriority | None = None

    @field_validator("max_rounds")
    @classmethod
    def validate_max_rounds(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("max_rounds must be at least 1")
        return value

    @field_validator("candidate_execution_limit")
    @classmethod
    def validate_candidate_execution_limit(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("candidate_execution_limit must be at least 1")
        return value


class DatasetSpec(BaseModel):
    name: str
    description: str
    train_size: int
    test_size: int
    input_fields: list[str] = Field(default_factory=list)
    label_space: list[str] = Field(default_factory=list)
    query_fields: list[str] = Field(default_factory=list)
    candidate_count: int | None = None
    source_kind: BenchmarkKind | None = None
    source_url: str | None = None
    source_dataset_id: str | None = None
    source_revision: str | None = None
    source_license: str | None = None
    source_fingerprint: str | None = None
    publication_grade: bool = False


class SweepConfig(BaseModel):
    label: str
    params: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None


class BaselineSpec(BaseModel):
    name: str
    description: str


class MetricSpec(BaseModel):
    name: str
    goal: str
    description: str


class AblationSpec(BaseModel):
    name: str
    description: str


class ConceptualFramework(BaseModel):
    core_concepts: list[str] = Field(default_factory=list)
    theoretical_basis: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    expected_mechanism: str | None = None


class ResearchPlan(BaseModel):
    topic: str
    title: str
    task_family: TaskFamily
    problem_statement: str
    motivation: str
    proposed_method: str
    research_questions: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    planned_contributions: list[str] = Field(default_factory=list)
    experiment_outline: list[str] = Field(default_factory=list)
    scope_limits: list[str] = Field(default_factory=list)
    conceptual_framework: ConceptualFramework | None = None
    literature_gaps_addressed: list[str] = Field(default_factory=list)
    novelty_statement: str | None = None
    contribution_statements: list[str] = Field(default_factory=list)
    problem_anchor: str | None = None


class AcceptanceRule(BaseModel):
    id: str
    description: str
    kind: AcceptanceRuleKind = "custom"
    metric: str | None = None
    target: AcceptanceRuleTarget | None = None
    baseline_system: str | None = None
    comparison: AcceptanceComparison | None = None
    required_statistics: list[AcceptanceStatistic] = Field(default_factory=list)
    scope: Literal["selected_sweep"] = "selected_sweep"
    comparison_scope: SignificanceComparisonScope | None = None

    @classmethod
    def from_legacy_string(cls, criterion: str, index: int = 0) -> AcceptanceRule:
        text = criterion.strip()
        lowered = text.lower()
        fallback_id = f"acceptance_rule_{index + 1}"
        if (
            "objective system" in lowered
            and "outperform" in lowered
            and ("majority baseline" in lowered or "random baseline" in lowered)
        ):
            baseline = "random_ranker" if "random baseline" in lowered else "majority"
            return cls(
                id=_rule_slug(text, fallback=fallback_id),
                description=text,
                kind="objective_metric_comparison",
                metric="primary_metric",
                target="objective_system",
                baseline_system=baseline,
                comparison="gt",
                required_statistics=["mean"],
            )
        if "every requested seed" in lowered:
            return cls(
                id=_rule_slug(text, fallback=fallback_id),
                description=text,
                kind="seed_coverage",
            )
        if (
            "mean and standard deviation" in lowered
            or "standard deviation" in lowered
            or "confidence interval" in lowered
        ):
            required_statistics: list[AcceptanceStatistic] = []
            if "mean" in lowered:
                required_statistics.append("mean")
            if "standard deviation" in lowered or "std" in lowered:
                required_statistics.append("std")
            if "confidence interval" in lowered:
                required_statistics.append("confidence_interval")
            return cls(
                id=_rule_slug(text, fallback=fallback_id),
                description=text,
                kind="aggregate_metric_reporting",
                metric="primary_metric",
                target="objective_system",
                required_statistics=required_statistics or ["mean"],
            )
        return cls(
            id=_rule_slug(text, fallback=fallback_id),
            description=text,
            kind="custom",
        )


class ConfidenceIntervalSummary(BaseModel):
    lower: float
    upper: float
    level: float = 0.95
    method: ConfidenceIntervalMethod = "student_t_95"


class SignificanceTestResult(BaseModel):
    scope: SignificanceComparisonScope
    metric: str
    candidate: str
    comparator: str
    comparison_family: str | None = None
    family_size: int = 1
    alternative: SignificanceAlternative = "two_sided"
    method: SignificanceTestMethod = "paired_sign_flip_exact"
    p_value: float
    adjusted_p_value: float | None = None
    adjusted_alpha: float | None = None
    correction: MultipleComparisonCorrection | None = None
    effect_size: float
    minimum_detectable_effect: float | None = None
    recommended_sample_count: int | None = None
    adequately_powered: bool | None = None
    power_detail: str | None = None
    significant: bool = False
    sample_count: int = 0
    detail: str


class FailureRecord(BaseModel):
    scope: FailureScope = "seed"
    sweep_label: str
    seed: int | None = None
    category: FailureCategory = "unknown_failure"
    config_signature: str | None = None
    config_params: dict[str, Any] = Field(default_factory=dict)
    runtime_context: dict[str, Any] = Field(default_factory=dict)
    summary: str
    detail: str
    diagnosis: str | None = None
    likely_fix: str | None = None
    returncode: int | None = None
    status: Literal["failed"] = "failed"


class NegativeResultRecord(BaseModel):
    scope: NegativeResultScope
    subject: str
    reference: str
    metric: str
    observed_score: float | None = None
    reference_score: float | None = None
    delta: float | None = None
    detail: str


class AnomalousTrialRecord(BaseModel):
    sweep_label: str
    seed: int
    metric: str
    observed_score: float
    mean_score: float
    z_score: float | None = None
    detail: str


class ExperimentSpec(BaseModel):
    task_family: TaskFamily
    benchmark_name: str
    benchmark_description: str
    dataset: DatasetSpec
    baselines: list[BaselineSpec] = Field(default_factory=list)
    metrics: list[MetricSpec] = Field(default_factory=list)
    hypothesis: str
    ablations: list[AblationSpec] = Field(default_factory=list)
    implementation_notes: list[str] = Field(default_factory=list)
    search_strategies: list[str] = Field(default_factory=list)
    seeds: list[int] = Field(default_factory=list)
    sweeps: list[SweepConfig] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceRule] = Field(default_factory=list)

    @field_validator("acceptance_criteria", mode="before")
    @classmethod
    def _normalize_acceptance_criteria(cls, value: Any) -> Any:
        if value is None:
            return []
        if not isinstance(value, list):
            return value
        normalized: list[Any] = []
        for index, item in enumerate(value):
            if isinstance(item, str):
                normalized.append(AcceptanceRule.from_legacy_string(item, index=index))
                continue
            if isinstance(item, dict) and "description" not in item and "criterion" in item:
                normalized.append({**item, "description": item["criterion"]})
                continue
            normalized.append(item)
        return normalized


class SystemMetricResult(BaseModel):
    system: str
    metrics: dict[str, float] = Field(default_factory=dict)
    notes: str | None = None


class AggregateSystemMetricResult(BaseModel):
    system: str
    mean_metrics: dict[str, float] = Field(default_factory=dict)
    std_metrics: dict[str, float] = Field(default_factory=dict)
    confidence_intervals: dict[str, ConfidenceIntervalSummary] = Field(default_factory=dict)
    min_metrics: dict[str, float] = Field(default_factory=dict)
    max_metrics: dict[str, float] = Field(default_factory=dict)
    sample_count: int = 1


class SeedArtifactResult(BaseModel):
    seed: int
    sweep_label: str
    best_system: str | None = None
    objective_system: str | None = None
    objective_score: float | None = None
    primary_metric: str | None = None
    system_results: list[SystemMetricResult] = Field(default_factory=list)


class SweepEvaluationResult(BaseModel):
    label: str
    params: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None
    status: SweepStatus = "done"
    best_system: str | None = None
    objective_system: str | None = None
    objective_score_mean: float | None = None
    objective_score_std: float | None = None
    objective_score_confidence_interval: ConfidenceIntervalSummary | None = None
    aggregate_system_results: list[AggregateSystemMetricResult] = Field(default_factory=list)
    failed_seeds: list[int] = Field(default_factory=list)
    seed_count: int = 0
    successful_seed_count: int = 0
    failure_categories: list[FailureCategory] = Field(default_factory=list)


class AcceptanceCheck(BaseModel):
    criterion: str
    passed: bool
    detail: str
    rule_id: str | None = None
    rule_kind: AcceptanceRuleKind | None = None


class ResultTable(BaseModel):
    title: str
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class ResultArtifact(BaseModel):
    status: Literal["queued", "running", "done", "failed"]
    summary: str
    key_findings: list[str] = Field(default_factory=list)
    primary_metric: str
    best_system: str | None = None
    system_results: list[SystemMetricResult] = Field(default_factory=list)
    aggregate_system_results: list[AggregateSystemMetricResult] = Field(default_factory=list)
    per_seed_results: list[SeedArtifactResult] = Field(default_factory=list)
    sweep_results: list[SweepEvaluationResult] = Field(default_factory=list)
    significance_tests: list[SignificanceTestResult] = Field(default_factory=list)
    power_analysis_notes: list[str] = Field(default_factory=list)
    negative_results: list[NegativeResultRecord] = Field(default_factory=list)
    failed_trials: list[FailureRecord] = Field(default_factory=list)
    anomalous_trials: list[AnomalousTrialRecord] = Field(default_factory=list)
    acceptance_checks: list[AcceptanceCheck] = Field(default_factory=list)
    tables: list[ResultTable] = Field(default_factory=list)
    logs: str | None = None
    environment: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    objective_system: str | None = None
    objective_score: float | None = None


class LiteratureInsight(BaseModel):
    paper_id: str | None = None
    title: str
    year: int | None = None
    source: str | None = None
    insight: str
    method_hint: str | None = None
    gap_hint: str | None = None
    thematic_group: str | None = None
    methodological_detail: str | None = None
    limitation: str | None = None
    relevance: str | None = None


class LiteratureTheme(BaseModel):
    theme_id: str
    label: str
    description: str
    paper_ids: list[str] = Field(default_factory=list)
    consensus: str | None = None
    tension: str | None = None
    relevance_to_current: str | None = None


class ResearchGap(BaseModel):
    gap_id: str
    description: str
    evidence_from: list[str] = Field(default_factory=list)
    gap_type: Literal["methodological", "empirical", "theoretical", "evaluation"] = "empirical"
    opportunity: str | None = None


class LiteratureSynthesis(BaseModel):
    themes: list[LiteratureTheme] = Field(default_factory=list)
    gaps: list[ResearchGap] = Field(default_factory=list)
    positioning: str | None = None
    novelty_claim: str | None = None
    insights: list[LiteratureInsight] = Field(default_factory=list)


class HypothesisResolution(BaseModel):
    hypothesis: str
    resolution: Literal["supported", "contradicted", "inconclusive"] = "inconclusive"
    evidence: str = ""


class NarrativeAnalysis(BaseModel):
    story_arc: str = ""
    surprising_findings: list[str] = Field(default_factory=list)
    hypothesis_resolutions: list[HypothesisResolution] = Field(default_factory=list)
    key_argument: str = ""
    evidence_chain: list[str] = Field(default_factory=list)
    recommended_emphasis: list[str] = Field(default_factory=list)
    alternative_explanations: list[str] = Field(default_factory=list)
    connections_to_literature: list[str] = Field(default_factory=list)


class AutoResearchProjectFlowDraftRead(BaseModel):
    version: int | None = None
    section: str | None = None
    excerpt: str | None = None
    claim_count: int = 0
    claims: list[str] = Field(default_factory=list)


class AutoResearchProjectFlowEvidenceRead(BaseModel):
    claim_count: int = 0
    claims: list[str] = Field(default_factory=list)
    snippets: list[str] = Field(default_factory=list)


class AutoResearchProjectFlowReviewRead(BaseModel):
    latest_draft_version: int | None = None
    suggestion_count: int = 0
    suggestions: list[str] = Field(default_factory=list)


class AutoResearchProjectFlowContextRead(BaseModel):
    generated_at: datetime
    project_title: str | None = None
    project_topic: str | None = None
    project_status: str | None = None
    template_id: str | None = None
    template_excerpt: str | None = None
    template_sections: list[str] = Field(default_factory=list)
    draft: AutoResearchProjectFlowDraftRead | None = None
    evidence: AutoResearchProjectFlowEvidenceRead | None = None
    review: AutoResearchProjectFlowReviewRead | None = None
    api_surface_hints: list[str] = Field(default_factory=list)
    flow_constraints: list[str] = Field(default_factory=list)
    summary: str


class AutoResearchClaimEvidenceRefRead(BaseModel):
    source_kind: AutoResearchEvidenceSourceKind
    label: str
    detail: str
    locator: str | None = None


class AutoResearchClaimEvidenceEntryRead(BaseModel):
    claim_id: str
    category: AutoResearchClaimCategory
    section_hint: str
    claim: str
    support_status: AutoResearchClaimSupportStatus = "supported"
    evidence: list[AutoResearchClaimEvidenceRefRead] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class AutoResearchClaimEvidenceMatrixRead(BaseModel):
    generated_at: datetime
    claim_count: int = 0
    supported_claim_count: int = 0
    unsupported_claim_count: int = 0
    entries: list[AutoResearchClaimEvidenceEntryRead] = Field(default_factory=list)


class AutoResearchPaperPlanSectionRead(BaseModel):
    section_id: str
    title: str
    objective: str
    claim_ids: list[str] = Field(default_factory=list)
    evidence_focus: list[str] = Field(default_factory=list)
    narrative_guidance: str | None = None
    emphasis: Literal["standard", "expanded", "brief"] = "standard"


class AutoResearchPaperPlanRead(BaseModel):
    generated_at: datetime
    title: str
    narrative_summary: str
    sections: list[AutoResearchPaperPlanSectionRead] = Field(default_factory=list)


class AutoResearchFigurePlanItemRead(BaseModel):
    figure_id: str
    title: str
    kind: AutoResearchFigureAssetKind = "table"
    source: str
    caption: str
    status: AutoResearchFigureStatus = "planned"


class AutoResearchFigurePlanRead(BaseModel):
    generated_at: datetime
    items: list[AutoResearchFigurePlanItemRead] = Field(default_factory=list)


class AutoResearchPaperRevisionStateRead(BaseModel):
    generated_at: datetime
    revision_round: int = 0
    status: AutoResearchPaperRevisionStatus = "drafted"
    open_issues: list[str] = Field(default_factory=list)
    completed_actions: list[str] = Field(default_factory=list)
    focus_sections: list[str] = Field(default_factory=list)
    next_actions: list["AutoResearchPaperRevisionActionRead"] = Field(default_factory=list)
    checkpoints: list["AutoResearchPaperRevisionCheckpointRead"] = Field(default_factory=list)


class AutoResearchPaperRevisionActionRead(BaseModel):
    action_id: str
    priority: AutoResearchRevisionPriority = "medium"
    section_title: str
    detail: str
    status: AutoResearchPaperRevisionActionStatus = "open"


class AutoResearchPaperRevisionCheckpointRead(BaseModel):
    revision_round: int = 0
    generated_at: datetime
    status: AutoResearchPaperRevisionStatus = "drafted"
    summary: str
    open_issue_count: int = 0
    open_issue_summaries: list[str] = Field(default_factory=list)
    focus_sections: list[str] = Field(default_factory=list)
    next_action_ids: list[str] = Field(default_factory=list)
    completed_action_titles: list[str] = Field(default_factory=list)
    relative_assets: list[str] = Field(default_factory=list)


class AutoResearchPaperSectionRewritePacketRead(BaseModel):
    section_id: str
    section_title: str
    revision_round: int = 0
    focus: bool = False
    objective: str
    claim_ids: list[str] = Field(default_factory=list)
    evidence_focus: list[str] = Field(default_factory=list)
    action_ids: list[str] = Field(default_factory=list)
    open_issues: list[str] = Field(default_factory=list)
    current_word_count: int = 0
    relative_path: str
    source_asset_paths: list[str] = Field(default_factory=list)


class AutoResearchPaperSectionRewriteIndexRead(BaseModel):
    generated_at: datetime
    revision_round: int = 0
    packet_count: int = 0
    focus_packet_count: int = 0
    packets: list[AutoResearchPaperSectionRewritePacketRead] = Field(default_factory=list)


class AutoResearchPaperRevisionDiffSectionRead(BaseModel):
    section_id: str
    section_title: str
    status: AutoResearchPaperRevisionDiffStatus = "unchanged"
    previous_word_count: int = 0
    current_word_count: int = 0
    word_delta: int = 0
    previous_action_ids: list[str] = Field(default_factory=list)
    current_action_ids: list[str] = Field(default_factory=list)
    resolved_action_ids: list[str] = Field(default_factory=list)
    previous_open_issue_count: int = 0
    current_open_issue_count: int = 0
    resolved_issue_summaries: list[str] = Field(default_factory=list)


class AutoResearchPaperRevisionDiffRead(BaseModel):
    generated_at: datetime
    revision_round: int = 0
    base_revision_round: int | None = None
    summary: str
    changed_section_count: int = 0
    unchanged_section_count: int = 0
    resolved_action_count: int = 0
    resolved_issue_count: int = 0
    sections: list[AutoResearchPaperRevisionDiffSectionRead] = Field(default_factory=list)


class AutoResearchPaperRevisionActionEntryRead(BaseModel):
    action_id: str
    title: str | None = None
    detail: str
    priority: AutoResearchRevisionPriority = "medium"
    status: AutoResearchPaperRevisionActionMaterializationStatus = "pending"
    section_id: str | None = None
    section_title: str
    first_seen_round: int = 0
    last_seen_round: int = 0
    completed_round: int | None = None
    issue_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    evidence_focus: list[str] = Field(default_factory=list)
    packet_relative_path: str | None = None
    diff_status: AutoResearchPaperRevisionDiffStatus = "unchanged"
    current_word_count: int = 0
    word_delta: int = 0
    open_issue_summaries: list[str] = Field(default_factory=list)
    resolved_issue_summaries: list[str] = Field(default_factory=list)
    current_excerpt: str | None = None


class AutoResearchPaperRevisionActionIndexRead(BaseModel):
    generated_at: datetime
    revision_round: int = 0
    total_action_count: int = 0
    pending_action_count: int = 0
    completed_action_count: int = 0
    materialized_action_count: int = 0
    summary: str
    actions: list[AutoResearchPaperRevisionActionEntryRead] = Field(default_factory=list)


class AutoResearchPaperSourceFileRead(BaseModel):
    relative_path: str
    kind: AutoResearchPaperSourceKind
    description: str


class AutoResearchPaperSourcesManifestRead(BaseModel):
    generated_at: datetime
    entrypoint: str
    bibliography: str | None = None
    compiler_hint: str
    compile_commands: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    files: list[AutoResearchPaperSourceFileRead] = Field(default_factory=list)


class AutoResearchPaperParagraphEvidenceRead(BaseModel):
    paragraph_id: str
    section_id: str
    section_title: str
    paragraph_index: int = 0
    excerpt: str
    claim_ids: list[str] = Field(default_factory=list)
    evidence_kinds: list[AutoResearchPaperEvidenceKind] = Field(default_factory=list)
    evidence_refs: list[AutoResearchClaimEvidenceRefRead] = Field(default_factory=list)
    missing_evidence_kinds: list[AutoResearchPaperEvidenceKind] = Field(default_factory=list)
    support_status: AutoResearchClaimSupportStatus = "unsupported"


class AutoResearchPaperClaimLedgerEntryRead(BaseModel):
    claim_id: str
    claim: str
    category: AutoResearchClaimCategory
    section_ids: list[str] = Field(default_factory=list)
    paragraph_ids: list[str] = Field(default_factory=list)
    support_status: AutoResearchClaimSupportStatus = "unsupported"
    evidence_kinds: list[AutoResearchPaperEvidenceKind] = Field(default_factory=list)
    evidence_count: int = 0
    strong: bool = False


class AutoResearchPaperUnregisteredClaimRead(BaseModel):
    claim_id: str
    section_id: str
    section_title: str
    excerpt: str
    reason: str


class AutoResearchPaperContradictionRead(BaseModel):
    contradiction_id: str
    section_id: str
    section_title: str
    severity: Literal["warning", "blocker"] = "warning"
    claim_id: str | None = None
    summary: str
    detail: str


class AutoResearchPaperCompileReportRead(BaseModel):
    generated_at: datetime
    entrypoint: str
    bibliography: str | None = None
    compiler_hint: str
    compile_commands: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    missing_required_inputs: list[str] = Field(default_factory=list)
    required_source_files: list[str] = Field(default_factory=list)
    missing_required_source_files: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    materialized_outputs: list[str] = Field(default_factory=list)
    source_package_complete: bool = False
    all_expected_outputs_materialized: bool = False
    ready_for_compile: bool = False
    paper_tier: AutoResearchPaperTier = "technical_report"
    evidence_bound_paragraph_count: int = 0
    evidence_unbound_paragraph_count: int = 0
    strong_claim_count: int = 0
    registered_strong_claim_count: int = 0
    unregistered_claim_count: int = 0
    contradiction_count: int = 0
    blocker_count: int = 0
    paragraph_evidence: list[AutoResearchPaperParagraphEvidenceRead] = Field(default_factory=list)
    claim_ledger: list[AutoResearchPaperClaimLedgerEntryRead] = Field(default_factory=list)
    unregistered_claims: list[AutoResearchPaperUnregisteredClaimRead] = Field(default_factory=list)
    contradictions: list[AutoResearchPaperContradictionRead] = Field(default_factory=list)
    evidence_blockers: list[str] = Field(default_factory=list)
    evidence_warnings: list[str] = Field(default_factory=list)
    evidence_compiler_fingerprint: str | None = None


class AutoResearchPaperPipelineArtifactsRead(BaseModel):
    narrative_report_markdown: str
    claim_evidence_matrix: AutoResearchClaimEvidenceMatrixRead
    paper_plan: AutoResearchPaperPlanRead
    figure_plan: AutoResearchFigurePlanRead
    paper_revision_state: AutoResearchPaperRevisionStateRead
    paper_compile_report: AutoResearchPaperCompileReportRead
    paper_revision_diff: AutoResearchPaperRevisionDiffRead
    paper_revision_action_index: AutoResearchPaperRevisionActionIndexRead
    paper_section_rewrite_index: AutoResearchPaperSectionRewriteIndexRead
    paper_latex_source: str
    paper_bibliography_bib: str
    paper_sources_manifest: AutoResearchPaperSourcesManifestRead
    paper_markdown: str


class ExperimentAttempt(BaseModel):
    round_index: int
    strategy: str
    goal: str
    status: Literal["done", "failed"]
    summary: str
    critique: str | None = None
    code_path: str | None = None
    repair_summary: dict[str, Any] | None = None
    artifact: ResultArtifact | None = None


class ResearchProgram(BaseModel):
    id: str
    topic: str
    title: str
    task_family: TaskFamily
    objective: str
    benchmark_name: str | None = None
    portfolio_policy: str
    research_questions: list[str] = Field(default_factory=list)
    scope_limits: list[str] = Field(default_factory=list)


class HypothesisCandidate(BaseModel):
    id: str
    program_id: str
    rank: int
    portfolio_role: str | None = None
    diversity_axis: str | None = None
    title: str
    hypothesis: str
    proposed_method: str
    rationale: str
    planned_contributions: list[str] = Field(default_factory=list)
    differentiators: list[str] = Field(default_factory=list)
    search_strategies: list[str] = Field(default_factory=list)
    status: HypothesisCandidateStatus = "planned"
    score: float | None = None
    selection_reason: str | None = None
    attempts: list[ExperimentAttempt] = Field(default_factory=list)
    artifact: ResultArtifact | None = None
    workspace_path: str | None = None
    plan_path: str | None = None
    spec_path: str | None = None
    attempts_path: str | None = None
    artifact_path: str | None = None
    manifest_path: str | None = None
    generated_code_path: str | None = None
    paper_path: str | None = None
    paper_markdown: str | None = None
    selected_round_index: int | None = None


class PortfolioDecisionRecord(BaseModel):
    candidate_id: str
    rank: int
    status: HypothesisCandidateStatus
    quality_tier: str | None = None
    outcome: PortfolioDecisionOutcome = "pending"
    executed: bool = False
    selected: bool = False
    objective_score: float | None = None
    acceptance_passed: int = 0
    acceptance_total: int = 0
    acceptance_ratio: float = 0.0
    compared_to_candidate_id: str | None = None
    criteria: list[str] = Field(default_factory=list)
    reason: str


class PortfolioSummary(BaseModel):
    status: PortfolioStatus = "planned"
    total_candidates: int = 0
    candidate_rankings: list[str] = Field(default_factory=list)
    executed_candidate_ids: list[str] = Field(default_factory=list)
    selected_candidate_id: str | None = None
    selection_policy: str
    decision_summary: str
    winning_score: float | None = None
    decisions: list[PortfolioDecisionRecord] = Field(default_factory=list)


class AutoResearchRunRead(BaseModel):
    id: str
    project_id: str
    topic: str
    status: AutoResearchRunStatus
    brief_id: str | None = None
    hypothesis_id: str | None = None
    direction_selection_reason: str | None = None
    request: AutoResearchRunConfig | None = None
    task_family: TaskFamily | None = None
    benchmark: BenchmarkSource | None = None
    execution_backend: ExecutionBackendSpec | None = None
    program: ResearchProgram | None = None
    plan: ResearchPlan | None = None
    spec: ExperimentSpec | None = None
    literature: list[LiteratureInsight] = Field(default_factory=list)
    literature_synthesis: LiteratureSynthesis | None = None
    narrative_analysis: NarrativeAnalysis | None = None
    project_context: AutoResearchProjectFlowContextRead | None = None
    project_context_path: str | None = None
    narrative_report_markdown: str | None = None
    narrative_report_path: str | None = None
    claim_evidence_matrix: AutoResearchClaimEvidenceMatrixRead | None = None
    claim_evidence_matrix_path: str | None = None
    paper_plan: AutoResearchPaperPlanRead | None = None
    paper_plan_path: str | None = None
    figure_plan: AutoResearchFigurePlanRead | None = None
    figure_plan_path: str | None = None
    paper_revision_state: AutoResearchPaperRevisionStateRead | None = None
    paper_revision_state_path: str | None = None
    paper_compile_report: AutoResearchPaperCompileReportRead | None = None
    paper_compile_report_path: str | None = None
    paper_revision_diff: AutoResearchPaperRevisionDiffRead | None = None
    paper_revision_diff_path: str | None = None
    paper_revision_action_index: AutoResearchPaperRevisionActionIndexRead | None = None
    paper_revision_action_index_path: str | None = None
    paper_section_rewrite_index: AutoResearchPaperSectionRewriteIndexRead | None = None
    paper_section_rewrite_index_path: str | None = None
    experiment_factory_plan: AutoResearchExperimentFactoryPlanRead | None = None
    experiment_factory_plan_path: str | None = None
    experiment_factory_environment_manifest: AutoResearchExperimentFactoryEnvironmentManifestRead | None = None
    experiment_factory_environment_manifest_path: str | None = None
    experiment_factory_materialized_jobs: list[AutoResearchExperimentFactoryMaterializedJobRead] = Field(default_factory=list)
    experiment_factory_materialized_jobs_path: str | None = None
    evidence_ledger: AutoResearchEvidenceLedgerRead | None = None
    evidence_ledger_path: str | None = None
    experiment_factory_repair_plan: AutoResearchExperimentFactoryRepairPlanRead | None = None
    experiment_factory_repair_plan_path: str | None = None
    paper_sources_dir: str | None = None
    paper_section_rewrite_packets_dir: str | None = None
    paper_latex_source: str | None = None
    paper_latex_path: str | None = None
    paper_bibliography_bib: str | None = None
    paper_bibliography_path: str | None = None
    paper_sources_manifest: AutoResearchPaperSourcesManifestRead | None = None
    paper_sources_manifest_path: str | None = None
    reviewer_simulation: "AutoResearchReviewerSimulationRead | None" = None
    reviewer_simulation_path: str | None = None
    candidates: list[HypothesisCandidate] = Field(default_factory=list)
    portfolio: PortfolioSummary | None = None
    attempts: list[ExperimentAttempt] = Field(default_factory=list)
    artifact: ResultArtifact | None = None
    generated_code_path: str | None = None
    paper_path: str | None = None
    paper_markdown: str | None = None
    paper_draft_version: int | None = None
    docker_image: str | None = None
    error: str | None = None
    selected_round_index: int | None = None
    created_at: datetime
    updated_at: datetime


class AutoResearchRunList(BaseModel):
    items: list[AutoResearchRunRead] = Field(default_factory=list)


class AutoResearchRegistryAssetRef(BaseModel):
    path: str
    kind: AutoResearchRegistryAssetKind = "file"
    exists: bool = False
    size_bytes: int | None = None
    sha256: str | None = None


class AutoResearchLineageEdgeRead(BaseModel):
    source_kind: AutoResearchLineageNodeKind
    source_id: str
    relation: AutoResearchLineageRelation
    target_kind: AutoResearchLineageNodeKind
    target_id: str
    target_path: str | None = None
    exists: bool | None = None


class AutoResearchRunRegistryFiles(BaseModel):
    root: AutoResearchRegistryAssetRef
    run_json: AutoResearchRegistryAssetRef
    program_json: AutoResearchRegistryAssetRef | None = None
    plan_json: AutoResearchRegistryAssetRef | None = None
    spec_json: AutoResearchRegistryAssetRef | None = None
    portfolio_json: AutoResearchRegistryAssetRef | None = None
    artifact_json: AutoResearchRegistryAssetRef | None = None
    benchmark_json: AutoResearchRegistryAssetRef | None = None
    benchmark_card_json: AutoResearchRegistryAssetRef | None = None
    generated_code: AutoResearchRegistryAssetRef | None = None
    paper_markdown: AutoResearchRegistryAssetRef | None = None
    narrative_report_markdown: AutoResearchRegistryAssetRef | None = None
    claim_evidence_matrix_json: AutoResearchRegistryAssetRef | None = None
    experiment_design_json: AutoResearchRegistryAssetRef | None = None
    failure_analysis_json: AutoResearchRegistryAssetRef | None = None
    research_replan_json: AutoResearchRegistryAssetRef | None = None
    research_protocol_json: AutoResearchRegistryAssetRef | None = None
    methodology_audit_json: AutoResearchRegistryAssetRef | None = None
    publication_readiness_json: AutoResearchRegistryAssetRef | None = None
    contribution_assessment_json: AutoResearchRegistryAssetRef | None = None
    literature_graph_json: AutoResearchRegistryAssetRef | None = None
    novelty_validation_json: AutoResearchRegistryAssetRef | None = None
    revision_dossier_json: AutoResearchRegistryAssetRef | None = None
    publication_evidence_index_json: AutoResearchRegistryAssetRef | None = None
    artifact_integrity_audit_json: AutoResearchRegistryAssetRef | None = None
    publication_repair_plan_json: AutoResearchRegistryAssetRef | None = None
    publication_repair_execution_json: AutoResearchRegistryAssetRef | None = None
    reviewer_simulation_json: AutoResearchRegistryAssetRef | None = None
    experiment_factory_plan_json: AutoResearchRegistryAssetRef | None = None
    experiment_factory_environment_manifest_json: AutoResearchRegistryAssetRef | None = None
    experiment_factory_materialized_jobs_json: AutoResearchRegistryAssetRef | None = None
    evidence_ledger_json: AutoResearchRegistryAssetRef | None = None
    experiment_factory_repair_plan_json: AutoResearchRegistryAssetRef | None = None
    paper_plan_json: AutoResearchRegistryAssetRef | None = None
    figure_plan_json: AutoResearchRegistryAssetRef | None = None
    paper_revision_history_markdown: AutoResearchRegistryAssetRef | None = None
    paper_revision_state_json: AutoResearchRegistryAssetRef | None = None
    paper_compile_report_json: AutoResearchRegistryAssetRef | None = None
    paper_revision_diff_json: AutoResearchRegistryAssetRef | None = None
    paper_revision_action_index_json: AutoResearchRegistryAssetRef | None = None
    paper_section_rewrite_index_json: AutoResearchRegistryAssetRef | None = None
    paper_revision_brief_markdown: AutoResearchRegistryAssetRef | None = None
    paper_sources_dir: AutoResearchRegistryAssetRef | None = None
    paper_section_rewrite_packets_dir: AutoResearchRegistryAssetRef | None = None
    paper_build_script: AutoResearchRegistryAssetRef | None = None
    paper_checkpoint_index_json: AutoResearchRegistryAssetRef | None = None
    paper_latex_source: AutoResearchRegistryAssetRef | None = None
    paper_bibliography_bib: AutoResearchRegistryAssetRef | None = None
    paper_sources_manifest_json: AutoResearchRegistryAssetRef | None = None
    paper_compiled_pdf: AutoResearchRegistryAssetRef | None = None
    paper_bibliography_output_bbl: AutoResearchRegistryAssetRef | None = None


class AutoResearchCandidateRegistryFiles(BaseModel):
    workspace: AutoResearchRegistryAssetRef
    candidate_json: AutoResearchRegistryAssetRef | None = None
    plan_json: AutoResearchRegistryAssetRef | None = None
    spec_json: AutoResearchRegistryAssetRef | None = None
    attempts_json: AutoResearchRegistryAssetRef | None = None
    artifact_json: AutoResearchRegistryAssetRef | None = None
    manifest_json: AutoResearchRegistryAssetRef | None = None
    generated_code: AutoResearchRegistryAssetRef | None = None
    paper_markdown: AutoResearchRegistryAssetRef | None = None


class AutoResearchCandidateManifestCandidate(BaseModel):
    id: str
    program_id: str
    rank: int
    title: str
    status: HypothesisCandidateStatus
    objective_score: float | None = None
    selection_reason: str | None = None


class AutoResearchCandidateManifestRead(BaseModel):
    manifest_source: AutoResearchManifestSource = "generated_fallback"
    candidate: AutoResearchCandidateManifestCandidate
    decision: PortfolioDecisionRecord | None = None
    files: AutoResearchCandidateRegistryFiles


class AutoResearchCandidateRegistryEntry(BaseModel):
    candidate_id: str
    program_id: str
    rank: int
    title: str
    status: HypothesisCandidateStatus
    objective_score: float | None = None
    selected: bool = False
    selected_round_index: int | None = None
    attempt_count: int = 0
    artifact_status: str | None = None
    manifest_source: AutoResearchManifestSource = "generated_fallback"
    decision_outcome: PortfolioDecisionOutcome | None = None
    decision_reason: str | None = None
    files: AutoResearchCandidateRegistryFiles


class AutoResearchRunLineageRead(BaseModel):
    selected_candidate_id: str | None = None
    top_level_plan_candidate_id: str | None = None
    top_level_spec_candidate_id: str | None = None
    top_level_artifact_candidate_id: str | None = None
    top_level_paper_candidate_id: str | None = None
    edges: list[AutoResearchLineageEdgeRead] = Field(default_factory=list)


class AutoResearchCandidateLineageRead(BaseModel):
    selected: bool = False
    decision_outcome: PortfolioDecisionOutcome | None = None
    edges: list[AutoResearchLineageEdgeRead] = Field(default_factory=list)


class AutoResearchRunRegistryRead(BaseModel):
    project_id: str
    run_id: str
    topic: str
    status: AutoResearchRunStatus
    task_family: TaskFamily | None = None
    program_id: str | None = None
    benchmark_name: str | None = None
    portfolio_status: PortfolioStatus | None = None
    selected_candidate_id: str | None = None
    decision_summary: str | None = None
    root_path: str
    files: AutoResearchRunRegistryFiles
    lineage: AutoResearchRunLineageRead
    candidates: list[AutoResearchCandidateRegistryEntry] = Field(default_factory=list)


class AutoResearchCandidateRegistryRead(BaseModel):
    project_id: str
    run_id: str
    candidate_id: str
    selected: bool = False
    root_path: str
    candidate: HypothesisCandidate
    decision: PortfolioDecisionRecord | None = None
    manifest: AutoResearchCandidateManifestRead
    lineage: AutoResearchCandidateLineageRead


class AutoResearchBundleAssetRead(BaseModel):
    asset_id: str
    label: str
    role: AutoResearchBundleAssetRole
    candidate_id: str | None = None
    selected: bool = False
    required: bool = True
    ref: AutoResearchRegistryAssetRef


class AutoResearchBundleRead(BaseModel):
    id: str
    name: str
    description: str
    selected_candidate_id: str | None = None
    candidate_ids: list[str] = Field(default_factory=list)
    asset_count: int = 0
    existing_asset_count: int = 0
    missing_asset_count: int = 0
    assets: list[AutoResearchBundleAssetRead] = Field(default_factory=list)


class AutoResearchBundleIndexRead(BaseModel):
    project_id: str
    run_id: str
    bundles: list[AutoResearchBundleRead] = Field(default_factory=list)


class AutoResearchRegistryViewRead(BaseModel):
    id: str
    label: str
    description: str
    candidate_ids: list[str] = Field(default_factory=list)
    count: int = 0
    entries: list[AutoResearchCandidateRegistryEntry] = Field(default_factory=list)


class AutoResearchRegistryViewCounts(BaseModel):
    total_candidates: int = 0
    selected: int = 0
    eliminated: int = 0
    failed: int = 0
    active: int = 0


class AutoResearchRunRegistryViewsRead(BaseModel):
    project_id: str
    run_id: str
    selected_candidate_id: str | None = None
    counts: AutoResearchRegistryViewCounts
    views: list[AutoResearchRegistryViewRead] = Field(default_factory=list)


class AutoResearchReviewScoresRead(BaseModel):
    evidence_support: int = 0
    statistical_rigor: int = 0
    contextualization: int = 0
    reproducibility: int = 0
    publish_readiness: int = 0


class AutoResearchReviewEvidenceRead(BaseModel):
    selected_bundle_id: str | None = None
    literature_count: int = 0
    candidate_count: int = 0
    executed_candidate_count: int = 0
    seed_count: int = 0
    completed_seed_count: int = 0
    sweep_count: int = 0
    significance_test_count: int = 0
    negative_result_count: int = 0
    failed_trial_count: int = 0
    acceptance_passed: int = 0
    acceptance_total: int = 0
    citation_marker_count: int = 0
    missing_required_asset_count: int = 0
    real_literature_count: int = 0
    synthetic_literature_count: int = 0
    publication_grade_benchmark: bool = False


class AutoResearchReadinessCheckRead(BaseModel):
    check_id: str
    category: AutoResearchReadinessCategory
    passed: bool = False
    required_for_final_publish: bool = True
    summary: str
    detail: str


class AutoResearchPublicationReadinessRead(BaseModel):
    generated_at: datetime
    tier: AutoResearchPublicationTier = "exploratory"
    score: int = 0
    summary: str
    final_publish_ready: bool = False
    publication_grade_benchmark: bool = False
    real_literature_count: int = 0
    synthetic_literature_count: int = 0
    completed_seed_count: int = 0
    requested_seed_count: int = 0
    significance_test_count: int = 0
    planned_ablation_count: int = 0
    observed_ablation_count: int = 0
    unsupported_claim_count: int = 0
    checks: list[AutoResearchReadinessCheckRead] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AutoResearchContributionClaimRead(BaseModel):
    claim_id: str
    text: str
    contribution_type: AutoResearchContributionType
    claim_strength: AutoResearchClaimStrength = "unsupported"
    core: bool = False
    evidence_sources: list[str] = Field(default_factory=list)
    rationale: str


class AutoResearchNoveltyRiskRead(BaseModel):
    risk_id: str
    risk_type: Literal[
        "duplicate_risk",
        "incremental_risk",
        "evidence_gap",
        "literature_gap",
        "claim_overreach",
    ]
    severity: AutoResearchNoveltyRiskSeverity = "medium"
    summary: str
    detail: str
    evidence_refs: list[str] = Field(default_factory=list)


class AutoResearchContributionAssessmentRead(BaseModel):
    generated_at: datetime
    assessment_id: str = "contribution_assessment_v1"
    contribution_claims: list[AutoResearchContributionClaimRead] = Field(default_factory=list)
    novelty_risks: list[AutoResearchNoveltyRiskRead] = Field(default_factory=list)
    publishability_score: int = 0
    clear_contribution_count: int = 0
    strong_core_claim_count: int = 0
    artifact_supported_claim_count: int = 0
    statistically_supported_claim_count: int = 0
    literature_positioned_claim_count: int = 0
    complete: bool = False
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    assessment_fingerprint: str


class AutoResearchExperimentBaselinePlanRead(BaseModel):
    name: str
    baseline_type: AutoResearchExperimentBaselineType
    required: bool = True
    present_in_spec: bool = False
    present_in_results: bool = False
    fair_comparison: bool = False
    rationale: str


class AutoResearchExperimentAblationPlanRead(BaseModel):
    component_id: str
    component: str
    ablation_name: str | None = None
    planned: bool = False
    observed: bool = False
    rationale: str


class AutoResearchExperimentSeedPlanRead(BaseModel):
    planned_seeds: list[int] = Field(default_factory=list)
    planned_seed_count: int = 0
    minimum_completed_seed_count: int = 1
    completed_seed_count: int = 0
    sufficient_for_profile: bool = False
    rationale: str


class AutoResearchExperimentSweepPlanRead(BaseModel):
    planned_sweeps: list[str] = Field(default_factory=list)
    planned_sweep_count: int = 0
    observed_sweeps: list[str] = Field(default_factory=list)
    covers_search_space: bool = False
    rationale: str


class AutoResearchExperimentStatisticalTestPlanRead(BaseModel):
    primary_metric: str | None = None
    recommended_test: AutoResearchStatisticalTestChoice = "permutation_test"
    comparison_unit: Literal["seed", "example", "aggregate"] = "seed"
    requires_confidence_interval: bool = True
    requires_effect_size: bool = True
    requires_power_note: bool = True
    planned_statistic_count: int = 0
    observed_significance_test_count: int = 0
    complete: bool = False
    rationale: str


class AutoResearchExperimentFailureModeRead(BaseModel):
    mode_id: str
    category: Literal[
        "performance_failure",
        "baseline_fairness_failure",
        "ablation_coverage_failure",
        "statistical_power_failure",
        "artifact_failure",
    ]
    trigger: str
    planned_response: str
    severity: Literal["low", "medium", "high"] = "medium"


class AutoResearchExperimentDesignRead(BaseModel):
    generated_at: datetime
    design_id: str = "experiment_design_v1"
    project_id: str
    run_id: str
    execution_profile: AutoResearchExecutionProfile = "exploratory"
    baseline_plan: list[AutoResearchExperimentBaselinePlanRead] = Field(default_factory=list)
    ablation_plan: list[AutoResearchExperimentAblationPlanRead] = Field(default_factory=list)
    seed_plan: AutoResearchExperimentSeedPlanRead
    sweep_plan: AutoResearchExperimentSweepPlanRead
    statistical_test_plan: AutoResearchExperimentStatisticalTestPlanRead
    failure_mode_analysis: list[AutoResearchExperimentFailureModeRead] = Field(default_factory=list)
    naive_baseline_present: bool = False
    strong_baseline_present: bool = False
    candidate_method_present: bool = False
    fair_baseline_count: int = 0
    ablation_coverage: float = 0.0
    completeness_score: int = 0
    completeness: AutoResearchExperimentDesignCompleteness = "partial"
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    design_fingerprint: str


class AutoResearchFailureFindingRead(BaseModel):
    failure_id: str
    failure_type: AutoResearchFailureType
    severity: Literal["low", "medium", "high"] = "medium"
    summary: str
    detail: str
    trigger: str
    evidence_refs: list[str] = Field(default_factory=list)
    recommended_action: AutoResearchResearchActionKind = "rerun_plan"
    blocks_publication: bool = False


class AutoResearchFailureAnalysisRead(BaseModel):
    generated_at: datetime
    analysis_id: str = "failure_analysis_v1"
    project_id: str
    run_id: str
    selected_candidate_id: str | None = None
    finding_count: int = 0
    high_severity_count: int = 0
    publication_blocker_count: int = 0
    performance_failure_count: int = 0
    baseline_failure_count: int = 0
    ablation_failure_count: int = 0
    statistical_failure_count: int = 0
    novelty_failure_count: int = 0
    artifact_failure_count: int = 0
    findings: list[AutoResearchFailureFindingRead] = Field(default_factory=list)
    complete: bool = False
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    analysis_fingerprint: str


class AutoResearchResearchReplanActionRead(BaseModel):
    action_id: str
    action_kind: AutoResearchResearchActionKind
    priority: AutoResearchRevisionPriority = "medium"
    title: str
    rationale: str
    target: str | None = None
    source_failure_ids: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)


class AutoResearchResearchReplanRead(BaseModel):
    generated_at: datetime
    replan_id: str = "research_replan_v1"
    project_id: str
    run_id: str
    selected_candidate_id: str | None = None
    hypothesis_update: str | None = None
    task_scope_update: str | None = None
    actions: list[AutoResearchResearchReplanActionRead] = Field(default_factory=list)
    action_count: int = 0
    rerun_required: bool = False
    abandon_recommended: bool = False
    claim_downgrade_required: bool = False
    experiment_design_repair_required: bool = False
    complete: bool = False
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    replan_fingerprint: str


class AutoResearchResearchProtocolRead(BaseModel):
    generated_at: datetime
    protocol_id: str = "research_protocol_v1"
    execution_profile: AutoResearchExecutionProfile = "exploratory"
    topic: str | None = None
    title: str | None = None
    task_family: TaskFamily | None = None
    benchmark_name: str | None = None
    benchmark_publication_grade: bool = False
    dataset_source_kind: BenchmarkKind | None = None
    dataset_source_url: str | None = None
    dataset_source_dataset_id: str | None = None
    dataset_fingerprint: str | None = None
    hypothesis: str | None = None
    research_questions: list[str] = Field(default_factory=list)
    primary_metric: str | None = None
    baseline_systems: list[str] = Field(default_factory=list)
    ablation_systems: list[str] = Field(default_factory=list)
    planned_seed_count: int = 0
    minimum_completed_seed_count: int = 0
    planned_sweep_count: int = 0
    acceptance_rule_count: int = 0
    acceptance_rule_ids: list[str] = Field(default_factory=list)
    required_statistics: list[AcceptanceStatistic] = Field(default_factory=list)
    significance_required: bool = False
    power_analysis_required: bool = False
    literature_minimum: int = 0
    evidence_requirements: list[str] = Field(default_factory=list)
    reproducibility_requirements: list[str] = Field(default_factory=list)
    threat_model: list[str] = Field(default_factory=list)
    checks: list[AutoResearchReadinessCheckRead] = Field(default_factory=list)
    complete: bool = False
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    protocol_fingerprint: str


class AutoResearchBenchmarkCardRead(BaseModel):
    generated_at: datetime
    card_id: str = "benchmark_card_v1"
    topic: str | None = None
    task_family: TaskFamily | None = None
    benchmark_name: str | None = None
    benchmark_description: str | None = None
    dataset_name: str | None = None
    dataset_description: str | None = None
    train_size: int = 0
    test_size: int = 0
    total_examples: int = 0
    label_space: list[str] = Field(default_factory=list)
    input_fields: list[str] = Field(default_factory=list)
    source_kind: BenchmarkKind | None = None
    source_url: str | None = None
    source_dataset_id: str | None = None
    source_revision: str | None = None
    source_license: str | None = None
    source_fingerprint: str | None = None
    publication_grade: bool = False
    provenance_complete: bool = False
    checks: list[AutoResearchReadinessCheckRead] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    recommended_use: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    card_fingerprint: str


AutoResearchEvidenceIndexCategory = Literal[
    "run",
    "benchmark",
    "protocol",
    "design",
    "failure",
    "replan",
    "methodology",
    "readiness",
    "contribution",
    "novelty",
    "revision",
    "claims",
    "paper",
    "code",
    "review",
    "lineage",
    "package",
]


class AutoResearchEvidenceIndexItemRead(BaseModel):
    evidence_id: str
    label: str
    category: AutoResearchEvidenceIndexCategory
    role: AutoResearchBundleAssetRole | None = None
    path: str | None = None
    exists: bool = False
    size_bytes: int | None = None
    sha256: str | None = None
    required_for_final_publish: bool = False
    supports: list[str] = Field(default_factory=list)
    status: Literal["present", "missing"] = "missing"


class AutoResearchPublicationEvidenceIndexRead(BaseModel):
    generated_at: datetime
    index_id: str = "publication_evidence_index_v1"
    project_id: str
    run_id: str
    selected_candidate_id: str | None = None
    review_round: int = 0
    review_fingerprint: str | None = None
    publication_tier: AutoResearchPublicationTier = "exploratory"
    publication_readiness_score: int = 0
    evidence_item_count: int = 0
    required_evidence_count: int = 0
    present_required_evidence_count: int = 0
    missing_required_evidence_count: int = 0
    missing_required_evidence_ids: list[str] = Field(default_factory=list)
    evidence_items: list[AutoResearchEvidenceIndexItemRead] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    complete: bool = False
    evidence_index_fingerprint: str


class AutoResearchReviewerSimulationReviewRead(BaseModel):
    review_id: str
    role: AutoResearchReviewerRole
    summary: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    score: int = 0
    confidence: int = 0
    decision: AutoResearchReviewerDecision = "borderline"
    reject_reason: str | None = None


class AutoResearchReviewerResponseActionRead(BaseModel):
    action_id: str
    reviewer_role: AutoResearchReviewerRole
    action_kind: AutoResearchReviewerResponseActionKind
    priority: AutoResearchRevisionPriority = "medium"
    title: str
    detail: str
    maps_to: str
    source_review_ids: list[str] = Field(default_factory=list)


class AutoResearchReviewerSimulationRead(BaseModel):
    generated_at: datetime
    simulation_id: str = "reviewer_simulation_v1"
    project_id: str
    run_id: str
    selected_candidate_id: str | None = None
    reviews: list[AutoResearchReviewerSimulationReviewRead] = Field(default_factory=list)
    average_score: float = 0.0
    minimum_score: int = 0
    minimum_decision: AutoResearchReviewerDecision = "borderline"
    weak_reject_or_worse_count: int = 0
    confidence_mean: float = 0.0
    publication_blocker_count: int = 0
    response_plan: list[AutoResearchReviewerResponseActionRead] = Field(default_factory=list)
    response_plan_action_count: int = 0
    complete: bool = False
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    simulation_fingerprint: str


class AutoResearchMetaAnalysisRunSummaryRead(BaseModel):
    run_id: str
    topic: str
    hypothesis: str | None = None
    method: str | None = None
    dataset: str | None = None
    primary_metric: str | None = None
    objective_score: float | None = None
    seed_count: int = 0
    significant_result_count: int = 0
    contribution_score: int = 0
    novelty_risk: AutoResearchNoveltyRiskLevel = "medium"
    publication_tier: AutoResearchPublicationTier | None = None
    final_publish_ready: bool = False


class AutoResearchMetaAnalysisComparisonRead(BaseModel):
    comparison_id: str
    axis: AutoResearchMetaAnalysisComparisonAxis
    label: str
    run_ids: list[str] = Field(default_factory=list)
    best_run_id: str | None = None
    metric: str | None = None
    score_range: list[float] = Field(default_factory=list)
    stability: AutoResearchConclusionStability = "conditional"
    rationale: str


class AutoResearchStableConclusionRead(BaseModel):
    conclusion_id: str
    text: str
    stability: AutoResearchConclusionStability = "conditional"
    supporting_run_ids: list[str] = Field(default_factory=list)
    scope: str
    caveats: list[str] = Field(default_factory=list)


class AutoResearchCrossRunMetaAnalysisRead(BaseModel):
    generated_at: datetime
    analysis_id: str = "cross_run_meta_analysis_v1"
    project_id: str
    topic_key: str | None = None
    run_count: int = 0
    comparable_run_count: int = 0
    publication_ready_run_count: int = 0
    run_summaries: list[AutoResearchMetaAnalysisRunSummaryRead] = Field(default_factory=list)
    comparisons: list[AutoResearchMetaAnalysisComparisonRead] = Field(default_factory=list)
    stable_conclusions: list[AutoResearchStableConclusionRead] = Field(default_factory=list)
    project_level_paper_recommended: bool = False
    recommended_run_ids: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    analysis_fingerprint: str


class AutoResearchProjectConclusionEntryRead(BaseModel):
    conclusion_id: str
    kind: AutoResearchProjectConclusionKind
    text: str
    supporting_run_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    paper_claim_allowed: bool = False


class AutoResearchProjectConclusionLedgerRead(BaseModel):
    ledger_id: str = "project_conclusion_ledger_v1"
    project_id: str
    stable_conclusions: list[AutoResearchProjectConclusionEntryRead] = Field(default_factory=list)
    conditional_conclusions: list[AutoResearchProjectConclusionEntryRead] = Field(default_factory=list)
    negative_findings: list[AutoResearchProjectConclusionEntryRead] = Field(default_factory=list)
    failed_hypotheses: list[AutoResearchProjectConclusionEntryRead] = Field(default_factory=list)
    limitations: list[AutoResearchProjectConclusionEntryRead] = Field(default_factory=list)
    conclusion_count: int = 0
    ledger_fingerprint: str


class AutoResearchProjectClaimTraceRead(BaseModel):
    claim_id: str
    claim: str
    source_conclusion_id: str
    support_status: AutoResearchProjectClaimTraceStatus = "unsupported"
    supporting_run_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    unsupported_reasons: list[str] = Field(default_factory=list)
    strong_claim: bool = False


class AutoResearchProjectPaperOrchestrationRead(BaseModel):
    generated_at: datetime
    orchestrator_id: str = "project_paper_orchestrator_v1"
    project_id: str
    brief_count: int = 0
    latest_brief_id: str | None = None
    latest_brief_selected_hypothesis_id: str | None = None
    candidate_run_count: int = 0
    selected_run_ids: list[str] = Field(default_factory=list)
    selected_run_count: int = 0
    meta_analysis: AutoResearchCrossRunMetaAnalysisRead
    conclusion_ledger: AutoResearchProjectConclusionLedgerRead
    claim_traces: list[AutoResearchProjectClaimTraceRead] = Field(default_factory=list)
    core_claim_count: int = 0
    supported_core_claim_count: int = 0
    unsupported_core_claim_count: int = 0
    reviewer_simulation_count: int = 0
    reviewer_average_score: float = 0.0
    should_write_paper: bool = False
    project_level_paper_allowed: bool = False
    paper_decision: AutoResearchProjectPaperDecision = "do_not_write"
    paper_tier: AutoResearchPaperTier = "technical_report"
    source_strategy: AutoResearchProjectPaperSourceStrategy = "no_paper"
    project_publish_gate_passed: bool = False
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    orchestration_fingerprint: str


class AutoResearchSystemEvaluationTaskRead(BaseModel):
    task_id: str
    task_kind: AutoResearchEvaluationTaskKind
    title: str
    description: str
    target_capabilities: list[str] = Field(default_factory=list)
    required_artifacts: list[str] = Field(default_factory=list)
    mapped_run_ids: list[str] = Field(default_factory=list)
    score: int = 0
    blockers: list[str] = Field(default_factory=list)


class AutoResearchSystemEvaluationMetricRead(BaseModel):
    metric_id: str
    label: str
    score: int = 0
    numerator: int = 0
    denominator: int = 0
    rationale: str


class AutoResearchEvaluationCaseTraceRead(BaseModel):
    idea: str
    brief_id: str | None = None
    selected_hypothesis_id: str | None = None
    experiment_plan_id: str | None = None
    evidence_ledger_id: str | None = None
    result_artifact_status: str | None = None
    primary_metric: str | None = None
    objective_score: float | None = None
    paper_decision: AutoResearchProjectPaperDecision = "do_not_write"
    steps_completed: list[str] = Field(default_factory=list)
    direction_count: int = 0
    hypothesis_count: int = 0
    experiment_job_count: int = 0
    evidence_entry_count: int = 0
    repair_action_count: int = 0
    evidence_complete: bool = False
    paper_review_package_ready: bool = False
    architecture_materials: list[str] = Field(default_factory=list)
    case_study_materials: list[str] = Field(default_factory=list)
    failure_analysis_materials: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class AutoResearchEvaluationCaseRead(BaseModel):
    case_id: str
    task_kind: AutoResearchEvaluationTaskKind
    idea: str
    expected_brief_quality: str
    expected_novelty_risks: list[str] = Field(default_factory=list)
    expected_experiment_design_requirements: list[str] = Field(default_factory=list)
    expected_failure_replan_behavior: str
    expected_paper_tier: AutoResearchPaperTier = "technical_report"
    mapped_run_ids: list[str] = Field(default_factory=list)
    trace: AutoResearchEvaluationCaseTraceRead | None = None
    score: int = 0
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AutoResearchEvaluationCaseSuiteRead(BaseModel):
    generated_at: datetime
    suite_id: str = "autoresearch_evaluation_case_suite_v1"
    project_id: str
    case_count: int = 0
    executed_case_count: int = 0
    completed_case_count: int = 0
    evaluation_artifact_count: int = 0
    cases: list[AutoResearchEvaluationCaseRead] = Field(default_factory=list)
    metrics: list[AutoResearchSystemEvaluationMetricRead] = Field(default_factory=list)
    scholarflow_paper_materials: list[str] = Field(default_factory=list)
    architecture_materials: list[str] = Field(default_factory=list)
    case_study_materials: list[str] = Field(default_factory=list)
    failure_analysis_materials: list[str] = Field(default_factory=list)
    toy_end_to_end_ready: bool = False
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    suite_fingerprint: str


class AutoResearchSystemEvaluationRead(BaseModel):
    generated_at: datetime
    evaluation_id: str = "system_level_evaluation_v1"
    project_id: str
    task_count: int = 0
    completed_task_count: int = 0
    overall_score: int = 0
    tasks: list[AutoResearchSystemEvaluationTaskRead] = Field(default_factory=list)
    metrics: list[AutoResearchSystemEvaluationMetricRead] = Field(default_factory=list)
    scholarflow_paper_materials: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evaluation_fingerprint: str


AutoResearchArtifactIntegritySeverity = Literal["error", "warning"]
AutoResearchArtifactIntegrityCategory = Literal["registry", "bundle", "lineage", "identity"]


class AutoResearchArtifactIntegrityIssueRead(BaseModel):
    issue_id: str
    severity: AutoResearchArtifactIntegritySeverity
    category: AutoResearchArtifactIntegrityCategory
    summary: str
    detail: str
    asset_id: str | None = None
    role: AutoResearchBundleAssetRole | None = None
    path: str | None = None


class AutoResearchArtifactIntegrityAuditRead(BaseModel):
    generated_at: datetime
    audit_id: str = "artifact_integrity_audit_v1"
    project_id: str
    run_id: str
    selected_candidate_id: str | None = None
    registry_asset_count: int = 0
    existing_registry_asset_count: int = 0
    missing_registry_asset_count: int = 0
    bundle_count: int = 0
    selected_bundle_asset_count: int = 0
    selected_bundle_missing_required_count: int = 0
    lineage_edge_count: int = 0
    missing_lineage_target_count: int = 0
    untraced_existing_asset_count: int = 0
    issue_count: int = 0
    blocker_count: int = 0
    warning_count: int = 0
    issues: list[AutoResearchArtifactIntegrityIssueRead] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    complete: bool = False
    audit_fingerprint: str


AutoResearchRepairActionKind = Literal[
    "rebuild_paper_sources",
    "repair_claim_evidence",
    "refresh_literature",
    "rerun_experiments",
    "repair_experiment_design",
    "research_replan",
    "update_benchmark_provenance",
    "rebuild_publish_package",
    "manual_review",
]
AutoResearchRepairActionStatus = Literal["pending", "blocked", "not_needed"]
AutoResearchRepairActionSource = Literal[
    "review_finding",
    "revision_action",
    "revision_dossier",
    "evidence_index",
    "artifact_integrity_audit",
    "reviewer_simulation",
    "readiness",
    "contribution_assessment",
    "novelty_validation",
    "experiment_design",
    "failure_analysis",
    "research_replan",
]


class AutoResearchPublicationRepairActionRead(BaseModel):
    action_id: str
    kind: AutoResearchRepairActionKind
    source: AutoResearchRepairActionSource
    source_ids: list[str] = Field(default_factory=list)
    priority: AutoResearchRevisionPriority = "medium"
    title: str
    detail: str
    status: AutoResearchRepairActionStatus = "pending"
    auto_applicable: bool = False
    expected_outputs: list[str] = Field(default_factory=list)
    supporting_asset_ids: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class AutoResearchPublicationRepairPlanRead(BaseModel):
    generated_at: datetime
    plan_id: str = "publication_repair_plan_v1"
    project_id: str
    run_id: str
    selected_candidate_id: str | None = None
    review_round: int = 0
    review_fingerprint: str | None = None
    publication_tier: AutoResearchPublicationTier = "exploratory"
    publication_readiness_score: int = 0
    action_count: int = 0
    pending_action_count: int = 0
    blocked_action_count: int = 0
    auto_applicable_action_count: int = 0
    next_action_ids: list[str] = Field(default_factory=list)
    actions: list[AutoResearchPublicationRepairActionRead] = Field(default_factory=list)
    complete: bool = False
    blockers: list[str] = Field(default_factory=list)
    repair_plan_fingerprint: str


AutoResearchRepairExecutionActionStatus = Literal["executed", "partial", "blocked", "skipped"]


class AutoResearchPublicationRepairExecutionActionRead(BaseModel):
    action_id: str
    kind: AutoResearchRepairActionKind
    title: str
    status: AutoResearchRepairExecutionActionStatus = "skipped"
    auto_applicable: bool = False
    expected_output_asset_ids: list[str] = Field(default_factory=list)
    materialized_output_asset_ids: list[str] = Field(default_factory=list)
    missing_output_asset_ids: list[str] = Field(default_factory=list)
    detail: str


class AutoResearchPublicationRepairExecutionRead(BaseModel):
    generated_at: datetime
    execution_id: str = "publication_repair_execution_v1"
    project_id: str
    run_id: str
    selected_candidate_id: str | None = None
    repair_plan_fingerprint: str | None = None
    review_round_before: int = 0
    review_fingerprint_before: str | None = None
    review_round_after: int = 0
    review_fingerprint_after: str | None = None
    attempted_action_count: int = 0
    executed_action_count: int = 0
    partial_action_count: int = 0
    blocked_action_count: int = 0
    materialized_output_asset_ids: list[str] = Field(default_factory=list)
    missing_output_asset_ids: list[str] = Field(default_factory=list)
    action_results: list[AutoResearchPublicationRepairExecutionActionRead] = Field(default_factory=list)
    success: bool = False
    execution_fingerprint: str


class AutoResearchMethodologyAuditRead(BaseModel):
    generated_at: datetime
    audit_id: str = "methodology_audit_v1"
    protocol_fingerprint: str | None = None
    audit_fingerprint: str
    execution_profile: AutoResearchExecutionProfile = "exploratory"
    primary_metric: str | None = None
    planned_seed_count: int = 0
    completed_seed_count: int = 0
    minimum_completed_seed_count: int = 0
    planned_sweep_labels: list[str] = Field(default_factory=list)
    observed_sweep_labels: list[str] = Field(default_factory=list)
    planned_ablation_systems: list[str] = Field(default_factory=list)
    observed_ablation_systems: list[str] = Field(default_factory=list)
    acceptance_rule_ids: list[str] = Field(default_factory=list)
    satisfied_acceptance_rule_ids: list[str] = Field(default_factory=list)
    required_statistics: list[AcceptanceStatistic] = Field(default_factory=list)
    observed_statistics: list[AcceptanceStatistic] = Field(default_factory=list)
    significance_test_count: int = 0
    adequately_powered_test_count: int = 0
    power_analysis_reported_count: int = 0
    real_literature_count: int = 0
    synthetic_literature_count: int = 0
    literature_minimum: int = 0
    unsupported_claim_count: int = 0
    partial_claim_count: int = 0
    compile_ready: bool = False
    paper_source_package_complete: bool = False
    checks: list[AutoResearchReadinessCheckRead] = Field(default_factory=list)
    score: int = 0
    compliant: bool = False
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AutoResearchCitationCoverageRead(BaseModel):
    literature_item_count: int = 0
    citation_marker_count: int = 0
    cited_literature_count: int = 0
    invalid_citation_indices: list[int] = Field(default_factory=list)
    sections_without_citations: list[str] = Field(default_factory=list)
    has_related_work_section: bool = False
    has_references_section: bool = False


class AutoResearchRelatedWorkMatchRead(BaseModel):
    paper_id: str | None = None
    title: str
    year: int | None = None
    source: str | None = None
    overlap_score: int = 0
    shared_terms: list[str] = Field(default_factory=list)
    gap_alignment_terms: list[str] = Field(default_factory=list)
    rationale: str


class AutoResearchNoveltyAssessmentRead(BaseModel):
    status: AutoResearchNoveltyStatus = "missing_context"
    summary: str
    compared_paper_count: int = 0
    strong_match_count: int = 0
    gap_aligned_paper_count: int = 0
    covered_claim_count: int = 0
    total_claim_count: int = 0
    uncovered_claims: list[str] = Field(default_factory=list)
    top_related_work: list[AutoResearchRelatedWorkMatchRead] = Field(default_factory=list)


class AutoResearchLiteratureGraphNodeRead(BaseModel):
    node_id: str
    node_type: AutoResearchLiteratureGraphNodeKind
    label: str
    source_paper_id: str | None = None
    synthetic: bool = False
    attributes: dict[str, Any] = Field(default_factory=dict)


class AutoResearchLiteratureGraphEdgeRead(BaseModel):
    source_id: str
    relation: AutoResearchLiteratureGraphRelation
    target_id: str
    evidence: str
    weight: int = 1


class AutoResearchLiteratureGraphMatchRead(BaseModel):
    match_id: str
    match_type: Literal["method", "task", "benchmark"]
    paper_id: str | None = None
    paper_title: str
    overlap_score: int = 0
    shared_terms: list[str] = Field(default_factory=list)
    rationale: str


class AutoResearchKnownSotaRead(BaseModel):
    paper_id: str | None = None
    paper_title: str
    method: str | None = None
    dataset: str | None = None
    metric: str | None = None
    score: str | None = None
    evidence: str


class AutoResearchLiteratureGraphRead(BaseModel):
    generated_at: datetime
    graph_id: str = "literature_graph_v1"
    project_id: str
    run_id: str
    paper_nodes: list[AutoResearchLiteratureGraphNodeRead] = Field(default_factory=list)
    method_nodes: list[AutoResearchLiteratureGraphNodeRead] = Field(default_factory=list)
    dataset_nodes: list[AutoResearchLiteratureGraphNodeRead] = Field(default_factory=list)
    metric_nodes: list[AutoResearchLiteratureGraphNodeRead] = Field(default_factory=list)
    claim_nodes: list[AutoResearchLiteratureGraphNodeRead] = Field(default_factory=list)
    edges: list[AutoResearchLiteratureGraphEdgeRead] = Field(default_factory=list)
    similar_methods: list[AutoResearchLiteratureGraphMatchRead] = Field(default_factory=list)
    similar_tasks: list[AutoResearchLiteratureGraphMatchRead] = Field(default_factory=list)
    similar_benchmarks: list[AutoResearchLiteratureGraphMatchRead] = Field(default_factory=list)
    known_sota: list[AutoResearchKnownSotaRead] = Field(default_factory=list)
    real_paper_count: int = 0
    synthetic_paper_count: int = 0
    graph_fingerprint: str


class AutoResearchGapValidationRead(BaseModel):
    gap_id: str
    description: str
    literature_evidence: list[str] = Field(default_factory=list)
    experimentally_testable: bool = False
    validation_target: str | None = None
    status: AutoResearchGapValidityStatus = "missing"
    blockers: list[str] = Field(default_factory=list)


class AutoResearchNoveltyValidationRead(BaseModel):
    generated_at: datetime
    validation_id: str = "novelty_validation_v1"
    project_id: str
    run_id: str
    duplicate_risk: AutoResearchNoveltyRiskLevel = "medium"
    incremental_risk: AutoResearchNoveltyRiskLevel = "medium"
    gap_validity: AutoResearchGapValidityStatus = "missing"
    experiment_coverage_risk: AutoResearchNoveltyRiskLevel = "medium"
    duplicate_risk_detail: str
    incremental_risk_detail: str
    experiment_coverage_detail: str
    recommendation: Literal[
        "proceed",
        "reframe_positioning",
        "change_research_question",
        "change_experiment_design",
        "attach_literature",
    ] = "attach_literature"
    gap_validations: list[AutoResearchGapValidationRead] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    complete: bool = False
    validation_fingerprint: str


class AutoResearchReviewFindingRead(BaseModel):
    id: str
    severity: AutoResearchReviewSeverity
    category: AutoResearchReviewCategory
    summary: str
    detail: str
    supporting_asset_ids: list[str] = Field(default_factory=list)


class AutoResearchRevisionActionRead(BaseModel):
    id: str
    priority: AutoResearchRevisionPriority
    title: str
    detail: str
    finding_ids: list[str] = Field(default_factory=list)


class AutoResearchRunReviewRead(BaseModel):
    project_id: str
    run_id: str
    generated_at: datetime
    selected_candidate_id: str | None = None
    backed_by_bundle_id: str | None = None
    overall_status: AutoResearchReviewStatus = "needs_revision"
    unsupported_claim_risk: AutoResearchUnsupportedClaimRisk = "medium"
    summary: str
    persisted_path: str | None = None
    evidence: AutoResearchReviewEvidenceRead
    citation_coverage: AutoResearchCitationCoverageRead
    novelty_assessment: AutoResearchNoveltyAssessmentRead | None = None
    literature_graph: AutoResearchLiteratureGraphRead | None = None
    literature_graph_path: str | None = None
    novelty_validation: AutoResearchNoveltyValidationRead | None = None
    novelty_validation_path: str | None = None
    experiment_design: AutoResearchExperimentDesignRead | None = None
    experiment_design_path: str | None = None
    failure_analysis: AutoResearchFailureAnalysisRead | None = None
    failure_analysis_path: str | None = None
    research_replan: AutoResearchResearchReplanRead | None = None
    research_replan_path: str | None = None
    benchmark_card: AutoResearchBenchmarkCardRead | None = None
    benchmark_card_path: str | None = None
    research_protocol: AutoResearchResearchProtocolRead | None = None
    research_protocol_path: str | None = None
    methodology_audit: AutoResearchMethodologyAuditRead | None = None
    methodology_audit_path: str | None = None
    publication_readiness: AutoResearchPublicationReadinessRead | None = None
    publication_readiness_path: str | None = None
    contribution_assessment: AutoResearchContributionAssessmentRead | None = None
    contribution_assessment_path: str | None = None
    scores: AutoResearchReviewScoresRead
    findings: list[AutoResearchReviewFindingRead] = Field(default_factory=list)
    revision_plan: list[AutoResearchRevisionActionRead] = Field(default_factory=list)
    revision_dossier: "AutoResearchRevisionDossierRead | None" = None
    revision_dossier_path: str | None = None
    publication_evidence_index: AutoResearchPublicationEvidenceIndexRead | None = None
    publication_evidence_index_path: str | None = None
    reviewer_simulation: AutoResearchReviewerSimulationRead | None = None
    reviewer_simulation_path: str | None = None
    artifact_integrity_audit: AutoResearchArtifactIntegrityAuditRead | None = None
    artifact_integrity_audit_path: str | None = None
    publication_repair_plan: AutoResearchPublicationRepairPlanRead | None = None
    publication_repair_plan_path: str | None = None
    publication_repair_execution: AutoResearchPublicationRepairExecutionRead | None = None
    publication_repair_execution_path: str | None = None


class AutoResearchReviewLoopRoundRead(BaseModel):
    round_index: int = 0
    generated_at: datetime
    fingerprint: str
    overall_status: AutoResearchReviewStatus = "needs_revision"
    unsupported_claim_risk: AutoResearchUnsupportedClaimRisk = "medium"
    summary: str
    review_path: str | None = None
    finding_ids: list[str] = Field(default_factory=list)
    revision_action_ids: list[str] = Field(default_factory=list)
    revision_action_titles: list[str] = Field(default_factory=list)
    blocker_count: int = 0


class AutoResearchReviewLoopIssueRead(BaseModel):
    issue_id: str
    category: AutoResearchReviewCategory
    severity: AutoResearchReviewSeverity
    summary: str
    detail: str
    status: AutoResearchReviewLoopIssueStatus = "open"
    first_seen_round: int = 1
    last_seen_round: int = 1
    finding_ids: list[str] = Field(default_factory=list)
    action_titles: list[str] = Field(default_factory=list)
    supporting_asset_ids: list[str] = Field(default_factory=list)


AutoResearchReviewLoopActionKind = Literal[
    "paper_revision",
    "experiment_repair",
    "claim_downgrade",
    "literature_refresh",
    "publish_package",
    "re_review",
    "manual_review",
]
AutoResearchReviewLoopExecutionRoute = Literal[
    "paper_rebuild",
    "research_replan",
    "experiment_rerun",
    "literature_refresh",
    "publish_rebuild",
    "manual_review",
    "re_review",
]


class AutoResearchReviewLoopActionRead(BaseModel):
    action_id: str
    action_kind: AutoResearchReviewLoopActionKind = "paper_revision"
    repair_kind: AutoResearchRepairActionKind | None = None
    execution_route: AutoResearchReviewLoopExecutionRoute = "paper_rebuild"
    priority: AutoResearchRevisionPriority = "medium"
    title: str
    detail: str
    status: AutoResearchReviewLoopActionStatus = "pending"
    first_seen_round: int = 1
    last_seen_round: int = 1
    completed_round: int | None = None
    finding_ids: list[str] = Field(default_factory=list)
    issue_ids: list[str] = Field(default_factory=list)
    auto_applicable: bool = False
    expected_output_asset_ids: list[str] = Field(default_factory=list)
    terminal_condition: str = "Re-review confirms that the underlying finding no longer recurs."
    requires_rereview: bool = True
    max_auto_rounds: int = 3


class AutoResearchReviewLoopRead(BaseModel):
    project_id: str
    run_id: str
    generated_at: datetime
    persisted_path: str | None = None
    current_round: int = 0
    overall_status: AutoResearchReviewStatus = "needs_revision"
    unsupported_claim_risk: AutoResearchUnsupportedClaimRisk = "medium"
    latest_review_path: str | None = None
    latest_review_fingerprint: str | None = None
    rounds: list[AutoResearchReviewLoopRoundRead] = Field(default_factory=list)
    issues: list[AutoResearchReviewLoopIssueRead] = Field(default_factory=list)
    actions: list[AutoResearchReviewLoopActionRead] = Field(default_factory=list)
    open_issue_count: int = 0
    resolved_issue_count: int = 0
    pending_action_count: int = 0
    completed_action_count: int = 0
    pending_revision_actions: list[str] = Field(default_factory=list)
    paper_revision_action_count: int = 0
    experiment_repair_action_count: int = 0
    claim_downgrade_action_count: int = 0
    literature_refresh_action_count: int = 0
    re_review_action_count: int = 0
    manual_review_action_count: int = 0
    next_review_required: bool = False
    auto_revision_round_limit: int = 3
    auto_revision_rounds_remaining: int = 0


class AutoResearchRevisionDossierItemRead(BaseModel):
    item_id: str
    finding_id: str | None = None
    issue_id: str | None = None
    severity: AutoResearchReviewSeverity = "warning"
    category: AutoResearchReviewCategory = "context"
    summary: str
    response: str
    status: AutoResearchRevisionDossierItemStatus = "action_required"
    required_for_final_publish: bool = False
    action_ids: list[str] = Field(default_factory=list)
    action_titles: list[str] = Field(default_factory=list)
    supporting_asset_ids: list[str] = Field(default_factory=list)


class AutoResearchRevisionDossierRead(BaseModel):
    generated_at: datetime
    dossier_id: str = "revision_dossier_v1"
    review_round: int = 0
    review_fingerprint: str | None = None
    review_path: str | None = None
    overall_status: AutoResearchReviewStatus = "needs_revision"
    publication_tier: AutoResearchPublicationTier = "exploratory"
    publication_readiness_score: int = 0
    methodology_audit_score: int = 0
    methodology_audit_compliant: bool = False
    open_issue_count: int = 0
    resolved_issue_count: int = 0
    pending_action_count: int = 0
    completed_action_count: int = 0
    blocker_count: int = 0
    final_blocker_count: int = 0
    required_action_titles: list[str] = Field(default_factory=list)
    items: list[AutoResearchRevisionDossierItemRead] = Field(default_factory=list)
    complete: bool = False
    dossier_fingerprint: str


class AutoResearchDeploymentRefRead(BaseModel):
    deployment_id: str
    label: str
    listed_at: datetime


class AutoResearchPublicationManifestRead(BaseModel):
    publication_id: str
    project_id: str
    project_title: str | None = None
    run_id: str
    topic: str
    paper_title: str
    paper_summary: str | None = None
    generated_at: datetime
    updated_at: datetime
    selected_candidate_id: str | None = None
    benchmark_name: str | None = None
    task_family: TaskFamily | None = None
    package_id: str
    package_fingerprint: str | None = None
    bundle_kind: AutoResearchPublishBundleKind = "review_bundle"
    review_bundle_ready: bool = False
    final_publish_ready: bool = False
    publication_tier: AutoResearchPublicationTier = "exploratory"
    publication_readiness_score: int = 0
    benchmark_card_path: str | None = None
    benchmark_card_sha256: str | None = None
    research_protocol_path: str | None = None
    research_protocol_sha256: str | None = None
    methodology_audit_path: str | None = None
    methodology_audit_sha256: str | None = None
    publication_readiness_path: str | None = None
    publication_readiness_sha256: str | None = None
    experiment_design_path: str | None = None
    experiment_design_sha256: str | None = None
    failure_analysis_path: str | None = None
    failure_analysis_sha256: str | None = None
    research_replan_path: str | None = None
    research_replan_sha256: str | None = None
    contribution_assessment_path: str | None = None
    contribution_assessment_sha256: str | None = None
    literature_graph_path: str | None = None
    literature_graph_sha256: str | None = None
    novelty_validation_path: str | None = None
    novelty_validation_sha256: str | None = None
    revision_dossier_path: str | None = None
    revision_dossier_sha256: str | None = None
    publication_evidence_index_path: str | None = None
    publication_evidence_index_sha256: str | None = None
    artifact_integrity_audit_path: str | None = None
    artifact_integrity_audit_sha256: str | None = None
    reviewer_simulation_path: str | None = None
    reviewer_simulation_sha256: str | None = None
    publication_repair_plan_path: str | None = None
    publication_repair_plan_sha256: str | None = None
    publication_repair_execution_path: str | None = None
    publication_repair_execution_sha256: str | None = None
    submission_manifest_path: str | None = None
    submission_manifest_sha256: str | None = None
    reproducibility_checklist_path: str | None = None
    reproducibility_checklist_sha256: str | None = None
    reviewer_response_path: str | None = None
    reviewer_response_sha256: str | None = None
    claim_evidence_index_path: str | None = None
    claim_evidence_index_sha256: str | None = None
    lineage_archive_path: str | None = None
    lineage_archive_sha256: str | None = None
    archive_ready: bool = False
    archive_current: bool = False
    review_round: int = 0
    review_fingerprint: str | None = None
    publication_manifest_path: str
    publish_manifest_path: str
    publish_archive_path: str
    paper_path: str | None = None
    compiled_paper_path: str | None = None
    compiled_paper_sha256: str | None = None
    paper_compile_output_paths: list[str] = Field(default_factory=list)
    code_package_path: str | None = None
    code_package_sha256: str | None = None
    run_api_path: str
    registry_api_path: str
    publish_api_path: str
    publish_download_path: str
    paper_download_path: str | None = None
    compiled_paper_download_path: str | None = None
    code_package_download_path: str | None = None
    deployments: list[AutoResearchDeploymentRefRead] = Field(default_factory=list)


class AutoResearchDeploymentPublicationRead(BaseModel):
    deployment_id: str
    listed_at: datetime
    publication: AutoResearchPublicationManifestRead


class AutoResearchDeploymentFiltersRead(BaseModel):
    search: str | None = None
    final_publish_ready: bool | None = None
    bundle_kind: AutoResearchPublishBundleKind | None = None
    task_family: TaskFamily | None = None


class AutoResearchDeploymentSummaryRead(BaseModel):
    deployment_id: str
    label: str
    created_at: datetime
    updated_at: datetime
    publication_count: int = 0
    project_count: int = 0
    final_publish_ready_count: int = 0
    latest_publication_id: str | None = None
    latest_run_id: str | None = None


class AutoResearchDeploymentRead(BaseModel):
    deployment_id: str
    label: str
    created_at: datetime
    updated_at: datetime
    publication_count: int = 0
    filtered_publication_count: int = 0
    project_count: int = 0
    final_publish_ready_count: int = 0
    latest_publication_id: str | None = None
    latest_run_id: str | None = None
    filters: AutoResearchDeploymentFiltersRead = Field(default_factory=AutoResearchDeploymentFiltersRead)
    publications: list[AutoResearchDeploymentPublicationRead] = Field(default_factory=list)


class AutoResearchDeploymentListRead(BaseModel):
    deployment_count: int = 0
    publication_count: int = 0
    deployments: list[AutoResearchDeploymentSummaryRead] = Field(default_factory=list)


class AutoResearchPublishExportRequest(BaseModel):
    deployment_id: str | None = None
    deployment_label: str | None = None


class AutoResearchPublishPackageRead(BaseModel):
    project_id: str
    run_id: str
    package_id: str
    generated_at: datetime
    selected_candidate_id: str | None = None
    source_bundle_id: str | None = None
    status: AutoResearchPublishStatus = "revision_required"
    publish_ready: bool = False
    review_bundle_ready: bool = False
    final_publish_ready: bool = False
    publication_tier: AutoResearchPublicationTier = "exploratory"
    publication_readiness_score: int = 0
    benchmark_card_path: str | None = None
    experiment_design_path: str | None = None
    failure_analysis_path: str | None = None
    research_replan_path: str | None = None
    research_protocol_path: str | None = None
    methodology_audit_path: str | None = None
    contribution_assessment_path: str | None = None
    literature_graph_path: str | None = None
    novelty_validation_path: str | None = None
    revision_dossier_path: str | None = None
    publication_evidence_index_path: str | None = None
    artifact_integrity_audit_path: str | None = None
    reviewer_simulation_path: str | None = None
    publication_repair_plan_path: str | None = None
    publication_repair_execution_path: str | None = None
    submission_manifest_path: str | None = None
    reproducibility_checklist_path: str | None = None
    reviewer_response_path: str | None = None
    claim_evidence_index_path: str | None = None
    lineage_archive_path: str | None = None
    submission_ready: bool = False
    submission_asset_count: int = 0
    reproducibility_checklist_complete: bool = False
    reviewer_response_complete: bool = False
    claim_evidence_index_complete: bool = False
    lineage_archive_complete: bool = False
    completeness_status: AutoResearchPublishCompletenessStatus = "incomplete"
    review_path: str | None = None
    publication_readiness_path: str | None = None
    manifest_path: str | None = None
    archive_path: str | None = None
    archive_manifest_path: str | None = None
    publication_id: str | None = None
    publication_manifest_path: str | None = None
    code_package_path: str | None = None
    deployment_ids: list[str] = Field(default_factory=list)
    package_fingerprint: str | None = None
    review_round: int = 0
    review_fingerprint: str | None = None
    archive_status: AutoResearchPublishArchiveStatus = "missing"
    archive_ready: bool = False
    archive_current: bool = False
    archive_generated_at: datetime | None = None
    archive_bundle_kind: AutoResearchPublishBundleKind | None = None
    archive_review_round: int | None = None
    archive_review_fingerprint: str | None = None
    asset_count: int = 0
    existing_asset_count: int = 0
    missing_required_asset_count: int = 0
    missing_final_asset_count: int = 0
    blocker_count: int = 0
    final_blocker_count: int = 0
    revision_count: int = 0
    blockers: list[str] = Field(default_factory=list)
    final_blockers: list[str] = Field(default_factory=list)
    revision_actions: list[str] = Field(default_factory=list)
    required_assets: list[AutoResearchBundleAssetRead] = Field(default_factory=list)
    final_required_assets: list[AutoResearchBundleAssetRead] = Field(default_factory=list)
    optional_assets: list[AutoResearchBundleAssetRead] = Field(default_factory=list)


class AutoResearchPublishExportRead(BaseModel):
    project_id: str
    run_id: str
    package_id: str
    generated_at: datetime
    publication_id: str | None = None
    publication_manifest_path: str | None = None
    deployment_id: str | None = None
    deployment_label: str | None = None
    bundle_kind: AutoResearchPublishBundleKind = "review_bundle"
    review_bundle_ready: bool = False
    final_publish_ready: bool = False
    file_name: str
    archive_path: str
    archive_manifest_path: str | None = None
    code_package_path: str | None = None
    code_package_download_path: str | None = None
    package_fingerprint: str | None = None
    review_round: int = 0
    review_fingerprint: str | None = None
    download_path: str
    asset_count: int = 0
    included_asset_count: int = 0
    omitted_asset_count: int = 0
    download_ready: bool = True


class AutoResearchBridgeImportedArtifactRead(BaseModel):
    imported_at: datetime
    source: Literal["inline", "file"]
    artifact_path: str
    summary: str
    primary_metric: str
    objective_score: float | None = None


class AutoResearchBridgeSessionRead(BaseModel):
    session_id: str
    created_at: datetime
    updated_at: datetime
    status: AutoResearchBridgeSessionStatus = "waiting_result"
    candidate_id: str
    candidate_title: str
    round_index: int
    goal: str
    strategy: str
    handoff_dir: str
    manifest_path: str
    instructions_path: str
    code_path: str
    benchmark_path: str | None = None
    result_path: str
    last_polled_at: datetime | None = None
    external_status: str | None = None
    last_error: str | None = None
    imported_artifact: AutoResearchBridgeImportedArtifactRead | None = None


class AutoResearchBridgeCheckpointRead(BaseModel):
    checkpoint_id: str
    created_at: datetime
    kind: AutoResearchBridgeCheckpointKind
    summary: str
    detail: str | None = None
    session_id: str | None = None


class AutoResearchBridgeNotificationRead(BaseModel):
    notification_id: str
    created_at: datetime
    event: AutoResearchBridgeNotificationEvent
    channel: AutoResearchBridgeNotificationChannel
    status: AutoResearchBridgeNotificationStatus = "sent"
    target: str | None = None
    message: str
    delivered_at: datetime | None = None
    error: str | None = None


class AutoResearchExperimentBridgeRead(BaseModel):
    project_id: str
    run_id: str
    enabled: bool = False
    config: AutoResearchExperimentBridgeConfig | None = None
    persisted_path: str | None = None
    status: AutoResearchBridgeStatus = "inactive"
    active_session_id: str | None = None
    latest_session_id: str | None = None
    open_session_count: int = 0
    imported_session_count: int = 0
    session_count: int = 0
    checkpoint_count: int = 0
    notification_count: int = 0
    current_session: AutoResearchBridgeSessionRead | None = None
    sessions: list[AutoResearchBridgeSessionRead] = Field(default_factory=list)
    checkpoints: list[AutoResearchBridgeCheckpointRead] = Field(default_factory=list)
    notifications: list[AutoResearchBridgeNotificationRead] = Field(default_factory=list)


class AutoResearchOperatorProjectActionsRead(BaseModel):
    start_run: bool = True
    create_idea_brief: bool = True
    create_run_from_brief: bool = True
    build_meta_analysis: bool = True
    build_system_evaluation: bool = True


class AutoResearchOperatorConsoleFiltersRead(BaseModel):
    search: str | None = None
    status: AutoResearchRunStatus | None = None
    publish_status: AutoResearchPublishStatus | None = None
    publication_tier: AutoResearchPublicationTier | None = None
    review_risk: AutoResearchUnsupportedClaimRisk | None = None
    novelty_status: AutoResearchNoveltyStatus | None = None
    budget_status: AutoResearchBudgetStatus | None = None
    queue_priority: AutoResearchQueuePriority | None = None


class AutoResearchOperatorRunActionsRead(BaseModel):
    resume: bool = False
    retry: bool = False
    cancel: bool = False
    refresh_bridge: bool = False
    import_bridge_result: bool = False
    refresh_review: bool = False
    apply_review_actions: bool = False
    rebuild_paper: bool = False
    export_publish: bool = False
    download_publish: bool = False
    replan_research: bool = False
    update_controls: bool = False


class AutoResearchOperatorRunSummaryRead(BaseModel):
    run_id: str
    topic: str
    status: AutoResearchRunStatus
    created_at: datetime
    updated_at: datetime
    task_family: TaskFamily | None = None
    benchmark_name: str | None = None
    selected_candidate_id: str | None = None
    candidate_count: int = 0
    selected_count: int = 0
    active_count: int = 0
    failed_count: int = 0
    eliminated_count: int = 0
    latest_job_status: AutoResearchJobStatus | None = None
    active_job_id: str | None = None
    cancel_requested: bool = False
    queue_priority: AutoResearchQueuePriority = "normal"
    budget_status: AutoResearchBudgetStatus = "default"
    max_rounds: int = 3
    candidate_execution_limit: int | None = None
    execution_profile: AutoResearchExecutionProfile = "exploratory"
    executed_candidate_count: int = 0
    recovery_count: int = 0
    bridge_status: AutoResearchBridgeStatus | None = None
    bridge_target_label: str | None = None
    bridge_session_status: AutoResearchBridgeSessionStatus | None = None
    bridge_session_count: int = 0
    review_round: int = 0
    open_issue_count: int = 0
    pending_action_count: int = 0
    completed_action_count: int = 0
    publish_status: AutoResearchPublishStatus | None = None
    publish_ready: bool = False
    review_bundle_ready: bool = False
    final_publish_ready: bool = False
    publication_tier: AutoResearchPublicationTier | None = None
    publication_readiness_score: int = 0
    research_protocol_complete: bool = False
    research_protocol_blocker_count: int = 0
    research_protocol_blockers: list[str] = Field(default_factory=list)
    methodology_audit_score: int = 0
    methodology_audit_compliant: bool = False
    methodology_audit_blocker_count: int = 0
    methodology_audit_blockers: list[str] = Field(default_factory=list)
    methodology_audit_checks_passed: int = 0
    methodology_audit_checks_total: int = 0
    revision_dossier_complete: bool = False
    revision_dossier_blocker_count: int = 0
    revision_dossier_required_actions: list[str] = Field(default_factory=list)
    benchmark_card_publication_grade: bool = False
    benchmark_card_provenance_complete: bool = False
    benchmark_card_total_examples: int = 0
    benchmark_card_blocker_count: int = 0
    benchmark_card_blockers: list[str] = Field(default_factory=list)
    publication_evidence_index_complete: bool = False
    publication_evidence_index_missing_count: int = 0
    publication_evidence_index_blockers: list[str] = Field(default_factory=list)
    reviewer_simulation_complete: bool = False
    reviewer_simulation_average_score: float = 0.0
    reviewer_simulation_minimum_score: int = 0
    reviewer_simulation_minimum_decision: AutoResearchReviewerDecision | None = None
    reviewer_simulation_weak_reject_or_worse_count: int = 0
    reviewer_simulation_publication_blocker_count: int = 0
    reviewer_simulation_response_plan_action_count: int = 0
    reviewer_simulation_blockers: list[str] = Field(default_factory=list)
    weakest_reviewer_role: AutoResearchReviewerRole | None = None
    contribution_score: int = 0
    novelty_duplicate_risk: AutoResearchNoveltyRiskLevel | None = None
    novelty_incremental_risk: AutoResearchNoveltyRiskLevel | None = None
    experiment_design_completeness: AutoResearchExperimentDesignCompleteness | None = None
    next_research_action: AutoResearchResearchActionRecommendation | None = None
    next_research_action_detail: str | None = None
    artifact_integrity_audit_complete: bool = False
    artifact_integrity_audit_blocker_count: int = 0
    artifact_integrity_audit_warning_count: int = 0
    artifact_integrity_audit_untraced_asset_count: int = 0
    artifact_integrity_audit_missing_lineage_target_count: int = 0
    artifact_integrity_audit_blockers: list[str] = Field(default_factory=list)
    publication_repair_plan_complete: bool = False
    publication_repair_plan_pending_count: int = 0
    publication_repair_plan_blocked_count: int = 0
    publication_repair_plan_auto_applicable_count: int = 0
    publication_repair_plan_next_actions: list[str] = Field(default_factory=list)
    publication_repair_execution_success: bool = False
    publication_repair_execution_attempted_count: int = 0
    publication_repair_execution_executed_count: int = 0
    publication_repair_execution_partial_count: int = 0
    publication_repair_execution_blocked_count: int = 0
    publication_repair_execution_missing_outputs: list[str] = Field(default_factory=list)
    publication_grade_benchmark: bool = False
    publication_blocker_count: int = 0
    publication_blockers: list[str] = Field(default_factory=list)
    readiness_checks_passed: int = 0
    readiness_checks_total: int = 0
    archive_ready: bool = False
    review_risk: AutoResearchUnsupportedClaimRisk | None = None
    novelty_status: AutoResearchNoveltyStatus | None = None
    blocker_count: int = 0
    final_blocker_count: int = 0
    revision_count: int = 0
    revision_actions: list[str] = Field(default_factory=list)


class AutoResearchOperatorRunDetailRead(BaseModel):
    run: AutoResearchRunRead
    execution: AutoResearchRunExecutionRead
    bridge: AutoResearchExperimentBridgeRead | None = None
    registry: AutoResearchRunRegistryRead
    registry_views: AutoResearchRunRegistryViewsRead
    review: AutoResearchRunReviewRead | None = None
    review_loop: AutoResearchReviewLoopRead | None = None
    publish: AutoResearchPublishPackageRead | None = None
    actions: AutoResearchOperatorRunActionsRead


class AutoResearchOperatorConsoleRead(BaseModel):
    project_id: str
    run_count: int = 0
    brief_count: int = 0
    latest_brief_id: str | None = None
    latest_brief_status: str | None = None
    latest_brief_original_idea: str | None = None
    latest_brief_hypothesis_count: int = 0
    latest_brief_selected_direction_id: str | None = None
    latest_brief_selected_hypothesis_id: str | None = None
    latest_brief_next_action: str | None = None
    latest_brief_literature_scout_ready: bool = False
    latest_brief_gap_count: int = 0
    latest_brief_recommended_gap: str | None = None
    filtered_run_count: int = 0
    latest_run_id: str | None = None
    selected_run_id: str | None = None
    filters: AutoResearchOperatorConsoleFiltersRead = Field(default_factory=AutoResearchOperatorConsoleFiltersRead)
    actions: AutoResearchOperatorProjectActionsRead
    queue: "AutoResearchQueueTelemetryRead | None" = None
    workers: list["AutoResearchWorkerState"] = Field(default_factory=list)
    meta_analysis: AutoResearchCrossRunMetaAnalysisRead | None = None
    system_evaluation: AutoResearchSystemEvaluationRead | None = None
    runs: list[AutoResearchOperatorRunSummaryRead] = Field(default_factory=list)
    current_run: AutoResearchOperatorRunDetailRead | None = None


class AutoResearchExecutionJob(BaseModel):
    id: str
    project_id: str
    run_id: str
    action: AutoResearchJobAction
    priority: AutoResearchQueuePriority = "normal"
    status: AutoResearchJobStatus = "queued"
    lease_id: str | None = None
    detail: str | None = None
    enqueued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    cancellation_requested_at: datetime | None = None
    attempt_count: int = 0
    recovery_count: int = 0
    last_recovered_at: datetime | None = None
    worker_id: str | None = None
    error: str | None = None


class AutoResearchWorkerState(BaseModel):
    worker_id: str | None = None
    status: AutoResearchWorkerStatus = "idle"
    current_job_id: str | None = None
    current_run_id: str | None = None
    current_lease_id: str | None = None
    heartbeat_at: datetime | None = None
    lease_expires_at: datetime | None = None
    last_started_at: datetime | None = None
    last_completed_at: datetime | None = None
    last_recovered_at: datetime | None = None
    processed_jobs: int = 0
    queue_depth: int = 0
    recovered_job_count: int = 0
    stale: bool = False
    last_error: str | None = None


class AutoResearchQueueTelemetryRead(BaseModel):
    queue_depth: int = 0
    total_jobs: int = 0
    queued_jobs: int = 0
    leased_jobs: int = 0
    running_jobs: int = 0
    succeeded_jobs: int = 0
    failed_jobs: int = 0
    canceled_jobs: int = 0
    worker_count: int = 0
    active_workers: int = 0
    idle_workers: int = 0
    stale_workers: int = 0
    total_processed_jobs: int = 0
    total_recovered_jobs: int = 0
    last_recovered_at: datetime | None = None
    last_job_started_at: datetime | None = None
    last_job_finished_at: datetime | None = None


class AutoResearchRunExecutionRead(BaseModel):
    project_id: str
    run_id: str
    jobs: list[AutoResearchExecutionJob] = Field(default_factory=list)
    active_job_id: str | None = None
    cancel_requested: bool = False
    queue: AutoResearchQueueTelemetryRead | None = None
    worker: AutoResearchWorkerState | None = None
    workers: list[AutoResearchWorkerState] = Field(default_factory=list)


class AutoResearchExecutionCommandResponse(BaseModel):
    run_id: str
    job_id: str | None = None
    status: AutoResearchCommandStatus = "accepted"
    execution: AutoResearchRunExecutionRead


class AutoResearchRunControlUpdateRead(BaseModel):
    run: AutoResearchRunRead
    execution: AutoResearchRunExecutionRead


class AutoResearchBridgeImportRequest(BaseModel):
    session_id: str | None = None
    summary: str
    objective_score: float
    primary_metric: str = "macro_f1"
    objective_system: str = "candidate_system"
    baseline_system: str = "baseline"
    baseline_score: float | None = None
    key_findings: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("summary must not be empty")
        return cleaned

    @field_validator("primary_metric", "objective_system", "baseline_system")
    @classmethod
    def validate_non_empty_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("field must not be empty")
        return cleaned


class AutoResearchBridgeUpdateRead(BaseModel):
    bridge: AutoResearchExperimentBridgeRead
    run: AutoResearchRunRead
    execution: AutoResearchRunExecutionRead
    imported: bool = False
    resumed: bool = False
    source: Literal["none", "inline", "file"] = "none"


class AutoResearchReviewLoopApplyRequest(BaseModel):
    expected_round: int
    expected_review_fingerprint: str

    @field_validator("expected_round")
    @classmethod
    def validate_expected_round(cls, value: int) -> int:
        if value < 1:
            raise ValueError("expected_round must be at least 1")
        return value


class AutoResearchReviewLoopAutoApplyRequest(BaseModel):
    max_rounds: int = 3
    expected_review_fingerprint: str | None = None

    @field_validator("max_rounds")
    @classmethod
    def validate_max_rounds(cls, value: int) -> int:
        if value < 1:
            raise ValueError("max_rounds must be at least 1")
        if value > 10:
            raise ValueError("max_rounds must be at most 10")
        return value


AutoResearchReviewLoopAutoApplyStepStatus = Literal[
    "applied",
    "rerun_required",
    "repair_incomplete",
    "blocked",
    "round_limit_reached",
    "no_pending_actions",
]


class AutoResearchReviewLoopAutoApplyStepRead(BaseModel):
    round_before: int
    review_fingerprint_before: str | None = None
    status: AutoResearchReviewLoopAutoApplyStepStatus = "applied"
    detail: str
    applied_action_ids: list[str] = Field(default_factory=list)
    repair_execution: AutoResearchPublicationRepairExecutionRead | None = None
    queued_rerun_required: bool = False


class AutoResearchReviewLoopApplyRead(BaseModel):
    run: AutoResearchRunRead
    review: AutoResearchRunReviewRead
    review_loop: AutoResearchReviewLoopRead
    repair_execution: AutoResearchPublicationRepairExecutionRead | None = None
    applied_action_ids: list[str] = Field(default_factory=list)
    queued_rerun_required: bool = False


class AutoResearchReviewLoopAutoApplyRead(BaseModel):
    run: AutoResearchRunRead
    review: AutoResearchRunReviewRead
    review_loop: AutoResearchReviewLoopRead
    steps: list[AutoResearchReviewLoopAutoApplyStepRead] = Field(default_factory=list)
    step_count: int = 0
    applied_action_ids: list[str] = Field(default_factory=list)
    completed: bool = False
    blocked: bool = False
    queued_rerun_required: bool = False
    stop_reason: str


class AutoResearchResearchReplanApplyRead(BaseModel):
    run: AutoResearchRunRead
    review: AutoResearchRunReviewRead
    review_loop: AutoResearchReviewLoopRead
    repair_execution: AutoResearchPublicationRepairExecutionRead | None = None
    applied_action_ids: list[str] = Field(default_factory=list)
    queued_rerun_required: bool = False
