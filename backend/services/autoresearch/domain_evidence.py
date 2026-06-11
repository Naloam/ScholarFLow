from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from schemas.autoresearch import (
    AutoResearchDomainBenchmarkResolverRead,
    AutoResearchDomainEvidenceStatus,
    AutoResearchDomainExperimentProtocolRead,
    AutoResearchDomainId,
    AutoResearchDomainLiteratureResultRead,
    AutoResearchDomainLiteratureStrategyRead,
    AutoResearchDomainRelatedSystemCoverageRead,
    AutoResearchDomainTemplateRead,
    AutoResearchLiteratureScoutPaperRead,
    AutoResearchLiteratureScoutRead,
    AutoResearchResearchBriefRead,
    BenchmarkSource,
)
from services.autoresearch.benchmarks import (
    ResolvedBenchmark,
    benchmark_source_publication_eligibility,
    builtin_benchmark,
)
from services.autoresearch.domain_router import (
    benchmark_source_for_template,
    get_domain_template,
)
from services.autoresearch.ingestion import resolve_benchmark


_REAL_LITERATURE_SOURCES = {"arxiv", "semantic_scholar", "crossref"}
_SYNTHETIC_LITERATURE_SOURCES = {"fixture", "fixture_offline", "offline_project_context"}
_SCIFACT_VERIFICATION_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "frozen_benchmarks"
    / "scifact_claim_verification_frozen_snapshot_v1.json"
)
_SCIFACT_RETRIEVAL_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "frozen_benchmarks"
    / "scifact_claim_retrieval_frozen_snapshot_v1.json"
)
_SCIFACT_SOURCE_URL = "https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz"
_SCIFACT_SOURCE_SHA256 = "11c621288d41ac144d29b13b0f8503b3820b7d6e8b1f6ff24dff335c196d76be"
_SCIFACT_REVISION = f"release-latest-data-tarball-sha256-{_SCIFACT_SOURCE_SHA256}"
_SCIFACT_LICENSE = "claims/evidence annotations: CC BY 4.0; corpus abstracts: S2ORC/ODC-By 1.0"


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _dedupe(items: list[str | None]) -> list[str]:
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


def _tokens(*texts: str | None) -> set[str]:
    return {
        raw
        for text in texts
        for raw in re.findall(r"[a-z][a-z0-9_]+", (text or "").lower())
        if len(raw) >= 4
    }


def _literature_source_class(paper: AutoResearchLiteratureScoutPaperRead) -> str:
    if paper.source in _REAL_LITERATURE_SOURCES:
        if paper.cache_freshness == "stale":
            return "real_stale_cache"
        if paper.cache_freshness == "unknown":
            return "real_unknown_freshness"
        return "real_fresh_cached_or_network"
    if paper.source in _SYNTHETIC_LITERATURE_SOURCES or paper.cache_status in {"offline", "fixture"}:
        return "fixture_or_offline"
    return "unknown"


def _template_or_none(domain_id: AutoResearchDomainId | str | None) -> AutoResearchDomainTemplateRead | None:
    if domain_id == "unsupported":
        return None
    return get_domain_template(domain_id)


