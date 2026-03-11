from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from services.llm.client import chat
from services.llm.prompting import load_prompt


PROMPT_PATH = "backend/prompts/tutor/v0.1.0.md"


class TutorAgent(BaseAgent):
    name = "tutor"

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        stage = payload.get("stage") or "outline"
        topic = payload.get("topic") or ""
        context = payload.get("context") or ""
        prompt = load_prompt(PROMPT_PATH)
        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Stage: {stage}\nTopic: {topic}\nContext: {context}",
            },
        ]
        resp = chat(messages)
        content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"stage": stage, "guidance": content}
