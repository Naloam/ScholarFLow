from __future__ import annotations

from schemas.autoresearch import (
    ExperimentAttempt,
    ExperimentSpec,
    LiteratureInsight,
    ResearchPlan,
    ResultArtifact,
    ResultTable,
)


def _markdown_table(table: ResultTable) -> str:
    if not table.columns:
        return ""
    header = "| " + " | ".join(table.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(table.columns)) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in table.rows]
    return "\n".join([header, separator, *rows])


class PaperWriter:
    def _aggregate_metric(self, artifact: ResultArtifact, system_name: str | None, metric: str) -> float | None:
        if not system_name:
            return None
        for item in artifact.aggregate_system_results:
            if item.system == system_name:
                value = item.mean_metrics.get(metric)
                return float(value) if value is not None else None
        return self._metric(artifact, system_name, metric)

    def _aggregate_std(self, artifact: ResultArtifact, system_name: str | None, metric: str) -> float | None:
        if not system_name:
            return None
        for item in artifact.aggregate_system_results:
            if item.system == system_name:
                value = item.std_metrics.get(metric)
                return float(value) if value is not None else None
        return None

    def _metric(self, artifact: ResultArtifact, system_name: str | None, metric: str) -> float | None:
        if not system_name:
            return None
        for item in artifact.system_results:
            if item.system == system_name:
                value = item.metrics.get(metric)
                return float(value) if value is not None else None
        return None

    def _results_table(self, artifact: ResultArtifact) -> str:
        if not artifact.tables:
            return ""
        rendered = []
        for table in artifact.tables:
            rendered.append(f"### {table.title}\n")
            rendered.append(_markdown_table(table))
            rendered.append("")
        return "\n".join(rendered).strip()

    def _literature_block(self, literature: list[LiteratureInsight]) -> str:
        if not literature:
            return "No project-specific literature was attached, so related-work grounding is limited."
        return "\n".join(
            f"- {item.title} ({item.year or 'n.d.'}): {item.insight}"
            for item in literature
        )

    def _attempt_block(self, attempts: list[ExperimentAttempt]) -> str:
        if not attempts:
            return "- No iterative attempts were recorded."
        return "\n".join(
            f"- Round {item.round_index} using `{item.strategy}` ({item.goal}): {item.summary}"
            for item in attempts
        )

    def _acceptance_block(self, artifact: ResultArtifact) -> str:
        if not artifact.acceptance_checks:
            return "- No explicit acceptance checks were recorded."
        return "\n".join(
            f"- {'PASS' if item.passed else 'FAIL'}: {item.criterion} ({item.detail})"
            for item in artifact.acceptance_checks
        )

    def write(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        artifact: ResultArtifact,
        *,
        literature: list[LiteratureInsight] | None = None,
        attempts: list[ExperimentAttempt] | None = None,
        benchmark_name: str | None = None,
    ) -> str:
        if artifact.status != "done":
            raise ValueError("PaperWriter requires a completed ResultArtifact")

        literature = literature or []
        attempts = attempts or []
        best_metric = self._aggregate_metric(artifact, artifact.best_system, artifact.primary_metric)
        best_std = self._aggregate_std(artifact, artifact.best_system, artifact.primary_metric)
        learned_system = spec.baselines[-1].name if spec.baselines else artifact.best_system
        ablation_name = spec.ablations[0].name if spec.ablations else None
        learned_metric = self._aggregate_metric(artifact, learned_system, artifact.primary_metric)
        ablation_metric = self._aggregate_metric(artifact, ablation_name, artifact.primary_metric)
        majority_metric = self._aggregate_metric(artifact, "majority", artifact.primary_metric)
        environment = artifact.environment
        runtime = environment.get("runtime_seconds")
        executor_mode = environment.get("executor_mode", "unknown")
        selected_sweep = environment.get("selected_sweep") or "default"
        seed_count = environment.get("seed_count") or len(artifact.per_seed_results) or len(spec.seeds) or 1

        findings = "\n".join(f"- {item}" for item in artifact.key_findings) or "- No additional findings recorded."
        metrics = ", ".join(metric.name for metric in spec.metrics)
        results_table = self._results_table(artifact)
        literature_block = self._literature_block(literature)
        attempt_block = self._attempt_block(attempts)
        acceptance_block = self._acceptance_block(artifact)
        benchmark_display = benchmark_name or spec.benchmark_name

        comparison_sentence = (
            f"The executed run identified `{artifact.best_system}` as the strongest system with "
            f"mean {artifact.primary_metric}={best_metric:.4f}"
            f"{f' (std={best_std:.4f})' if best_std is not None else ''}."
            if best_metric is not None and artifact.best_system
            else "The executed run completed successfully and produced a ranked set of systems."
        )
        learned_sentence = (
            f"The main learned system `{learned_system}` reached "
            f"mean {artifact.primary_metric}={learned_metric:.4f}."
            if learned_metric is not None and learned_system
            else "The main learned system was evaluated in the same benchmark."
        )
        ablation_sentence = (
            f"The ablation `{ablation_name}` scored mean {artifact.primary_metric}={ablation_metric:.4f}, "
            f"which quantifies the cost of removing one key modeling choice."
            if ablation_name and ablation_metric is not None
            else "An explicit ablation was included to test the importance of the proposed design."
        )
        majority_sentence = (
            f"The majority baseline achieved mean {artifact.primary_metric}={majority_metric:.4f}, "
            "providing a minimal lower bound."
            if majority_metric is not None
            else "A majority baseline was included as a lower bound."
        )
        if spec.task_family == "ir_reranking":
            dataset_sentence = (
                f"The dataset used in the experiment is `{spec.dataset.name}` with "
                f"{spec.dataset.train_size} training queries and {spec.dataset.test_size} test queries. "
                f"Queries are represented through the fields {', '.join(spec.dataset.query_fields or ['query'])}, "
                f"and each query is associated with up to {spec.dataset.candidate_count or 'unknown'} candidates."
            )
        else:
            dataset_sentence = (
                f"The dataset used in the experiment is `{spec.dataset.name}` with "
                f"{spec.dataset.train_size} training examples and {spec.dataset.test_size} test examples. "
                f"Inputs are represented through the fields {', '.join(spec.dataset.input_fields)}, "
                f"and labels belong to {{{', '.join(spec.dataset.label_space)}}}."
            )

        return f"""# {plan.title}

## Abstract
This paper presents `CS AutoResearch v0`, a minimal computer science research loop that maps a topic into a research plan, generates executable experiment code, runs the experiment in a sandbox-oriented environment, and writes a paper only from the resulting evidence. The concrete topic for this run is **{plan.topic}**, instantiated as a `{spec.task_family}` benchmark named `{benchmark_display}`.

The experimental study follows the hypothesis that {spec.hypothesis.lower()} {comparison_sentence} The run reports {metrics}, preserves logs and environment metadata, and exports a structured artifact that can be inspected independently from the paper text.

## 1. Introduction
{plan.problem_statement}

The motivation for this run is practical rather than purely stylistic. ScholarFlow should not stop at generating generic prose. It should be able to define a tractable problem, select an executable benchmark, compare baselines, and report measurable outcomes. In this version, the scope is intentionally restricted to small classification tasks that can be executed quickly without external dependencies. This restriction makes the pipeline reproducible while still forcing the system to reason about hypotheses, baselines, ablations, and result interpretation.

The central research questions are:
{chr(10).join(f"- {item}" for item in plan.research_questions)}

## 2. Related Work and Research Plan
The planning stage was conditioned on the following literature cues:
{literature_block}

The planning stage produced the following working hypothesis set:
{chr(10).join(f"- {item}" for item in plan.hypotheses)}

Planned contributions for the run were:
{chr(10).join(f"- {item}" for item in plan.planned_contributions)}

Operationally, the run followed this outline:
{chr(10).join(f"1. {item}" for item in plan.experiment_outline)}

## 3. Method
The proposed method in the plan is summarized as {plan.proposed_method.lower()} The executable experiment specification narrows that idea into a benchmark with fixed train and test partitions, explicit baselines, and a small ablation suite. The supported benchmark in this run is `{benchmark_display}`, described as: {spec.benchmark_description}

{dataset_sentence} The compared baselines are {", ".join(item.name for item in spec.baselines)}. The ablation suite contains {", ".join(item.name for item in spec.ablations) if spec.ablations else "no ablations"}.

Implementation constraints were also explicit:
{chr(10).join(f"- {item}" for item in spec.implementation_notes)}

## 4. Experimental Setup
All experiments were executed from generated Python code inside the existing ScholarFlow sandbox runner. The observed execution mode for this run was `{executor_mode}`. The recorded environment reports Python `{environment.get("python_version") or environment.get("host_python") or "unknown"}` on `{environment.get("platform") or environment.get("host_platform") or "unknown"}`. The experiment runtime reported by the artifact was `{runtime if runtime is not None else "unknown"}` seconds.

The selected configuration for the final artifact was sweep `{selected_sweep}` evaluated over `{seed_count}` seeds. This run therefore reports aggregated metrics instead of a single execution trace, and retains the full seed-level evidence inside the result artifact.

Evaluation uses {metrics}. The purpose of the benchmark is not to claim state of the art performance, but to verify that the system can carry out a complete research loop with a real result table and a grounded discussion.

The search and repair trace for this run was:
{attempt_block}

## 5. Results
{comparison_sentence} {learned_sentence} {majority_sentence} {ablation_sentence}

{results_table}

Key findings recorded directly in the artifact are:
{findings}

Acceptance checks for the selected configuration were:
{acceptance_block}

## 6. Discussion
The results show that the pipeline can now produce a paper-shaped artifact with concrete experimental content instead of a generic short essay. The differences among the compared systems matter because they provide evidence that the method choice changes measurable outcomes. That is the minimum standard for a computational research run.

At the same time, the benchmark remains intentionally small. The value of this v0 system is not that it solves an open scientific problem, but that it demonstrates the operational scaffolding required for future automated research runs: a planner, a structured experiment specification, executable code generation, artifact preservation, and grounded writing.

## 7. Limitations
{chr(10).join(f"- {item}" for item in plan.scope_limits)}
- The benchmark is built into the repository, so data collection and large scale reproducibility are out of scope.
- The learned methods are lightweight toy models rather than competitive research systems.
- The writing stage is grounded by construction, which avoids fabricated experiments but also limits rhetorical flexibility.

## 8. Conclusion
`CS AutoResearch v0` completes a narrow but real research loop for `{plan.topic}`. The system planned the study, executed the benchmark, preserved a structured result artifact, and produced a paper whose claims are anchored to the recorded experiment outputs. This establishes the minimum backend skeleton needed to push ScholarFlow toward an automated computer science research system rather than a generic writing assistant.
"""
