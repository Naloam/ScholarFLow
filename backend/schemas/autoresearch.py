"""Trimmed survivor set of the retired autoresearch schema module.

The orchestrator-era schemas were physically retired (S15). Only the
symbols still imported by research_harness / sandbox / literature_connectors
survive here, extracted verbatim from the original module.
"""

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator

TaskFamily = Literal["text_classification", "tabular_classification", "ir_reranking", "llm_evaluation"]

AutoResearchPaperTier = Literal[
    "technical_report",
    "workshop_candidate",
    "conference_candidate",
    "strong_conference_candidate",
]

BenchmarkKind = Literal[
    "builtin",
    "remote_csv",
    "remote_jsonl",
    "remote_json",
    "huggingface_file",
    "openml_file",
    "beir_json",
    "scifact_json",
]

ExecutionBackendKind = Literal["auto", "local", "docker", "docker_gpu", "command"]

AutoResearchCacheFreshness = Literal["fresh", "stale", "unknown", "not_applicable"]

AutoResearchNoveltyRiskLevel = Literal["low", "medium", "high"]

AutoResearchMemoryItemType = Literal[
    "paper",
    "method",
    "dataset",
    "metric",
    "benchmark",
    "reported_result",
    "implementation",
    "negative_finding",
    "blocker",
    "project_conclusion",
    "reviewer_finding",
    "compliance_release_caveat",
]

AutoResearchMemoryEvidenceGrade = Literal[
    "unsupported",
    "weak",
    "review_only",
    "artifact_supported",
    "publication_candidate",
]

AutoResearchMemorySourceClass = Literal[
    "literature",
    "experiment",
    "benchmark",
    "project",
    "review",
    "runbook",
    "compliance",
    "release",
]

AutoResearchMemoryExtractionLevel = Literal[
    "metadata",
    "abstract",
    "full_text",
    "artifact",
    "ledger",
    "project_summary",
]

AutoResearchMemoryCurrentness = Literal["fresh", "aging", "stale", "unknown", "revoked"]

AutoResearchMemoryReusePolicy = Literal[
    "discovery_only",
    "requires_current_project_revalidation",
    "internal_only",
    "blocked",
    "expired",
]

AutoResearchMemoryNegativeStatus = Literal[
    "none",
    "negative_finding",
    "blocker",
    "policy_blocked",
    "revoked",
]

AutoResearchContributionType = Literal[
    "new_method",
    "new_system",
    "experimental_finding",
    "new_benchmark",
    "analysis_framework",
]

AutoResearchDomainId = Literal[
    "claim_evidence_retrieval",
    "rag_citation_faithfulness",
    "lightweight_ml_nlp_benchmark",
    "unsupported",
]

AutoResearchDomainEvidenceStatus = Literal["blocked", "limited", "ready"]

ConfidenceIntervalMethod = Literal["student_t_95"]

SignificanceComparisonScope = Literal["system", "sweep"]

SignificanceAlternative = Literal["greater", "less", "two_sided"]

SignificanceTestMethod = Literal["paired_sign_flip_exact", "paired_sign_flip_monte_carlo"]

MultipleComparisonCorrection = Literal["holm_bonferroni"]

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

class AutoResearchIdeaFeasibilityAssessmentRead(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    level: Literal["low", "medium", "high"] = "medium"
    summary: str
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

class AutoResearchDomainDecisionRead(BaseModel):
    domain_id: AutoResearchDomainId = "unsupported"
    domain_label: str = "Unsupported Domain"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_signals: list[str] = Field(default_factory=list)
    unsupported_reason: str | None = None
    required_capabilities: list[str] = Field(default_factory=list)
    evidence_policy: list[str] = Field(default_factory=list)
    publish_readiness_policy: list[str] = Field(default_factory=list)
    default_blockers: list[str] = Field(default_factory=list)
    template_id: str | None = None
    template_version: str | None = None
    is_supported: bool = False

class AutoResearchDomainTemplateRead(BaseModel):
    domain_id: AutoResearchDomainId
    domain_label: str
    template_id: str
    template_version: str
    research_brief_template: str
    literature_query_plan: list[str] = Field(default_factory=list)
    benchmark_resolver_policy: list[str] = Field(default_factory=list)
    method_baseline_ladder: list[str] = Field(default_factory=list)
    metric_schema: list[str] = Field(default_factory=list)
    experiment_factory_protocol: list[str] = Field(default_factory=list)
    evidence_ledger_schema: list[str] = Field(default_factory=list)
    paper_section_requirements: list[str] = Field(default_factory=list)
    publish_readiness_constraints: list[str] = Field(default_factory=list)
    negative_evidence_taxonomy: list[str] = Field(default_factory=list)
    required_package_artifacts: list[str] = Field(default_factory=list)
    task_family: TaskFamily
    benchmark_name: str
    template_complete: bool = True
    blockers: list[str] = Field(default_factory=list)

class AutoResearchDomainLiteratureStrategyRead(BaseModel):
    strategy_id: str
    domain_id: AutoResearchDomainId
    template_id: str | None = None
    template_version: str | None = None
    query_strings: list[str] = Field(default_factory=list)
    required_source_classes: list[str] = Field(default_factory=list)
    minimum_real_source_count: int = 0
    related_system_coverage_expectations: list[str] = Field(default_factory=list)
    novelty_risk_extraction: list[str] = Field(default_factory=list)
    known_method_extraction: list[str] = Field(default_factory=list)
    known_dataset_extraction: list[str] = Field(default_factory=list)
    known_metric_extraction: list[str] = Field(default_factory=list)
    known_sota_extraction: list[str] = Field(default_factory=list)
    fixture_only_limitation_policy: str
    final_publish_literature_blockers: list[str] = Field(default_factory=list)
    required_followups: list[str] = Field(default_factory=list)
    kill_criteria: list[str] = Field(default_factory=list)
    strategy_fingerprint: str

class AutoResearchDomainRelatedSystemCoverageRead(BaseModel):
    expectation: str
    matched_paper_ids: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)
    covered: bool = False
    limitation: str | None = None