def _strategy_profile(domain_id: AutoResearchDomainId) -> dict[str, Any]:
    if domain_id == "claim_evidence_retrieval":
        return {
            "required_source_classes": ["arxiv", "semantic_scholar", "crossref"],
            "minimum_real_source_count": 3,
            "related_systems": ["SciFact", "FEVER", "BEIR", "claim verification", "evidence retrieval"],
            "novelty": ["duplicate claim-verification framing", "retrieval-only novelty inflation"],
            "methods": ["claim verification", "lexical reranking", "evidence ledger", "abstention"],
            "datasets": ["SciFact", "FEVER", "BEIR"],
            "metrics": ["mrr", "recall_at_1", "recall_at_10", "ndcg", "verification_accuracy"],
            "sota": ["reported retrieval or verification SOTA", "abstention and repair-router results"],
            "fixture_policy": (
                "Fixture-only literature may support a smoke review bundle, but it blocks novelty "
                "and final-publish related-work claims."
            ),
            "final_blockers": [
                "Final publish requires multi-source real literature coverage for claim verification, retrieval, and unsupported-claim handling.",
                "Fixture-only or offline-project-context literature cannot establish novelty.",
            ],
        }
    if domain_id == "rag_citation_faithfulness":
        return {
            "required_source_classes": ["arxiv", "semantic_scholar", "crossref"],
            "minimum_real_source_count": 2,
            "related_systems": ["RAG", "attribution", "citation faithfulness", "grounding", "knowledge-intensive QA"],
            "novelty": ["citation-faithfulness duplicate risk", "grounding metric overlap"],
            "methods": ["citation support scoring", "attribution evaluation", "grounded generation", "abstention"],
            "datasets": ["ASQA", "ELI5", "KILT", "FEVER", "citation benchmark"],
            "metrics": ["citation_support_coverage", "faithfulness", "precision", "recall", "abstention"],
            "sota": ["reported citation-faithfulness or attribution benchmark results"],
            "fixture_policy": (
                "Repository-local citation fixtures can support review-only evidence; final-publish "
                "claims require real multi-source citation-faithfulness provenance."
            ),
            "final_blockers": [
                "Final publish requires real multi-source citation-faithfulness literature and benchmark provenance.",
                "Missing attribution/RAG related-system coverage must remain a limitation or follow-up.",
            ],
        }
    if domain_id == "lightweight_ml_nlp_benchmark":
        return {
            "required_source_classes": ["arxiv", "semantic_scholar", "crossref"],
            "minimum_real_source_count": 2,
            "related_systems": ["lightweight benchmark", "text classification", "macro F1", "local baseline", "reproducibility"],
            "novelty": ["small-benchmark duplicate risk", "baseline-only contribution risk"],
            "methods": ["majority baseline", "keyword rule", "naive Bayes", "local deterministic metric"],
            "datasets": ["AG News", "SST", "TREC", "text classification"],
            "metrics": ["accuracy", "macro_f1"],
            "sota": ["reported lightweight classification baselines"],
            "fixture_policy": (
                "Local toy ML/NLP fixtures are engineering-validation evidence only and cannot "
                "support publication-grade benchmark claims."
            ),
            "final_blockers": [
                "Final publish requires imported real benchmark provenance, adequate scale, and statistical evidence.",
                "Fixture-only benchmark/literature support keeps the claim ceiling at review-only or technical-report scope.",
            ],
        }
    return {
        "required_source_classes": [],
        "minimum_real_source_count": 0,
        "related_systems": [],
        "novelty": ["unsupported-domain novelty cannot be assessed without a complete template"],
        "methods": [],
        "datasets": [],
        "metrics": [],
        "sota": [],
        "fixture_policy": "Unsupported domains do not receive fixture substitutions.",
        "final_blockers": ["Unsupported domain has no literature strategy."],
    }


def build_domain_literature_strategy(
    brief: AutoResearchResearchBriefRead,
) -> AutoResearchDomainLiteratureStrategyRead | None:
    decision = brief.domain_decision
    template = brief.domain_template or _template_or_none(decision.domain_id if decision else None)
    if decision is None or template is None or not decision.is_supported:
        return None
    profile = _strategy_profile(template.domain_id)
    query_strings = _dedupe([*template.literature_query_plan, *brief.novelty_search_plan])
    payload = {
        "strategy_id": f"{template.domain_id}_literature_strategy_v1",
        "domain_id": template.domain_id,
        "template_id": template.template_id,
        "template_version": template.template_version,
        "query_strings": query_strings,
        "required_source_classes": profile["required_source_classes"],
        "minimum_real_source_count": profile["minimum_real_source_count"],
        "related_system_coverage_expectations": profile["related_systems"],
        "novelty_risk_extraction": profile["novelty"],
        "known_method_extraction": profile["methods"],
        "known_dataset_extraction": profile["datasets"],
        "known_metric_extraction": profile["metrics"],
        "known_sota_extraction": profile["sota"],
        "fixture_only_limitation_policy": profile["fixture_policy"],
        "final_publish_literature_blockers": profile["final_blockers"],
        "required_followups": [
            "Refresh cached/imported literature until required source classes and related-system coverage are present.",
            "Verify abstract-level metadata against full papers before novelty or final-publish claims.",
        ],
        "kill_criteria": [
            "Kill or reframe the direction if literature shows a direct duplicate with no narrower experimentally testable gap.",
            "Keep final_publish_ready=false while literature is fixture-only or lacks required related-system coverage.",
        ],
    }
    return AutoResearchDomainLiteratureStrategyRead(
        strategy_fingerprint=_fingerprint(payload),
        **payload,
    )


