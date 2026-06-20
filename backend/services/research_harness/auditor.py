"""AuditorAgent (V2, plan §6) — post-writing evidence gate.

Ports the *logic* (not the 13975-line orchestrator) of the frozen
``claim_evidence_gate.py`` / ``citation_verifier.py`` / ``paper_evidence_compiler.py``
into a small, deterministic, self-contained gate that runs AFTER the Writer.

Contract (docs/goal_session6.md Step 3, hard constraints — never loosened):
  - claim with no supporting metric / citation → marked ``[UNVERIFIED]`` → gate false
  - "significantly outperforms" with no significant favorable result → ``[UNVERIFIED]``
  - "outperforms across all datasets" when the method lost on some dataset → ``[UNVERIFIED]``
  - "competitive" / "promising" on a negative result → ``[UNVERIFIED]``
  - execution never ran → the draft must not contain a results section (Writer-enforced;
    the Auditor still flags any result-style claim it finds)

The gate is deliberately NON-LLM: verifying an LLM's claims with another LLM call is
circular. Evidence comes from ``metrics.json`` + ``papers.jsonl`` (what the experiment
actually produced), matched by portable keyword overlap (the frozen gate's approach).

Outputs: rewrites ``paper/draft.md`` with inline ``[UNVERIFIED: reason]`` markers,
writes ``ledger/claim_audit.json``, and annotates ``research_report.md`` with the
gate outcome (never silently passing a failed audit).
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from config.settings import settings
from services.research_harness import citation
from services.research_harness import evidence

logger = logging.getLogger(__name__)
WORKSPACE_ROOT = Path(settings.data_dir) / "research_workspace"

# Cue sets (port of paper_evidence_compiler's strong/overclaim cues, trimmed to the
# portable substrings the gate acts on). Matched case-insensitively as substrings.
_RESULT_CUES: tuple[str, ...] = (
    "outperform", "significantly", "superior", "improve", "improves", "improved",
    "improvement", "achieves", "achieve", "demonstrate", "demonstrates", "establish",
    "beats", "beat the baseline", "better than", "higher than", "lower error",
    "best-performing", "highest", "strongest", "robust",
)
_SPIN_CUES: tuple[str, ...] = (
    "competitive", "promising", "state-of-the-art", "sota", "novel", "contribution",
)
# A sentence is a "claim" worth auditing if it carries any result or spin cue.
_CLAIM_CUES: tuple[str, ...] = _RESULT_CUES + _SPIN_CUES

# Universal-scope phrases → "outperforms across all datasets" style overclaim.
_SCOPE_PHRASES: tuple[str, ...] = (
    "all datasets", "every dataset", "across all", "all three", "all of the",
    "uniformly", "consistently", "in every", "on each dataset", "broadly",
    "generalization", "generalizes", "robustly",
)

# Split on sentence-final punctuation followed by whitespace + a capital/structural opener.
# Resists splitting on decimals like "0.003" (the "." there is followed by a digit, not whitespace).
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(“\"`\[])")


def _project_dir(project_id: str) -> Path:
    return WORKSPACE_ROOT / project_id


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT_RE.split(text or "") if s and s.strip()]


def _dataset_names(metrics: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for d in (metrics.get("baseline_comparison") or {}).get("datasets") or []:
        if isinstance(d, dict) and d.get("dataset"):
            names.add(str(d["dataset"]))
    return names


def _lost_datasets(metrics: dict[str, Any]) -> list[str]:
    return [
        str(d["dataset"])
        for d in (metrics.get("baseline_comparison") or {}).get("datasets") or []
        if isinstance(d, dict) and d.get("beats_baseline") is False
    ]


# --------------------------------------------------------------------------- #
# V2.2 omitted-material-metric gate (goal_session8.md Step 3)
# --------------------------------------------------------------------------- #
#
# Closes the "selective reporting" hole: a draft that reports success on a
# generic metric (macro_f1) while silently dropping the hypothesis's actual
# target metrics (abstention / calibration). A metric that IS in metrics.json,
# IS material to the hypothesis's main target (primary metric name, or the
# abstention/error/spearman/consistency keyword family), but is NEVER mentioned
# in the draft → an ``category="omission"`` claim that fails the gate. Only adds
# claims; never loosens an existing verdict.

_MATERIAL_METRIC_KEYWORDS: tuple[str, ...] = (
    "abstention", "abstain", "spearman", "consistency", "error_rate", "calibration",
)
# Tokens too generic to count as "the draft discussed this metric".
_GENERIC_METRIC_TOKENS: frozenset[str] = frozenset(
    {"score", "value", "metric", "rate", "label", "result", "test", "data", "mean"}
)


def _distinctive_metric_tokens(name: str) -> list[str]:
    toks = re.split(r"[_\s\-]+", (name or "").lower())
    return [t for t in toks if len(t) >= 5 and t not in _GENERIC_METRIC_TOKENS and not t.isdigit()]


def _metric_mentioned(name: str, draft_lower: str) -> bool:
    """Is ``name`` discussed in the draft? Full-name match (with underscores or
    spaces) OR a distinctive (≥5-char, non-generic) token of the name appears."""
    if not name:
        return False
    n = name.lower()
    if n in draft_lower or n.replace("_", " ") in draft_lower:
        return True
    return any(tok in draft_lower for tok in _distinctive_metric_tokens(name))


def _material_metric_names(metrics: dict[str, Any], primary_name: str | None) -> set[str]:
    """Metrics material to the hypothesis's main target: the abstention family
    (always material when present) + any metric whose name carries a material
    keyword + the hypothesis's resolved primary metric (when non-generic)."""
    names: set[str] = set()
    for key in (metrics.get("abstention_metrics") or {}):
        if isinstance(key, str):
            names.add(key)
    for name in evidence._metric_names_in_metrics(metrics):
        n = name.lower()
        if any(kw in n for kw in _MATERIAL_METRIC_KEYWORDS):
            names.add(name)
    if primary_name:
        names.add(primary_name)
    return names


