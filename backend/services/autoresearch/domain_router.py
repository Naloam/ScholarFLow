from __future__ import annotations

import re
from collections.abc import Iterable

from schemas.autoresearch import (
    AutoResearchDomainDecisionRead,
    AutoResearchDomainId,
    AutoResearchDomainTemplateRead,
    AutoResearchIdeaRequest,
    BenchmarkSource,
    TaskFamily,
)


_DOMAIN_TEMPLATE_REQUIRED_FIELDS = (
    "research_brief_template",
    "literature_query_plan",
    "benchmark_resolver_policy",
    "method_baseline_ladder",
    "metric_schema",
    "experiment_factory_protocol",
    "evidence_ledger_schema",
    "paper_section_requirements",
    "publish_readiness_constraints",
    "negative_evidence_taxonomy",
    "required_package_artifacts",
)

_STOPWORDS = {
    "about",
    "and",
    "build",
    "for",
    "from",
    "idea",
    "improve",
    "improving",
    "new",
    "research",
    "study",
    "system",
    "systems",
    "the",
    "this",
    "using",
    "with",
}


def _terms(*texts: str | None) -> set[str]:
    terms: set[str] = set()
    for text in texts:
        for raw in re.findall(r"[a-z][a-z0-9_]+", (text or "").lower()):
            if len(raw) < 3 or raw in _STOPWORDS:
                continue
            terms.add(raw)
    return terms