def _coverage_for_expectation(
    expectation: str,
    papers: list[AutoResearchLiteratureScoutPaperRead],
) -> AutoResearchDomainRelatedSystemCoverageRead:
    expectation_terms = _tokens(expectation)
    matched_ids: list[str] = []
    matched_terms: list[str] = []
    for paper in papers:
        paper_text = " ".join(
            [
                paper.title,
                paper.abstract or "",
                paper.evidence,
                " ".join(paper.methods),
                " ".join(paper.datasets),
                " ".join(paper.metrics),
                " ".join(paper.reported_results),
                paper.known_sota or "",
            ]
        )
        hits = sorted(expectation_terms & _tokens(paper_text))
        if hits:
            matched_ids.append(paper.paper_id)
            matched_terms.extend(hits)
    covered = bool(matched_ids)
    return AutoResearchDomainRelatedSystemCoverageRead(
        expectation=expectation,
        matched_paper_ids=_dedupe(matched_ids)[:8],
        matched_terms=_dedupe(matched_terms)[:12],
        covered=covered,
        limitation=None if covered else f"Missing related-system coverage for `{expectation}`.",
    )


def build_domain_literature_result(
    *,
    strategy: AutoResearchDomainLiteratureStrategyRead | None,
    scout: AutoResearchLiteratureScoutRead,
) -> AutoResearchDomainLiteratureResultRead | None:
    if strategy is None:
        return None
    papers = list(scout.similar_papers)
    real_papers = [paper for paper in papers if paper.source in _REAL_LITERATURE_SOURCES]
    stale_real_papers = [paper for paper in real_papers if paper.cache_freshness == "stale"]
    sufficient_real_papers = [
        paper
        for paper in real_papers
        if paper.cache_freshness != "stale"
    ]
    source_classes: dict[str, int] = {}
    for paper in papers:
        source_class = _literature_source_class(paper)
        source_classes[source_class] = source_classes.get(source_class, 0) + 1
    real_sources = sorted({paper.source for paper in sufficient_real_papers})
    observed_real_sources = sorted({paper.source for paper in real_papers})
    required_present = [
        source
        for source in strategy.required_source_classes
        if source in real_sources
    ]
    missing_required_sources = [
        source
        for source in strategy.required_source_classes
        if source not in required_present
    ]
    source_sufficiency_ready = (
        len(real_sources) >= strategy.minimum_real_source_count
        and not missing_required_sources
    )
    fixture_only = bool(papers) and not real_papers
    coverage = [
        _coverage_for_expectation(expectation, sufficient_real_papers)
        for expectation in strategy.related_system_coverage_expectations
    ]
    coverage_complete = bool(coverage) and all(item.covered for item in coverage)
    limitations = _dedupe(
        [
            *[item.limitation for item in coverage if item.limitation],
            "Literature scout metadata is abstract-level; full-paper verification is required before final-publish positioning.",
            strategy.fixture_only_limitation_policy if fixture_only else None,
            (
                f"{len(stale_real_papers)} real literature source observation(s) came from stale cache and are discovery context only."
                if stale_real_papers
                else None
            ),
        ]
    )
    extraction_limitations = _dedupe(
        [
            (
                f"Paper `{paper.paper_id}` has extraction_status={paper.extraction_status}; "
                "do not use it alone for novelty or final-publish positioning."
            )
            for paper in papers
            if paper.extraction_status in {"limited_metadata", "metadata_only", "abstract_only"}
        ]
        + [
            f"Paper `{paper.paper_id}` uses stale cached {paper.source} metadata; refresh before final-publish literature claims."
            for paper in stale_real_papers
        ]
    )
    blockers = _dedupe(
        [
            (
                f"Literature strategy requires at least {strategy.minimum_real_source_count} real cached/network sources; "
                f"found {len(real_sources)}."
                if len(real_sources) < strategy.minimum_real_source_count
                else None
            ),
            (
                "Literature strategy has fixture/offline-only evidence and cannot support novelty or final-publish claims."
                if fixture_only or not real_papers
                else None
            ),
            (
                "Missing required literature source classes: "
                + ", ".join(missing_required_sources)
                if missing_required_sources
                else None
            ),
            (
                "Literature source sufficiency policy is not satisfied for final-publish novelty claims."
                if not source_sufficiency_ready
                else None
            ),
            (
                f"{len(stale_real_papers)} real literature source observation(s) are stale and do not count toward final-publish source sufficiency."
                if stale_real_papers
                else None
            ),
            (
                "Missing related-system coverage for: "
                + ", ".join(item.expectation for item in coverage if not item.covered)
                if coverage and not coverage_complete
                else None
            ),
        ]
    )
    final_publish_blockers = _dedupe(
        [
            *strategy.final_publish_literature_blockers,
            *blockers,
        ]
    )
    status: AutoResearchDomainEvidenceStatus = (
        "blocked"
        if not papers
        else "ready"
        if not blockers
        else "limited"
    )
    novelty_risks = _dedupe(
        [
            *(paper.novelty_risk_signal for paper in papers if paper.novelty_risk_signal != "low"),
            *strategy.novelty_risk_extraction,
        ]
    )
    payload = {
        "result_id": f"{strategy.domain_id}_literature_result_v1",
        "strategy_id": strategy.strategy_id,
        "domain_id": strategy.domain_id,
        "status": status,
        "source_counts": dict(scout.source_counts),
        "source_class_counts": source_classes,
        "real_source_count": len(real_sources),
        "real_source_types": real_sources,
        "required_source_classes": list(strategy.required_source_classes),
        "required_source_classes_present": required_present,
        "source_sufficiency_policy": {
            "minimum_real_source_count": strategy.minimum_real_source_count,
            "real_source_count": len(real_sources),
            "observed_real_source_count": len(observed_real_sources),
            "stale_real_source_observation_count": len(stale_real_papers),
            "required_source_classes": list(strategy.required_source_classes),
            "required_source_classes_present": required_present,
            "missing_required_source_classes": missing_required_sources,
            "ready": source_sufficiency_ready,
            "connector_statuses": [
                status.model_dump(mode="json")
                for status in scout.source_statuses
            ],
        },
        "source_sufficiency_ready": source_sufficiency_ready,
        "fixture_only": fixture_only,
        "related_system_coverage": [item.model_dump(mode="json") for item in coverage],
        "related_system_coverage_complete": coverage_complete,
        "known_methods": list(scout.methods),
        "known_datasets": list(scout.datasets),
        "known_metrics": list(scout.metrics),
        "known_sota": list(scout.known_sota),
        "novelty_risks": novelty_risks,
        "limitations": limitations,
        "extraction_limitations": extraction_limitations,
        "final_publish_blockers": final_publish_blockers,
        "blockers": blockers,
        "required_followups": _dedupe(
            [
                *strategy.required_followups,
                *[
                    f"Add or verify literature coverage for `{item.expectation}`."
                    for item in coverage
                    if not item.covered
                ],
                *(
                    [
                        "Verify abstract-level or metadata-only literature against full papers before novelty claims."
                    ]
                    if extraction_limitations
                    else []
                ),
            ]
        ),
        "kill_criteria": list(strategy.kill_criteria),
        "evidence_refs": [
            f"brief:{scout.brief_id}:literature_scout",
            *[f"literature_paper:{paper.paper_id}" for paper in papers[:12]],
        ],
    }
    return AutoResearchDomainLiteratureResultRead(
        result_fingerprint=_fingerprint(payload),
        **payload,
    )