class AutoResearchDomainLiteratureResultRead(BaseModel):
    result_id: str
    strategy_id: str
    domain_id: AutoResearchDomainId
    status: AutoResearchDomainEvidenceStatus = "blocked"
    source_counts: dict[str, int] = Field(default_factory=dict)
    source_class_counts: dict[str, int] = Field(default_factory=dict)
    real_source_count: int = 0
    real_source_types: list[str] = Field(default_factory=list)
    required_source_classes: list[str] = Field(default_factory=list)
    required_source_classes_present: list[str] = Field(default_factory=list)
    source_sufficiency_policy: dict[str, Any] = Field(default_factory=dict)
    source_sufficiency_ready: bool = False
    fixture_only: bool = False
    related_system_coverage: list[AutoResearchDomainRelatedSystemCoverageRead] = Field(default_factory=list)
    related_system_coverage_complete: bool = False
    known_methods: list[str] = Field(default_factory=list)
    known_datasets: list[str] = Field(default_factory=list)
    known_metrics: list[str] = Field(default_factory=list)
    known_sota: list[str] = Field(default_factory=list)
    novelty_risks: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    extraction_limitations: list[str] = Field(default_factory=list)
    final_publish_blockers: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    required_followups: list[str] = Field(default_factory=list)
    kill_criteria: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    result_fingerprint: str

class AutoResearchDomainBenchmarkResolverRead(BaseModel):
    resolver_id: str
    domain_id: AutoResearchDomainId
    status: AutoResearchDomainEvidenceStatus = "blocked"
    benchmark_name: str | None = None
    task_family: TaskFamily | None = None
    source_kind: BenchmarkKind | None = None
    source_class: str | None = None
    source_locator: str | None = None
    dataset_id: str | None = None
    revision: str | None = None
    license: str | None = None
    source_fingerprint: str | None = None
    sample_count: int = 0
    train_split_count: int = 0
    test_split_count: int = 0
    label_schema_coverage: dict[str, Any] = Field(default_factory=dict)
    query_document_evidence_schema_coverage: dict[str, Any] = Field(default_factory=dict)
    source_observation_coverage: dict[str, Any] = Field(default_factory=dict)
    benchmark_provenance_complete: bool = False
    publication_grade_eligible: bool = False
    final_candidate_eligible: bool = False
    source_independence_audit: dict[str, Any] = Field(default_factory=dict)
    benchmark_payload_ref: str | None = None
    blockers: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    required_followups: list[str] = Field(default_factory=list)
    kill_criteria: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    resolver_fingerprint: str

class AutoResearchDomainExperimentProtocolRead(BaseModel):
    protocol_id: str
    domain_id: AutoResearchDomainId
    status: AutoResearchDomainEvidenceStatus = "blocked"
    method_baseline_ladder: list[str] = Field(default_factory=list)
    metric_schema: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    runtime_contract: dict[str, Any] = Field(default_factory=dict)
    deterministic_execution_route: str
    import_replay_route: str
    evidence_ledger_schema: list[str] = Field(default_factory=list)
    negative_evidence_categories: list[str] = Field(default_factory=list)
    repair_routing_policy: dict[str, str] = Field(default_factory=dict)
    readiness_blockers: list[str] = Field(default_factory=list)
    final_publish_limitations: list[str] = Field(default_factory=list)
    benchmark_resolver_id: str | None = None
    benchmark_resolver_status: AutoResearchDomainEvidenceStatus = "blocked"
    protocol_complete: bool = False
    blockers: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    required_followups: list[str] = Field(default_factory=list)
    kill_criteria: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    protocol_fingerprint: str

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
    source_id: str | None = None
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
    cache_key: str | None = None
    cache_timestamp: datetime | None = None
    cache_freshness: AutoResearchCacheFreshness = "unknown"
    retrieved_at: datetime | None = None
    connector_provider: str | None = None
    source_observation_fingerprint: str | None = None
    fingerprint: str | None = None
    extraction_status: Literal["limited_metadata", "metadata_only", "abstract_only", "full_text"] = "metadata_only"
    extraction_limitations: list[str] = Field(default_factory=list)
    source_sufficiency_status: str | None = None
    related_system_coverage: list[str] = Field(default_factory=list)
    contradiction_signals: list[str] = Field(default_factory=list)
    claim_ceiling: str | None = None
    evidence: str

