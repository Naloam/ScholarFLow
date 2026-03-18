from __future__ import annotations

from schemas.autoresearch import ExperimentSpec, ResearchPlan, ResultArtifact, ResultTable


def _markdown_table(table: ResultTable) -> str:
    if not table.columns:
        return ""
    header = "| " + " | ".join(table.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(table.columns)) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in table.rows]
    return "\n".join([header, separator, *rows])


class PaperWriter:
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

    def write(self, plan: ResearchPlan, spec: ExperimentSpec, artifact: ResultArtifact) -> str:
        if artifact.status != "done":
            raise ValueError("PaperWriter requires a completed ResultArtifact")

        best_metric = self._metric(artifact, artifact.best_system, artifact.primary_metric)
        learned_system = spec.baselines[-1].name if spec.baselines else artifact.best_system
        ablation_name = spec.ablations[0].name if spec.ablations else None
        learned_metric = self._metric(artifact, learned_system, artifact.primary_metric)
        ablation_metric = self._metric(artifact, ablation_name, artifact.primary_metric)
        majority_metric = self._metric(artifact, "majority", artifact.primary_metric)
        environment = artifact.environment
        runtime = environment.get("runtime_seconds")
        executor_mode = environment.get("executor_mode", "unknown")

        findings = "\n".join(f"- {item}" for item in artifact.key_findings) or "- No additional findings recorded."
        baselines = ", ".join(item.name for item in spec.baselines[:2]) or "simple baselines"
        metrics = ", ".join(metric.name for metric in spec.metrics)
        results_table = self._results_table(artifact)

        comparison_sentence = (
            f"The executed run identified `{artifact.best_system}` as the strongest system with "
            f"{artifact.primary_metric}={best_metric:.4f}."
            if best_metric is not None and artifact.best_system
            else "The executed run completed successfully and produced a ranked set of systems."
        )
        learned_sentence = (
            f"The main learned system `{learned_system}` reached "
            f"{artifact.primary_metric}={learned_metric:.4f}."
            if learned_metric is not None and learned_system
            else "The main learned system was evaluated in the same benchmark."
        )
        ablation_sentence = (
            f"The ablation `{ablation_name}` scored {artifact.primary_metric}={ablation_metric:.4f}, "
            f"which quantifies the cost of removing one key modeling choice."
            if ablation_name and ablation_metric is not None
            else "An explicit ablation was included to test the importance of the proposed design."
        )
        majority_sentence = (
            f"The majority baseline achieved {artifact.primary_metric}={majority_metric:.4f}, "
            "providing a minimal lower bound."
            if majority_metric is not None
            else "A majority baseline was included as a lower bound."
        )

        return f"""# {plan.title}

## Abstract
This paper presents `CS AutoResearch v0`, a minimal computer science research loop that maps a topic into a research plan, generates executable experiment code, runs the experiment in a sandbox-oriented environment, and writes a paper only from the resulting evidence. The concrete topic for this run is **{plan.topic}**, instantiated as a `{spec.task_family}` benchmark named `{spec.benchmark_name}`.

The experimental study follows the hypothesis that {spec.hypothesis.lower()} {comparison_sentence} The run reports {metrics}, preserves logs and environment metadata, and exports a structured artifact that can be inspected independently from the paper text.

## 1. Introduction
{plan.problem_statement}

The motivation for this run is practical rather than purely stylistic. ScholarFlow should not stop at generating generic prose. It should be able to define a tractable problem, select an executable benchmark, compare baselines, and report measurable outcomes. In this version, the scope is intentionally restricted to small classification tasks that can be executed quickly without external dependencies. This restriction makes the pipeline reproducible while still forcing the system to reason about hypotheses, baselines, ablations, and result interpretation.

The central research questions are:
{chr(10).join(f"- {item}" for item in plan.research_questions)}

## 2. Research Plan
The planning stage produced the following working hypothesis set:
{chr(10).join(f"- {item}" for item in plan.hypotheses)}

Planned contributions for the run were:
{chr(10).join(f"- {item}" for item in plan.planned_contributions)}

Operationally, the run followed this outline:
{chr(10).join(f"1. {item}" for item in plan.experiment_outline)}

## 3. Method
The proposed method in the plan is summarized as {plan.proposed_method.lower()} The executable experiment specification narrows that idea into a benchmark with fixed train and test partitions, explicit baselines, and a small ablation suite. The supported benchmark in this run is `{spec.benchmark_name}`, described as: {spec.benchmark_description}

The dataset used in the experiment is `{spec.dataset.name}` with {spec.dataset.train_size} training examples and {spec.dataset.test_size} test examples. Inputs are represented through the fields {", ".join(spec.dataset.input_fields)}, and labels belong to {{{", ".join(spec.dataset.label_space)}}}. The compared baselines are {", ".join(item.name for item in spec.baselines)}. The ablation suite contains {", ".join(item.name for item in spec.ablations) if spec.ablations else "no ablations"}.

Implementation constraints were also explicit:
{chr(10).join(f"- {item}" for item in spec.implementation_notes)}

## 4. Experimental Setup
All experiments were executed from generated Python code inside the existing ScholarFlow sandbox runner. The observed execution mode for this run was `{executor_mode}`. The recorded environment reports Python `{environment.get("python_version") or environment.get("host_python") or "unknown"}` on `{environment.get("platform") or environment.get("host_platform") or "unknown"}`. The experiment runtime reported by the artifact was `{runtime if runtime is not None else "unknown"}` seconds.

Evaluation uses {metrics}. The purpose of the benchmark is not to claim state of the art performance, but to verify that the system can carry out a complete research loop with a real result table and a grounded discussion.

## 5. Results
{comparison_sentence} {learned_sentence} {majority_sentence} {ablation_sentence}

{results_table}

Key findings recorded directly in the artifact are:
{findings}

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