def _claim_evidence_source() -> BenchmarkSource:
    return BenchmarkSource(
        kind="scifact_json",
        name="SciFact Claim Verification Frozen Snapshot",
        url=_SCIFACT_SOURCE_URL,
        file_path=str(_SCIFACT_VERIFICATION_SNAPSHOT_PATH),
        dataset_id="allenai/scifact",
        revision=_SCIFACT_REVISION,
        license=_SCIFACT_LICENSE,
        task_family_hint="ir_reranking",
    )


def _resolved_benchmark_for_template(
    template: AutoResearchDomainTemplateRead,
    *,
    topic: str,
    benchmark_source: BenchmarkSource | None = None,
) -> ResolvedBenchmark:
    if benchmark_source is not None:
        return resolve_benchmark(
            topic=topic,
            task_family_hint=template.task_family,
            benchmark_source=benchmark_source,
        )
    if template.domain_id == "claim_evidence_retrieval" and _SCIFACT_VERIFICATION_SNAPSHOT_PATH.is_file():
        return resolve_benchmark(
            topic=topic,
            task_family_hint="ir_reranking",
            benchmark_source=_claim_evidence_source(),
        )
    source = benchmark_source_for_template(template)
    return builtin_benchmark(template.task_family, source=source, topic=topic)


def _schema_coverage(benchmark: ResolvedBenchmark) -> dict[str, Any]:
    payload = benchmark.payload
    declared = payload.get("query_document_evidence_schema")
    if isinstance(declared, dict):
        return dict(declared)
    first_test = payload.get("test", [{}])[0] if payload.get("test") else {}
    if not isinstance(first_test, dict):
        first_test = {}
    query_fields = [key for key in ("query", "text", "input", "features") if key in first_test]
    document_fields = ["candidates.id", "candidates.text"] if first_test.get("candidates") else []
    evidence_fields = [key for key in ("relevant_ids", "evidence", "evidence_labels") if key in first_test]
    label_fields = [key for key in ("label", "claim_label", "unsupported_claim") if key in first_test]
    return {
        "query_fields": query_fields,
        "document_fields": document_fields,
        "evidence_fields": evidence_fields,
        "label_fields": label_fields,
        "label_space": payload.get("label_space") or payload.get("verification_label_space") or [],
        "split_fields": [field for field in ("train", "test") if payload.get(field)],
        "supports_claim_verification": bool(payload.get("supports_claim_verification")),
        "schema_complete": bool(query_fields and (label_fields or evidence_fields or document_fields) and payload.get("train") and payload.get("test")),
    }


