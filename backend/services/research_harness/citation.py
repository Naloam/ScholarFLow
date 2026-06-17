"""Citation verification (V2.1, plan §6 contract completion — Session 7).

The V2 contract (plan §6) is: *every claim in ``paper/draft.md`` must be backed
by ``metrics.json`` OR ``literature/papers.jsonl``.* Session 6 covered the
metric/overlap half; this module covers the **citation** half — each ``[n]`` /
``[Author, Year]`` / ``**"Title"**`` / reference-list entry must resolve to a
paper that was actually retrieved, else it is marked
``[UNVERIFIED: citation "…" not found in retrieved literature]``.

Design rules (goal_session7.md Step 2, hard constraints):

- **Offline by default.** The offline path matches citation titles against the
  local ``papers.jsonl`` only — no network, deterministic, safe in CI.
- **Live path is opt-in.** ``verify_citations_live`` (DBLP → CrossRef) is
  imported + called ONLY under ``live_research`` (``SCHOLARFLOW_OFFLINE_LLM != "1"``),
  and even then wrapped so a network failure never breaks the audit. CI / the
  default suite never touches it.
- **New code isolation.** This is a fresh implementation in ``research_harness/``;
  the FROZEN ``services/autoresearch/citation_verifier.py`` is untouched (we port
  its ``_titles_match`` + extraction regexes, not the class).

Outputs are plain dicts so the Auditor can fold citation verdicts into the same
``claims`` ledger as metric-backed claims (with ``category: "citation"``).
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

# Offline mode gate (matches services/llm/client.py). When OFFLINE_LLM=1 the live
# DBLP/CrossRef path is never imported — guarantees CI / fixture runs stay network-free.
def _is_offline() -> bool:
    return os.getenv("SCHOLARFLOW_OFFLINE_LLM", "1") == "1"


# --------------------------------------------------------------------------- #
# Title normalization + fuzzy match (port of citation_verifier._titles_match)
# --------------------------------------------------------------------------- #

_NORM_RE = re.compile(r"[^a-z0-9]")


def _normalize_title(title: str) -> str:
    """Lowercase, strip everything except alphanumerics — the comparison form."""
    return _NORM_RE.sub("", (title or "").lower())


def titles_match(a: str, b: str) -> bool:
    """Fuzzy title equality: exact / containment / long shared prefix on the
    normalized form.

    Ported from ``citation_verifier.CitationVerifier._titles_match`` so citation
    matching agrees with the frozen verifier's notion of "same paper". Titles are
    long, so the containment path is safe against accidental short-string hits in
    practice (callers also drop candidates shorter than ``_MIN_TITLE_LEN``).
    """
    na = _normalize_title(a)
    nb = _normalize_title(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # One title contained in the other (handles truncation / subtitle trimming).
    if na in nb or nb in na:
        return True
    # Long shared prefix (≈ the verifier's >20-char prefix rule).
    shorter = min(len(na), len(nb))
    if shorter > 20 and na[:shorter] == nb[:shorter]:
        return True
    return False


# --------------------------------------------------------------------------- #
# Citation extraction
# --------------------------------------------------------------------------- #

# A citation worth verifying must carry (or resolve to) a real title. Drop
# degenerate fragments that would produce noisy false matches.
_MIN_TITLE_LEN = 10

# Reference-section headings we recognize (case-insensitive "## references" etc.).
_REF_HEADING_RE = re.compile(r"^#{1,6}\s*(references|bibliography|works cited)\b\s*$", re.IGNORECASE)
_ANY_HEADING_RE = re.compile(r"^#{1,6}\s")

# In-text numeric / author-year markers: [1], [1,2], [1-3], [Smith, 2023], [Smith et al., 2023].
_INLINE_MARKER_RE = re.compile(r"\[((?:\d+(?:\s*[-,]\s*\d+)+|\d+(?:\s*,\s*\d+)*|[A-Z][A-Za-z'\-]+(?:\s+et\s+al\.?)?,\s*\d{4}[a-z]?))\]")
# A quoted title, optionally bolded: **"Title"** / "Title" / *"Title"*.
_QUOTED_TITLE_RE = re.compile(r'\*{0,2}"([^"]+)"\*{0,2}')
# Italic title in a reference line: *Title*. or _Title_.
_ITALIC_TITLE_RE = re.compile(r"(?:^|\s)\*([^*\n]{%d,}?)\*(?:[.,\s]|$)" % _MIN_TITLE_LEN)

_SECTION_NAMES_TO_SKIP = (
    "abstract", "introduction", "method", "methods", "results", "result",
    "discussion", "conclusion", "related work", "background", "experiments",
    "evaluation", "experiment", "setup", "implementation",
)


def _split_refs_section(text: str) -> tuple[str, str]:
    """Return (body, references_text). The references section is everything from
    the first ``## References``-style heading to the next heading (or EOF)."""
    lines = (text or "").splitlines()
    in_refs = False
    body: list[str] = []
    refs: list[str] = []
    for line in lines:
        if _ANY_HEADING_RE.match(line):
            if _REF_HEADING_RE.match(line.strip()):
                in_refs = True
                continue
            if in_refs:
                in_refs = False
        (refs if in_refs else body).append(line)
    return "\n".join(body), "\n".join(refs)


