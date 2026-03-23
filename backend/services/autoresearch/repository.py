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
    AutoResearchLineageEdgeRead,
    AutoResearchRegistryAssetRef,
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
from services.workspace import autoresearch_dir


RUN_FILENAME = "run.json"
PROGRAM_FILENAME = "program.json"
PLAN_FILENAME = "plan.json"
SPEC_FILENAME = "spec.json"
PORTFOLIO_FILENAME = "portfolio.json"
ARTIFACT_FILENAME = "artifact.json"
CODE_FILENAME = "experiment.py"
PAPER_FILENAME = "paper.md"
NARRATIVE_REPORT_FILENAME = "narrative_report.md"
CLAIM_EVIDENCE_MATRIX_FILENAME = "claim_evidence_matrix.json"
PAPER_PLAN_FILENAME = "paper_plan.json"
FIGURE_PLAN_FILENAME = "figure_plan.json"
PAPER_REVISION_STATE_FILENAME = "paper_revision_state.json"
PAPER_SOURCES_DIRNAME = "paper_sources"
PAPER_LATEX_FILENAME = "main.tex"
PAPER_BIB_FILENAME = "references.bib"
PAPER_SOURCES_MANIFEST_FILENAME = "manifest.json"
BENCHMARK_FILENAME = "benchmark.json"
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


def _run_path(project_id: str, run_id: str) -> Path:
    return _runs_dir(project_id) / run_id


def _candidate_path(project_id: str, run_id: str, candidate_id: str) -> Path:
    return _run_path(project_id, run_id) / CANDIDATES_DIRNAME / candidate_id


def run_dir(project_id: str, run_id: str) -> Path:
    path = _run_path(project_id, run_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def candidate_dir(project_id: str, run_id: str, candidate_id: str) -> Path:
    path = _candidate_path(project_id, run_id, candidate_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _read_json(path: Path) -> object | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


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
            ("paper_plan_json", "paper_plan"),
            ("figure_plan_json", "figure_plan"),
            ("paper_revision_state_json", "paper_revision_state"),
            ("paper_sources_dir", "paper_sources"),
            ("paper_latex_source", "paper_latex"),
            ("paper_bibliography_bib", "paper_bibliography"),
            ("paper_sources_manifest_json", "paper_sources_manifest"),
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
        ("paper_plan_json", "paper_plan"),
        ("figure_plan_json", "figure_plan"),
        ("paper_revision_state_json", "paper_revision_state"),
        ("paper_sources_dir", "paper_sources"),
        ("paper_latex_source", "paper_latex"),
        ("paper_bibliography_bib", "paper_bibliography"),
        ("paper_sources_manifest_json", "paper_sources_manifest"),
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
            asset_id=f"{run_registry.run_id}:run_paper_revision_state_json",
            label="Selected run paper revision state",
            role="run_paper_revision_state_json",
            ref=files.paper_revision_state_json,
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
        request=effective_request,
        benchmark=effective_request.benchmark,
        execution_backend=effective_request.execution_backend,
        docker_image=effective_request.docker_image,
        created_at=now,
        updated_at=now,
    )
    save_run(run)
    return run


def save_run(run: AutoResearchRunRead) -> AutoResearchRunRead:
    payload = run.model_copy(update={"updated_at": _utcnow()})
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
    if payload.paper_markdown:
        (base / PAPER_FILENAME).write_text(payload.paper_markdown, encoding="utf-8")
    if payload.narrative_report_markdown:
        (base / NARRATIVE_REPORT_FILENAME).write_text(payload.narrative_report_markdown, encoding="utf-8")
    if payload.claim_evidence_matrix is not None:
        _write_json(base / CLAIM_EVIDENCE_MATRIX_FILENAME, payload.claim_evidence_matrix.model_dump(mode="json"))
    if payload.paper_plan is not None:
        _write_json(base / PAPER_PLAN_FILENAME, payload.paper_plan.model_dump(mode="json"))
    if payload.figure_plan is not None:
        _write_json(base / FIGURE_PLAN_FILENAME, payload.figure_plan.model_dump(mode="json"))
    if payload.paper_revision_state is not None:
        _write_json(base / PAPER_REVISION_STATE_FILENAME, payload.paper_revision_state.model_dump(mode="json"))
    if (
        payload.paper_latex_source is not None
        or payload.paper_bibliography_bib is not None
        or payload.paper_sources_manifest is not None
    ):
        paper_sources_dir = base / PAPER_SOURCES_DIRNAME
        paper_sources_dir.mkdir(parents=True, exist_ok=True)
        if payload.paper_latex_source is not None:
            (paper_sources_dir / PAPER_LATEX_FILENAME).write_text(payload.paper_latex_source, encoding="utf-8")
        if payload.paper_bibliography_bib is not None:
            (paper_sources_dir / PAPER_BIB_FILENAME).write_text(payload.paper_bibliography_bib, encoding="utf-8")
        if payload.paper_sources_manifest is not None:
            _write_json(
                paper_sources_dir / PAPER_SOURCES_MANIFEST_FILENAME,
                payload.paper_sources_manifest.model_dump(mode="json"),
            )
    return payload


def load_run(project_id: str, run_id: str) -> AutoResearchRunRead | None:
    path = _run_path(project_id, run_id) / RUN_FILENAME
    if not path.exists():
        return None
    return AutoResearchRunRead.model_validate_json(path.read_text(encoding="utf-8"))


def list_runs(project_id: str) -> list[AutoResearchRunRead]:
    items: list[AutoResearchRunRead] = []
    root = _runs_dir(project_id)
    for path in sorted(root.glob("*/run.json"), reverse=True):
        try:
            items.append(AutoResearchRunRead.model_validate_json(path.read_text(encoding="utf-8")))
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


def narrative_report_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / NARRATIVE_REPORT_FILENAME)