def _observation_coverage(benchmark: ResolvedBenchmark) -> dict[str, Any]:
    payload = benchmark.payload
    test = payload.get("test", [])
    train = payload.get("train", [])
    records = [item for item in [*train, *test] if isinstance(item, dict)]
    candidate_ids = {
        str(candidate.get("id"))
        for item in records
        for candidate in item.get("candidates", [])
        if isinstance(candidate, dict) and candidate.get("id") is not None
    }
    relevant_ids = {
        str(candidate_id)
        for item in records
        for candidate_id in item.get("relevant_ids", [])
        if candidate_id is not None
    }
    label_values = {
        str(item.get("label") or item.get("claim_label"))
        for item in records
        if item.get("label") is not None or item.get("claim_label") is not None
    }
    return {
        "query_count": int(payload.get("query_count") or len(test)),
        "document_count": int(payload.get("document_count") or len(candidate_ids)),
        "evidence_annotation_count": int(payload.get("evidence_annotation_count") or 0),
        "retrieval_relevance_count": int(payload.get("retrieval_relevance_count") or len(relevant_ids)),
        "label_count": len(label_values),
        "split_count": len([split for split in ("train", "test") if payload.get(split)]),
        "observation_complete": bool(records and (label_values or relevant_ids or candidate_ids)),
    }


