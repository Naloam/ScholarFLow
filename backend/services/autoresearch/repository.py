from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from schemas.autoresearch import (
    AutoResearchBundleAssetRead,
    AutoResearchBundleIndexRead,
    AutoResearchBundleRead,
    AutoResearchCandidateLineageRead,
    AutoResearchCandidateManifestCandidate,
    AutoResearchCandidateManifestRead,
    AutoResearchCandidateRegistryEntry,
    AutoResearchCandidateRegistryFiles,
    AutoResearchCandidateRegistryRead,
    AutoResearchEvidenceLedgerRead,
    AutoResearchExperimentExecutionPlanRead,
    AutoResearchExperimentExecutionResultRead,
    AutoResearchExperimentFactoryEnvironmentManifestRead,
    AutoResearchExperimentFactoryMaterializedJobRead,
    AutoResearchExperimentFactoryPlanRead,
    AutoResearchExperimentFactoryRepairPlanRead,
    AutoResearchResearchBriefRead,
    AutoResearchLineageEdgeRead,
    AutoResearchPaperRevisionActionIndexRead,
    AutoResearchPaperRevisionDiffRead,
    AutoResearchPaperSectionRewriteIndexRead,
    AutoResearchRegistryAssetRef,
    AutoResearchReviewerSimulationRead,
    AutoResearchReviewLoopRead,
    AutoResearchRegistryViewCounts,
    AutoResearchRegistryViewRead,
    AutoResearchRunRead,
    AutoResearchRunLineageRead,
    AutoResearchRunRegistryFiles,
    AutoResearchRunRegistryRead,
    AutoResearchRunRegistryViewsRead,
    BenchmarkSource,
    ExecutionBackendSpec,
    ExperimentSpec,
    HypothesisCandidate,
    AutoResearchRunConfig,
    PortfolioDecisionRecord,
    ResearchPlan,
)
from services.autoresearch.writer import PaperWriter, _compile_required_source_files
from services.autoresearch.paper_evidence_compiler import compile_paper_evidence
from services.workspace import autoresearch_dir


RUN_FILENAME = "run.json"
BRIEF_FILENAME = "brief.json"
PROGRAM_FILENAME = "program.json"
PLAN_FILENAME = "plan.json"
SPEC_FILENAME = "spec.json"
PORTFOLIO_FILENAME = "portfolio.json"
ARTIFACT_FILENAME = "artifact.json"
CODE_FILENAME = "experiment.py"
PAPER_FILENAME = "paper.md"
PROJECT_CONTEXT_FILENAME = "project_context.json"
NARRATIVE_REPORT_FILENAME = "narrative_report.md"
CLAIM_EVIDENCE_MATRIX_FILENAME = "claim_evidence_matrix.json"
EXPERIMENT_DESIGN_FILENAME = "experiment_design.json"
FAILURE_ANALYSIS_FILENAME = "failure_analysis.json"
RESEARCH_REPLAN_FILENAME = "research_replan.json"
RESEARCH_PROTOCOL_FILENAME = "research_protocol.json"
METHODOLOGY_AUDIT_FILENAME = "methodology_audit.json"
PUBLICATION_READINESS_FILENAME = "publication_readiness.json"
CONTRIBUTION_ASSESSMENT_FILENAME = "contribution_assessment.json"
LITERATURE_GRAPH_FILENAME = "literature_graph.json"
NOVELTY_VALIDATION_FILENAME = "novelty_validation.json"
REVISION_DOSSIER_FILENAME = "revision_dossier.json"
PUBLICATION_EVIDENCE_INDEX_FILENAME = "publication_evidence_index.json"
ARTIFACT_INTEGRITY_AUDIT_FILENAME = "artifact_integrity_audit.json"
PUBLICATION_REPAIR_PLAN_FILENAME = "publication_repair_plan.json"
PUBLICATION_REPAIR_EXECUTION_FILENAME = "publication_repair_execution.json"
REVIEWER_SIMULATION_FILENAME = "reviewer_simulation.json"
PAPER_PLAN_FILENAME = "paper_plan.json"
FIGURE_PLAN_FILENAME = "figure_plan.json"
EXPERIMENT_FACTORY_PLAN_FILENAME = "experiment_factory_plan.json"
EXPERIMENT_FACTORY_ENVIRONMENT_MANIFEST_FILENAME = "experiment_factory_environment_manifest.json"
EXPERIMENT_FACTORY_MATERIALIZED_JOBS_FILENAME = "experiment_factory_materialized_jobs.json"
EXPERIMENT_EXECUTION_PLAN_FILENAME = "experiment_execution_plan.json"
EXPERIMENT_EXECUTION_RESULT_FILENAME = "experiment_execution_result.json"
EVIDENCE_LEDGER_FILENAME = "evidence_ledger.json"
EXPERIMENT_FACTORY_REPAIR_PLAN_FILENAME = "experiment_factory_repair_plan.json"
PAPER_SECTION_REWRITE_INDEX_FILENAME = "paper_section_rewrite_index.json"
PAPER_REVISION_DIFF_FILENAME = "paper_revision_diff.json"
PAPER_REVISION_ACTION_INDEX_FILENAME = "paper_revision_action_index.json"
PAPER_REVISION_HISTORY_FILENAME = "revision_history.md"
PAPER_REVISION_DIFF_NOTE_FILENAME = "revision_diff.md"
PAPER_REVISION_ACTION_NOTE_FILENAME = "revision_actions.md"
PAPER_REVISION_BRIEF_FILENAME = "revision_brief.md"
PAPER_REVISION_STATE_FILENAME = "paper_revision_state.json"
PAPER_COMPILE_REPORT_FILENAME = "paper_compile_report.json"
PAPER_SOURCES_DIRNAME = "paper_sources"
PAPER_REWRITE_PACKETS_DIRNAME = "rewrite_packets"
PAPER_REWRITE_PACKET_INDEX_FILENAME = "index.json"
PAPER_CHECKPOINTS_DIRNAME = "checkpoints"
PAPER_CHECKPOINT_INDEX_FILENAME = "index.json"
PAPER_CHECKPOINT_SUMMARY_FILENAME = "checkpoint.json"
PAPER_CHECKPOINT_NOTE_FILENAME = "checkpoint_note.md"
PAPER_BUILD_SCRIPT_FILENAME = "build.sh"
PAPER_LATEX_FILENAME = "main.tex"
PAPER_BIB_FILENAME = "references.bib"
PAPER_SOURCES_MANIFEST_FILENAME = "manifest.json"
PAPER_COMPILED_PDF_FILENAME = "main.pdf"
PAPER_BIBLIOGRAPHY_OUTPUT_FILENAME = "main.bbl"
LITERATURE_SCOUT_CACHE_DIRNAME = "literature_scout_cache"
BENCHMARK_FILENAME = "benchmark.json"
BENCHMARK_CARD_FILENAME = "benchmark_card.json"
CANDIDATES_DIRNAME = "candidates"
CANDIDATE_FILENAME = "candidate.json"
ATTEMPTS_FILENAME = "attempts.json"
MANIFEST_FILENAME = "manifest.json"


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _runs_dir(project_id: str) -> Path:
    path = autoresearch_dir(project_id) / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _briefs_dir(project_id: str) -> Path:
    path = autoresearch_dir(project_id) / "briefs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _run_path(project_id: str, run_id: str) -> Path:
    return _runs_dir(project_id) / run_id


def _brief_path(project_id: str, brief_id: str) -> Path:
    return _briefs_dir(project_id) / brief_id


