from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from services.llm.client import chat
from services.llm.prompting import load_prompt


PROMPT_PATH = "backend/prompts/editor/v0.1.0.md"


class EditorAgent(BaseAgent):
    name = "editor"

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        content = payload.get("content") or ""
        style = payload.get("style") or "academic"
        prompt = load_prompt(PROMPT_PATH)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Style: {style}\n\nContent:\n{content}"},
        ]
        resp = chat(messages)
        edited = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"content": edited or content}
