from __future__ import annotations

from datetime import UTC, datetime

from schemas.autoresearch import (
    AutoResearchClaimEvidenceEntryRead,
    AutoResearchClaimEvidenceMatrixRead,
    AutoResearchClaimEvidenceRefRead,
    AutoResearchFigurePlanItemRead,
    AutoResearchFigurePlanRead,
    AutoResearchPaperPipelineArtifactsRead,
    AutoResearchPaperPlanRead,
    AutoResearchPaperPlanSectionRead,
    AutoResearchPaperRevisionStateRead,
    ConfidenceIntervalSummary,
    ExperimentAttempt,
    ExperimentSpec,
    HypothesisCandidate,
    LiteratureInsight,
    PortfolioSummary,
    ResearchPlan,
    ResearchProgram,
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


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class PaperWriter:
    def _literature_citation_span(self, literature: list[LiteratureInsight], *, limit: int = 2) -> str:
        if not literature:
            return ""
        count = min(len(literature), max(1, limit))
        labels = ", ".join(str(index) for index in range(1, count + 1))
        return f"[{labels}]"

    def _literature_context_sentence(self, literature: list[LiteratureInsight]) -> str:
        if not literature:
            return ""
        return (
            f"Recent retrieved work {self._literature_citation_span(literature)} anchored the benchmark framing and "
            "preserved explicit related-work context for the selected hypothesis."
        )

    def _discussion_context_sentence(self, literature: list[LiteratureInsight]) -> str:
        if not literature:
            return ""
        return (
            f"The preserved literature context {self._literature_citation_span(literature)} makes the contribution "
            "boundary explicit: this run is a bounded executable check rather than a state-of-the-art claim."
        )

    def _conclusion_context_sentence(self, literature: list[LiteratureInsight]) -> str:
        if not literature:
            return ""
        return (
            f"Relative to the retrieved literature context {self._literature_citation_span(literature)}, the primary "
            "contribution here is the end-to-end evidence trail and not a claim of algorithmic novelty."
        )

    def _reference_entry(self, index: int, item: LiteratureInsight) -> str:
        year = str(item.year) if item.year is not None else "n.d."
        source = (item.source or "unknown source").replace("_", " ")
        paper_id = f" id={item.paper_id}." if item.paper_id else ""
        return f"[{index}] {item.title}. {source}, {year}.{paper_id}"

    def _references_block(self, literature: list[LiteratureInsight]) -> str:
        if not literature:
            return ""
        return "\n".join(
            self._reference_entry(index + 1, item)
            for index, item in enumerate(literature)
        )

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

    def _aggregate_confidence_interval(
        self,
        artifact: ResultArtifact,
        system_name: str | None,
        metric: str,
    ) -> ConfidenceIntervalSummary | None:
        if not system_name:
            return None
        for item in artifact.aggregate_system_results:
            if item.system == system_name:
                return item.confidence_intervals.get(metric)
        return None

    def _format_confidence_interval(self, interval: ConfidenceIntervalSummary | None) -> str | None:
        if interval is None:
            return None
        level_percent = int(round(interval.level * 100))
        return f"{level_percent}% CI [{interval.lower:.4f}, {interval.upper:.4f}]"

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
            (
                f"- [{index + 1}] {item.title} ({item.year or 'n.d.'}; {(item.source or 'unknown source').replace('_', ' ')}): "
                + " ".join(
                    part
                    for part in (
                        item.insight,
                        item.method_hint,
                        item.gap_hint,
                    )
                    if part
                )
            )
            for index, item in enumerate(literature)
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

    def _significance_block(self, artifact: ResultArtifact) -> str:
        if not artifact.significance_tests:
            return "- No paired significance comparisons were recorded."
        return "\n".join(
            (
                f"- {item.scope}: `{item.candidate}` vs `{item.comparator}` on `{item.metric}` "
                f"(effect={item.effect_size:.4f}, adjusted p="
                f"{(item.adjusted_p_value if item.adjusted_p_value is not None else item.p_value):.4f}, "
                f"{'significant' if item.significant else 'not significant'})."
            )
            for item in artifact.significance_tests
        )

    def _negative_results_block(self, artifact: ResultArtifact) -> str:
        if not artifact.negative_results:
            return "- No explicit negative results were recorded."
        return "\n".join(f"- {item.detail}" for item in artifact.negative_results)

    def _failure_block(self, artifact: ResultArtifact) -> str:
        if not artifact.failed_trials:
            return "- No failed seed or sweep configurations were recorded."
        return "\n".join(
            f"- {item.scope} failure in sweep `{item.sweep_label}`"
            f"{f' seed {item.seed}' if item.seed is not None else ''}: "
            f"{item.category} ({item.summary})"
            for item in artifact.failed_trials
        )

    def _anomaly_block(self, artifact: ResultArtifact) -> str:
        if not artifact.anomalous_trials:
            return "- No anomalous trials were flagged."
        return "\n".join(f"- {item.detail}" for item in artifact.anomalous_trials)

    def _portfolio_block(
        self,
        program: ResearchProgram | None,
        portfolio: PortfolioSummary | None,
        candidates: list[HypothesisCandidate],
    ) -> str:
        if not portfolio or not candidates:
            return "Portfolio planning has not been enabled for this run."
        selected = next(
            (candidate for candidate in candidates if candidate.id == portfolio.selected_candidate_id),
            None,
        )
        lines = [
            f"- Rank {candidate.rank}: `{candidate.title}` ({candidate.status}) - {candidate.rationale}"
            for candidate in candidates
        ]
        if selected is not None:
            selected_reason = selected.selection_reason or portfolio.decision_summary
            if selected_reason and selected_reason[-1] not in ".!?":
                selected_reason = f"{selected_reason}."
            selected_sentence = f"The execution focus was `{selected.title}` because {selected_reason}"
        else:
            selected_sentence = portfolio.decision_summary
        benchmark_clause = (
            f" on benchmark `{program.benchmark_name}`"
            if program is not None and program.benchmark_name
            else ""
        )
        return (
            f"Portfolio planning generated {len(candidates)} ranked candidates{benchmark_clause}.\n"
            f"{selected_sentence}\n"
            f"{portfolio.decision_summary}\n"
            + "\n".join(lines)
        )

    def _acceptance_counts(self, artifact: ResultArtifact) -> tuple[int, int]:
        total = len(artifact.acceptance_checks)
        passed = sum(1 for item in artifact.acceptance_checks if item.passed)
        return passed, total

    def _claim_entries(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        artifact: ResultArtifact,
        *,
        literature: list[LiteratureInsight],
        attempts: list[ExperimentAttempt],
        portfolio: PortfolioSummary | None,
        candidates: list[HypothesisCandidate],
    ) -> list[AutoResearchClaimEvidenceEntryRead]:
        best_metric = self._aggregate_metric(artifact, artifact.best_system, artifact.primary_metric)
        passed_acceptance, total_acceptance = self._acceptance_counts(artifact)
        selected_candidate = next(
            (candidate for candidate in candidates if portfolio and candidate.id == portfolio.selected_candidate_id),
            candidates[0] if candidates else None,
        )

        entries: list[AutoResearchClaimEvidenceEntryRead] = [
            AutoResearchClaimEvidenceEntryRead(
                claim_id="claim_problem_scope",
                category="problem",
                section_hint="Introduction",
                claim=plan.problem_statement,
                support_status="supported",
                evidence=[
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="plan",
                        label="Problem statement",
                        detail=plan.problem_statement,
                    ),
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="plan",
                        label="Research questions",
                        detail="; ".join(plan.research_questions) or "No research questions were recorded.",
                    ),
                ],
            ),
            AutoResearchClaimEvidenceEntryRead(
                claim_id="claim_method_selection",
                category="method",
                section_hint="Method",
                claim=(
                    f"The selected candidate `{selected_candidate.title}` operationalizes the run hypothesis."
                    if selected_candidate is not None
                    else f"The executable study operationalizes the run hypothesis: {spec.hypothesis}"
                ),
                support_status="supported",
                evidence=[
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="plan",
                        label="Proposed method",
                        detail=plan.proposed_method,
                    ),
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="portfolio",
                        label="Portfolio decision",
                        detail=(
                            portfolio.decision_summary
                            if portfolio is not None
                            else "No portfolio summary was persisted."
                        ),
                    ),
                ],
            ),
        ]

        result_evidence = [
            AutoResearchClaimEvidenceRefRead(
                source_kind="artifact",
                label="Artifact summary",
                detail=artifact.summary,
            ),
            AutoResearchClaimEvidenceRefRead(
                source_kind="artifact",
                label="Key findings",
                detail="; ".join(artifact.key_findings) or "No explicit key findings were recorded.",
            ),
        ]
        if artifact.tables:
            result_evidence.append(
                AutoResearchClaimEvidenceRefRead(
                    source_kind="artifact",
                    label="Result tables",
                    detail=", ".join(table.title for table in artifact.tables),
                )
            )
        if artifact.significance_tests:
            top_test = artifact.significance_tests[0]
            result_evidence.append(
                AutoResearchClaimEvidenceRefRead(
                    source_kind="artifact",
                    label="Significance evidence",
                    detail=top_test.detail,
                )
            )
        result_claim = (
            f"The selected configuration produced `{artifact.best_system}` as the strongest system "
            f"with mean {artifact.primary_metric}={best_metric:.4f}."
            if artifact.best_system and best_metric is not None
            else "The selected configuration produced a completed result artifact."
        )
        entries.append(
            AutoResearchClaimEvidenceEntryRead(
                claim_id="claim_result_summary",
                category="result",
                section_hint="Results",
                claim=result_claim,
                support_status="supported",
                evidence=result_evidence,
            )
        )

        robustness_support = "supported" if len(artifact.per_seed_results) >= 2 else "partial"
        robustness_gaps = [] if robustness_support == "supported" else ["Increase completed seed coverage for stronger aggregate claims."]
        entries.append(
            AutoResearchClaimEvidenceEntryRead(
                claim_id="claim_statistical_grounding",
                category="result",
                section_hint="Experimental Setup",
                claim=(
                    f"The run is grounded in multi-seed aggregate reporting across {len(artifact.per_seed_results) or len(spec.seeds) or 1} seeds, "
                    f"with acceptance {passed_acceptance}/{total_acceptance}."
                ),
                support_status=robustness_support,
                evidence=[
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="artifact",
                        label="Per-seed execution",
                        detail=f"{len(artifact.per_seed_results)} completed seed artifacts were preserved.",
                    ),
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="artifact",
                        label="Aggregate reporting",
                        detail=f"{len(artifact.aggregate_system_results)} aggregate system summaries and {len(artifact.significance_tests)} significance comparisons were recorded.",
                    ),
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="artifact",
                        label="Acceptance checks",
                        detail=f"{passed_acceptance}/{total_acceptance} acceptance checks passed.",
                    ),
                ],
                gaps=robustness_gaps,
            )
        )

        context_support = "supported" if literature else "unsupported"
        context_gaps = [] if literature else ["Attach retrieved literature so related-work and novelty framing stay grounded."]
        context_evidence = [
            AutoResearchClaimEvidenceRefRead(
                source_kind="literature",
                label=item.title,
                detail=" ".join(part for part in (item.insight, item.method_hint, item.gap_hint) if part),
                locator=item.paper_id,
            )
            for item in literature[:3]
        ]
        if not context_evidence:
            context_evidence.append(
                AutoResearchClaimEvidenceRefRead(
                    source_kind="literature",
                    label="Missing literature context",
                    detail="No project-specific literature was persisted for this run.",
                )
            )
        entries.append(
            AutoResearchClaimEvidenceEntryRead(
                claim_id="claim_context_grounding",
                category="context",
                section_hint="Related Work and Research Plan",
                claim="The paper's related-work framing is grounded in persisted literature context.",
                support_status=context_support,
                evidence=context_evidence,
                gaps=context_gaps,
            )
        )

        limitation_items = list(plan.scope_limits)
        if artifact.negative_results:
            limitation_items.append(artifact.negative_results[0].detail)
        if artifact.failed_trials:
            limitation_items.append(artifact.failed_trials[0].detail)
        entries.append(
            AutoResearchClaimEvidenceEntryRead(
                claim_id="claim_limitations",
                category="limitation",
                section_hint="Limitations",
                claim="The manuscript should retain explicit scope limits, failed configurations, and negative results.",
                support_status="supported",
                evidence=[
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="plan",
                        label="Scope limits",
                        detail="; ".join(plan.scope_limits) or "No explicit scope limits were captured.",
                    ),
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="artifact",
                        label="Negative or failed outcomes",
                        detail="; ".join(limitation_items) if limitation_items else "No limitation evidence was captured.",
                    ),
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="attempts",
                        label="Repair and search trace",
                        detail=f"{len(attempts)} execution rounds were preserved for this candidate.",
                    ),
                ],
            )
        )
        return entries

    def build_claim_evidence_matrix(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        artifact: ResultArtifact,
        *,
        literature: list[LiteratureInsight] | None = None,
        attempts: list[ExperimentAttempt] | None = None,
        portfolio: PortfolioSummary | None = None,
        candidates: list[HypothesisCandidate] | None = None,
    ) -> AutoResearchClaimEvidenceMatrixRead:
        literature = literature or []
        attempts = attempts or []
        candidates = candidates or []
        entries = self._claim_entries(
            plan,
            spec,
            artifact,
            literature=literature,
            attempts=attempts,
            portfolio=portfolio,
            candidates=candidates,
        )
        unsupported_claim_count = sum(1 for item in entries if item.support_status != "supported")
        return AutoResearchClaimEvidenceMatrixRead(
            generated_at=_utcnow(),
            claim_count=len(entries),
            supported_claim_count=len(entries) - unsupported_claim_count,
            unsupported_claim_count=unsupported_claim_count,
            entries=entries,
        )

    def build_narrative_report(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        artifact: ResultArtifact,
        claim_evidence_matrix: AutoResearchClaimEvidenceMatrixRead,
        *,
        literature: list[LiteratureInsight] | None = None,
        attempts: list[ExperimentAttempt] | None = None,
        benchmark_name: str | None = None,
        program: ResearchProgram | None = None,
        portfolio: PortfolioSummary | None = None,
        candidates: list[HypothesisCandidate] | None = None,
    ) -> str:
        literature = literature or []
        attempts = attempts or []
        candidates = candidates or []
        benchmark_display = benchmark_name or spec.benchmark_name
        claim_lines = []
        for entry in claim_evidence_matrix.entries:
            evidence_lines = "\n".join(
                f"  - [{item.source_kind}] {item.label}: {item.detail}"
                for item in entry.evidence
            ) or "  - No evidence anchors recorded."
            gap_lines = "\n".join(f"  - {item}" for item in entry.gaps) if entry.gaps else "  - None."
            claim_lines.append(
                "\n".join(
                    [
                        f"### {entry.claim_id}: {entry.claim}",
                        f"- Status: {entry.support_status}",
                        f"- Section hint: {entry.section_hint}",
                        "- Evidence:",
                        evidence_lines,
                        "- Gaps:",
                        gap_lines,
                    ]
                )
            )
        open_issues = [
            gap
            for entry in claim_evidence_matrix.entries
            for gap in entry.gaps
        ]
        open_issue_block = "\n".join(f"- {item}" for item in open_issues) or "- None."
        literature_titles = "\n".join(
            f"- {item.title} ({item.year or 'n.d.'})"
            for item in literature[:5]
        ) or "- No attached literature context."
        return f"""# Narrative Report: {plan.title}

## Research Program
The run targeted `{plan.topic}` on benchmark `{benchmark_display}` and kept the work bounded to executable computer-science evidence.

Program objective:
- {(program.objective if program is not None else plan.motivation)}

## Portfolio Outcome
{self._portfolio_block(program, portfolio, candidates)}

## Evidence Summary
- Artifact summary: {artifact.summary}
- Primary metric: `{artifact.primary_metric}`
- Best system: `{artifact.best_system or 'unknown'}`
- Key findings: {"; ".join(artifact.key_findings) or "No explicit key findings recorded."}
- Search / repair rounds: {len(attempts)}

## Claim-Evidence Commitments
{chr(10).join(claim_lines)}

## Related Work Inputs
{literature_titles}

## Open Issues
{open_issue_block}
"""

    def build_paper_plan(
        self,
        plan: ResearchPlan,
        claim_evidence_matrix: AutoResearchClaimEvidenceMatrixRead,
    ) -> AutoResearchPaperPlanRead:
        sections = [
            AutoResearchPaperPlanSectionRead(
                section_id="abstract",
                title="Abstract",
                objective="Summarize the executable research loop, selected benchmark, and top-line evidence.",
                claim_ids=["claim_problem_scope", "claim_result_summary"],
                evidence_focus=["artifact.summary", "claim_evidence_matrix"],
            ),
            AutoResearchPaperPlanSectionRead(
                section_id="introduction",
                title="Introduction",
                objective="Frame the problem, motivation, and bounded research questions.",
                claim_ids=["claim_problem_scope", "claim_context_grounding"],
                evidence_focus=["plan.problem_statement", "plan.research_questions", "literature"],
            ),
            AutoResearchPaperPlanSectionRead(
                section_id="related_work",
                title="Related Work and Research Plan",
                objective="Explain the literature context, working hypotheses, and portfolio decision.",
                claim_ids=["claim_context_grounding", "claim_method_selection"],
                evidence_focus=["literature", "portfolio.decision_summary"],
            ),
            AutoResearchPaperPlanSectionRead(
                section_id="method",
                title="Method",
                objective="Describe the proposed method, baselines, and executable constraints.",
                claim_ids=["claim_method_selection"],
                evidence_focus=["plan.proposed_method", "spec"],
            ),
            AutoResearchPaperPlanSectionRead(
                section_id="results",
                title="Results",
                objective="Present the selected configuration, aggregate metrics, and statistical grounding.",
                claim_ids=["claim_result_summary", "claim_statistical_grounding"],
                evidence_focus=["artifact.tables", "artifact.significance_tests", "artifact.acceptance_checks"],
            ),
            AutoResearchPaperPlanSectionRead(
                section_id="limitations",
                title="Limitations",
                objective="Preserve scope limits, negative results, and unresolved risks.",
                claim_ids=["claim_limitations"],
                evidence_focus=["plan.scope_limits", "artifact.negative_results", "artifact.failed_trials"],
            ),
            AutoResearchPaperPlanSectionRead(
                section_id="conclusion",
                title="Conclusion",
                objective="Close with the strongest supported claims and outstanding gaps.",
                claim_ids=["claim_result_summary", "claim_limitations"],
                evidence_focus=["claim_evidence_matrix", "paper_revision_state"],
            ),
        ]
        summary = (
            f"Ground the manuscript in {claim_evidence_matrix.supported_claim_count}/{claim_evidence_matrix.claim_count} "
            "supported claim bundles before final revision."
        )
        return AutoResearchPaperPlanRead(
            generated_at=_utcnow(),
            title=plan.title,
            narrative_summary=summary,
            sections=sections,
        )

    def build_figure_plan(
        self,
        artifact: ResultArtifact,
        *,
        portfolio: PortfolioSummary | None = None,
    ) -> AutoResearchFigurePlanRead:
        items = [
            AutoResearchFigurePlanItemRead(
                figure_id=f"figure_{index + 1}",
                title=table.title,
                kind="table",
                source=f"artifact.tables.{index}",
                caption=f"Promote `{table.title}` directly from the persisted artifact into the manuscript.",
                status="ready",
            )
            for index, table in enumerate(artifact.tables)
        ]
        if portfolio is not None:
            items.append(
                AutoResearchFigurePlanItemRead(
                    figure_id="figure_portfolio_decision",
                    title="Portfolio Decision Summary",
                    kind="diagram",
                    source="portfolio.decisions",
                    caption="Summarize how the selected candidate emerged from the ranked portfolio.",
                    status="planned",
                )
            )
        return AutoResearchFigurePlanRead(
            generated_at=_utcnow(),
            items=items,
        )

    def build_paper_revision_state(
        self,
        claim_evidence_matrix: AutoResearchClaimEvidenceMatrixRead,
    ) -> AutoResearchPaperRevisionStateRead:
        open_issues = [
            gap
            for entry in claim_evidence_matrix.entries
            for gap in entry.gaps
        ]
        return AutoResearchPaperRevisionStateRead(
            generated_at=_utcnow(),
            revision_round=0,
            status="needs_review",
            open_issues=open_issues,
            completed_actions=[
                "Persisted narrative report",
                "Persisted claim-evidence matrix",
                "Persisted paper plan",
                "Persisted figure plan",
                "Rendered grounded manuscript draft",
            ],
        )

    def build_pipeline(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        artifact: ResultArtifact,
        *,
        literature: list[LiteratureInsight] | None = None,
        attempts: list[ExperimentAttempt] | None = None,
        benchmark_name: str | None = None,
        program: ResearchProgram | None = None,
        portfolio: PortfolioSummary | None = None,
        candidates: list[HypothesisCandidate] | None = None,
    ) -> AutoResearchPaperPipelineArtifactsRead:
        literature = literature or []
        attempts = attempts or []
        candidates = candidates or []
        claim_evidence_matrix = self.build_claim_evidence_matrix(
            plan,
            spec,
            artifact,
            literature=literature,
            attempts=attempts,
            portfolio=portfolio,
            candidates=candidates,
        )
        narrative_report_markdown = self.build_narrative_report(
            plan,
            spec,
            artifact,
            claim_evidence_matrix,
            literature=literature,
            attempts=attempts,
            benchmark_name=benchmark_name,
            program=program,
            portfolio=portfolio,
            candidates=candidates,
        )
        paper_plan = self.build_paper_plan(plan, claim_evidence_matrix)
        figure_plan = self.build_figure_plan(artifact, portfolio=portfolio)
        paper_revision_state = self.build_paper_revision_state(claim_evidence_matrix)
        paper_markdown = self.write(
            plan,
            spec,
            artifact,
            literature=literature,
            attempts=attempts,
            benchmark_name=benchmark_name,
            program=program,
            portfolio=portfolio,
            candidates=candidates,
            narrative_report_markdown=narrative_report_markdown,
            claim_evidence_matrix=claim_evidence_matrix,
            paper_plan=paper_plan,
            figure_plan=figure_plan,
            paper_revision_state=paper_revision_state,
        )
        return AutoResearchPaperPipelineArtifactsRead(
            narrative_report_markdown=narrative_report_markdown,
            claim_evidence_matrix=claim_evidence_matrix,
            paper_plan=paper_plan,
            figure_plan=figure_plan,
            paper_revision_state=paper_revision_state,
            paper_markdown=paper_markdown,
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
        program: ResearchProgram | None = None,
        portfolio: PortfolioSummary | None = None,
        candidates: list[HypothesisCandidate] | None = None,
        narrative_report_markdown: str | None = None,
        claim_evidence_matrix: AutoResearchClaimEvidenceMatrixRead | None = None,
        paper_plan: AutoResearchPaperPlanRead | None = None,
        figure_plan: AutoResearchFigurePlanRead | None = None,
        paper_revision_state: AutoResearchPaperRevisionStateRead | None = None,
    ) -> str:
        if artifact.status != "done":
            raise ValueError("PaperWriter requires a completed ResultArtifact")

        literature = literature or []
        attempts = attempts or []
        candidates = candidates or []
        claim_evidence_matrix = claim_evidence_matrix or self.build_claim_evidence_matrix(
            plan,
            spec,
            artifact,
            literature=literature,
            attempts=attempts,
            portfolio=portfolio,
            candidates=candidates,
        )
        paper_plan = paper_plan or self.build_paper_plan(plan, claim_evidence_matrix)
        figure_plan = figure_plan or self.build_figure_plan(artifact, portfolio=portfolio)
        paper_revision_state = paper_revision_state or self.build_paper_revision_state(claim_evidence_matrix)
        narrative_report_markdown = narrative_report_markdown or self.build_narrative_report(
            plan,
            spec,
            artifact,
            claim_evidence_matrix,
            literature=literature,
            attempts=attempts,
            benchmark_name=benchmark_name,
            program=program,
            portfolio=portfolio,
            candidates=candidates,
        )
        best_metric = self._aggregate_metric(artifact, artifact.best_system, artifact.primary_metric)
        best_std = self._aggregate_std(artifact, artifact.best_system, artifact.primary_metric)
        best_ci = self._aggregate_confidence_interval(artifact, artifact.best_system, artifact.primary_metric)
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
        literature_context_sentence = self._literature_context_sentence(literature)
        discussion_context_sentence = self._discussion_context_sentence(literature)
        conclusion_context_sentence = self._conclusion_context_sentence(literature)
        references_block = self._references_block(literature)
        attempt_block = self._attempt_block(attempts)
        acceptance_block = self._acceptance_block(artifact)
        significance_block = self._significance_block(artifact)
        negative_results_block = self._negative_results_block(artifact)
        failure_block = self._failure_block(artifact)
        anomaly_block = self._anomaly_block(artifact)
        portfolio_block = self._portfolio_block(program, portfolio, candidates)
        benchmark_display = benchmark_name or spec.benchmark_name
        plan_section_titles = ", ".join(section.title for section in paper_plan.sections)
        claim_commitments = "\n".join(
            f"- `{entry.claim_id}` ({entry.section_hint}, {entry.support_status}): {entry.claim}"
            for entry in claim_evidence_matrix.entries
        )
        figure_plan_block = "\n".join(
            f"- {item.title} [{item.kind}, {item.status}] from {item.source}: {item.caption}"
            for item in figure_plan.items
        ) or "- No figure or table promotions were planned."
        revision_issue_block = "\n".join(
            f"- {item}" for item in paper_revision_state.open_issues
        ) or "- No open revision issues were recorded at draft time."
        narrative_summary = paper_plan.narrative_summary
        best_ci_text = self._format_confidence_interval(best_ci)
        best_detail_parts = []
        if best_std is not None:
            best_detail_parts.append(f"std={best_std:.4f}")
        if best_ci_text is not None:
            best_detail_parts.append(best_ci_text)
        best_detail = f" ({'; '.join(best_detail_parts)})" if best_detail_parts else ""

        comparison_sentence = (
            f"The executed run identified `{artifact.best_system}` as the strongest system with "
            f"mean {artifact.primary_metric}={best_metric:.4f}"
            f"{best_detail}."
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

The experimental study follows the hypothesis that {spec.hypothesis.lower()} {comparison_sentence} The run reports {metrics}, preserves logs and environment metadata, and exports a structured artifact that can be inspected independently from the paper text. The writing pipeline first materialized a narrative report, claim-evidence matrix, paper plan, and figure plan; {narrative_summary.lower()}

## 1. Introduction
{plan.problem_statement}

The motivation for this run is practical rather than purely stylistic. ScholarFlow should not stop at generating generic prose. It should be able to define a tractable problem, select an executable benchmark, compare baselines, and report measurable outcomes. In this version, the scope is intentionally restricted to small classification tasks that can be executed quickly without external dependencies. This restriction makes the pipeline reproducible while still forcing the system to reason about hypotheses, baselines, ablations, and result interpretation.

{literature_context_sentence}

The central research questions are:
{chr(10).join(f"- {item}" for item in plan.research_questions)}

## 2. Related Work and Research Plan
The planning stage was conditioned on the following literature cues:
{literature_block}

The persisted narrative report summarized the drafting target as:
{narrative_summary}

The planning stage produced the following working hypothesis set:
{chr(10).join(f"- {item}" for item in plan.hypotheses)}

Planned contributions for the run were:
{chr(10).join(f"- {item}" for item in plan.planned_contributions)}

The portfolio manager currently reports:
{portfolio_block}

Operationally, the run followed this outline:
{chr(10).join(f"1. {item}" for item in plan.experiment_outline)}

The paper plan locked the manuscript into these sections before prose rendering:
- {plan_section_titles}

Claim-evidence commitments carried into manuscript drafting were:
{claim_commitments}

## 3. Method
The proposed method in the plan is summarized as {plan.proposed_method.lower()} The executable experiment specification narrows that idea into a benchmark with fixed train and test partitions, explicit baselines, and a small ablation suite. The supported benchmark in this run is `{benchmark_display}`, described as: {spec.benchmark_description}

{dataset_sentence} The compared baselines are {", ".join(item.name for item in spec.baselines)}. The ablation suite contains {", ".join(item.name for item in spec.ablations) if spec.ablations else "no ablations"}.

Implementation constraints were also explicit:
{chr(10).join(f"- {item}" for item in spec.implementation_notes)}

## 4. Experimental Setup
All experiments were executed from generated Python code inside the existing ScholarFlow sandbox runner. The observed execution mode for this run was `{executor_mode}`. The recorded environment reports Python `{environment.get("python_version") or environment.get("host_python") or "unknown"}` on `{environment.get("platform") or environment.get("host_platform") or "unknown"}`. The experiment runtime reported by the artifact was `{runtime if runtime is not None else "unknown"}` seconds.

The selected configuration for the final artifact was sweep `{selected_sweep}` evaluated over `{seed_count}` seeds. This run therefore reports aggregated metrics instead of a single execution trace, and retains the full seed-level evidence inside the result artifact.

Aggregate reporting includes mean, standard deviation, and two-sided 95% confidence intervals over the selected sweep's seed-level scores.

The statistical analysis also records paired sign-flip significance comparisons with Holm correction, preserves failed seed/sweep configurations, and keeps explicit negative-result summaries rather than only the winning configuration.

Evaluation uses {metrics}. The purpose of the benchmark is not to claim state of the art performance, but to verify that the system can carry out a complete research loop with a real result table and a grounded discussion.

The figure plan promoted the following artifact-backed visuals into the paper workflow:
{figure_plan_block}

The search and repair trace for this run was:
{attempt_block}

## 5. Results
{comparison_sentence} {learned_sentence} {majority_sentence} {ablation_sentence}

{results_table}

Key findings recorded directly in the artifact are:
{findings}

Paired significance comparisons for the selected configuration were:
{significance_block}

Negative results retained in the artifact were:
{negative_results_block}

Failure analysis for seeds and sweeps was:
{failure_block}

Anomalous trials flagged for manual inspection were:
{anomaly_block}

Acceptance checks for the selected configuration were:
{acceptance_block}

## 6. Discussion
The results show that the pipeline can now produce a paper-shaped artifact with concrete experimental content instead of a generic short essay. The differences among the compared systems matter because they provide evidence that the method choice changes measurable outcomes. Recording significance comparisons, failed configurations, and negative outcomes raises the artifact above a single best-number report and closer to a real experimental logbook.

At the same time, the benchmark remains intentionally small. The value of this v0 system is not that it solves an open scientific problem, but that it demonstrates the operational scaffolding required for future automated research runs: a planner, a structured experiment specification, executable code generation, artifact preservation, and grounded writing.

{discussion_context_sentence}

The persisted narrative report remained available during drafting to keep each section tied to explicit claims:
`{narrative_report_markdown.splitlines()[0] if narrative_report_markdown else 'Narrative report unavailable.'}`

## 7. Limitations
{chr(10).join(f"- {item}" for item in plan.scope_limits)}
- The benchmark is built into the repository, so data collection and large scale reproducibility are out of scope.
- The learned methods are lightweight toy models rather than competitive research systems.
- The writing stage is grounded by construction, which avoids fabricated experiments but also limits rhetorical flexibility.

Outstanding revision issues recorded for the next paper-improvement round were:
{revision_issue_block}

## 8. Conclusion
`CS AutoResearch v0` completes a narrow but real research loop for `{plan.topic}`. The system planned the study, executed the benchmark, preserved a structured result artifact, and produced a paper whose claims are anchored to the recorded experiment outputs. This establishes the minimum backend skeleton needed to push ScholarFlow toward an automated computer science research system rather than a generic writing assistant.

{conclusion_context_sentence}
{f"{chr(10)}## 9. References{chr(10)}{references_block}" if references_block else ""}
"""
