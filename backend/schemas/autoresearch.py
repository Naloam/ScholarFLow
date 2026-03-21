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
AutoResearchJobAction = Literal["run", "resume", "retry"]
AutoResearchJobStatus = Literal["queued", "leased", "running", "succeeded", "failed", "canceled"]
AutoResearchWorkerStatus = Literal["idle", "starting", "running", "stopping"]
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
AutoResearchPublishStatus = Literal["publish_ready", "revision_required", "blocked"]
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
    benchmark: BenchmarkSource | None = None
    execution_backend: ExecutionBackendSpec | None = None
    auto_search_literature: bool = False
    auto_fetch_literature: bool = False


class AutoResearchRunConfig(BaseModel):
    task_family_hint: TaskFamily | None = None
    paper_ids: list[str] | None = None
    max_rounds: int = 3
    benchmark: BenchmarkSource | None = None
    execution_backend: ExecutionBackendSpec | None = None
    auto_search_literature: bool = False
    auto_fetch_literature: bool = False
    docker_image: str | None = None

    @classmethod
    def from_request(cls, payload: AutoResearchRunRequest) -> "AutoResearchRunConfig":
        return cls(
            task_family_hint=payload.task_family_hint,
            paper_ids=payload.paper_ids,
            max_rounds=payload.max_rounds,
            benchmark=payload.benchmark,
            execution_backend=payload.execution_backend,
            auto_search_literature=payload.auto_search_literature,
            auto_fetch_literature=payload.auto_fetch_literature,
            docker_image=payload.docker_image,
        )


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
    alternative: SignificanceAlternative = "two_sided"
    method: SignificanceTestMethod = "paired_sign_flip_exact"
    p_value: float
    adjusted_p_value: float | None = None
    correction: MultipleComparisonCorrection | None = None
    effect_size: float
    significant: bool = False
    sample_count: int = 0
    detail: str


class FailureRecord(BaseModel):
    scope: FailureScope = "seed"
    sweep_label: str
    seed: int | None = None
    category: FailureCategory = "unknown_failure"
    summary: str
    detail: str
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
    sections_without_citations: list[str] = Field(default_factory=list)
    has_related_work_section: bool = False


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
    scores: AutoResearchReviewScoresRead
    findings: list[AutoResearchReviewFindingRead] = Field(default_factory=list)
    revision_plan: list[AutoResearchRevisionActionRead] = Field(default_factory=list)


class AutoResearchPublishPackageRead(BaseModel):
    project_id: str
    run_id: str
    package_id: str
    generated_at: datetime
    selected_candidate_id: str | None = None
    source_bundle_id: str | None = None
    status: AutoResearchPublishStatus = "revision_required"
    publish_ready: bool = False
    review_path: str | None = None
    manifest_path: str | None = None
    archive_path: str | None = None
    asset_count: int = 0
    existing_asset_count: int = 0
    missing_required_asset_count: int = 0
    blocker_count: int = 0
    revision_count: int = 0
    blockers: list[str] = Field(default_factory=list)
    revision_actions: list[str] = Field(default_factory=list)
    required_assets: list[AutoResearchBundleAssetRead] = Field(default_factory=list)
    optional_assets: list[AutoResearchBundleAssetRead] = Field(default_factory=list)


class AutoResearchPublishExportRead(BaseModel):
    project_id: str
    run_id: str
    package_id: str
    generated_at: datetime
    file_name: str
    archive_path: str
    download_path: str
    asset_count: int = 0
    download_ready: bool = True


class AutoResearchExecutionJob(BaseModel):
    id: str
    project_id: str
    run_id: str
    action: AutoResearchJobAction
    status: AutoResearchJobStatus = "queued"
    detail: str | None = None
    enqueued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    cancellation_requested_at: datetime | None = None
    attempt_count: int = 0
    worker_id: str | None = None
    error: str | None = None


class AutoResearchWorkerState(BaseModel):
    worker_id: str | None = None
    status: AutoResearchWorkerStatus = "idle"
    current_job_id: str | None = None
    current_run_id: str | None = None
    heartbeat_at: datetime | None = None
    processed_jobs: int = 0
    queue_depth: int = 0
    last_error: str | None = None


class AutoResearchRunExecutionRead(BaseModel):
    project_id: str
    run_id: str
    jobs: list[AutoResearchExecutionJob] = Field(default_factory=list)
    active_job_id: str | None = None
    cancel_requested: bool = False
    worker: AutoResearchWorkerState | None = None


class AutoResearchExecutionCommandResponse(BaseModel):
    run_id: str
    job_id: str | None = None
    status: AutoResearchCommandStatus = "accepted"
    execution: AutoResearchRunExecutionRead
