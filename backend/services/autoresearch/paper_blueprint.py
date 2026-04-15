"""Paper Blueprint — FARS pattern.

Before writing, generate a blueprint that maps every data source to exactly one
output format (table vs figure), lists all claims, and specifies figure/table
captions and data sources. Prevents redundancy and ensures complete coverage.
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


class PaperBlueprint:
    """Generate a structured paper blueprint mapping data to outputs."""

    def build_blueprint(
        self,
        *,
        plan,
        artifact,
        claim_matrix: dict | None = None,
    ) -> dict:
        """Build the paper blueprint.

        Returns a blueprint dict with:
        - figures: planned figures with data sources
        - tables: planned tables with data sources
        - claims: claims mapped to their supporting output
        - sections: section plan with data assignments
        - data_coverage: which evidence items are assigned to outputs
        """
        figures = self._plan_figures(artifact)
        tables = self._plan_tables(artifact)
        claim_output_map = self._map_claims_to_outputs(
            plan, figures, tables, claim_matrix
        )
        sections = self._plan_sections(plan, figures, tables)
        coverage = self._check_data_coverage(artifact, figures, tables)

        return {
            "figures": figures,
            "tables": tables,
            "claim_output_map": claim_output_map,
            "sections": sections,
            "data_coverage": coverage,
            "total_outputs": len(figures) + len(tables),
            "claims_with_output": sum(1 for c in claim_output_map if c.get("output_ref")),
            "claims_without_output": sum(1 for c in claim_output_map if not c.get("output_ref")),
        }

    def _plan_figures(self, artifact) -> list[dict]:
        """Plan figures from artifact data."""
        figures = []
        if artifact is None:
            return figures

        # Main results comparison figure
        system_results = getattr(artifact, "system_results", []) or []
        if system_results:
            systems = []
            for sr in system_results:
                name = getattr(sr, "system", "") or (sr.get("system", "") if isinstance(sr, dict) else "")
                systems.append(name)
            if systems:
                figures.append({
                    "id": "fig_main_results",
                    "title": "Main Results Comparison",
                    "caption": f"Comparison of {', '.join(systems[:4])} on the primary metric.",
                    "data_source": "system_results",
                    "chart_type": "bar_chart",
                    "assigned_claim": "primary_performance",
                })

        # Sweep analysis figure
        sweep_results = getattr(artifact, "sweep_results", []) or []
        if len(sweep_results) > 1:
            figures.append({
                "id": "fig_sweep_comparison",
                "title": "Sweep Configuration Analysis",
                "caption": f"Performance across {len(sweep_results)} sweep configurations.",
                "data_source": "sweep_results",
                "chart_type": "line_chart",
                "assigned_claim": "sweep_stability",
            })

        # Significance heatmap
        sig_tests = getattr(artifact, "significance_tests", []) or []
        if len(sig_tests) >= 2:
            figures.append({
                "id": "fig_significance",
                "title": "Statistical Significance Map",
                "caption": "Paired significance test results with Holm-Bonferroni correction.",
                "data_source": "significance_tests",
                "chart_type": "heatmap",
                "assigned_claim": "statistical_rigor",
            })

        # Seed stability figure
        per_seed = getattr(artifact, "per_seed_results", []) or []
        if len(per_seed) >= 3:
            figures.append({
                "id": "fig_seed_stability",
                "title": "Cross-Seed Stability",
                "caption": f"Objective score distribution across {len(per_seed)} random seeds.",
                "data_source": "per_seed_results",
                "chart_type": "box_plot",
                "assigned_claim": "reproducibility",
            })

        return figures

    def _plan_tables(self, artifact) -> list[dict]:
        """Plan tables from artifact data."""
        tables = []
        if artifact is None:
            return tables

        # Main results table
        existing_tables = getattr(artifact, "tables", []) or []
        for i, table in enumerate(existing_tables):
            title = getattr(table, "title", "") or (table.get("title", "") if isinstance(table, dict) else "")
            if "Main Results" in title or "Aggregate" in title:
                tables.append({
                    "id": f"tab_main_{i+1}",
                    "title": title or "Main Results",
                    "caption": f"Primary experimental results. Best scores are bolded.",
                    "data_source": f"artifact.tables[{i}]",
                    "assigned_claim": "primary_performance",
                })
            elif "Significance" in title:
                tables.append({
                    "id": f"tab_sig_{i+1}",
                    "title": title or "Significance Tests",
                    "caption": "Statistical significance test results with adjusted p-values.",
                    "data_source": f"artifact.tables[{i}]",
                    "assigned_claim": "statistical_rigor",
                })
            elif "Ablation" in title or "Sweep" in title:
                tables.append({
                    "id": f"tab_ablation_{i+1}",
                    "title": title or "Ablation Study",
                    "caption": "Component ablation results showing individual contributions.",
                    "data_source": f"artifact.tables[{i}]",
                    "assigned_claim": "ablation_analysis",
                })
            else:
                tables.append({
                    "id": f"tab_other_{i+1}",
                    "title": title or f"Table {i+1}",
                    "caption": f"Experimental data: {title or 'additional results'}.",
                    "data_source": f"artifact.tables[{i}]",
                    "assigned_claim": None,
                })

        # If no tables from artifact, plan a default one
        if not tables:
            system_results = getattr(artifact, "system_results", []) or []
            if system_results:
                tables.append({
                    "id": "tab_default_main",
                    "title": "Main Results",
                    "caption": "Performance comparison across evaluated systems.",
                    "data_source": "system_results",
                    "assigned_claim": "primary_performance",
                })

        return tables

    def _map_claims_to_outputs(
        self, plan, figures, tables, claim_matrix,
    ) -> list[dict]:
        """Map each claim to its supporting figure/table output."""
        claims = []
        hypotheses = getattr(plan, "hypotheses", []) or []
        contributions = getattr(plan, "planned_contributions", []) or []

        all_outputs = [
            {"ref": f"Figure {i+1}", "id": f["id"], "claim": f.get("assigned_claim")}
            for i, f in enumerate(figures)
        ] + [
            {"ref": f"Table {i+1}", "id": t["id"], "claim": t.get("assigned_claim")}
            for i, t in enumerate(tables)
        ]

        for i, hyp in enumerate(hypotheses):
            claim_id = f"claim_h{i+1}"
            output_ref = self._find_output_for_claim(claim_id, all_outputs, hyp)
            claims.append({
                "claim_id": claim_id,
                "claim": hyp,
                "output_ref": output_ref,
            })

        for i, contrib in enumerate(contributions):
            claim_id = f"claim_c{i+1}"
            output_ref = self._find_output_for_claim(claim_id, all_outputs, contrib)
            claims.append({
                "claim_id": claim_id,
                "claim": contrib,
                "output_ref": output_ref,
            })

        return claims

    def _find_output_for_claim(self, claim_id: str, outputs: list[dict], claim_text: str) -> str | None:
        """Find the best output to support a claim."""
        # Direct match on claim type
        for out in outputs:
            if out["claim"] and claim_id.startswith(f"claim_{out['claim'][0]}"):
                return out["ref"]
        # Fallback: first main results output
        for out in outputs:
            if "main" in out["id"].lower():
                return out["ref"]
        return outputs[0]["ref"] if outputs else None

    def _plan_sections(self, plan, figures, tables) -> list[dict]:
        """Plan sections with their assigned data outputs."""
        sections = [
            {"title": "Abstract", "outputs": [], "claims": ["primary_performance"]},
            {"title": "Introduction", "outputs": [], "claims": []},
            {"title": "Related Work", "outputs": [], "claims": []},
            {"title": "Method", "outputs": [], "claims": []},
            {
                "title": "Experimental Setup",
                "outputs": [],
                "claims": [],
            },
            {
                "title": "Results",
                "outputs": [f"Figure {i+1}" for i in range(len(figures))]
                          + [f"Table {i+1}" for i in range(len(tables))],
                "claims": ["primary_performance", "statistical_rigor"],
            },
            {"title": "Discussion", "outputs": [], "claims": ["ablation_analysis"]},
            {"title": "Conclusion", "outputs": [], "claims": []},
        ]
        return sections

    def _check_data_coverage(self, artifact, figures, tables) -> dict:
        """Check how much of the artifact data is covered by planned outputs."""
        if artifact is None:
            return {"coverage": 0.0, "unassigned": [], "total_data_sources": 0}

        data_sources = set()
        if getattr(artifact, "system_results", None):
            data_sources.add("system_results")
        if getattr(artifact, "sweep_results", None):
            data_sources.add("sweep_results")
        if getattr(artifact, "significance_tests", None):
            data_sources.add("significance_tests")
        if getattr(artifact, "per_seed_results", None):
            data_sources.add("per_seed_results")
        if getattr(artifact, "tables", None):
            data_sources.add("tables")
        if getattr(artifact, "negative_results", None):
            data_sources.add("negative_results")
        if getattr(artifact, "failed_trials", None):
            data_sources.add("failed_trials")

        assigned = set()
        for f in figures:
            assigned.add(f["data_source"].split("[")[0].split(".")[0] if "." in f["data_source"] else f["data_source"])
        for t in tables:
            ds = t["data_source"]
            if ds.startswith("artifact."):
                ds = ds.replace("artifact.", "").split("[")[0]
            assigned.add(ds)

        unassigned = data_sources - assigned
        total = len(data_sources) or 1
        return {
            "coverage": len(assigned) / total,
            "unassigned": list(unassigned),
            "total_data_sources": len(data_sources),
        }

    def blueprint_to_markdown(self, blueprint: dict) -> str:
        """Render blueprint as markdown for paper writing context."""
        lines = ["# Paper Blueprint", ""]

        lines.append("## Planned Figures")
        for i, fig in enumerate(blueprint.get("figures", [])):
            lines.append(f"### Figure {i+1}: {fig['title']}")
            lines.append(f"- Caption: {fig['caption']}")
            lines.append(f"- Data source: {fig['data_source']}")
            lines.append(f"- Chart type: {fig['chart_type']}")
            if fig.get("assigned_claim"):
                lines.append(f"- Supports claim: {fig['assigned_claim']}")
            lines.append("")

        lines.append("## Planned Tables")
        for i, tab in enumerate(blueprint.get("tables", [])):
            lines.append(f"### Table {i+1}: {tab['title']}")
            lines.append(f"- Caption: {tab['caption']}")
            lines.append(f"- Data source: {tab['data_source']}")
            if tab.get("assigned_claim"):
                lines.append(f"- Supports claim: {tab['assigned_claim']}")
            lines.append("")

        lines.append("## Claim-Output Mapping")
        for claim in blueprint.get("claim_output_map", []):
            ref = claim.get("output_ref") or "UNASSIGNED"
            lines.append(f"- **{claim['claim_id']}** -> {ref}: {claim['claim'][:80]}")

        coverage = blueprint.get("data_coverage", {})
        lines.append("")
        lines.append(f"**Data coverage: {coverage.get('coverage', 0):.0%}**")
        if coverage.get("unassigned"):
            lines.append(f"Unassigned data sources: {', '.join(coverage['unassigned'])}")

        return "\n".join(lines)