def _clean_title(raw: str) -> str:
    title = raw.strip().strip("*_\"'").strip()
    # Trim a trailing period and any venue/year tail after the first sentence boundary
    # only if it obviously continues past the title (heuristic, conservative).
    return title


def _is_plausible_title(title: str) -> bool:
    t = title.strip()
    if len(t) < _MIN_TITLE_LEN:
        return False
    low = t.lower()
    if low in _SECTION_NAMES_TO_SKIP:
        return False
    # Drop lines that are clearly a section heading echo.
    if t.endswith(":") and len(t) < 40:
        return False
    return True


def _extract_reference_titles(refs_text: str) -> list[dict[str, str]]:
    """Parse reference-list entries into ``{marker, raw_title}``.

    Each non-empty line is one entry. The title is taken from the first quoted,
    italicized, or sentence-boundary chunk; the marker is the leading ``[n]`` /
    ``n.`` if present (falls back to the line itself).
    """
    out: list[dict[str, str]] = []
    for line in refs_text.splitlines():
        stripped = line.strip()
        if not stripped or len(stripped) < _MIN_TITLE_LEN:
            continue
        marker = stripped[:32]
        # Leading [n] or n.
        m_lead = re.match(r"^(?:\[(\d+(?:[-,]\s*\d+)*)\]|(\d+)\.)\s*(.+)$", stripped)
        title: str
        if m_lead:
            marker = f"[{m_lead.group(1) or m_lead.group(2)}]"
            title = _title_from_entry(m_lead.group(3))
        else:
            title = _title_from_entry(stripped)
        title = _clean_title(title)
        if _is_plausible_title(title):
            out.append({"marker": marker, "raw_title": title})
    return out


def _title_from_entry(entry: str) -> str:
    """Best-effort title extraction from a single reference entry body."""
    quoted = _QUOTED_TITLE_RE.search(entry)
    if quoted and len(quoted.group(1)) >= _MIN_TITLE_LEN:
        return quoted.group(1)
    italic = _ITALIC_TITLE_RE.search(entry)
    if italic and len(italic.group(1)) >= _MIN_TITLE_LEN:
        return italic.group(1)
    # Fallback: an author list ends at the first period followed by a capitalized
    # word, so split there and pick the LONGEST plausible chunk. Titles are almost
    # always the longest sentence in a reference entry, which also sidesteps the
    # "J. Fabricated." trap where a single-name initial reads as a sentence boundary.
    chunks = re.split(r"(?<=[.])\s+(?=[A-Z(])", entry)
    plausible = [c for c in chunks if _is_plausible_title(c)]
    if plausible:
        return max(plausible, key=len)
    return chunks[-1] if chunks else entry


