from agents.base import BaseAgent
from schemas.papers import PaperMeta
from schemas.search import SearchRequest, SearchResponse, SearchResult
from services.search.arxiv import ArxivClient
from services.search.crossref import CrossrefClient
from services.search.ranking import rank_items
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
        sources = set(req.sources or ["semantic_scholar", "arxiv", "crossref"])

        items: list[PaperMeta] = []
        if "semantic_scholar" in sources:
            items.extend(self.client.search(req.query, req.limit))
        if "arxiv" in sources:
            items.extend(self.arxiv.search(req.query, req.limit))
        if "crossref" in sources:
            items.extend(self.crossref.search(req.query, req.limit))

        # post-filter by year
        if req.year_from is not None:
            items = [i for i in items if (i.year or 0) >= req.year_from]
        if req.year_to is not None:
            items = [i for i in items if (i.year or 0) <= req.year_to]

        # dedup by DOI, else by normalized title
        seen_doi: set[str] = set()
        seen_title: set[str] = set()
        deduped: list[PaperMeta] = []
        for item in items:
            doi = normalize_doi(item.doi) if item.doi else None
            title = normalize_title(item.title or "")
            key = doi or title
            if not key:
                continue
            if doi:
                if doi in seen_doi:
                    continue
                seen_doi.add(doi)
            else:
                if title in seen_title:
                    continue
                seen_title.add(title)
            deduped.append(item)

        ranked = rank_items(deduped)
        result = SearchResult(
            query=req.query,
            items=ranked[: req.limit],
            sources=req.sources,
            year_from=req.year_from,
            year_to=req.year_to,
        )
        return SearchResponse(result=result).model_dump()
