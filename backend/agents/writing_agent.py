from __future__ import annotations

from typing import Any
import json
import re

from agents.base import BaseAgent
from services.llm.client import chat
from services.llm.prompting import load_prompt


PROMPT_PATH = "backend/prompts/writing/v0.1.0.md"


class WritingAgent(BaseAgent):
    name = "writing"

    def _extract_claims(self, content: str) -> list[dict[str, Any]]:
        claims: list[dict[str, Any]] = []
        for line in content.splitlines():
            if line.strip().lower().startswith("claim:"):
                claims.append({"claim": line.split(":", 1)[1].strip(), "evidence_refs": []})
        if claims:
            return claims

        # fallback: pick a few sentences from abstract/introduction
        sentences = re.split(r"(?<=[.!?。！？])\s+", content.strip())
        for sent in sentences:
            if 20 <= len(sent) <= 200:
                claims.append({"claim": sent.strip(), "evidence_refs": []})
            if len(claims) >= 5:
                break
        return claims

    def _parse_json(self, text: str) -> dict[str, Any] | None:
        if not text:
            return None
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        topic = payload.get("topic") or "Untitled Topic"
        scope = payload.get("scope") or ""
        papers = payload.get("papers") or []
        template = payload.get("template") or ""

        prompt = load_prompt(PROMPT_PATH)
        context = {
            "topic": topic,
            "scope": scope,
            "papers": papers,
            "template": template,
        }
        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nGenerate a structured draft.",
            },
        ]
        resp = chat(messages)
        content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = self._parse_json(content)
        if parsed and isinstance(parsed, dict):
            draft_content = parsed.get("content") or ""
            claims = parsed.get("claims") or []
            if not isinstance(claims, list):
                claims = []
            return {"content": draft_content, "claims": claims}

        if not content:
            content = (
                f"# {topic}\n\n## Abstract\n[NEEDS_EVIDENCE]\n\n## Introduction\n"
                "[NEEDS_EVIDENCE]\n\n## Related Work\n[NEEDS_EVIDENCE]\n\n"
                "## Method\n[NEEDS_EVIDENCE]\n\n## Conclusion\n[NEEDS_EVIDENCE]\n\n## References\n"
            )
        claims = self._extract_claims(content)
        return {"content": content, "claims": claims}
