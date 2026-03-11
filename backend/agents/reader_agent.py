from __future__ import annotations

import math
import re
from uuid import uuid4

from agents.base import BaseAgent
from schemas.agents import Chunk, ReadResult
from services.embedding.embeddings import embed_texts
from services.parsing.tei import extract_paragraphs


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?。！？])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _cosine(a: list[float], b: list[float]) -> float:
    denom = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    if denom == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / denom


def chunk_text(paragraphs: list[str], max_chars: int = 1000, sim_threshold: float = 0.2) -> list[str]:
    text = "\n".join(paragraphs)
    sents = _sentences(text)
    if not sents:
        return []
    embeddings = embed_texts(sents)

    chunks: list[str] = []
    current = sents[0]
    for i in range(1, len(sents)):
        sim = _cosine(embeddings[i - 1], embeddings[i])
        if len(current) + len(sents[i]) + 1 > max_chars or sim < sim_threshold:
            chunks.append(current.strip())
            current = sents[i]
        else:
            current = (current + " " + sents[i]).strip()
    if current:
        chunks.append(current.strip())
    return chunks


class ReaderAgent(BaseAgent):
    name = "reader"

    def run(self, payload: dict) -> dict:
        paper_id = payload.get("paper_id")
        xml_path = payload.get("grobid_xml_path")
        text = payload.get("text")

        paragraphs: list[str] = []
        if xml_path:
            paragraphs = extract_paragraphs(xml_path)
        if not paragraphs and text:
            paragraphs = [text]

        chunks = [
            Chunk(chunk_id=f"ch_{uuid4().hex}", text=txt, paper_id=paper_id)
            for txt in chunk_text(paragraphs)
        ]

        return ReadResult(paper_id=paper_id, chunks=chunks).model_dump()