def _literature_scout_cache_dir(project_id: str) -> Path:
    path = autoresearch_dir(project_id) / LITERATURE_SCOUT_CACHE_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _literature_scout_cache_key(*, source: str, query: str, limit: int) -> str:
    payload = json.dumps(
        {"source": source, "query": query, "limit": limit},
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _candidate_path(project_id: str, run_id: str, candidate_id: str) -> Path:
    return _run_path(project_id, run_id) / CANDIDATES_DIRNAME / candidate_id


def run_dir(project_id: str, run_id: str) -> Path:
    path = _run_path(project_id, run_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def brief_dir(project_id: str, brief_id: str) -> Path:
    path = _brief_path(project_id, brief_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def candidate_dir(project_id: str, run_id: str, candidate_id: str) -> Path:
    path = _candidate_path(project_id, run_id, candidate_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    temporary_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary_path.write_text(encoded, encoding="utf-8")
    temporary_path.replace(path)


def _read_json(path: Path) -> object | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def literature_scout_cache_file_path(
    project_id: str,
    *,
    source: str,
    query: str,
    limit: int,
) -> str:
    key = _literature_scout_cache_key(source=source, query=query, limit=limit)
    safe_source = "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in source
    )
    return str(_literature_scout_cache_dir(project_id) / f"{safe_source}_{key[:20]}.json")


def load_literature_scout_cache(
    project_id: str,
    *,
    source: str,
    query: str,
    limit: int,
) -> dict[str, object] | None:
    payload = _read_json(
        Path(literature_scout_cache_file_path(project_id, source=source, query=query, limit=limit))
    )
    return payload if isinstance(payload, dict) else None


def save_literature_scout_cache(
    project_id: str,
    *,
    source: str,
    query: str,
    limit: int,
    payload: dict[str, object],
) -> str:
    path = Path(
        literature_scout_cache_file_path(project_id, source=source, query=query, limit=limit)
    )
    _write_json(
        path,
        {
            "source": source,
            "query": query,
            "limit": limit,
            **payload,
        },
    )
    return str(path)


def _sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _model_dump_without_generated_at(model: object) -> dict[str, object] | None:
    if not hasattr(model, "model_dump"):
        return None
    payload = model.model_dump(mode="json")
    if isinstance(payload, dict):
        payload.pop("generated_at", None)
        return payload
    return None


def _paper_revision_brief(run: AutoResearchRunRead) -> str | None:
    if run.paper_revision_state is None:
        return None
    return PaperWriter().build_revision_brief(
        run.paper_revision_state,
        paper_plan=run.paper_plan,
    )


def _paper_revision_history(run: AutoResearchRunRead) -> str | None:
    if run.paper_revision_state is None:
        return None
    return PaperWriter().build_revision_history(
        run.paper_revision_state,
        paper_plan=run.paper_plan,
    )


def _paper_build_script(run: AutoResearchRunRead) -> str | None:
    if run.paper_sources_manifest is None:
        return None
    return PaperWriter().build_paper_build_script(
        paper_sources_manifest=run.paper_sources_manifest,
    )


def _paper_revision_diff_note(run: AutoResearchRunRead) -> str | None:
    if run.paper_revision_diff is None:
        return None
    return PaperWriter().build_paper_revision_diff_note(
        run.paper_revision_diff,
        paper_plan=run.paper_plan,
    )


def _paper_revision_action_note(run: AutoResearchRunRead) -> str | None:
    if run.paper_revision_action_index is None:
        return None
    return PaperWriter().build_paper_revision_action_note(
        run.paper_revision_action_index,
        paper_plan=run.paper_plan,
    )


def _paper_section_rewrite_packets(
    run: AutoResearchRunRead,
) -> tuple[AutoResearchPaperSectionRewriteIndexRead | None, dict[str, str]]:
    if (
        run.paper_section_rewrite_index is None
        or run.paper_plan is None
        or run.claim_evidence_matrix is None
        or run.paper_revision_state is None
        or run.paper_markdown is None
    ):
        return None, {}
    writer = PaperWriter()
    packets = {
        item.relative_path: writer.build_section_rewrite_packet(
            item,
            paper_plan=run.paper_plan,
            claim_evidence_matrix=run.claim_evidence_matrix,
            paper_revision_state=run.paper_revision_state,
            paper_markdown=run.paper_markdown,
        )
        for item in run.paper_section_rewrite_index.packets
    }
    return run.paper_section_rewrite_index, packets


def _load_review_loop_snapshot(base: Path) -> AutoResearchReviewLoopRead | None:
    path = base / "review_loop.json"
    if not path.is_file():
        return None
    try:
        return AutoResearchReviewLoopRead.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_previous_revision_checkpoint_snapshot(
    payload: AutoResearchRunRead,
    *,
    base: Path,
) -> tuple[int | None, str | None, AutoResearchPaperSectionRewriteIndexRead | None]:
    if payload.paper_revision_state is None or payload.paper_revision_state.revision_round <= 0:
        return None, None, None
    paper_sources_dir = Path(payload.paper_sources_dir) if payload.paper_sources_dir else (base / PAPER_SOURCES_DIRNAME)
    current_round = payload.paper_revision_state.revision_round
    prior_rounds = sorted(
        {
            item.revision_round
            for item in payload.paper_revision_state.checkpoints
            if item.revision_round < current_round
        },
        reverse=True,
    )
    for revision_round in prior_rounds:
        checkpoint_dir = _paper_checkpoint_dir(paper_sources_dir, revision_round)
        paper_path = checkpoint_dir / PAPER_FILENAME
        rewrite_index_path = checkpoint_dir / PAPER_REWRITE_PACKETS_DIRNAME / PAPER_REWRITE_PACKET_INDEX_FILENAME
        previous_paper_markdown = paper_path.read_text(encoding="utf-8") if paper_path.is_file() else None
        previous_section_rewrite_index = (
            AutoResearchPaperSectionRewriteIndexRead.model_validate_json(
                rewrite_index_path.read_text(encoding="utf-8")
            )
            if rewrite_index_path.is_file()
            else None
        )
        if previous_paper_markdown is not None or previous_section_rewrite_index is not None:
            return revision_round, previous_paper_markdown, previous_section_rewrite_index
    return None, None, None


def _paper_checkpoint_dir(paper_sources_dir: Path, revision_round: int) -> Path:
    return paper_sources_dir / PAPER_CHECKPOINTS_DIRNAME / f"round_{revision_round:04d}"


def _write_paper_revision_checkpoints(
    payload: AutoResearchRunRead,
    *,
    base: Path,
    paper_sources_dir: Path,
    revision_brief: str | None,
    revision_diff_note: str | None,
    revision_action_note: str | None,
    revision_history: str | None,
    paper_build_script: str | None,
) -> None:
    if payload.paper_revision_state is None:
        return

    section_rewrite_index, section_rewrite_packets = _paper_section_rewrite_packets(payload)
    checkpoints_dir = paper_sources_dir / PAPER_CHECKPOINTS_DIRNAME
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        checkpoints_dir / PAPER_CHECKPOINT_INDEX_FILENAME,
        {
            "generated_at": _utcnow().isoformat(),
            "current_revision_round": payload.paper_revision_state.revision_round,
            "checkpoints": payload.paper_revision_state.model_dump(mode="json")["checkpoints"],
        },
    )
    current_round = payload.paper_revision_state.revision_round
    review_path = base / "review.json"
    review_loop_path = base / "review_loop.json"

    for checkpoint in payload.paper_revision_state.checkpoints:
        checkpoint_dir = _paper_checkpoint_dir(paper_sources_dir, checkpoint.revision_round)
        checkpoint_summary_path = checkpoint_dir / PAPER_CHECKPOINT_SUMMARY_FILENAME
        should_refresh = checkpoint.revision_round == current_round or not checkpoint_summary_path.exists()
        if not should_refresh:
            continue
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        _write_json(checkpoint_summary_path, checkpoint.model_dump(mode="json"))
        checkpoint_note = PaperWriter().build_revision_checkpoint_note(
            checkpoint,
            paper_plan=payload.paper_plan,
        )
        (checkpoint_dir / PAPER_CHECKPOINT_NOTE_FILENAME).write_text(checkpoint_note, encoding="utf-8")
        if payload.paper_markdown is not None:
            (checkpoint_dir / PAPER_FILENAME).write_text(payload.paper_markdown, encoding="utf-8")
        if payload.narrative_report_markdown:
            (checkpoint_dir / NARRATIVE_REPORT_FILENAME).write_text(
                payload.narrative_report_markdown,
                encoding="utf-8",
            )
        if payload.claim_evidence_matrix is not None:
            _write_json(
                checkpoint_dir / CLAIM_EVIDENCE_MATRIX_FILENAME,
                payload.claim_evidence_matrix.model_dump(mode="json"),
            )
        if payload.paper_plan is not None:
            _write_json(
                checkpoint_dir / PAPER_PLAN_FILENAME,
                payload.paper_plan.model_dump(mode="json"),
            )
        if payload.figure_plan is not None:
            _write_json(
                checkpoint_dir / FIGURE_PLAN_FILENAME,
                payload.figure_plan.model_dump(mode="json"),
            )
        if revision_history is not None:
            (checkpoint_dir / PAPER_REVISION_HISTORY_FILENAME).write_text(revision_history, encoding="utf-8")
        if revision_brief is not None:
            (checkpoint_dir / PAPER_REVISION_BRIEF_FILENAME).write_text(revision_brief, encoding="utf-8")
        _write_json(
            checkpoint_dir / PAPER_REVISION_STATE_FILENAME,
            payload.paper_revision_state.model_dump(mode="json"),
        )
        if payload.paper_compile_report is not None:
            _write_json(
                checkpoint_dir / PAPER_COMPILE_REPORT_FILENAME,
                payload.paper_compile_report.model_dump(mode="json"),
            )
        if payload.paper_revision_diff is not None:
            _write_json(
                checkpoint_dir / PAPER_REVISION_DIFF_FILENAME,
                payload.paper_revision_diff.model_dump(mode="json"),
            )
        if revision_diff_note is not None:
            (checkpoint_dir / PAPER_REVISION_DIFF_NOTE_FILENAME).write_text(revision_diff_note, encoding="utf-8")
        if payload.paper_revision_action_index is not None:
            _write_json(
                checkpoint_dir / PAPER_REVISION_ACTION_INDEX_FILENAME,
                payload.paper_revision_action_index.model_dump(mode="json"),
            )
        if revision_action_note is not None:
            (checkpoint_dir / PAPER_REVISION_ACTION_NOTE_FILENAME).write_text(revision_action_note, encoding="utf-8")
        if paper_build_script is not None:
            build_script_path = checkpoint_dir / PAPER_BUILD_SCRIPT_FILENAME
            build_script_path.write_text(paper_build_script, encoding="utf-8")
            build_script_path.chmod(0o755)
        if payload.paper_latex_source is not None:
            (checkpoint_dir / PAPER_LATEX_FILENAME).write_text(payload.paper_latex_source, encoding="utf-8")
        if payload.paper_bibliography_bib is not None:
            (checkpoint_dir / PAPER_BIB_FILENAME).write_text(payload.paper_bibliography_bib, encoding="utf-8")
        if payload.paper_sources_manifest is not None:
            _write_json(
                checkpoint_dir / PAPER_SOURCES_MANIFEST_FILENAME,
                payload.paper_sources_manifest.model_dump(mode="json"),
            )
        if section_rewrite_index is not None:
            checkpoint_packets_dir = checkpoint_dir / PAPER_REWRITE_PACKETS_DIRNAME
            checkpoint_packets_dir.mkdir(parents=True, exist_ok=True)
            _write_json(
                checkpoint_packets_dir / PAPER_REWRITE_PACKET_INDEX_FILENAME,
                section_rewrite_index.model_dump(mode="json"),
            )
            for relative_path, content in section_rewrite_packets.items():
                packet_path = checkpoint_dir / relative_path
                packet_path.parent.mkdir(parents=True, exist_ok=True)
                packet_path.write_text(content, encoding="utf-8")
        if review_path.is_file():
            (checkpoint_dir / "review.json").write_text(review_path.read_text(encoding="utf-8"), encoding="utf-8")
        if review_loop_path.is_file():
            (checkpoint_dir / "review_loop.json").write_text(
                review_loop_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )


def _asset_ref(path: Path | str | None, *, kind: str = "file") -> AutoResearchRegistryAssetRef | None:
    if path is None:
        return None
    candidate = Path(path)
    exists = candidate.exists()
    size_bytes = candidate.stat().st_size if exists and candidate.is_file() else None
    return AutoResearchRegistryAssetRef(
        path=str(candidate),
        kind="directory" if kind == "directory" else "file",
        exists=exists,
        size_bytes=size_bytes,
        sha256=_sha256_file(candidate) if exists and candidate.is_file() else None,
    )


def _candidate_registry_files(
    *,
    base: Path,
    manifest_path: Path,
    candidate: HypothesisCandidate,
    manifest_files: dict[str, object] | None = None,
) -> AutoResearchCandidateRegistryFiles:
    payload = manifest_files or {}

    def _payload_path(key: str, fallback: Path | str | None) -> Path | str | None:
        value = payload.get(key)
        return value if isinstance(value, str) and value else fallback

    return AutoResearchCandidateRegistryFiles(
        workspace=_asset_ref(_payload_path("workspace_path", base), kind="directory")
        or AutoResearchRegistryAssetRef(path=str(base), kind="directory", exists=False),
        candidate_json=_asset_ref(_payload_path("candidate_path", base / CANDIDATE_FILENAME)),
        plan_json=_asset_ref(_payload_path("plan_path", candidate.plan_path or base / PLAN_FILENAME)),
        spec_json=_asset_ref(_payload_path("spec_path", candidate.spec_path or base / SPEC_FILENAME)),
        attempts_json=_asset_ref(
            _payload_path(
                "attempts_path",
                candidate.attempts_path or (base / ATTEMPTS_FILENAME),
            )
        ),
        artifact_json=_asset_ref(
            _payload_path(
                "artifact_path",
                candidate.artifact_path or (base / ARTIFACT_FILENAME),
            )
        ),
        manifest_json=_asset_ref(manifest_path),
        generated_code=_asset_ref(
            _payload_path("generated_code_path", candidate.generated_code_path),
        ),
        paper_markdown=_asset_ref(
            _payload_path(
                "paper_path",
                candidate.paper_path or (base / PAPER_FILENAME),
            )
        ),
    )


def _fallback_candidate_manifest(
    *,
    project_id: str,
    run_id: str,
    candidate: HypothesisCandidate,
    decision: PortfolioDecisionRecord | None = None,
) -> AutoResearchCandidateManifestRead:
    base = _candidate_path(project_id, run_id, candidate.id)
    manifest_path = base / MANIFEST_FILENAME
    return AutoResearchCandidateManifestRead(
        manifest_source="generated_fallback",
        candidate=AutoResearchCandidateManifestCandidate(
            id=candidate.id,
            program_id=candidate.program_id,
            rank=candidate.rank,
            title=candidate.title,
            status=candidate.status,
            objective_score=candidate.score,
            selection_reason=candidate.selection_reason,
        ),
        decision=decision,
        files=_candidate_registry_files(
            base=base,
            manifest_path=manifest_path,
            candidate=candidate,
        ),
    )


def _candidate_lineage_edges(
    *,
    run_id: str,
    candidate_id: str,
    files: AutoResearchCandidateRegistryFiles,
    selected: bool,
    run_assets: AutoResearchRunRegistryFiles | None = None,
) -> list[AutoResearchLineageEdgeRead]:
    edges: list[AutoResearchLineageEdgeRead] = [
        AutoResearchLineageEdgeRead(
            source_kind="run",
            source_id=run_id,
            relation="selected_candidate" if selected else "owns",
            target_kind="candidate",
            target_id=candidate_id,
        ),
        AutoResearchLineageEdgeRead(
            source_kind="candidate",
            source_id=candidate_id,
            relation="has_asset",
            target_kind="workspace",
            target_id=f"{candidate_id}:workspace",
            target_path=files.workspace.path,
            exists=files.workspace.exists,
        ),
    ]

    file_targets = [
        ("candidate_json", "candidate"),
        ("plan_json", "plan"),
        ("spec_json", "spec"),
        ("attempts_json", "attempts"),
        ("artifact_json", "artifact"),
        ("manifest_json", "manifest"),
        ("generated_code", "generated_code"),
        ("paper_markdown", "paper"),
    ]
    for attr, target_kind in file_targets:
        ref = getattr(files, attr)
        if ref is None:
            continue
        edges.append(
            AutoResearchLineageEdgeRead(
                source_kind="candidate",
                source_id=candidate_id,
                relation="has_asset",
                target_kind=target_kind,
                target_id=f"{candidate_id}:{target_kind}",
                target_path=ref.path,
                exists=ref.exists,
            )
        )

    if selected and run_assets is not None:
        mirrored_assets = [
            ("plan_json", "plan"),
            ("spec_json", "spec"),
            ("artifact_json", "artifact"),
            ("paper_markdown", "paper"),
            ("narrative_report_markdown", "narrative_report"),
            ("claim_evidence_matrix_json", "claim_evidence_matrix"),
            ("experiment_design_json", "experiment_design"),
            ("failure_analysis_json", "failure_analysis"),
            ("research_replan_json", "research_replan"),
            ("benchmark_card_json", "benchmark_card"),
            ("research_protocol_json", "research_protocol"),
            ("methodology_audit_json", "methodology_audit"),
            ("publication_readiness_json", "publication_readiness"),
            ("contribution_assessment_json", "contribution_assessment"),
            ("literature_graph_json", "literature_graph"),
            ("novelty_validation_json", "novelty_validation"),
            ("revision_dossier_json", "revision_dossier"),
            ("publication_evidence_index_json", "publication_evidence_index"),
            ("artifact_integrity_audit_json", "artifact_integrity_audit"),
            ("publication_repair_plan_json", "publication_repair_plan"),
            ("publication_repair_execution_json", "publication_repair_execution"),
            ("reviewer_simulation_json", "reviewer_simulation"),
            ("experiment_factory_plan_json", "experiment_factory_plan"),
            (
                "experiment_factory_environment_manifest_json",
                "experiment_factory_environment_manifest",
            ),
            ("experiment_factory_materialized_jobs_json", "experiment_factory_materialized_jobs"),
            ("evidence_ledger_json", "evidence_ledger"),
            ("experiment_factory_repair_plan_json", "experiment_factory_repair_plan"),
            ("paper_plan_json", "paper_plan"),
            ("figure_plan_json", "figure_plan"),
            ("paper_revision_history_markdown", "paper_revision_history"),
            ("paper_revision_state_json", "paper_revision_state"),
            ("paper_compile_report_json", "paper_compile_report"),
            ("paper_revision_diff_json", "paper_revision_diff"),
            ("paper_revision_action_index_json", "paper_revision_action_index"),
            ("paper_section_rewrite_index_json", "paper_section_rewrite_index"),
            ("paper_revision_brief_markdown", "paper_revision_brief"),
            ("paper_sources_dir", "paper_sources"),
            ("paper_section_rewrite_packets_dir", "paper_section_rewrite_packets"),
            ("paper_build_script", "paper_build_script"),
            ("paper_checkpoint_index_json", "paper_checkpoint_index"),
            ("paper_latex_source", "paper_latex"),
            ("paper_bibliography_bib", "paper_bibliography"),
            ("paper_sources_manifest_json", "paper_sources_manifest"),
            ("paper_compiled_pdf", "paper_compiled_pdf"),
            ("paper_bibliography_output_bbl", "paper_bibliography_output"),
            ("generated_code", "generated_code"),
        ]
        for attr, target_kind in mirrored_assets:
            ref = getattr(run_assets, attr)
            if ref is None:
                continue
            edges.append(
                AutoResearchLineageEdgeRead(
                    source_kind="candidate",
                    source_id=candidate_id,
                    relation="materialized_to_run_asset",
                    target_kind=target_kind,
                    target_id=f"{run_id}:{target_kind}",
                    target_path=ref.path,
                    exists=ref.exists,
                )
            )
    return edges


def _run_derivation_lineage_edges(
    *,
    run: AutoResearchRunRead,
    run_assets: AutoResearchRunRegistryFiles,
) -> list[AutoResearchLineageEdgeRead]:
    edges: list[AutoResearchLineageEdgeRead] = []

    def add_derivation(
        *,
        source_kind: str,
        source_id: str,
        target_attr: str,
        target_kind: str,
    ) -> None:
        ref = getattr(run_assets, target_attr)
        if ref is None:
            return
        edges.append(
            AutoResearchLineageEdgeRead(
                source_kind=source_kind,
                source_id=source_id,
                relation="derived_from",
                target_kind=target_kind,
                target_id=f"{run.id}:{target_kind}",
                target_path=ref.path,
                exists=ref.exists,
            )
        )

    if run_assets.artifact_json is not None:
        artifact_source_id = f"{run.id}:artifact"
        add_derivation(
            source_kind="artifact",
            source_id=artifact_source_id,
            target_attr="spec_json",
            target_kind="spec",
        )
        add_derivation(
            source_kind="artifact",
            source_id=artifact_source_id,
            target_attr="generated_code",
            target_kind="generated_code",
        )
        add_derivation(
            source_kind="artifact",
            source_id=artifact_source_id,
            target_attr="benchmark_json",
            target_kind="benchmark",
        )
        add_derivation(
            source_kind="artifact",
            source_id=artifact_source_id,
            target_attr="benchmark_card_json",
            target_kind="benchmark_card",
        )
        add_derivation(
            source_kind="artifact",
            source_id=artifact_source_id,
            target_attr="experiment_design_json",
            target_kind="experiment_design",
        )
        add_derivation(
            source_kind="artifact",
            source_id=artifact_source_id,
            target_attr="failure_analysis_json",
            target_kind="failure_analysis",
        )
        add_derivation(
            source_kind="artifact",
            source_id=artifact_source_id,
            target_attr="publication_readiness_json",
            target_kind="publication_readiness",
        )
        add_derivation(
            source_kind="artifact",
            source_id=artifact_source_id,
            target_attr="contribution_assessment_json",
            target_kind="contribution_assessment",
        )
        add_derivation(
            source_kind="artifact",
            source_id=artifact_source_id,
            target_attr="novelty_validation_json",
            target_kind="novelty_validation",
        )

    if run_assets.paper_markdown is not None:
        paper_source_id = f"{run.id}:paper"
        for target_attr, target_kind in (
            ("plan_json", "plan"),
            ("spec_json", "spec"),
            ("artifact_json", "artifact"),
            ("claim_evidence_matrix_json", "claim_evidence_matrix"),
            ("experiment_design_json", "experiment_design"),
            ("failure_analysis_json", "failure_analysis"),
            ("research_replan_json", "research_replan"),
            ("benchmark_card_json", "benchmark_card"),
            ("research_protocol_json", "research_protocol"),
            ("methodology_audit_json", "methodology_audit"),
            ("publication_readiness_json", "publication_readiness"),
            ("contribution_assessment_json", "contribution_assessment"),
            ("literature_graph_json", "literature_graph"),
            ("novelty_validation_json", "novelty_validation"),
            ("revision_dossier_json", "revision_dossier"),
            ("publication_evidence_index_json", "publication_evidence_index"),
            ("publication_repair_plan_json", "publication_repair_plan"),
            ("publication_repair_execution_json", "publication_repair_execution"),
            ("reviewer_simulation_json", "reviewer_simulation"),
            ("experiment_factory_plan_json", "experiment_factory_plan"),
            ("evidence_ledger_json", "evidence_ledger"),
            ("experiment_factory_repair_plan_json", "experiment_factory_repair_plan"),
            ("narrative_report_markdown", "narrative_report"),
            ("paper_plan_json", "paper_plan"),
            ("figure_plan_json", "figure_plan"),
            ("generated_code", "generated_code"),
            ("benchmark_json", "benchmark"),
        ):
            add_derivation(
                source_kind="paper",
                source_id=paper_source_id,
                target_attr=target_attr,
                target_kind=target_kind,
            )

    if run_assets.claim_evidence_matrix_json is not None:
        add_derivation(
            source_kind="claim_evidence_matrix",
            source_id=f"{run.id}:claim_evidence_matrix",
            target_attr="experiment_design_json",
            target_kind="experiment_design",
        )
        add_derivation(
            source_kind="claim_evidence_matrix",
            source_id=f"{run.id}:claim_evidence_matrix",
            target_attr="failure_analysis_json",
            target_kind="failure_analysis",
        )
        add_derivation(
            source_kind="claim_evidence_matrix",
            source_id=f"{run.id}:claim_evidence_matrix",
            target_attr="publication_readiness_json",
            target_kind="publication_readiness",
        )
        add_derivation(
            source_kind="claim_evidence_matrix",
            source_id=f"{run.id}:claim_evidence_matrix",
            target_attr="contribution_assessment_json",
            target_kind="contribution_assessment",
        )
        add_derivation(
            source_kind="claim_evidence_matrix",
            source_id=f"{run.id}:claim_evidence_matrix",
            target_attr="literature_graph_json",
            target_kind="literature_graph",
        )
        add_derivation(
            source_kind="claim_evidence_matrix",
            source_id=f"{run.id}:claim_evidence_matrix",
            target_attr="novelty_validation_json",
            target_kind="novelty_validation",
        )
    if run_assets.spec_json is not None:
        add_derivation(
            source_kind="spec",
            source_id=f"{run.id}:spec",
            target_attr="experiment_design_json",
            target_kind="experiment_design",
        )
        add_derivation(
            source_kind="spec",
            source_id=f"{run.id}:spec",
            target_attr="research_protocol_json",
            target_kind="research_protocol",
        )
        add_derivation(
            source_kind="spec",
            source_id=f"{run.id}:spec",
            target_attr="benchmark_card_json",
            target_kind="benchmark_card",
        )
    if run_assets.benchmark_json is not None:
        add_derivation(
            source_kind="benchmark",
            source_id=f"{run.id}:benchmark",
            target_attr="benchmark_card_json",
            target_kind="benchmark_card",
        )
    if run_assets.plan_json is not None:
        add_derivation(
            source_kind="plan",
            source_id=f"{run.id}:plan",
            target_attr="experiment_design_json",
            target_kind="experiment_design",
        )
        add_derivation(
            source_kind="plan",
            source_id=f"{run.id}:plan",
            target_attr="research_protocol_json",
            target_kind="research_protocol",
        )
    if run_assets.experiment_design_json is not None:
        add_derivation(
            source_kind="experiment_design",
            source_id=f"{run.id}:experiment_design",
            target_attr="research_protocol_json",
            target_kind="research_protocol",
        )
        add_derivation(
            source_kind="experiment_design",
            source_id=f"{run.id}:experiment_design",
            target_attr="methodology_audit_json",
            target_kind="methodology_audit",
        )
        add_derivation(
            source_kind="experiment_design",
            source_id=f"{run.id}:experiment_design",
            target_attr="publication_evidence_index_json",
            target_kind="publication_evidence_index",
        )
        add_derivation(
            source_kind="experiment_design",
            source_id=f"{run.id}:experiment_design",
            target_attr="failure_analysis_json",
            target_kind="failure_analysis",
        )
    if run_assets.research_protocol_json is not None:
        add_derivation(
            source_kind="research_protocol",
            source_id=f"{run.id}:research_protocol",
            target_attr="methodology_audit_json",
            target_kind="methodology_audit",
        )
    if run_assets.artifact_json is not None:
        add_derivation(
            source_kind="artifact",
            source_id=f"{run.id}:artifact",
            target_attr="methodology_audit_json",
            target_kind="methodology_audit",
        )
    if run_assets.claim_evidence_matrix_json is not None:
        add_derivation(
            source_kind="claim_evidence_matrix",
            source_id=f"{run.id}:claim_evidence_matrix",
            target_attr="methodology_audit_json",
            target_kind="methodology_audit",
        )
    if run_assets.paper_compile_report_json is not None:
        add_derivation(
            source_kind="paper_compile_report",
            source_id=f"{run.id}:paper_compile_report",
            target_attr="methodology_audit_json",
            target_kind="methodology_audit",
        )
    if run_assets.methodology_audit_json is not None:
        add_derivation(
            source_kind="methodology_audit",
            source_id=f"{run.id}:methodology_audit",
            target_attr="publication_readiness_json",
            target_kind="publication_readiness",
        )
        add_derivation(
            source_kind="methodology_audit",
            source_id=f"{run.id}:methodology_audit",
            target_attr="revision_dossier_json",
            target_kind="revision_dossier",
        )
    if run_assets.publication_readiness_json is not None:
        add_derivation(
            source_kind="publication_readiness",
            source_id=f"{run.id}:publication_readiness",
            target_attr="contribution_assessment_json",
            target_kind="contribution_assessment",
        )
        add_derivation(
            source_kind="publication_readiness",
            source_id=f"{run.id}:publication_readiness",
            target_attr="failure_analysis_json",
            target_kind="failure_analysis",
        )
        add_derivation(
            source_kind="publication_readiness",
            source_id=f"{run.id}:publication_readiness",
            target_attr="revision_dossier_json",
            target_kind="revision_dossier",
        )
    if run_assets.contribution_assessment_json is not None:
        add_derivation(
            source_kind="contribution_assessment",
            source_id=f"{run.id}:contribution_assessment",
            target_attr="revision_dossier_json",
            target_kind="revision_dossier",
        )
        add_derivation(
            source_kind="contribution_assessment",
            source_id=f"{run.id}:contribution_assessment",
            target_attr="failure_analysis_json",
            target_kind="failure_analysis",
        )
        add_derivation(
            source_kind="contribution_assessment",
            source_id=f"{run.id}:contribution_assessment",
            target_attr="publication_evidence_index_json",
            target_kind="publication_evidence_index",
        )
    if run_assets.literature_graph_json is not None:
        add_derivation(
            source_kind="literature_graph",
            source_id=f"{run.id}:literature_graph",
            target_attr="novelty_validation_json",
            target_kind="novelty_validation",
        )
        add_derivation(
            source_kind="literature_graph",
            source_id=f"{run.id}:literature_graph",
            target_attr="publication_evidence_index_json",
            target_kind="publication_evidence_index",
        )
    if run_assets.novelty_validation_json is not None:
        add_derivation(
            source_kind="novelty_validation",
            source_id=f"{run.id}:novelty_validation",
            target_attr="revision_dossier_json",
            target_kind="revision_dossier",
        )
        add_derivation(
            source_kind="novelty_validation",
            source_id=f"{run.id}:novelty_validation",
            target_attr="failure_analysis_json",
            target_kind="failure_analysis",
        )
        add_derivation(
            source_kind="novelty_validation",
            source_id=f"{run.id}:novelty_validation",
            target_attr="publication_evidence_index_json",
            target_kind="publication_evidence_index",
        )
    if run_assets.claim_evidence_matrix_json is not None:
        add_derivation(
            source_kind="claim_evidence_matrix",
            source_id=f"{run.id}:claim_evidence_matrix",
            target_attr="revision_dossier_json",
            target_kind="revision_dossier",
        )
        add_derivation(
            source_kind="claim_evidence_matrix",
            source_id=f"{run.id}:claim_evidence_matrix",
            target_attr="publication_evidence_index_json",
            target_kind="publication_evidence_index",
        )
    if run_assets.benchmark_card_json is not None:
        add_derivation(
            source_kind="benchmark_card",
            source_id=f"{run.id}:benchmark_card",
            target_attr="publication_evidence_index_json",
            target_kind="publication_evidence_index",
        )
    if run_assets.research_protocol_json is not None:
        add_derivation(
            source_kind="research_protocol",
            source_id=f"{run.id}:research_protocol",
            target_attr="publication_evidence_index_json",
            target_kind="publication_evidence_index",
        )
    if run_assets.methodology_audit_json is not None:
        add_derivation(
            source_kind="methodology_audit",
            source_id=f"{run.id}:methodology_audit",
            target_attr="publication_evidence_index_json",
            target_kind="publication_evidence_index",
        )
    if run_assets.publication_readiness_json is not None:
        add_derivation(
            source_kind="publication_readiness",
            source_id=f"{run.id}:publication_readiness",
            target_attr="publication_evidence_index_json",
            target_kind="publication_evidence_index",
        )
    if run_assets.revision_dossier_json is not None:
        add_derivation(
            source_kind="revision_dossier",
            source_id=f"{run.id}:revision_dossier",
            target_attr="publication_evidence_index_json",
            target_kind="publication_evidence_index",
        )
        add_derivation(
            source_kind="revision_dossier",
            source_id=f"{run.id}:revision_dossier",
            target_attr="publication_repair_plan_json",
            target_kind="publication_repair_plan",
        )
    if run_assets.publication_evidence_index_json is not None:
        add_derivation(
            source_kind="publication_evidence_index",
            source_id=f"{run.id}:publication_evidence_index",
            target_attr="publication_repair_plan_json",
            target_kind="publication_repair_plan",
        )
    if run_assets.reviewer_simulation_json is not None:
        add_derivation(
            source_kind="reviewer_simulation",
            source_id=f"{run.id}:reviewer_simulation",
            target_attr="publication_repair_plan_json",
            target_kind="publication_repair_plan",
        )
    if run_assets.experiment_factory_plan_json is not None:
        add_derivation(
            source_kind="experiment_factory_plan",
            source_id=f"{run.id}:experiment_factory_plan",
            target_attr="experiment_factory_environment_manifest_json",
            target_kind="experiment_factory_environment_manifest",
        )
        add_derivation(
            source_kind="experiment_factory_plan",
            source_id=f"{run.id}:experiment_factory_plan",
            target_attr="experiment_factory_materialized_jobs_json",
            target_kind="experiment_factory_materialized_jobs",
        )
        add_derivation(
            source_kind="experiment_factory_plan",
            source_id=f"{run.id}:experiment_factory_plan",
            target_attr="evidence_ledger_json",
            target_kind="evidence_ledger",
        )
        add_derivation(
            source_kind="experiment_factory_plan",
            source_id=f"{run.id}:experiment_factory_plan",
            target_attr="artifact_json",
            target_kind="artifact",
        )
    if run_assets.experiment_factory_materialized_jobs_json is not None:
        add_derivation(
            source_kind="experiment_factory_materialized_jobs",
            source_id=f"{run.id}:experiment_factory_materialized_jobs",
            target_attr="artifact_json",
            target_kind="artifact",
        )
        add_derivation(
            source_kind="experiment_factory_materialized_jobs",
            source_id=f"{run.id}:experiment_factory_materialized_jobs",
            target_attr="evidence_ledger_json",
            target_kind="evidence_ledger",
        )
    if run_assets.evidence_ledger_json is not None:
        add_derivation(
            source_kind="evidence_ledger",
            source_id=f"{run.id}:evidence_ledger",
            target_attr="experiment_factory_repair_plan_json",
            target_kind="experiment_factory_repair_plan",
        )
    if run_assets.failure_analysis_json is not None:
        add_derivation(
            source_kind="failure_analysis",
            source_id=f"{run.id}:failure_analysis",
            target_attr="research_replan_json",
            target_kind="research_replan",
        )
        add_derivation(
            source_kind="failure_analysis",
            source_id=f"{run.id}:failure_analysis",
            target_attr="publication_evidence_index_json",
            target_kind="publication_evidence_index",
        )
        add_derivation(
            source_kind="failure_analysis",
            source_id=f"{run.id}:failure_analysis",
            target_attr="publication_repair_plan_json",
            target_kind="publication_repair_plan",
        )
    if run_assets.research_replan_json is not None:
        add_derivation(
            source_kind="research_replan",
            source_id=f"{run.id}:research_replan",
            target_attr="publication_evidence_index_json",
            target_kind="publication_evidence_index",
        )
        add_derivation(
            source_kind="research_replan",
            source_id=f"{run.id}:research_replan",
            target_attr="publication_repair_plan_json",
            target_kind="publication_repair_plan",
        )
    if run_assets.artifact_integrity_audit_json is not None:
        add_derivation(
            source_kind="run",
            source_id=run.id,
            target_attr="artifact_integrity_audit_json",
            target_kind="artifact_integrity_audit",
        )
    if run_assets.publication_readiness_json is not None:
        add_derivation(
            source_kind="publication_readiness",
            source_id=f"{run.id}:publication_readiness",
            target_attr="publication_repair_plan_json",
            target_kind="publication_repair_plan",
        )
    if run_assets.contribution_assessment_json is not None:
        add_derivation(
            source_kind="contribution_assessment",
            source_id=f"{run.id}:contribution_assessment",
            target_attr="publication_repair_plan_json",
            target_kind="publication_repair_plan",
        )
    if run_assets.novelty_validation_json is not None:
        add_derivation(
            source_kind="novelty_validation",
            source_id=f"{run.id}:novelty_validation",
            target_attr="publication_repair_plan_json",
            target_kind="publication_repair_plan",
        )
    if run_assets.publication_repair_plan_json is not None:
        add_derivation(
            source_kind="publication_repair_plan",
            source_id=f"{run.id}:publication_repair_plan",
            target_attr="publication_repair_execution_json",
            target_kind="publication_repair_execution",
        )
    if run_assets.paper_revision_action_index_json is not None:
        add_derivation(
            source_kind="paper_revision_action_index",
            source_id=f"{run.id}:paper_revision_action_index",
            target_attr="publication_repair_execution_json",
            target_kind="publication_repair_execution",
        )
    if run_assets.paper_compile_report_json is not None:
        add_derivation(
            source_kind="paper_compile_report",
            source_id=f"{run.id}:paper_compile_report",
            target_attr="publication_readiness_json",
            target_kind="publication_readiness",
        )
    if run_assets.benchmark_json is not None:
        add_derivation(
            source_kind="benchmark",
            source_id=f"{run.id}:benchmark",
            target_attr="publication_readiness_json",
            target_kind="publication_readiness",
        )

    if run_assets.paper_latex_source is not None and run_assets.paper_markdown is not None:
        add_derivation(
            source_kind="paper_latex",
            source_id=f"{run.id}:paper_latex",
            target_attr="paper_markdown",
            target_kind="paper",
        )

    return edges


def _run_lineage_edges(
    *,
    run: AutoResearchRunRead,
    run_assets: AutoResearchRunRegistryFiles,
) -> list[AutoResearchLineageEdgeRead]:
    edges: list[AutoResearchLineageEdgeRead] = []
    selected_candidate_id = run.portfolio.selected_candidate_id if run.portfolio is not None else None
    if run.program is not None:
        edges.append(
            AutoResearchLineageEdgeRead(
                source_kind="run",
                source_id=run.id,
                relation="owns",
                target_kind="program",
                target_id=run.program.id,
                target_path=run_assets.program_json.path if run_assets.program_json is not None else None,
                exists=run_assets.program_json.exists if run_assets.program_json is not None else None,
            )
        )
    if run.portfolio is not None:
        edges.append(
            AutoResearchLineageEdgeRead(
                source_kind="run",
                source_id=run.id,
                relation="owns",
                target_kind="portfolio",
                target_id=f"{run.id}:portfolio",
                target_path=run_assets.portfolio_json.path if run_assets.portfolio_json is not None else None,
                exists=run_assets.portfolio_json.exists if run_assets.portfolio_json is not None else None,
            )
        )

    run_asset_targets = [
        ("plan_json", "plan"),
        ("spec_json", "spec"),
        ("artifact_json", "artifact"),
        ("paper_markdown", "paper"),
        ("narrative_report_markdown", "narrative_report"),
        ("claim_evidence_matrix_json", "claim_evidence_matrix"),
        ("experiment_design_json", "experiment_design"),
        ("failure_analysis_json", "failure_analysis"),
        ("research_replan_json", "research_replan"),
        ("benchmark_card_json", "benchmark_card"),
        ("research_protocol_json", "research_protocol"),
        ("methodology_audit_json", "methodology_audit"),
        ("publication_readiness_json", "publication_readiness"),
        ("contribution_assessment_json", "contribution_assessment"),
        ("literature_graph_json", "literature_graph"),
        ("novelty_validation_json", "novelty_validation"),
        ("revision_dossier_json", "revision_dossier"),
        ("publication_evidence_index_json", "publication_evidence_index"),
        ("artifact_integrity_audit_json", "artifact_integrity_audit"),
        ("publication_repair_plan_json", "publication_repair_plan"),
        ("publication_repair_execution_json", "publication_repair_execution"),
        ("reviewer_simulation_json", "reviewer_simulation"),
        ("experiment_factory_plan_json", "experiment_factory_plan"),
        ("evidence_ledger_json", "evidence_ledger"),
        ("experiment_factory_repair_plan_json", "experiment_factory_repair_plan"),
        ("paper_plan_json", "paper_plan"),
        ("figure_plan_json", "figure_plan"),
        ("paper_revision_history_markdown", "paper_revision_history"),
        ("paper_revision_state_json", "paper_revision_state"),
        ("paper_compile_report_json", "paper_compile_report"),
        ("paper_revision_diff_json", "paper_revision_diff"),
        ("paper_revision_action_index_json", "paper_revision_action_index"),
        ("paper_section_rewrite_index_json", "paper_section_rewrite_index"),
        ("paper_revision_brief_markdown", "paper_revision_brief"),
        ("paper_sources_dir", "paper_sources"),
        ("paper_section_rewrite_packets_dir", "paper_section_rewrite_packets"),
        ("paper_build_script", "paper_build_script"),
        ("paper_checkpoint_index_json", "paper_checkpoint_index"),
        ("paper_latex_source", "paper_latex"),
        ("paper_bibliography_bib", "paper_bibliography"),
        ("paper_sources_manifest_json", "paper_sources_manifest"),
        ("paper_compiled_pdf", "paper_compiled_pdf"),
        ("paper_bibliography_output_bbl", "paper_bibliography_output"),
        ("generated_code", "generated_code"),
        ("benchmark_json", "benchmark"),
    ]
    for attr, target_kind in run_asset_targets:
        ref = getattr(run_assets, attr)
        if ref is None:
            continue
        edges.append(
            AutoResearchLineageEdgeRead(
                source_kind="run",
                source_id=run.id,
                relation="has_asset",
                target_kind=target_kind,
                target_id=f"{run.id}:{target_kind}",
                target_path=ref.path,
                exists=ref.exists,
            )
        )
    edges.extend(_run_derivation_lineage_edges(run=run, run_assets=run_assets))
    for candidate in run.candidates:
        edges.append(
            AutoResearchLineageEdgeRead(
                source_kind="run",
                source_id=run.id,
                relation="selected_candidate" if candidate.id == selected_candidate_id else "owns",
                target_kind="candidate",
                target_id=candidate.id,
            )
        )
    return edges


def _bundle_asset(
    *,
    asset_id: str,
    label: str,
    role: str,
    ref: AutoResearchRegistryAssetRef | None,
    candidate_id: str | None = None,
    selected: bool = False,
    required: bool = True,
) -> AutoResearchBundleAssetRead | None:
    if ref is None:
        return None
    return AutoResearchBundleAssetRead(
        asset_id=asset_id,
        label=label,
        role=role,
        candidate_id=candidate_id,
        selected=selected,
        required=required,
        ref=ref,
    )


def _finalize_bundle(
    *,
    bundle_id: str,
    name: str,
    description: str,
    selected_candidate_id: str | None,
    candidate_ids: list[str],
    assets: list[AutoResearchBundleAssetRead | None],
) -> AutoResearchBundleRead:
    materialized_assets = [item for item in assets if item is not None]
    existing_asset_count = sum(1 for item in materialized_assets if item.ref.exists)
    return AutoResearchBundleRead(
        id=bundle_id,
        name=name,
        description=description,
        selected_candidate_id=selected_candidate_id,
        candidate_ids=candidate_ids,
        asset_count=len(materialized_assets),
        existing_asset_count=existing_asset_count,
        missing_asset_count=len(materialized_assets) - existing_asset_count,
        assets=materialized_assets,
    )


def _registry_view(
    *,
    view_id: str,
    label: str,
    description: str,
    entries: list[AutoResearchCandidateRegistryEntry],
) -> AutoResearchRegistryViewRead:
    return AutoResearchRegistryViewRead(
        id=view_id,
        label=label,
        description=description,
        candidate_ids=[item.candidate_id for item in entries],
        count=len(entries),
        entries=entries,
    )


def _run_bundle_assets(
    *,
    run_registry: AutoResearchRunRegistryRead,
) -> list[AutoResearchBundleAssetRead | None]:
    files = run_registry.files
    return [
        _bundle_asset(asset_id=f"{run_registry.run_id}:run_json", label="Run snapshot", role="run_json", ref=files.run_json),
        _bundle_asset(asset_id=f"{run_registry.run_id}:program_json", label="Program snapshot", role="program_json", ref=files.program_json),
        _bundle_asset(asset_id=f"{run_registry.run_id}:portfolio_json", label="Portfolio snapshot", role="portfolio_json", ref=files.portfolio_json),
        _bundle_asset(asset_id=f"{run_registry.run_id}:benchmark_json", label="Benchmark snapshot", role="benchmark_json", ref=files.benchmark_json, required=False),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_benchmark_card_json",
                label="Selected run benchmark card",
                role="run_benchmark_card_json",
                ref=files.benchmark_card_json,
                required=False,
            )
            if files.benchmark_card_json is not None and files.benchmark_card_json.exists
            else None
        ),
        _bundle_asset(asset_id=f"{run_registry.run_id}:run_plan_json", label="Selected run plan", role="run_plan_json", ref=files.plan_json, required=False),
        _bundle_asset(asset_id=f"{run_registry.run_id}:run_spec_json", label="Selected run spec", role="run_spec_json", ref=files.spec_json, required=False),
        _bundle_asset(asset_id=f"{run_registry.run_id}:run_artifact_json", label="Selected run artifact", role="run_artifact_json", ref=files.artifact_json, required=False),
        _bundle_asset(asset_id=f"{run_registry.run_id}:run_generated_code", label="Selected run generated code", role="run_generated_code", ref=files.generated_code, required=False),
        _bundle_asset(asset_id=f"{run_registry.run_id}:run_paper_markdown", label="Selected run paper", role="run_paper_markdown", ref=files.paper_markdown, required=False),
        _bundle_asset(
            asset_id=f"{run_registry.run_id}:run_narrative_report_markdown",
            label="Selected run narrative report",
            role="run_narrative_report_markdown",
            ref=files.narrative_report_markdown,
            required=False,
        ),
        _bundle_asset(
            asset_id=f"{run_registry.run_id}:run_claim_evidence_matrix_json",
            label="Selected run claim-evidence matrix",
            role="run_claim_evidence_matrix_json",
            ref=files.claim_evidence_matrix_json,
            required=False,
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_research_protocol_json",
                label="Selected run research protocol",
                role="run_research_protocol_json",
                ref=files.research_protocol_json,
                required=False,
            )
            if files.research_protocol_json is not None and files.research_protocol_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_experiment_design_json",
                label="Selected run experiment design",
                role="run_experiment_design_json",
                ref=files.experiment_design_json,
                required=False,
            )
            if files.experiment_design_json is not None and files.experiment_design_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_failure_analysis_json",
                label="Selected run failure analysis",
                role="run_failure_analysis_json",
                ref=files.failure_analysis_json,
                required=False,
            )
            if files.failure_analysis_json is not None and files.failure_analysis_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_research_replan_json",
                label="Selected run research replan",
                role="run_research_replan_json",
                ref=files.research_replan_json,
                required=False,
            )
            if files.research_replan_json is not None and files.research_replan_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_methodology_audit_json",
                label="Selected run methodology audit",
                role="run_methodology_audit_json",
                ref=files.methodology_audit_json,
                required=False,
            )
            if files.methodology_audit_json is not None and files.methodology_audit_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_publication_readiness_json",
                label="Selected run publication readiness report",
                role="run_publication_readiness_json",
                ref=files.publication_readiness_json,
                required=False,
            )
            if files.publication_readiness_json is not None and files.publication_readiness_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_contribution_assessment_json",
                label="Selected run contribution assessment",
                role="run_contribution_assessment_json",
                ref=files.contribution_assessment_json,
                required=False,
            )
            if files.contribution_assessment_json is not None and files.contribution_assessment_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_literature_graph_json",
                label="Selected run literature graph",
                role="run_literature_graph_json",
                ref=files.literature_graph_json,
                required=False,
            )
            if files.literature_graph_json is not None and files.literature_graph_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_novelty_validation_json",
                label="Selected run novelty validation",
                role="run_novelty_validation_json",
                ref=files.novelty_validation_json,
                required=False,
            )
            if files.novelty_validation_json is not None and files.novelty_validation_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_revision_dossier_json",
                label="Selected run revision dossier",
                role="run_revision_dossier_json",
                ref=files.revision_dossier_json,
                required=False,
            )
            if files.revision_dossier_json is not None and files.revision_dossier_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_publication_evidence_index_json",
                label="Selected run publication evidence index",
                role="run_publication_evidence_index_json",
                ref=files.publication_evidence_index_json,
                required=False,
            )
            if files.publication_evidence_index_json is not None
            and files.publication_evidence_index_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_artifact_integrity_audit_json",
                label="Selected run artifact integrity audit",
                role="run_artifact_integrity_audit_json",
                ref=files.artifact_integrity_audit_json,
                required=False,
            )
            if files.artifact_integrity_audit_json is not None
            and files.artifact_integrity_audit_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_publication_repair_plan_json",
                label="Selected run publication repair plan",
                role="run_publication_repair_plan_json",
                ref=files.publication_repair_plan_json,
                required=False,
            )
            if files.publication_repair_plan_json is not None
            and files.publication_repair_plan_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_publication_repair_execution_json",
                label="Selected run publication repair execution",
                role="run_publication_repair_execution_json",
                ref=files.publication_repair_execution_json,
                required=False,
            )
            if files.publication_repair_execution_json is not None
            and files.publication_repair_execution_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_reviewer_simulation_json",
                label="Selected run reviewer simulation",
                role="run_reviewer_simulation_json",
                ref=files.reviewer_simulation_json,
                required=False,
            )
            if files.reviewer_simulation_json is not None
            and files.reviewer_simulation_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_experiment_factory_plan_json",
                label="Selected run experiment factory plan",
                role="run_experiment_factory_plan_json",
                ref=files.experiment_factory_plan_json,
                required=False,
            )
            if files.experiment_factory_plan_json is not None
            and files.experiment_factory_plan_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=(
                    f"{run_registry.run_id}:"
                    "run_experiment_factory_environment_manifest_json"
                ),
                label="Selected run experiment factory environment manifest",
                role="run_experiment_factory_environment_manifest_json",
                ref=files.experiment_factory_environment_manifest_json,
                required=False,
            )
            if files.experiment_factory_environment_manifest_json is not None
            and files.experiment_factory_environment_manifest_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_experiment_factory_materialized_jobs_json",
                label="Selected run experiment factory materialized jobs",
                role="run_experiment_factory_materialized_jobs_json",
                ref=files.experiment_factory_materialized_jobs_json,
                required=False,
            )
            if files.experiment_factory_materialized_jobs_json is not None
            and files.experiment_factory_materialized_jobs_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_experiment_execution_plan_json",
                label="Selected run typed experiment execution plan",
                role="run_experiment_execution_plan_json",
                ref=files.experiment_execution_plan_json,
                required=False,
            )
            if files.experiment_execution_plan_json is not None
            and files.experiment_execution_plan_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_experiment_execution_result_json",
                label="Selected run typed experiment execution result",
                role="run_experiment_execution_result_json",
                ref=files.experiment_execution_result_json,
                required=False,
            )
            if files.experiment_execution_result_json is not None
            and files.experiment_execution_result_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_evidence_ledger_json",
                label="Selected run evidence ledger",
                role="run_evidence_ledger_json",
                ref=files.evidence_ledger_json,
                required=False,
            )
            if files.evidence_ledger_json is not None
            and files.evidence_ledger_json.exists
            else None
        ),
        (
            _bundle_asset(
                asset_id=f"{run_registry.run_id}:run_experiment_factory_repair_plan_json",
                label="Selected run experiment factory repair plan",
                role="run_experiment_factory_repair_plan_json",
                ref=files.experiment_factory_repair_plan_json,
                required=False,
            )
            if files.experiment_factory_repair_plan_json is not None
            and files.experiment_factory_repair_plan_json.exists
            else None
        ),
        _bundle_asset(
            asset_id=f"{run_registry.run_id}:run_paper_plan_json",
            label="Selected run paper plan",
            role="run_paper_plan_json",
            ref=files.paper_plan_json,
            required=False,
        ),
        _bundle_asset(
            asset_id=f"{run_registry.run_id}:run_figure_plan_json",
            label="Selected run figure plan",
            role="run_figure_plan_json",
            ref=files.figure_plan_json,
            required=False,
        ),
        _bundle_asset(
            asset_id=f"{run_registry.run_id}:run_paper_revision_history_markdown",
            label="Selected run paper revision history",
            role="run_paper_revision_history_markdown",
            ref=files.paper_revision_history_markdown,
            required=False,
        ),
        _bundle_asset(
            asset_id=f"{run_registry.run_id}:run_paper_revision_brief_markdown",
            label="Selected run paper revision brief",
            role="run_paper_revision_brief_markdown",
            ref=files.paper_revision_brief_markdown,
            required=False,
        ),
        _bundle_asset(
            asset_id=f"{run_registry.run_id}:run_paper_revision_state_json",
            label="Selected run paper revision state",
            role="run_paper_revision_state_json",
            ref=files.paper_revision_state_json,
            required=False,
        ),
        _bundle_asset(
            asset_id=f"{run_registry.run_id}:run_paper_compile_report_json",
            label="Selected run paper compile report",
            role="run_paper_compile_report_json",
            ref=files.paper_compile_report_json,
            required=False,
        ),
        _bundle_asset(
            asset_id=f"{run_registry.run_id}:run_paper_revision_diff_json",
            label="Selected run paper revision diff",
            role="run_paper_revision_diff_json",
            ref=files.paper_revision_diff_json,
            required=False,
        ),
        _bundle_asset(
            asset_id=f"{run_registry.run_id}:run_paper_revision_action_index_json",
            label="Selected run paper revision action index",
            role="run_paper_revision_action_index_json",
            ref=files.paper_revision_action_index_json,
            required=False,
        ),
        _bundle_asset(
            asset_id=f"{run_registry.run_id}:run_paper_section_rewrite_index_json",
            label="Selected run paper section rewrite index",
            role="run_paper_section_rewrite_index_json",
            ref=files.paper_section_rewrite_index_json,
            required=False,
        ),
        _bundle_asset(
            asset_id=f"{run_registry.run_id}:run_paper_sources_dir",
            label="Selected run paper sources directory",
            role="run_paper_sources_dir",
            ref=files.paper_sources_dir,
            required=False,
        ),
        _bundle_asset(
            asset_id=f"{run_registry.run_id}:run_paper_section_rewrite_packets_dir",
            label="Selected run paper section rewrite packets",
            role="run_paper_section_rewrite_packets_dir",
            ref=files.paper_section_rewrite_packets_dir,
            required=False,
        ),
        _bundle_asset(
            asset_id=f"{run_registry.run_id}:run_paper_build_script",
            label="Selected run paper build script",
            role="run_paper_build_script",
            ref=files.paper_build_script,
            required=False,
        ),
        _bundle_asset(
            asset_id=f"{run_registry.run_id}:run_paper_checkpoint_index_json",
            label="Selected run paper checkpoint index",
            role="run_paper_checkpoint_index_json",
            ref=files.paper_checkpoint_index_json,
            required=False,
        ),
        _bundle_asset(
            asset_id=f"{run_registry.run_id}:run_paper_latex_source",
            label="Selected run paper LaTeX source",
            role="run_paper_latex_source",
            ref=files.paper_latex_source,
            required=False,
        ),
        _bundle_asset(
            asset_id=f"{run_registry.run_id}:run_paper_bibliography_bib",
            label="Selected run paper bibliography",
            role="run_paper_bibliography_bib",
            ref=files.paper_bibliography_bib,
            required=False,
        ),
        _bundle_asset(
            asset_id=f"{run_registry.run_id}:run_paper_sources_manifest_json",
            label="Selected run paper sources manifest",
            role="run_paper_sources_manifest_json",
            ref=files.paper_sources_manifest_json,
            required=False,
        ),
        _bundle_asset(
            asset_id=f"{run_registry.run_id}:run_paper_compiled_pdf",
            label="Selected run compiled paper PDF",
            role="run_paper_compiled_pdf",
            ref=files.paper_compiled_pdf,
            required=False,
        )
        if files.paper_compiled_pdf is not None and files.paper_compiled_pdf.exists
        else None,
        _bundle_asset(
            asset_id=f"{run_registry.run_id}:run_paper_bibliography_output_bbl",
            label="Selected run compiled bibliography output",
            role="run_paper_bibliography_output_bbl",
            ref=files.paper_bibliography_output_bbl,
            required=False,
        )
        if files.paper_bibliography_output_bbl is not None and files.paper_bibliography_output_bbl.exists
        else None,
    ]


