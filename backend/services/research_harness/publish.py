"""Session 14 — P3 publication surface: publish-bundle export (plan §6).

Builds a self-contained publish bundle on top of the NEW research_harness
workspace. The bundle is the minimum needed to ship / archive / review an honest
research artifact offline:

  publish_bundle/
    manifest.json                 <- idea, best candidate, honest verdict, audit
                                     gate, unverified count, metric summary,
                                     provenance, publishable flag + reason
    paper/draft.md                <- the audited draft (with [UNVERIFIED] markers)
    code/experiment.py            <- reproducible experiment
    code/requirements.txt
    evidence/portfolio.json       <- aggregated portfolio ledger
    evidence/anchored_verdict.json<- hypothesis-anchored honest verdict + kill criteria
    evidence/claim_audit.json     <- per-claim audit ledger

Honesty contract (non-negotiable, mirrors V2.2/V2.3 honest gates): a bundle is
``publishable: false`` whenever the audit gate failed OR the honest verdict is a
non-publishable outcome (negative / all_negative / execution_failed /
no_comparison). The manifest always carries the full honest verdict + unverified
count regardless of the flag — transparency, never suppression.

YAGNI: no venue adapters, no compliance-checklist matrix, no auto-deploy. This is
the minimal usable publication surface on a weighted, honest artifact.
"""
from __future__ import annotations

import json
import logging
import zipfile
from pathlib import Path
from typing import Any

from services.research_harness import pipeline

logger = logging.getLogger("research_harness.publish")

MANIFEST_VERSION = "1.0"

# Verdicts that are not honest positive results and therefore block publication.
# "no_comparison" = no baseline comparison (no evidence of improvement);
# "execution_failed" = code never produced results; "negative" = worse than baseline.
_NON_PUBLISHABLE_VERDICTS: frozenset[str] = frozenset(
    {"execution_failed", "no_comparison", "negative"}
)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except (OSError, json.JSONDecodeError):
        return default


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError:
        return ""


def _bundle_name(manifest: dict) -> str:
    """Stable, human-readable archive name (no timestamps — reproducible)."""
    pid = manifest.get("project_id", "project")
    cand = manifest.get("best_candidate_id") or "best"
    pub = "publishable" if manifest.get("publishable") else "gated"
    return f"{pid}__{cand}__{pub}.zip"