def claim_evidence_matrix_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / CLAIM_EVIDENCE_MATRIX_FILENAME)


def paper_plan_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PAPER_PLAN_FILENAME)


def figure_plan_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / FIGURE_PLAN_FILENAME)


def paper_revision_state_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PAPER_REVISION_STATE_FILENAME)


def paper_sources_dir_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PAPER_SOURCES_DIRNAME)


def paper_latex_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PAPER_SOURCES_DIRNAME / PAPER_LATEX_FILENAME)


def paper_bibliography_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PAPER_SOURCES_DIRNAME / PAPER_BIB_FILENAME)


def paper_sources_manifest_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PAPER_SOURCES_DIRNAME / PAPER_SOURCES_MANIFEST_FILENAME)


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
            generated_code=_asset_ref(current_run.generated_code_path),
            paper_markdown=_asset_ref(run_paper_path),
            narrative_report_markdown=_asset_ref(
                current_run.narrative_report_path or (run_base / NARRATIVE_REPORT_FILENAME)
            ),
            claim_evidence_matrix_json=_asset_ref(
                current_run.claim_evidence_matrix_path or (run_base / CLAIM_EVIDENCE_MATRIX_FILENAME)
            ),
            paper_plan_json=_asset_ref(
                current_run.paper_plan_path or (run_base / PAPER_PLAN_FILENAME)
            ),
            figure_plan_json=_asset_ref(
                current_run.figure_plan_path or (run_base / FIGURE_PLAN_FILENAME)
            ),
            paper_revision_state_json=_asset_ref(
                current_run.paper_revision_state_path or (run_base / PAPER_REVISION_STATE_FILENAME)
            ),
            paper_sources_dir=_asset_ref(
                current_run.paper_sources_dir or (run_base / PAPER_SOURCES_DIRNAME),
                kind="directory",
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
        generated_code=_asset_ref(run.generated_code_path),
        paper_markdown=_asset_ref(paper_path),
        narrative_report_markdown=_asset_ref(
            run.narrative_report_path or (base / NARRATIVE_REPORT_FILENAME)
        ),
        claim_evidence_matrix_json=_asset_ref(
            run.claim_evidence_matrix_path or (base / CLAIM_EVIDENCE_MATRIX_FILENAME)
        ),
        paper_plan_json=_asset_ref(
            run.paper_plan_path or (base / PAPER_PLAN_FILENAME)
        ),
        figure_plan_json=_asset_ref(
            run.figure_plan_path or (base / FIGURE_PLAN_FILENAME)
        ),
        paper_revision_state_json=_asset_ref(
            run.paper_revision_state_path or (base / PAPER_REVISION_STATE_FILENAME)
        ),
        paper_sources_dir=_asset_ref(
            run.paper_sources_dir or (base / PAPER_SOURCES_DIRNAME),
            kind="directory",
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