def _dedupe(items: Iterable[str | None]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = " ".join(str(item or "").split()).strip()
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def validate_domain_template_payload(payload: dict[str, object]) -> list[str]:
    blockers: list[str] = []
    for field in _DOMAIN_TEMPLATE_REQUIRED_FIELDS:
        value = payload.get(field)
        if isinstance(value, str):
            missing = not value.strip()
        else:
            missing = not bool(value)
        if missing:
            blockers.append(f"Domain template missing required field `{field}`.")
    if not payload.get("benchmark_resolver_policy"):
        blockers.append("Domain template missing benchmark resolver policy.")
    if not payload.get("metric_schema"):
        blockers.append("Domain template missing metric schema.")
    if not payload.get("paper_section_requirements"):
        blockers.append("Domain template missing paper section requirements.")
    return _dedupe(blockers)


def _template(
    *,
    domain_id: AutoResearchDomainId,
    domain_label: str,
    template_id: str,
    research_brief_template: str,
    literature_query_plan: list[str],
    benchmark_resolver_policy: list[str],
    method_baseline_ladder: list[str],
    metric_schema: list[str],
    experiment_factory_protocol: list[str],
    evidence_ledger_schema: list[str],
    paper_section_requirements: list[str],
    publish_readiness_constraints: list[str],
    negative_evidence_taxonomy: list[str],
    required_package_artifacts: list[str],
    task_family: TaskFamily,
    benchmark_name: str,
) -> AutoResearchDomainTemplateRead:
    payload = {
        "domain_id": domain_id,
        "domain_label": domain_label,
        "template_id": template_id,
        "template_version": template_id.rsplit("_", 1)[-1],
        "research_brief_template": research_brief_template,
        "literature_query_plan": literature_query_plan,
        "benchmark_resolver_policy": benchmark_resolver_policy,
        "method_baseline_ladder": method_baseline_ladder,
        "metric_schema": metric_schema,
        "experiment_factory_protocol": experiment_factory_protocol,
        "evidence_ledger_schema": evidence_ledger_schema,
        "paper_section_requirements": paper_section_requirements,
        "publish_readiness_constraints": publish_readiness_constraints,
        "negative_evidence_taxonomy": negative_evidence_taxonomy,
        "required_package_artifacts": required_package_artifacts,
        "task_family": task_family,
        "benchmark_name": benchmark_name,
    }
    blockers = validate_domain_template_payload(payload)
    return AutoResearchDomainTemplateRead(
        **payload,
        template_complete=not blockers,
        blockers=blockers,
    )


_SUPPORTED_TEMPLATES: dict[AutoResearchDomainId, AutoResearchDomainTemplateRead] = {
    "claim_evidence_retrieval": _template(
        domain_id="claim_evidence_retrieval",
        domain_label="Claim-Evidence Retrieval And Verification",
        template_id="claim_evidence_retrieval_v1",
        research_brief_template=(
            "Narrow the idea to scientific-writing claim support retrieval, claim verification, "
            "abstention, and repair routing with explicit evidence-ledger obligations."
        ),
        literature_query_plan=[
            "claim evidence retrieval scientific writing agents",
            "scientific claim verification retrieval evidence support",
            "citation grounded writing unsupported claim detection",
        ],
        benchmark_resolver_policy=[
            "Prefer repository-local SciFact verification/retrieval frozen snapshots when available.",
            "Use frozen_claim_evidence_reranking only as a deterministic fixture for smoke/review paths.",
            "Require benchmark provenance before final-publish claims.",
        ],
        method_baseline_ladder=[
            "random_ranker",
            "overlap_ranker",
            "idf_ranker",
            "bigram_ranker",
            "ledger_aware_ranker",
            "abstention_and_repair_router",
        ],
        metric_schema=[
            "mrr",
            "recall_at_1",
            "ndcg_at_10",
            "recall_at_10",
            "evidence_coverage",
            "verification_accuracy",
            "unsupported_claim_precision",
            "unsupported_claim_recall",
            "abstention_accuracy",
            "repair_precision",
            "repair_recall",
        ],
        experiment_factory_protocol=[
            "Create lexical baseline jobs before candidate reranking.",
            "Materialize ablations for bigram, ledger-aware, retrieval-only, and repair-router-disabled variants when evidence exists.",
            "Persist result artifacts, evidence ledger entries, environment manifests, and repair classifications.",
        ],
        evidence_ledger_schema=[
            "claim_id",
            "retrieved_evidence_ids",
            "support_status",
            "missing_or_contradictory_evidence",
            "repair_action",
            "artifact_ref",
        ],
        paper_section_requirements=[
            "Research Question",
            "Related Work",
            "Method",
            "Benchmark And Data",
            "Experimental Setup",
            "Results",
            "Negative Evidence",
            "Limitations",
            "Reproducibility",
        ],
        publish_readiness_constraints=[
            "Do not promote unsupported claims from retrieval-only evidence.",
            "Final publish requires real/frozen/imported benchmark provenance, sufficient scale, statistics, negative evidence, and independent source evidence.",
            "Review-ready bundles must remain distinct from final-publish bundles.",
        ],
        negative_evidence_taxonomy=[
            "retrieval_miss",
            "unsupported_claim_false_negative",
            "unsupported_claim_false_positive",
            "contradiction_refutation_ambiguity",
            "insufficient_evidence_case",
            "abstention_failure",
            "repair_router_failure",
            "failed_or_blocked_repair_attempt",
        ],
        required_package_artifacts=[
            "claim_evidence_index.md",
            "retrieval_evidence_ledger.json",
            "benchmark_provenance_manifest.json",
            "statistics_report.json",
            "negative_evidence_report.json",
            "publication_readiness_report.json",
            "publication_manifest.json",
        ],
        task_family="ir_reranking",
        benchmark_name="frozen_claim_evidence_reranking",
    ),
    "rag_citation_faithfulness": _template(
        domain_id="rag_citation_faithfulness",
        domain_label="RAG Citation Faithfulness",
        template_id="rag_citation_faithfulness_v1",
        research_brief_template=(
            "Narrow the idea to citation-faithfulness evaluation for knowledge-intensive QA/RAG, "
            "where retrieved citation evidence must justify answer claims."
        ),
        literature_query_plan=[
            "retrieval augmented generation citation faithfulness evaluation",
            "RAG attribution citation support benchmark",
            "knowledge intensive QA citation grounding metrics",
        ],
        benchmark_resolver_policy=[
            "Use toy_paper_evidence_reranking as repository-local smoke/review fixture.",
            "Block final-publish claims until a real multi-source citation-faithfulness benchmark is imported or frozen.",
            "Require citation-support provenance and source-document lineage before broad claims.",
        ],
        method_baseline_ladder=[
            "random_ranker",
            "overlap_ranker",
            "idf_ranker",
            "bigram_ranker",
            "citation_support_reranker",
        ],
        metric_schema=[
            "mrr",
            "recall_at_1",
            "ndcg_at_10",
            "recall_at_10",
            "evidence_coverage",
            "citation_support_coverage",
        ],
        experiment_factory_protocol=[
            "Create retrieval baselines before citation-support candidate jobs.",
            "Record citation-support outputs as review evidence only when using toy fixtures.",
            "Classify missing real benchmark provenance as a blocker, not as a completed repair.",
        ],
        evidence_ledger_schema=[
            "question_id",
            "answer_claim",
            "citation_ref",
            "supporting_passage_id",
            "faithfulness_status",
            "artifact_ref",
        ],
        paper_section_requirements=[
            "Research Question",
            "Related Work",
            "Method",
            "Benchmark And Data",
            "Experimental Setup",
            "Results",
            "Negative Evidence",
            "Limitations",
            "Reproducibility",
        ],
        publish_readiness_constraints=[
            "Toy citation fixtures can support only smoke/review evidence.",
            "Final publish requires real multi-source citation-faithfulness benchmark provenance.",
            "Unsupported or uncited answer claims must remain blockers or limitations.",
        ],
        negative_evidence_taxonomy=[
            "unsupported_citation",
            "irrelevant_citation",
            "answer_claim_not_in_source",
            "retrieval_miss",
            "fixture_only_literature",
            "missing_citation_benchmark_provenance",
        ],
        required_package_artifacts=[
            "literature_support_index.json",
            "claim_evidence_index.md",
            "benchmark_card.json",
            "benchmark_provenance_manifest.json",
            "negative_evidence_report.json",
            "publication_readiness_report.json",
        ],
        task_family="ir_reranking",
        benchmark_name="toy_paper_evidence_reranking",
    ),
    "lightweight_ml_nlp_benchmark": _template(
        domain_id="lightweight_ml_nlp_benchmark",
        domain_label="Lightweight ML/NLP Benchmark",
        template_id="lightweight_ml_nlp_benchmark_v1",
        research_brief_template=(
            "Narrow the idea to a deterministic local ML/NLP benchmark comparison with explicit "
            "train/test splits, lightweight baselines, metrics, and smoke-test evidence limits."
        ),
        literature_query_plan=[
            "lightweight NLP benchmark comparison macro F1",
            "deterministic local text classification baseline evaluation",
            "small benchmark reproducibility machine learning NLP",
        ],
        benchmark_resolver_policy=[
            "Use toy_ml_nlp_robotics_topic for deterministic local text-classification smoke evidence.",
            "Allow tabular/text local fixtures for engineering validation only.",
            "Require imported real benchmark provenance and scale before publication-grade claims.",
        ],
        method_baseline_ladder=[
            "majority",
            "keyword_rule",
            "naive_bayes_limited_vocab",
            "naive_bayes",
        ],
        metric_schema=[
            "accuracy",
            "macro_f1",
        ],
        experiment_factory_protocol=[
            "Create majority and keyword-rule baseline jobs before candidate lexical model jobs.",
            "Record held-out split metrics and limited-vocabulary ablation evidence.",
            "Keep fixture/local smoke results scoped to review or engineering validation.",
        ],
        evidence_ledger_schema=[
            "dataset_split",
            "system_name",
            "metric_name",
            "metric_value",
            "baseline_comparison",
            "artifact_ref",
        ],
        paper_section_requirements=[
            "Research Question",
            "Benchmark And Data",
            "Experimental Setup",
            "Results",
            "Negative Evidence",
            "Limitations",
            "Reproducibility",
        ],
        publish_readiness_constraints=[
            "Do not call toy/local fixture results publication-grade.",
            "Require real/imported benchmark provenance, sufficient scale, and statistical evidence for paper claims.",
            "Negative or non-significant local results must remain in the evidence ledger.",
        ],
        negative_evidence_taxonomy=[
            "candidate_not_better_than_baseline",
            "insufficient_statistics",
            "fixture_only_benchmark",
            "missing_ablation",
            "runtime_failure",
        ],
        required_package_artifacts=[
            "benchmark_card.json",
            "experiment_factory_environment_manifest.json",
            "evidence_ledger.json",
            "statistics_report.json",
            "negative_evidence_report.json",
            "publication_readiness_report.json",
        ],
        task_family="text_classification",
        benchmark_name="toy_ml_nlp_robotics_topic",
    ),
}


def list_domain_templates() -> list[AutoResearchDomainTemplateRead]:
    templates = list(_SUPPORTED_TEMPLATES.values())
    ids = [item.domain_id for item in templates]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate domain id in domain template registry")
    return templates


def get_domain_template(domain_id: AutoResearchDomainId | str | None) -> AutoResearchDomainTemplateRead | None:
    if domain_id is None:
        return None
    return _SUPPORTED_TEMPLATES.get(domain_id)  # type: ignore[arg-type]


def benchmark_source_for_template(
    template: AutoResearchDomainTemplateRead,
) -> BenchmarkSource:
    return BenchmarkSource(
        kind="builtin",
        name=template.benchmark_name,
        task_family_hint=template.task_family,
    )


_DOMAIN_SIGNAL_GROUPS: dict[AutoResearchDomainId, list[set[str]]] = {
    "claim_evidence_retrieval": [
        {"claim", "claims", "evidence", "support", "unsupported"},
        {"retrieval", "reranking", "verification", "verify"},
        {"scientific", "writing", "paper", "manuscript", "citation", "citations", "literature", "review"},
    ],
    "rag_citation_faithfulness": [
        {"rag", "retrieval", "augmented", "generation", "qa", "question", "answering"},
        {"citation", "citations", "attribution", "source", "sources"},
        {"faithfulness", "faithful", "grounding", "grounded", "support"},
    ],
    "lightweight_ml_nlp_benchmark": [
        {"lightweight", "local", "deterministic", "small", "toy", "test"},
        {
            "ml",
            "machine",
            "learning",
            "nlp",
            "text",
            "classification",
            "classifier",
            "tabular",
            "model",
            "models",
            "calibration",
            "llm",
            "prompt",
            "prompting",
            "memory",
            "planning",
            "risky",
            "adversarial",
        },
        {
            "benchmark",
            "comparison",
            "baseline",
            "metric",
            "macro",
            "accuracy",
            "evaluation",
            "reliability",
            "failure",
            "evidence",
            "checks",
        },
    ],
}

_DOMAIN_HINT_ALIASES: dict[str, AutoResearchDomainId] = {
    "claim_evidence": "claim_evidence_retrieval",
    "claim_evidence_retrieval": "claim_evidence_retrieval",
    "claim-evidence retrieval": "claim_evidence_retrieval",
    "rag": "rag_citation_faithfulness",
    "rag_citation_faithfulness": "rag_citation_faithfulness",
    "citation faithfulness": "rag_citation_faithfulness",
    "lightweight_ml_nlp_benchmark": "lightweight_ml_nlp_benchmark",
    "lightweight ml nlp benchmark": "lightweight_ml_nlp_benchmark",
    "ml nlp benchmark": "lightweight_ml_nlp_benchmark",
}


def _capability_policy(template: AutoResearchDomainTemplateRead) -> tuple[list[str], list[str], list[str]]:
    if template.domain_id == "claim_evidence_retrieval":
        return (
            [
                "cached_literature_scout",
                "claim_evidence_benchmark_resolver",
                "deterministic_ir_execution_or_import_replay",
                "claim_evidence_ledger",
                "review_and_revision_loop",
            ],
            list(template.publish_readiness_constraints),
            [
                "Final publish remains blocked unless SciFact/frozen/imported provenance, statistics, negative evidence, and source independence are satisfied."
            ],
        )
    if template.domain_id == "rag_citation_faithfulness":
        return (
            [
                "cached_literature_scout",
                "citation_faithfulness_benchmark_resolver",
                "deterministic_ir_fixture_execution",
                "citation_support_ledger",
            ],
            list(template.publish_readiness_constraints),
            [
                "RAG/citation faithfulness currently has repository-local toy review evidence only; import a real multi-source citation-faithfulness benchmark before final-publish claims."
            ],
        )
    return (
        [
            "cached_literature_scout",
            "local_text_classification_fixture",
            "deterministic_local_metrics",
            "evidence_ledger",
        ],
        list(template.publish_readiness_constraints),
        [
            "Lightweight local ML/NLP fixture evidence is smoke/review evidence only and cannot support publication-grade claims."
        ],
    )


def _score_domain(
    *,
    domain_id: AutoResearchDomainId,
    tokens: set[str],
    text: str,
    domain_hint: str | None,
) -> tuple[int, list[str]]:
    if domain_id == "unsupported":
        return 0, []
    groups = _DOMAIN_SIGNAL_GROUPS[domain_id]
    matched: list[str] = []
    covered_groups = 0
    score = 0
    for group in groups:
        hits = sorted(tokens & group)
        if hits:
            covered_groups += 1
            score += len(hits) * 2
            matched.extend(hits[:4])
    phrase_signals: dict[AutoResearchDomainId, list[str]] = {
        "claim_evidence_retrieval": [
            "claim-evidence",
            "claim evidence",
            "unsupported claims",
            "scientific writing",
            "evidence ledger",
        ],
        "rag_citation_faithfulness": [
            "retrieval augmented generation",
            "citation ranking",
            "citation faithfulness",
            "citation faithful",
            "citation grounding",
            "knowledge intensive qa",
        ],
        "lightweight_ml_nlp_benchmark": [
            "lightweight benchmark",
            "local benchmark",
            "text classification",
            "macro f1",
            "machine learning",
            "llm evaluation",
            "prompting strategy",
            "tabular model",
        ],
    }
    for phrase in phrase_signals[domain_id]:
        if phrase in text:
            score += 4
            matched.append(phrase)
    if domain_hint:
        hint = domain_hint.lower().strip()
        alias = _DOMAIN_HINT_ALIASES.get(hint)
        if alias == domain_id or any(signal in hint for signal in matched):
            score += 5
            matched.append(f"domain_hint:{domain_hint}")
    if covered_groups < 2:
        score = min(score, 5)
    return score, _dedupe(matched)


def _unsupported_reason(
    *,
    text: str,
    best_score: int,
    allow_web: bool,
    allow_gpu: bool,
    execution_backend_kind: str | None,
) -> str:
    hard_requirements = []
    if any(signal in text for signal in ("live web", "internet only", "online benchmark", "crawl")) and not allow_web:
        hard_requirements.append("live network access")
    if any(signal in text for signal in ("gpu", "cuda", "large model training", "train a large model")) and not allow_gpu:
        hard_requirements.append("GPU or large-model training")
    if "docker only" in text or execution_backend_kind in {"docker", "docker_gpu"}:
        hard_requirements.append("Docker-only benchmark execution")
    if hard_requirements:
        return (
            "Unsupported domain or policy request: this idea requires "
            + ", ".join(_dedupe(hard_requirements))
            + ", which is outside deterministic Goal 2 execution."
        )
    if best_score < 7:
        return (
            "Unsupported domain: the idea does not match claim-evidence retrieval, "
            "RAG/citation faithfulness, or lightweight ML/NLP benchmark signals with enough confidence."
        )
    return "Unsupported domain: no complete domain template and deterministic benchmark resolver matched this idea."


def route_domain(payload: AutoResearchIdeaRequest) -> AutoResearchDomainDecisionRead:
    text = " ".join(
        [
            payload.idea,
            payload.domain or "",
            payload.task_family_hint or "",
            payload.benchmark.name if payload.benchmark is not None and payload.benchmark.name else "",
            payload.benchmark.dataset_id if payload.benchmark is not None and payload.benchmark.dataset_id else "",
        ]
    ).lower()
    tokens = _terms(text)
    explicit_hint = _DOMAIN_HINT_ALIASES.get((payload.domain or "").lower().strip())
    candidates: list[tuple[int, AutoResearchDomainId, list[str]]] = []
    for domain_id in _SUPPORTED_TEMPLATES:
        score, matched = _score_domain(
            domain_id=domain_id,
            tokens=tokens,
            text=text,
            domain_hint=payload.domain,
        )
        if explicit_hint == domain_id:
            score += 6
            matched.append(f"explicit_domain_hint:{payload.domain}")
        candidates.append((score, domain_id, matched))
    candidates.sort(key=lambda item: (item[0], len(item[2])), reverse=True)
    best_score, best_domain_id, matched_signals = candidates[0]
    template = get_domain_template(best_domain_id)
    execution_backend_kind = (
        payload.execution_backend.kind if payload.execution_backend is not None else None
    )
    unsupported_reason = _unsupported_reason(
        text=text,
        best_score=best_score,
        allow_web=payload.allow_web,
        allow_gpu=payload.resource_budget.allow_gpu,
        execution_backend_kind=execution_backend_kind,
    )
    requires_blocked_policy = unsupported_reason.startswith("Unsupported domain or policy request")
    if template is None or best_score < 7 or requires_blocked_policy:
        return AutoResearchDomainDecisionRead(
            domain_id="unsupported",
            domain_label="Unsupported Domain",
            confidence=round(min(0.99, best_score / 24), 2),
            matched_signals=matched_signals,
            unsupported_reason=unsupported_reason,
            required_capabilities=[
                "complete_domain_template",
                "deterministic_benchmark_resolver",
                "offline_or_cached_evidence_path",
            ],
            evidence_policy=[
                "Do not synthesize unrelated toy experiment outputs for unsupported ideas.",
                "Create only an auditable blocker record until a supported domain template exists.",
            ],
            publish_readiness_policy=[
                "Unsupported domains cannot enter experiment execution or publication packaging.",
            ],
            default_blockers=[unsupported_reason],
            is_supported=False,
        )
    capabilities, publish_policy, default_blockers = _capability_policy(template)
    confidence = min(0.99, 0.45 + best_score / 32)
    return AutoResearchDomainDecisionRead(
        domain_id=template.domain_id,
        domain_label=template.domain_label,
        confidence=round(confidence, 2),
        matched_signals=matched_signals,
        unsupported_reason=None,
        required_capabilities=capabilities,
        evidence_policy=[
            *template.benchmark_resolver_policy,
            "Persist domain decision, template id, and evidence limitations in trace/readiness artifacts.",
        ],
        publish_readiness_policy=publish_policy,
        default_blockers=default_blockers,
        template_id=template.template_id,
        template_version=template.template_version,
        is_supported=True,
    )