def _extract_inline_titles(body: str) -> list[dict[str, str]]:
    """In-text ``**"Title"**`` / ``"Title"`` citations in the body (not refs)."""
    out: list[dict[str, str]] = []
    for m in _QUOTED_TITLE_RE.finditer(body):
        title = _clean_title(m.group(1))
        if _is_plausible_title(title):
            out.append({"marker": m.group(0)[:32], "raw_title": title})
    return out


def _inline_marker_tokens(body: str) -> list[str]:
    """All in-text ``[n]`` / ``[Author, Year]`` tokens (for the 'no reference entry'
    diagnostic — not for title matching by themselves)."""
    seen: list[str] = []
    for m in _INLINE_MARKER_RE.finditer(body):
        token = m.group(0)
        if token not in seen:
            seen.append(token)
    return seen


def extract_citations(draft_text: str) -> list[dict[str, str]]:
    """Extract every citation worth verifying from a draft.

    Returns ``[{marker, raw_title}, ...]`` deduplicated by normalized title.
    Sources, in priority order: the reference-list entries (canonical targets),
    then in-text ``"Title"`` citations. Pure regex; no network.

    The ``marker`` is a short display string (e.g. ``[1]`` or the head of the
    line) so the Auditor can point a human at where the citation lives.
    """
    body, refs_text = _split_refs_section(draft_text)
    citations = _extract_reference_titles(refs_text)
    citations.extend(_extract_inline_titles(body))

    # Dedup by normalized title (a paper cited [1] inline + listed once in refs
    # is one citation, not two).
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for c in citations:
        key = _normalize_title(c["raw_title"])
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(c)
    return unique


# --------------------------------------------------------------------------- #
# Offline verification against papers.jsonl
# --------------------------------------------------------------------------- #


def _paper_titles(papers: list[dict[str, Any]]) -> list[str]:
    titles: list[str] = []
    for p in papers or []:
        if not isinstance(p, dict):
            continue
        title = p.get("title")
        if isinstance(title, str) and title.strip():
            titles.append(title.strip())
    return titles


def verify_citations(
    draft_text: str,
    papers: list[dict[str, Any]],
    *,
    live: bool | None = None,
) -> list[dict[str, Any]]:
    """Verify every extracted citation against ``papers.jsonl`` titles (offline).

    Each result: ``{marker, raw_title, verdict, source, matched_title, reason}``
    where ``verdict`` ∈ ``{"verified", "unverified"}``. Unmatched citations get
    ``reason='citation "…" not found in retrieved literature'``.

    When ``live`` is True (or auto-enabled under ``live_research`` —
    ``SCHOLARFLOW_OFFLINE_LLM != "1"``), citations that missed the local
    literature get a second chance via DBLP/CrossRef; matches are upgraded to
    ``verified`` with ``source`` ∈ ``{"dblp", "crossref"}``. The live path imports
    ``httpx`` lazily and swallows network errors, so it can never break the audit.
    """
    citations = extract_citations(draft_text)
    if not citations:
        return []

    titles = _paper_titles(papers)
    live_enabled = (not _is_offline()) if live is None else bool(live)

    results: list[dict[str, Any]] = []
    live_upgrades: dict[str, dict[str, Any]] = {}
    unmatched: list[str] = []
    for c in citations:
        raw_title = c["raw_title"]
        hit = next((t for t in titles if titles_match(raw_title, t)), None)
        if hit is not None:
            results.append(_citation_verdict(c, "verified", "literature", hit, ""))
            continue
        if live_enabled:
            unmatched.append(raw_title)
        else:
            results.append(_citation_verdict(c, "unverified", "none", None, _unmatched_reason(raw_title)))

    if live_enabled and unmatched:
        try:
            live_upgrades = verify_citations_live(unmatched)
        except Exception as exc:  # noqa: BLE001 — network must never break the audit
            logger.warning("live citation verification failed (falling back to offline): %s", exc)
            live_upgrades = {}
        for c in citations:
            raw_title = c["raw_title"]
            upgrade = live_upgrades.get(_normalize_title(raw_title)) or live_upgrades.get(raw_title)
            if upgrade and upgrade.get("verdict") == "verified":
                results.append(_citation_verdict(c, "verified", upgrade.get("source", "live"),
                                                 upgrade.get("matched_title"), ""))
            elif any(_normalize_title(t) == _normalize_title(raw_title) for t in unmatched):
                results.append(_citation_verdict(c, "unverified", "none", None, _unmatched_reason(raw_title)))
    return results