def resolve_domain_benchmark(
    brief: AutoResearchResearchBriefRead,
) -> AutoResearchDomainBenchmarkResolverRead | None:
    decision = brief.domain_decision
    template = brief.domain_template or _template_or_none(decision.domain_id if decision else None)
    if decision is None or template is None or not decision.is_supported:
        payload = {
            "resolver_id": "unsupported_domain_benchmark_resolver_v1",
            "domain_id": "unsupported",
            "status": "blocked",
            "blockers": [
                decision.unsupported_reason if decision is not None and decision.unsupported_reason else "Unsupported domain has no benchmark resolver."
            ],
            "limitations": [],
            "required_followups": ["Add a complete supported-domain template before resolving benchmarks."],
            "kill_criteria": ["Do not generate toy experiment outputs for unsupported domains."],
            "evidence_refs": [f"brief:{brief.brief_id}:domain_decision"],
        }
        return AutoResearchDomainBenchmarkResolverRead(
            resolver_fingerprint=_fingerprint(payload),
            **payload,
        )
    benchmark = _resolved_benchmark_for_template(
        template,
        topic=brief.polished_idea,
        benchmark_source=brief.benchmark_source,
    )
    eligibility = benchmark_source_publication_eligibility(benchmark.source, benchmark.payload)
    schema = _schema_coverage(benchmark)
    observations = _observation_coverage(benchmark)
    source_class = str(eligibility.get("source_class") or "unknown")
    final_candidate = bool(benchmark.payload.get("final_publish_candidate_eligible")) or (
        bool(eligibility.get("publication_grade"))
        and int(eligibility.get("sample_count") or 0) >= 100
        and source_class in {"frozen_snapshot", "imported_real", "remote_real"}
    )
    domain_limitations: list[str] = []
    domain_blockers: list[str] = []
    domain_followups: list[str] = []
    imported_source_used = brief.benchmark_source is not None
    if template.domain_id == "claim_evidence_retrieval":
        domain_limitations.append(
            "Goal 1-compatible SciFact frozen snapshots support a scoped review/final-candidate audit, but same-release source independence remains a project-level final-publish blocker."
        )
    elif not imported_source_used:
        domain_blockers.append(
            "Repository-local fixture benchmark cannot be publication-grade or final-publish-candidate evidence."
        )
        domain_limitations.append(
            "This resolver result is deterministic review/engineering evidence only until a real/imported benchmark is attached."
        )
        domain_followups.append(
            "Import or freeze a real benchmark with source locator, dataset id, revision, license, fingerprint, adequate scale, and task-aware observations."
        )
        final_candidate = False
    elif not bool(eligibility.get("publication_grade")):
        domain_blockers.append(
            "Imported benchmark provenance is incomplete or below publication-grade eligibility."
        )
        domain_followups.append(
            "Repair imported benchmark provenance, license, fingerprint, source locator, scale, or schema before final-publish claims."
        )
        final_candidate = False
    else:
        domain_limitations.append(
            "Imported benchmark provenance can support domain readiness, but statistics, source independence, execution validation, and negative evidence still gate final publish."
        )
    blockers = _dedupe([*eligibility.get("blockers", []), *domain_blockers])
    status: AutoResearchDomainEvidenceStatus = "ready" if not blockers else "limited"
    payload = {
        "resolver_id": f"{template.domain_id}_benchmark_resolver_v1",
        "domain_id": template.domain_id,
        "status": status,
        "benchmark_name": benchmark.benchmark_name,
        "task_family": template.task_family,
        "source_kind": benchmark.source.kind,
        "source_class": source_class,
        "source_locator": eligibility.get("source_locator"),
        "dataset_id": eligibility.get("source_dataset_id"),
        "revision": eligibility.get("source_revision"),
        "license": eligibility.get("source_license"),
        "source_fingerprint": eligibility.get("source_fingerprint"),
        "sample_count": int(eligibility.get("sample_count") or 0),
        "train_split_count": int(eligibility.get("train_size") or 0),
        "test_split_count": int(eligibility.get("test_size") or 0),
        "label_schema_coverage": {
            "label_fields": schema.get("label_fields", []),
            "label_space": schema.get("label_space", []),
            "supports_claim_verification": schema.get("supports_claim_verification", False),
        },
        "query_document_evidence_schema_coverage": schema,
        "source_observation_coverage": observations,
        "benchmark_provenance_complete": bool(eligibility.get("provenance_complete")),
        "publication_grade_eligible": bool(eligibility.get("publication_grade")) and (
            template.domain_id == "claim_evidence_retrieval" or imported_source_used
        ),
        "final_candidate_eligible": final_candidate and (
            template.domain_id == "claim_evidence_retrieval" or imported_source_used
        ),
        "source_independence_audit": {
            "ready": False if template.domain_id == "claim_evidence_retrieval" or imported_source_used else None,
            "policy": (
                "Claim-evidence frozen verification and retrieval views share the same parent SciFact release; independent source replication remains required."
                if template.domain_id == "claim_evidence_retrieval"
                else "Imported benchmark provenance still requires independent source replication before final publish."
                if imported_source_used
                else "Fixture benchmark has no source-independence evidence."
            ),
            "blockers": (
                ["Independent source replication is required before broad final-publish claims."]
                if template.domain_id == "claim_evidence_retrieval"
                else ["Independent source replication is required before final-publish claims."]
                if imported_source_used
                else ["Fixture benchmark has no independent source provenance."]
            ),
        },
        "benchmark_payload_ref": (
            str(_SCIFACT_VERIFICATION_SNAPSHOT_PATH)
            if template.domain_id == "claim_evidence_retrieval"
            else brief.benchmark_source.file_path
            if imported_source_used and brief.benchmark_source is not None and brief.benchmark_source.file_path
            else brief.benchmark_source.url
            if imported_source_used and brief.benchmark_source is not None and brief.benchmark_source.url
            else f"builtin:{benchmark.benchmark_name}"
        ),
        "blockers": blockers,
        "limitations": _dedupe(
            [
                *domain_limitations,
                *(
                    []
                    if bool(eligibility.get("publication_grade"))
                    else ["Benchmark source is not publication-grade."]
                ),
            ]
        ),
        "required_followups": _dedupe(
            [
                *domain_followups,
                *(
                    ["Add independent benchmark/source replication before final publish."]
                    if template.domain_id == "claim_evidence_retrieval"
                    else []
                ),
            ]
        ),
        "kill_criteria": [
            "Block experiment claims if benchmark schema or expected output validation fails.",
            "Do not promote fixture or source-less benchmark results to publication-grade claims.",
        ],
        "evidence_refs": [
            f"brief:{brief.brief_id}:domain_template:{template.template_id}",
            f"benchmark:{benchmark.benchmark_name}:{eligibility.get('source_fingerprint')}",
        ],
    }
    return AutoResearchDomainBenchmarkResolverRead(
        resolver_fingerprint=_fingerprint(payload),
        **payload,
    )


