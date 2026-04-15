"""Claims-Evidence Matrix — ARIS pattern.

Every claim in the paper must map to concrete experimental evidence.
The matrix is built before paper writing and enforced during section generation.
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


class ClaimEvidenceMatrix:
    """Build and validate a claims-evidence matrix from research plan and artifact."""

    def build_matrix(
        self,
        *,
        plan,
        artifact,
        attempts=None,
        literature=None,
    ) -> dict:
        """Build a structured claims-evidence matrix.

        Returns dict with:
        - claims: list of {id, claim, evidence_refs, support_status}
        - coverage_score: float 0-1
        - unsupported_claims: list
        - evidence_utilization: how much evidence is mapped to claims
        """
        claims = self._extract_claims(plan)
        evidence_items = self._extract_evidence(artifact, attempts)

        matrix_entries = []
        for claim_entry in claims:
            claim_id = claim_entry["id"]
            claim_text = claim_entry["claim"]
            supporting = self._match_evidence(claim_text, evidence_items)
            status = "supported" if supporting else "unsupported"
            if supporting and len(supporting) < len(evidence_items) * 0.3:
                status = "partially_supported"
            matrix_entries.append({
                "claim_id": claim_id,
                "claim": claim_text,
                "evidence_refs": [e["id"] for e in supporting],
                "evidence_summary": [e["summary"] for e in supporting],
                "support_status": status,
                "section_hint": claim_entry.get("section_hint", ""),
            })

        supported_count = sum(1 for e in matrix_entries if e["support_status"] == "supported")
        total = len(matrix_entries) or 1
        all_evidence_ids = set()
        for e in matrix_entries:
            all_evidence_ids.update(e["evidence_refs"])
        utilization = len(all_evidence_ids) / max(len(evidence_items), 1)

        return {
            "claims": matrix_entries,
            "total_claims": len(matrix_entries),
            "supported_claims": supported_count,
            "unsupported_claims": [
                e for e in matrix_entries if e["support_status"] == "unsupported"
            ],
            "coverage_score": supported_count / total,
            "evidence_utilization": utilization,
            "evidence_items": evidence_items,
        }

    def _extract_claims(self, plan) -> list[dict]:
        """Extract testable claims from research plan."""
        claims = []

        # From hypotheses
        for i, hyp in enumerate(getattr(plan, "hypotheses", []) or []):
            claims.append({
                "id": f"claim_h{i+1}",
                "claim": hyp,
                "section_hint": "Results",
                "source": "hypothesis",
            })

        # From planned contributions
        for i, contrib in enumerate(getattr(plan, "planned_contributions", []) or []):
            claims.append({
                "id": f"claim_c{i+1}",
                "claim": contrib,
                "section_hint": "Conclusion",
                "source": "contribution",
            })

        # From research questions (as expected evidence)
        for i, q in enumerate(getattr(plan, "research_questions", []) or []):
            claims.append({
                "id": f"claim_q{i+1}",
                "claim": f"Experiment addresses: {q}",
                "section_hint": "Experimental Setup",
                "source": "question",
            })

        return claims

    def _extract_evidence(self, artifact, attempts=None) -> list[dict]:
        """Extract evidence items from result artifact."""
        items = []
        if artifact is None:
            return items

        # From system results
        for i, sr in enumerate(getattr(artifact, "system_results", []) or []):
            system = getattr(sr, "system", "") or (sr.get("system", "") if isinstance(sr, dict) else "")
            metrics = getattr(sr, "metrics", {}) or (sr.get("metrics", {}) if isinstance(sr, dict) else {})
            if metrics:
                metric_str = ", ".join(f"{k}={v:.4f}" if isinstance(v, (int, float)) else f"{k}={v}"
                                       for k, v in list(metrics.items())[:5])
                items.append({
                    "id": f"ev_sr{i+1}",
                    "summary": f"System '{system}': {metric_str}",
                    "keywords": self._keywords(f"{system} {' '.join(str(v) for v in metrics.values())}"),
                    "type": "system_result",
                })

        # From significance tests
        for i, st in enumerate(getattr(artifact, "significance_tests", []) or []):
            candidate = getattr(st, "candidate", "") or (st.get("candidate", "") if isinstance(st, dict) else "")
            comparator = getattr(st, "comparator", "") or (st.get("comparator", "") if isinstance(st, dict) else "")
            effect = getattr(st, "effect_size", None) or (st.get("effect_size") if isinstance(st, dict) else None)
            p_val = getattr(st, "p_value", None) or (st.get("p_value") if isinstance(st, dict) else None)
            items.append({
                "id": f"ev_sig{i+1}",
                "summary": f"Significance: {candidate} vs {comparator}, effect={effect}, p={p_val}",
                "keywords": self._keywords(f"{candidate} {comparator} significant effect"),
                "type": "significance_test",
            })

        # From key findings
        for i, finding in enumerate(getattr(artifact, "key_findings", []) or []):
            items.append({
                "id": f"ev_kf{i+1}",
                "summary": finding[:200] if finding else "",
                "keywords": self._keywords(finding or ""),
                "type": "key_finding",
            })

        # From tables
        for i, table in enumerate(getattr(artifact, "tables", []) or []):
            title = getattr(table, "title", "") or (table.get("title", "") if isinstance(table, dict) else "")
            items.append({
                "id": f"ev_tab{i+1}",
                "summary": f"Table: {title}",
                "keywords": self._keywords(title),
                "type": "table",
            })

        # From sweep results
        for i, sweep in enumerate(getattr(artifact, "sweep_results", []) or []):
            label = getattr(sweep, "label", "") or (sweep.get("label", "") if isinstance(sweep, dict) else "")
            score = getattr(sweep, "objective_score_mean", None)
            items.append({
                "id": f"ev_sweep{i+1}",
                "summary": f"Sweep '{label}': objective_score={score}",
                "keywords": self._keywords(f"sweep {label}"),
                "type": "sweep_result",
            })

        return items

    def _match_evidence(self, claim_text: str, evidence_items: list[dict]) -> list[dict]:
        """Match a claim to supporting evidence via keyword overlap."""
        claim_keywords = self._keywords(claim_text)
        if not claim_keywords:
            return []

        matched = []
        for item in evidence_items:
            ev_keywords = item.get("keywords", set())
            overlap = claim_keywords & ev_keywords
            # Require at least 2 keyword overlap or 30% of claim keywords
            if len(overlap) >= 2 or (claim_keywords and len(overlap) / len(claim_keywords) >= 0.3):
                matched.append(item)

        return matched

    def _keywords(self, text: str) -> set[str]:
        """Extract meaningful keywords from text."""
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "can", "shall", "to", "of", "in", "for",
            "on", "with", "at", "by", "from", "as", "into", "about", "it", "its",
            "this", "that", "these", "those", "and", "or", "but", "not", "no",
            "we", "our", "us", "which", "what", "how", "when", "where", "why",
            "if", "then", "than", "so", "such", "more", "most", "also", "very",
            "just", "only", "each", "every", "all", "both", "few", "some", "any",
        }
        words = re.findall(r"[a-z]{3,}", text.lower())
        return {w for w in words if w not in stop_words}

    def matrix_to_markdown(self, matrix: dict) -> str:
        """Render matrix as markdown table for paper context."""
        lines = [
            "# Claims-Evidence Matrix",
            "",
            f"| Claim | Status | Evidence |",
            f"|-------|---------|----------|",
        ]
        for entry in matrix.get("claims", []):
            status_icon = {
                "supported": "YES",
                "partially_supported": "PARTIAL",
                "unsupported": "NO",
            }.get(entry["support_status"], "?")
            evidence_str = "; ".join(entry["evidence_summary"][:2]) or "None"
            if len(evidence_str) > 80:
                evidence_str = evidence_str[:77] + "..."
            claim_short = entry["claim"][:60] + ("..." if len(entry["claim"]) > 60 else "")
            lines.append(f"| {claim_short} | {status_icon} | {evidence_str} |")

        lines.append("")
        coverage = matrix.get("coverage_score", 0)
        lines.append(f"**Coverage: {coverage:.0%} ({matrix.get('supported_claims', 0)}/{matrix.get('total_claims', 0)} claims supported)**")

        unsupported = matrix.get("unsupported_claims", [])
        if unsupported:
            lines.append("")
            lines.append("## Unsupported Claims")
            for entry in unsupported:
                lines.append(f"- **{entry['claim_id']}**: {entry['claim'][:100]}")

        return "\n".join(lines)