def _unmatched_reason(raw_title: str) -> str:
    return f'citation "{raw_title}" not found in retrieved literature'


def _citation_verdict(
    citation: dict[str, str],
    verdict_kind: str,
    source: str,
    matched_title: str | None,
    reason: str,
) -> dict[str, Any]:
    return {
        "marker": citation.get("marker", ""),
        "raw_title": citation.get("raw_title", ""),
        "verdict": verdict_kind,
        "source": source,
        "matched_title": matched_title,
        "reason": reason,
    }


# --------------------------------------------------------------------------- #
# Live verification (DBLP → CrossRef) — live_research ONLY
# --------------------------------------------------------------------------- #

DBLP_SEARCH_URL = "https://dblp.org/search/publ/api"
CROSSREF_API_URL = "https://api.crossref.org/works"


def verify_citations_live(titles: list[str]) -> dict[str, dict[str, Any]]:
    """DBLP → CrossRef chain for titles that missed the local literature.

    Returns ``{normalized_or_raw_title: {verdict, source, matched_title, ...}}``.
    ONLY called under ``live_research``; imports ``httpx`` lazily so the offline
    import path stays network-free. Any exception is caught by the caller.
    """
    import httpx  # lazy: keeps offline import side-effect-free

    out: dict[str, dict[str, Any]] = {}
    client = httpx.Client(timeout=10.0, follow_redirects=True)
    try:
        for title in titles:
            dblp = _search_dblp(client, title)
            if dblp is not None:
                out[title] = {"verdict": "verified", "source": "dblp", "matched_title": dblp}
                continue
            crossref = _search_crossref(client, title)
            if crossref is not None:
                out[title] = {"verdict": "verified", "source": "crossref", "matched_title": crossref}
            else:
                out[title] = {"verdict": "unverified", "source": "none", "matched_title": None}
    finally:
        client.close()
    return out


def _search_dblp(client: Any, title: str) -> str | None:
    try:
        resp = client.get(DBLP_SEARCH_URL, params={"q": title[:100], "format": "json", "h": 3})
        if resp.status_code != 200:
            return None
        hits = resp.json().get("result", {}).get("hits", {}).get("hit", []) or []
        for hit in hits if isinstance(hits, list) else [hits]:
            info = (hit or {}).get("info", {}) or {}
            hit_title = info.get("title", "") or ""
            if titles_match(title, hit_title):
                return hit_title
    except Exception as exc:  # noqa: BLE001
        logger.debug("dblp search failed for '%s': %s", title[:50], exc)
    return None


def _search_crossref(client: Any, title: str) -> str | None:
    try:
        resp = client.get(
            CROSSREF_API_URL,
            params={"query.title": title[:100], "rows": 3},
        )
        if resp.status_code != 200:
            return None
        items = resp.json().get("message", {}).get("items", []) or []
        for item in items:
            hit_titles = item.get("title", []) or []
            if hit_titles and titles_match(title, hit_titles[0]):
                return hit_titles[0]
    except Exception as exc:  # noqa: BLE001
        logger.debug("crossref search failed for '%s': %s", title[:50], exc)
    return None


__all__ = [
    "titles_match",
    "extract_citations",
    "verify_citations",
    "verify_citations_live",
    "DBLP_SEARCH_URL",
    "CROSSREF_API_URL",
]
