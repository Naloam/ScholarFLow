from __future__ import annotations

import json
import re
from typing import Any

from agents.base import BaseAgent
from services.llm.client import chat
from services.llm.prompting import load_prompt
from services.drafts.analysis import needs_evidence_count


PROMPT_PATH = "backend/prompts/review/v0.1.0.md"


class ReviewAgent(BaseAgent):
    name = "review"

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
        draft = payload.get("draft") or ""
        references = payload.get("references") or []

        prompt = load_prompt(PROMPT_PATH)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"draft:\n{draft}\n\nreferences:\n{references}"},
        ]
        resp = chat(messages)
        content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = self._parse_json(content)
        if parsed:
            return parsed

        missing = needs_evidence_count(draft)
        base = 6 if missing == 0 else 4
        scores = {
            "originality": base,
            "importance": base,
            "evidence_support": max(1, base - min(3, missing)),
            "soundness": base,
            "clarity": base,
            "value": base,
            "contextualization": base,
        }
        suggestions = [
            "补充关键断言的证据来源并标记引用位置 [NEEDS_EVIDENCE]",
            "强化相关工作对比，明确本研究贡献点",
            "完善方法细节与实验/验证设计",
        ]
        return {"scores": scores, "suggestions": suggestions}
