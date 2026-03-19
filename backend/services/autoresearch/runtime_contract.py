from __future__ import annotations

import ast
import json
import re
from typing import Any


SEED_ENV_VAR = "SCHOLARFLOW_SEED"
SWEEP_ENV_VAR = "SCHOLARFLOW_SWEEP_JSON"

_SEED_ENV_PATTERN = re.compile(
    r'os\.(?:environ\.get|getenv)\(\s*[\'"]SCHOLARFLOW_SEED[\'"]',
    flags=re.S,
)
_SWEEP_ENV_PATTERN = re.compile(
    r'os\.(?:environ\.get|getenv)\(\s*[\'"]SCHOLARFLOW_SWEEP_JSON[\'"]',
    flags=re.S,
)
_ENV_RECORD_PATTERN = re.compile(
    r'[\'"](seed|sweep)[\'"]\s*:',
    flags=re.S,
)


def runtime_contract_payload() -> dict[str, object]:
    return {
        "seed_env_var": SEED_ENV_VAR,
        "sweep_env_var": SWEEP_ENV_VAR,
        "requirements": [
            f"Read {SEED_ENV_VAR} from the environment and use it as the active seed.",
            f"Read {SWEEP_ENV_VAR} from the environment and parse it with json.loads into a sweep/config dict.",
            "Use the active seed and sweep config in the experiment logic rather than ignoring them.",
            "Record the exact active seed under artifact.environment['seed'].",
            "Record the exact active sweep config under artifact.environment['sweep'].",
        ],
    }


def _is_constant_str(node: ast.AST, value: str) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value == value


def _is_os_environ_get_call(node: ast.AST, env_var: str) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if (
        isinstance(func, ast.Attribute)
        and func.attr == "get"
        and isinstance(func.value, ast.Attribute)
        and func.value.attr == "environ"
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == "os"
    ):
        return bool(node.args) and _is_constant_str(node.args[0], env_var)
    if (
        isinstance(func, ast.Attribute)
        and func.attr == "getenv"
        and isinstance(func.value, ast.Name)
        and func.value.id == "os"
    ):
        return bool(node.args) and _is_constant_str(node.args[0], env_var)
    return False


def _contains_env_access(node: ast.AST, env_var: str) -> bool:
    return any(_is_os_environ_get_call(item, env_var) for item in ast.walk(node))


def _contains_json_loads(node: ast.AST) -> bool:
    return any(
        isinstance(item, ast.Call)
        and isinstance(item.func, ast.Attribute)
        and item.func.attr == "loads"
        and isinstance(item.func.value, ast.Name)
        and item.func.value.id == "json"
        for item in ast.walk(node)
    )


def _assigned_runtime_names(tree: ast.AST) -> tuple[set[str], set[str]]:
    seed_names: set[str] = set()
    sweep_names: set[str] = set()
    for node in ast.walk(tree):
        value: ast.AST | None = None
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            value = node.value
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            targets = [node.target]
        if value is None:
            continue
        names = [target.id for target in targets if isinstance(target, ast.Name)]
        if not names:
            continue
        if _contains_env_access(value, SEED_ENV_VAR):
            seed_names.update(names)
        if _contains_env_access(value, SWEEP_ENV_VAR) and _contains_json_loads(value):
            sweep_names.update(names)
    return seed_names, sweep_names


def _loaded_names(tree: ast.AST) -> set[str]:
    return {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }


def _dict_records_runtime(tree: ast.AST, *, key: str, names: set[str], env_var: str) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for dict_key, value in zip(node.keys, node.values, strict=False):
            if not _is_constant_str(dict_key, key):
                continue
            if isinstance(value, ast.Name) and value.id in names:
                return True
            if _contains_env_access(value, env_var):
                return True
    return False


def missing_runtime_controls(code: str | None) -> list[str]:
    if not code:
        return [
            "seed_env_read",
            "sweep_env_read",
            "sweep_json_parse",
            "seed_runtime_use",
            "sweep_runtime_use",
            "seed_environment_record",
            "sweep_environment_record",
        ]

    missing: list[str] = []
    if _SEED_ENV_PATTERN.search(code) is None:
        missing.append("seed_env_read")
    if _SWEEP_ENV_PATTERN.search(code) is None:
        missing.append("sweep_env_read")
    if "json.loads" not in code:
        missing.append("sweep_json_parse")

    try:
        tree = ast.parse(code)
    except SyntaxError:
        if "seed_env_read" not in missing:
            missing.append("seed_runtime_use")
            missing.append("seed_environment_record")
        if "sweep_env_read" not in missing or "sweep_json_parse" not in missing:
            missing.append("sweep_runtime_use")
            missing.append("sweep_environment_record")
        return missing

    seed_names, sweep_names = _assigned_runtime_names(tree)
    loaded_names = _loaded_names(tree)
    if not seed_names or not any(name in loaded_names for name in seed_names):
        missing.append("seed_runtime_use")
    if not sweep_names or not any(name in loaded_names for name in sweep_names):
        missing.append("sweep_runtime_use")
    if not _dict_records_runtime(tree, key="seed", names=seed_names, env_var=SEED_ENV_VAR):
        missing.append("seed_environment_record")
    if not _dict_records_runtime(tree, key="sweep", names=sweep_names, env_var=SWEEP_ENV_VAR):
        missing.append("sweep_environment_record")
    return missing


def protected_runtime_line_numbers(code: str | None) -> set[int]:
    if not code:
        return set()
    protected: set[int] = set()
    for index, line in enumerate(code.splitlines(), start=1):
        if _SEED_ENV_PATTERN.search(line) or _SWEEP_ENV_PATTERN.search(line):
            protected.add(index)
            continue
        if _ENV_RECORD_PATTERN.search(line) and ("SEED" in line or "SWEEP" in line):
            protected.add(index)
    return protected


def _normalize_sweep(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def runtime_environment_violations(
    environment: dict[str, Any] | None,
    *,
    expected_seed: int,
    expected_sweep: dict[str, Any],
) -> list[str]:
    if not isinstance(environment, dict):
        return ["environment_missing", "seed_mismatch", "sweep_mismatch"]

    violations: list[str] = []
    seed_value = environment.get("seed")
    try:
        normalized_seed = int(seed_value)
    except Exception:
        normalized_seed = None
    if normalized_seed != expected_seed:
        violations.append("seed_mismatch")

    sweep_value = _normalize_sweep(environment.get("sweep"))
    if sweep_value != expected_sweep:
        violations.append("sweep_mismatch")
    return violations