def _candidate_bundle_assets(
    *,
    candidate_registry: AutoResearchCandidateRegistryRead,
) -> list[AutoResearchBundleAssetRead | None]:
    candidate = candidate_registry.candidate
    files = candidate_registry.manifest.files
    selected = candidate_registry.selected
    return [
        _bundle_asset(
            asset_id=f"{candidate.id}:workspace",
            label=f"Candidate {candidate.rank} workspace",
            role="workspace",
            ref=files.workspace,
            candidate_id=candidate.id,
            selected=selected,
        ),
        _bundle_asset(
            asset_id=f"{candidate.id}:candidate_json",
            label=f"Candidate {candidate.rank} snapshot",
            role="candidate_json",
            ref=files.candidate_json,
            candidate_id=candidate.id,
            selected=selected,
        ),
        _bundle_asset(
            asset_id=f"{candidate.id}:plan_json",
            label=f"Candidate {candidate.rank} plan",
            role="plan_json",
            ref=files.plan_json,
            candidate_id=candidate.id,
            selected=selected,
        ),
        _bundle_asset(
            asset_id=f"{candidate.id}:spec_json",
            label=f"Candidate {candidate.rank} spec",
            role="spec_json",
            ref=files.spec_json,
            candidate_id=candidate.id,
            selected=selected,
        ),
        _bundle_asset(
            asset_id=f"{candidate.id}:attempts_json",
            label=f"Candidate {candidate.rank} attempts",
            role="attempts_json",
            ref=files.attempts_json,
            candidate_id=candidate.id,
            selected=selected,
            required=False,
        ),
        _bundle_asset(
            asset_id=f"{candidate.id}:artifact_json",
            label=f"Candidate {candidate.rank} artifact",
            role="artifact_json",
            ref=files.artifact_json,
            candidate_id=candidate.id,
            selected=selected,
            required=False,
        ),
        _bundle_asset(
            asset_id=f"{candidate.id}:manifest_json",
            label=f"Candidate {candidate.rank} manifest",
            role="manifest_json",
            ref=files.manifest_json,
            candidate_id=candidate.id,
            selected=selected,
        ),
        _bundle_asset(
            asset_id=f"{candidate.id}:generated_code",
            label=f"Candidate {candidate.rank} generated code",
            role="generated_code",
            ref=files.generated_code,
            candidate_id=candidate.id,
            selected=selected,
            required=False,
        ),
        _bundle_asset(
            asset_id=f"{candidate.id}:paper_markdown",
            label=f"Candidate {candidate.rank} paper",
            role="paper_markdown",
            ref=files.paper_markdown,
            candidate_id=candidate.id,
            selected=selected,
            required=False,
        ),
    ]


