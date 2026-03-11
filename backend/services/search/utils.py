from __future__ import annotations

import re


def normalize_doi(doi: str) -> str:
    return doi.strip().lower()


def normalize_title(title: str) -> str:
    t = re.sub(r"\s+", " ", (title or "").strip().lower())
    t = re.sub(r"[^a-z0-9 ]", "", t)
    return t