def build_domain_experiment_protocol(
    brief: AutoResearchResearchBriefRead,
    *,
    benchmark_resolver: AutoResearchDomainBenchmarkResolverRead | None = None,
) -> AutoResearchDomainExperimentProtocolRead | None:
    decision = brief.domain_decision
    template = brief.domain_template or _template_or_none(decision.domain_id if decision else None)
    if decision is None or template is None or not decision.is_supported:
        payload = {
            "protocol_id": "unsupported_domain_protocol_v1",
            "domain_id": "unsupported",
            "status": "blocked",
            "deterministic_execution_route": "none",
            "import_replay_route": "none",
            "blockers": ["Unsupported domain has no experiment protocol."],
            "readiness_blockers": ["No supported-domain protocol can be executed."],
            "required_followups": ["Define a complete domain protocol before execution."],
            "kill_criteria": ["Do not synthesize experiment outputs for unsupported domains."],
            "evidence_refs": [f"brief:{brief.brief_id}:domain_decision"],
        }
        return AutoResearchDomainExperimentProtocolRead(
            protocol_fingerprint=_fingerprint(payload),
            **payload,
        )
    resolver_status: AutoResearchDomainEvidenceStatus = (
        benchmark_resolver.status if benchmark_resolver is not None else "blocked"
    )
    expected_outputs = [
        "method_outputs.json",
        "metrics.json",
        "evidence_ledger.json",
        "negative_evidence.json",
        "execution_profile.json",
        "environment_manifest.json",
        "benchmark_resolver_ref.json",
        "deterministic_fingerprint.txt",
    ]
    if template.domain_id == "rag_citation_faithfulness":
        expected_outputs.extend(["citation_support_scores.json", "unsupported_citations.json", "abstentions.json"])
        deterministic_route = "deterministic_citation_support_fixture_execution"
        import_route = "citation_faithfulness_replay_import_v1"
    elif template.domain_id == "lightweight_ml_nlp_benchmark":
        expected_outputs.extend(["classification_predictions.json", "baseline_comparison.json"])
        deterministic_route = "deterministic_local_text_classification_fixture_execution"
        import_route = "lightweight_ml_nlp_metric_replay_import_v1"
    else:
        expected_outputs.extend(["retrieval_evidence_ledger.json", "claim_verification_metrics.json"])
        deterministic_route = "cached_scifact_claim_evidence_execution"
        import_route = "claim_evidence_frozen_snapshot_replay_import_v1"
    readiness_blockers = _dedupe(
        [
            *(
                benchmark_resolver.blockers
                if benchmark_resolver is not None and benchmark_resolver.status == "blocked"
                else []
            ),
            *(
                [
                    "Experiment protocol is review-only until benchmark provenance and scale are publication-grade."
                ]
                if template.domain_id != "claim_evidence_retrieval"
                else []
            ),
        ]
    )
    status: AutoResearchDomainEvidenceStatus = (
        "blocked"
        if benchmark_resolver is None or benchmark_resolver.status == "blocked"
        else "limited"
        if readiness_blockers or template.domain_id != "claim_evidence_retrieval"
        else "ready"
    )
    payload = {
        "protocol_id": f"{template.domain_id}_experiment_protocol_v1",
        "domain_id": template.domain_id,
        "status": status,
        "method_baseline_ladder": list(template.method_baseline_ladder),
        "metric_schema": list(template.metric_schema),
        "expected_outputs": _dedupe(expected_outputs),
        "runtime_contract": {
            "deterministic": True,
            "requires_live_network": False,
            "requires_paid_llm": False,
            "requires_gpu": False,
            "requires_docker_daemon": False,
            "metric_schema": list(template.metric_schema),
            "expected_outputs": _dedupe(expected_outputs),
        },
        "deterministic_execution_route": deterministic_route,
        "import_replay_route": import_route,
        "evidence_ledger_schema": list(template.evidence_ledger_schema),
        "negative_evidence_categories": list(template.negative_evidence_taxonomy),
        "repair_routing_policy": {
            "missing_baseline": "add_missing_baseline",
            "missing_ablation": "add_missing_ablation",
            "insufficient_statistics": "increase_seed_count",
            "runtime_failure": "rerun_failed_job",
            "missing_output": "rerun_failed_job",
            "metric_schema_mismatch": "block_readiness_and_repair_protocol",
            "benchmark_mismatch": "block_readiness_and_resolve_benchmark",
        },
        "readiness_blockers": readiness_blockers,
        "final_publish_limitations": list(template.publish_readiness_constraints),
        "benchmark_resolver_id": benchmark_resolver.resolver_id if benchmark_resolver is not None else None,
        "benchmark_resolver_status": resolver_status,
        "protocol_complete": status != "blocked",
        "blockers": readiness_blockers if status == "blocked" else [],
        "limitations": _dedupe(
            [
                *template.publish_readiness_constraints,
                *(
                    ["Fixture/local smoke execution is non-final and review-only."]
                    if template.domain_id != "claim_evidence_retrieval"
                    else []
                ),
            ]
        ),
        "required_followups": _dedupe(
            [
                *(
                    benchmark_resolver.required_followups
                    if benchmark_resolver is not None
                    else ["Resolve benchmark before protocol execution."]
                ),
                "Validate metric schema against materialized outputs before evidence-ledger completion.",
            ]
        ),
        "kill_criteria": [
            "Block readiness if expected outputs are missing.",
            "Block readiness if metrics do not match the domain metric schema.",
            "Route runtime failures into repair classification rather than completed evidence.",
        ],
        "evidence_refs": [
            f"brief:{brief.brief_id}:domain_template:{template.template_id}",
            *(
                [f"benchmark_resolver:{benchmark_resolver.resolver_id}"]
                if benchmark_resolver is not None
                else []
            ),
        ],
    }
    return AutoResearchDomainExperimentProtocolRead(
        protocol_fingerprint=_fingerprint(payload),
        **payload,
    )