def create_run(
    project_id: str,
    topic: str,
    request: AutoResearchRunConfig | None = None,
    docker_image: str | None = None,
    benchmark: BenchmarkSource | None = None,
    execution_backend: ExecutionBackendSpec | None = None,
    brief_id: str | None = None,
    hypothesis_id: str | None = None,
    direction_selection_reason: str | None = None,
) -> AutoResearchRunRead:
    now = _utcnow()
    effective_request = request or AutoResearchRunConfig(
        benchmark=benchmark,
        execution_backend=execution_backend,
        docker_image=docker_image,
    )
    run = AutoResearchRunRead(
        id=f"arun_{uuid4().hex}",
        project_id=project_id,
        topic=topic,
        status="queued",
        brief_id=brief_id,
        hypothesis_id=hypothesis_id,
        direction_selection_reason=direction_selection_reason,
        request=effective_request,
        benchmark=effective_request.benchmark,
        execution_backend=effective_request.execution_backend,
        docker_image=effective_request.docker_image,
        created_at=now,
        updated_at=now,
    )
    save_run(run)
    return run


def save_research_brief(brief: AutoResearchResearchBriefRead) -> AutoResearchResearchBriefRead:
    base = brief_dir(brief.project_id, brief.brief_id)
    path = base / BRIEF_FILENAME
    payload = brief.model_copy(
        update={
            "updated_at": _utcnow(),
            "brief_path": str(path),
        }
    )
    _write_json(path, payload.model_dump(mode="json"))
    return payload


