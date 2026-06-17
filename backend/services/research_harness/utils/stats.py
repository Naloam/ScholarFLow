"""
统计工具函数。
从 services/autoresearch/runner.py 抽取，逻辑不变，仅改为公共接口。
"""
from __future__ import annotations

import itertools
import math
import random

from schemas.autoresearch import ConfidenceIntervalSummary, SignificanceTestResult


# --- 私有辅助：与 runner.py 中保持一致，逻辑不变 ---


def _round_metric(value: float) -> float:
    return round(value, 4)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _sample_std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    center = _mean(values)
    variance = sum((value - center) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance)


_T_CRITICAL_95 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.16,
    14: 2.145,
    15: 2.131,
    16: 2.12,
    17: 2.11,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.08,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.06,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
    30: 2.042,
}


# --- 公共统计接口 ---


def confidence_interval(values: list[float]) -> ConfidenceIntervalSummary | None:
    if not values:
        return None
    center = _mean(values)
    if len(values) == 1:
        return ConfidenceIntervalSummary(
            lower=_round_metric(center),
            upper=_round_metric(center),
        )
    degrees_of_freedom = len(values) - 1
    critical_value = _T_CRITICAL_95.get(degrees_of_freedom, 1.96)
    margin = critical_value * _sample_std(values) / math.sqrt(len(values))
    return ConfidenceIntervalSummary(
        lower=_round_metric(center - margin),
        upper=_round_metric(center + margin),
    )


def paired_sign_flip_test(
    values_a: list[float],
    values_b: list[float],
) -> tuple[float, str, float, int, str]:
    pairs = list(zip(values_a, values_b, strict=False))
    if not pairs:
        return 1.0, "two_sided", 0.0, 0, "paired_sign_flip_exact"
    differences = [left - right for left, right in pairs]
    effect_size = _round_metric(_mean(differences))
    non_zero = [value for value in differences if abs(value) > 1e-12]
    if not non_zero:
        return 1.0, "two_sided", effect_size, len(differences), "paired_sign_flip_exact"

    alternative = "greater" if effect_size >= 0 else "less"
    observed = _mean(non_zero)
    max_exact = 12
    if len(non_zero) <= max_exact:
        flipped_means = [
            _mean([sign * value for sign, value in zip(signs, non_zero, strict=False)])
            for signs in itertools.product((-1.0, 1.0), repeat=len(non_zero))
        ]
        if alternative == "greater":
            extreme = sum(1 for value in flipped_means if value >= observed - 1e-12)
        else:
            extreme = sum(1 for value in flipped_means if value <= observed + 1e-12)
        p_value = extreme / len(flipped_means)
        method = "paired_sign_flip_exact"
    else:
        rng = random.Random(0)
        draws = 4096
        extreme = 0
        for _ in range(draws):
            sampled = _mean([rng.choice((-1.0, 1.0)) * value for value in non_zero])
            if alternative == "greater" and sampled >= observed - 1e-12:
                extreme += 1
            elif alternative == "less" and sampled <= observed + 1e-12:
                extreme += 1
        p_value = extreme / draws
        method = "paired_sign_flip_monte_carlo"
    return _round_metric(p_value), alternative, effect_size, len(differences), method


def paired_differences(values_a: list[float], values_b: list[float]) -> list[float]:
    return [left - right for left, right in zip(values_a, values_b, strict=False)]


def power_style_analysis(differences: list[float]) -> dict[str, object]:
    sample_count = len(differences)
    absolute_effect = abs(_mean(differences)) if differences else 0.0
    if sample_count < 2:
        return {
            "minimum_detectable_effect": None,
            "recommended_sample_count": 4,
            "adequately_powered": False,
            "power_detail": (
                f"Only {sample_count} paired seed(s) were available, so power-style analysis is "
                "advisory only and more paired seeds are recommended."
            ),
        }

    difference_std = _sample_std(differences)
    if difference_std <= 1e-12:
        recommended = 2 if absolute_effect > 0 else 4
        adequately_powered = sample_count >= recommended and absolute_effect > 0
        return {
            "minimum_detectable_effect": 0.0,
            "recommended_sample_count": recommended,
            "adequately_powered": adequately_powered,
            "power_detail": (
                f"Observed paired differences were nearly deterministic across {sample_count} seeds; "
                f"an effect of {absolute_effect:.4f} is already stable under the current design."
                if adequately_powered
                else (
                    f"Observed paired differences were nearly deterministic, but the mean paired delta "
                    f"({absolute_effect:.4f}) is too small to treat the current design as adequately powered."
                )
            ),
        }

    z_alpha_plus_beta = 2.8
    minimum_detectable_effect = z_alpha_plus_beta * difference_std / math.sqrt(sample_count)
    if absolute_effect <= 1e-12:
        recommended_sample_count = 512
    else:
        recommended_sample_count = int(
            max(
                2,
                min(
                    512,
                    math.ceil((z_alpha_plus_beta * difference_std / absolute_effect) ** 2),
                ),
            )
        )
    adequately_powered = sample_count >= recommended_sample_count
    return {
        "minimum_detectable_effect": _round_metric(minimum_detectable_effect),
        "recommended_sample_count": recommended_sample_count,
        "adequately_powered": adequately_powered,
        "power_detail": (
            f"With {sample_count} paired seeds and paired-difference std={difference_std:.4f}, "
            f"the design can reliably detect deltas around {minimum_detectable_effect:.4f}; "
            f"the observed mean delta was {absolute_effect:.4f}."
            + (
                " Current seed coverage is likely adequate."
                if adequately_powered
                else f" Roughly {recommended_sample_count} paired seeds would be safer."
            )
        ),
    }


def holm_bonferroni_adjustment(results: list[SignificanceTestResult]) -> list[SignificanceTestResult]:
    if not results:
        return results
    grouped: dict[str, list[tuple[int, SignificanceTestResult]]] = {}
    for index, item in enumerate(results):
        family = f"{item.scope}:{item.metric}"
        grouped.setdefault(family, []).append((index, item))

    updates: dict[int, dict[str, object]] = {}
    for family, family_results in grouped.items():
        indexed = sorted(family_results, key=lambda item: item[1].p_value)
        running_max = 0.0
        total = len(indexed)
        for position, (original_index, item) in enumerate(indexed, start=1):
            candidate = min(1.0, item.p_value * (total - position + 1))
            running_max = max(running_max, candidate)
            adjusted_alpha = 0.05 / (total - position + 1)
            updates[original_index] = {
                "comparison_family": family,
                "family_size": total,
                "adjusted_p_value": _round_metric(running_max),
                "adjusted_alpha": round(adjusted_alpha, 6),
                "correction": "holm_bonferroni",
                "significant": running_max < 0.05,
            }
    return [
        item.model_copy(update=updates[index])
        for index, item in enumerate(results)
    ]
