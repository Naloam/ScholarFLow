from __future__ import annotations

from pathlib import Path

import httpx

from config.settings import settings


def parse_fulltext(pdf_path: Path) -> str | None:
    url = f"{settings.grobid_url}/api/processFulltextDocument"
    with httpx.Client(timeout=60) as client:
        with pdf_path.open("rb") as f:
            files = {"input": (pdf_path.name, f, "application/pdf")}
            resp = client.post(url, files=files)
            if resp.status_code != 200:
                return None
            return resp.text