def load_research_brief(project_id: str, brief_id: str) -> AutoResearchResearchBriefRead | None:
    path = _brief_path(project_id, brief_id) / BRIEF_FILENAME
    if not path.exists():
        return None
    try:
        loaded = AutoResearchResearchBriefRead.model_validate_json(path.read_text(encoding="utf-8"))
        return loaded.model_copy(update={"brief_path": str(path)})
    except Exception:
        return None


def list_research_briefs(project_id: str) -> list[AutoResearchResearchBriefRead]:
    items: list[AutoResearchResearchBriefRead] = []
    root = _briefs_dir(project_id)
    for path in sorted(root.glob(f"*/{BRIEF_FILENAME}"), reverse=True):
        try:
            loaded = AutoResearchResearchBriefRead.model_validate_json(path.read_text(encoding="utf-8"))
            items.append(loaded.model_copy(update={"brief_path": str(path)}))
        except Exception:
            continue
    items.sort(key=lambda item: item.updated_at, reverse=True)
    return items


def _refresh_paper_compile_report(
    payload: AutoResearchRunRead,
    *,
    base: Path,
) -> AutoResearchRunRead:
    report = payload.paper_compile_report
    if report is None:
        return payload

    paper_sources_dir = Path(payload.paper_sources_dir) if payload.paper_sources_dir else (base / PAPER_SOURCES_DIRNAME)

    def _input_present(relative_path: str) -> bool:
        if relative_path == report.entrypoint:
            return payload.paper_latex_source is not None or (paper_sources_dir / relative_path).is_file()
        if report.bibliography is not None and relative_path == report.bibliography:
            return payload.paper_bibliography_bib is not None or (paper_sources_dir / relative_path).is_file()
        return (paper_sources_dir / relative_path).exists()

    missing_required_inputs = [
        item
        for item in report.required_inputs
        if not _input_present(item)
    ]
    required_source_files = report.required_source_files or (
        _compile_required_source_files(payload.paper_sources_manifest)
        if payload.paper_sources_manifest is not None
        else []
    )
    missing_required_source_files = [
        item
        for item in required_source_files
        if not _input_present(item)
    ]
    materialized_outputs = [
        item
        for item in report.expected_outputs
        if (paper_sources_dir / item).exists()
    ]
    source_package_complete = not missing_required_source_files
    all_expected_outputs_materialized = (
        not report.expected_outputs
        or len(materialized_outputs) == len(report.expected_outputs)
    )
    ready_for_compile = not missing_required_inputs and source_package_complete
    compile_report = report.model_copy(
        update={
            "generated_at": _utcnow(),
            "missing_required_inputs": missing_required_inputs,
            "required_source_files": required_source_files,
            "missing_required_source_files": missing_required_source_files,
            "materialized_outputs": materialized_outputs,
            "source_package_complete": source_package_complete,
            "all_expected_outputs_materialized": all_expected_outputs_materialized,
            "ready_for_compile": ready_for_compile,
        }
    )
    compile_report = compile_paper_evidence(
        compile_report,
        run=payload,
        paper_markdown=payload.paper_markdown,
        paper_plan=payload.paper_plan,
        claim_evidence_matrix=payload.claim_evidence_matrix,
        artifact=payload.artifact,
        literature_count=len(payload.literature),
    )
    if (
        compile_report.model_dump(mode="json") == report.model_dump(mode="json")
        and report.missing_required_inputs == missing_required_inputs
        and report.required_source_files == required_source_files
        and report.missing_required_source_files == missing_required_source_files
        and report.materialized_outputs == materialized_outputs
        and report.source_package_complete == source_package_complete
        and report.all_expected_outputs_materialized == all_expected_outputs_materialized
        and report.ready_for_compile == ready_for_compile
    ):
        return payload
    return payload.model_copy(update={"paper_compile_report": compile_report})


def _load_reviewer_simulation(payload: AutoResearchRunRead, *, base: Path) -> AutoResearchRunRead:
    if payload.reviewer_simulation is not None:
        return payload
    path = base / REVIEWER_SIMULATION_FILENAME
    if not path.is_file():
        return payload
    try:
        simulation = AutoResearchReviewerSimulationRead.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return payload
    return payload.model_copy(
        update={
            "reviewer_simulation": simulation,
            "reviewer_simulation_path": str(path),
        }
    )


def _load_experiment_factory_artifacts(payload: AutoResearchRunRead, *, base: Path) -> AutoResearchRunRead:
    updates: dict[str, object] = {}
    if payload.experiment_factory_plan is None:
        path = base / EXPERIMENT_FACTORY_PLAN_FILENAME
        if path.is_file():
            try:
                updates["experiment_factory_plan"] = AutoResearchExperimentFactoryPlanRead.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
                updates["experiment_factory_plan_path"] = str(path)
            except Exception:
                pass
    if payload.experiment_factory_environment_manifest is None:
        path = base / EXPERIMENT_FACTORY_ENVIRONMENT_MANIFEST_FILENAME
        if path.is_file():
            try:
                updates["experiment_factory_environment_manifest"] = (
                    AutoResearchExperimentFactoryEnvironmentManifestRead.model_validate_json(
                        path.read_text(encoding="utf-8")
                    )
                )
                updates["experiment_factory_environment_manifest_path"] = str(path)
            except Exception:
                pass
    if not payload.experiment_factory_materialized_jobs:
        path = base / EXPERIMENT_FACTORY_MATERIALIZED_JOBS_FILENAME
        if path.is_file():
            try:
                raw_jobs = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw_jobs, list):
                    updates["experiment_factory_materialized_jobs"] = [
                        AutoResearchExperimentFactoryMaterializedJobRead.model_validate(item)
                        for item in raw_jobs
                    ]
                    updates["experiment_factory_materialized_jobs_path"] = str(path)
            except Exception:
                pass
    if payload.experiment_execution_plan is None:
        path = base / EXPERIMENT_EXECUTION_PLAN_FILENAME
        if path.is_file():
            try:
                updates["experiment_execution_plan"] = AutoResearchExperimentExecutionPlanRead.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
                updates["experiment_execution_plan_path"] = str(path)
            except Exception:
                pass
    if payload.experiment_execution_result is None:
        path = base / EXPERIMENT_EXECUTION_RESULT_FILENAME
        if path.is_file():
            try:
                updates["experiment_execution_result"] = AutoResearchExperimentExecutionResultRead.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
                updates["experiment_execution_result_path"] = str(path)
            except Exception:
                pass
    if payload.evidence_ledger is None:
        path = base / EVIDENCE_LEDGER_FILENAME
        if path.is_file():
            try:
                updates["evidence_ledger"] = AutoResearchEvidenceLedgerRead.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
                updates["evidence_ledger_path"] = str(path)
            except Exception:
                pass
    if payload.experiment_factory_repair_plan is None:
        path = base / EXPERIMENT_FACTORY_REPAIR_PLAN_FILENAME
        if path.is_file():
            try:
                updates["experiment_factory_repair_plan"] = (
                    AutoResearchExperimentFactoryRepairPlanRead.model_validate_json(
                        path.read_text(encoding="utf-8")
                    )
                )
                updates["experiment_factory_repair_plan_path"] = str(path)
            except Exception:
                pass
    return payload.model_copy(update=updates) if updates else payload


def _hydrate_run(payload: AutoResearchRunRead) -> AutoResearchRunRead:
    base = run_dir(payload.project_id, payload.id)
    hydrated = _refresh_paper_section_rewrite_index(payload)
    hydrated = _refresh_paper_revision_diff(hydrated, base=base)
    hydrated = _refresh_paper_revision_action_index(hydrated, base=base)
    hydrated = _refresh_paper_compile_report(hydrated, base=base)
    hydrated = _load_reviewer_simulation(hydrated, base=base)
    hydrated = _load_experiment_factory_artifacts(hydrated, base=base)
    return hydrated


def _refresh_paper_section_rewrite_index(payload: AutoResearchRunRead) -> AutoResearchRunRead:
    if (
        payload.paper_plan is None
        or payload.claim_evidence_matrix is None
        or payload.paper_revision_state is None
        or payload.paper_markdown is None
    ):
        return payload
    index = PaperWriter().build_section_rewrite_packet_index(
        paper_plan=payload.paper_plan,
        claim_evidence_matrix=payload.claim_evidence_matrix,
        paper_revision_state=payload.paper_revision_state,
        paper_markdown=payload.paper_markdown,
    )
    if (
        payload.paper_section_rewrite_index is not None
        and _model_dump_without_generated_at(payload.paper_section_rewrite_index)
        == _model_dump_without_generated_at(index)
    ):
        return payload
    return payload.model_copy(update={"paper_section_rewrite_index": index})


