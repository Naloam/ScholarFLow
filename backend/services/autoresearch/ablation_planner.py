"""Ablation Planner — ARIS pattern.

Automatically design ablation experiments: component ablations first,
hyperparameter sensitivity second, then design choice comparisons.
Also outputs "unnecessary ablations" to skip, saving compute.
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


class AblationPlanner:
    """Plan systematic ablation experiments for a research candidate."""

    def plan_ablations(
        self,
        *,
        plan,
        spec,
        artifact=None,
    ) -> dict:
        """Generate a complete ablation plan.

        Returns dict with:
        - component_ablations: ablations that remove/replace core components
        - hyperparameter_ablations: sensitivity analysis experiments
        - design_choice_ablations: alternative design decisions
        - unnecessary_ablations: explicitly NOT needed (to save compute)
        - suggested_order: execution priority
        - estimated_compute: relative cost estimate
        """
        proposed_method = getattr(plan, "proposed_method", "") or ""
        hypotheses = getattr(plan, "hypotheses", []) or []
        task_family = getattr(plan, "task_family", "") or "text_classification"

        component = self._plan_component_ablations(proposed_method, task_family, artifact)
        hyperparam = self._plan_hyperparameter_ablations(spec, task_family)
        design = self._plan_design_choices(proposed_method, task_family)
        unnecessary = self._identify_unnecessary(component, hyperparam)

        all_ablations = component + hyperparam + design
        ordered = self._prioritize_ablations(all_ablations)
        total_compute = sum(a.get("compute_cost", 1) for a in ordered)

        return {
            "component_ablations": component,
            "hyperparameter_ablations": hyperparam,
            "design_choice_ablations": design,
            "unnecessary_ablations": unnecessary,
            "suggested_order": [a["name"] for a in ordered],
            "all_ablations": ordered,
            "estimated_compute": total_compute,
            "total_planned": len(ordered),
        }

    def _plan_component_ablations(self, method: str, task_family: str, artifact) -> list[dict]:
        """Plan ablations that remove or replace core method components."""
        ablations = []

        method_lower = method.lower()

        # Extract method components from the description
        components = self._extract_components(method_lower, task_family)

        for comp in components:
            ablations.append({
                "name": f"remove_{comp['id']}",
                "type": "component",
                "what_it_tests": comp["description"],
                "expected_if_matters": comp["expected_drop"],
                "expected_if_not": "No significant change in primary metric",
                "priority": comp["priority"],
                "compute_cost": 1,
                "implementation": comp["implementation"],
            })

        # Always include a "random baseline" ablation
        ablations.append({
            "name": "random_baseline",
            "type": "component",
            "what_it_tests": "Whether the method does anything beyond random guessing",
            "expected_if_matters": "Random baseline significantly worse",
            "expected_if_not": "Method provides no real signal",
            "priority": 5,
            "compute_cost": 1,
            "implementation": "Replace method predictions with random sampling from label distribution",
        })

        return ablations

    def _plan_hyperparameter_ablations(self, spec, task_family: str) -> list[dict]:
        """Plan hyperparameter sensitivity experiments."""
        ablations = []

        sweeps = getattr(spec, "sweeps", []) or []
        seeds = getattr(spec, "seeds", []) or []

        # Learning rate / key parameter sensitivity
        ablations.append({
            "name": "seed_sensitivity",
            "type": "hyperparameter",
            "what_it_tests": "Robustness to random seed selection",
            "expected_if_matters": "Performance varies >5% across seeds",
            "expected_if_not": "Stable performance across seeds",
            "priority": 3 if len(seeds) >= 3 else 1,
            "compute_cost": len(seeds) if seeds else 3,
            "implementation": f"Run with seeds={seeds or [0, 42, 123]}",
        })

        # If sweeps are defined, plan sweep sensitivity
        if sweeps and len(sweeps) > 1:
            ablations.append({
                "name": "sweep_sensitivity",
                "type": "hyperparameter",
                "what_it_tests": "Sensitivity to hyperparameter configuration",
                "expected_if_matters": "Some configurations significantly outperform others",
                "expected_if_not": "Consistent performance across configurations",
                "priority": 2,
                "compute_cost": len(sweeps),
                "implementation": "Compare all sweep configurations head-to-head",
            })

        # Generic hyperparameters based on task family
        if task_family in ("text_classification", "tabular_classification"):
            for param in ["vocabulary_size", "feature_count", "ngram_range"]:
                ablations.append({
                    "name": f"sensitivity_{param}",
                    "type": "hyperparameter",
                    "what_it_tests": f"Sensitivity to {param} choice",
                    "expected_if_matters": f"Changing {param} causes >3% metric change",
                    "expected_if_not": f"Robust to {param} variation",
                    "priority": 1,
                    "compute_cost": 2,
                    "implementation": f"Vary {param} by +/-50% and compare",
                })
        elif task_family == "ir_reranking":
            for param in ["scoring_weights", "idf_smoothing", "normalization"]:
                ablations.append({
                    "name": f"sensitivity_{param}",
                    "type": "hyperparameter",
                    "what_it_tests": f"Sensitivity to {param} choice",
                    "expected_if_matters": f"Changing {param} causes >3% metric change",
                    "expected_if_not": f"Robust to {param} variation",
                    "priority": 1,
                    "compute_cost": 2,
                    "implementation": f"Vary {param} and compare MRR/recall",
                })

        return ablations

    def _plan_design_choices(self, method: str, task_family: str) -> list[dict]:
        """Plan alternative design decision comparisons."""
        ablations = []

        if "naive bayes" in method or "bayes" in method:
            ablations.append({
                "name": "alt_logistic_regression",
                "type": "design_choice",
                "what_it_tests": "Would a discriminative model work better?",
                "expected_if_matters": "Significant performance gap between generative and discriminative",
                "expected_if_not": "Generative model is adequate for this task",
                "priority": 2,
                "compute_cost": 1,
                "implementation": "Replace Naive Bayes with simple logistic regression",
            })

        if "weighted" in method or "idf" in method:
            ablations.append({
                "name": "alt_unweighted",
                "type": "design_choice",
                "what_it_tests": "Are the weights necessary?",
                "expected_if_matters": "Unweighted version significantly worse",
                "expected_if_not": "Weights add complexity without benefit",
                "priority": 3,
                "compute_cost": 1,
                "implementation": "Remove weighting, use uniform weights",
            })

        if "rerank" in method or "reranking" in method:
            ablations.append({
                "name": "alt_single_stage",
                "type": "design_choice",
                "what_it_tests": "Is the multi-stage approach necessary?",
                "expected_if_matters": "Two-stage approach clearly outperforms single-stage",
                "expected_if_not": "Single-stage is sufficient",
                "priority": 2,
                "compute_cost": 1,
                "implementation": "Use only first-stage retrieval without reranking",
            })

        # If no specific design choices detected, add generic ones
        if not ablations:
            ablations.append({
                "name": "alt_simpler_baseline",
                "type": "design_choice",
                "what_it_tests": "Can a simpler approach achieve similar performance?",
                "expected_if_matters": "Simpler approach is significantly worse",
                "expected_if_not": "Complexity is not justified",
                "priority": 2,
                "compute_cost": 1,
                "implementation": "Replace with simplest possible baseline approach",
            })

        return ablations

    def _extract_components(self, method_lower: str, task_family: str) -> list[dict]:
        """Extract testable components from the method description."""
        components = []

        # Common component patterns
        patterns = [
            ("idf", "IDF weighting", "Score drops without IDF weighting", 3),
            ("tfidf", "TF-IDF features", "Performance drops without TF-IDF", 3),
            ("bigram", "Bigram features", "Score drops without bigram features", 2),
            ("normaliz", "Feature normalization", "Performance degrades without normalization", 2),
            ("weight", "Custom weighting scheme", "Unweighted version performs worse", 3),
            ("pool", "Pooling strategy", "Different pooling changes results", 2),
            ("attention", "Attention mechanism", "Removing attention hurts performance", 3),
            ("dropout", "Dropout regularization", "Overfitting increases without dropout", 2),
            ("embedding", "Embedding layer", "Performance drops without learned embeddings", 3),
            ("scoring", "Scoring function", "Alternative scoring is worse", 2),
        ]

        for keyword, desc, expected, priority in patterns:
            if keyword in method_lower:
                components.append({
                    "id": keyword.replace(" ", "_"),
                    "description": desc,
                    "expected_drop": expected,
                    "priority": priority,
                    "implementation": f"Remove or replace {desc.lower()} component",
                })

        # If no components detected, create generic ones
        if not components:
            components.append({
                "id": "main_method",
                "description": "The core proposed method",
                "expected_drop": "Replacing with majority baseline drops score significantly",
                "priority": 4,
                "implementation": "Replace proposed method with majority/random baseline",
            })

        return components

    def _identify_unnecessary(self, component: list, hyperparam: list) -> list[dict]:
        """Identify ablations that are NOT needed (ARIS pattern).

        Explicitly outputs what to skip to save compute.
        """
        unnecessary = []

        # Skip redundant hyperparameter ablations if already covered
        seen_types = set()
        for ablation in hyperparam:
            ablation_type = ablation["name"].split("_")[0]
            if ablation_type in seen_types:
                unnecessary.append({
                    "name": ablation["name"],
                    "reason": f"Redundant with another {ablation_type} sensitivity test",
                })
            seen_types.add(ablation_type)

        # Skip very low-priority ablations (priority 0 or 1)
        for ablation in component + hyperparam:
            if ablation.get("priority", 3) <= 1 and len(component) > 3:
                unnecessary.append({
                    "name": ablation["name"],
                    "reason": "Low priority — defer unless main results are inconclusive",
                })

        return unnecessary

    def _prioritize_ablations(self, all_ablations: list[dict]) -> list[dict]:
        """Sort ablations by priority (highest first)."""
        return sorted(all_ablations, key=lambda a: a.get("priority", 0), reverse=True)

    def plan_to_markdown(self, plan: dict) -> str:
        """Render ablation plan as markdown."""
        lines = ["# Ablation Study Plan", ""]

        lines.append("## Component Ablations (Priority)")
        for a in plan.get("component_ablations", []):
            lines.append(f"- **{a['name']}** (priority {a['priority']}): {a['what_it_tests']}")
            lines.append(f"  - Implementation: {a['implementation']}")
        lines.append("")

        lines.append("## Hyperparameter Sensitivity")
        for a in plan.get("hyperparameter_ablations", []):
            lines.append(f"- **{a['name']}** (cost {a['compute_cost']}): {a['what_it_tests']}")
        lines.append("")

        lines.append("## Design Choice Comparisons")
        for a in plan.get("design_choice_ablations", []):
            lines.append(f"- **{a['name']}**: {a['what_it_tests']}")
        lines.append("")

        if plan.get("unnecessary_ablations"):
            lines.append("## Unnecessary Ablations (Skip These)")
            for a in plan["unnecessary_ablations"]:
                lines.append(f"- ~~{a['name']}~~: {a['reason']}")
            lines.append("")

        lines.append(f"**Suggested order**: {' -> '.join(plan.get('suggested_order', []))}")
        lines.append(f"**Total estimated compute**: {plan.get('estimated_compute', 0)} run units")

        return "\n".join(lines)