def build_publish_bundle(project_id: str) -> dict:
    """Aggregate the workspace into a publish-bundle manifest + zip.

    Reads the new workspace, writes ``publish_bundle/manifest.json`` and
    ``publish_bundle.zip`` into the workspace, and returns the manifest dict.

    Raises ``FileNotFoundError`` if the workspace does not exist (the API layer
    maps this to a 404).
    """
    proj = pipeline.project_dir(project_id)
    if not proj.exists():
        raise FileNotFoundError(f"Project workspace not found: {project_id}")

    meta = pipeline.read_project_meta(project_id) or {"project_id": project_id, "idea": project_id}
    metrics = pipeline.load_metrics(project_id)
    portfolio = _read_json(proj / "ledger" / "portfolio.json", None) or {}
    anchored = _read_json(proj / "ledger" / "anchored_verdict.json", None) or {}
    audit = _read_json(proj / "ledger" / "claim_audit.json", None) or {}

    best_candidate_id = portfolio.get("best_candidate_id") if isinstance(portfolio, dict) else None
    portfolio_verdict = portfolio.get("portfolio_verdict") if isinstance(portfolio, dict) else None

    verdict = anchored.get("verdict") if isinstance(anchored, dict) else None
    gate = bool(audit.get("gate", False)) if isinstance(audit, dict) else False
    unverified = audit.get("unverified_count", 0) if isinstance(audit, dict) else 0
    omission_unverified = audit.get("omission_unverified_count", 0) if isinstance(audit, dict) else 0
    citation_unverified = audit.get("citation_unverified_count", 0) if isinstance(audit, dict) else 0

    baseline_comparison = metrics.get("baseline_comparison") or {} if isinstance(metrics, dict) else {}
    statistics = metrics.get("statistics") or {} if isinstance(metrics, dict) else {}
    datasets = [
        d.get("dataset") for d in (baseline_comparison.get("datasets") or [])
        if isinstance(d, dict) and d.get("dataset")
    ]

    # --- publishable decision (honesty contract) ---
    reasons: list[str] = []
    if not gate:
        breakdown = []
        if omission_unverified:
            breakdown.append(f"{omission_unverified} omission")
        if citation_unverified:
            breakdown.append(f"{citation_unverified} citation")
        detail = f" ({', '.join(breakdown)})" if breakdown else ""
        reasons.append(f"audit gate failed: {unverified} unverified claim(s){detail}")
    if verdict in _NON_PUBLISHABLE_VERDICTS:
        reasons.append(f"verdict is {verdict}")
    if portfolio_verdict == "all_negative":
        reasons.append("portfolio all_negative")

    publishable = not reasons
    publishable_reason = "; ".join(reasons)

    manifest: dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "project_id": project_id,
        "idea": meta.get("idea", project_id),
        "best_candidate_id": best_candidate_id,
        "honest_verdict": anchored if isinstance(anchored, dict) else {},
        "portfolio_verdict": portfolio_verdict,
        "audit_gate": {
            "gate": gate,
            "total_claims": audit.get("total_claims", 0) if isinstance(audit, dict) else 0,
            "verified_count": audit.get("verified_count", 0) if isinstance(audit, dict) else 0,
            "unverified_count": unverified,
            "citation_unverified_count": citation_unverified,
            "omission_unverified_count": omission_unverified,
        },
        "publishable": publishable,
        "publishable_reason": publishable_reason,
        "metric_summary": {
            "execution_status": metrics.get("execution_status") if isinstance(metrics, dict) else None,
            "primary_metric": baseline_comparison.get("metric_name"),
            "overall_beats_baseline": bool(baseline_comparison.get("overall_beats_baseline", False)),
            "any_significant": bool(statistics.get("any_significant", False)),
            "seed_count": statistics.get("seed_count", 0),
            "datasets": baseline_comparison.get("datasets", []),
        },
        "provenance": {
            "created_at": meta.get("created_at"),
            "updated_at": meta.get("updated_at"),
            "datasets": datasets,
            "seed_count": statistics.get("seed_count", 0),
            "candidate_count": len(portfolio.get("summary", [])) if isinstance(portfolio, dict) else 0,
            "run_steps_done": [
                e.get("step") for e in pipeline.read_timeline(project_id) if e.get("status") == "done"
            ],
        },
        "bundle_files": [
            "manifest.json",
            "paper/draft.md",
            "code/experiment.py",
            "code/requirements.txt",
            "evidence/portfolio.json",
            "evidence/anchored_verdict.json",
            "evidence/claim_audit.json",
        ],
    }

    _write_bundle(proj, manifest)
    return manifest


def _write_bundle(proj: Path, manifest: dict) -> None:
    """Persist ``publish_bundle/manifest.json`` + ``publish_bundle.zip``."""
    bundle_dir = proj / "publish_bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2)
    (bundle_dir / "manifest.json").write_text(manifest_json, encoding="utf-8")

    # Assemble the zip from the workspace files that exist (skip missing pieces
    # rather than failing — a partial workspace still produces an honest bundle).
    entries: list[tuple[str, bytes]] = [("manifest.json", manifest_json.encode("utf-8"))]
    sources: list[tuple[str, Path]] = [
        ("paper/draft.md", proj / "paper" / "draft.md"),
        ("code/experiment.py", proj / "code" / "experiment.py"),
        ("code/requirements.txt", proj / "code" / "requirements.txt"),
        ("evidence/portfolio.json", proj / "ledger" / "portfolio.json"),
        ("evidence/anchored_verdict.json", proj / "ledger" / "anchored_verdict.json"),
        ("evidence/claim_audit.json", proj / "ledger" / "claim_audit.json"),
    ]
    for arcname, src in sources:
        if src.is_file():
            entries.append((arcname, src.read_bytes()))

    zip_path = bundle_dir / "publish_bundle.zip"
    # Stable, reproducible archive: deterministic member order, no per-entry timestamp.
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, data in entries:
            info = zipfile.ZipInfo(arcname)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.date_time = (1980, 1, 1, 0, 0, 0)  # fixed → reproducible bytes
            zf.writestr(info, data)
    logger.info("Wrote publish bundle for %s (%d files)", manifest.get("project_id"), len(entries))