def _refresh_paper_revision_diff(
    payload: AutoResearchRunRead,
    *,
    base: Path,
) -> AutoResearchRunRead:
    if (
        payload.paper_plan is None
        or payload.paper_revision_state is None
        or payload.paper_section_rewrite_index is None
        or payload.paper_markdown is None
    ):
        return payload
    (
        base_revision_round,
        previous_paper_markdown,
        previous_section_rewrite_index,
    ) = _load_previous_revision_checkpoint_snapshot(payload, base=base)
    diff = PaperWriter().build_paper_revision_diff(
        paper_plan=payload.paper_plan,
        paper_revision_state=payload.paper_revision_state,
        paper_section_rewrite_index=payload.paper_section_rewrite_index,
        paper_markdown=payload.paper_markdown,
        previous_paper_markdown=previous_paper_markdown,
        previous_section_rewrite_index=previous_section_rewrite_index,
        base_revision_round=base_revision_round,
    )
    if (
        payload.paper_revision_diff is not None
        and _model_dump_without_generated_at(payload.paper_revision_diff)
        == _model_dump_without_generated_at(diff)
    ):
        return payload
    return payload.model_copy(update={"paper_revision_diff": diff})


def _refresh_paper_revision_action_index(
    payload: AutoResearchRunRead,
    *,
    base: Path,
) -> AutoResearchRunRead:
    if (
        payload.paper_revision_state is None
        or payload.paper_section_rewrite_index is None
        or payload.paper_revision_diff is None
        or payload.paper_markdown is None
    ):
        return payload
    review_loop = _load_review_loop_snapshot(base)
    index = PaperWriter().build_paper_revision_action_index(
        paper_revision_state=payload.paper_revision_state,
        paper_section_rewrite_index=payload.paper_section_rewrite_index,
        paper_revision_diff=payload.paper_revision_diff,
        paper_markdown=payload.paper_markdown,
        paper_plan=payload.paper_plan,
        review_loop=review_loop,
    )
    if (
        payload.paper_revision_action_index is not None
        and _model_dump_without_generated_at(payload.paper_revision_action_index)
        == _model_dump_without_generated_at(index)
    ):
        return payload
    return payload.model_copy(update={"paper_revision_action_index": index})


def save_run(
    run: AutoResearchRunRead,
    *,
    touch_updated_at: bool = True,
    materialize_paper_workspace: bool = True,
) -> AutoResearchRunRead:
    payload = run.model_copy(update={"updated_at": _utcnow()}) if touch_updated_at else run.model_copy()
    payload = _hydrate_run(payload)
    base = run_dir(payload.project_id, payload.id)
    _write_json(base / RUN_FILENAME, payload.model_dump(mode="json"))
    if payload.program is not None:
        _write_json(base / PROGRAM_FILENAME, payload.program.model_dump(mode="json"))
    if payload.plan is not None:
        _write_json(base / PLAN_FILENAME, payload.plan.model_dump(mode="json"))
    if payload.spec is not None:
        _write_json(base / SPEC_FILENAME, payload.spec.model_dump(mode="json"))
    if payload.portfolio is not None:
        _write_json(base / PORTFOLIO_FILENAME, payload.portfolio.model_dump(mode="json"))
    if payload.candidates:
        candidate_dir = base / CANDIDATES_DIRNAME
        candidate_dir.mkdir(parents=True, exist_ok=True)
        for candidate in payload.candidates:
            _write_json(candidate_dir / f"{candidate.id}.json", candidate.model_dump(mode="json"))
    if payload.artifact is not None:
        _write_json(base / ARTIFACT_FILENAME, payload.artifact.model_dump(mode="json"))
    if payload.project_context is not None:
        _write_json(base / PROJECT_CONTEXT_FILENAME, payload.project_context.model_dump(mode="json"))
    if payload.paper_markdown and materialize_paper_workspace:
        (base / PAPER_FILENAME).write_text(payload.paper_markdown, encoding="utf-8")
    if payload.narrative_report_markdown:
        (base / NARRATIVE_REPORT_FILENAME).write_text(payload.narrative_report_markdown, encoding="utf-8")
    if payload.claim_evidence_matrix is not None:
        _write_json(base / CLAIM_EVIDENCE_MATRIX_FILENAME, payload.claim_evidence_matrix.model_dump(mode="json"))
    if payload.paper_plan is not None:
        _write_json(base / PAPER_PLAN_FILENAME, payload.paper_plan.model_dump(mode="json"))
    if payload.figure_plan is not None:
        _write_json(base / FIGURE_PLAN_FILENAME, payload.figure_plan.model_dump(mode="json"))
    if payload.experiment_factory_plan is not None:
        _write_json(
            base / EXPERIMENT_FACTORY_PLAN_FILENAME,
            payload.experiment_factory_plan.model_dump(mode="json"),
        )
    if payload.experiment_factory_environment_manifest is not None:
        _write_json(
            base / EXPERIMENT_FACTORY_ENVIRONMENT_MANIFEST_FILENAME,
            payload.experiment_factory_environment_manifest.model_dump(mode="json"),
        )
    if payload.experiment_factory_materialized_jobs:
        _write_json(
            base / EXPERIMENT_FACTORY_MATERIALIZED_JOBS_FILENAME,
            [item.model_dump(mode="json") for item in payload.experiment_factory_materialized_jobs],
        )
    if payload.experiment_execution_plan is not None:
        _write_json(
            base / EXPERIMENT_EXECUTION_PLAN_FILENAME,
            payload.experiment_execution_plan.model_dump(mode="json"),
        )
    if payload.experiment_execution_result is not None:
        _write_json(
            base / EXPERIMENT_EXECUTION_RESULT_FILENAME,
            payload.experiment_execution_result.model_dump(mode="json"),
        )
    if payload.evidence_ledger is not None:
        _write_json(base / EVIDENCE_LEDGER_FILENAME, payload.evidence_ledger.model_dump(mode="json"))
    if payload.experiment_factory_repair_plan is not None:
        _write_json(
            base / EXPERIMENT_FACTORY_REPAIR_PLAN_FILENAME,
            payload.experiment_factory_repair_plan.model_dump(mode="json"),
        )
    if payload.paper_revision_state is not None:
        _write_json(base / PAPER_REVISION_STATE_FILENAME, payload.paper_revision_state.model_dump(mode="json"))
    if payload.paper_compile_report is not None and materialize_paper_workspace:
        _write_json(base / PAPER_COMPILE_REPORT_FILENAME, payload.paper_compile_report.model_dump(mode="json"))
    if payload.paper_revision_diff is not None:
        _write_json(base / PAPER_REVISION_DIFF_FILENAME, payload.paper_revision_diff.model_dump(mode="json"))
    if payload.paper_revision_action_index is not None:
        _write_json(
            base / PAPER_REVISION_ACTION_INDEX_FILENAME,
            payload.paper_revision_action_index.model_dump(mode="json"),
        )
    if payload.reviewer_simulation is not None:
        _write_json(
            base / REVIEWER_SIMULATION_FILENAME,
            payload.reviewer_simulation.model_dump(mode="json"),
        )
    if payload.paper_section_rewrite_index is not None:
        _write_json(
            base / PAPER_SECTION_REWRITE_INDEX_FILENAME,
            payload.paper_section_rewrite_index.model_dump(mode="json"),
        )
    path_updates: dict[str, str] = {}
    if payload.experiment_factory_plan is not None:
        path_updates["experiment_factory_plan_path"] = str(base / EXPERIMENT_FACTORY_PLAN_FILENAME)
    if payload.experiment_factory_environment_manifest is not None:
        path_updates["experiment_factory_environment_manifest_path"] = str(
            base / EXPERIMENT_FACTORY_ENVIRONMENT_MANIFEST_FILENAME
        )
    if payload.experiment_factory_materialized_jobs:
        path_updates["experiment_factory_materialized_jobs_path"] = str(
            base / EXPERIMENT_FACTORY_MATERIALIZED_JOBS_FILENAME
        )
    if payload.experiment_execution_plan is not None:
        path_updates["experiment_execution_plan_path"] = str(
            base / EXPERIMENT_EXECUTION_PLAN_FILENAME
        )
    if payload.experiment_execution_result is not None:
        path_updates["experiment_execution_result_path"] = str(
            base / EXPERIMENT_EXECUTION_RESULT_FILENAME
        )
    if payload.evidence_ledger is not None:
        path_updates["evidence_ledger_path"] = str(base / EVIDENCE_LEDGER_FILENAME)
    if payload.experiment_factory_repair_plan is not None:
        path_updates["experiment_factory_repair_plan_path"] = str(
            base / EXPERIMENT_FACTORY_REPAIR_PLAN_FILENAME
        )
    if path_updates:
        payload = payload.model_copy(update=path_updates)
        _write_json(base / RUN_FILENAME, payload.model_dump(mode="json"))
    if (
        (payload.paper_markdown is not None and materialize_paper_workspace)
        or (payload.paper_compile_report is not None and materialize_paper_workspace)
        or payload.paper_revision_diff is not None
        or payload.paper_revision_action_index is not None
        or payload.paper_section_rewrite_index is not None
        or (payload.paper_latex_source is not None and materialize_paper_workspace)
        or (payload.paper_bibliography_bib is not None and materialize_paper_workspace)
        or (payload.paper_sources_manifest is not None and materialize_paper_workspace)
    ):
        paper_sources_dir = base / PAPER_SOURCES_DIRNAME
        paper_sources_dir.mkdir(parents=True, exist_ok=True)
        revision_history = _paper_revision_history(payload)
        revision_diff_note = _paper_revision_diff_note(payload)
        revision_action_note = _paper_revision_action_note(payload)
        revision_brief = _paper_revision_brief(payload)
        paper_build_script = _paper_build_script(payload)
        section_rewrite_index, section_rewrite_packets = _paper_section_rewrite_packets(payload)
        if payload.paper_markdown is not None and materialize_paper_workspace:
            (paper_sources_dir / PAPER_FILENAME).write_text(payload.paper_markdown, encoding="utf-8")
        if payload.narrative_report_markdown:
            (paper_sources_dir / NARRATIVE_REPORT_FILENAME).write_text(
                payload.narrative_report_markdown,
                encoding="utf-8",
            )
        if payload.claim_evidence_matrix is not None:
            _write_json(
                paper_sources_dir / CLAIM_EVIDENCE_MATRIX_FILENAME,
                payload.claim_evidence_matrix.model_dump(mode="json"),
            )
        if payload.paper_plan is not None:
            _write_json(
                paper_sources_dir / PAPER_PLAN_FILENAME,
                payload.paper_plan.model_dump(mode="json"),
            )
        if payload.figure_plan is not None:
            _write_json(
                paper_sources_dir / FIGURE_PLAN_FILENAME,
                payload.figure_plan.model_dump(mode="json"),
            )
        if revision_history is not None:
            (paper_sources_dir / PAPER_REVISION_HISTORY_FILENAME).write_text(revision_history, encoding="utf-8")
        if revision_brief is not None:
            (paper_sources_dir / PAPER_REVISION_BRIEF_FILENAME).write_text(revision_brief, encoding="utf-8")
        if payload.paper_revision_state is not None:
            _write_json(
                paper_sources_dir / PAPER_REVISION_STATE_FILENAME,
                payload.paper_revision_state.model_dump(mode="json"),
            )
        if payload.paper_compile_report is not None and materialize_paper_workspace:
            _write_json(
                paper_sources_dir / PAPER_COMPILE_REPORT_FILENAME,
                payload.paper_compile_report.model_dump(mode="json"),
            )
        if payload.paper_revision_diff is not None:
            _write_json(
                paper_sources_dir / PAPER_REVISION_DIFF_FILENAME,
                payload.paper_revision_diff.model_dump(mode="json"),
            )
        if revision_diff_note is not None:
            (paper_sources_dir / PAPER_REVISION_DIFF_NOTE_FILENAME).write_text(revision_diff_note, encoding="utf-8")
        if payload.paper_revision_action_index is not None:
            _write_json(
                paper_sources_dir / PAPER_REVISION_ACTION_INDEX_FILENAME,
                payload.paper_revision_action_index.model_dump(mode="json"),
            )
        if revision_action_note is not None:
            (paper_sources_dir / PAPER_REVISION_ACTION_NOTE_FILENAME).write_text(revision_action_note, encoding="utf-8")
        if section_rewrite_index is not None:
            rewrite_packets_dir = paper_sources_dir / PAPER_REWRITE_PACKETS_DIRNAME
            rewrite_packets_dir.mkdir(parents=True, exist_ok=True)
            _write_json(
                rewrite_packets_dir / PAPER_REWRITE_PACKET_INDEX_FILENAME,
                section_rewrite_index.model_dump(mode="json"),
            )
            for relative_path, content in section_rewrite_packets.items():
                packet_path = paper_sources_dir / relative_path
                packet_path.parent.mkdir(parents=True, exist_ok=True)
                packet_path.write_text(content, encoding="utf-8")
        if paper_build_script is not None and materialize_paper_workspace:
            build_script_path = paper_sources_dir / PAPER_BUILD_SCRIPT_FILENAME
            build_script_path.write_text(paper_build_script, encoding="utf-8")
            build_script_path.chmod(0o755)
        if payload.paper_latex_source is not None and materialize_paper_workspace:
            (paper_sources_dir / PAPER_LATEX_FILENAME).write_text(payload.paper_latex_source, encoding="utf-8")
        if payload.paper_bibliography_bib is not None and materialize_paper_workspace:
            (paper_sources_dir / PAPER_BIB_FILENAME).write_text(payload.paper_bibliography_bib, encoding="utf-8")
        if payload.paper_sources_manifest is not None and materialize_paper_workspace:
            _write_json(
                paper_sources_dir / PAPER_SOURCES_MANIFEST_FILENAME,
                payload.paper_sources_manifest.model_dump(mode="json"),
            )
        _write_paper_revision_checkpoints(
            payload,
            base=base,
            paper_sources_dir=paper_sources_dir,
            revision_brief=revision_brief,
            revision_diff_note=revision_diff_note,
            revision_action_note=revision_action_note,
            revision_history=revision_history,
            paper_build_script=paper_build_script,
        )
    if payload.paper_compile_report is not None and materialize_paper_workspace:
        payload = _refresh_paper_compile_report(payload, base=base)
        _write_json(base / RUN_FILENAME, payload.model_dump(mode="json"))
        _write_json(base / PAPER_COMPILE_REPORT_FILENAME, payload.paper_compile_report.model_dump(mode="json"))
        paper_sources_dir = base / PAPER_SOURCES_DIRNAME
        if paper_sources_dir.is_dir():
            _write_json(
                paper_sources_dir / PAPER_COMPILE_REPORT_FILENAME,
                payload.paper_compile_report.model_dump(mode="json"),
            )
    return payload


def load_run(project_id: str, run_id: str) -> AutoResearchRunRead | None:
    path = _run_path(project_id, run_id) / RUN_FILENAME
    if not path.exists():
        return None
    try:
        return _hydrate_run(AutoResearchRunRead.model_validate_json(path.read_text(encoding="utf-8")))
    except Exception:
        return None


def list_runs(project_id: str) -> list[AutoResearchRunRead]:
    items: list[AutoResearchRunRead] = []
    root = _runs_dir(project_id)
    for path in sorted(root.glob("*/run.json"), reverse=True):
        try:
            items.append(_hydrate_run(AutoResearchRunRead.model_validate_json(path.read_text(encoding="utf-8"))))
        except Exception:
            continue
    items.sort(key=lambda item: item.updated_at, reverse=True)
    return items


