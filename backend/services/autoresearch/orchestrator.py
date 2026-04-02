from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from schemas.autoresearch import (
    AutoResearchJobAction,
    AutoResearchRunRead,
    BenchmarkSource,
    ExecutionBackendSpec,
    ExperimentAttempt,
    ExperimentSpec,
    HypothesisCandidate,
    PortfolioDecisionRecord,
    PortfolioSummary,
    ResearchPlan,
    ResultArtifact,
    TaskFamily,
)
from services.autoresearch.benchmarks import ResolvedBenchmark, build_experiment_spec
from services.autoresearch.bridge import AutoResearchExperimentBridgeService, build_bridge_state
from services.autoresearch.ingestion import resolve_benchmark
from services.autoresearch.literature_pipeline import build_fallback_literature_context, gather_literature_context
from services.autoresearch.planner import ResearchPlanner
from services.autoresearch.repair import ExperimentRepairEngine
from services.autoresearch.repository import (
    paper_bibliography_file_path,
    candidate_paper_file_path,
    claim_evidence_matrix_file_path,
    figure_plan_file_path,
    load_run,
    load_benchmark_snapshot,
    narrative_report_file_path,
    paper_compile_report_file_path,
    paper_revision_action_index_file_path,
    paper_revision_diff_file_path,
    paper_latex_file_path,
    paper_plan_file_path,
    paper_revision_state_file_path,
    paper_section_rewrite_index_file_path,
    paper_section_rewrite_packets_dir_path,
    paper_sources_dir_path,
    paper_sources_manifest_file_path,
    paper_file_path,
    save_candidate_manifest,
    save_candidate_snapshot,
    save_benchmark_snapshot,
    save_run,
)
from services.autoresearch.runner import AutoExperimentRunner
from services.autoresearch.writer import PaperWriter
from services.drafts.repository import create_draft
from services.projects.repository import set_project_status


class AutoResearchExecutionCancelled(RuntimeError):
    pass


