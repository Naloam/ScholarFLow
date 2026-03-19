from __future__ import annotations

import json
import re
from typing import Any

from schemas.autoresearch import (
    ExperimentSpec,
    HypothesisCandidate,
    LiteratureInsight,
    PortfolioSummary,
    ResearchPlan,
    ResearchProgram,
    TaskFamily,
)
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
        if task_family == "ir_reranking":
            title = f"AutoResearch v0: Lightweight Reranking for {topic}"
            method = "a lexical rarity-aware reranker backed by overlap baselines"
            questions = [
                "Can a lightweight lexical reranker recover the relevant document in short candidate lists?",
                "Do rarity-aware query terms improve reciprocal rank over plain overlap scoring?",
            ]
            hypothesis = [
                "IDF-weighted overlap will outperform both random order and plain lexical overlap.",
                "Adding bigram agreement will further improve ranking precision on focused CS queries.",
            ]
            contributions = [
                "A reproducible toy reranking benchmark for CS information retrieval.",
                "A multi-round reranking search trace with overlap, IDF, and bigram lexical variants.",
                "A grounded paper generated only from executed ranking artifacts.",
            ]
        elif task_family == "tabular_classification":
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

    def _portfolio_templates(self, plan: ResearchPlan) -> list[dict[str, Any]]:
        method_sentence = plan.proposed_method.rstrip(".")
        return [
            {
                "title_suffix": "Primary Method Candidate",
                "method": method_sentence,
                "rationale": (
                    "Highest-upside candidate that keeps the main method, the benchmark fit, "
                    "and the baseline/ablation structure aligned."
                ),
                "differentiators": [
                    "Optimizes for strongest benchmark performance under the fixed sandbox budget.",
                    "Preserves the full baseline comparison expected by the current paper writer.",
                    "Best fit for the leading hypothesis in the current research plan.",
                ],
                "selection_reason": (
                    "Selected first because it best matches the plan's main hypothesis while "
                    "retaining the clearest path to an executable result table."
                ),
            },
            {
                "title_suffix": "Baseline Anchor Candidate",
                "method": (
                    f"{method_sentence}; execution is biased toward stronger heuristic baselines "
                    "and a narrower modeling delta."
                ),
                "rationale": (
                    "Lower-risk reserve candidate that asks whether a simpler baseline-heavy "
                    "study already satisfies the objective."
                ),
                "differentiators": [
                    "Favors interpretability over upside.",
                    "Keeps the contribution small enough to isolate benchmark and labeling issues.",
                    "Serves as a reserve candidate when the primary method overfits or fails.",
                ],
                "selection_reason": (
                    "Held in reserve as the simplest fallback candidate if the main method fails "
                    "to clear acceptance checks."
                ),
            },
            {
                "title_suffix": "Stability Probe Candidate",
                "method": (
                    f"{method_sentence}; execution emphasizes robustness checks, smaller "
                    "ablations, and failure-surface inspection."
                ),
                "rationale": (
                    "Reserve candidate dedicated to stability evidence, negative results, and "
                    "ablation signal rather than peak score."
                ),
                "differentiators": [
                    "Prioritizes robustness evidence over raw objective score.",
                    "Makes later statistical-rigor work easier by foregrounding failure cases.",
                    "Acts as a backup path when the topic needs ablation-driven justification.",
                ],
                "selection_reason": (
                    "Deferred for now, but kept as the strongest follow-up candidate when the "
                    "portfolio needs deeper robustness evidence."
                ),
            },
        ]

    def _candidate_hypothesis(self, plan: ResearchPlan, index: int) -> str:
        if plan.hypotheses:
            return plan.hypotheses[min(index, len(plan.hypotheses) - 1)]
        if plan.research_questions:
            return plan.research_questions[min(index, len(plan.research_questions) - 1)]
        return plan.proposed_method

    def _candidate_search_strategies(
        self,
        base_strategies: list[str],
        rank: int,
    ) -> list[str]:
        if not base_strategies:
            return []
        if rank == 1:
            return list(base_strategies)
        if rank == 2:
            return list(base_strategies[:-1] or base_strategies[:1])
        return list(base_strategies[:1])

    def build_program(
        self,
        *,
        run_id: str,
        plan: ResearchPlan,
        benchmark_name: str | None = None,
    ) -> ResearchProgram:
        return ResearchProgram(
            id=f"{run_id}_program",
            topic=plan.topic,
            title=plan.title,
            task_family=plan.task_family,
            objective=plan.problem_statement,
            benchmark_name=benchmark_name,
            portfolio_policy=(
                "Rank candidates by expected research signal, benchmark fit, and reproducibility "
                "under the current execution budget before expanding to full candidate fan-out."
            ),
            research_questions=plan.research_questions,
            scope_limits=plan.scope_limits,
        )

    def build_portfolio(
        self,
        *,
        program: ResearchProgram,
        plan: ResearchPlan,
        spec: ExperimentSpec,
    ) -> tuple[list[HypothesisCandidate], PortfolioSummary]:
        templates = self._portfolio_templates(plan)
        candidates: list[HypothesisCandidate] = []
        for index, template in enumerate(templates, start=1):
            candidate_id = f"{program.id}_cand_{index:02d}"
            planned_contributions = [
                plan.planned_contributions[min(index - 1, len(plan.planned_contributions) - 1)]
                if plan.planned_contributions
                else "Preserve an auditable execution trace for the selected benchmark.",
                "Keep seed/sweep execution, acceptance checks, and artifact persistence intact.",
            ]
            candidates.append(
                HypothesisCandidate(
                    id=candidate_id,
                    program_id=program.id,
                    rank=index,
                    title=f"{plan.title}: {template['title_suffix']}",
                    hypothesis=self._candidate_hypothesis(plan, index - 1),
                    proposed_method=template["method"],
                    rationale=template["rationale"],
                    planned_contributions=planned_contributions,
                    differentiators=template["differentiators"],
                    search_strategies=self._candidate_search_strategies(spec.search_strategies, index),
                    status="selected" if index == 1 else "planned",
                    selection_reason=template["selection_reason"],
                )
            )

        portfolio = PortfolioSummary(
            status="planned",
            total_candidates=len(candidates),
            candidate_rankings=[candidate.id for candidate in candidates],
            selected_candidate_id=candidates[0].id if candidates else None,
            selection_policy=program.portfolio_policy,
            decision_summary=(
                f"Generated {len(candidates)} portfolio candidates and provisionally selected "
                f"`{candidates[0].title}` for execution because it best matches the current main "
                "hypothesis and execution budget."
                if candidates
                else "No portfolio candidates were generated."
            ),
        )
        return candidates, portfolio

    def candidate_plan(self, plan: ResearchPlan, candidate: HypothesisCandidate) -> ResearchPlan:
        remaining_hypotheses = [item for item in plan.hypotheses if item != candidate.hypothesis]
        return plan.model_copy(
            update={
                "proposed_method": candidate.proposed_method,
                "hypotheses": [candidate.hypothesis, *remaining_hypotheses],
                "planned_contributions": candidate.planned_contributions or plan.planned_contributions,
            }
        )

    def candidate_spec(self, spec: ExperimentSpec, candidate: HypothesisCandidate) -> ExperimentSpec:
        return spec.model_copy(
            update={
                "hypothesis": candidate.hypothesis,
                "search_strategies": candidate.search_strategies or spec.search_strategies,
            }
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