def save_generated_code(
    project_id: str,
    run_id: str,
    code: str,
    filename: str | None = None,
    subdir: str | None = None,
) -> str:
    base = run_dir(project_id, run_id)
    if subdir:
        base = base / subdir
        base.mkdir(parents=True, exist_ok=True)
    path = base / (filename or CODE_FILENAME)
    path.write_text(code, encoding="utf-8")
    return str(path)


def paper_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PAPER_FILENAME)


def project_context_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PROJECT_CONTEXT_FILENAME)


def narrative_report_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / NARRATIVE_REPORT_FILENAME)


def claim_evidence_matrix_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / CLAIM_EVIDENCE_MATRIX_FILENAME)


def research_protocol_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / RESEARCH_PROTOCOL_FILENAME)


def methodology_audit_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / METHODOLOGY_AUDIT_FILENAME)


def publication_readiness_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PUBLICATION_READINESS_FILENAME)


def contribution_assessment_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / CONTRIBUTION_ASSESSMENT_FILENAME)


def experiment_design_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / EXPERIMENT_DESIGN_FILENAME)


def failure_analysis_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / FAILURE_ANALYSIS_FILENAME)


def research_replan_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / RESEARCH_REPLAN_FILENAME)


def literature_graph_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / LITERATURE_GRAPH_FILENAME)


def novelty_validation_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / NOVELTY_VALIDATION_FILENAME)


def revision_dossier_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / REVISION_DOSSIER_FILENAME)


def publication_evidence_index_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PUBLICATION_EVIDENCE_INDEX_FILENAME)


def artifact_integrity_audit_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / ARTIFACT_INTEGRITY_AUDIT_FILENAME)


def publication_repair_plan_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PUBLICATION_REPAIR_PLAN_FILENAME)


def publication_repair_execution_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PUBLICATION_REPAIR_EXECUTION_FILENAME)


def reviewer_simulation_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / REVIEWER_SIMULATION_FILENAME)


def paper_plan_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PAPER_PLAN_FILENAME)


def figure_plan_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / FIGURE_PLAN_FILENAME)


def paper_revision_state_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PAPER_REVISION_STATE_FILENAME)


def paper_compile_report_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PAPER_COMPILE_REPORT_FILENAME)


def paper_revision_diff_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PAPER_REVISION_DIFF_FILENAME)


def paper_revision_action_index_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PAPER_REVISION_ACTION_INDEX_FILENAME)


def paper_section_rewrite_index_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PAPER_SECTION_REWRITE_INDEX_FILENAME)


def paper_sources_dir_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PAPER_SOURCES_DIRNAME)


def paper_section_rewrite_packets_dir_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PAPER_SOURCES_DIRNAME / PAPER_REWRITE_PACKETS_DIRNAME)


def paper_latex_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PAPER_SOURCES_DIRNAME / PAPER_LATEX_FILENAME)


def paper_bibliography_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PAPER_SOURCES_DIRNAME / PAPER_BIB_FILENAME)


def paper_sources_manifest_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PAPER_SOURCES_DIRNAME / PAPER_SOURCES_MANIFEST_FILENAME)


def benchmark_card_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / BENCHMARK_CARD_FILENAME)


def candidate_paper_file_path(project_id: str, run_id: str, candidate_id: str) -> str:
    return str(candidate_dir(project_id, run_id, candidate_id) / PAPER_FILENAME)


def save_benchmark_snapshot(project_id: str, run_id: str, payload: dict) -> str:
    path = run_dir(project_id, run_id) / BENCHMARK_FILENAME
    _write_json(path, payload)
    return str(path)


def load_benchmark_snapshot(project_id: str, run_id: str) -> dict | None:
    payload = _read_json(_run_path(project_id, run_id) / BENCHMARK_FILENAME)
    return payload if isinstance(payload, dict) else None


def load_candidate_manifest(
    project_id: str,
    run_id: str,
    candidate: HypothesisCandidate,
    *,
    decision: PortfolioDecisionRecord | None = None,
) -> AutoResearchCandidateManifestRead:
    base = _candidate_path(project_id, run_id, candidate.id)
    manifest_path = base / MANIFEST_FILENAME
    payload = _read_json(manifest_path)
    if not isinstance(payload, dict):
        return _fallback_candidate_manifest(
            project_id=project_id,
            run_id=run_id,
            candidate=candidate,
            decision=decision,
        )

    candidate_payload = payload.get("candidate")
    files_payload = payload.get("files")
    decision_payload = payload.get("decision")
    try:
        manifest_candidate = AutoResearchCandidateManifestCandidate.model_validate(candidate_payload)
        manifest_decision = (
            PortfolioDecisionRecord.model_validate(decision_payload)
            if isinstance(decision_payload, dict)
            else decision
        )
        return AutoResearchCandidateManifestRead(
            manifest_source="file",
            candidate=manifest_candidate,
            decision=manifest_decision,
            files=_candidate_registry_files(
                base=base,
                manifest_path=manifest_path,
                candidate=candidate,
                manifest_files=files_payload if isinstance(files_payload, dict) else None,
            ),
        )
    except Exception:
        return _fallback_candidate_manifest(
            project_id=project_id,
            run_id=run_id,
            candidate=candidate,
            decision=decision,
        )


def load_candidate_registry(
    project_id: str,
    run_id: str,
    candidate_id: str,
    *,
    run: AutoResearchRunRead | None = None,
) -> AutoResearchCandidateRegistryRead | None:
    current_run = run or load_run(project_id, run_id)
    if current_run is None:
        return None
    candidate = next((item for item in current_run.candidates if item.id == candidate_id), None)
    if candidate is None:
        return None
    selected_candidate_id = current_run.portfolio.selected_candidate_id if current_run.portfolio else None
    decisions = current_run.portfolio.decisions if current_run.portfolio else []
    decision = next((item for item in decisions if item.candidate_id == candidate_id), None)
    base = _candidate_path(project_id, run_id, candidate_id)
    run_assets = None
    if candidate_id == selected_candidate_id:
        run_base = _run_path(project_id, run_id)
        run_paper_path = current_run.paper_path or (run_base / PAPER_FILENAME)
        run_assets = AutoResearchRunRegistryFiles(
            root=_asset_ref(run_base, kind="directory")
            or AutoResearchRegistryAssetRef(path=str(run_base), kind="directory", exists=False),
            run_json=_asset_ref(run_base / RUN_FILENAME)
            or AutoResearchRegistryAssetRef(path=str(run_base / RUN_FILENAME), exists=False),
            program_json=_asset_ref(run_base / PROGRAM_FILENAME),
            plan_json=_asset_ref(run_base / PLAN_FILENAME),
            spec_json=_asset_ref(run_base / SPEC_FILENAME),
            portfolio_json=_asset_ref(run_base / PORTFOLIO_FILENAME),
            artifact_json=_asset_ref(run_base / ARTIFACT_FILENAME),
            benchmark_json=_asset_ref(run_base / BENCHMARK_FILENAME),
            benchmark_card_json=_asset_ref(run_base / BENCHMARK_CARD_FILENAME),
            generated_code=_asset_ref(current_run.generated_code_path),
            paper_markdown=_asset_ref(run_paper_path),
            narrative_report_markdown=_asset_ref(
                current_run.narrative_report_path or (run_base / NARRATIVE_REPORT_FILENAME)
            ),
            claim_evidence_matrix_json=_asset_ref(
                current_run.claim_evidence_matrix_path or (run_base / CLAIM_EVIDENCE_MATRIX_FILENAME)
            ),
            experiment_design_json=_asset_ref(run_base / EXPERIMENT_DESIGN_FILENAME),
            failure_analysis_json=_asset_ref(run_base / FAILURE_ANALYSIS_FILENAME),
            research_replan_json=_asset_ref(run_base / RESEARCH_REPLAN_FILENAME),
            research_protocol_json=_asset_ref(run_base / RESEARCH_PROTOCOL_FILENAME),
            methodology_audit_json=_asset_ref(run_base / METHODOLOGY_AUDIT_FILENAME),
            publication_readiness_json=_asset_ref(run_base / PUBLICATION_READINESS_FILENAME),
            contribution_assessment_json=_asset_ref(run_base / CONTRIBUTION_ASSESSMENT_FILENAME),
            literature_graph_json=_asset_ref(run_base / LITERATURE_GRAPH_FILENAME),
            novelty_validation_json=_asset_ref(run_base / NOVELTY_VALIDATION_FILENAME),
            revision_dossier_json=_asset_ref(run_base / REVISION_DOSSIER_FILENAME),
            publication_evidence_index_json=_asset_ref(run_base / PUBLICATION_EVIDENCE_INDEX_FILENAME),
            artifact_integrity_audit_json=_asset_ref(run_base / ARTIFACT_INTEGRITY_AUDIT_FILENAME),
            publication_repair_plan_json=_asset_ref(run_base / PUBLICATION_REPAIR_PLAN_FILENAME),
            publication_repair_execution_json=_asset_ref(run_base / PUBLICATION_REPAIR_EXECUTION_FILENAME),
            reviewer_simulation_json=_asset_ref(
                current_run.reviewer_simulation_path or (run_base / REVIEWER_SIMULATION_FILENAME)
            ),
        experiment_factory_plan_json=_asset_ref(
            current_run.experiment_factory_plan_path or (run_base / EXPERIMENT_FACTORY_PLAN_FILENAME)
        ),
        experiment_factory_environment_manifest_json=_asset_ref(
            current_run.experiment_factory_environment_manifest_path
            or (run_base / EXPERIMENT_FACTORY_ENVIRONMENT_MANIFEST_FILENAME)
        ),
        experiment_factory_materialized_jobs_json=_asset_ref(
            current_run.experiment_factory_materialized_jobs_path
            or (run_base / EXPERIMENT_FACTORY_MATERIALIZED_JOBS_FILENAME)
        ),
        experiment_execution_plan_json=_asset_ref(
            current_run.experiment_execution_plan_path
            or (run_base / EXPERIMENT_EXECUTION_PLAN_FILENAME)
        ),
        experiment_execution_result_json=_asset_ref(
            current_run.experiment_execution_result_path
            or (run_base / EXPERIMENT_EXECUTION_RESULT_FILENAME)
        ),
        evidence_ledger_json=_asset_ref(
            current_run.evidence_ledger_path or (run_base / EVIDENCE_LEDGER_FILENAME)
        ),
            experiment_factory_repair_plan_json=_asset_ref(
                current_run.experiment_factory_repair_plan_path
                or (run_base / EXPERIMENT_FACTORY_REPAIR_PLAN_FILENAME)
            ),
            paper_plan_json=_asset_ref(
                current_run.paper_plan_path or (run_base / PAPER_PLAN_FILENAME)
            ),
            figure_plan_json=_asset_ref(
                current_run.figure_plan_path or (run_base / FIGURE_PLAN_FILENAME)
            ),
            paper_revision_history_markdown=_asset_ref(
                run_base / PAPER_SOURCES_DIRNAME / PAPER_REVISION_HISTORY_FILENAME
            ),
            paper_revision_state_json=_asset_ref(
                current_run.paper_revision_state_path or (run_base / PAPER_REVISION_STATE_FILENAME)
            ),
            paper_compile_report_json=_asset_ref(
                current_run.paper_compile_report_path or (run_base / PAPER_COMPILE_REPORT_FILENAME)
            ),
            paper_revision_diff_json=_asset_ref(
                current_run.paper_revision_diff_path or (run_base / PAPER_REVISION_DIFF_FILENAME)
            ),
            paper_revision_action_index_json=_asset_ref(
                current_run.paper_revision_action_index_path or (run_base / PAPER_REVISION_ACTION_INDEX_FILENAME)
            ),
            paper_section_rewrite_index_json=_asset_ref(
                current_run.paper_section_rewrite_index_path or (run_base / PAPER_SECTION_REWRITE_INDEX_FILENAME)
            ),
            paper_revision_brief_markdown=_asset_ref(
                run_base / PAPER_SOURCES_DIRNAME / PAPER_REVISION_BRIEF_FILENAME
            ),
            paper_sources_dir=_asset_ref(
                current_run.paper_sources_dir or (run_base / PAPER_SOURCES_DIRNAME),
                kind="directory",
            ),
            paper_section_rewrite_packets_dir=_asset_ref(
                current_run.paper_section_rewrite_packets_dir
                or (run_base / PAPER_SOURCES_DIRNAME / PAPER_REWRITE_PACKETS_DIRNAME),
                kind="directory",
            ),
            paper_build_script=_asset_ref(
                run_base / PAPER_SOURCES_DIRNAME / PAPER_BUILD_SCRIPT_FILENAME
            ),
            paper_checkpoint_index_json=_asset_ref(
                run_base / PAPER_SOURCES_DIRNAME / PAPER_CHECKPOINTS_DIRNAME / PAPER_CHECKPOINT_INDEX_FILENAME
            ),
            paper_latex_source=_asset_ref(
                current_run.paper_latex_path or (run_base / PAPER_SOURCES_DIRNAME / PAPER_LATEX_FILENAME)
            ),
            paper_bibliography_bib=_asset_ref(
                current_run.paper_bibliography_path or (run_base / PAPER_SOURCES_DIRNAME / PAPER_BIB_FILENAME)
            ),
            paper_sources_manifest_json=_asset_ref(
                current_run.paper_sources_manifest_path
                or (run_base / PAPER_SOURCES_DIRNAME / PAPER_SOURCES_MANIFEST_FILENAME)
            ),
            paper_compiled_pdf=_asset_ref(
                run_base / PAPER_SOURCES_DIRNAME / PAPER_COMPILED_PDF_FILENAME
            ),
            paper_bibliography_output_bbl=_asset_ref(
                run_base / PAPER_SOURCES_DIRNAME / PAPER_BIBLIOGRAPHY_OUTPUT_FILENAME
            ),
        )
    manifest = load_candidate_manifest(
        project_id,
        run_id,
        candidate,
        decision=decision,
    )
    return AutoResearchCandidateRegistryRead(
        project_id=project_id,
        run_id=run_id,
        candidate_id=candidate_id,
        selected=candidate_id == selected_candidate_id,
        root_path=str(base),
        candidate=candidate,
        decision=decision,
        manifest=manifest,
        lineage=AutoResearchCandidateLineageRead(
            selected=candidate_id == selected_candidate_id,
            decision_outcome=decision.outcome if decision is not None else None,
            edges=_candidate_lineage_edges(
                run_id=run_id,
                candidate_id=candidate_id,
                files=manifest.files,
                selected=candidate_id == selected_candidate_id,
                run_assets=run_assets,
            ),
        ),
    )


