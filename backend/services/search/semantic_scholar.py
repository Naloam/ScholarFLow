from typing import List

import httpx

from config.settings import settings
from schemas.papers import PaperMeta


class SemanticScholarClient:
    base_url = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.semantic_scholar_api_key

    def search(self, query: str, limit: int = 10) -> List[PaperMeta]:
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        params = {
            "query": query,
            "limit": limit,
            "fields": "title,authors,year,abstract,doi,url",
        }

        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{self.base_url}/paper/search", params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        items: list[PaperMeta] = []
        for raw in data.get("data", []):
            authors = [a.get("name", "") for a in raw.get("authors", []) if a.get("name")]
            items.append(
                PaperMeta(
                    title=raw.get("title", ""),
                    authors=authors,
                    year=raw.get("year"),
                    abstract=raw.get("abstract"),
                    doi=raw.get("doi"),
                    url=raw.get("url"),
                    source="semantic_scholar",
                )
            )

        return items
