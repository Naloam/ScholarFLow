"""Hill-climbing experiment search inspired by karpathy/autoresearch."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

from schemas.autoresearch import ResultArtifact
from services.llm.client import chat
from services.llm.prompting import load_prompt
from services.llm.response_utils import get_message_content

logger = logging.getLogger(__name__)

HILL_CLIMBER_PROMPT_PATH = "backend/prompts/autoresearch/hill_climber/v0.1.0.md"


@dataclass
class HillClimbIteration:
    iteration: int
    description: str = ""
    rationale: str = ""
    candidate_score: float | None = None
    baseline_score: float = 0.0
    status: str = "pending"  # kept | discarded | crash | timeout
    elapsed_seconds: float = 0.0
    error_message: str | None = None


@dataclass
class HillClimbResult:
    best_artifact: ResultArtifact | None = None
    best_code: str = ""
    iterations: list[HillClimbIteration] = field(default_factory=list)
    total_elapsed_seconds: float = 0.0
    improvements: int = 0


class ExperimentHillClimber:
    """Iterative experiment optimizer using LLM-proposed code modifications."""

    def __init__(
        self,
        execute_fn,
        *,
        primary_metric: str = "accuracy",
        time_budget_seconds: int = 600,
        max_iterations: int = 30,
        min_improvement: float = 0.0001,
    ) -> None:
        self._execute_fn = execute_fn
        self._primary_metric = primary_metric
        self._time_budget_seconds = time_budget_seconds
        self._max_iterations = max_iterations
        self._min_improvement = min_improvement

    def run(
        self,
        initial_code: str,
        baseline_artifact: ResultArtifact,
    ) -> HillClimbResult:
        result = HillClimbResult()
        result.best_code = initial_code
        result.best_artifact = baseline_artifact

        baseline_score = baseline_artifact.objective_score
        if baseline_score is None:
            logger.warning("hill_climber: baseline has no objective_score, cannot hill-climb")
            return result
        current_score = baseline_score
        start_time = time.monotonic()

        consecutive_discards = 0
        for i in range(self._max_iterations):
            elapsed = time.monotonic() - start_time
            if elapsed > self._time_budget_seconds:
                logger.info("hill_climber: time budget exhausted (%.0fs > %ds)", elapsed, self._time_budget_seconds)
                break

            iteration = HillClimbIteration(
                iteration=i,
                baseline_score=current_score,
            )
            iter_start = time.monotonic()

            # 1. Propose modification
            modification = self._propose_modification(
                current_code=result.best_code,
                best_score=current_score,
                best_system=baseline_artifact.best_system or "unknown",
                iteration_history=result.iterations[-10:],
            )
            if modification is None:
                logger.warning("hill_climber: iteration %d failed to propose modification", i)
                iteration.status = "crash"
                iteration.description = "LLM failed to produce a modification"
                result.iterations.append(iteration)
                consecutive_discards += 1
                if consecutive_discards >= 5:
                    break
                continue

            iteration.description = modification.get("description", "")
            iteration.rationale = modification.get("rationale", "")

            # 2. Apply modification
            candidate_code = self._apply_modification(result.best_code, modification.get("patches", []))
            if candidate_code is None:
                iteration.status = "crash"
                iteration.error_message = "Patch application failed"
                result.iterations.append(iteration)
                consecutive_discards += 1
                continue

            # 3. Execute
            try:
                candidate_artifact = self._execute_fn(candidate_code)
            except Exception as exc:
                logger.warning("hill_climber: iteration %d execution failed: %s", i, exc)
                iteration.status = "crash"
                iteration.error_message = str(exc)
                iteration.elapsed_seconds = time.monotonic() - iter_start
                result.iterations.append(iteration)
                consecutive_discards += 1
                continue

            candidate_score = candidate_artifact.objective_score
            iteration.candidate_score = candidate_score
            iteration.elapsed_seconds = time.monotonic() - iter_start

            # 4. Compare
            if candidate_score is not None and candidate_score > current_score + self._min_improvement:
                result.best_code = candidate_code
                result.best_artifact = candidate_artifact
                current_score = candidate_score
                iteration.status = "kept"
                result.improvements += 1
                consecutive_discards = 0
                logger.info(
                    "hill_climber: iteration %d KEPT (%.4f -> %.4f, +%.4f): %s",
                    i, iteration.baseline_score, candidate_score,
                    candidate_score - iteration.baseline_score,
                    iteration.description,
                )
            else:
                iteration.status = "discarded"
                consecutive_discards += 1
                score_str = f"{candidate_score:.4f}" if candidate_score is not None else "None"
                logger.info(
                    "hill_climber: iteration %d DISCARDED (%s vs %.4f): %s",
                    i, score_str, iteration.baseline_score, iteration.description,
                )

            result.iterations.append(iteration)

            if consecutive_discards >= 10:
                logger.info("hill_climber: 10 consecutive discards, stopping")
                break

        result.total_elapsed_seconds = time.monotonic() - start_time
        logger.info(
            "hill_climber: completed %d iterations, %d improvements, %.4f -> %.4f (%.1fs)",
            len(result.iterations), result.improvements,
            baseline_score, current_score, result.total_elapsed_seconds,
        )
        return result

    def _propose_modification(
        self,
        current_code: str,
        best_score: float,
        best_system: str,
        iteration_history: list[HillClimbIteration],
    ) -> dict | None:
        try:
            prompt_template = load_prompt(HILL_CLIMBER_PROMPT_PATH)
            history_lines = []
            for it in iteration_history:
                score_str = f"{it.candidate_score:.4f}" if it.candidate_score is not None else "crash"
                history_lines.append(
                    f"- Iteration {it.iteration}: {it.status} "
                    f"(score: {score_str}, baseline: {it.baseline_score:.4f}) "
                    f"| {it.description}"
                )
            history_block = "\n".join(history_lines) if history_lines else "No prior iterations."

            prompt = (
                prompt_template
                .replace("{{current_code}}", current_code)
                .replace("{{primary_metric}}", self._primary_metric)
                .replace("{{best_score}}", f"{best_score:.4f}")
                .replace("{{best_system}}", best_system)
                .replace("{{iteration_history}}", history_block)
            )

            response = chat(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "Propose the next experiment modification."},
                ],
            )
            content = get_message_content(response).strip()
            if not content:
                return None

            # Extract JSON from response (may have markdown fences)
            json_str = content
            if "```json" in json_str:
                json_str = json_str.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in json_str:
                json_str = json_str.split("```", 1)[1].split("```", 1)[0]

            return json.loads(json_str.strip())
        except Exception as exc:
            logger.error("hill_climber: modification proposal failed: %s", exc)
            return None

    @staticmethod
    def _apply_modification(code: str, patches: list[dict]) -> str | None:
        if not patches:
            return None
        lines = code.splitlines()
        # Apply patches in reverse order to preserve line numbers
        sorted_patches = sorted(patches, key=lambda p: p.get("line_start", 0), reverse=True)
        for patch in sorted_patches:
            op = patch.get("op", "replace")
            line_start = patch.get("line_start", 0) - 1  # convert to 0-based
            line_end = patch.get("line_end", 0) - 1
            new_lines = patch.get("new_lines", [])

            if line_start < 0 or line_start >= len(lines):
                logger.warning("hill_climber: patch line_start %d out of range", line_start + 1)
                continue

            # Check for protected lines
            for check_idx in range(line_start, min(line_end + 1, len(lines))):
                if "SCHOLARFLOW_CONTRACT" in lines[check_idx]:
                    logger.warning("hill_climber: refusing to patch protected line %d", check_idx + 1)
                    return None

            if op == "replace":
                lines[line_start:line_end + 1] = new_lines
            elif op == "insert":
                for offset, new_line in enumerate(new_lines):
                    lines.insert(line_start + offset, new_line)
            elif op == "delete":
                del lines[line_start:line_end + 1]

        return "\n".join(lines)
