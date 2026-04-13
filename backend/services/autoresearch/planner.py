from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

from schemas.autoresearch import (
    AutoResearchProjectFlowContextRead,
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
from services.llm.response_utils import get_message_content


PROMPT_PATH = "backend/prompts/autoresearch/planner/v0.1.2.md"


class ResearchPlanner:
    def _topic_title(self, topic: str) -> str:
        cleaned = " ".join(topic.split()).strip().rstrip(".")
        if not cleaned:
            return "Executable Benchmark Study"
        return cleaned[0].upper() + cleaned[1:]

    def _fallback_title(self, topic: str, task_family: TaskFamily) -> str:
        topic_title = self._topic_title(topic)
        if task_family == "ir_reranking":
            return f"{topic_title}: Lightweight Retrieval Signals"
        if task_family == "tabular_classification":
            return f"{topic_title}: Stable Tabular Baselines"
        if task_family == "llm_evaluation":
            return f"{topic_title}: LLM Prompting Strategy Comparison"
        return f"{topic_title}: Lightweight Lexical Baselines"

    def _is_generic_title(self, title: str | None) -> bool:
        normalized = " ".join((title or "").split()).strip().lower()
        if not normalized:
            return True
        generic_prefixes = (
            "compact retrieval signal study",
            "compact stability signal study",
            "compact benchmark study",
            "executable benchmark study",
        )
        return normalized.startswith(generic_prefixes)

    def _benchmark_scope_phrase(
        self,
        benchmark_name: str | None,
        benchmark_description: str | None,
        benchmark_labels: list[str] | None,
    ) -> str:
        label_phrase = (
            f" covering labels {{{', '.join(benchmark_labels)}}}"
            if benchmark_labels
            else ""
        )
        if benchmark_name and benchmark_description:
            return f"`{benchmark_name}` ({benchmark_description}){label_phrase}"
        if benchmark_name:
            return f"`{benchmark_name}`{label_phrase}"
        if benchmark_description:
            return f"the selected benchmark ({benchmark_description}){label_phrase}"
        if benchmark_labels:
            return f"the selected benchmark with labels {{{', '.join(benchmark_labels)}}}"
        return "the selected benchmark"

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
        project_context: AutoResearchProjectFlowContextRead | None = None,
        benchmark_name: str | None = None,
        benchmark_description: str | None = None,
        benchmark_labels: list[str] | None = None,
    ) -> ResearchPlan:
        literature_phrase = self._literature_method_phrase(literature)
        benchmark_scope = self._benchmark_scope_phrase(
            benchmark_name,
            benchmark_description,
            benchmark_labels,
        )
        project_summary = project_context.summary if project_context is not None else ""
        title = self._fallback_title(topic, task_family)
        if task_family == "ir_reranking":
            method = "a lexical rarity-aware reranker backed by overlap baselines"
            questions = [
                f"Can a lightweight lexical reranker recover the relevant document on {benchmark_scope}?",
                "Do rarity-aware query terms improve reciprocal rank over plain overlap scoring?",
            ]
            hypothesis = [
                "IDF-weighted overlap will outperform both random order and plain lexical overlap.",
                "Adding bigram agreement will further improve ranking precision on focused CS queries.",
            ]
            contributions = [
                f"A reproducible reranking benchmark scoped to {benchmark_scope}.",
                "A multi-round reranking search trace with overlap, IDF, and bigram lexical variants.",
                "An artifact-grounded analysis of the executed ranking variants.",
            ]
        elif task_family == "tabular_classification":
            method = "a scaled linear classifier backed by simple rule based baselines"
            questions = [
                f"Can a small scaled linear model separate the labels exposed by {benchmark_scope}?",
                "How much does feature scaling contribute on a low resource tabular benchmark?",
            ]
            hypothesis = [
                "Feature scaling will improve the perceptron style learner over unscaled training.",
                "A learned linear model will beat majority and threshold heuristics on held out runs.",
            ]
            contributions = [
                f"A reproducible tabular benchmark scoped to {benchmark_scope}.",
                "A baseline comparison between majority, threshold, and lightweight linear models.",
                "An artifact-grounded analysis of the executed experiment variants.",
            ]
        elif task_family == "llm_evaluation":
            method = "a prompting strategy comparison backed by zero-shot and few-shot baselines"
            questions = [
                f"How do different prompting strategies compare on {benchmark_scope}?",
                "Does providing few-shot examples improve classification over zero-shot approaches?",
            ]
            hypothesis = [
                "Few-shot prompting with label-relevant examples will outperform zero-shot classification.",
                "Rule-based keyword matching will provide a competitive baseline for structured tasks.",
            ]
            contributions = [
                f"A reproducible LLM evaluation benchmark scoped to {benchmark_scope}.",
                "A comparison between zero-shot, few-shot, and rule-based classification strategies.",
                "An artifact-grounded analysis of prompting strategy effectiveness.",
            ]
        else:
            method = "a lexical probabilistic classifier backed by majority and keyword baselines"
            questions = [
                f"Can lightweight lexical modeling classify short snippets from {benchmark_scope} without external libraries?",
                f"Does a probabilistic model outperform simple keyword rules on {benchmark_scope}?",
            ]
            hypothesis = [
                "Naive Bayes style lexical modeling will exceed majority and keyword baselines.",
                "Reducing the vocabulary will hurt macro F1, showing that broad lexical coverage matters.",
            ]
            contributions = [
                f"A compact benchmark scoped to {benchmark_scope} for automated experimentation.",
                "A reproducible comparison between majority, keyword, and probabilistic lexical models.",
                "An artifact-grounded analysis that reports only executed experimental evidence.",
            ]

        return ResearchPlan(
            topic=topic,
            title=title,
            task_family=task_family,
            problem_statement=(
                f"This study investigates {topic} through a deliberately small but executable "
                f"{task_family.replace('_', ' ')} benchmark centered on {benchmark_scope}. The goal is to test "
                "concrete hypotheses while keeping claims tied to preserved execution evidence."
                + (
                    f" The run also stays aligned with persisted project flow constraints: {project_summary}"
                    if project_summary
                    else ""
                )
            ),
            motivation=(
                "The topic needs an executable benchmark that is cheap enough to run repeatedly "
                "yet structured enough to support hypotheses, baselines, ablations, and "
                "a result table."
                + (
                    f" Existing project materials further constrain the study: {project_summary}"
                    if project_summary
                    else ""
                )
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
                *(
                    ["Reconcile the selected benchmark study with the persisted project template, draft, evidence, and review state."]
                    if project_summary
                    else []
                ),
            ],
            scope_limits=[
                "The study is restricted to built-in benchmark families for text classification, tabular classification, and IR reranking.",
                "The benchmark is intentionally small and does not claim broad external validity.",
                "No external datasets or large-scale training jobs are included in this study.",
                *(
                    [project_summary]
                    if project_summary
                    else []
                ),
            ],
        )

    def _portfolio_templates(self, plan: ResearchPlan) -> list[dict[str, Any]]:
        method_sentence = plan.proposed_method.rstrip(".")
        return [
            {
                "role": "primary_method",
                "diversity_axis": "highest_upside",
                "title_suffix": "Primary Method Candidate",
                "method": method_sentence,
                "rationale": (
                "Highest-upside candidate that keeps the main method, the benchmark fit, "
                "and the baseline/ablation structure aligned."
            ),
            "differentiators": [
                "Optimizes for strongest benchmark performance under the fixed execution budget.",
                "Preserves the full baseline comparison expected by the current paper writer.",
                "Best fit for the leading hypothesis in the current research plan.",
            ],
                "selection_reason": (
                    "Selected first because it best matches the plan's main hypothesis while "
                    "retaining the clearest path to an executable result table."
                ),
            },
            {
                "role": "baseline_anchor",
                "diversity_axis": "low_risk_anchor",
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
                "role": "stability_probe",
                "diversity_axis": "robustness_probe",
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
        *,
        role: str,
    ) -> list[str]:
        if not base_strategies:
            return []
        if role == "baseline_anchor":
            return list(base_strategies[:-1] or base_strategies[:1])
        if role == "stability_probe":
            if len(base_strategies) == 1:
                return list(base_strategies)
            if len(base_strategies) == 2:
                return [base_strategies[1], base_strategies[0]]
            return [base_strategies[1], base_strategies[0], *base_strategies[2:]]
        if role == "primary_method":
            return list(base_strategies)
        return list(base_strategies)

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
                "Rank candidates by expected research signal, diversity of candidate posture, "
                "benchmark fit, and reproducibility under the current execution budget before "
                "expanding to full candidate fan-out."
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
                    portfolio_role=template["role"],
                    diversity_axis=template["diversity_axis"],
                    title=f"{plan.title}: {template['title_suffix']}",
                    hypothesis=self._candidate_hypothesis(plan, index - 1),
                    proposed_method=template["method"],
                    rationale=template["rationale"],
                    planned_contributions=planned_contributions,
                    differentiators=template["differentiators"],
                    search_strategies=self._candidate_search_strategies(
                        spec.search_strategies,
                        role=template["role"],
                    ),
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
        project_context: AutoResearchProjectFlowContextRead | None = None,
        benchmark_name: str | None = None,
        benchmark_description: str | None = None,
        benchmark_labels: list[str] | None = None,
    ) -> ResearchPlan:
        literature = literature or []
        task_family = infer_task_family(topic, task_family_hint)
        fallback = self._fallback_plan(
            topic,
            task_family,
            literature,
            project_context=project_context,
            benchmark_name=benchmark_name,
            benchmark_description=benchmark_description,
            benchmark_labels=benchmark_labels,
        )
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
                            f"Benchmark context: {{'name': {benchmark_name!r}, 'description': {benchmark_description!r}, 'labels': {benchmark_labels or []!r}}}\n"
                            f"Literature context: {[item.model_dump(mode='json') for item in literature]}\n"
                            f"Project flow context: {project_context.model_dump(mode='json') if project_context is not None else None}\n"
                            "Return a JSON object for a minimal but realistic computer science "
                            "research plan."
                        ),
                    },
                ]
            )
            content = get_message_content(response)
            parsed = self._parse_json(content)
            if not parsed:
                return fallback
            parsed["topic"] = topic
            parsed["task_family"] = task_family
            parsed.setdefault("title", fallback.title)
            if self._is_generic_title(parsed.get("title")):
                parsed["title"] = fallback.title
            # Normalize LLM outputs: convert non-string fields that expect strings
            for _key in ("problem_statement", "motivation", "proposed_method"):
                _val = parsed.get(_key)
                if isinstance(_val, dict):
                    parsed[_key] = ". ".join(str(v) for v in _val.values() if v)
                elif _val is not None and not isinstance(_val, str):
                    parsed[_key] = str(_val)
                parsed.setdefault(_key, getattr(fallback, _key))
            for _list_key in ("research_questions", "hypotheses", "planned_contributions", "experiment_outline", "scope_limits"):
                _val = parsed.get(_list_key)
                if isinstance(_val, str):
                    parsed[_list_key] = [line.lstrip("- 0123456789.) ").strip() for line in _val.split("\n") if line.strip()]
                elif not isinstance(_val, list):
                    parsed[_list_key] = getattr(fallback, _list_key)
                parsed.setdefault(_list_key, getattr(fallback, _list_key))
            return ResearchPlan.model_validate(parsed)
        except Exception as exc:
            logger.warning("planner: LLM plan failed (%s), using fallback", exc)
            return fallback
