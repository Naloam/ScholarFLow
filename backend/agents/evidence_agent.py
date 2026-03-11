from __future__ import annotations

import re
from collections import Counter

from agents.base import BaseAgent
from schemas.evidence import EvidenceItem


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def score_overlap(claim: str, chunk_text: str) -> int:
    claim_tokens = Counter(tokenize(claim))
    chunk_tokens = Counter(tokenize(chunk_text))
    return sum((claim_tokens & chunk_tokens).values())


class EvidenceAgent(BaseAgent):
    name = "evidence"

    def run(self, payload: dict) -> dict:
        claims = payload.get("claims", [])
        chunks = payload.get("chunks", [])
        project_id = payload.get("project_id")

        evidence_items: list[EvidenceItem] = []
        for claim in claims:
            best = []
            for ch in chunks:
                score = score_overlap(claim, ch.get("text", ""))
                if score > 0:
                    best.append((score, ch))
            best.sort(key=lambda x: x[0], reverse=True)
            for _, ch in best[:3]:
                evidence_items.append(
                    EvidenceItem(
                        project_id=project_id,
                        claim_text=claim,
                        paper_id=ch.get("paper_id") or "",
                        chunk_id=ch.get("chunk_id"),
                        page=ch.get("page"),
                        section=ch.get("section"),
                        snippet=(ch.get("text") or "")[:400],
                        confidence=None,
                        type=None,
                    )
                )

        return {"items": [e.model_dump() for e in evidence_items]}