def load_run_registry(project_id: str, run_id: str) -> AutoResearchRunRegistryRead | None:
    run = load_run(project_id, run_id)
    if run is None:
        return None

    base = _run_path(project_id, run_id)
    selected_candidate_id = run.portfolio.selected_candidate_id if run.portfolio else None
    entries: list[AutoResearchCandidateRegistryEntry] = []
    for candidate in sorted(run.candidates, key=lambda item: (item.rank, item.id)):
        detail = load_candidate_registry(
            project_id,
            run_id,
            candidate.id,
            run=run,
        )
        if detail is None:
            continue
        entries.append(
            AutoResearchCandidateRegistryEntry(
                candidate_id=detail.candidate.id,
                program_id=detail.candidate.program_id,
                rank=detail.candidate.rank,
                title=detail.candidate.title,
                status=detail.candidate.status,
                objective_score=detail.candidate.score,
                selected=detail.selected,
                selected_round_index=detail.candidate.selected_round_index,
                attempt_count=len(detail.candidate.attempts),
                artifact_status=detail.candidate.artifact.status if detail.candidate.artifact else None,
                manifest_source=detail.manifest.manifest_source,
                decision_outcome=detail.decision.outcome if detail.decision is not None else None,
                decision_reason=detail.decision.reason if detail.decision is not None else None,
                files=detail.manifest.files,
            )
        )

    paper_path = run.paper_path or (base / PAPER_FILENAME)
    benchmark_name = None
    if run.spec is not None:
        benchmark_name = run.spec.benchmark_name
    elif run.program is not None:
        benchmark_name = run.program.benchmark_name

    run_assets = AutoResearchRunRegistryFiles(
        root=_asset_ref(base, kind="directory")
        or AutoResearchRegistryAssetRef(path=str(base), kind="directory", exists=False),
        run_json=_asset_ref(base / RUN_FILENAME)
        or AutoResearchRegistryAssetRef(path=str(base / RUN_FILENAME), exists=False),
        program_json=_asset_ref(base / PROGRAM_FILENAME),
        plan_json=_asset_ref(base / PLAN_FILENAME),
        spec_json=_asset_ref(base / SPEC_FILENAME),
        portfolio_json=_asset_ref(base / PORTFOLIO_FILENAME),
        artifact_json=_asset_ref(base / ARTIFACT_FILENAME),
        benchmark_json=_asset_ref(base / BENCHMARK_FILENAME),
        benchmark_card_json=_asset_ref(base / BENCHMARK_CARD_FILENAME),
        generated_code=_asset_ref(run.generated_code_path),
        paper_markdown=_asset_ref(paper_path),
        narrative_report_markdown=_asset_ref(
            run.narrative_report_path or (base / NARRATIVE_REPORT_FILENAME)
        ),
        claim_evidence_matrix_json=_asset_ref(
            run.claim_evidence_matrix_path or (base / CLAIM_EVIDENCE_MATRIX_FILENAME)
        ),
        experiment_design_json=_asset_ref(base / EXPERIMENT_DESIGN_FILENAME),
        failure_analysis_json=_asset_ref(base / FAILURE_ANALYSIS_FILENAME),
        research_replan_json=_asset_ref(base / RESEARCH_REPLAN_FILENAME),
        research_protocol_json=_asset_ref(base / RESEARCH_PROTOCOL_FILENAME),
        methodology_audit_json=_asset_ref(base / METHODOLOGY_AUDIT_FILENAME),
        publication_readiness_json=_asset_ref(base / PUBLICATION_READINESS_FILENAME),
        contribution_assessment_json=_asset_ref(base / CONTRIBUTION_ASSESSMENT_FILENAME),
        literature_graph_json=_asset_ref(base / LITERATURE_GRAPH_FILENAME),
        novelty_validation_json=_asset_ref(base / NOVELTY_VALIDATION_FILENAME),
        revision_dossier_json=_asset_ref(base / REVISION_DOSSIER_FILENAME),
        publication_evidence_index_json=_asset_ref(base / PUBLICATION_EVIDENCE_INDEX_FILENAME),
        artifact_integrity_audit_json=_asset_ref(base / ARTIFACT_INTEGRITY_AUDIT_FILENAME),
        publication_repair_plan_json=_asset_ref(base / PUBLICATION_REPAIR_PLAN_FILENAME),
        publication_repair_execution_json=_asset_ref(base / PUBLICATION_REPAIR_EXECUTION_FILENAME),
        reviewer_simulation_json=_asset_ref(
            run.reviewer_simulation_path or (base / REVIEWER_SIMULATION_FILENAME)
        ),
        experiment_factory_plan_json=_asset_ref(
            run.experiment_factory_plan_path or (base / EXPERIMENT_FACTORY_PLAN_FILENAME)
        ),
        experiment_factory_environment_manifest_json=_asset_ref(
            run.experiment_factory_environment_manifest_path
            or (base / EXPERIMENT_FACTORY_ENVIRONMENT_MANIFEST_FILENAME)
        ),
        experiment_factory_materialized_jobs_json=_asset_ref(
            run.experiment_factory_materialized_jobs_path
            or (base / EXPERIMENT_FACTORY_MATERIALIZED_JOBS_FILENAME)
        ),
        experiment_execution_plan_json=_asset_ref(
            run.experiment_execution_plan_path
            or (base / EXPERIMENT_EXECUTION_PLAN_FILENAME)
        ),
        experiment_execution_result_json=_asset_ref(
            run.experiment_execution_result_path
            or (base / EXPERIMENT_EXECUTION_RESULT_FILENAME)
        ),
        evidence_ledger_json=_asset_ref(
            run.evidence_ledger_path or (base / EVIDENCE_LEDGER_FILENAME)
        ),
        experiment_factory_repair_plan_json=_asset_ref(
            run.experiment_factory_repair_plan_path or (base / EXPERIMENT_FACTORY_REPAIR_PLAN_FILENAME)
        ),
        paper_plan_json=_asset_ref(
            run.paper_plan_path or (base / PAPER_PLAN_FILENAME)
        ),
        figure_plan_json=_asset_ref(
            run.figure_plan_path or (base / FIGURE_PLAN_FILENAME)
        ),
        paper_revision_history_markdown=_asset_ref(
            base / PAPER_SOURCES_DIRNAME / PAPER_REVISION_HISTORY_FILENAME
        ),
        paper_revision_state_json=_asset_ref(
            run.paper_revision_state_path or (base / PAPER_REVISION_STATE_FILENAME)
        ),
        paper_compile_report_json=_asset_ref(
            run.paper_compile_report_path or (base / PAPER_COMPILE_REPORT_FILENAME)
        ),
        paper_revision_diff_json=_asset_ref(
            run.paper_revision_diff_path or (base / PAPER_REVISION_DIFF_FILENAME)
        ),
        paper_revision_action_index_json=_asset_ref(
            run.paper_revision_action_index_path or (base / PAPER_REVISION_ACTION_INDEX_FILENAME)
        ),
        paper_section_rewrite_index_json=_asset_ref(
            run.paper_section_rewrite_index_path or (base / PAPER_SECTION_REWRITE_INDEX_FILENAME)
        ),
        paper_revision_brief_markdown=_asset_ref(
            base / PAPER_SOURCES_DIRNAME / PAPER_REVISION_BRIEF_FILENAME
        ),
        paper_sources_dir=_asset_ref(
            run.paper_sources_dir or (base / PAPER_SOURCES_DIRNAME),
            kind="directory",
        ),
        paper_section_rewrite_packets_dir=_asset_ref(
            run.paper_section_rewrite_packets_dir or (base / PAPER_SOURCES_DIRNAME / PAPER_REWRITE_PACKETS_DIRNAME),
            kind="directory",
        ),
        paper_build_script=_asset_ref(
            base / PAPER_SOURCES_DIRNAME / PAPER_BUILD_SCRIPT_FILENAME
        ),
        paper_checkpoint_index_json=_asset_ref(
            base / PAPER_SOURCES_DIRNAME / PAPER_CHECKPOINTS_DIRNAME / PAPER_CHECKPOINT_INDEX_FILENAME
        ),
        paper_latex_source=_asset_ref(
            run.paper_latex_path or (base / PAPER_SOURCES_DIRNAME / PAPER_LATEX_FILENAME)
        ),
        paper_bibliography_bib=_asset_ref(
            run.paper_bibliography_path or (base / PAPER_SOURCES_DIRNAME / PAPER_BIB_FILENAME)
        ),
        paper_sources_manifest_json=_asset_ref(
            run.paper_sources_manifest_path or (base / PAPER_SOURCES_DIRNAME / PAPER_SOURCES_MANIFEST_FILENAME)
        ),
        paper_compiled_pdf=_asset_ref(
            base / PAPER_SOURCES_DIRNAME / PAPER_COMPILED_PDF_FILENAME
        ),
        paper_bibliography_output_bbl=_asset_ref(
            base / PAPER_SOURCES_DIRNAME / PAPER_BIBLIOGRAPHY_OUTPUT_FILENAME
        ),
    )

    return AutoResearchRunRegistryRead(
        project_id=project_id,
        run_id=run_id,
        topic=run.topic,
        status=run.status,
        task_family=run.task_family,
        program_id=run.program.id if run.program is not None else None,
        benchmark_name=benchmark_name,
        portfolio_status=run.portfolio.status if run.portfolio is not None else None,
        selected_candidate_id=selected_candidate_id,
        decision_summary=run.portfolio.decision_summary if run.portfolio is not None else None,
        root_path=str(base),
        files=run_assets,
        lineage=AutoResearchRunLineageRead(
            selected_candidate_id=selected_candidate_id,
            top_level_plan_candidate_id=selected_candidate_id if run.plan is not None else None,
            top_level_spec_candidate_id=selected_candidate_id if run.spec is not None else None,
            top_level_artifact_candidate_id=selected_candidate_id if run.artifact is not None else None,
            top_level_paper_candidate_id=selected_candidate_id if _asset_ref(paper_path) else None,
            edges=_run_lineage_edges(
                run=run,
                run_assets=run_assets,
            ),
        ),
        candidates=entries,
    )


def load_run_bundle_index(project_id: str, run_id: str) -> AutoResearchBundleIndexRead | None:
    run_registry = load_run_registry(project_id, run_id)
    if run_registry is None:
        return None

    candidate_details: list[AutoResearchCandidateRegistryRead] = []
    for entry in run_registry.candidates:
        detail = load_candidate_registry(project_id, run_id, entry.candidate_id)
        if detail is not None:
            candidate_details.append(detail)

    selected_candidate = next((item for item in candidate_details if item.selected), None)
    selected_candidate_id = run_registry.selected_candidate_id

    selected_bundle_assets: list[AutoResearchBundleAssetRead | None] = _run_bundle_assets(
        run_registry=run_registry
    )
    if selected_candidate is not None:
        selected_bundle_assets.extend(
            _candidate_bundle_assets(candidate_registry=selected_candidate)
        )

    portfolio_bundle_assets: list[AutoResearchBundleAssetRead | None] = _run_bundle_assets(
        run_registry=run_registry
    )
    for detail in candidate_details:
        portfolio_bundle_assets.extend(_candidate_bundle_assets(candidate_registry=detail))

    bundles = [
        _finalize_bundle(
            bundle_id="selected_candidate_repro",
            name="Selected Candidate Repro Bundle",
            description=(
                "Run-level outputs plus the selected candidate workspace, manifest, code, "
                "artifact, and paper assets needed to inspect or export the winning result."
            ),
            selected_candidate_id=selected_candidate_id,
            candidate_ids=[selected_candidate_id] if selected_candidate_id else [],
            assets=selected_bundle_assets,
        ),
        _finalize_bundle(
            bundle_id="portfolio_full",
            name="Full Portfolio Bundle",
            description=(
                "Run-level outputs plus every candidate workspace and manifest-bearing asset, "
                "including eliminated candidates."
            ),
            selected_candidate_id=selected_candidate_id,
            candidate_ids=[item.candidate_id for item in run_registry.candidates],
            assets=portfolio_bundle_assets,
        ),
    ]
    return AutoResearchBundleIndexRead(
        project_id=project_id,
        run_id=run_id,
        bundles=bundles,
    )


def load_run_registry_views(project_id: str, run_id: str) -> AutoResearchRunRegistryViewsRead | None:
    run_registry = load_run_registry(project_id, run_id)
    if run_registry is None:
        return None

    entries = run_registry.candidates
    selected_entries = [item for item in entries if item.selected]
    failed_entries = [
        item
        for item in entries
        if item.decision_outcome == "failed" or item.status == "failed"
    ]
    eliminated_entries = [item for item in entries if item.decision_outcome == "eliminated"]
    active_entries = [
        item
        for item in entries
        if item.decision_outcome in {"pending", "running", "leading"}
    ]

    views = [
        _registry_view(
            view_id="selected",
            label="Selected Candidate",
            description="The promoted portfolio winner that materialized into the run-level outputs.",
            entries=selected_entries,
        ),
        _registry_view(
            view_id="eliminated",
            label="Eliminated Candidates",
            description="Candidates that completed execution but did not win the portfolio.",
            entries=eliminated_entries,
        ),
        _registry_view(
            view_id="failed",
            label="Failed Candidates",
            description="Candidates whose execution failed to produce a promotable artifact.",
            entries=failed_entries,
        ),
        _registry_view(
            view_id="active",
            label="Active Or Pending Candidates",
            description="Candidates that are planned, running, or currently leading before finalization.",
            entries=active_entries,
        ),
        _registry_view(
            view_id="all",
            label="All Candidates",
            description="Complete registry listing for the run.",
            entries=entries,
        ),
    ]

    return AutoResearchRunRegistryViewsRead(
        project_id=project_id,
        run_id=run_id,
        selected_candidate_id=run_registry.selected_candidate_id,
        counts=AutoResearchRegistryViewCounts(
            total_candidates=len(entries),
            selected=len(selected_entries),
            eliminated=len(eliminated_entries),
            failed=len(failed_entries),
            active=len(active_entries),
        ),
        views=views,
    )


def save_candidate_snapshot(
    project_id: str,
    run_id: str,
    candidate: HypothesisCandidate,
    *,
    plan: ResearchPlan,
    spec: ExperimentSpec,
) -> HypothesisCandidate:
    base = candidate_dir(project_id, run_id, candidate.id)
    payload = candidate.model_copy(
        update={
            "workspace_path": str(base),
            "plan_path": str(base / PLAN_FILENAME),
            "spec_path": str(base / SPEC_FILENAME),
            "attempts_path": str(base / ATTEMPTS_FILENAME) if candidate.attempts else None,
            "artifact_path": str(base / ARTIFACT_FILENAME) if candidate.artifact is not None else None,
            "paper_path": (
                candidate.paper_path
                or (str(base / PAPER_FILENAME) if candidate.paper_markdown else None)
            ),
        }
    )
    _write_json(base / CANDIDATE_FILENAME, payload.model_dump(mode="json"))
    _write_json(base / PLAN_FILENAME, plan.model_dump(mode="json"))
    _write_json(base / SPEC_FILENAME, spec.model_dump(mode="json"))
    if payload.attempts:
        _write_json(
            base / ATTEMPTS_FILENAME,
            [item.model_dump(mode="json") for item in payload.attempts],
        )
    if payload.artifact is not None:
        _write_json(base / ARTIFACT_FILENAME, payload.artifact.model_dump(mode="json"))
    if payload.paper_markdown:
        (base / PAPER_FILENAME).write_text(payload.paper_markdown, encoding="utf-8")
    return payload


def save_candidate_manifest(
    project_id: str,
    run_id: str,
    candidate: HypothesisCandidate,
    *,
    decision: PortfolioDecisionRecord | None = None,
) -> HypothesisCandidate:
    base = candidate_dir(project_id, run_id, candidate.id)
    manifest_path = base / MANIFEST_FILENAME
    manifest_payload = {
        "candidate": {
            "id": candidate.id,
            "program_id": candidate.program_id,
            "rank": candidate.rank,
            "title": candidate.title,
            "status": candidate.status,
            "objective_score": candidate.score,
            "selection_reason": candidate.selection_reason,
        },
        "decision": decision.model_dump(mode="json") if decision is not None else None,
        "files": {
            "workspace_path": str(base),
            "candidate_path": str(base / CANDIDATE_FILENAME),
            "plan_path": candidate.plan_path,
            "spec_path": candidate.spec_path,
            "attempts_path": candidate.attempts_path,
            "artifact_path": candidate.artifact_path,
            "generated_code_path": candidate.generated_code_path,
            "paper_path": candidate.paper_path,
        },
    }
    _write_json(manifest_path, manifest_payload)
    return candidate.model_copy(update={"manifest_path": str(manifest_path)})
