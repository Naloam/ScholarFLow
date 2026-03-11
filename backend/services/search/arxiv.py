from __future__ import annotations

from datetime import datetime
import xml.etree.ElementTree as ET
from typing import List

import httpx

from schemas.papers import PaperMeta


class ArxivClient:
    base_url = "http://export.arxiv.org/api/query"

    def search(self, query: str, limit: int = 10) -> List[PaperMeta]:
        params = {"search_query": f"all:{query}", "start": 0, "max_results": limit}
        with httpx.Client(timeout=20) as client:
            resp = client.get(self.base_url, params=params)
            resp.raise_for_status()
            xml = resp.text

        root = ET.fromstring(xml)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        items: list[PaperMeta] = []
        for entry in root.findall("a:entry", ns):
            title = entry.findtext("a:title", default="", namespaces=ns).strip()
            summary = entry.findtext("a:summary", default="", namespaces=ns).strip()
            authors = [
                a.findtext("a:name", default="", namespaces=ns).strip()
                for a in entry.findall("a:author", ns)
            ]
            published = entry.findtext("a:published", default="", namespaces=ns)
            year = None
            if published:
                try:
                    year = datetime.fromisoformat(published.replace("Z", "+00:00")).year
                except ValueError:
                    year = None
            entry_id = entry.findtext("a:id", default="", namespaces=ns)
            pdf_url = entry_id.replace("/abs/", "/pdf/") + ".pdf" if "/abs/" in entry_id else None

            items.append(
                PaperMeta(
                    title=title or None,
                    authors=[a for a in authors if a],
                    year=year,
                    abstract=summary or None,
                    url=entry_id or None,
                    pdf_url=pdf_url,
                    source="arxiv",
                )
            )
        return items