class AutoResearchLiteratureScoutSourceStatusRead(BaseModel):
    source: str
    query_count: int = 0
    cache_hit_count: int = 0
    cache_miss_count: int = 0
    network_request_count: int = 0
    paper_count: int = 0
    error_count: int = 0
    availability_status: Literal["available", "cache_miss", "unavailable", "unsupported", "error"] = "available"
    unavailable_reason: str | None = None
    cache_freshness_counts: dict[str, int] = Field(default_factory=dict)
    stale_cache_count: int = 0
    freshness_policy: str | None = None
    availability_blockers: list[str] = Field(default_factory=list)
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

class AutoResearchMemoryHintRead(BaseModel):
    hint_id: str
    memory_id: str
    item_type: AutoResearchMemoryItemType
    source_project_id: str
    source_run_id: str | None = None
    source_branch_id: str | None = None
    source_artifact_ref: str
    source_fingerprint: str
    title: str
    summary: str
    source_refs: list[str] = Field(default_factory=list)
    currentness: AutoResearchMemoryCurrentness = "unknown"
    limitations: list[str] = Field(default_factory=list)
    reuse_policy: AutoResearchMemoryReusePolicy = "requires_current_project_revalidation"
    reuse_requirements: list[str] = Field(default_factory=list)
    required_current_project_validation_actions: list[str] = Field(default_factory=list)
    evidence_grade: AutoResearchMemoryEvidenceGrade = "weak"
    source_class: AutoResearchMemorySourceClass
    extraction_level: AutoResearchMemoryExtractionLevel = "metadata"
    negative_status: AutoResearchMemoryNegativeStatus = "none"
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_terms: list[str] = Field(default_factory=list)
    memory_hint_only: bool = True

class AutoResearchLiteratureScoutRead(BaseModel):
    scout_id: str = "literature_scout_v1"
    project_id: str
    brief_id: str
    generated_at: datetime
    domain_literature_strategy: AutoResearchDomainLiteratureStrategyRead | None = None
    domain_literature_result: AutoResearchDomainLiteratureResultRead | None = None
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
    memory_hints: list[AutoResearchMemoryHintRead] = Field(default_factory=list)
    memory_policy_notes: list[str] = Field(default_factory=list)
    memory_risks: list[str] = Field(default_factory=list)
    memory_required_followups: list[str] = Field(default_factory=list)
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
    memory_risks: list[str] = Field(default_factory=list)
    memory_required_followups: list[str] = Field(default_factory=list)
    miner_fingerprint: str

class AutoResearchResearchBriefRead(BaseModel):
    brief_id: str
    project_id: str
    generated_at: datetime
    updated_at: datetime
    status: Literal["drafted", "ready_for_selection", "blocked"] = "ready_for_selection"
    original_idea: str
    polished_idea: str
    domain: str | None = None
    domain_decision: AutoResearchDomainDecisionRead | None = None
    domain_template: AutoResearchDomainTemplateRead | None = None
    domain_blockers: list[str] = Field(default_factory=list)
    domain_literature_strategy: AutoResearchDomainLiteratureStrategyRead | None = None
    domain_literature_result: AutoResearchDomainLiteratureResultRead | None = None
    domain_benchmark_resolver: AutoResearchDomainBenchmarkResolverRead | None = None
    domain_experiment_protocol: AutoResearchDomainExperimentProtocolRead | None = None
    domain_readiness_status: AutoResearchDomainEvidenceStatus = "blocked"
    domain_required_followups: list[str] = Field(default_factory=list)
    domain_kill_criteria: list[str] = Field(default_factory=list)
    domain_claim_ceiling: str | None = None
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
    memory_hints: list[AutoResearchMemoryHintRead] = Field(default_factory=list)
    memory_policy_notes: list[str] = Field(default_factory=list)
    memory_required_followups: list[str] = Field(default_factory=list)
    memory_validation_actions: list[str] = Field(default_factory=list)
    selected_direction_id: str | None = None
    selected_hypothesis_id: str | None = None
    selection_reason: str | None = None
    direction_selection: AutoResearchDirectionSelectionRead | None = None
    next_action: Literal["build_hypothesis_bank", "select_direction", "create_run", "blocked"] = "build_hypothesis_bank"
    allow_web: bool = False
    allow_experiments: bool = True
    target_tier: AutoResearchPaperTier = "workshop_candidate"
    resource_budget: AutoResearchIdeaResourceBudget = Field(default_factory=AutoResearchIdeaResourceBudget)
    benchmark_source: BenchmarkSource | None = None
    brief_fingerprint: str | None = None
    brief_path: str | None = None

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
