from __future__ import annotations

import json
import re
from typing import Any

from schemas.autoresearch import LiteratureInsight, ResearchPlan, TaskFamily
from services.autoresearch.benchmarks import infer_task_family
from services.llm.client import chat
from services.llm.prompting import load_prompt


PROMPT_PATH = "backend/prompts/autoresearch/planner/v0.1.0.md"


class ResearchPlanner:
    def _literature_method_phrase(self, literature: list[LiteratureInsight]) -> str:
        method_hints = [item.method_hint for item in literature if item.method_hint]
        if not method_hints:
            return ""
        return " ".join(method_hints[:2])

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

    def _fallback_plan(
        self,
        topic: str,
        task_family: TaskFamily,
        literature: list[LiteratureInsight],
    ) -> ResearchPlan:
        literature_phrase = self._literature_method_phrase(literature)
        if task_family == "tabular_classification":
            title = f"AutoResearch v0: Lightweight Stability Prediction for {topic}"
            method = "a scaled linear classifier backed by simple rule based baselines"
            questions = [
                "Can a small scaled linear model separate stable and unstable training runs?",
                "How much does feature scaling contribute on a low resource tabular benchmark?",
            ]
            hypothesis = [
                "Feature scaling will improve the perceptron style learner over unscaled training.",
                "A learned linear model will beat majority and threshold heuristics on held out runs.",
            ]
            contributions = [
                "A reproducible toy benchmark for training run stability classification.",
                "A baseline comparison between majority, threshold, and lightweight linear models.",
                "A grounded paper generated only from executed experiment artifacts.",
            ]
        else:
            title = f"AutoResearch v0: Lightweight Topic Classification for {topic}"
            method = "a lexical probabilistic classifier backed by majority and keyword baselines"
            questions = [
                "Can lightweight lexical modeling classify short CS abstracts without external libraries?",
                "Does a probabilistic model outperform simple keyword rules on a small benchmark?",
            ]
            hypothesis = [
                "Naive Bayes style lexical modeling will exceed majority and keyword baselines.",
                "Reducing the vocabulary will hurt macro F1, showing that broad lexical coverage matters.",
            ]
            contributions = [
                "A compact benchmark of CS abstract snippets for automated experimentation.",
                "A reproducible comparison between majority, keyword, and probabilistic lexical models.",
                "A grounded paper that reports only executed experimental evidence.",
            ]

        return ResearchPlan(
            topic=topic,
            title=title,
            task_family=task_family,
            problem_statement=(
                f"This run studies {topic} through a deliberately small but executable "
                f"{task_family.replace('_', ' ')} benchmark so ScholarFlow can complete an "
                "end to end computer science research loop from planning to paper writing."
            ),
            motivation=(
                "The system needs a benchmark that is cheap enough to execute in a sandbox yet "
                "structured enough to support hypotheses, baselines, ablations, and a result table."
            ),
            proposed_method=(
                f"We evaluate {method}."
                + (f" The proposal is conditioned on literature cues: {literature_phrase}" if literature_phrase else "")
            ),
            research_questions=questions,
            hypotheses=(
                hypothesis
                + [item.gap_hint for item in literature[:2] if item.gap_hint]
            ),
            planned_contributions=contributions,
            experiment_outline=[
                "Instantiate a built in benchmark and split it into train and test partitions.",
                "Run majority and task specific heuristic baselines.",
                "Run the lightweight learned method and one ablation.",
                "Summarize metrics, logs, and environment metadata into a structured artifact.",
                "Use project literature to justify the chosen benchmark and method family.",
            ],
            scope_limits=[
                "v0 only supports built in text and tabular classification benchmarks.",
                "The benchmark is intentionally small and does not claim broad external validity.",
                "No external datasets or large scale training jobs are attempted in this version.",
            ],
        )

    def plan(
        self,
        topic: str,
        task_family_hint: TaskFamily | None = None,
        literature: list[LiteratureInsight] | None = None,
    ) -> ResearchPlan:
        literature = literature or []
        task_family = infer_task_family(topic, task_family_hint)
        fallback = self._fallback_plan(topic, task_family, literature)
        try:
            prompt = load_prompt(PROMPT_PATH)
            response = chat(
                [
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Topic: {topic}\n"
                            f"Task family: {task_family}\n"
                            f"Literature context: {[item.model_dump(mode='json') for item in literature]}\n"
                            "Return a JSON object for a minimal but realistic computer science "
                            "research plan."
                        ),
                    },
                ]
            )
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = self._parse_json(content)
            if not parsed:
                return fallback
            parsed["topic"] = topic
            parsed["task_family"] = task_family
            parsed.setdefault("title", fallback.title)
            parsed.setdefault("problem_statement", fallback.problem_statement)
            parsed.setdefault("motivation", fallback.motivation)
            parsed.setdefault("proposed_method", fallback.proposed_method)
            parsed.setdefault("research_questions", fallback.research_questions)
            parsed.setdefault("hypotheses", fallback.hypotheses)
            parsed.setdefault("planned_contributions", fallback.planned_contributions)
            parsed.setdefault("experiment_outline", fallback.experiment_outline)
            parsed.setdefault("scope_limits", fallback.scope_limits)
            return ResearchPlan.model_validate(parsed)
        except Exception:
            return fallback