def _omitted_material_metrics(
    draft_text: str,
    metrics: dict[str, Any],
    hypothesis: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Material metrics present in ``metrics`` but absent from the draft body.

    Returns ``category="omission"`` claims (verdict=unverified). Returns ``[]``
    when there is no hypothesis (the gate is hypothesis-anchored — only-add)."""
    if not hypothesis:
        return []
    pm = evidence.primary_metric_for(hypothesis, metrics)
    primary_name = pm["name"] if pm["source"] != "comparison_default" else None
    candidates = _material_metric_names(metrics, primary_name)
    draft_lower = (draft_text or "").lower()
    omitted: list[dict[str, Any]] = []
    for i, name in enumerate(sorted(candidates), start=1):
        if _metric_mentioned(name, draft_lower):
            continue
        omitted.append(
            {
                "claim_id": f"omission_{i}",
                "claim": name,
                "metric": name,
                "verdict": "unverified",
                "category": "omission",
                "evidence_refs": [],
                "reason": f'omitted material metric "{name}"',
            }
        )
    return omitted


def _has_any(text: str, cues: tuple[str, ...]) -> bool:
    lowered = (text or "").lower()
    return any(cue in lowered for cue in cues)


def extract_claims(draft_text: str) -> list[dict[str, Any]]:
    """Sentences carrying a result/spin cue — these are the claims that need evidence.

    Descriptive sentences without a cue are not audited (background/method text).
    Markdown heading lines are dropped before splitting so a claim never absorbs a
    ``# Heading``; the surviving sentences remain verbatim substrings of the draft,
    so :func:`annotate_draft` can still locate them for inline marking.
    Each claim dict: ``{id, text, category}`` where category ∈ {result, spin}.
    """
    # Drop standalone markdown headers (structural, not claims).
    body = "\n".join(
        line for line in (draft_text or "").splitlines()
        if not re.match(r"^#{1,6}\s", line)
    )
    claims: list[dict[str, Any]] = []
    idx = 0
    for sentence in _split_sentences(body):
        if not _has_any(sentence, _CLAIM_CUES):
            continue
        category = "spin" if _has_any(sentence, _SPIN_CUES) and not _has_any(sentence, _RESULT_CUES) else "result"
        idx += 1
        claims.append({"id": f"claim_{idx}", "text": sentence, "category": category})
    return claims


def _citation_claim(result: dict[str, Any], index: int) -> dict[str, Any]:
    """Lift a citation.verify_citations result into the ledger's claim shape."""
    title = result.get("raw_title") or result.get("marker") or ""
    marker = result.get("marker", "")
    display = f"{marker} {title}".strip() or title
    return {
        "id": f"citation_{index}",
        "text": display,
        "category": "citation",
        "raw_title": title,
        "marker": marker,
    }


def _evidence_overlap(claim_text: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Evidence items whose keyword set overlaps the claim (≥2 shared terms, or ≥30% of the
    claim's keywords). Port of claim_evidence_gate._match_evidence."""
    claim_kw = evidence.keywords(claim_text)
    if not claim_kw:
        return []
    matched: list[dict[str, Any]] = []
    for item in items:
        overlap = claim_kw & item.get("keywords", set())
        if len(overlap) >= 2 or len(overlap) / len(claim_kw) >= 0.3:
            matched.append(item)
    return matched


def _classify_claim(claim: dict[str, Any], metrics: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply the overclaim rules, then the evidence check. Returns a verdict dict.

    verdict ∈ {"verified", "unverified"}; gates on the FIRST overclaim rule that fires.
    """
    text = claim["text"]
    cid = claim["id"]
    cat = claim.get("category", "result")
    v = evidence.verdict(metrics)
    datasets = _dataset_names(metrics)
    lost = _lost_datasets(metrics)
    has_sig = evidence.has_significant_favorable(metrics)
    text_lower = text.lower()
    names_dataset = any(evidence.keywords(d) & evidence.keywords(text) for d in datasets) or any(
        d.lower() in text_lower for d in datasets
    )

    # Rule 1 — significance overclaim: claims significant superiority with no significant favorable result.
    sig_superiority = "significantly" in text_lower and _has_any(text, ("outperform", "superior", "improve", "better", "beats"))
    if sig_superiority and not has_sig:
        return _verdict(cid, "unverified", text, [],
                        "claims a significant superiority but no statistically significant favorable result exists", cat)

    # Rule 2 — scope overclaim: uniform/general superiority while the method lost on some dataset.
    if _has_any(text, _SCOPE_PHRASES) and lost:
        return _verdict(
            cid, "unverified", text, [],
            f"claims uniform/general superiority but the proposed method lost on: {', '.join(lost)}", cat,
        )

    # Rule 3 — positive spin on a negative result.
    if v == "negative" and _has_any(text, ("competitive", "promising", "state-of-the-art", "sota")):
        return _verdict(cid, "unverified", text, [],
                        "uses competitive/promising/state-of-the-art wording for a negative result", cat)

    # Rule 4 — global superiority without a dataset qualifier while overall not beating baseline.
    bare_superiority = _has_any(text, ("outperforms the baseline", "beats the baseline", "superior to the baseline"))
    if bare_superiority and not names_dataset and (metrics.get("baseline_comparison") or {}).get("overall_beats_baseline") is False:
        return _verdict(cid, "unverified", text, [],
                        "claims to outperform the baseline overall but the proposed method does not beat it overall", cat)

    # Rule 5 — evidence check: must find supporting metric/citation.
    matched = _evidence_overlap(text, items)
    if matched:
        return _verdict(
            cid, "verified", text, [m["id"] for m in matched],
            "supported by metric evidence: " + " | ".join(m["summary"] for m in matched[:3]),
            claim.get("category", "result"),
        )
    return _verdict(cid, "unverified", text, [], "no supporting metric or citation found for this claim", claim.get("category", "result"))


def _verdict(
    cid: str,
    verdict_kind: str,
    text: str,
    refs: list[str],
    reason: str,
    category: str = "result",
) -> dict[str, Any]:
    return {
        "claim_id": cid,
        "claim": text,
        "verdict": verdict_kind,
        "category": category,
        "evidence_refs": refs,
        "reason": reason,
    }


def _citation_verdict(claim: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Lift a citation.verify_citations result into the ledger's claim shape."""
    verdict_kind = result.get("verdict", "unverified")
    reason = result.get("reason") or (
        "matched retrieved literature" if verdict_kind == "verified" else "citation not found in retrieved literature"
    )
    refs = [result["matched_title"]] if verdict_kind == "verified" and result.get("matched_title") else []
    if result.get("source") in {"dblp", "crossref"}:
        reason = f"matched external source ({result['source']})"
    return {
        "claim_id": claim["id"],
        "claim": claim["text"],
        "verdict": verdict_kind,
        "category": "citation",
        "raw_title": claim.get("raw_title", ""),
        "marker": claim.get("marker", ""),
        "evidence_refs": refs,
        "reason": reason,
    }


def audit_draft(
    draft_text: str,
    metrics: dict[str, Any],
    papers: list[dict[str, Any]] | None = None,
    *,
    live: bool | None = None,
    hypothesis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pure audit: returns the ledger dict without touching disk.

    Three gate families, all never loosened:
      1. **Metric/overclaim gate** (V2): each result/spin claim must be backed by a
         metric or literature-overlap item, and must not overclaim significance /
         scope / positive spin on a loss.
      2. **Citation gate** (V2.1): each ``[n]`` / ``"Title"`` / reference-list entry
         must resolve to a paper in ``papers.jsonl`` (offline) — else it is marked
         ``[UNVERIFIED: citation "…" not found in retrieved literature]`` and fails
         the gate. ``live`` enables an optional DBLP/CrossRef second chance under
         ``live_research`` only.
      3. **Omitted-material-metric gate** (V2.2, hypothesis-anchored): a metric that
         IS in ``metrics`` and IS material to the hypothesis's main target but is
         NEVER mentioned in the draft → ``[UNVERIFIED: omitted material metric …]``
         and fails the gate. Inert when ``hypothesis`` is None (only-add).

    Returns the ledger dict. ``unverified_count`` and ``gate`` reflect ALL gates.
    """
    items = evidence.build_evidence_items(metrics)
    # Fold paper titles into the evidence pool so literature-grounded claims can match too.
    if papers:
        for i, p in enumerate(papers[:30]):
            if not isinstance(p, dict):
                continue
            title = p.get("title") or ""
            items.append({"id": f"lit_{i}", "kind": "literature", "summary": title, "keywords": evidence.keywords(title)})

    claim_sentences = extract_claims(draft_text)
    verdicts = [_classify_claim(c, metrics, items) for c in claim_sentences]

    # Citation gate (V2.1). One call, offline by default; live is opt-in and safe.
    citation_results = citation.verify_citations(draft_text, papers or [], live=live)
    for i, result in enumerate(citation_results, start=1):
        cclaim = _citation_claim(result, i)
        verdicts.append(_citation_verdict(cclaim, result))

    # Omitted-material-metric gate (V2.2). Hypothesis-anchored; inert without one.
    verdicts.extend(_omitted_material_metrics(draft_text, metrics, hypothesis))

    unverified = [v for v in verdicts if v["verdict"] == "unverified"]
    gate = len(unverified) == 0
    citation_unverified = sum(1 for v in verdicts if v.get("category") == "citation" and v["verdict"] == "unverified")
    omission_unverified = sum(1 for v in verdicts if v.get("category") == "omission" and v["verdict"] == "unverified")

    return {
        "total_claims": len(verdicts),
        "verified_count": len(verdicts) - len(unverified),
        "unverified_count": len(unverified),
        "citation_unverified_count": citation_unverified,
        "omission_unverified_count": omission_unverified,
        "gate": gate,
        "claims": verdicts,
        "verdict": evidence.verdict(metrics),
        "audited_at": datetime.now().isoformat(timespec="seconds"),
    }


def annotate_draft(draft_text: str, result: dict[str, Any]) -> str:
    """Insert ``[UNVERIFIED: reason]`` after each unverified claim sentence, and
    after each unverified citation's title/entry.

    Sentence claims are matched by exact text (they were extracted from the same
    draft). Citation claims are matched by their ``raw_title`` substring — if the
    title isn't found verbatim (e.g. the Writer paraphrased it), the marker is
    skipped rather than corrupting the text; the ledger still records the verdict.
    """
    annotated = draft_text
    for v in result.get("claims", []):
        if v["verdict"] != "unverified":
            continue
        if v.get("category") == "omission":
            continue  # no in-text anchor — handled by the appended block below.
        marker = f" [UNVERIFIED: {v['reason']}]"
        if marker in annotated:
            continue
        if v.get("category") == "citation":
            anchor = v.get("raw_title") or v.get("marker") or ""
            if not anchor:
                continue
            idx = annotated.find(anchor)
        else:
            anchor = v["claim"]
            idx = annotated.find(anchor)
        if idx == -1:
            continue
        end = idx + len(anchor)
        annotated = annotated[:end] + marker + annotated[end:]

    # Omission claims have no in-text anchor (the metric is missing by definition);
    # append a clearly-delimited block so the draft still carries the inline markers.
    omissions = [
        v for v in result.get("claims", [])
        if v.get("category") == "omission" and v["verdict"] == "unverified"
    ]
    if omissions:
        block = "\n\n<!-- auditor: omitted material metrics (V2.2 honesty gate) -->\n"
        for v in omissions:
            block += f"> [UNVERIFIED: {v['reason']}]\n"
        annotated = annotated.rstrip() + "\n" + block
    return annotated


_REPORT_AUDIT_HEADER = "## Paper Audit"


def _annotate_report(project_id: str, result: dict[str, Any]) -> None:
    """Append a clearly-delimited audit section to research_report.md (idempotent).

    Never edits the honest Conclusion — only appends the post-hoc gate outcome, so a
    failed audit can never be silently passed. If write/audit ran but the report is
    missing, the ledger on disk still carries the verdict.
    """
    report_path = _project_dir(project_id) / "research_report.md"
    if not report_path.exists():
        return
    existing = report_path.read_text(encoding="utf-8")
    # Drop a previously-appended audit section so reruns don't stack duplicates.
    if _REPORT_AUDIT_HEADER in existing:
        existing = existing.split(_REPORT_AUDIT_HEADER)[0].rstrip() + "\n"
    gate_word = "PASSED" if result.get("gate") else "FAILED"
    citation_line = ""
    citation_unverified = result.get("citation_unverified_count") or 0
    if citation_unverified:
        citation_line = (
            f" Of the unverified, {citation_unverified} are citations not found in the "
            "retrieved literature (possible hallucinated references)."
        )
    section = (
        f"\n\n{_REPORT_AUDIT_HEADER}\n\n"
        f"The paper draft was audited against the experiment's own metrics and the "
        f"retrieved literature. "
        f"**Gate: {gate_word}** — {result.get('verified_count', 0)}/{result.get('total_claims', 0)} "
        f"claims verified, {result.get('unverified_count', 0)} unverified.{citation_line} "
        f"Verdict of the underlying experiment: `{result.get('verdict')}`. "
        "Unverified claims are marked `[UNVERIFIED]` inline in `paper/draft.md`; see "
        "`ledger/claim_audit.json` for the full per-claim ledger.\n"
    )
    report_path.write_text(existing + section, encoding="utf-8")


# Matches the Auditor's OWN previously-injected omission block (the marker
# ``annotate_draft`` appends at line ~428) so a re-audit can strip it before
# auditing. A draft that carries this marker into a re-audit is "poisoned": the
# metric name inside the marker satisfies ``_metric_mentioned`` (pseudo-clearing
# the very omission it flags) and the quoted name trips a false citation. Only
# the stable prefix is anchored, so the match survives suffix/version drift.
_AUDITOR_OMISSION_BLOCK_RE = re.compile(
    r"\n*<!-- auditor: omitted material metrics\b.*?(?=\n\n|\Z)",
    re.DOTALL,
)
_ORPHAN_OMISSION_MARKER_PREFIX = "> [UNVERIFIED: omitted material"


def _strip_self_injected_omission_block(draft_text: str) -> str:
    """Remove the Auditor's own previously-injected omission block before re-auditing.

    Re-audit hygiene: ``annotate_draft`` appends a ``<!-- auditor: omitted material
    metrics … -->`` block plus ``> [UNVERIFIED: omitted material metric "…"]`` lines
    to flag omissions inline. On the NEXT ``run_auditor_agent`` re-audit the Auditor
    read that marker back as draft content, which (a) pseudo-cleared the omission —
    the metric name inside the marker satisfied ``_metric_mentioned`` — and (b) the
    quoted name tripped a false citation. Stripping the Auditor's own write-back lets
    re-audit see the human content.

    **Only-add / never-loosen**: a real omission (a material metric genuinely absent
    from the human text) is still reported once the marker is gone — only the
    Auditor's own marker is removed, never a human sentence. See the regression test
    ``test_research_harness_auditor_marker_hygiene.py``.
    """
    cleaned = _AUDITOR_OMISSION_BLOCK_RE.sub("", draft_text or "")
    # Defense-in-depth: drop an orphaned omitted-metric marker line even if the HTML
    # comment header that normally precedes it is missing.
    cleaned = "\n".join(
        line
        for line in cleaned.splitlines()
        if not line.strip().startswith(_ORPHAN_OMISSION_MARKER_PREFIX)
    )
    if cleaned and not cleaned.endswith("\n"):
        cleaned += "\n"
    return cleaned


def run_auditor_agent(project_id: str, metrics: dict[str, Any]) -> dict[str, Any]:
    """Read paper/draft.md, audit it, write ledger + annotated draft + report annotation."""
    proj = _project_dir(project_id)
    draft_path = proj / "paper" / "draft.md"
    if not draft_path.exists():
        logger.warning("[AuditorAgent] no paper/draft.md for %s — skipping audit", project_id)
        return {"gate": False, "skipped": True, "reason": "no_draft"}

    draft_text = draft_path.read_text(encoding="utf-8")
    # Re-audit hygiene (only-add): strip our OWN previously-injected omission block so
    # the marker can't pseudo-clear an omission or trigger a false citation. Real
    # omissions are still detected from the human content.
    draft_text = _strip_self_injected_omission_block(draft_text)

    papers: list[dict[str, Any]] = []
    papers_path = proj / "literature" / "papers.jsonl"
    if papers_path.exists():
        for line in papers_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                papers.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # Load the selected hypothesis so the V2.2 omitted-material-metric gate is anchored.
    selected: dict[str, Any] | None = None
    selected_path = proj / "ideas" / "selected.json"
    if selected_path.exists():
        try:
            loaded = json.loads(selected_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                selected = loaded
        except json.JSONDecodeError:
            selected = None

    result = audit_draft(draft_text, metrics, papers, hypothesis=selected)

    ledger_dir = proj / "ledger"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    (ledger_dir / "claim_audit.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Rewrite draft.md with inline [UNVERIFIED] markers; keep draft.raw.md pristine.
    annotated = annotate_draft(draft_text, result)
    draft_path.write_text(annotated, encoding="utf-8")

    _annotate_report(project_id, result)

    logger.info(
        "[AuditorAgent] %s: gate=%s verified=%d unverified=%d",
        project_id, result["gate"], result["verified_count"], result["unverified_count"],
    )
    return result
