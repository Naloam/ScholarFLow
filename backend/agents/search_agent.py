from agents.base import BaseAgent
from schemas.papers import PaperMeta
from schemas.search import SearchRequest, SearchResponse, SearchResult
from services.search.arxiv import ArxivClient
from services.search.crossref import CrossrefClient
from services.search.semantic_scholar import SemanticScholarClient
from services.search.utils import normalize_doi, normalize_title


class SearchAgent(BaseAgent):
    name = "search"

    def __init__(self) -> None:
        self.client = SemanticScholarClient()
        self.arxiv = ArxivClient()
        self.crossref = CrossrefClient()

    def run(self, payload: dict) -> dict:
        req = SearchRequest(**payload)
        sources = set((req.sources or ["semantic_scholar", "arxiv", "crossref"]))

        items: list[PaperMeta] = []
        if "semantic_scholar" in sources:\n            items.extend(self.client.search(req.query, req.limit))\n        if "arxiv" in sources:\n            items.extend(self.arxiv.search(req.query, req.limit))\n        if "crossref" in sources:\n            items.extend(self.crossref.search(req.query, req.limit))\n\n+        # post-filter by year\n+        if req.year_from is not None:\n            items = [i for i in items if (i.year or 0) >= req.year_from]\n+        if req.year_to is not None:\n            items = [i for i in items if (i.year or 0) <= req.year_to]\n+\n+        # dedup by DOI, else by normalized title\n+        seen_doi: set[str] = set()\n+        seen_title: set[str] = set()\n+        deduped: list[PaperMeta] = []\n+        for item in items:\n+            doi = normalize_doi(item.doi) if item.doi else None\n+            title = normalize_title(item.title or \"\")\n+            key = doi or title\n+            if not key:\n+                continue\n+            if doi:\n+                if doi in seen_doi:\n+                    continue\n+                seen_doi.add(doi)\n+            else:\n+                if title in seen_title:\n+                    continue\n+                seen_title.add(title)\n+            deduped.append(item)\n+\n+        result = SearchResult(query=req.query, items=deduped[: req.limit])\n         return SearchResponse(result=result).model_dump()
        return SearchResponse(result=result).model_dump()
