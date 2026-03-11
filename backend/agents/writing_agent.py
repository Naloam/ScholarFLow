from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from services.llm.client import chat
from services.llm.prompting import load_prompt


PROMPT_PATH = "backend/prompts/writing/v0.1.0.md"


class WritingAgent(BaseAgent):
    name = "writing"

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
        if not content:
            content = (
                f"# {topic}\n\n## Abstract\n[NEEDS_EVIDENCE]\n\n## Introduction\n"
                "[NEEDS_EVIDENCE]\n\n## Related Work\n[NEEDS_EVIDENCE]\n\n"
                "## Method\n[NEEDS_EVIDENCE]\n\n## Conclusion\n[NEEDS_EVIDENCE]\n\n## References\n"
            )
        claims = []
        for line in content.splitlines():
            if line.strip().lower().startswith("claim:"):
                claims.append({"claim": line.split(":", 1)[1].strip(), "evidence_refs": []})
        return {"content": content, "claims": claims}
