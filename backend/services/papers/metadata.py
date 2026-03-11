from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

import httpx


def normalize_doi(doi: str) -> str:
    return doi.strip().lower()


def extract_arxiv_id(url: str) -> str | None:
    m = re.search(r"arxiv\.org/(abs|pdf)/([^?#]+)", url)
    if not m:
        return None
    arxiv_id = m.group(2)
    arxiv_id = arxiv_id.replace(".pdf", "")
    return arxiv_id


def strip_tags(text: str | None) -> str | None:
    if not text:
        return text
    return re.sub(r"<[^>]+>", "", text)


def fetch_crossref_by_doi(doi: str) -> dict[str, Any] | None:
    url = f"https://api.crossref.org/works/{doi}"
    with httpx.Client(timeout=20) as client:
        resp = client.get(url)
        if resp.status_code != 200:
            return None
        data = resp.json()
    msg = data.get("message", {})
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
    abstract = strip_tags(msg.get("abstract"))
    return {
        "title": title,
        "authors": authors,
        "year": year,
        "abstract": abstract,
        "doi": normalize_doi(doi),
        "url": msg.get("URL"),
        "source": "crossref",
    }


def fetch_arxiv_by_id(arxiv_id: str) -> dict[str, Any] | None:
    url = "http://export.arxiv.org/api/query"
    params = {"search_query": f"id:{arxiv_id}", "start": 0, "max_results": 1}
    with httpx.Client(timeout=20) as client:
        resp = client.get(url, params=params)
        if resp.status_code != 200:
            return None
        xml = resp.text
    root = ET.fromstring(xml)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entry = root.find("a:entry", ns)
    if entry is None:
        return None
    title = entry.findtext("a:title", default="", namespaces=ns).strip()
    summary = entry.findtext("a:summary", default="", namespaces=ns).strip()
    authors = [a.findtext("a:name", default="", namespaces=ns).strip() for a in entry.findall("a:author", ns)]
    published = entry.findtext("a:published", default="", namespaces=ns)
    year = None
    if published:
        try:
            year = datetime.fromisoformat(published.replace("Z", "+00:00")).year
        except ValueError:
            year = None
    entry_id = entry.findtext("a:id", default="", namespaces=ns)
    pdf_url = entry_id.replace("/abs/", "/pdf/") + ".pdf" if "/abs/" in entry_id else None
    return {
        "title": title or None,
        "authors": [a for a in authors if a],
        "year": year,
        "abstract": summary or None,
        "url": entry_id or None,
        "pdf_url": pdf_url,
        "source": "arxiv",
    }


def fetch_metadata(doi: str | None, url: str | None) -> dict[str, Any] | None:
    if doi:
        return fetch_crossref_by_doi(normalize_doi(doi))
    if url and "arxiv.org" in url:
        arxiv_id = extract_arxiv_id(url)
        if arxiv_id:
            return fetch_arxiv_by_id(arxiv_id)
    return None
