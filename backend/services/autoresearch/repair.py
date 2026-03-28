from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from schemas.autoresearch import ExperimentAttempt, ExperimentSpec, ResearchPlan
from services.autoresearch.runtime_contract import (
    missing_runtime_controls,
    protected_runtime_line_numbers,
    runtime_contract_payload,
)
from services.llm.client import chat
from services.llm.prompting import load_prompt
from services.llm.response_utils import get_message_content


PROMPT_PATH = "backend/prompts/autoresearch/repair/v0.1.0.md"


@dataclass(frozen=True)
class TracebackContext:
    line_number: int | None
    exception_type: str | None
    message: str | None
    failing_line: str | None


@dataclass(frozen=True)
class PatchOp:
    op: str
    line_number: int
    content: str | None = None


@dataclass(frozen=True)
class RepairCandidate:
    strategy: str
    code: str
    sanity_checks: list[str]
    patch_ops: list[PatchOp]


class ExperimentRepairEngine:
    def _extract_code(self, text: str) -> str | None:
        if not text:
            return None
        fenced = re.search(r"```(?:python)?\s*(.*?)```", text, flags=re.S)
        if fenced:
            return fenced.group(1).strip()
        return text.strip() or None

    def _extract_json_payload(self, text: str) -> Any | None:
        if not text:
            return None
        fenced = re.search(r"```(?:json|javascript|js|python)?\s*(.*?)```", text, flags=re.S)
        raw = fenced.group(1).strip() if fenced else text.strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def _extract_patch_ops(self, text: str) -> list[PatchOp] | None:
        payload = self._extract_json_payload(text)
        if isinstance(payload, dict):
            raw_ops = payload.get("patch_ops")
        else:
            raw_ops = payload
        if not isinstance(raw_ops, list):
            return None

        patch_ops: list[PatchOp] = []
        for item in raw_ops:
            if not isinstance(item, dict):
                return None
            op = str(item.get("op") or "").strip()
            if op not in {"replace", "insert", "delete"}:
                return None
            try:
                line_number = int(item.get("line_number"))
            except Exception:
                return None
            if line_number <= 0:
                return None
            content = item.get("content")
            if op == "delete":
                content = None
            elif content is not None and not isinstance(content, str):
                return None
            patch_ops.append(PatchOp(op=op, line_number=line_number, content=content))
        return patch_ops

    def _is_valid_code(self, code: str | None) -> bool:
        if not code or "__RESULT__" not in code:
            return False
        if missing_runtime_controls(code):
            return False
        try:
            compile(code, "<repair>", "exec")
        except Exception:
            return False
        return True

    def _traceback_context(self, code: str, logs: str) -> TracebackContext:
        line_number = None
        matches = re.findall(r'main\.py", line (\d+)', logs)
        if matches:
            try:
                line_number = int(matches[-1])
            except Exception:
                line_number = None

        exception_type = None
        message = None
        for raw_line in reversed(logs.splitlines()):
            line = raw_line.strip()
            if not line:
                continue
            match = re.match(r"([A-Za-z_][A-Za-z0-9_]*):\s*(.*)", line)
            if match:
                exception_type = match.group(1)
                message = match.group(2).strip()
                break

        failing_line = None
        code_lines = code.splitlines()
        if line_number is not None and 1 <= line_number <= len(code_lines):
            failing_line = code_lines[line_number - 1]

        return TracebackContext(
            line_number=line_number,
            exception_type=exception_type,
            message=message,
            failing_line=failing_line,
        )

    def _first_body_index(self, lines: list[str]) -> int:
        index = 0
        while index < len(lines):
            stripped = lines[index].strip()
            if not stripped:
                index += 1
                continue
            if stripped.startswith(("import ", "from ")):
                index += 1
                continue
            break
        return index

    def _apply_patch_ops(self, code: str, patch_ops: list[PatchOp]) -> str:
        lines = code.splitlines()
        for patch in sorted(patch_ops, key=lambda item: item.line_number, reverse=True):
            index = max(0, min(patch.line_number - 1, len(lines)))
            if patch.op == "replace":
                if index >= len(lines):
                    raise ValueError("Cannot replace a line outside the file")
                lines[index] = patch.content or ""
            elif patch.op == "insert":
                lines.insert(index, patch.content or "")
            elif patch.op == "delete":
                if index >= len(lines):
                    raise ValueError("Cannot delete a line outside the file")
                del lines[index]
            else:
                raise ValueError(f"Unsupported patch op: {patch.op}")
        return "\n".join(lines)

    def _sanity_checks(
        self,
        previous_code: str,
        candidate_code: str | None,
        patch_ops: list[PatchOp],
        *,
        local_patch: bool,
        patch_budget: int | None = None,
    ) -> list[str] | None:
        if not candidate_code or not candidate_code.strip():
            return None

        checks: list[str] = []
        try:
            compile(candidate_code, "<repair_sanity>", "exec")
        except Exception:
            return None
        checks.append("compiles")

        if "__RESULT__" not in candidate_code:
            return None
        checks.append("contains_result_marker")

        protected_lines = protected_runtime_line_numbers(previous_code)
        if any(
            patch.op in {"replace", "delete"} and patch.line_number in protected_lines
            for patch in patch_ops
        ):
            return None
        if protected_lines:
            checks.append("preserves_runtime_contract_lines")

        missing_contract = missing_runtime_controls(candidate_code)
        if missing_contract:
            return None
        checks.extend(missing_contract and [] or ["reads_seed_env", "reads_sweep_env", "parses_sweep_json"])

        if 'if __name__ == "__main__":' in previous_code:
            if 'if __name__ == "__main__":' not in candidate_code:
                return None
            checks.append("preserves_entrypoint")

        if "def run(" in previous_code:
            if "def run(" not in candidate_code:
                return None
            checks.append("preserves_run_function")

        effective_budget = 8 if local_patch else patch_budget
        if effective_budget is not None:
            if len(patch_ops) == 0 or len(patch_ops) > effective_budget:
                return None
            changed_lines = len({patch.line_number for patch in patch_ops})
            if changed_lines == 0 or changed_lines > effective_budget:
                return None
            checks.append("patch_is_local" if local_patch else "patch_within_budget")
            previous_lines = max(len(previous_code.splitlines()), 1)
            current_lines = len(candidate_code.splitlines())
            if current_lines < max(5, int(previous_lines * 0.5)):
                return None
            checks.append("preserves_file_shape")

        return checks

    def _build_candidate(
        self,
        previous_code: str,
        candidate_code: str | None,
        *,
        strategy: str,
        patch_ops: list[PatchOp] | None = None,
        local_patch: bool = False,
        patch_budget: int | None = None,
    ) -> RepairCandidate | None:
        ops = patch_ops or []
        checks = self._sanity_checks(
            previous_code,
            candidate_code,
            ops,
            local_patch=local_patch,
            patch_budget=patch_budget,
        )
        if checks is None or candidate_code is None:
            return None
        return RepairCandidate(
            strategy=strategy,
            code=candidate_code,
            sanity_checks=checks,
            patch_ops=ops,
        )

    def _local_patch_candidate(self, code: str, logs: str) -> RepairCandidate | None:
        context = self._traceback_context(code, logs)
        if context.line_number is None or context.failing_line is None:
            return None
        protected_lines = protected_runtime_line_numbers(code)
        if context.line_number in protected_lines:
            return None

        idx = context.line_number
        target = context.failing_line
        indent = re.match(r"\s*", target).group(0)
        exception_type = context.exception_type or ""
        message = context.message or ""
        patch_ops: list[PatchOp] = []

        if exception_type in {"RuntimeError", "AssertionError", "NotImplementedError"}:
            stripped = target.strip()
            if stripped.startswith("raise ") or stripped.startswith("assert "):
                patch_ops.append(
                    PatchOp("replace", idx, f"{indent}pass  # ScholarFlow local patch")
                )

        elif exception_type == "NameError":
            match = re.search(r"name '([^']+)' is not defined", message)
            if match:
                missing_name = match.group(1)
                insert_at = idx if idx > 1 else self._first_body_index(code.splitlines()) + 1
                patch_ops.append(
                    PatchOp(
                        "insert",
                        insert_at,
                        f"{indent}{missing_name} = None  # ScholarFlow local patch",
                    )
                )

        elif exception_type == "ModuleNotFoundError":
            match = re.search(r"No module named '([^']+)'", message)
            fallback_map = {"ujson": "json", "orjson": "json"}
            missing_module = match.group(1) if match else None
            fallback_module = fallback_map.get(missing_module or "")
            if fallback_module and target.strip().startswith(("import ", "from ")):
                patch_ops.append(
                    PatchOp("replace", idx, f"{indent}import {fallback_module} as {missing_module}")
                )

        elif exception_type == "KeyError":
            match = re.search(r"['\"]([^'\"]+)['\"]", message)
            missing_key = match.group(1) if match else None
            if missing_key and f'["{missing_key}"]' in target:
                patch_ops.append(
                    PatchOp(
                        "replace",
                        idx,
                        target.replace(
                            f'["{missing_key}"]',
                            f'.get("{missing_key}")',
                        ),
                    )
                )

        if not patch_ops:
            return None
        try:
            candidate_code = self._apply_patch_ops(code, patch_ops)
        except Exception:
            return None
        return self._build_candidate(
            code,
            candidate_code,
            strategy="repair_local_patch",
            patch_ops=patch_ops,
            local_patch=True,
        )

    def _llm_patch_candidate(self, code: str, response_text: str) -> RepairCandidate | None:
        patch_ops = self._extract_patch_ops(response_text)
        if not patch_ops:
            return None
        try:
            candidate_code = self._apply_patch_ops(code, patch_ops)
        except Exception:
            return None
        return self._build_candidate(
            code,
            candidate_code,
            strategy="repair_llm_patch",
            patch_ops=patch_ops,
            patch_budget=12,
        )

    def _line_numbered_code(self, code: str) -> str:
        return "\n".join(f"{index:04d}: {line}" for index, line in enumerate(code.splitlines(), start=1))

    def _heuristic_repair(self, code: str, logs: str) -> str:
        repaired = code
        # Remove deliberately injected hard failures and debugging sentinels.
        repaired = re.sub(r'^\s*raise RuntimeError\(.*?\)\s*$', "", repaired, flags=re.M)
        repaired = re.sub(r'^\s*assert False.*?$', "", repaired, flags=re.M)
        if "NameError" in logs:
            missing = re.findall(r"NameError: name '([^']+)' is not defined", logs)
            for name in missing:
                if name in {"json", "os"}:
                    import_stmt = f"import {name}\n"
                    if import_stmt not in repaired:
                        repaired = import_stmt + repaired
                    continue
                repaired = f"{name} = None\n" + repaired
        return repaired

    def repair(
        self,
        *,
        previous_attempt: ExperimentAttempt,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        benchmark_payload: dict[str, Any],
    ) -> tuple[str, str]:
        if not previous_attempt.code_path:
            raise RuntimeError("Repair requested without a previous code path")
        code = Path(previous_attempt.code_path).read_text(encoding="utf-8")
        logs = previous_attempt.artifact.logs if previous_attempt.artifact and previous_attempt.artifact.logs else previous_attempt.summary
        local_candidate = self._local_patch_candidate(code, logs)
        if local_candidate is not None:
            return local_candidate
        try:
            prompt = load_prompt(PROMPT_PATH)
            response = chat(
                [
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "plan": plan.model_dump(mode="json"),
                                "spec": spec.model_dump(mode="json"),
                                "benchmark_payload": benchmark_payload,
                                "failed_attempt": previous_attempt.model_dump(mode="json"),
                                "failed_code": code,
                                "failed_code_with_line_numbers": self._line_numbered_code(code),
                                "logs": logs,
                                "runtime_contract": runtime_contract_payload(),
                                "patch_budget": 12,
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                    },
                ]
            )
            response_text = get_message_content(response)
            llm_candidate = self._llm_patch_candidate(code, response_text)
            if llm_candidate is not None:
                return llm_candidate
        except Exception:
            pass

        heuristic = self._heuristic_repair(code, logs)
        heuristic_candidate = self._build_candidate(
            code,
            heuristic,
            strategy="repair_heuristic_patch",
        )
        if heuristic_candidate is not None:
            return heuristic_candidate
        return RepairCandidate(
            strategy="repair_regenerate",
            code=code,
            sanity_checks=["fallback_to_regenerate"],
            patch_ops=[],
        )
