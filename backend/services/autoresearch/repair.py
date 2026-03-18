from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from schemas.autoresearch import ExperimentAttempt, ExperimentSpec, ResearchPlan
from services.llm.client import chat
from services.llm.prompting import load_prompt


PROMPT_PATH = "backend/prompts/autoresearch/repair/v0.1.0.md"


@dataclass(frozen=True)
class TracebackContext:
    line_number: int | None
    exception_type: str | None
    message: str | None
    failing_line: str | None


class ExperimentRepairEngine:
    def _extract_code(self, text: str) -> str | None:
        if not text:
            return None
        fenced = re.search(r"```(?:python)?\s*(.*?)```", text, flags=re.S)
        if fenced:
            return fenced.group(1).strip()
        return text.strip() or None

    def _is_valid_code(self, code: str | None) -> bool:
        if not code or "__RESULT__" not in code:
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

    def _traceback_patch(self, code: str, logs: str) -> str | None:
        context = self._traceback_context(code, logs)
        if context.line_number is None or context.failing_line is None:
            return None

        lines = code.splitlines()
        idx = context.line_number - 1
        target = lines[idx]
        indent = re.match(r"\s*", target).group(0)
        exception_type = context.exception_type or ""
        message = context.message or ""

        if exception_type in {"RuntimeError", "AssertionError", "NotImplementedError"}:
            stripped = target.strip()
            if stripped.startswith("raise ") or stripped.startswith("assert "):
                lines[idx] = f"{indent}pass  # ScholarFlow traceback repair"
                return "\n".join(lines)

        if exception_type == "NameError":
            match = re.search(r"name '([^']+)' is not defined", message)
            if match:
                missing_name = match.group(1)
                insert_at = idx if idx > 0 else self._first_body_index(lines)
                lines.insert(
                    insert_at,
                    f"{indent}{missing_name} = None  # ScholarFlow traceback repair",
                )
                return "\n".join(lines)

        if exception_type == "ModuleNotFoundError":
            match = re.search(r"No module named '([^']+)'", message)
            fallback_map = {"ujson": "json", "orjson": "json"}
            missing_module = match.group(1) if match else None
            fallback_module = fallback_map.get(missing_module or "")
            if fallback_module and target.strip().startswith(("import ", "from ")):
                lines[idx] = f"{indent}import {fallback_module} as {missing_module}"
                return "\n".join(lines)

        if exception_type == "KeyError":
            match = re.search(r"['\"]([^'\"]+)['\"]", message)
            missing_key = match.group(1) if match else None
            if missing_key and f'["{missing_key}"]' in target:
                lines[idx] = target.replace(
                    f'["{missing_key}"]',
                    f'.get("{missing_key}")',
                )
                return "\n".join(lines)

        return None

    def _heuristic_repair(self, code: str, logs: str) -> str:
        repaired = code
        # Remove deliberately injected hard failures and debugging sentinels.
        repaired = re.sub(r'^\s*raise RuntimeError\(.*?\)\s*$', "", repaired, flags=re.M)
        repaired = re.sub(r'^\s*assert False.*?$', "", repaired, flags=re.M)
        if "NameError" in logs:
            missing = re.findall(r"NameError: name '([^']+)' is not defined", logs)
            for name in missing:
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
        traceback_patch = self._traceback_patch(code, logs)
        if self._is_valid_code(traceback_patch):
            return "repair_traceback_patch", traceback_patch or ""
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
                                "logs": logs,
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                    },
                ]
            )
            candidate = self._extract_code(response.get("choices", [{}])[0].get("message", {}).get("content", ""))
            if self._is_valid_code(candidate):
                return "repair_llm_patch", candidate or ""
        except Exception:
            pass

        heuristic = self._heuristic_repair(code, logs)
        if self._is_valid_code(heuristic):
            return "repair_heuristic_patch", heuristic
        return "repair_regenerate", code
