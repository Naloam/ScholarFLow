from __future__ import annotations

from uuid import uuid4

from agents.base import BaseAgent
from schemas.agents import Chunk, ReadResult
from services.parsing.tei import extract_paragraphs


def chunk_text(paragraphs: list[str], max_chars: int = 1000) -> list[str]:
    chunks: list[str] = []
    current = ""
    for p in paragraphs:
        if len(current) + len(p) + 1 > max_chars and current:
            chunks.append(current.strip())
            current = p
        else:
            current = (current + "\n" + p).strip()
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
