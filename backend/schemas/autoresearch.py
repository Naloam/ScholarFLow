from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


TaskFamily = Literal["text_classification", "tabular_classification", "ir_reranking"]
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
    "run_plan_json",
    "run_spec_json",
    "run_artifact_json",
    "run_generated_code",
    "run_paper_markdown",
    "run_narrative_report_markdown",
    "run_claim_evidence_matrix_json",
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
    "narrative_report",
    "claim_evidence_matrix",
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
]
AutoResearchReviewSeverity = Literal["info", "warning", "error"]
AutoResearchReviewCategory = Literal[
    "artifact",
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
AutoResearchBudgetStatus = Literal["default", "constrained"]
AutoResearchClaimSupportStatus = Literal["supported", "partial", "unsupported"]
AutoResearchClaimCategory = Literal["problem", "method", "result", "context", "limitation"]
AutoResearchEvidenceSourceKind = Literal["plan", "portfolio", "artifact", "literature", "attempts"]
AutoResearchFigureAssetKind = Literal["table", "chart", "diagram"]
AutoResearchFigureStatus = Literal["planned", "ready", "not_available"]
AutoResearchPaperRevisionStatus = Literal["drafted", "needs_review", "revising", "ready_for_publish"]
AutoResearchPaperRevisionDiffStatus = Literal["initial", "updated", "unchanged"]
AutoResearchPaperRevisionActionMaterializationStatus = Literal["pending", "completed"]
AutoResearchPaperSourceKind = Literal["latex", "bibtex", "json", "markdown", "shell"]
AutoResearchPaperRevisionActionStatus = Literal["open", "done"]
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
        )


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
    request: AutoResearchRunConfig | None = None
    task_family: TaskFamily | None = None
    benchmark: BenchmarkSource | None = None
    execution_backend: ExecutionBackendSpec | None = None
    program: ResearchProgram | None = None
    plan: ResearchPlan | None = None
    spec: ExperimentSpec | None = None
    literature: list[LiteratureInsight] = Field(default_factory=list)
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
    paper_sources_dir: str | None = None
    paper_section_rewrite_packets_dir: str | None = None
    paper_latex_source: str | None = None
    paper_latex_path: str | None = None
    paper_bibliography_bib: str | None = None
    paper_bibliography_path: str | None = None
    paper_sources_manifest: AutoResearchPaperSourcesManifestRead | None = None
    paper_sources_manifest_path: str | None = None
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
    generated_code: AutoResearchRegistryAssetRef | None = None
    paper_markdown: AutoResearchRegistryAssetRef | None = None
    narrative_report_markdown: AutoResearchRegistryAssetRef | None = None
    claim_evidence_matrix_json: AutoResearchRegistryAssetRef | None = None
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
    scores: AutoResearchReviewScoresRead
    findings: list[AutoResearchReviewFindingRead] = Field(default_factory=list)
    revision_plan: list[AutoResearchRevisionActionRead] = Field(default_factory=list)


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


class AutoResearchReviewLoopActionRead(BaseModel):
    action_id: str
    priority: AutoResearchRevisionPriority = "medium"
    title: str
    detail: str
    status: AutoResearchReviewLoopActionStatus = "pending"
    first_seen_round: int = 1
    last_seen_round: int = 1
    completed_round: int | None = None
    finding_ids: list[str] = Field(default_factory=list)
    issue_ids: list[str] = Field(default_factory=list)


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
    completeness_status: AutoResearchPublishCompletenessStatus = "incomplete"
    review_path: str | None = None
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


class AutoResearchOperatorConsoleFiltersRead(BaseModel):
    search: str | None = None
    status: AutoResearchRunStatus | None = None
    publish_status: AutoResearchPublishStatus | None = None
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
    review_risk: AutoResearchUnsupportedClaimRisk | None = None
    novelty_status: AutoResearchNoveltyStatus | None = None
    blocker_count: int = 0
    revision_count: int = 0


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
    filtered_run_count: int = 0
    latest_run_id: str | None = None
    selected_run_id: str | None = None
    filters: AutoResearchOperatorConsoleFiltersRead = Field(default_factory=AutoResearchOperatorConsoleFiltersRead)
    actions: AutoResearchOperatorProjectActionsRead
    queue: "AutoResearchQueueTelemetryRead | None" = None
    workers: list["AutoResearchWorkerState"] = Field(default_factory=list)
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


class AutoResearchReviewLoopApplyRead(BaseModel):
    run: AutoResearchRunRead
    review: AutoResearchRunReviewRead
    review_loop: AutoResearchReviewLoopRead
