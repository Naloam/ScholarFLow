from agents.base import BaseAgent
from schemas.search import SearchRequest, SearchResponse, SearchResult
from services.search.semantic_scholar import SemanticScholarClient


class SearchAgent(BaseAgent):
    name = "search"

    def __init__(self) -> None:
        self.client = SemanticScholarClient()

    def run(self, payload: dict) -> dict:
        req = SearchRequest(**payload)
        items = self.client.search(req.query, req.limit)
        result = SearchResult(query=req.query, items=items)
        return SearchResponse(result=result).model_dump()
