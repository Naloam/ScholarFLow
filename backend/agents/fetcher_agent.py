from __future__ import annotations

from pathlib import Path
from time import sleep
from uuid import uuid4

import httpx

from agents.base import BaseAgent
from schemas.agents import FetchItem, FetchResult
from services.parsing.grobid import parse_fulltext
from services.workspace import papers_dir, parsed_dir


class FetcherAgent(BaseAgent):
    name = "fetcher"

    def run(self, payload: dict) -> dict:
        items = [FetchItem(**x) for x in payload.get("items", [])]
        project_id = payload.get("project_id", "")

        results: list[FetchResult] = []
        for item in items:
            if not item.pdf_url:
                results.append(FetchResult(paper_id=item.paper_id, status="no_pdf_url"))
                continue

            pdf_dir = papers_dir(project_id)
            xml_dir = parsed_dir(project_id)
            filename = f"{item.paper_id}_{uuid4().hex}.pdf"
            pdf_path = pdf_dir / filename

            downloaded = False
            for attempt in range(3):
                try:
                    with httpx.Client(timeout=60) as client:
                        resp = client.get(item.pdf_url)
                        resp.raise_for_status()
                        pdf_path.write_bytes(resp.content)
                    downloaded = True
                    break
                except Exception:
                    sleep(0.5 * (attempt + 1))
            if not downloaded:
                results.append(FetchResult(paper_id=item.paper_id, status="download_failed"))
                continue

            xml_text = None
            for attempt in range(3):
                try:
                    xml_text = parse_fulltext(pdf_path)
                    if xml_text:
                        break
                except Exception:
                    xml_text = None
                sleep(0.5 * (attempt + 1))

            xml_path: Path | None = None
            if xml_text:
                xml_path = xml_dir / f"{item.paper_id}_{uuid4().hex}.tei.xml"
                xml_path.write_text(xml_text)
                status = "ok"
            else:
                status = "grobid_failed"

            results.append(
                FetchResult(
                    paper_id=item.paper_id,
                    pdf_path=str(pdf_path),
                    grobid_xml_path=str(xml_path) if xml_path else None,
                    status=status,
                )
            )

        return {"items": [r.model_dump() for r in results]}
