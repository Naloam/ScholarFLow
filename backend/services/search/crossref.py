from __future__ import annotations

from typing import List

import httpx

from schemas.papers import PaperMeta


class CrossrefClient:
    base_url = "https://api.crossref.org/works"

    def search(self, query: str, limit: int = 10) -> List[PaperMeta]:
        params = {"query": query, "rows": limit}
        with httpx.Client(timeout=20) as client:
            resp = client.get(self.base_url, params=params)
            resp.raise_for_status()
            data = resp.json()

        items: list[PaperMeta] = []
        for msg in data.get("message", {}).get("items", []) or []:
            title = (msg.get("title") or [None])[0]
            authors = []
            for a in msg.get("author", []) or []:
                given = a.get("given", "")
                family = a.get("family", "")
                name = (given + " " + family).strip()
                if name:
                    authors.append(name)
            year = None
            for key in ("published-print", "published-online", "issued"):
                parts = msg.get(key, {}).get("date-parts", [])
                if parts and parts[0]:
                    year = parts[0][0]
                    break
            items.append(
                PaperMeta(
                    title=title,
                    authors=authors,
                    year=year,
                    abstract=None,
                    doi=msg.get("DOI"),
                    url=msg.get("URL"),
                    source="crossref",
                )
            )
        return items
