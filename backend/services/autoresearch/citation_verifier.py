"""Citation Verification Chain — ARIS pattern.

DBLP -> CrossRef -> [VERIFY] chain to verify citations are real papers.
Prevents hallucinated references in generated papers.
"""
from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

DBLP_SEARCH_URL = "https://dblp.org/search/publ/api"
CROSSREF_API_URL = "https://api.crossref.org/works"


class CitationVerifier:
    """Verify that cited papers actually exist via DBLP -> CrossRef -> [VERIFY] chain."""

    def __init__(self, timeout: float = 10.0) -> None:
        self.client = httpx.Client(timeout=timeout, follow_redirects=True)

    def verify_citation(self, title: str) -> dict:
        """Verify a single citation. Returns verification result dict.

        Chain: DBLP -> CrossRef -> mark as [VERIFY] if both fail.
        """
        result = {
            "title": title,
            "verified": False,
            "source": None,
            "bib_key": None,
            "year": None,
            "authors": None,
            "venue": None,
            "doi": None,
            "needs_manual_verify": False,
        }

        # Step 1: Try DBLP
        dblp_result = self._search_dblp(title)
        if dblp_result:
            result.update(dblp_result)
            result["verified"] = True
            result["source"] = "dblp"
            return result

        # Step 2: Try CrossRef
        crossref_result = self._search_crossref(title)
        if crossref_result:
            result.update(crossref_result)
            result["verified"] = True
            result["source"] = "crossref"
            return result

        # Step 3: Mark as needing manual verification
        result["needs_manual_verify"] = True
        result["source"] = "unverified"
        return result

    def verify_citations_batch(self, titles: list[str]) -> list[dict]:
        """Verify multiple citations."""
        return [self.verify_citation(title) for title in titles]

    def extract_citations_from_markdown(self, markdown: str) -> list[str]:
        """Extract citation titles from paper markdown.

        Handles patterns like:
        - [1] Author et al., "Title", Venue, Year.
        - - Author (Year). *Title*. Venue.
        - > Author et al. Title. Venue.
        """
        titles = []
        # Pattern: number-quoted references [N] Author, "Title", ...
        for match in re.finditer(r'\[[\d,]+\]\s*.*?"([^"]+)"', markdown):
            title = match.group(1).strip()
            if len(title) > 10:
                titles.append(title)

        # Pattern: bullet references with italicized titles
        for match in re.finditer(r'\*\*([^*]+)\*\*', markdown):
            title = match.group(1).strip()
            if len(title) > 10 and not title.startswith(("Abstract", "Introduction", "Method", "Results")):
                titles.append(title)

        # Pattern: reference section entries
        in_refs = False
        for line in markdown.splitlines():
            lower = line.lower().strip()
            if lower.startswith("## ") and "reference" in lower:
                in_refs = True
                continue
            if in_refs and lower.startswith("## "):
                in_refs = False
            if in_refs:
                # Match common reference patterns
                ref_match = re.match(r'^[\-\d.\s]+\s*(.+)', line.strip())
                if ref_match:
                    ref_text = ref_match.group(1)
                    # Try to extract quoted title
                    quoted = re.search(r'"([^"]+)"', ref_text)
                    if quoted and len(quoted.group(1)) > 10:
                        titles.append(quoted.group(1))
                    elif len(ref_text) > 20:
                        # Use first meaningful chunk
                        titles.append(ref_text[:120])

        # Deduplicate
        seen = set()
        unique = []
        for title in titles:
            normalized = title.lower().strip()
            if normalized not in seen:
                seen.add(normalized)
                unique.append(title)
        return unique

    def annotate_markdown(self, markdown: str) -> str:
        """Add [VERIFY] markers to unverified citations in markdown."""
        citations = self.extract_citations_from_markdown(markdown)
        if not citations:
            return markdown

        results = self.verify_citations_batch(citations)
        unverified = {
            r["title"] for r in results if r["needs_manual_verify"]
        }

        if not unverified:
            return markdown

        # Mark unverified references
        lines = markdown.splitlines()
        in_refs = False
        annotated = []
        for line in lines:
            lower = line.lower().strip()
            if lower.startswith("## ") and "reference" in lower:
                in_refs = True
                annotated.append(line)
                continue
            if in_refs and lower.startswith("## "):
                in_refs = False
            if in_refs:
                for title in unverified:
                    escaped = re.escape(title[:60])
                    if re.search(escaped, line, re.IGNORECASE):
                        line = line.rstrip() + " **[VERIFY]**"
                        break
            annotated.append(line)
        return "\n".join(annotated)

    def _search_dblp(self, title: str) -> dict | None:
        """Search DBLP for a paper by title."""
        try:
            resp = self.client.get(DBLP_SEARCH_URL, params={
                "q": title[:100],
                "format": "json",
                "h": 3,
            })
            if resp.status_code != 200:
                return None

            data = resp.json()
            hits = data.get("result", {}).get("hits", {}).get("hit", [])
            if not hits:
                return None

            for hit in hits if isinstance(hits, list) else [hits]:
                info = hit.get("info", {})
                hit_title = info.get("title", "")
                if self._titles_match(title, hit_title):
                    authors_raw = info.get("authors", {}).get("author", [])
                    if isinstance(authors_raw, dict):
                        authors_raw = [authors_raw]
                    authors = [a.get("text", "") for a in authors_raw] if authors_raw else []
                    return {
                        "bib_key": info.get("key", ""),
                        "year": info.get("year"),
                        "authors": authors[:5],
                        "venue": info.get("venue"),
                        "doi": info.get("doi"),
                    }
        except Exception as exc:
            logger.debug("dblp search failed for '%s': %s", title[:50], exc)
        return None

    def _search_crossref(self, title: str) -> dict | None:
        """Search CrossRef for a paper by title."""
        try:
            resp = self.client.get(CROSSREF_API_URL, params={
                "query.title": title[:100],
                "rows": 3,
                "select": "title,author,published-print,published-online,DOI,container-title",
            })
            if resp.status_code != 200:
                return None

            items = resp.json().get("message", {}).get("items", [])
            for item in items:
                hit_titles = item.get("title", [])
                if not hit_titles:
                    continue
                hit_title = hit_titles[0]
                if self._titles_match(title, hit_title):
                    authors_raw = item.get("author", [])
                    authors = [
                        f"{a.get('family', '')}, {a.get('given', '')}"
                        for a in authors_raw[:5]
                    ]
                    date = item.get("published-print") or item.get("published-online") or {}
                    parts = date.get("date-parts", [[""]])
                    year = str(parts[0][0]) if parts and parts[0] else None
                    venue = item.get("container-title", [""])[0] if item.get("container-title") else None
                    return {
                        "doi": item.get("DOI"),
                        "year": year,
                        "authors": authors,
                        "venue": venue,
                    }
        except Exception as exc:
            logger.debug("crossref search failed for '%s': %s", title[:50], exc)
        return None

    def _titles_match(self, a: str, b: str) -> bool:
        """Fuzzy title match: normalize and compare."""
        def normalize(t: str) -> str:
            return re.sub(r"[^a-z0-9]", "", t.lower())

        na = normalize(a)
        nb = normalize(b)
        if not na or not nb:
            return False
        if na == nb:
            return True
        # Allow one to be a prefix of the other (truncated titles)
        if na in nb or nb in na:
            return True
        # Simple overlap check
        shorter = min(len(na), len(nb))
        if shorter > 20 and na[:shorter] == nb[:shorter]:
            return True
        return False
