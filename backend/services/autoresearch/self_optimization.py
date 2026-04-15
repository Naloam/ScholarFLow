"""Self-Optimization Trace — FARS pattern.

Meta-experiment layer that reviews prior experiment results,
identifies issues (model capacity, sampling diversity, bugs),
and produces a refined configuration for the next iteration.
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


class SelfOptimizationTrace:
    """Analyze experiment results and suggest improvements for next iteration."""

    def analyze_and_suggest(
        self,
        *,
        artifact,
        attempts=None,
        spec=None,
        plan=None,
        round_index: int = 1,
        max_rounds: int = 3,
    ) -> dict:
        """Analyze current results and produce improvement suggestions.

        Returns dict with:
        - issues_found: list of identified issues
        - suggestions: list of concrete improvement actions
        - severity: overall assessment (good/needs_improvement/critical)
        - should_continue: whether another round is recommended
        - config_changes: suggested configuration modifications
        """
        issues = []
        suggestions = []

        # Analyze failure patterns
        issues.extend(self._check_failures(artifact))

        # Analyze score distribution
        issues.extend(self._check_score_distribution(artifact))

        # Analyze statistical power
        issues.extend(self._check_statistical_power(artifact))

        # Analyze acceptance
        issues.extend(self._check_acceptance(artifact))

        # Generate suggestions from issues
        suggestions = self._generate_suggestions(issues, artifact, spec)

        # Determine severity
        critical_count = sum(1 for i in issues if i["severity"] == "critical")
        warning_count = sum(1 for i in issues if i["severity"] == "warning")

        if critical_count > 0:
            severity = "critical"
        elif warning_count > 2:
            severity = "needs_improvement"
        else:
            severity = "good"

        should_continue = (
            round_index < max_rounds
            and severity != "good"
            and len(suggestions) > 0
        )

        return {
            "issues_found": issues,
            "suggestions": suggestions,
            "severity": severity,
            "should_continue": should_continue,
            "round": round_index,
            "max_rounds": max_rounds,
            "config_changes": self._extract_config_changes(suggestions),
            "summary": self._build_summary(issues, suggestions, severity),
        }

    def _check_failures(self, artifact) -> list[dict]:
        """Check for execution failures."""
        issues = []
        if artifact is None:
            issues.append({
                "category": "execution",
                "severity": "critical",
                "issue": "No artifact produced",
                "detail": "The experiment did not produce a result artifact.",
                "fix": "Review generated code for syntax errors or missing dependencies.",
            })
            return issues

        failed_trials = getattr(artifact, "failed_trials", []) or []
        if failed_trials:
            # Categorize failures
            failure_cats: dict[str, int] = {}
            for trial in failed_trials:
                cat = getattr(trial, "category", "unknown") or "unknown"
                if isinstance(trial, dict):
                    cat = trial.get("category", "unknown")
                failure_cats[cat] = failure_cats.get(cat, 0) + 1

            dominant = max(failure_cats, key=failure_cats.get) if failure_cats else "unknown"
            if len(failed_trials) > 2:
                issues.append({
                    "category": "execution",
                    "severity": "critical" if dominant == "code_failure" else "warning",
                    "issue": f"{len(failed_trials)} failed configurations ({dominant} dominant)",
                    "detail": f"Failure categories: {failure_cats}",
                    "fix": self._failure_fix(dominant),
                })

        return issues

    def _check_score_distribution(self, artifact) -> list[dict]:
        """Check score distribution for anomalies."""
        issues = []
        if artifact is None:
            return issues

        sweep_results = getattr(artifact, "sweep_results", []) or []
        if not sweep_results:
            return issues

        scores = []
        for sweep in sweep_results:
            score = getattr(sweep, "objective_score_mean", None)
            if score is not None:
                scores.append(float(score))

        if len(scores) < 2:
            return issues

        # Check for very small variance (all configs give same result)
        mean_score = sum(scores) / len(scores)
        variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
        if variance < 1e-8 and mean_score > 0:
            issues.append({
                "category": "score_distribution",
                "severity": "warning",
                "issue": "All sweep configurations produce nearly identical scores",
                "detail": f"Variance={variance:.8f}, mean={mean_score:.4f}",
                "fix": "Try more diverse sweep parameters or fundamentally different approaches.",
            })

        # Check for negative scores
        if mean_score < 0:
            issues.append({
                "category": "score_distribution",
                "severity": "warning",
                "issue": "Negative objective score detected",
                "detail": f"Mean score = {mean_score:.4f}",
                "fix": "Check if metric direction is correct. The method may be worse than baseline.",
            })

        # Check for NaN-like values
        objective_score = getattr(artifact, "objective_score", None)
        if objective_score is None:
            issues.append({
                "category": "score_distribution",
                "severity": "warning",
                "issue": "No objective score computed",
                "detail": "Artifact lacks objective_score field",
                "fix": "Ensure experiment code computes and reports objective_score.",
            })

        return issues

    def _check_statistical_power(self, artifact) -> list[dict]:
        """Check if experiments have adequate statistical power."""
        issues = []
        if artifact is None:
            return issues

        sig_tests = getattr(artifact, "significance_tests", []) or []
        if not sig_tests:
            return issues

        underpowered = [
            t for t in sig_tests
            if getattr(t, "adequately_powered", None) is False
        ]
        if underpowered:
            issues.append({
                "category": "statistical_power",
                "severity": "warning",
                "issue": f"{len(underpowered)} significance test(s) are underpowered",
                "detail": "Insufficient seeds for reliable statistical inference",
                "fix": "Increase seed count to at least the recommended_sample_count.",
            })

        return issues

    def _check_acceptance(self, artifact) -> list[dict]:
        """Check acceptance criteria."""
        issues = []
        if artifact is None:
            return issues

        checks = getattr(artifact, "acceptance_checks", []) or []
        if not checks:
            return issues

        failed = [c for c in checks if not getattr(c, "passed", True)]
        if failed:
            criteria = [getattr(c, "criterion", "") for c in failed[:3]]
            issues.append({
                "category": "acceptance",
                "severity": "warning",
                "issue": f"{len(failed)} acceptance check(s) failed",
                "detail": f"Failed: {'; '.join(criteria)}",
                "fix": "Address failed acceptance criteria or adjust criteria if too strict.",
            })

        return issues

    def _generate_suggestions(self, issues, artifact, spec) -> list[dict]:
        """Generate concrete improvement suggestions from identified issues."""
        suggestions = []

        for issue in issues:
            suggestions.append({
                "target_issue": issue["issue"],
                "action": issue["fix"],
                "priority": "high" if issue["severity"] == "critical" else "medium",
            })

        # Add proactive suggestions based on artifact state
        if artifact is not None:
            per_seed = getattr(artifact, "per_seed_results", []) or []
            if len(per_seed) < 3:
                suggestions.append({
                    "target_issue": "Low seed count limits statistical reliability",
                    "action": f"Increase seeds to at least 3 (currently {len(per_seed)})",
                    "priority": "medium",
                })

            sweep_results = getattr(artifact, "sweep_results", []) or []
            if len(sweep_results) <= 1:
                suggestions.append({
                    "target_issue": "Only one sweep configuration tested",
                    "action": "Add at least one alternative sweep configuration for comparison",
                    "priority": "medium",
                })

        return suggestions

    def _failure_fix(self, category: str) -> str:
        """Return fix suggestion for a failure category."""
        fixes = {
            "code_failure": "Review generated code for syntax errors. Consider simpler method.",
            "data_failure": "Check benchmark data loading. Verify field names and types.",
            "environment_failure": "Check sandbox configuration, dependencies, and timeouts.",
            "metric_failure": "Ensure experiment outputs objective_score and system_results.",
            "runtime_contract_failure": "Ensure experiment records SCHOLARFLOW_SEED and SCHOLARFLOW_SWEEP_JSON.",
        }
        return fixes.get(category, "Investigate the failure and adjust approach.")

    def _extract_config_changes(self, suggestions) -> dict:
        """Extract config-level changes from suggestions."""
        changes = {}
        for s in suggestions:
            action = s.get("action", "").lower()
            if "seed" in action:
                changes["seeds"] = [0, 42, 123, 7, 999]
            if "sweep" in action:
                changes["add_sweep"] = True
        return changes

    def _build_summary(self, issues, suggestions, severity) -> str:
        """Build a human-readable summary."""
        if severity == "good":
            return "Experiment results look solid. No critical issues found."
        parts = [f"Self-optimization analysis ({severity}):"]
        for issue in issues[:5]:
            parts.append(f"  - [{issue['severity']}] {issue['issue']}")
        parts.append(f"  Generated {len(suggestions)} improvement suggestions.")
        return "\n".join(parts)

    def trace_to_markdown(self, trace: dict) -> str:
        """Render trace as markdown."""
        lines = ["# Self-Optimization Trace", ""]
        lines.append(f"**Severity**: {trace['severity']}")
        lines.append(f"**Round**: {trace['round']}/{trace['max_rounds']}")
        lines.append(f"**Continue**: {'Yes' if trace['should_continue'] else 'No'}")
        lines.append("")

        if trace["issues_found"]:
            lines.append("## Issues Found")
            for issue in trace["issues_found"]:
                icon = {"critical": "CRITICAL", "warning": "WARNING"}.get(issue["severity"], "INFO")
                lines.append(f"- [{icon}] {issue['issue']}")
                lines.append(f"  Fix: {issue['fix']}")
            lines.append("")

        if trace["suggestions"]:
            lines.append("## Improvement Suggestions")
            for s in trace["suggestions"]:
                lines.append(f"- [{s['priority']}] {s['action']}")
            lines.append("")

        lines.append("## Summary")
        lines.append(trace["summary"])

        return "\n".join(lines)