def domain_claim_ceiling(
    *,
    literature_result: AutoResearchDomainLiteratureResultRead | None,
    benchmark_resolver: AutoResearchDomainBenchmarkResolverRead | None,
    protocol: AutoResearchDomainExperimentProtocolRead | None,
) -> str:
    if benchmark_resolver is None or protocol is None:
        return "blocked_no_domain_evidence"
    if benchmark_resolver.domain_id == "unsupported" or protocol.status == "blocked":
        return "blocked_no_supported_domain_claim"
    if (
        benchmark_resolver.publication_grade_eligible
        and benchmark_resolver.final_candidate_eligible
        and literature_result is not None
        and literature_result.status in {"ready", "limited"}
    ):
        return "scoped_review_or_final_candidate_audit_claim"
    if benchmark_resolver.source_class in {"cached_fixture", "toy_builtin"}:
        return "review_only_engineering_validation_claim"
    return "technical_report_only"


def domain_readiness_status(
    *,
    literature_result: AutoResearchDomainLiteratureResultRead | None,
    benchmark_resolver: AutoResearchDomainBenchmarkResolverRead | None,
    protocol: AutoResearchDomainExperimentProtocolRead | None,
) -> AutoResearchDomainEvidenceStatus:
    statuses = [
        item.status
        for item in (literature_result, benchmark_resolver, protocol)
        if item is not None
    ]
    if not statuses or "blocked" in statuses:
        return "blocked"
    if "limited" in statuses:
        return "limited"
    return "ready"