class AutoResearchOrchestrator:
    def __init__(self) -> None:
        self.planner = ResearchPlanner()
        self.repair = ExperimentRepairEngine()
        self.runner = AutoExperimentRunner()
        self.writer = PaperWriter()

    def _attempt_goal(self, attempts: list[ExperimentAttempt], round_index: int) -> str:
        if round_index == 1:
            return "initial_run"
        if attempts and attempts[-1].status == "failed":
            return "repair_previous_failure"
        return "search_for_better_candidate"

    def _artifact_score(self, artifact: ResultArtifact) -> float:
        if artifact.objective_score is not None:
            return float(artifact.objective_score)
        if artifact.best_system:
            for item in artifact.system_results:
                if item.system == artifact.best_system:
                    value = item.metrics.get(artifact.primary_metric)
                    if value is not None:
                        return float(value)
        return float("-inf")

    def _attempt_critique(
        self,
        artifact: ResultArtifact,
        attempts: list[ExperimentAttempt],
    ) -> str:
        if artifact.status != "done":
            return "Attempt failed, so the next round should repair execution and preserve a result artifact."
        failed_acceptance = [item.criterion for item in artifact.acceptance_checks if not item.passed]
        if failed_acceptance:
            return (
                "Attempt executed successfully but missed acceptance checks: "
                + "; ".join(failed_acceptance[:2])
                + (", among others." if len(failed_acceptance) > 2 else ".")
            )
        if not attempts:
            return "First successful attempt establishes the initial objective score."
        previous = attempts[-1].artifact
        if previous is None:
            return "Previous attempt had no artifact, so this round restores executable results."
        prev_score = self._artifact_score(previous)
        current_score = self._artifact_score(artifact)
        if current_score > prev_score:
            return (
                f"Objective score improved from {prev_score:.4f} to {current_score:.4f}; "
                "keep the stronger candidate as the current best."
            )
        return (
            f"Objective score did not improve over the previous round ({prev_score:.4f} -> "
            f"{current_score:.4f}); retain the earlier best candidate."
        )

    def _selected_candidate(
        self,
        candidates: list[HypothesisCandidate],
        portfolio: PortfolioSummary | None,
    ) -> HypothesisCandidate | None:
        if portfolio and portfolio.selected_candidate_id:
            for candidate in candidates:
                if candidate.id == portfolio.selected_candidate_id:
                    return candidate
        return candidates[0] if candidates else None

    def _update_candidate(
        self,
        candidates: list[HypothesisCandidate],
        candidate_id: str | None,
        **updates,
    ) -> list[HypothesisCandidate]:
        if not candidate_id:
            return candidates
        updated: list[HypothesisCandidate] = []
        for candidate in candidates:
            if candidate.id == candidate_id:
                updated.append(candidate.model_copy(update=updates))
            else:
                updated.append(candidate)
        return updated

    def _defer_reserve_candidates(
        self,
        candidates: list[HypothesisCandidate],
        allowed_candidate_ids: set[str],
        *,
        selected_candidate_id: str | None,
    ) -> list[HypothesisCandidate]:
        deferred: list[HypothesisCandidate] = []
        for candidate in candidates:
            if candidate.id in allowed_candidate_ids:
                if candidate.status == "deferred" and not candidate.attempts and candidate.artifact is None:
                    deferred.append(
                        candidate.model_copy(
                            update={
                                "status": "selected" if candidate.id == selected_candidate_id else "planned",
                            }
                        )
                    )
                    continue
                deferred.append(candidate)
                continue
            if candidate.status in {"done", "failed"} or candidate.attempts:
                deferred.append(candidate)
                continue
            deferred.append(candidate.model_copy(update={"status": "deferred"}))
        return deferred

    def _budgeted_candidate_order(
        self,
        *,
        candidates: list[HypothesisCandidate],
        portfolio: PortfolioSummary,
        candidate_execution_limit: int | None,
    ) -> list[str]:
        candidate_order = list(portfolio.candidate_rankings) or [candidate.id for candidate in candidates]
        if candidate_execution_limit is None:
            return candidate_order
        executed_count = len(
            [candidate_id for candidate_id in portfolio.executed_candidate_ids if candidate_id in candidate_order]
        )
        effective_limit = min(len(candidate_order), max(candidate_execution_limit, executed_count))
        return candidate_order[:effective_limit]

    def _portfolio_decision_summary(
        self,
        candidate: HypothesisCandidate | None,
        artifact: ResultArtifact | None,
        attempts: list[ExperimentAttempt],
        benchmark_name: str,
    ) -> str:
        if candidate is None or artifact is None or artifact.status != "done":
            return (
                "No portfolio candidate completed successfully, so the run did not produce a "
                "winner for writing."
            )
        score = self._artifact_score(artifact)
        _, passed, total, ratio = self._acceptance_summary(artifact)
        score_fragment = (
            f"{artifact.primary_metric}={score:.4f}"
            if score != float("-inf")
            else "a completed artifact"
        )
        quality_tier = self._candidate_quality_tier(candidate)
        return (
            f"Selected `{candidate.title}` as the current portfolio winner after "
            f"{len(attempts)} execution rounds on `{benchmark_name}` with {score_fragment} and "
            f"acceptance {passed}/{total} ({ratio:.2f}); quality tier={quality_tier}."
        )

    def _acceptance_summary(self, artifact: ResultArtifact | None) -> tuple[bool, int, int, float]:
        if artifact is None or artifact.status != "done":
            return False, 0, 0, 0.0
        total = len(artifact.acceptance_checks)
        passed = sum(1 for item in artifact.acceptance_checks if item.passed)
        ratio = (passed / total) if total else 1.0
        return total == 0 or passed == total, passed, total, ratio

    def _attempt_preference_key(self, artifact: ResultArtifact | None) -> tuple[int, float, float]:
        if artifact is None or artifact.status != "done":
            return 0, 0.0, float("-inf")
        all_passed, _, _, ratio = self._acceptance_summary(artifact)
        return int(all_passed), ratio, self._artifact_score(artifact)

    def _artifact_power_ok(self, artifact: ResultArtifact | None) -> bool:
        if artifact is None or artifact.status != "done":
            return False
        power_checks = [
            item.adequately_powered
            for item in artifact.significance_tests
            if item.adequately_powered is not None
        ]
        if not power_checks:
            return True
        return all(power_checks)

    def _artifact_failure_free(self, artifact: ResultArtifact | None) -> bool:
        return artifact is not None and artifact.status == "done" and not artifact.failed_trials

    def _candidate_quality_tier(self, candidate: HypothesisCandidate) -> str:
        artifact = candidate.artifact
        if candidate.status != "done" or artifact is None or artifact.status != "done":
            return "incomplete"
        all_passed, _, _, _ = self._acceptance_summary(artifact)
        if all_passed and self._artifact_failure_free(artifact) and self._artifact_power_ok(artifact):
            return "robust"
        if all_passed and self._artifact_failure_free(artifact):
            return "complete"
        if all_passed:
            return "fragile"
        return "insufficient"

    def _candidate_sort_key(self, candidate: HypothesisCandidate) -> tuple[int, int, int, int, float, float]:
        artifact = candidate.artifact
        is_done = int(candidate.status == "done" and artifact is not None and artifact.status == "done")
        all_passed, _, _, ratio = self._acceptance_summary(artifact)
        score = candidate.score if candidate.score is not None else float("-inf")
        quality_rank = {
            "robust": 3,
            "complete": 2,
            "fragile": 1,
            "insufficient": 0,
            "incomplete": 0,
        }[self._candidate_quality_tier(candidate)]
        failure_free = int(self._artifact_failure_free(artifact))
        power_ok = int(self._artifact_power_ok(artifact)) if artifact is not None else 0
        return quality_rank, is_done, int(all_passed), failure_free + power_ok, ratio, score

    def _rank_candidates(self, candidates: list[HypothesisCandidate]) -> list[HypothesisCandidate]:
        ranked = sorted(candidates, key=self._candidate_sort_key, reverse=True)
        return [
            candidate.model_copy(update={"rank": index})
            for index, candidate in enumerate(ranked, start=1)
        ]

    def _leader_candidate(self, candidates: list[HypothesisCandidate]) -> HypothesisCandidate | None:
        ranked = self._rank_candidates(candidates)
        for candidate in ranked:
            if candidate.status == "done" and candidate.artifact is not None:
                return candidate
        return None

    def _portfolio_progress_summary(
        self,
        leader: HypothesisCandidate | None,
        *,
        executed_count: int,
        total_candidates: int,
        benchmark_name: str,
    ) -> str:
        if leader is None or leader.artifact is None:
            return (
                f"Executed {executed_count}/{total_candidates} portfolio candidates on "
                f"`{benchmark_name}`, but none has produced a successful artifact yet."
            )
        _, passed, total, ratio = self._acceptance_summary(leader.artifact)
        quality_tier = self._candidate_quality_tier(leader)
        return (
            f"Executed {executed_count}/{total_candidates} portfolio candidates on `{benchmark_name}`. "
            f"Current leader is `{leader.title}` with score {leader.score if leader.score is not None else float('-inf'):.4f} "
            f"and acceptance {passed}/{total} ({ratio:.2f}); quality tier={quality_tier}."
        )

    def _candidate_selection_reason(
        self,
        candidate: HypothesisCandidate,
        *,
        winner: HypothesisCandidate | None,
        benchmark_name: str,
    ) -> str:
        if candidate.status == "deferred":
            return (
                f"Candidate stayed in the ranked portfolio for `{benchmark_name}`, but execution was deferred "
                "before benchmarking because the run hit its candidate budget."
            )
        artifact = candidate.artifact
        if artifact is None or candidate.status != "done":
            latest_summary = candidate.attempts[-1].summary if candidate.attempts else "No execution artifact."
            return (
                f"Candidate did not complete successfully on `{benchmark_name}`. "
                f"Latest summary: {latest_summary}"
            )
        _, passed, total, ratio = self._acceptance_summary(artifact)
        score_fragment = (
            f"{artifact.primary_metric}={candidate.score:.4f}"
            if candidate.score is not None
            else "a completed artifact"
        )
        quality_tier = self._candidate_quality_tier(candidate)
        failed_configs = len(artifact.failed_trials)
        underpowered = sum(1 for item in artifact.significance_tests if item.adequately_powered is False)
        if winner is not None and candidate.id == winner.id:
            return (
                f"Won the executed portfolio on `{benchmark_name}` with {score_fragment} and "
                f"acceptance {passed}/{total} ({ratio:.2f}); quality tier={quality_tier}."
            )
        winner_fragment = (
            f"`{winner.title}` with {winner.artifact.primary_metric}={winner.score:.4f}"
            if winner is not None and winner.artifact is not None and winner.score is not None
            else "the selected winner"
        )
        tradeoff_notes: list[str] = []
        if failed_configs:
            tradeoff_notes.append(f"{failed_configs} failed config(s)")
        if underpowered:
            tradeoff_notes.append(f"{underpowered} underpowered comparison(s)")
        tradeoff_clause = (
            " Evidence was weaker due to " + ", ".join(tradeoff_notes) + "."
            if tradeoff_notes
            else ""
        )
        return (
            f"Completed on `{benchmark_name}` with {score_fragment} and acceptance "
            f"{passed}/{total} ({ratio:.2f}), but trailed {winner_fragment}; "
            f"quality tier={quality_tier}.{tradeoff_clause}"
        )

    def _apply_selection_reasons(
        self,
        candidates: list[HypothesisCandidate],
        *,
        winner: HypothesisCandidate | None,
        benchmark_name: str,
    ) -> list[HypothesisCandidate]:
        return [
            candidate.model_copy(
                update={
                    "selection_reason": self._candidate_selection_reason(
                        candidate,
                        winner=winner,
                        benchmark_name=benchmark_name,
                    )
                }
            )
            for candidate in candidates
        ]

    def _candidate_by_id(
        self,
        candidates: list[HypothesisCandidate],
        candidate_id: str,
    ) -> HypothesisCandidate | None:
        for candidate in candidates:
            if candidate.id == candidate_id:
                return candidate
        return None

    def _replace_candidate(
        self,
        candidates: list[HypothesisCandidate],
        replacement: HypothesisCandidate,
    ) -> list[HypothesisCandidate]:
        return [
            replacement if candidate.id == replacement.id else candidate
            for candidate in candidates
        ]

    def _persist_candidate(
        self,
        *,
        project_id: str,
        run_id: str,
        base_plan: ResearchPlan,
        base_spec: ExperimentSpec,
        candidate: HypothesisCandidate,
    ) -> HypothesisCandidate:
        return save_candidate_snapshot(
            project_id,
            run_id,
            candidate,
            plan=self.planner.candidate_plan(base_plan, candidate),
            spec=self.planner.candidate_spec(base_spec, candidate),
        )

    def _raise_if_cancelled(self, should_cancel: Callable[[], bool] | None) -> None:
        if should_cancel is not None and should_cancel():
            raise AutoResearchExecutionCancelled("Run canceled by user")

    def _can_resume_from_checkpoint(self, run: AutoResearchRunRead) -> bool:
        return (
            run.program is not None
            and run.plan is not None
            and run.spec is not None
            and run.portfolio is not None
            and bool(run.candidates)
        )

    def _benchmark_from_checkpoint(
        self,
        *,
        project_id: str,
        run_id: str,
    ) -> ResolvedBenchmark | None:
        payload = load_benchmark_snapshot(project_id, run_id)
        if payload is None:
            return None
        raw_source = payload.get("source")
        raw_task_family = payload.get("task_family")
        raw_benchmark_payload = payload.get("payload")
        raw_name = payload.get("benchmark_name")
        raw_description = payload.get("benchmark_description")
        if not isinstance(raw_source, dict):
            return None
        if not isinstance(raw_task_family, str):
            return None
        if not isinstance(raw_benchmark_payload, dict):
            return None
        if not isinstance(raw_name, str):
            return None
        if not isinstance(raw_description, str):
            return None
        return ResolvedBenchmark(
            source=BenchmarkSource.model_validate(raw_source),
            task_family=raw_task_family,  # type: ignore[arg-type]
            payload=raw_benchmark_payload,
            benchmark_name=raw_name,
            benchmark_description=raw_description,
        )

    def _best_attempt_from_history(
        self,
        attempts: list[ExperimentAttempt],
    ) -> ExperimentAttempt | None:
        best_attempt: ExperimentAttempt | None = None
        for attempt in attempts:
            artifact = attempt.artifact
            if artifact is None or artifact.status != "done":
                continue
            if best_attempt is None or self._attempt_preference_key(artifact) > self._attempt_preference_key(
                best_attempt.artifact
            ):
                best_attempt = attempt
        return best_attempt

    def _retry_candidate(
        self,
        candidate: HypothesisCandidate,
        *,
        selected: bool,
    ) -> HypothesisCandidate:
        return candidate.model_copy(
            update={
                "status": "selected" if selected else "planned",
                "score": None,
                "attempts": [],
                "artifact": None,
                "generated_code_path": None,
                "paper_path": None,
                "paper_markdown": None,
                "selected_round_index": None,
            }
        )

    def _retry_portfolio(
        self,
        portfolio: PortfolioSummary,
        candidates: list[HypothesisCandidate],
    ) -> PortfolioSummary:
        candidate_rankings = list(portfolio.candidate_rankings) or [candidate.id for candidate in candidates]
        selected_candidate_id = candidate_rankings[0] if candidate_rankings else None
        summary = (
            f"Retry reset the executed portfolio to rerun {len(candidate_rankings)} candidates."
            if candidate_rankings
            else "Retry reset the portfolio, but no candidates are available."
        )
        return portfolio.model_copy(
            update={
                "status": "planned",
                "candidate_rankings": candidate_rankings,
                "executed_candidate_ids": [],
                "selected_candidate_id": selected_candidate_id,
                "winning_score": None,
                "decision_summary": summary,
                "decisions": [],
            }
        )

    def _should_skip_candidate(
        self,
        candidate: HypothesisCandidate,
        *,
        execution_action: AutoResearchJobAction,
    ) -> bool:
        if execution_action == "retry":
            return False
        return candidate.status in {"done", "failed"}

    def _decision_reason(
        self,
        candidate: HypothesisCandidate,
        *,
        winner: HypothesisCandidate | None,
        benchmark_name: str,
        final: bool,
    ) -> str:
        if final:
            return self._candidate_selection_reason(
                candidate,
                winner=winner,
                benchmark_name=benchmark_name,
            )
        if candidate.status == "planned":
            return f"Pending execution on `{benchmark_name}`."
        if candidate.status == "deferred":
            return (
                f"Execution was deferred on `{benchmark_name}` because the run's candidate budget "
                "did not extend far enough down the ranked portfolio."
            )
        if candidate.status == "running":
            return f"Currently executing on `{benchmark_name}`."
        if candidate.status == "failed":
            latest_summary = candidate.attempts[-1].summary if candidate.attempts else "Execution failed."
            return f"Execution failed on `{benchmark_name}`. Latest summary: {latest_summary}"
        if candidate.status == "done" and candidate.artifact is not None:
            artifact = candidate.artifact
            _, passed, total, ratio = self._acceptance_summary(artifact)
            score_fragment = (
                f"{artifact.primary_metric}={candidate.score:.4f}"
                if candidate.score is not None
                else "a completed artifact"
            )
            leader_fragment = (
                f" Current leader: `{winner.title}`."
                if winner is not None and winner.id != candidate.id
                else ""
            )
            quality_tier = self._candidate_quality_tier(candidate)
            failure_fragment = (
                f" Failed configs={len(artifact.failed_trials)}."
                if artifact.failed_trials
                else ""
            )
            return (
                f"Completed on `{benchmark_name}` with {score_fragment} and acceptance "
                f"{passed}/{total} ({ratio:.2f}); quality tier={quality_tier}.{failure_fragment}{leader_fragment}"
            )
        return f"No structured decision is available yet for `{candidate.title}`."

    def _decision_outcome(
        self,
        candidate: HypothesisCandidate,
        *,
        winner: HypothesisCandidate | None,
        final: bool,
    ) -> str:
        if candidate.status == "failed":
            return "failed"
        if final:
            if winner is not None and candidate.id == winner.id:
                return "promoted"
            if candidate.status == "deferred":
                return "eliminated"
            if candidate.status == "done":
                return "eliminated"
            return "failed"
        if candidate.status in {"planned", "selected", "deferred"}:
            return "pending"
        if candidate.status == "running":
            return "running"
        if winner is not None and candidate.id == winner.id and candidate.status == "done":
            return "leading"
        if candidate.status == "done":
            return "running"
        return "pending"

    def _decision_criteria(
        self,
        candidate: HypothesisCandidate,
        *,
        winner: HypothesisCandidate | None,
        benchmark_name: str,
        final: bool,
    ) -> list[str]:
        artifact = candidate.artifact
        _, passed, total, ratio = self._acceptance_summary(artifact)
        criteria: list[str] = [f"benchmark={benchmark_name}", f"status={candidate.status}"]
        criteria.append(f"quality_tier={self._candidate_quality_tier(candidate)}")
        if candidate.portfolio_role:
            criteria.append(f"portfolio_role={candidate.portfolio_role}")
        if candidate.diversity_axis:
            criteria.append(f"diversity_axis={candidate.diversity_axis}")
        if candidate.score is not None and artifact is not None:
            criteria.append(f"{artifact.primary_metric}={candidate.score:.4f}")
        if total:
            criteria.append(f"acceptance={passed}/{total}")
            criteria.append(f"acceptance_ratio={ratio:.2f}")
        if candidate.status == "deferred":
            criteria.append("deferred_by_candidate_budget")
        if artifact is not None and artifact.status == "done":
            criteria.append(f"failed_configs={len(artifact.failed_trials)}")
            underpowered = sum(
                1 for item in artifact.significance_tests if item.adequately_powered is False
            )
            if artifact.significance_tests:
                criteria.append(f"underpowered_comparisons={underpowered}")
        if final and winner is not None:
            if candidate.id == winner.id:
                criteria.append("ranked_first_among_executed_candidates")
            else:
                criteria.append(f"trailed={winner.id}")
        elif winner is not None and candidate.id == winner.id and candidate.status == "done":
            criteria.append("current_leader")
        return criteria

    def _decision_records(
        self,
        candidates: list[HypothesisCandidate],
        *,
        winner: HypothesisCandidate | None,
        benchmark_name: str,
        final: bool,
    ) -> list[PortfolioDecisionRecord]:
        records: list[PortfolioDecisionRecord] = []
        for candidate in candidates:
            _, passed, total, ratio = self._acceptance_summary(candidate.artifact)
            records.append(
                PortfolioDecisionRecord(
                    candidate_id=candidate.id,
                    rank=candidate.rank,
                    status=candidate.status,
                    quality_tier=self._candidate_quality_tier(candidate),
                    outcome=self._decision_outcome(
                        candidate,
                        winner=winner,
                        final=final,
                    ),
                    executed=bool(candidate.attempts),
                    selected=winner is not None and candidate.id == winner.id,
                    objective_score=candidate.score,
                    acceptance_passed=passed,
                    acceptance_total=total,
                    acceptance_ratio=ratio,
                    compared_to_candidate_id=(
                        winner.id if winner is not None and winner.id != candidate.id else None
                    ),
                    criteria=self._decision_criteria(
                        candidate,
                        winner=winner,
                        benchmark_name=benchmark_name,
                        final=final,
                    ),
                    reason=self._decision_reason(
                        candidate,
                        winner=winner,
                        benchmark_name=benchmark_name,
                        final=final,
                    ),
                )
            )
        return records

    def _sync_candidate_manifests(
        self,
        *,
        project_id: str,
        run_id: str,
        candidates: list[HypothesisCandidate],
        decisions: list[PortfolioDecisionRecord],
    ) -> list[HypothesisCandidate]:
        decisions_by_candidate = {item.candidate_id: item for item in decisions}
        synced: list[HypothesisCandidate] = []
        for candidate in candidates:
            synced.append(
                save_candidate_manifest(
                    project_id,
                    run_id,
                    candidate,
                    decision=decisions_by_candidate.get(candidate.id),
                )
            )
        return synced

    def _checkpoint_run_state(
        self,
        run: AutoResearchRunRead,
        *,
        candidates: list[HypothesisCandidate],
        portfolio: PortfolioSummary,
        preferred_candidate_id: str | None = None,
    ) -> AutoResearchRunRead:
        preferred_candidate = (
            self._candidate_by_id(candidates, preferred_candidate_id)
            if preferred_candidate_id is not None
            else None
        )
        snapshot_candidate = preferred_candidate or self._leader_candidate(candidates)
        return save_run(
            run.model_copy(
                update={
                    "candidates": candidates,
                    "portfolio": portfolio,
                    "attempts": snapshot_candidate.attempts if snapshot_candidate else run.attempts,
                    "artifact": snapshot_candidate.artifact if snapshot_candidate else run.artifact,
                    "generated_code_path": (
                        snapshot_candidate.generated_code_path
                        if snapshot_candidate is not None
                        else run.generated_code_path
                    ),
                    "selected_round_index": (
                        snapshot_candidate.selected_round_index
                        if snapshot_candidate is not None
                        else run.selected_round_index
                    ),
                }
            )
        )

    def ingest_bridge_result(
        self,
        *,
        project_id: str,
        run_id: str,
        session_id: str,
        artifact: ResultArtifact,
    ) -> AutoResearchRunRead:
        run = load_run(project_id, run_id)
        if run is None:
            raise ValueError(f"Run not found: {run_id}")
        if run.plan is None or run.spec is None or run.portfolio is None:
            raise ValueError("Run is missing persisted planning state required for bridge import")
        bridge = build_bridge_state(project_id, run_id)
        if bridge is None:
            raise ValueError(f"Run not found: {run_id}")
        session = next((item for item in bridge.sessions if item.session_id == session_id), None)
        if session is None:
            raise ValueError(f"Bridge session not found: {session_id}")
        candidate = self._candidate_by_id(run.candidates, session.candidate_id)
        if candidate is None:
            raise ValueError(f"Candidate not found for bridge session: {session.candidate_id}")

        attempts = list(candidate.attempts)
        if any(item.round_index == session.round_index for item in attempts):
            raise ValueError(
                f"Bridge result for round {session.round_index} was already imported for {session.candidate_id}"
            )
        critique = self._attempt_critique(artifact, attempts)
        attempt = ExperimentAttempt(
            round_index=session.round_index,
            strategy=session.strategy,
            goal=session.goal,
            status="done" if artifact.status == "done" else "failed",
            summary=artifact.summary,
            critique=critique,
            code_path=session.code_path,
            repair_summary=None,
            artifact=artifact,
        )
        attempts.append(attempt)
        best_attempt = self._best_attempt_from_history(attempts)
        best_artifact = best_attempt.artifact if best_attempt is not None else attempts[-1].artifact
        best_code_path = best_attempt.code_path if best_attempt is not None else attempts[-1].code_path
        best_score = (
            self._artifact_score(best_attempt.artifact)
            if best_attempt is not None and best_attempt.artifact is not None
            else None
        )

        candidates = self._update_candidate(
            run.candidates,
            candidate.id,
            status="running",
            attempts=attempts,
            artifact=best_artifact,
            generated_code_path=best_code_path,
            selected_round_index=best_attempt.round_index if best_attempt is not None else None,
            score=(
                best_score
                if best_score is not None and best_score != float("-inf")
                else None
            ),
        )
        checkpoint_candidate = self._candidate_by_id(candidates, candidate.id)
        if checkpoint_candidate is not None:
            candidates = self._replace_candidate(
                candidates,
                self._persist_candidate(
                    project_id=project_id,
                    run_id=run_id,
                    base_plan=run.plan,
                    base_spec=run.spec,
                    candidate=checkpoint_candidate,
                ),
            )
        candidates = self._sync_candidate_manifests(
            project_id=project_id,
            run_id=run_id,
            candidates=candidates,
            decisions=run.portfolio.decisions,
        )
        return self._checkpoint_run_state(
            run,
            candidates=candidates,
            portfolio=run.portfolio,
            preferred_candidate_id=candidate.id,
        )

    def apply_review_actions(
        self,
        *,
        db: Session,
        project_id: str,
        run_id: str,
        expected_round: int,
        expected_review_fingerprint: str,
    ) -> AutoResearchRunRead:
        from services.autoresearch.review_publish import build_review_loop

        review_loop = build_review_loop(project_id, run_id)
        if review_loop is None:
            raise ValueError(f"Run not found: {run_id}")
        if review_loop.current_round != expected_round:
            raise ValueError(
                f"Review loop round changed from expected {expected_round} to {review_loop.current_round}"
            )
        if review_loop.latest_review_fingerprint != expected_review_fingerprint:
            raise ValueError("Review loop fingerprint changed; refresh review state before applying revisions")
        if review_loop.pending_action_count < 1:
            raise ValueError("Review loop has no pending revision actions to apply")
        return self._rebuild_paper_pipeline(
            db=db,
            project_id=project_id,
            run_id=run_id,
            refresh_review_after_rebuild=True,
        )

    def rebuild_paper_pipeline(
        self,
        *,
        db: Session,
        project_id: str,
        run_id: str,
    ) -> AutoResearchRunRead:
        return self._rebuild_paper_pipeline(
            db=db,
            project_id=project_id,
            run_id=run_id,
            refresh_review_after_rebuild=False,
        )

    def _rebuild_paper_pipeline(
        self,
        *,
        db: Session,
        project_id: str,
        run_id: str,
        refresh_review_after_rebuild: bool,
    ) -> AutoResearchRunRead:
        from services.autoresearch.review_publish import build_review_loop

        run = load_run(project_id, run_id)
        if run is None:
            raise ValueError(f"Run not found: {run_id}")
        if run.status != "done":
            raise ValueError("Paper pipeline rebuild requires a completed auto research run")
        if run.program is None or run.plan is None or run.spec is None or run.portfolio is None or run.artifact is None:
            raise ValueError("Run is missing persisted planning or artifact state required for paper rebuild")
        selected_candidate_id = run.portfolio.selected_candidate_id
        if not selected_candidate_id:
            raise ValueError("Run does not have a selected candidate for paper rebuild")
        selected_candidate = self._candidate_by_id(run.candidates, selected_candidate_id)
        if selected_candidate is None or selected_candidate.artifact is None:
            raise ValueError("Selected candidate is missing the persisted artifact required for paper rebuild")

        # Pull the latest persisted review-loop state into the paper revision state before rebuilding.
        build_review_loop(project_id, run_id)
        refreshed_run = load_run(project_id, run_id)
        if refreshed_run is not None:
            run = refreshed_run
            selected_candidate = self._candidate_by_id(run.candidates, selected_candidate_id)
        if selected_candidate is None or selected_candidate.artifact is None:
            raise ValueError("Selected candidate is missing the persisted artifact required for paper rebuild")

        set_project_status(db, project_id, "write")
        paper_pipeline = self.writer.build_pipeline(
            run.plan,
            run.spec,
            selected_candidate.artifact,
            literature=run.literature,
            attempts=selected_candidate.attempts or run.attempts,
            benchmark_name=run.program.benchmark_name or run.spec.benchmark_name,
            program=run.program,
            portfolio=run.portfolio,
            candidates=run.candidates,
            paper_plan=run.paper_plan,
            figure_plan=run.figure_plan,
            paper_revision_state=run.paper_revision_state,
        )
        paper_path = paper_file_path(project_id, run_id)
        candidate_paper_path = candidate_paper_file_path(project_id, run_id, selected_candidate.id)
        narrative_report_path = narrative_report_file_path(project_id, run_id)
        claim_evidence_matrix_path = claim_evidence_matrix_file_path(project_id, run_id)
        paper_plan_path = paper_plan_file_path(project_id, run_id)
        figure_plan_path = figure_plan_file_path(project_id, run_id)
        paper_revision_state_path = paper_revision_state_file_path(project_id, run_id)
        paper_compile_report_path = paper_compile_report_file_path(project_id, run_id)
        paper_revision_action_index_path = paper_revision_action_index_file_path(project_id, run_id)
        paper_revision_diff_path = paper_revision_diff_file_path(project_id, run_id)
        paper_section_rewrite_index_path = paper_section_rewrite_index_file_path(project_id, run_id)
        paper_sources_dir = paper_sources_dir_path(project_id, run_id)
        paper_section_rewrite_packets_dir = paper_section_rewrite_packets_dir_path(project_id, run_id)
        paper_latex_path = paper_latex_file_path(project_id, run_id)
        paper_bibliography_path = paper_bibliography_file_path(project_id, run_id)
        paper_sources_manifest_path = paper_sources_manifest_file_path(project_id, run_id)

        rebuilt_candidate = save_candidate_snapshot(
            project_id,
            run_id,
            selected_candidate.model_copy(
                update={
                    "paper_markdown": paper_pipeline.paper_markdown,
                    "paper_path": candidate_paper_path,
                }
            ),
            plan=run.plan,
            spec=run.spec,
        )
        decision = next(
            (item for item in run.portfolio.decisions if item.candidate_id == selected_candidate.id),
            None,
        )
        rebuilt_candidate = save_candidate_manifest(
            project_id,
            run_id,
            rebuilt_candidate,
            decision=decision,
        )
        updated_candidates = self._replace_candidate(run.candidates, rebuilt_candidate)
        draft = create_draft(
            db,
            project_id,
            paper_pipeline.paper_markdown,
            claims=[],
            section="autorresearch_v0",
        )
        rebuilt_run = save_run(
            run.model_copy(
                update={
                    "narrative_report_markdown": paper_pipeline.narrative_report_markdown,
                    "narrative_report_path": narrative_report_path,
                    "claim_evidence_matrix": paper_pipeline.claim_evidence_matrix,
                    "claim_evidence_matrix_path": claim_evidence_matrix_path,
                    "paper_plan": paper_pipeline.paper_plan,
                    "paper_plan_path": paper_plan_path,
                    "figure_plan": paper_pipeline.figure_plan,
                    "figure_plan_path": figure_plan_path,
                    "paper_revision_state": paper_pipeline.paper_revision_state,
                    "paper_revision_state_path": paper_revision_state_path,
                    "paper_compile_report": paper_pipeline.paper_compile_report,
                    "paper_compile_report_path": paper_compile_report_path,
                    "paper_revision_action_index": paper_pipeline.paper_revision_action_index,
                    "paper_revision_action_index_path": paper_revision_action_index_path,
                    "paper_revision_diff": paper_pipeline.paper_revision_diff,
                    "paper_revision_diff_path": paper_revision_diff_path,
                    "paper_section_rewrite_index": paper_pipeline.paper_section_rewrite_index,
                    "paper_section_rewrite_index_path": paper_section_rewrite_index_path,
                    "paper_sources_dir": paper_sources_dir,
                    "paper_section_rewrite_packets_dir": paper_section_rewrite_packets_dir,
                    "paper_latex_source": paper_pipeline.paper_latex_source,
                    "paper_latex_path": paper_latex_path,
                    "paper_bibliography_bib": paper_pipeline.paper_bibliography_bib,
                    "paper_bibliography_path": paper_bibliography_path,
                    "paper_sources_manifest": paper_pipeline.paper_sources_manifest,
                    "paper_sources_manifest_path": paper_sources_manifest_path,
                    "paper_markdown": paper_pipeline.paper_markdown,
                    "paper_path": paper_path,
                    "paper_draft_version": draft.version,
                    "candidates": updated_candidates,
                }
        )
        )
        set_project_status(db, project_id, "edit")
        if refresh_review_after_rebuild:
            build_review_loop(project_id, run_id)
        return load_run(project_id, run_id) or rebuilt_run

    def execute(
        self,
        *,
        db: Session,
        project_id: str,
        run_id: str,
        topic: str,
        task_family_hint: TaskFamily | None = None,
        paper_ids: list[str] | None = None,
        max_rounds: int = 3,
        candidate_execution_limit: int | None = None,
        benchmark_source: BenchmarkSource | None = None,
        execution_backend: ExecutionBackendSpec | None = None,
        auto_search_literature: bool = True,
        auto_fetch_literature: bool = False,
        docker_image: str | None = None,
        execution_action: AutoResearchJobAction = "run",
        should_cancel: Callable[[], bool] | None = None,
    ) -> AutoResearchRunRead:
        run = load_run(project_id, run_id)
        if run is None:
            raise ValueError(f"Run not found: {run_id}")

        self._raise_if_cancelled(should_cancel)
        set_project_status(db, project_id, "write")
        run = save_run(run.model_copy(update={"status": "running"}))
        try:
            effective_backend = execution_backend or run.execution_backend
            if effective_backend is None and docker_image:
                effective_backend = ExecutionBackendSpec(docker_image=docker_image)
            bridge_service = AutoResearchExperimentBridgeService()
            self._raise_if_cancelled(should_cancel)
            restoring_from_checkpoint = (
                execution_action in {"resume", "retry"} and self._can_resume_from_checkpoint(run)
            )
            chunk_context = None

            if restoring_from_checkpoint:
                benchmark = self._benchmark_from_checkpoint(project_id=project_id, run_id=run_id)
                if benchmark is None:
                    benchmark = resolve_benchmark(
                        topic=topic,
                        task_family_hint=task_family_hint,
                        benchmark_source=benchmark_source or run.benchmark,
                    )
                literature = list(run.literature)
                plan = run.plan
                spec = run.spec
                program = run.program
                portfolio = run.portfolio
                candidates = [candidate.model_copy(deep=True) for candidate in run.candidates]
                assert plan is not None
                assert spec is not None
                assert program is not None
                assert portfolio is not None
                if execution_action == "retry":
                    selected_candidate_id = (
                        portfolio.candidate_rankings[0]
                        if portfolio.candidate_rankings
                        else (candidates[0].id if candidates else None)
                    )
                    candidates = [
                        self._retry_candidate(
                            candidate,
                            selected=candidate.id == selected_candidate_id,
                        )
                        for candidate in candidates
                    ]
                    portfolio = self._retry_portfolio(portfolio, candidates)
            else:
                benchmark = resolve_benchmark(
                    topic=topic,
                    task_family_hint=task_family_hint,
                    benchmark_source=benchmark_source,
                )
                _papers, literature, chunk_context = gather_literature_context(
                    db=db,
                    project_id=project_id,
                    topic=topic,
                    paper_ids=paper_ids,
                    auto_search=auto_search_literature,
                    auto_fetch=auto_fetch_literature,
                )
                if auto_search_literature and not literature:
                    literature = build_fallback_literature_context(
                        topic=topic,
                        benchmark_name=benchmark.benchmark_name,
                        benchmark_description=benchmark.benchmark_description,
                        dataset_name=str(benchmark.payload.get("name") or benchmark.benchmark_name),
                        dataset_description=str(
                            benchmark.payload.get("description") or benchmark.benchmark_description
                        ),
                        task_family=benchmark.task_family,
                    )
                self._raise_if_cancelled(should_cancel)
                plan = self.planner.plan(
                    topic,
                    benchmark.task_family,
                    literature,
                    benchmark_name=benchmark.benchmark_name,
                    benchmark_description=benchmark.benchmark_description,
                    benchmark_labels=benchmark.payload.get("label_space"),
                )
                if not plan.experiment_outline:
                    plan.experiment_outline = [
                        "Pull or instantiate a benchmark snapshot and freeze train/test partitions.",
                        "Run baseline and candidate systems.",
                        "Summarize metrics and environment metadata.",
                    ]
                plan.experiment_outline[0] = (
                    "Pull a benchmark snapshot, validate its schema, and freeze train/test partitions."
                    if benchmark.source.kind != "builtin"
                    else "Instantiate the selected benchmark and freeze train/test partitions."
                )
                spec = build_experiment_spec(plan.task_family, benchmark)
                program = self.planner.build_program(
                    run_id=run_id,
                    plan=plan,
                    benchmark_name=benchmark.benchmark_name,
                )
                candidates, portfolio = self.planner.build_portfolio(
                    program=program,
                    plan=plan,
                    spec=spec,
                )

            self._raise_if_cancelled(should_cancel)
            benchmark_snapshot_path = save_benchmark_snapshot(
                project_id,
                run_id,
                {
                    "source": benchmark.source.model_dump(mode="json"),
                    "task_family": benchmark.task_family,
                    "benchmark_name": benchmark.benchmark_name,
                    "benchmark_description": benchmark.benchmark_description,
                    "payload": benchmark.payload,
                },
            )

            candidates = [
                self._persist_candidate(
                    project_id=project_id,
                    run_id=run_id,
                    base_plan=plan,
                    base_spec=spec,
                    candidate=candidate,
                )
                for candidate in candidates
            ]
            leader = self._leader_candidate(candidates)
            portfolio = portfolio.model_copy(
                update={
                    "decisions": self._decision_records(
                        candidates,
                        winner=leader,
                        benchmark_name=benchmark.benchmark_name,
                        final=False,
                    )
                }
            )
            candidates = self._sync_candidate_manifests(
                project_id=project_id,
                run_id=run_id,
                candidates=candidates,
                decisions=portfolio.decisions,
            )
            candidate_order = self._budgeted_candidate_order(
                candidates=candidates,
                portfolio=portfolio,
                candidate_execution_limit=candidate_execution_limit,
            )
            candidates = self._defer_reserve_candidates(
                candidates,
                set(candidate_order),
                selected_candidate_id=portfolio.selected_candidate_id,
            )
            portfolio = portfolio.model_copy(
                update={
                    "decisions": self._decision_records(
                        candidates,
                        winner=leader,
                        benchmark_name=benchmark.benchmark_name,
                        final=False,
                    )
                }
            )
            candidates = self._sync_candidate_manifests(
                project_id=project_id,
                run_id=run_id,
                candidates=candidates,
                decisions=portfolio.decisions,
            )
            run_updates = {
                "task_family": plan.task_family,
                "benchmark": benchmark.source,
                "execution_backend": effective_backend,
                "program": program,
                "plan": plan,
                "spec": spec,
                "literature": literature,
                "candidates": candidates,
                "portfolio": portfolio,
                "error": None,
            }
            if execution_action == "retry":
                run_updates.update(
                    {
                        "attempts": [],
                        "artifact": None,
                        "generated_code_path": None,
                        "paper_markdown": None,
                        "paper_path": None,
                        "narrative_report_markdown": None,
                        "narrative_report_path": None,
                        "claim_evidence_matrix": None,
                        "claim_evidence_matrix_path": None,
                        "paper_plan": None,
                        "paper_plan_path": None,
                        "figure_plan": None,
                        "figure_plan_path": None,
                        "paper_revision_state": None,
                        "paper_revision_state_path": None,
                        "paper_compile_report": None,
                        "paper_compile_report_path": None,
                        "paper_revision_action_index": None,
                        "paper_revision_action_index_path": None,
                        "paper_revision_diff": None,
                        "paper_revision_diff_path": None,
                        "paper_section_rewrite_index": None,
                        "paper_section_rewrite_index_path": None,
                        "paper_sources_dir": None,
                        "paper_section_rewrite_packets_dir": None,
                        "paper_latex_source": None,
                        "paper_latex_path": None,
                        "paper_bibliography_bib": None,
                        "paper_bibliography_path": None,
                        "paper_sources_manifest": None,
                        "paper_sources_manifest_path": None,
                        "paper_draft_version": None,
                        "selected_round_index": None,
                    }
                )
            run = save_run(run.model_copy(update=run_updates))
            bridge_enabled = bool(
                run.request is not None
                and run.request.experiment_bridge is not None
                and run.request.experiment_bridge.enabled
            )

            for candidate_id in candidate_order:
                self._raise_if_cancelled(should_cancel)
                candidate = self._candidate_by_id(candidates, candidate_id)
                if candidate is None:
                    continue
                if self._should_skip_candidate(candidate, execution_action=execution_action):
                    continue
                candidate_plan = self.planner.candidate_plan(plan, candidate)
                candidate_spec = self.planner.candidate_spec(spec, candidate)
                executed_ids = list(portfolio.executed_candidate_ids)
                if candidate.id not in executed_ids:
                    executed_ids.append(candidate.id)
                attempts = (
                    list(candidate.attempts)
                    if execution_action == "resume" and candidate.status == "running"
                    else []
                )
                best_attempt = self._best_attempt_from_history(attempts)
                start_round = len(attempts) + 1 if attempts else 1
                candidates = self._update_candidate(
                    candidates,
                    candidate.id,
                    status="running",
                )
                running_candidate = self._candidate_by_id(candidates, candidate.id)
                if running_candidate is not None:
                    candidates = self._replace_candidate(
                        candidates,
                        self._persist_candidate(
                            project_id=project_id,
                            run_id=run_id,
                            base_plan=plan,
                            base_spec=spec,
                            candidate=running_candidate,
                        ),
                    )
                leader = self._leader_candidate(candidates)
                portfolio = portfolio.model_copy(
                    update={
                        "status": "running",
                        "executed_candidate_ids": executed_ids,
                        "decisions": self._decision_records(
                            candidates,
                            winner=leader,
                            benchmark_name=benchmark.benchmark_name,
                            final=False,
                        ),
                    }
                )
                candidates = self._sync_candidate_manifests(
                    project_id=project_id,
                    run_id=run_id,
                    candidates=candidates,
                    decisions=portfolio.decisions,
                )
                run = self._checkpoint_run_state(
                    run,
                    candidates=candidates,
                    portfolio=portfolio,
                    preferred_candidate_id=candidate.id,
                )
                candidates = run.candidates

                total_rounds = max(
                    1,
                    min(max_rounds, max(1, len(candidate_spec.search_strategies))),
                )

                for round_index in range(start_round, total_rounds + 1):
                    self._raise_if_cancelled(should_cancel)
                    goal = self._attempt_goal(attempts, round_index)
                    repair_summary = None
                    code_override = None
                    strategy_override = None
                    if goal == "repair_previous_failure" and attempts:
                        repair_candidate = self.repair.repair(
                            previous_attempt=attempts[-1],
                            plan=candidate_plan,
                            spec=candidate_spec,
                            benchmark_payload=benchmark.payload,
                        )
                        repair_summary = {
                            "strategy": repair_candidate.strategy,
                            "sanity_checks": repair_candidate.sanity_checks,
                            "patch_line_count": len(
                                {patch.line_number for patch in repair_candidate.patch_ops}
                            ),
                        }
                        if repair_candidate.strategy != "repair_regenerate":
                            code_override = repair_candidate.code
                            strategy_override = repair_candidate.strategy

                    if bridge_enabled:
                        strategy, code_path, _prepared_code = self.runner.prepare_attempt(
                            project_id=project_id,
                            run_id=run_id,
                            plan=candidate_plan,
                            spec=candidate_spec,
                            benchmark_payload=benchmark.payload,
                            round_index=round_index,
                            goal=goal,
                            prior_attempts=attempts,
                            code_override=code_override,
                            strategy_override=strategy_override,
                            code_filename_prefix=candidate.id,
                            code_subdir=f"candidates/{candidate.id}",
                        )
                        candidates = self._update_candidate(
                            candidates,
                            candidate.id,
                            status="running",
                            generated_code_path=code_path,
                        )
                        checkpoint_candidate = self._candidate_by_id(candidates, candidate.id)
                        if checkpoint_candidate is not None:
                            candidates = self._replace_candidate(
                                candidates,
                                self._persist_candidate(
                                    project_id=project_id,
                                    run_id=run_id,
                                    base_plan=plan,
                                    base_spec=spec,
                                    candidate=checkpoint_candidate,
                                ),
                            )
                        candidates = self._sync_candidate_manifests(
                            project_id=project_id,
                            run_id=run_id,
                            candidates=candidates,
                            decisions=portfolio.decisions,
                        )
                        run = self._checkpoint_run_state(
                            run,
                            candidates=candidates,
                            portfolio=portfolio,
                            preferred_candidate_id=candidate.id,
                        )
                        candidates = run.candidates
                        active_candidate = self._candidate_by_id(candidates, candidate.id)
                        bridge_service.start_session(
                            project_id=project_id,
                            run_id=run_id,
                            candidate_id=candidate.id,
                            candidate_title=active_candidate.title if active_candidate is not None else candidate.title,
                            round_index=round_index,
                            goal=goal,
                            strategy=strategy,
                            code_path=code_path,
                            plan_payload=candidate_plan.model_dump(mode="json"),
                            spec_payload=candidate_spec.model_dump(mode="json"),
                            prior_attempts_payload=[item.model_dump(mode="json") for item in attempts],
                            execution_backend_payload=(
                                effective_backend.model_dump(mode="json")
                                if effective_backend is not None
                                else None
                            ),
                        )
                        return load_run(project_id, run_id) or run

                    strategy, code_path, artifact = self.runner.run(
                        project_id=project_id,
                        run_id=run_id,
                        plan=candidate_plan,
                        spec=candidate_spec,
                        benchmark_payload=benchmark.payload,
                        round_index=round_index,
                        goal=goal,
                        prior_attempts=attempts,
                        execution_backend=effective_backend,
                        code_override=code_override,
                        strategy_override=strategy_override,
                        code_filename_prefix=candidate.id,
                        code_subdir=f"candidates/{candidate.id}",
                    )
                    artifact.environment.setdefault("benchmark_snapshot_path", benchmark_snapshot_path)
                    if chunk_context:
                        artifact.environment.setdefault("literature_chunk_context", chunk_context)
                    critique = self._attempt_critique(artifact, attempts)
                    attempt = ExperimentAttempt(
                        round_index=round_index,
                        strategy=strategy,
                        goal=goal,
                        status="done" if artifact.status == "done" else "failed",
                        summary=artifact.summary,
                        critique=critique,
                        code_path=code_path,
                        repair_summary=repair_summary,
                        artifact=artifact,
                    )
                    attempts.append(attempt)

                    if artifact.status == "done" and (
                        best_attempt is None
                        or self._attempt_preference_key(artifact)
                        > self._attempt_preference_key(best_attempt.artifact)
                    ):
                        best_attempt = attempt
                    best_artifact = (
                        best_attempt.artifact if best_attempt is not None else attempts[-1].artifact
                    )
                    best_code_path = (
                        best_attempt.code_path if best_attempt is not None else attempts[-1].code_path
                    )
                    best_score = (
                        self._artifact_score(best_attempt.artifact)
                        if best_attempt is not None and best_attempt.artifact is not None
                        else None
                    )
                    candidates = self._update_candidate(
                        candidates,
                        candidate.id,
                        status="running",
                        attempts=attempts,
                        artifact=best_artifact,
                        generated_code_path=best_code_path,
                        selected_round_index=best_attempt.round_index if best_attempt else None,
                        score=(
                            best_score
                            if best_score is not None and best_score != float("-inf")
                            else None
                        ),
                    )
                    checkpoint_candidate = self._candidate_by_id(candidates, candidate.id)
                    if checkpoint_candidate is not None:
                        candidates = self._replace_candidate(
                            candidates,
                            self._persist_candidate(
                                project_id=project_id,
                                run_id=run_id,
                                base_plan=plan,
                                base_spec=spec,
                                candidate=checkpoint_candidate,
                            ),
                        )
                    candidates = self._sync_candidate_manifests(
                        project_id=project_id,
                        run_id=run_id,
                        candidates=candidates,
                        decisions=portfolio.decisions,
                    )
                    run = self._checkpoint_run_state(
                        run,
                        candidates=candidates,
                        portfolio=portfolio,
                        preferred_candidate_id=candidate.id,
                    )
                    candidates = run.candidates

                if best_attempt is None or best_attempt.artifact is None:
                    candidates = self._update_candidate(
                        candidates,
                        candidate.id,
                        status="failed",
                        attempts=attempts,
                        artifact=attempts[-1].artifact if attempts else None,
                        generated_code_path=attempts[-1].code_path if attempts else None,
                        selected_round_index=None,
                        score=None,
                    )
                else:
                    best_score = self._artifact_score(best_attempt.artifact)
                    candidates = self._update_candidate(
                        candidates,
                        candidate.id,
                        status="done",
                        attempts=attempts,
                        artifact=best_attempt.artifact,
                        generated_code_path=best_attempt.code_path,
                        selected_round_index=best_attempt.round_index,
                        score=best_score if best_score != float("-inf") else None,
                    )
                completed_candidate = self._candidate_by_id(candidates, candidate.id)
                if completed_candidate is not None:
                    candidates = self._replace_candidate(
                        candidates,
                        self._persist_candidate(
                            project_id=project_id,
                            run_id=run_id,
                            base_plan=plan,
                            base_spec=spec,
                            candidate=completed_candidate,
                        ),
                    )

                candidates = self._rank_candidates(candidates)
                leader = self._leader_candidate(candidates)
                leader_plan = self.planner.candidate_plan(plan, leader) if leader else plan
                leader_spec = self.planner.candidate_spec(spec, leader) if leader else spec
                portfolio = portfolio.model_copy(
                    update={
                        "candidate_rankings": [item.id for item in candidates],
                        "selected_candidate_id": leader.id if leader else None,
                        "winning_score": leader.score if leader else None,
                        "decision_summary": self._portfolio_progress_summary(
                            leader,
                            executed_count=len(portfolio.executed_candidate_ids),
                            total_candidates=len(candidates),
                            benchmark_name=benchmark.benchmark_name,
                        ),
                        "decisions": self._decision_records(
                            candidates,
                            winner=leader,
                            benchmark_name=benchmark.benchmark_name,
                            final=False,
                        ),
                    }
                )
                candidates = self._sync_candidate_manifests(
                    project_id=project_id,
                    run_id=run_id,
                    candidates=candidates,
                    decisions=portfolio.decisions,
                )
                run = save_run(
                    run.model_copy(
                        update={
                            "plan": leader_plan,
                            "spec": leader_spec,
                            "attempts": leader.attempts if leader else [],
                            "generated_code_path": leader.generated_code_path if leader else None,
                            "artifact": leader.artifact if leader else None,
                            "selected_round_index": leader.selected_round_index if leader else None,
                            "candidates": candidates,
                            "portfolio": portfolio,
                        }
                    )
                )
                candidates = run.candidates

            winner = self._leader_candidate(candidates)
            self._raise_if_cancelled(should_cancel)
            if winner is None or winner.artifact is None:
                latest_candidate = (
                    self._candidate_by_id(candidates, portfolio.executed_candidate_ids[-1])
                    if portfolio.executed_candidate_ids
                    else None
                )
                portfolio = portfolio.model_copy(
                    update={
                        "status": "failed",
                        "selected_candidate_id": None,
                        "winning_score": None,
                        "decision_summary": self._portfolio_progress_summary(
                            None,
                            executed_count=len(portfolio.executed_candidate_ids),
                            total_candidates=len(candidates),
                            benchmark_name=benchmark.benchmark_name,
                        ),
                        "decisions": self._decision_records(
                            candidates,
                            winner=None,
                            benchmark_name=benchmark.benchmark_name,
                            final=True,
                        ),
                    }
                )
                candidates = self._sync_candidate_manifests(
                    project_id=project_id,
                    run_id=run_id,
                    candidates=candidates,
                    decisions=portfolio.decisions,
                )
                failed = save_run(
                    run.model_copy(
                        update={
                            "status": "failed",
                            "attempts": latest_candidate.attempts if latest_candidate else [],
                            "artifact": latest_candidate.artifact if latest_candidate else None,
                            "generated_code_path": (
                                latest_candidate.generated_code_path if latest_candidate else None
                            ),
                            "selected_round_index": (
                                latest_candidate.selected_round_index if latest_candidate else None
                            ),
                            "error": (
                                latest_candidate.attempts[-1].summary
                                if latest_candidate and latest_candidate.attempts
                                else "No portfolio candidate produced a result artifact"
                            ),
                            "candidates": candidates,
                            "portfolio": portfolio,
                        }
                    )
                )
                bridge_service.finalize_run(
                    project_id=project_id,
                    run_id=run_id,
                    run_status="failed",
                )
                return failed

            winner_plan = self.planner.candidate_plan(plan, winner)
            winner_spec = self.planner.candidate_spec(spec, winner)
            portfolio = portfolio.model_copy(
                update={
                    "status": "done",
                    "selected_candidate_id": winner.id,
                    "winning_score": winner.score,
                    "decision_summary": self._portfolio_decision_summary(
                        winner,
                        winner.artifact,
                        winner.attempts,
                        benchmark.benchmark_name,
                    ),
                    "decisions": self._decision_records(
                        candidates,
                        winner=winner,
                        benchmark_name=benchmark.benchmark_name,
                        final=True,
                    ),
                }
            )
            candidates = self._apply_selection_reasons(
                candidates,
                winner=winner,
                benchmark_name=benchmark.benchmark_name,
            )
            candidates = self._sync_candidate_manifests(
                project_id=project_id,
                run_id=run_id,
                candidates=candidates,
                decisions=portfolio.decisions,
            )
            paper_path = paper_file_path(project_id, run_id)
            candidate_paper_path = candidate_paper_file_path(project_id, run_id, winner.id)
            narrative_report_path = narrative_report_file_path(project_id, run_id)
            claim_evidence_matrix_path = claim_evidence_matrix_file_path(project_id, run_id)
            paper_plan_path = paper_plan_file_path(project_id, run_id)
            figure_plan_path = figure_plan_file_path(project_id, run_id)
            paper_revision_state_path = paper_revision_state_file_path(project_id, run_id)
            paper_compile_report_path = paper_compile_report_file_path(project_id, run_id)
            paper_revision_action_index_path = paper_revision_action_index_file_path(project_id, run_id)
            paper_revision_diff_path = paper_revision_diff_file_path(project_id, run_id)
            paper_section_rewrite_index_path = paper_section_rewrite_index_file_path(project_id, run_id)
            paper_sources_dir = paper_sources_dir_path(project_id, run_id)
            paper_section_rewrite_packets_dir = paper_section_rewrite_packets_dir_path(project_id, run_id)
            paper_latex_path = paper_latex_file_path(project_id, run_id)
            paper_bibliography_path = paper_bibliography_file_path(project_id, run_id)
            paper_sources_manifest_path = paper_sources_manifest_file_path(project_id, run_id)
            paper_pipeline = self.writer.build_pipeline(
                winner_plan,
                winner_spec,
                winner.artifact,
                literature=literature,
                attempts=winner.attempts,
                benchmark_name=benchmark.benchmark_name,
                program=program,
                portfolio=portfolio,
                candidates=candidates,
            )
            paper_markdown = paper_pipeline.paper_markdown
            candidates = self._update_candidate(
                candidates,
                winner.id,
                paper_markdown=paper_markdown,
                paper_path=candidate_paper_path,
            )
            candidates = [
                self._persist_candidate(
                    project_id=project_id,
                    run_id=run_id,
                    base_plan=plan,
                    base_spec=spec,
                    candidate=candidate,
                )
                for candidate in candidates
            ]
            candidates = self._sync_candidate_manifests(
                project_id=project_id,
                run_id=run_id,
                candidates=candidates,
                decisions=portfolio.decisions,
            )
            winner = self._candidate_by_id(candidates, winner.id) or winner
            draft = create_draft(
                db,
                project_id,
                paper_markdown,
                claims=[],
                section="autorresearch_v0",
            )
            set_project_status(db, project_id, "edit")
            completed = save_run(
                run.model_copy(
                    update={
                        "status": "done",
                        "plan": winner_plan,
                        "spec": winner_spec,
                        "generated_code_path": winner.generated_code_path,
                        "artifact": winner.artifact,
                        "narrative_report_markdown": paper_pipeline.narrative_report_markdown,
                        "narrative_report_path": narrative_report_path,
                        "claim_evidence_matrix": paper_pipeline.claim_evidence_matrix,
                        "claim_evidence_matrix_path": claim_evidence_matrix_path,
                        "paper_plan": paper_pipeline.paper_plan,
                        "paper_plan_path": paper_plan_path,
                        "figure_plan": paper_pipeline.figure_plan,
                        "figure_plan_path": figure_plan_path,
                        "paper_revision_state": paper_pipeline.paper_revision_state,
                        "paper_revision_state_path": paper_revision_state_path,
                        "paper_compile_report": paper_pipeline.paper_compile_report,
                        "paper_compile_report_path": paper_compile_report_path,
                        "paper_revision_action_index": paper_pipeline.paper_revision_action_index,
                        "paper_revision_action_index_path": paper_revision_action_index_path,
                        "paper_revision_diff": paper_pipeline.paper_revision_diff,
                        "paper_revision_diff_path": paper_revision_diff_path,
                        "paper_section_rewrite_index": paper_pipeline.paper_section_rewrite_index,
                        "paper_section_rewrite_index_path": paper_section_rewrite_index_path,
                        "paper_sources_dir": paper_sources_dir,
                        "paper_section_rewrite_packets_dir": paper_section_rewrite_packets_dir,
                        "paper_latex_source": paper_pipeline.paper_latex_source,
                        "paper_latex_path": paper_latex_path,
                        "paper_bibliography_bib": paper_pipeline.paper_bibliography_bib,
                        "paper_bibliography_path": paper_bibliography_path,
                        "paper_sources_manifest": paper_pipeline.paper_sources_manifest,
                        "paper_sources_manifest_path": paper_sources_manifest_path,
                        "paper_markdown": paper_markdown,
                        "paper_path": paper_path,
                        "paper_draft_version": draft.version,
                        "attempts": winner.attempts,
                        "selected_round_index": winner.selected_round_index,
                        "candidates": candidates,
                        "portfolio": portfolio,
                    }
                )
            )
            bridge_service.finalize_run(
                project_id=project_id,
                run_id=run_id,
                run_status="done",
            )
            return completed
        except AutoResearchExecutionCancelled as exc:
            canceled = save_run(
                run.model_copy(
                    update={
                        "status": "canceled",
                        "error": str(exc),
                    }
                )
            )
            bridge_service.finalize_run(
                project_id=project_id,
                run_id=run_id,
                run_status="canceled",
            )
            raise AutoResearchExecutionCancelled(canceled.error or str(exc)) from exc
        except Exception as exc:
            failed = save_run(
                run.model_copy(
                    update={
                        "status": "failed",
                        "error": str(exc),
                    }
                )
            )
            bridge_service.finalize_run(
                project_id=project_id,
                run_id=run_id,
                run_status="failed",
            )
            return failed
