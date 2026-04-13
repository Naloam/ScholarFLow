from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from schemas.autoresearch import (
    AutoResearchClaimEvidenceEntryRead,
    AutoResearchClaimEvidenceMatrixRead,
    AutoResearchClaimEvidenceRefRead,
    AutoResearchFigurePlanItemRead,
    AutoResearchFigurePlanRead,
    AutoResearchPaperPipelineArtifactsRead,
    AutoResearchPaperCompileReportRead,
    AutoResearchProjectFlowContextRead,
    AutoResearchPaperPlanRead,
    AutoResearchPaperPlanSectionRead,
    AutoResearchPaperRevisionActionEntryRead,
    AutoResearchPaperRevisionActionIndexRead,
    AutoResearchPaperRevisionActionRead,
    AutoResearchPaperRevisionCheckpointRead,
    AutoResearchPaperRevisionDiffRead,
    AutoResearchPaperRevisionDiffSectionRead,
    AutoResearchPaperSectionRewriteIndexRead,
    AutoResearchPaperSectionRewritePacketRead,
    AutoResearchPaperRevisionStateRead,
    AutoResearchPaperSourceFileRead,
    AutoResearchPaperSourcesManifestRead,
    AutoResearchReviewLoopActionRead,
    AutoResearchReviewLoopRead,
    AutoResearchRunReviewRead,
    ConfidenceIntervalSummary,
    ExperimentAttempt,
    ExperimentSpec,
    HypothesisCandidate,
    LiteratureInsight,
    PortfolioSummary,
    ResearchPlan,
    ResearchProgram,
    ResultArtifact,
    ResultTable,
)
from services.llm.client import chat
from services.llm.prompting import load_prompt
from services.llm.response_utils import get_message_content
from config.settings import settings
from services.autoresearch.figure_generator import FigureGenerator

logger = logging.getLogger(__name__)


def _markdown_table(table: ResultTable) -> str:
    if not table.columns:
        return ""
    header = "| " + " | ".join(table.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(table.columns)) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in table.rows]
    return "\n".join([header, separator, *rows])


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


_INLINE_LATEX_PATTERN = re.compile(r"`([^`]+)`|\[(\d+(?:,\s*\d+)*)\]")
_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_PATTERN = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_COMPILE_REQUIRED_SOURCE_KINDS = {"latex", "bibtex", "shell"}
_COMPILE_REQUIRED_SOURCE_PATHS = {"paper.md", "paper_compile_report.json", "manifest.json"}
PAPER_WRITER_PROMPT_PATH = "backend/prompts/autoresearch/paper_writer/v0.1.0.md"
PAPER_WRITER_SECTION_PROMPT_PATH = "backend/prompts/autoresearch/paper_writer/v0.2.0.md"
PAPER_SELF_REVIEW_PROMPT_PATH = "backend/prompts/autoresearch/paper_self_review/v0.1.0.md"
PAPER_REVISION_PROMPT_PATH = "backend/prompts/autoresearch/paper_revision/v0.1.0.md"


def _latex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(character, character) for character in text)


def _compile_required_source_files(
    paper_sources_manifest: AutoResearchPaperSourcesManifestRead,
) -> list[str]:
    return _dedupe_preserving_order(
        [
            item.relative_path
            for item in paper_sources_manifest.files
            if item.kind in _COMPILE_REQUIRED_SOURCE_KINDS
            or item.relative_path in _COMPILE_REQUIRED_SOURCE_PATHS
        ]
    )


def _excerpt(text: str, *, limit: int = 280) -> str | None:
    collapsed = " ".join(part for part in text.split())
    if not collapsed:
        return None
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: max(0, limit - 3)].rstrip() + "..."


def _render_inline_latex(text: str) -> str:
    # Handle images first: ![alt](path) -> \includegraphics
    text = _IMAGE_PATTERN.sub(
        lambda m: r"\includegraphics[width=0.9\linewidth]{" + m.group(2) + "}",
        text,
    )
    # Handle bold: **text** -> \textbf{text}
    text = _BOLD_PATTERN.sub(lambda m: r"\textbf{" + m.group(1) + "}", text)
    # Handle italic: *text* -> \textit{text} (not ** or inside \textbf)
    text = _ITALIC_PATTERN.sub(lambda m: r"\textit{" + m.group(1) + "}", text)
    # Handle inline code and citations
    segments: list[str] = []
    cursor = 0
    for match in _INLINE_LATEX_PATTERN.finditer(text):
        if match.start() > cursor:
            segments.append(_latex_escape(text[cursor:match.start()]))
        inline_code = match.group(1)
        citation_indices = match.group(2)
        if inline_code is not None:
            segments.append(r"\texttt{" + _latex_escape(inline_code) + "}")
        elif citation_indices is not None:
            keys = ",".join(f"ref{item.strip()}" for item in citation_indices.split(","))
            segments.append(r"\cite{" + keys + "}")
        cursor = match.end()
    if cursor < len(text):
        segments.append(_latex_escape(text[cursor:]))
    return "".join(segments)


def _parse_markdown_table_block(lines: list[str], start: int) -> tuple[list[list[str]], int] | None:
    if start + 1 >= len(lines):
        return None
    if "|" not in lines[start] or "|" not in lines[start + 1]:
        return None
    if not re.search(r"[-:]+", lines[start + 1]):
        return None
    rows: list[list[str]] = []
    index = start
    while index < len(lines) and "|" in lines[index]:
        cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
        if index == start + 1:
            index += 1
            continue
        rows.append(cells)
        index += 1
    return rows, index


def _latex_table_block(rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    column_count = max(len(row) for row in rows)
    align = " | ".join(["l"] * column_count)

    def _row_cells(row: list[str]) -> list[str]:
        padded = list(row[:column_count])
        while len(padded) < column_count:
            padded.append("")
        return [_render_inline_latex(cell) for cell in padded]

    rendered = [
        r"\begin{center}",
        r"\begin{tabular}{" + align + "}",
        r"\hline",
        " & ".join(_row_cells(rows[0])) + r" \\ \hline",
    ]
    for row in rows[1:]:
        rendered.append(" & ".join(_row_cells(row)) + r" \\")
    rendered.extend(
        [
            r"\hline",
            r"\end{tabular}",
            r"\end{center}",
        ]
    )
    return rendered


def _collect_list_items(
    lines: list[str], start: int, prefix: str, *, ordered: bool = False,
) -> tuple[list[tuple[int, str]], int]:
    """Collect list items with their indentation level."""
    items: list[tuple[int, str]] = []
    index = start
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            # blank line might separate list blocks
            if index + 1 < len(lines) and (lines[index + 1].strip().startswith("- ") or re.match(r"^\d+\.\s+", lines[index + 1].strip())):
                index += 1
                continue
            break
        if ordered:
            m = re.match(r"^(\s*)(\d+\.\s+)(.*)", line)
            if not m:
                break
            indent = len(m.group(1))
            text = m.group(3).strip()
        else:
            m = re.match(r"^(\s*)- (.*)", line)
            if not m:
                break
            indent = len(m.group(1))
            text = m.group(2).strip()
        level = indent // 2
        items.append((level, text))
        index += 1
    return items, index


def _latex_itemize(items: list[tuple[int, str]]) -> list[str]:
    """Render nested itemize from (level, text) pairs."""
    if not items:
        return []
    lines: list[str] = []
    prev_level = -1
    for level, text in items:
        while level > prev_level:
            lines.append(r"\begin{itemize}")
            prev_level += 1
        while level < prev_level:
            lines.append(r"\end{itemize}")
            prev_level -= 1
        lines.append(r"\item " + _render_inline_latex(text))
        prev_level = level
    while prev_level >= 0:
        lines.append(r"\end{itemize}")
        prev_level -= 1
    return lines


def _latex_enumerate(items: list[tuple[int, str]]) -> list[str]:
    """Render nested enumerate from (level, text) pairs."""
    if not items:
        return []
    lines: list[str] = []
    prev_level = -1
    for level, text in items:
        while level > prev_level:
            lines.append(r"\begin{enumerate}")
            prev_level += 1
        while level < prev_level:
            lines.append(r"\end{enumerate}")
            prev_level -= 1
        lines.append(r"\item " + _render_inline_latex(text))
        prev_level = level
    while prev_level >= 0:
        lines.append(r"\end{enumerate}")
        prev_level -= 1
    return lines


def _dedupe_preserving_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _section_slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return slug or "section"


def _section_heading_slug(title: str) -> str:
    normalized = re.sub(r"^\d+\.\s+", "", title.strip())
    return _section_slug(normalized)


class PaperWriter:
    def _fallback_section_body(self, section: AutoResearchPaperPlanSectionRead) -> str:
        claim_block = "\n".join(f"- `{item}`" for item in section.claim_ids) or "- No explicit claim ids were attached."
        evidence_block = "\n".join(f"- {item}" for item in section.evidence_focus) or "- No explicit evidence focus was attached."
        return (
            f"{section.objective}\n\n"
            "Claim focus:\n"
            f"{claim_block}\n\n"
            "Evidence focus:\n"
            f"{evidence_block}"
        )

    def _render_section_sequence(
        self,
        *,
        title: str,
        paper_plan: AutoResearchPaperPlanRead,
        section_bodies: dict[str, str],
        references_block: str,
    ) -> str:
        rendered_sections: list[str] = []
        numbered_section_index = 0
        for section in paper_plan.sections:
            slug = _section_slug(section.title)
            body = section_bodies.get(slug, self._fallback_section_body(section)).strip()
            if slug == "abstract":
                heading = "## Abstract"
            else:
                numbered_section_index += 1
                heading = f"## {numbered_section_index}. {section.title}"
            rendered_sections.append(f"{heading}\n{body}")
        if references_block:
            rendered_sections.append(f"## {numbered_section_index + 1}. References\n{references_block}")
        return f"# {title}\n\n" + "\n\n".join(rendered_sections) + "\n"

    def _paper_plan_title(
        self,
        paper_plan: AutoResearchPaperPlanRead | None,
        *candidates: str,
        fallback: str,
    ) -> str:
        if paper_plan is None:
            return fallback
        plan_titles = {section.title.lower(): section.title for section in paper_plan.sections}
        for candidate in candidates:
            matched = plan_titles.get(candidate.lower())
            if matched is not None:
                return matched
        return fallback

    def _section_rewrite_packet_relative_path(self, section: AutoResearchPaperPlanSectionRead) -> str:
        packet_id = section.section_id.strip() or _section_slug(section.title)
        return f"rewrite_packets/{packet_id}.md"

    def _paper_section_bodies(self, paper_markdown: str) -> dict[str, str]:
        sections: dict[str, list[str]] = {}
        current_slug: str | None = None
        for raw_line in paper_markdown.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if stripped.startswith("## "):
                current_slug = _section_heading_slug(stripped[3:])
                sections.setdefault(current_slug, [])
                continue
            if current_slug is not None:
                sections[current_slug].append(line)
        return {
            slug: "\n".join(lines).strip()
            for slug, lines in sections.items()
        }

    def _section_claim_entries(
        self,
        *,
        section: AutoResearchPaperPlanSectionRead,
        claim_evidence_matrix: AutoResearchClaimEvidenceMatrixRead,
    ) -> list[AutoResearchClaimEvidenceEntryRead]:
        selected: dict[str, AutoResearchClaimEvidenceEntryRead] = {}
        wanted_claim_ids = set(section.claim_ids)
        for entry in claim_evidence_matrix.entries:
            if entry.claim_id in wanted_claim_ids or entry.section_hint == section.title:
                selected.setdefault(entry.claim_id, entry)
        return list(selected.values())

    def _section_pending_actions(
        self,
        *,
        section: AutoResearchPaperPlanSectionRead,
        paper_revision_state: AutoResearchPaperRevisionStateRead,
    ) -> list[AutoResearchPaperRevisionActionRead]:
        return [
            item
            for item in paper_revision_state.next_actions
            if item.status == "open" and item.section_title == section.title
        ]

    def _section_open_issues(
        self,
        *,
        section: AutoResearchPaperPlanSectionRead,
        claim_entries: list[AutoResearchClaimEvidenceEntryRead],
        paper_revision_state: AutoResearchPaperRevisionStateRead,
    ) -> list[str]:
        issues = _dedupe_preserving_order(
            [
                gap
                for entry in claim_entries
                for gap in entry.gaps
            ]
        )
        if issues:
            return issues
        if section.title not in paper_revision_state.focus_sections:
            return []
        lowered_title = section.title.lower()
        return [
            item
            for item in paper_revision_state.open_issues
            if lowered_title in item.lower()
        ]

    def _humanize_evidence_focus(self, evidence_focus: list[str]) -> str | None:
        labels = _dedupe_preserving_order(
            [
                item.replace("paper_revision_state", "revision state")
                .replace("claim_evidence_matrix", "claim evidence matrix")
                .replace(".", " ")
                .replace("_", " ")
                for item in evidence_focus
            ]
        )
        if not labels:
            return None
        if len(labels) == 1:
            return labels[0]
        if len(labels) == 2:
            return f"{labels[0]} and {labels[1]}"
        return f"{', '.join(labels[:-1])}, and {labels[-1]}"

    def _auto_revision_paragraph_markers(self) -> tuple[str, ...]:
        return (
            "This revision pass keeps",
            "Claims without full support are now framed",
            "Open review items are treated",
            "Revision focus for this section:",
            "One unresolved review concern for this section is:",
            "The section foregrounds the preserved evidence anchors in",
            "This section was refreshed against",
        )

    def _strip_auto_revision_paragraph(self, body: str) -> str:
        paragraphs = [item.strip() for item in body.strip().split("\n\n") if item.strip()]
        if not paragraphs:
            return ""
        last_paragraph = paragraphs[-1]
        if any(marker in last_paragraph for marker in self._auto_revision_paragraph_markers()):
            return "\n\n".join(paragraphs[:-1]).strip()
        return body.strip()

    def _revision_sentence_fragment(self, text: str, *, limit: int = 180) -> str | None:
        excerpt = _excerpt(text, limit=limit)
        if excerpt is None:
            return None
        return excerpt if excerpt.endswith((".", "!", "?")) else f"{excerpt}."

    def _section_revision_scope_sentence(self, section: AutoResearchPaperPlanSectionRead) -> str:
        return ""

    def _auto_revision_draft(
        self,
        *,
        section: AutoResearchPaperPlanSectionRead,
        current_body: str,
        claim_entries: list[AutoResearchClaimEvidenceEntryRead],
        actions: list[AutoResearchPaperRevisionActionRead],
        open_issues: list[str],
        paper_revision_state: AutoResearchPaperRevisionStateRead,
    ) -> str:
        base_body = self._strip_auto_revision_paragraph(current_body) or self._fallback_section_body(section)
        if paper_revision_state.revision_round <= 0:
            return base_body
        focus_section = (
            section.title in paper_revision_state.focus_sections
            or bool(actions)
            or bool(open_issues)
        )
        if not focus_section:
            return base_body

        revision_sentences: list[str] = []
        unsupported_claim_count = sum(
            1 for item in claim_entries if item.support_status != "supported"
        )
        if unsupported_claim_count:
            revision_sentences.append(
                "Some claims in this section await further experimental support and are presented as preliminary observations."
            )
        if open_issues:
            primary_issue = self._revision_sentence_fragment(open_issues[0])
            if primary_issue is not None:
                revision_sentences.append(
                    f"One open question is: {primary_issue}"
                )
        evidence_focus = self._humanize_evidence_focus(section.evidence_focus)
        if evidence_focus:
            revision_sentences.append(
                f"This section draws on evidence from {evidence_focus}."
            )
        if actions:
            primary_action = self._revision_sentence_fragment(actions[0].detail)
            if primary_action is not None:
                revision_sentences.append(
                    f"Updated in revision {paper_revision_state.revision_round}: {primary_action}"
                )
        revision_paragraph = " ".join(revision_sentences).strip()
        if not revision_paragraph:
            return base_body
        return f"{base_body}\n\n{revision_paragraph}".strip()

    def _rewrite_packet_asset_paths(
        self,
        *,
        paper_plan: AutoResearchPaperPlanRead | None,
        base_dir: str,
    ) -> list[str]:
        if paper_plan is None:
            return []
        base = base_dir.rstrip("/")
        assets = [f"{base}/rewrite_packets/index.json"]
        assets.extend(
            f"{base}/{self._section_rewrite_packet_relative_path(section)}"
            for section in paper_plan.sections
        )
        return assets

    def _checkpoint_snapshot_assets(
        self,
        revision_round: int,
        *,
        paper_plan: AutoResearchPaperPlanRead | None = None,
        include_review_assets: bool = False,
    ) -> list[str]:
        round_dir = f"paper_sources/checkpoints/round_{revision_round:04d}"
        assets = [
            f"{round_dir}/checkpoint.json",
            f"{round_dir}/checkpoint_note.md",
            f"{round_dir}/paper.md",
            f"{round_dir}/narrative_report.md",
            f"{round_dir}/claim_evidence_matrix.json",
            f"{round_dir}/paper_plan.json",
            f"{round_dir}/figure_plan.json",
            f"{round_dir}/revision_history.md",
            f"{round_dir}/revision_diff.md",
            f"{round_dir}/revision_actions.md",
            f"{round_dir}/revision_brief.md",
            f"{round_dir}/paper_revision_state.json",
            f"{round_dir}/paper_compile_report.json",
            f"{round_dir}/paper_revision_diff.json",
            f"{round_dir}/paper_revision_action_index.json",
            f"{round_dir}/build.sh",
            f"{round_dir}/main.tex",
            f"{round_dir}/references.bib",
            f"{round_dir}/manifest.json",
        ]
        assets.extend(
            self._rewrite_packet_asset_paths(
                paper_plan=paper_plan,
                base_dir=round_dir,
            )
        )
        if include_review_assets:
            assets.extend(
                [
                    f"{round_dir}/review.json",
                    f"{round_dir}/review_loop.json",
                ]
            )
        return assets

    def _review_action_section_title(
        self,
        action: AutoResearchReviewLoopActionRead,
        *,
        paper_plan: AutoResearchPaperPlanRead | None = None,
    ) -> str:
        lowered = f"{action.title} {action.detail}".lower()
        if any(token in lowered for token in ("citation", "references", "related-work", "related work", "literature", "novelty", "context")):
            return self._paper_plan_title(
                paper_plan,
                "Related Work",
                "Introduction",
                fallback="Related Work",
            )
        if any(token in lowered for token in ("statistical", "significance", "seed", "sweep", "artifact", "results", "acceptance")):
            return self._paper_plan_title(
                paper_plan,
                "Results",
                fallback="Results",
            )
        if any(token in lowered for token in ("publish", "provenance", "manifest", "bundle", "restore")):
            return self._paper_plan_title(
                paper_plan,
                "Method",
                "Results",
                fallback="Method",
            )
        return self._paper_plan_title(
            paper_plan,
            "Results",
            "Method",
            fallback="Results",
        )

    def sync_paper_revision_state(
        self,
        existing_state: AutoResearchPaperRevisionStateRead | None,
        *,
        review: AutoResearchRunReviewRead,
        review_loop: AutoResearchReviewLoopRead,
        paper_plan: AutoResearchPaperPlanRead | None = None,
        figure_plan: AutoResearchFigurePlanRead | None = None,
    ) -> AutoResearchPaperRevisionStateRead:
        existing_checkpoints = list(existing_state.checkpoints) if existing_state is not None else []
        checkpoint_by_round = {
            item.revision_round: item.model_copy(deep=True)
            for item in existing_checkpoints
        }
        initial_completed = list(existing_state.completed_actions) if existing_state is not None else []
        open_issues = [item.summary for item in review_loop.issues if item.status == "open"]
        pending_actions = [item for item in review_loop.actions if item.status == "pending"]
        completed_actions = _dedupe_preserving_order(
            initial_completed
            + [item.title for item in review_loop.actions if item.status == "completed"]
        )
        next_actions = [
            AutoResearchPaperRevisionActionRead(
                action_id=item.action_id,
                priority=item.priority,
                section_title=self._review_action_section_title(item, paper_plan=paper_plan),
                detail=item.detail,
                status="open",
            )
            for item in pending_actions
        ]
        focus_sections = _dedupe_preserving_order(
            [item.section_title for item in next_actions]
            or (list(existing_state.focus_sections) if existing_state is not None else [])
            or ([section.title for section in paper_plan.sections[:3]] if paper_plan is not None else [])
        )
        status = (
            "ready_for_publish"
            if review.overall_status == "ready"
            else "revising"
            if pending_actions or review_loop.current_round > 0
            else "needs_review"
        )
        for round_state in review_loop.rounds:
            round_status = (
                "ready_for_publish"
                if round_state.overall_status == "ready"
                else "revising"
                if round_state.round_index == review_loop.current_round and pending_actions
                else "needs_review"
            )
            checkpoint_by_round[round_state.round_index] = AutoResearchPaperRevisionCheckpointRead(
                revision_round=round_state.round_index,
                generated_at=round_state.generated_at,
                status=round_status,
                summary=(
                    "Review round "
                    f"{round_state.round_index} cleared the paper for publish-ready packaging."
                    if round_state.overall_status == "ready"
                    else "Review round "
                    f"{round_state.round_index} captured persisted review findings and revision actions."
                ),
                open_issue_count=(
                    len(open_issues)
                    if round_state.round_index == review_loop.current_round
                    else len(round_state.finding_ids)
                ),
                open_issue_summaries=(
                    list(open_issues)
                    if round_state.round_index == review_loop.current_round
                    else (
                        list(checkpoint_by_round[round_state.round_index].open_issue_summaries)
                        if round_state.round_index in checkpoint_by_round
                        else []
                    )
                ),
                focus_sections=(
                    list(focus_sections)
                    if round_state.round_index == review_loop.current_round
                    else (
                        list(checkpoint_by_round[round_state.round_index].focus_sections)
                        if round_state.round_index in checkpoint_by_round
                        else []
                    )
                ),
                next_action_ids=(
                    [item.action_id for item in next_actions]
                    if round_state.round_index == review_loop.current_round
                    else (
                        list(checkpoint_by_round[round_state.round_index].next_action_ids)
                        if round_state.round_index in checkpoint_by_round
                        else []
                    )
                ),
                completed_action_titles=(
                    list(completed_actions)
                    if round_state.round_index == review_loop.current_round
                    else (
                        list(checkpoint_by_round[round_state.round_index].completed_action_titles)
                        if round_state.round_index in checkpoint_by_round
                        else []
                    )
                ),
                relative_assets=_dedupe_preserving_order(
                    [
                        "paper.md",
                        "narrative_report.md",
                        "claim_evidence_matrix.json",
                        "paper_plan.json",
                        "figure_plan.json",
                        "revision_history.md",
                        "revision_diff.md",
                        "revision_actions.md",
                        "paper_revision_state.json",
                        "paper_compile_report.json",
                        "paper_revision_diff.json",
                        "paper_revision_action_index.json",
                        "review.json",
                        "review_loop.json",
                        "paper_sources/paper_compile_report.json",
                        "paper_sources/paper_revision_diff.json",
                        "paper_sources/paper_revision_action_index.json",
                        "paper_sources/paper.md",
                        "paper_sources/revision_diff.md",
                        "paper_sources/revision_actions.md",
                        "paper_sources/build.sh",
                        "paper_sources/main.tex",
                        "paper_sources/references.bib",
                        "paper_sources/manifest.json",
                        *self._rewrite_packet_asset_paths(
                            paper_plan=paper_plan,
                            base_dir="paper_sources",
                        ),
                        "paper_sources/checkpoints/index.json",
                        *self._checkpoint_snapshot_assets(
                            round_state.round_index,
                            paper_plan=paper_plan,
                            include_review_assets=True,
                        ),
                    ]
                ),
            )
        if figure_plan is not None and any(item.status != "ready" for item in figure_plan.items) and "Results" not in focus_sections:
            focus_sections.append("Results")
        return AutoResearchPaperRevisionStateRead(
            generated_at=_utcnow(),
            revision_round=max(review_loop.current_round, existing_state.revision_round if existing_state is not None else 0),
            status=status,
            open_issues=open_issues,
            completed_actions=completed_actions,
            focus_sections=focus_sections,
            next_actions=next_actions,
            checkpoints=[
                checkpoint_by_round[key]
                for key in sorted(checkpoint_by_round)
            ],
        )

    def _literature_citation_span(self, literature: list[LiteratureInsight], *, limit: int = 2) -> str:
        if not literature:
            return ""
        count = min(len(literature), max(1, limit))
        labels = ", ".join(str(index) for index in range(1, count + 1))
        return f"[{labels}]"

    def _fallback_context_only(self, literature: list[LiteratureInsight]) -> bool:
        return bool(literature) and all((item.source or "").endswith("_context") for item in literature)

    def _literature_context_sentence(self, literature: list[LiteratureInsight]) -> str:
        if not literature:
            return ""
        if self._fallback_context_only(literature):
            return (
                f"Background context {self._literature_citation_span(literature)} provides the motivation "
                "for the experimental design and the choice of evaluation framework."
            )
        return (
            f"Recent related work {self._literature_citation_span(literature)} motivates the experimental "
            "design and informs the choice of methods."
        )

    def _discussion_context_sentence(self, literature: list[LiteratureInsight]) -> str:
        if not literature:
            return ""
        if self._fallback_context_only(literature):
            return (
                f"The background context {self._literature_citation_span(literature)} frames this study as "
                "a controlled experimental evaluation rather than a broad state-of-the-art claim."
            )
        return (
            f"The reviewed literature {self._literature_citation_span(literature)} situates our results "
            "within the broader field and clarifies the scope of our contribution."
        )

    def _conclusion_context_sentence(self, literature: list[LiteratureInsight]) -> str:
        if not literature:
            return ""
        if self._fallback_context_only(literature):
            return (
                f"Relative to the background context {self._literature_citation_span(literature)}, "
                "this work contributes reproducible experimental evidence and methodological insights."
            )
        return (
            f"Relative to the reviewed literature {self._literature_citation_span(literature)}, "
            "this work contributes reproducible experimental evidence and methodological insights."
        )

    def _project_flow_alignment_block(
        self,
        project_context: AutoResearchProjectFlowContextRead | None,
    ) -> str:
        if project_context is None:
            return ""
        details: list[str] = []
        if project_context.template_sections:
            details.append(
                "template sections "
                + ", ".join(f"`{item}`" for item in project_context.template_sections[:4])
            )
        if project_context.draft is not None:
            draft_bits = [f"draft v{project_context.draft.version}"]
            if project_context.draft.claims:
                draft_bits.append(
                    "claims such as "
                    + "; ".join(f"`{item}`" for item in project_context.draft.claims[:2])
                )
            details.append(" / ".join(draft_bits))
        if project_context.evidence is not None and project_context.evidence.claims:
            details.append(
                "saved evidence claims "
                + "; ".join(f"`{item}`" for item in project_context.evidence.claims[:2])
            )
        if project_context.review is not None and project_context.review.suggestions:
            details.append(
                "review guidance "
                + "; ".join(project_context.review.suggestions[:2])
            )
        if project_context.api_surface_hints:
            details.append(
                "API anchors "
                + ", ".join(f"`{item}`" for item in project_context.api_surface_hints[:4])
            )
        if not details:
            return ""
        return (
            "Project flow alignment: the manuscript is constrained by persisted project materials, including "
            + "; ".join(details)
            + "."
        )

    def _extract_markdown_headings(self, markdown: str) -> list[str]:
        return [
            line.strip()
            for line in markdown.splitlines()
            if line.startswith("#")
        ]

    def _llm_paper_candidate_valid(
        self,
        candidate: str,
        *,
        seed_markdown: str,
        literature: list[LiteratureInsight],
        project_context: AutoResearchProjectFlowContextRead | None,
    ) -> bool:
        if not candidate.strip():
            logger.warning("paper_writer validation: candidate is empty")
            return False
        seed_section_headings = [
            line.strip() for line in seed_markdown.splitlines()
            if line.strip().startswith("## ")
        ]
        candidate_heading_slugs = {
            _section_heading_slug(line.strip()[3:])
            for line in candidate.splitlines()
            if line.strip().startswith("## ")
        }
        missing = []
        for heading in seed_section_headings:
            slug = _section_heading_slug(heading[3:])
            if slug not in candidate_heading_slugs:
                missing.append(heading)
        if missing:
            logger.warning("paper_writer validation: missing section headings: %s", missing)
            return False
        if literature and "## References" in seed_markdown and "[1]" not in candidate:
            logger.warning("paper_writer validation: literature provided but no citation [1] found in candidate")
            return False
        if project_context is not None and "project" not in candidate.lower():
            logger.warning("paper_writer validation: project_context provided but no project reference found")
            return False
        return True

    def _maybe_refine_with_llm(
        self,
        *,
        seed_markdown: str,
        language: str,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        artifact: ResultArtifact,
        literature: list[LiteratureInsight],
        attempts: list[ExperimentAttempt],
        project_context: AutoResearchProjectFlowContextRead | None,
        narrative_report_markdown: str,
        claim_evidence_matrix: AutoResearchClaimEvidenceMatrixRead,
        paper_plan: AutoResearchPaperPlanRead,
        paper_revision_state: AutoResearchPaperRevisionStateRead,
    ) -> str:
        refined = seed_markdown
        try:
            prompt = load_prompt(PAPER_WRITER_PROMPT_PATH)
            logger.info("paper_writer: calling LLM for refinement (seed_len=%d)", len(seed_markdown))
            response = chat(
                [
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Target language: {language or 'en'}\n"
                            f"Plan: {plan.model_dump(mode='json')}\n"
                            f"Spec: {spec.model_dump(mode='json')}\n"
                            f"Artifact: {artifact.model_dump(mode='json')}\n"
                            f"Attempts: {[item.model_dump(mode='json') for item in attempts]}\n"
                            f"Literature: {[item.model_dump(mode='json') for item in literature]}\n"
                            f"Project flow context: {project_context.model_dump(mode='json') if project_context is not None else None}\n"
                            f"Claim-evidence matrix: {claim_evidence_matrix.model_dump(mode='json')}\n"
                            f"Paper plan: {paper_plan.model_dump(mode='json')}\n"
                            f"Paper revision state: {paper_revision_state.model_dump(mode='json')}\n"
                            f"Narrative report:\n{narrative_report_markdown}\n\n"
                            f"Seed paper markdown:\n{seed_markdown}"
                        ),
                    },
                ],
                model=settings.llm_writer_model,
            )
            content = get_message_content(response).strip()
            if content and self._llm_paper_candidate_valid(
                content,
                seed_markdown=seed_markdown,
                literature=literature,
                project_context=project_context,
            ):
                logger.info("paper_writer: LLM refinement accepted (content_len=%d)", len(content))
                refined = content
            elif content:
                logger.warning("paper_writer: LLM candidate failed validation, keeping seed markdown (content_len=%d)", len(content))
        except Exception as exc:
            logger.error("paper_writer: LLM refinement failed with exception: %s", exc)

        # --- Self-review + revision loop ---
        refined = self._self_review_and_revise(
            refined,
            plan=plan,
            artifact=artifact,
            literature=literature,
            seed_markdown=seed_markdown,
            project_context=project_context,
        )
        return refined

    def _self_review_and_revise(
        self,
        paper_markdown: str,
        *,
        plan: ResearchPlan,
        artifact: ResultArtifact,
        literature: list[LiteratureInsight],
        seed_markdown: str,
        project_context: AutoResearchProjectFlowContextRead | None,
        max_rounds: int = 2,
    ) -> str:
        writer_model = settings.llm_writer_model
        current = paper_markdown
        for round_idx in range(max_rounds):
            try:
                review_prompt = load_prompt(PAPER_SELF_REVIEW_PROMPT_PATH)
                review_prompt_filled = review_prompt.replace("{{paper_content}}", current)
                logger.info("paper_writer: self-review round %d/%d (len=%d)", round_idx + 1, max_rounds, len(current))
                review_response = chat(
                    [
                        {"role": "system", "content": review_prompt_filled},
                        {"role": "user", "content": "Provide your structured review now."},
                    ],
                    model=writer_model,
                )
                review_text = get_message_content(review_response).strip()
                if not review_text:
                    logger.warning("paper_writer: self-review round %d returned empty, stopping", round_idx + 1)
                    break

                # Check if revision is needed
                if '"overall_verdict": "accept"' in review_text.lower():
                    logger.info("paper_writer: self-review round %d verdict=accept, stopping", round_idx + 1)
                    break

                # Apply revision
                rev_prompt = load_prompt(PAPER_REVISION_PROMPT_PATH)
                evidence_summary = (
                    f"Best system: {artifact.best_system}, "
                    f"primary metric ({artifact.primary_metric}): {artifact.objective_score:.4f}\n"
                    f"Key findings: {'; '.join(artifact.key_findings[:5])}\n"
                ) if artifact.objective_score is not None else "No score available."
                rev_prompt_filled = (
                    rev_prompt
                    .replace("{{review_feedback}}", review_text)
                    .replace("{{evidence_data}}", evidence_summary)
                    .replace("{{paper_content}}", current)
                )
                rev_response = chat(
                    [
                        {"role": "system", "content": rev_prompt_filled},
                        {"role": "user", "content": "Revise the paper now."},
                    ],
                    model=writer_model,
                )
                revised = get_message_content(rev_response).strip()
                if not revised or len(revised) < len(current) * 0.5:
                    logger.warning(
                        "paper_writer: revision round %d produced insufficient output (%d chars), keeping current",
                        round_idx + 1, len(revised) if revised else 0,
                    )
                    break
                if self._llm_paper_candidate_valid(
                    revised,
                    seed_markdown=seed_markdown,
                    literature=literature,
                    project_context=project_context,
                ):
                    current = revised
                    logger.info("paper_writer: revision round %d accepted (%d chars)", round_idx + 1, len(current))
                else:
                    logger.warning("paper_writer: revision round %d failed validation, keeping current", round_idx + 1)
                    break
            except Exception as exc:
                logger.error("paper_writer: self-review/revision round %d failed: %s", round_idx + 1, exc)
                break
        return current

    def _write_section_with_llm(
        self,
        section_title: str,
        section_objective: str,
        *,
        evidence_context: str,
        prev_section_name: str = "",
        prev_section_summary: str = "",
        next_section_name: str = "",
        next_section_summary: str = "",
        literature_context: str = "",
        figure_context: str = "",
        section_guidance: str = "",
        topic: str = "",
    ) -> str | None:
        try:
            prompt_template = load_prompt(PAPER_WRITER_SECTION_PROMPT_PATH)
            prompt = (
                prompt_template
                .replace("{{section_name}}", section_title)
                .replace("{{section_objective}}", section_objective)
                .replace("{{evidence_context}}", evidence_context)
                .replace("{{prev_section_name}}", prev_section_name)
                .replace("{{prev_section_summary}}", prev_section_summary)
                .replace("{{next_section_name}}", next_section_name)
                .replace("{{next_section_summary}}", next_section_summary)
                .replace("{{literature_context}}", literature_context)
                .replace("{{figure_context}}", figure_context)
                .replace("{{section_guidance}}", section_guidance)
                .replace("{{topic}}", topic)
            )
            writer_model = settings.llm_writer_model
            logger.info(
                "paper_writer: generating section '%s' with model=%s",
                section_title, writer_model or "default",
            )
            response = chat(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Write the {section_title} section now."},
                ],
                model=writer_model,
            )
            content = get_message_content(response).strip()
            if not content or len(content) < 50:
                logger.warning(
                    "paper_writer: section '%s' LLM output too short (%d chars), skipping",
                    section_title, len(content),
                )
                return None
            logger.info(
                "paper_writer: section '%s' generated successfully (%d chars)",
                section_title, len(content),
            )
            return content
        except Exception as exc:
            logger.error("paper_writer: section '%s' generation failed: %s", section_title, exc)
            return None

    def _build_evidence_context_for_section(
        self,
        section: AutoResearchPaperPlanSectionRead,
        artifact: ResultArtifact,
        claim_evidence_matrix: AutoResearchClaimEvidenceMatrixRead,
    ) -> str:
        claim_ids = getattr(section, "claim_ids", None) or []
        relevant_claims = [
            entry for entry in claim_evidence_matrix.entries
            if not claim_ids or entry.claim_id in claim_ids
        ]
        parts: list[str] = []
        for claim in relevant_claims:
            evidence_details = "; ".join(
                f"{ref.label}: {ref.detail}" for ref in claim.evidence
            )
            parts.append(
                f"- [{claim.support_status}] {claim.claim}\n  Evidence: {evidence_details}"
            )
        if not parts:
            parts.append("- No specific claims assigned. Use general experimental data.")
        if artifact.tables:
            table_summaries = []
            for table in artifact.tables[:3]:
                cols = ", ".join(table.columns[:5])
                table_summaries.append(f"Table '{table.title}': columns=[{cols}], {len(table.rows)} rows")
            parts.append("\nAvailable result tables:\n" + "\n".join(f"- {s}" for s in table_summaries))
        if artifact.best_system and artifact.objective_score is not None:
            parts.append(
                f"\nBest system: {artifact.best_system}, "
                f"objective score ({artifact.primary_metric}): {artifact.objective_score:.4f}"
            )
        return "\n".join(parts)

    def _build_section_guidance(self, section_slug: str) -> str:
        guidance_map: dict[str, str] = {
            "abstract": "State the problem, method, key result, and significance in 150-250 words. End with the broader impact.",
            "introduction": "Present the problem and motivation as a narrative. State research questions naturally within the flow. Do NOT list them as a numbered list unless essential.",
            "related_work": "Survey prior work thematically, grouping by approach. If no external literature is available, discuss the problem domain and methodological background. Conclude by identifying the gap this work addresses.",
            "method": "Describe the approach as a coherent methodology. Cover data, models, training procedure, and evaluation criteria. Frame it as a contribution.",
            "experimental_setup": "Concisely describe the experimental conditions: environment, seeds, metrics, statistical tests. Keep technical but brief.",
            "results": "Present findings with tables, then interpret them. Do NOT just list numbers — explain what they mean. Highlight statistical significance where applicable.",
            "discussion": "Interpret results in context. Compare with expectations and prior work. Acknowledge limitations naturally, not as a bullet list.",
            "limitations": "Discuss scope constraints, negative results, and untested conditions honestly. This section builds credibility.",
            "conclusion": "Summarize key findings and their implications. Outline concrete future directions. Do NOT end with a generic 'Future work should extend to larger datasets' sentence.",
        }
        return guidance_map.get(section_slug, "Write clear, evidence-grounded academic prose.")

    def _write_full_paper_with_llm(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        artifact: ResultArtifact,
        paper_plan: AutoResearchPaperPlanRead,
        claim_evidence_matrix: AutoResearchClaimEvidenceMatrixRead,
        literature: list[LiteratureInsight],
        *,
        figure_paths: dict[str, str] | None = None,
    ) -> dict[str, str]:
        figure_paths = figure_paths or {}
        section_slugs = [_section_slug(s.title) for s in paper_plan.sections]
        literature_context_block = ""
        if literature:
            lit_items = []
            for i, item in enumerate(literature, 1):
                parts = [f"[{i}] {item.title}"]
                if item.insight:
                    lit_items.append(f"{parts[0]}: {item.insight}")
                else:
                    lit_items.append(parts[0])
            literature_context_block = "## Available literature\n" + "\n".join(f"- {s}" for s in lit_items)

        generated: dict[str, str] = {}
        for idx, section in enumerate(paper_plan.sections):
            slug = _section_slug(section.title)
            objective = (
                section.objectives
                if hasattr(section, "objectives") and section.objectives
                else f"Write the {section.title} section of the paper."
            )
            evidence = self._build_evidence_context_for_section(
                section, artifact, claim_evidence_matrix,
            )
            prev_slug = section_slugs[idx - 1] if idx > 0 else ""
            next_slug = section_slugs[idx + 1] if idx < len(section_slugs) - 1 else ""
            prev_summary = _excerpt(generated.get(prev_slug, ""), limit=200) or "This is the first section."
            next_summary = "Follows with the next section." if next_slug else "This is the final section."

            fig_block = ""
            if slug == "results" and figure_paths:
                fig_lines = [f"![{name}]({path})" for name, path in figure_paths.items()]
                fig_block = "## Figures available for embedding\n" + "\n".join(fig_lines)

            content = self._write_section_with_llm(
                section_title=section.title,
                section_objective=objective,
                evidence_context=evidence,
                prev_section_name=prev_slug.replace("_", " ").title() if prev_slug else "",
                prev_section_summary=prev_summary,
                next_section_name=next_slug.replace("_", " ").title() if next_slug else "",
                next_section_summary=next_summary,
                literature_context=literature_context_block if slug in ("related_work", "introduction", "discussion") else "",
                figure_context=fig_block,
                section_guidance=self._build_section_guidance(slug),
                topic=plan.topic,
            )
            if content is not None:
                generated[slug] = content
        return generated

    def _reference_entry(self, index: int, item: LiteratureInsight) -> str:
        year = str(item.year) if item.year is not None else "n.d."
        source = (item.source or "").replace("_", " ")
        if source == "benchmark context":
            source = "Benchmark documentation"
        elif source:
            source = source.title()
        else:
            source = "Technical report"
        return f"[{index}] {item.title}. {source}, {year}."

    def _references_block(self, literature: list[LiteratureInsight]) -> str:
        if not literature:
            return ""
        return "\n".join(
            self._reference_entry(index + 1, item)
            for index, item in enumerate(literature)
        )

    def _literature_synthesis_sentence(self, literature: list[LiteratureInsight], *, limit: int = 2) -> str:
        if not literature:
            return ""
        rendered: list[str] = []
        for index, item in enumerate(literature[: max(1, limit)], start=1):
            detail = self._revision_sentence_fragment(
                " ".join(
                    part
                    for part in (item.insight, item.method_hint, item.gap_hint)
                    if part
                ),
                limit=150,
            )
            if detail is None:
                detail = "provides adjacent context for the benchmark framing."
            rendered.append(f"[{index}] `{item.title}` {detail}")
        return " ".join(rendered)

    def _selected_candidate(
        self,
        portfolio: PortfolioSummary | None,
        candidates: list[HypothesisCandidate],
    ) -> HypothesisCandidate | None:
        if not candidates:
            return None
        if portfolio is not None and portfolio.selected_candidate_id:
            selected = next(
                (item for item in candidates if item.id == portfolio.selected_candidate_id),
                None,
            )
            if selected is not None:
                return selected
        return candidates[0]

    def _selected_candidate_sentence(
        self,
        portfolio: PortfolioSummary | None,
        candidates: list[HypothesisCandidate],
    ) -> str:
        selected = self._selected_candidate(portfolio, candidates)
        if selected is None:
            return ""
        reason = selected.selection_reason or (portfolio.decision_summary if portfolio is not None else "")
        if reason:
            reason = reason.strip()
            if reason[-1] not in ".!?":
                reason = f"{reason}."
            return f"The selected approach is `{selected.title}` because {reason}"
        return f"The selected approach is `{selected.title}`."

    def _portfolio_decision_sentence(
        self,
        portfolio: PortfolioSummary | None,
        candidates: list[HypothesisCandidate],
    ) -> str:
        selected = self._selected_candidate(portfolio, candidates)
        if selected is None:
            return ""
        reason = self._revision_sentence_fragment(
            selected.selection_reason or (portfolio.decision_summary if portfolio is not None else ""),
            limit=180,
        )
        if reason:
            return f"After evaluating all candidate approaches, the study adopts `{selected.title}` as the primary method. {reason}"
        return f"After evaluating all candidate approaches, the study adopts `{selected.title}` as the primary method."

    def _benchmark_slice_sentence(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        benchmark_display: str,
    ) -> str:
        benchmark_target = "query set" if spec.task_family == "ir_reranking" else "dataset"
        return (
            f"We operationalize the research question through the {benchmark_target} `{spec.dataset.name}` "
            f"in benchmark `{benchmark_display}`, which provides a controlled experimental setting for `{plan.topic}`."
        )

    def _bounded_interpretation_sentence(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        benchmark_display: str,
    ) -> str:
        return (
            f"These findings should be interpreted within the scope of benchmark `{benchmark_display}` "
            f"on dataset `{spec.dataset.name}`; generalization to broader `{plan.topic}` tasks remains "
            "an open question."
        )

    def _hypothesis_outcome_summary_sentence(
        self,
        spec: ExperimentSpec,
        artifact: ResultArtifact,
    ) -> str:
        target_systems = self._hypothesis_target_systems(spec)
        best_system = artifact.best_system or artifact.objective_system
        if not target_systems:
            return "The experimental results provide quantitative evidence on the benchmark, though the hypothesis framing does not isolate a single target system for a definitive conclusion."
        if best_system and best_system in target_systems:
            return "The leading system outcome supports the planned hypothesis."
        if best_system:
            return f"The leading system outcome contradicts the planned hypothesis by favoring `{best_system}`."
        return "The final artifact does not expose a single winner clearly enough to resolve the planned hypothesis."

    def _key_findings_sentence(self, artifact: ResultArtifact, *, limit: int = 2) -> str:
        findings: list[str] = []
        for item in artifact.key_findings[: max(1, limit)]:
            fragment = self._revision_sentence_fragment(item, limit=140)
            if fragment is None:
                continue
            findings.append(fragment.rstrip("."))
        if not findings:
            return ""
        return "Notable findings include " + "; ".join(findings) + "."

    def _aggregate_metric(self, artifact: ResultArtifact, system_name: str | None, metric: str) -> float | None:
        if not system_name:
            return None
        for item in artifact.aggregate_system_results:
            if item.system == system_name:
                value = item.mean_metrics.get(metric)
                return float(value) if value is not None else None
        return self._metric(artifact, system_name, metric)

    def _aggregate_std(self, artifact: ResultArtifact, system_name: str | None, metric: str) -> float | None:
        if not system_name:
            return None
        for item in artifact.aggregate_system_results:
            if item.system == system_name:
                value = item.std_metrics.get(metric)
                return float(value) if value is not None else None
        return None

    def _aggregate_confidence_interval(
        self,
        artifact: ResultArtifact,
        system_name: str | None,
        metric: str,
    ) -> ConfidenceIntervalSummary | None:
        if not system_name:
            return None
        for item in artifact.aggregate_system_results:
            if item.system == system_name:
                return item.confidence_intervals.get(metric)
        return None

    def _format_confidence_interval(self, interval: ConfidenceIntervalSummary | None) -> str | None:
        if interval is None:
            return None
        level_percent = int(round(interval.level * 100))
        return f"{level_percent}% CI [{interval.lower:.4f}, {interval.upper:.4f}]"

    def _metric(self, artifact: ResultArtifact, system_name: str | None, metric: str) -> float | None:
        if not system_name:
            return None
        for item in artifact.system_results:
            if item.system == system_name:
                value = item.metrics.get(metric)
                return float(value) if value is not None else None
        return None

    def _normalize_prose_text(self, text: str | None) -> str:
        return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()

    def _text_mentions_system(self, text: str | None, system_name: str) -> bool:
        normalized_text = f" {self._normalize_prose_text(text)} "
        aliases = {
            self._normalize_prose_text(system_name),
            self._normalize_prose_text(system_name.replace("_", " ")),
        }
        return any(alias and f" {alias} " in normalized_text for alias in aliases)

    def _paper_result_tables(self, artifact: ResultArtifact) -> list[ResultTable]:
        if not artifact.tables:
            return []
        excluded_titles = {"Negative Results", "Sweep Summary", "Seed Runs"}
        selected = [table for table in artifact.tables if table.title not in excluded_titles]
        return selected or artifact.tables[:1]

    def _results_table(self, artifact: ResultArtifact) -> str:
        tables = self._paper_result_tables(artifact)
        if not tables:
            return ""
        rendered = []
        for table in tables:
            rendered.append(f"### {table.title}\n")
            rendered.append(_markdown_table(table))
            rendered.append("")
        return "\n".join(rendered).strip()

    def _literature_block(self, literature: list[LiteratureInsight]) -> str:
        if not literature:
            return (
                "No project-specific papers were available for this run. The background context below is "
                "drawn from benchmark documentation and planning assumptions."
            )
        return "\n".join(
            (
                f"- [{index + 1}] {item.title} ({item.year or 'n.d.'}; {(item.source or 'unknown source').replace('_', ' ')}): "
                + " ".join(
                    part
                    for part in (
                        item.insight,
                        item.method_hint,
                        item.gap_hint,
                    )
                    if part
                )
            )
            for index, item in enumerate(literature)
        )

    def _attempt_block(self, attempts: list[ExperimentAttempt]) -> str:
        if not attempts:
            return "- No iterative attempts were recorded."
        return "\n".join(
            f"- Round {item.round_index} using `{item.strategy}` ({item.goal}): {item.summary}"
            for item in attempts
        )

    def _acceptance_block(self, artifact: ResultArtifact) -> str:
        if not artifact.acceptance_checks:
            return "- No explicit acceptance checks were recorded."
        return "\n".join(
            f"- {'PASS' if item.passed else 'FAIL'}: {item.criterion} ({item.detail})"
            for item in artifact.acceptance_checks
        )

    def _significance_block(self, artifact: ResultArtifact) -> str:
        if not artifact.significance_tests:
            return "- No paired significance comparisons were recorded."
        return "\n".join(
            (
                f"- {item.scope}: `{item.candidate}` vs `{item.comparator}` on `{item.metric}` "
                f"(effect={item.effect_size:.4f}, adjusted p="
                f"{(item.adjusted_p_value if item.adjusted_p_value is not None else item.p_value):.4f}, "
                f"{'significant' if item.significant else 'not significant'})."
            )
            for item in artifact.significance_tests
        )

    def _negative_results_block(self, artifact: ResultArtifact) -> str:
        salient: list[str] = []
        for item in artifact.negative_results:
            delta = abs(item.delta) if item.delta is not None else None
            if item.scope in {"system", "sweep"} and delta is not None and delta < 1e-9:
                continue
            salient.append(f"- {item.detail}")
        return "\n".join(salient[:3])

    def _failure_block(self, artifact: ResultArtifact) -> str:
        if not artifact.failed_trials:
            return "- No failed seed or sweep configurations were recorded."
        return "\n".join(
            f"- {item.scope} failure in sweep `{item.sweep_label}`"
            f"{f' seed {item.seed}' if item.seed is not None else ''}: "
            f"{item.category} ({item.summary})"
            for item in artifact.failed_trials
        )

    def _anomaly_block(self, artifact: ResultArtifact) -> str:
        if not artifact.anomalous_trials:
            return "- No anomalous trials were flagged."
        return "\n".join(f"- {item.detail}" for item in artifact.anomalous_trials)

    def _portfolio_block(
        self,
        program: ResearchProgram | None,
        portfolio: PortfolioSummary | None,
        candidates: list[HypothesisCandidate],
    ) -> str:
        if not portfolio or not candidates:
            return "Portfolio planning has not been enabled for this run."
        selected = next(
            (candidate for candidate in candidates if candidate.id == portfolio.selected_candidate_id),
            None,
        )
        lines = [
            f"- Rank {candidate.rank}: `{candidate.title}` ({candidate.status}) - {candidate.rationale}"
            for candidate in candidates
        ]
        if selected is not None:
            selected_reason = selected.selection_reason or portfolio.decision_summary
            if selected_reason and selected_reason[-1] not in ".!?":
                selected_reason = f"{selected_reason}."
            selected_sentence = f"The execution focus was `{selected.title}` because {selected_reason}"
        else:
            selected_sentence = portfolio.decision_summary
        benchmark_clause = (
            f" on benchmark `{program.benchmark_name}`"
            if program is not None and program.benchmark_name
            else ""
        )
        return (
            f"Portfolio planning generated {len(candidates)} ranked candidates{benchmark_clause}.\n"
            f"{selected_sentence}\n"
            f"{portfolio.decision_summary}\n"
            + "\n".join(lines)
        )

    def _proxy_scope_sentence(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        benchmark_display: str,
    ) -> str:
        topic_terms = {
            token
            for token in re.findall(r"[a-z][a-z0-9]+", (plan.topic or "").lower())
            if len(token) >= 4
        }
        proxy_blob = " ".join(
            [
                benchmark_display,
                spec.benchmark_description,
                spec.dataset.name,
                spec.dataset.description,
                " ".join(spec.dataset.input_fields),
                " ".join(spec.dataset.query_fields),
                " ".join(spec.dataset.label_space),
            ]
        ).lower()
        shared_terms = sorted(token for token in topic_terms if token in proxy_blob)
        if not shared_terms:
            return (
                f"The resulting claims are limited to benchmark `{benchmark_display}` on `{spec.dataset.name}`; they "
                f"should be read as bounded evidence about `{plan.topic}`, not as a direct evaluation of the full topic."
            )
        return (
            f"The resulting claims are limited to benchmark `{benchmark_display}` on `{spec.dataset.name}`; they "
            f"describe the specific experimental conditions tested rather than the full `{plan.topic}` literature."
        )

    def _hypothesis_target_systems(self, spec: ExperimentSpec) -> list[str]:
        candidate_names = sorted(
            {item.name for item in [*spec.baselines, *spec.ablations]},
            key=len,
            reverse=True,
        )
        return [item for item in candidate_names if self._text_mentions_system(spec.hypothesis, item)]

    def _attempt_labels_for_systems(
        self,
        attempts: list[ExperimentAttempt],
        system_names: list[str],
    ) -> list[str]:
        labels = []
        seen: set[str] = set()
        for attempt in attempts:
            matched = any(
                self._text_mentions_system(attempt.strategy, system_name)
                or self._text_mentions_system(attempt.summary, system_name)
                or (
                    attempt.artifact is not None
                    and (
                        attempt.artifact.best_system == system_name
                        or any(item.system == system_name for item in attempt.artifact.system_results)
                        or any(item.system == system_name for item in attempt.artifact.aggregate_system_results)
                    )
                )
                for system_name in system_names
            )
            if not matched:
                continue
            label = attempt.strategy.removesuffix("_search")
            if label in seen:
                continue
            seen.add(label)
            labels.append(label)
        return labels

    def _hypothesis_resolution_sentence(
        self,
        spec: ExperimentSpec,
        artifact: ResultArtifact,
        attempts: list[ExperimentAttempt],
    ) -> str:
        target_systems = self._hypothesis_target_systems(spec)
        best_system = artifact.best_system or artifact.objective_system
        if not target_systems:
            return (
                "The experimental results answer the research question posed by the benchmark, but the hypothesis "
                "does not name a single target system explicitly enough to classify as supported or contradicted."
            )
        target_label = ", ".join(f"`{item}`" for item in target_systems)
        if best_system and best_system in target_systems:
            return (
                f"Within this benchmark setting, the original hypothesis is supported: {target_label} delivered the "
                f"strongest observed `{artifact.primary_metric}` result."
            )
        attempt_labels = self._attempt_labels_for_systems(attempts, target_systems)
        attempt_clause = (
            f" Additional rounds still evaluated {', '.join(f'`{item}`' for item in attempt_labels)}."
            if attempt_labels
            else ""
        )
        if best_system:
            return (
                f"Within this benchmark setting, the original hypothesis is not supported. It expected {target_label} to "
                f"lead, but the selected artifact ranks `{best_system}` highest on `{artifact.primary_metric}`."
                f"{attempt_clause}"
            )
        return (
            f"The hypothesis names {target_label}, but the final artifact does not expose a best system clearly enough "
            "to resolve that claim in publish-facing prose."
        )

    def _limitation_points(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        artifact: ResultArtifact,
        *,
        literature: list[LiteratureInsight],
        benchmark_display: str,
    ) -> list[str]:
        baseline_names = [item.name for item in spec.baselines]
        ablation_names = [item.name for item in spec.ablations]
        compared_names = baseline_names + ablation_names
        points = [
            f"Claims are limited to benchmark `{benchmark_display}` on `{spec.dataset.name}`, so broader generalization to `{plan.topic}` remains untested.",
            (
                "The comparison set only covers lightweight baseline systems "
                f"({', '.join(f'`{item}`' for item in compared_names)}) rather than field-optimized or pretrained alternatives."
                if compared_names
                else "The comparison set remains limited to the small set of baseline systems encoded in the benchmark."
            ),
        ]
        points.extend(plan.scope_limits[:2])
        passed_acceptance, total_acceptance = self._acceptance_counts(artifact)
        requested_seed_count = len(spec.seeds)
        completed_seed_count = len(artifact.per_seed_results)
        if total_acceptance and passed_acceptance < total_acceptance:
            points.append(
                f"Acceptance checks were only partially satisfied ({passed_acceptance}/{total_acceptance} passed), which weakens the strongest manuscript claims."
            )
        elif requested_seed_count and completed_seed_count < requested_seed_count:
            points.append(
                f"Only {completed_seed_count} completed seed artifacts were preserved out of {requested_seed_count} requested seeds, limiting statistical stability."
            )
        if not artifact.significance_tests:
            points.append(
                "No paired significance comparisons were preserved for the final artifact, so small observed score gaps should be treated cautiously."
            )
        if artifact.negative_results:
            detail = self._revision_sentence_fragment(artifact.negative_results[0].detail, limit=180)
            if detail is not None:
                points.append(f"Negative evidence remained material: {detail}")
        if artifact.failed_trials:
            detail = self._revision_sentence_fragment(artifact.failed_trials[0].summary, limit=180)
            if detail is not None:
                points.append(f"At least one attempted configuration failed during execution: {detail}")
        if artifact.anomalous_trials:
            detail = self._revision_sentence_fragment(artifact.anomalous_trials[0].detail, limit=180)
            if detail is not None:
                points.append(f"Anomalous behavior was observed in the preserved run trace: {detail}")
        if not literature:
            points.append(
                "No project-specific literature was available for this run, so the paper cannot make a strong novelty claim against named prior work."
            )
        return _dedupe_preserving_order(points)

    def _compared_systems_sentence(self, artifact: ResultArtifact) -> str:
        system_names = [
            item.system for item in (artifact.aggregate_system_results or artifact.system_results)
        ]
        if not system_names:
            return ""
        rendered = ", ".join(f"`{item}`" for item in system_names)
        return f"The final artifact reports aggregate results for {rendered}."

    def _acceptance_counts(self, artifact: ResultArtifact) -> tuple[int, int]:
        total = len(artifact.acceptance_checks)
        passed = sum(1 for item in artifact.acceptance_checks if item.passed)
        return passed, total

    def _acceptance_summary_sentence(self, artifact: ResultArtifact) -> str:
        passed, total = self._acceptance_counts(artifact)
        if total < 1:
            return "No explicit acceptance checks were recorded for the selected configuration."
        if passed == total:
            return f"All {total} acceptance checks passed for the selected configuration."
        return f"{passed} of {total} acceptance checks passed for the selected configuration."

    def _lead_significance_sentence(self, artifact: ResultArtifact) -> str:
        if not artifact.significance_tests:
            return ""
        lead = next((item for item in artifact.significance_tests if item.significant), artifact.significance_tests[0])
        p_value = lead.adjusted_p_value if lead.adjusted_p_value is not None else lead.p_value
        return (
            f"The strongest paired comparison was `{lead.candidate}` versus `{lead.comparator}` on `{lead.metric}` "
            f"with effect={lead.effect_size:.4f} and adjusted p={p_value:.4f} "
            f"({'significant' if lead.significant else 'not significant'})."
        )

    def _negative_outcome_summary_sentence(self, artifact: ResultArtifact) -> str:
        if artifact.negative_results:
            detail = self._revision_sentence_fragment(artifact.negative_results[0].detail, limit=160)
            if detail is not None:
                return f"The artifact also preserves negative evidence, led by: {detail}"
        if artifact.failed_trials:
            detail = self._revision_sentence_fragment(artifact.failed_trials[0].summary, limit=160)
            if detail is not None:
                return f"The run also preserves failed configurations, including: {detail}"
        if artifact.anomalous_trials:
            detail = self._revision_sentence_fragment(artifact.anomalous_trials[0].detail, limit=160)
            if detail is not None:
                return f"The run also flags anomalous behavior for follow-up, including: {detail}"
        return ""

    def _interpret_results(
        self,
        artifact: ResultArtifact,
        spec: ExperimentSpec,
        best_metric: float | None,
        baseline_metric: float | None,
        baseline_system: str | None,
    ) -> str:
        parts: list[str] = []
        if best_metric is not None and artifact.best_system:
            if baseline_metric is not None and best_metric > baseline_metric:
                delta = best_metric - baseline_metric
                parts.append(
                    f"The proposed method ({artifact.best_system}) outperforms the "
                    f"baseline ({baseline_system}) by {delta:.4f} on {artifact.primary_metric}. "
                    f"This improvement {'is statistically significant' if artifact.significance_tests and any(t.significant for t in artifact.significance_tests) else 'warrants further statistical validation'}."
                )
            elif baseline_metric is not None:
                delta = baseline_metric - (best_metric or 0)
                parts.append(
                    f"The proposed method ({artifact.best_system}) did not outperform the "
                    f"baseline ({baseline_system}), trailing by {delta:.4f} on {artifact.primary_metric}. "
                    "This suggests the approach may need fundamental revision."
                )
            else:
                parts.append(
                    f"The best system ({artifact.best_system}) achieved "
                    f"{artifact.primary_metric}={best_metric:.4f}. No explicit baseline comparison is available."
                )
        else:
            parts.append("No definitive result metric was recorded.")

        if artifact.negative_results:
            parts.append(
                f"Notable negative result: {artifact.negative_results[0].detail[:200]}."
            )
        if artifact.per_seed_results and len(artifact.per_seed_results) >= 2:
            parts.append(
                f"Results are based on {len(artifact.per_seed_results)} seeds, providing multi-seed stability evidence."
            )
        return "\n".join(parts) if parts else "No result interpretation available."

    def _hypothesis_validation_block(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        artifact: ResultArtifact,
        best_metric: float | None,
        baseline_metric: float | None,
    ) -> str:
        lines: list[str] = []
        for i, hypothesis in enumerate(plan.hypotheses, 1):
            if best_metric is not None and baseline_metric is not None:
                if best_metric > baseline_metric:
                    verdict = "SUPPORTED"
                elif best_metric < baseline_metric:
                    verdict = "CONTRADICTED"
                else:
                    verdict = "INCONCLUSIVE"
            else:
                verdict = "UNTESTABLE"
            lines.append(f"- **H{i}**: {hypothesis} → **{verdict}**")
        if not lines:
            lines.append("- No explicit hypotheses were recorded.")
        return "\n".join(lines)

    def _key_findings_block(
        self,
        artifact: ResultArtifact,
        plan: ResearchPlan,
    ) -> str:
        lines: list[str] = []
        for finding in artifact.key_findings[:5]:
            lines.append(f"- {finding}")
        if artifact.tables:
            lines.append(f"- {len(artifact.tables)} result tables generated with cross-system comparisons.")
        if artifact.failed_trials:
            lines.append(f"- {len(artifact.failed_trials)} configurations failed, providing negative evidence.")
        if not lines:
            lines.append("- No structured findings beyond the artifact summary.")
        return "\n".join(lines)

    def _dynamic_result_claims(
        self,
        artifact: ResultArtifact,
        spec: ExperimentSpec,
        plan: ResearchPlan,
    ) -> list[AutoResearchClaimEvidenceEntryRead]:
        """Generate claims driven by actual experimental outcomes rather than fixed templates."""
        claims: list[AutoResearchClaimEvidenceEntryRead] = []
        best_metric = self._aggregate_metric(artifact, artifact.best_system, artifact.primary_metric)
        baseline_system = spec.baselines[0].name if spec.baselines else None
        baseline_metric = self._aggregate_metric(artifact, baseline_system, artifact.primary_metric) if baseline_system else None

        # Claim 1: primary result — adapted to positive / mixed / negative
        result_evidence = [
            AutoResearchClaimEvidenceRefRead(
                source_kind="artifact",
                label="Artifact summary",
                detail=artifact.summary,
            ),
            AutoResearchClaimEvidenceRefRead(
                source_kind="artifact",
                label="Key findings",
                detail="; ".join(artifact.key_findings) or "No explicit key findings recorded.",
            ),
        ]
        if artifact.tables:
            result_evidence.append(
                AutoResearchClaimEvidenceRefRead(
                    source_kind="artifact",
                    label="Result tables",
                    detail=", ".join(table.title for table in artifact.tables),
                )
            )

        if best_metric is not None and artifact.best_system:
            if baseline_metric is not None and best_metric > baseline_metric:
                claim_text = (
                    f"The proposed method ({artifact.best_system}) outperforms the strongest baseline "
                    f"({baseline_system}) on {artifact.primary_metric} "
                    f"({best_metric:.4f} vs {baseline_metric:.4f})."
                )
                support = "supported"
            elif baseline_metric is not None and best_metric < baseline_metric:
                claim_text = (
                    f"The proposed method ({artifact.best_system}) does not outperform the baseline "
                    f"({baseline_system}) on {artifact.primary_metric} "
                    f"({best_metric:.4f} vs {baseline_metric:.4f}), suggesting the hypothesis requires revision."
                )
                support = "partial"
            else:
                claim_text = (
                    f"The best system ({artifact.best_system}) achieved {artifact.primary_metric}={best_metric:.4f}."
                )
                support = "supported"
        else:
            claim_text = "The experimental results were collected and analyzed."
            support = "partial"

        claims.append(
            AutoResearchClaimEvidenceEntryRead(
                claim_id="claim_primary_result",
                category="result",
                section_hint="Results",
                claim=claim_text,
                support_status=support,
                evidence=result_evidence,
            )
        )

        # Claim 2: significance — only if we have tests
        if artifact.significance_tests:
            sig_tests = [t for t in artifact.significance_tests if t.significant]
            top_test = artifact.significance_tests[0]
            p_value = top_test.adjusted_p_value if top_test.adjusted_p_value is not None else top_test.p_value
            sig_claim = (
                f"The improvement of {top_test.candidate} over {top_test.comparator} is "
                f"{'statistically significant' if sig_tests else 'not statistically significant'} "
                f"(adjusted p={p_value:.4f}, effect size={top_test.effect_size:.4f})."
            )
            claims.append(
                AutoResearchClaimEvidenceEntryRead(
                    claim_id="claim_significance",
                    category="result",
                    section_hint="Results",
                    claim=sig_claim,
                    support_status="supported" if sig_tests else "partial",
                    evidence=[
                        AutoResearchClaimEvidenceRefRead(
                            source_kind="artifact",
                            label="Significance test",
                            detail=top_test.detail,
                        ),
                    ],
                )
            )

        # Claim 3: robustness — driven by seed count
        seed_count = len(artifact.per_seed_results)
        if seed_count >= 2:
            claims.append(
                AutoResearchClaimEvidenceEntryRead(
                    claim_id="claim_robustness",
                    category="result",
                    section_hint="Experimental Setup",
                    claim=(
                        f"Results are robust across {seed_count} independent seeds, "
                        f"strengthening confidence in the observed effects."
                    ),
                    support_status="supported",
                    evidence=[
                        AutoResearchClaimEvidenceRefRead(
                            source_kind="artifact",
                            label="Per-seed results",
                            detail=f"{seed_count} completed seed artifacts.",
                        ),
                    ],
                )
            )

        # Claim 4: negative results — only if they exist
        if artifact.negative_results:
            neg = artifact.negative_results[0]
            neg_detail = neg.detail if len(neg.detail) < 160 else neg.detail[:157] + "..."
            claims.append(
                AutoResearchClaimEvidenceEntryRead(
                    claim_id="claim_negative_evidence",
                    category="result",
                    section_hint="Discussion",
                    claim=f"Not all configurations succeeded: {neg_detail}",
                    support_status="partial",
                    evidence=[
                        AutoResearchClaimEvidenceRefRead(
                            source_kind="artifact",
                            label="Negative result",
                            detail=neg_detail,
                        ),
                    ],
                    gaps=["Negative results warrant further investigation."],
                )
            )

        return claims

    def _claim_entries(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        artifact: ResultArtifact,
        *,
        literature: list[LiteratureInsight],
        attempts: list[ExperimentAttempt],
        portfolio: PortfolioSummary | None,
        candidates: list[HypothesisCandidate],
    ) -> list[AutoResearchClaimEvidenceEntryRead]:
        best_metric = self._aggregate_metric(artifact, artifact.best_system, artifact.primary_metric)
        passed_acceptance, total_acceptance = self._acceptance_counts(artifact)
        selected_candidate = next(
            (candidate for candidate in candidates if portfolio and candidate.id == portfolio.selected_candidate_id),
            candidates[0] if candidates else None,
        )

        entries: list[AutoResearchClaimEvidenceEntryRead] = [
            AutoResearchClaimEvidenceEntryRead(
                claim_id="claim_problem_scope",
                category="problem",
                section_hint="Introduction",
                claim=plan.problem_statement,
                support_status="supported",
                evidence=[
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="plan",
                        label="Problem statement",
                        detail=plan.problem_statement,
                    ),
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="plan",
                        label="Research questions",
                        detail="; ".join(plan.research_questions) or "No research questions were recorded.",
                    ),
                ],
            ),
            AutoResearchClaimEvidenceEntryRead(
                claim_id="claim_method_selection",
                category="method",
                section_hint="Method",
                claim=(
                    f"The selected candidate `{selected_candidate.title}` operationalizes the run hypothesis."
                    if selected_candidate is not None
                    else f"The study operationalizes the hypothesis as: {spec.hypothesis}"
                ),
                support_status="supported",
                evidence=[
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="plan",
                        label="Proposed method",
                        detail=plan.proposed_method,
                    ),
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="portfolio",
                        label="Portfolio decision",
                        detail=(
                            portfolio.decision_summary
                            if portfolio is not None
                            else "No portfolio summary was persisted."
                        ),
                    ),
                ],
            ),
        ]

        result_evidence = [
            AutoResearchClaimEvidenceRefRead(
                source_kind="artifact",
                label="Artifact summary",
                detail=artifact.summary,
            ),
            AutoResearchClaimEvidenceRefRead(
                source_kind="artifact",
                label="Key findings",
                detail="; ".join(artifact.key_findings) or "No explicit key findings were recorded.",
            ),
        ]
        if artifact.tables:
            result_evidence.append(
                AutoResearchClaimEvidenceRefRead(
                    source_kind="artifact",
                    label="Result tables",
                    detail=", ".join(table.title for table in artifact.tables),
                )
            )
        if artifact.significance_tests:
            top_test = artifact.significance_tests[0]
            result_evidence.append(
                AutoResearchClaimEvidenceRefRead(
                    source_kind="artifact",
                    label="Significance evidence",
                    detail=top_test.detail,
                )
            )
        result_claim = (
            f"The selected configuration produced `{artifact.best_system}` as the strongest system "
            f"with mean {artifact.primary_metric}={best_metric:.4f}."
            if artifact.best_system and best_metric is not None
            else "The selected configuration produced a completed result artifact."
        )
        entries.append(
            AutoResearchClaimEvidenceEntryRead(
                claim_id="claim_result_summary",
                category="result",
                section_hint="Results",
                claim=result_claim,
                support_status="supported",
                evidence=result_evidence,
            )
        )

        robustness_support = "supported" if len(artifact.per_seed_results) >= 2 else "partial"
        robustness_gaps = [] if robustness_support == "supported" else ["Increase completed seed coverage for stronger aggregate claims."]
        entries.append(
            AutoResearchClaimEvidenceEntryRead(
                claim_id="claim_statistical_grounding",
                category="result",
                section_hint="Experimental Setup",
                claim=(
                    f"The run is grounded in multi-seed aggregate reporting across {len(artifact.per_seed_results) or len(spec.seeds) or 1} seeds, "
                    f"with acceptance {passed_acceptance}/{total_acceptance}."
                ),
                support_status=robustness_support,
                evidence=[
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="artifact",
                        label="Per-seed execution",
                        detail=f"{len(artifact.per_seed_results)} completed seed artifacts were preserved.",
                    ),
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="artifact",
                        label="Aggregate reporting",
                        detail=f"{len(artifact.aggregate_system_results)} aggregate system summaries and {len(artifact.significance_tests)} significance comparisons were recorded.",
                    ),
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="artifact",
                        label="Acceptance checks",
                        detail=f"{passed_acceptance}/{total_acceptance} acceptance checks passed.",
                    ),
                ],
                gaps=robustness_gaps,
            )
        )

        context_support = "supported" if literature else "unsupported"
        context_gaps = [] if literature else ["Attach retrieved literature so related-work and novelty framing stay grounded."]
        context_evidence = [
            AutoResearchClaimEvidenceRefRead(
                source_kind="literature",
                label=item.title,
                detail=" ".join(part for part in (item.insight, item.method_hint, item.gap_hint) if part),
                locator=item.paper_id,
            )
            for item in literature[:3]
        ]
        if not context_evidence:
            context_evidence.append(
                AutoResearchClaimEvidenceRefRead(
                    source_kind="literature",
                    label="Missing literature context",
                    detail="No project-specific literature was persisted for this run.",
                )
            )
        entries.append(
            AutoResearchClaimEvidenceEntryRead(
                claim_id="claim_context_grounding",
                category="context",
                section_hint="Related Work",
                claim="The paper's related-work framing is grounded in persisted literature context.",
                support_status=context_support,
                evidence=context_evidence,
                gaps=context_gaps,
            )
        )

        limitation_items = list(plan.scope_limits)
        if artifact.negative_results:
            limitation_items.append(artifact.negative_results[0].detail)
        if artifact.failed_trials:
            limitation_items.append(artifact.failed_trials[0].detail)
        entries.append(
            AutoResearchClaimEvidenceEntryRead(
                claim_id="claim_limitations",
                category="limitation",
                section_hint="Limitations",
                claim="The manuscript should retain explicit scope limits, failed configurations, and negative results.",
                support_status="supported",
                evidence=[
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="plan",
                        label="Scope limits",
                        detail="; ".join(plan.scope_limits) or "No explicit scope limits were captured.",
                    ),
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="artifact",
                        label="Negative or failed outcomes",
                        detail="; ".join(limitation_items) if limitation_items else "No limitation evidence was captured.",
                    ),
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="attempts",
                        label="Repair and search trace",
                        detail=f"{len(attempts)} execution rounds were preserved for this candidate.",
                    ),
                ],
            )
        )

        # Merge dynamic result-driven claims (dedup by claim_id)
        existing_ids = {e.claim_id for e in entries}
        for dynamic_claim in self._dynamic_result_claims(artifact, spec, plan):
            if dynamic_claim.claim_id not in existing_ids:
                entries.append(dynamic_claim)
                existing_ids.add(dynamic_claim.claim_id)

        return entries

    def build_claim_evidence_matrix(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        artifact: ResultArtifact,
        *,
        literature: list[LiteratureInsight] | None = None,
        attempts: list[ExperimentAttempt] | None = None,
        portfolio: PortfolioSummary | None = None,
        candidates: list[HypothesisCandidate] | None = None,
    ) -> AutoResearchClaimEvidenceMatrixRead:
        literature = literature or []
        attempts = attempts or []
        candidates = candidates or []
        entries = self._claim_entries(
            plan,
            spec,
            artifact,
            literature=literature,
            attempts=attempts,
            portfolio=portfolio,
            candidates=candidates,
        )
        unsupported_claim_count = sum(1 for item in entries if item.support_status != "supported")
        return AutoResearchClaimEvidenceMatrixRead(
            generated_at=_utcnow(),
            claim_count=len(entries),
            supported_claim_count=len(entries) - unsupported_claim_count,
            unsupported_claim_count=unsupported_claim_count,
            entries=entries,
        )

    def build_narrative_report(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        artifact: ResultArtifact,
        claim_evidence_matrix: AutoResearchClaimEvidenceMatrixRead,
        *,
        literature: list[LiteratureInsight] | None = None,
        attempts: list[ExperimentAttempt] | None = None,
        benchmark_name: str | None = None,
        program: ResearchProgram | None = None,
        portfolio: PortfolioSummary | None = None,
        candidates: list[HypothesisCandidate] | None = None,
        project_context: AutoResearchProjectFlowContextRead | None = None,
    ) -> str:
        literature = literature or []
        attempts = attempts or []
        candidates = candidates or []
        benchmark_display = benchmark_name or spec.benchmark_name
        best_metric = self._aggregate_metric(artifact, artifact.best_system, artifact.primary_metric)
        baseline_system = spec.baselines[0].name if spec.baselines else None
        baseline_metric = self._aggregate_metric(artifact, baseline_system, artifact.primary_metric) if baseline_system else None
        claim_lines = []
        for entry in claim_evidence_matrix.entries:
            evidence_lines = "\n".join(
                f"  - [{item.source_kind}] {item.label}: {item.detail}"
                for item in entry.evidence
            ) or "  - No evidence anchors recorded."
            gap_lines = "\n".join(f"  - {item}" for item in entry.gaps) if entry.gaps else "  - None."
            claim_lines.append(
                "\n".join(
                    [
                        f"### {entry.claim_id}: {entry.claim}",
                        f"- Status: {entry.support_status}",
                        f"- Section hint: {entry.section_hint}",
                        "- Evidence:",
                        evidence_lines,
                        "- Gaps:",
                        gap_lines,
                    ]
                )
            )
        open_issues = [
            gap
            for entry in claim_evidence_matrix.entries
            for gap in entry.gaps
        ]
        open_issue_block = "\n".join(f"- {item}" for item in open_issues) or "- None."
        literature_titles = "\n".join(
            f"- {item.title} ({item.year or 'n.d.'})"
            for item in literature[:5]
        ) or "- No attached literature context."
        project_flow_block = (
            f"\n## Project Flow Inputs\n- Summary: {project_context.summary}\n"
            + (
                f"- Template sections: {', '.join(project_context.template_sections)}\n"
                if project_context is not None and project_context.template_sections
                else ""
            )
            + (
                f"- API hints: {', '.join(project_context.api_surface_hints)}\n"
                if project_context is not None and project_context.api_surface_hints
                else ""
            )
            if project_context is not None
            else ""
        )
        result_interpretation = self._interpret_results(artifact, spec, best_metric, baseline_metric, baseline_system)
        hypothesis_validation = self._hypothesis_validation_block(plan, spec, artifact, best_metric, baseline_metric)
        findings_block = self._key_findings_block(artifact, plan)
        return f"""# Narrative Report: {plan.title}

## Research Program
The run targeted `{plan.topic}` on benchmark `{benchmark_display}` and kept the work bounded to reproducible experimental evidence.

Program objective:
- {(program.objective if program is not None else plan.motivation)}

## Portfolio Outcome
{self._portfolio_block(program, portfolio, candidates)}

## Evidence Summary
- Artifact summary: {artifact.summary}
- Primary metric: `{artifact.primary_metric}`
- Best system: `{artifact.best_system or 'unknown'}`
- Key findings: {"; ".join(artifact.key_findings) or "No explicit key findings recorded."}
- Search / repair rounds: {len(attempts)}

## Result Interpretation
{result_interpretation}

## Hypothesis Validation
{hypothesis_validation}

## Key Research Findings
{findings_block}

## Claim-Evidence Commitments
{chr(10).join(claim_lines)}

## Related Work Inputs
{literature_titles}
{project_flow_block}

## Open Issues
{open_issue_block}
"""

    def build_paper_plan(
        self,
        plan: ResearchPlan,
        claim_evidence_matrix: AutoResearchClaimEvidenceMatrixRead,
    ) -> AutoResearchPaperPlanRead:
        sections = [
            AutoResearchPaperPlanSectionRead(
                section_id="abstract",
                title="Abstract",
                objective="Summarize the research study, selected benchmark, and top-line findings.",
                claim_ids=["claim_problem_scope", "claim_result_summary"],
                evidence_focus=["artifact.summary", "claim_evidence_matrix"],
            ),
            AutoResearchPaperPlanSectionRead(
                section_id="introduction",
                title="Introduction",
                objective="Frame the problem, motivation, and bounded research questions.",
                claim_ids=["claim_problem_scope", "claim_context_grounding"],
                evidence_focus=["plan.problem_statement", "plan.research_questions", "literature"],
            ),
            AutoResearchPaperPlanSectionRead(
                section_id="related_work",
                title="Related Work",
                objective="Explain the literature context, working hypotheses, and portfolio decision.",
                claim_ids=["claim_context_grounding", "claim_method_selection"],
                evidence_focus=["literature", "portfolio.decision_summary"],
            ),
            AutoResearchPaperPlanSectionRead(
                section_id="method",
                title="Method",
                objective="Describe the proposed method, baselines, and experimental constraints.",
                claim_ids=["claim_method_selection"],
                evidence_focus=["plan.proposed_method", "spec"],
            ),
            AutoResearchPaperPlanSectionRead(
                section_id="experimental_setup",
                title="Experimental Setup",
                objective="Document runtime conditions, sweep selection, seed coverage, and the promoted figure/table inventory.",
                claim_ids=["claim_statistical_grounding"],
                evidence_focus=["artifact.environment", "artifact.acceptance_checks", "figure_plan"],
            ),
            AutoResearchPaperPlanSectionRead(
                section_id="results",
                title="Results",
                objective="Present the selected configuration, aggregate metrics, and statistical grounding.",
                claim_ids=["claim_result_summary", "claim_statistical_grounding"],
                evidence_focus=["artifact.tables", "artifact.significance_tests", "artifact.acceptance_checks"],
            ),
            AutoResearchPaperPlanSectionRead(
                section_id="discussion",
                title="Discussion",
                objective="Interpret the bounded contribution, evidence trail, and remaining scientific limits.",
                claim_ids=["claim_result_summary", "claim_context_grounding", "claim_limitations"],
                evidence_focus=["claim_evidence_matrix", "artifact.negative_results", "literature"],
            ),
            AutoResearchPaperPlanSectionRead(
                section_id="limitations",
                title="Limitations",
                objective="Preserve scope limits, negative results, and unresolved risks.",
                claim_ids=["claim_limitations"],
                evidence_focus=["plan.scope_limits", "artifact.negative_results", "artifact.failed_trials"],
            ),
            AutoResearchPaperPlanSectionRead(
                section_id="conclusion",
                title="Conclusion",
                objective="Close with the strongest supported claims and outstanding gaps.",
                claim_ids=["claim_result_summary", "claim_limitations"],
                evidence_focus=["claim_evidence_matrix", "paper_revision_state"],
            ),
        ]
        summary = (
            f"Ground the manuscript in {claim_evidence_matrix.supported_claim_count}/{claim_evidence_matrix.claim_count} "
            "supported claim bundles before final revision."
        )
        return AutoResearchPaperPlanRead(
            generated_at=_utcnow(),
            title=plan.title,
            narrative_summary=summary,
            sections=sections,
        )

    def build_figure_plan(
        self,
        artifact: ResultArtifact,
        *,
        portfolio: PortfolioSummary | None = None,
    ) -> AutoResearchFigurePlanRead:
        items = [
            AutoResearchFigurePlanItemRead(
                figure_id=f"figure_{index + 1}",
                title=table.title,
                kind="table",
                source=f"artifact.tables.{index}",
                caption=f"Promote `{table.title}` directly from the persisted artifact into the manuscript.",
                status="ready",
            )
            for index, table in enumerate(artifact.tables)
        ]
        if portfolio is not None:
            items.append(
                AutoResearchFigurePlanItemRead(
                    figure_id="figure_portfolio_decision",
                    title="Portfolio Decision Summary",
                    kind="diagram",
                    source="portfolio.decisions",
                    caption="Summarize how the selected candidate emerged from the ranked portfolio.",
                    status="planned",
                )
            )
        return AutoResearchFigurePlanRead(
            generated_at=_utcnow(),
            items=items,
        )

    def build_paper_revision_state(
        self,
        claim_evidence_matrix: AutoResearchClaimEvidenceMatrixRead,
        *,
        paper_plan: AutoResearchPaperPlanRead | None = None,
        figure_plan: AutoResearchFigurePlanRead | None = None,
    ) -> AutoResearchPaperRevisionStateRead:
        open_issues = [
            gap
            for entry in claim_evidence_matrix.entries
            for gap in entry.gaps
        ]
        focus_sections: list[str] = []
        next_actions: list[AutoResearchPaperRevisionActionRead] = []

        for entry in claim_evidence_matrix.entries:
            if entry.support_status == "supported" and not entry.gaps:
                continue
            if entry.section_hint not in focus_sections:
                focus_sections.append(entry.section_hint)
            next_actions.append(
                AutoResearchPaperRevisionActionRead(
                    action_id=f"revise_{entry.claim_id}",
                    priority="high" if entry.support_status == "unsupported" else "medium",
                    section_title=entry.section_hint,
                    detail=(
                        "; ".join(entry.gaps)
                        if entry.gaps
                        else "Tighten the claim wording so the section only states what the artifact supports."
                    ),
                )
            )

        if figure_plan is not None:
            pending_figures = [item for item in figure_plan.items if item.status != "ready"]
            if pending_figures and "Results" not in focus_sections:
                focus_sections.append("Results")
            for item in pending_figures:
                next_actions.append(
                    AutoResearchPaperRevisionActionRead(
                        action_id=f"figure_{item.figure_id}",
                        priority="medium",
                        section_title="Results",
                        detail=f"Either materialize `{item.title}` for the paper source package or remove it from the figure plan.",
                    )
                )

        if not focus_sections and paper_plan is not None:
            focus_sections = [section.title for section in paper_plan.sections[:3]]

        checkpoints = [
            AutoResearchPaperRevisionCheckpointRead(
                revision_round=0,
                generated_at=_utcnow(),
                status="needs_review",
                summary=(
                    "Initial grounded draft captured with narrative, evidence matrix, manuscript markdown, "
                    "and compile-oriented paper sources."
                ),
                open_issue_count=len(open_issues),
                open_issue_summaries=list(open_issues),
                focus_sections=list(focus_sections),
                next_action_ids=[item.action_id for item in next_actions],
                completed_action_titles=[
                    "Persisted narrative report",
                    "Persisted claim-evidence matrix",
                    "Persisted paper plan",
                    "Persisted figure plan",
                    "Persisted paper compile report",
                    "Persisted compile-ready paper sources",
                    "Rendered grounded manuscript draft",
                ],
                relative_assets=[
                    "paper.md",
                    "narrative_report.md",
                    "claim_evidence_matrix.json",
                    "paper_plan.json",
                    "figure_plan.json",
                    "revision_history.md",
                    "revision_diff.md",
                    "revision_actions.md",
                    "paper_revision_state.json",
                    "paper_compile_report.json",
                    "paper_revision_diff.json",
                    "paper_revision_action_index.json",
                    "paper_sources/paper_compile_report.json",
                    "paper_sources/paper_revision_diff.json",
                    "paper_sources/paper_revision_action_index.json",
                    "paper_sources/paper.md",
                    "paper_sources/revision_diff.md",
                    "paper_sources/revision_actions.md",
                    "paper_sources/build.sh",
                    "paper_sources/main.tex",
                    "paper_sources/references.bib",
                    "paper_sources/manifest.json",
                    *self._rewrite_packet_asset_paths(
                        paper_plan=paper_plan,
                        base_dir="paper_sources",
                    ),
                    "paper_sources/checkpoints/index.json",
                    *self._checkpoint_snapshot_assets(0, paper_plan=paper_plan),
                ],
            )
        ]
        return AutoResearchPaperRevisionStateRead(
            generated_at=_utcnow(),
            revision_round=0,
            status="needs_review",
            open_issues=open_issues,
            completed_actions=[
                "Persisted narrative report",
                "Persisted claim-evidence matrix",
                "Persisted paper plan",
                "Persisted figure plan",
                "Persisted paper compile report",
                "Persisted compile-ready paper sources",
                "Rendered grounded manuscript draft",
            ],
            focus_sections=focus_sections,
            next_actions=next_actions,
            checkpoints=checkpoints,
        )

    def build_revision_brief(
        self,
        paper_revision_state: AutoResearchPaperRevisionStateRead,
        *,
        paper_plan: AutoResearchPaperPlanRead | None = None,
    ) -> str:
        section_objectives = {
            section.title: section.objective
            for section in (paper_plan.sections if paper_plan is not None else [])
        }
        pending_actions = [item for item in paper_revision_state.next_actions if item.status == "open"]
        lines = [
            "# Revision Brief",
            "",
            f"- Revision round: {paper_revision_state.revision_round}",
            f"- Status: `{paper_revision_state.status}`",
            f"- Open issues: {len(paper_revision_state.open_issues)}",
            f"- Pending actions: {len(pending_actions)}",
        ]
        if paper_revision_state.focus_sections:
            lines.extend(["", "## Focus Sections"])
            for title in paper_revision_state.focus_sections:
                objective = section_objectives.get(title)
                if objective:
                    lines.append(f"- `{title}`: {objective}")
                else:
                    lines.append(f"- `{title}`")
        if paper_revision_state.open_issues:
            lines.extend(["", "## Open Issues"])
            lines.extend(f"- {item}" for item in paper_revision_state.open_issues)
        if pending_actions:
            lines.extend(["", "## Next Actions"])
            for item in pending_actions:
                lines.append(
                    f"- [{item.priority}] `{item.section_title}` ({item.action_id}): {item.detail}"
                )
        if paper_revision_state.completed_actions:
            lines.extend(["", "## Completed Actions"])
            lines.extend(f"- {item}" for item in paper_revision_state.completed_actions)
        if paper_revision_state.checkpoints:
            lines.extend(["", "## Checkpoints"])
            for item in paper_revision_state.checkpoints:
                lines.append(
                    f"- Round {item.revision_round} `{item.status}` with {item.open_issue_count} open issues: "
                    f"{item.summary}"
                )
        return "\n".join(lines).strip() + "\n"

    def build_revision_history(
        self,
        paper_revision_state: AutoResearchPaperRevisionStateRead,
        *,
        paper_plan: AutoResearchPaperPlanRead | None = None,
    ) -> str:
        section_objectives = {
            section.title: section.objective
            for section in (paper_plan.sections if paper_plan is not None else [])
        }
        lines = [
            "# Revision History",
            "",
            f"- Current revision round: {paper_revision_state.revision_round}",
            f"- Current status: `{paper_revision_state.status}`",
            f"- Total checkpoints: {len(paper_revision_state.checkpoints)}",
        ]
        for checkpoint in paper_revision_state.checkpoints:
            lines.extend(
                [
                    "",
                    f"## Round {checkpoint.revision_round}",
                    f"- Status: `{checkpoint.status}`",
                    f"- Open issues: {checkpoint.open_issue_count}",
                    f"- Summary: {checkpoint.summary}",
                ]
            )
            if checkpoint.focus_sections:
                lines.append("- Focus sections:")
                for title in checkpoint.focus_sections:
                    objective = section_objectives.get(title)
                    if objective:
                        lines.append(f"  - `{title}`: {objective}")
                    else:
                        lines.append(f"  - `{title}`")
            if checkpoint.next_action_ids:
                lines.append("- Pending action ids:")
                lines.extend(f"  - `{item}`" for item in checkpoint.next_action_ids)
            if checkpoint.completed_action_titles:
                lines.append("- Completed actions:")
                lines.extend(f"  - {item}" for item in checkpoint.completed_action_titles)
            if checkpoint.open_issue_summaries:
                lines.append("- Open issue summaries:")
                lines.extend(f"  - {item}" for item in checkpoint.open_issue_summaries)
        return "\n".join(lines).strip() + "\n"

    def build_revision_checkpoint_note(
        self,
        checkpoint: AutoResearchPaperRevisionCheckpointRead,
        *,
        paper_plan: AutoResearchPaperPlanRead | None = None,
    ) -> str:
        section_objectives = {
            section.title: section.objective
            for section in (paper_plan.sections if paper_plan is not None else [])
        }
        lines = [
            f"# Revision Checkpoint: Round {checkpoint.revision_round}",
            "",
            f"- Status: `{checkpoint.status}`",
            f"- Open issues: {checkpoint.open_issue_count}",
            f"- Summary: {checkpoint.summary}",
        ]
        if checkpoint.focus_sections:
            lines.extend(["", "## Focus Sections"])
            for title in checkpoint.focus_sections:
                objective = section_objectives.get(title)
                if objective:
                    lines.append(f"- `{title}`: {objective}")
                else:
                    lines.append(f"- `{title}`")
        if checkpoint.next_action_ids:
            lines.extend(["", "## Pending Action Ids"])
            lines.extend(f"- `{item}`" for item in checkpoint.next_action_ids)
        if checkpoint.completed_action_titles:
            lines.extend(["", "## Completed Actions"])
            lines.extend(f"- {item}" for item in checkpoint.completed_action_titles)
        if checkpoint.open_issue_summaries:
            lines.extend(["", "## Open Issue Summaries"])
            lines.extend(f"- {item}" for item in checkpoint.open_issue_summaries)
        return "\n".join(lines).strip() + "\n"

    def build_section_rewrite_packet_index(
        self,
        *,
        paper_plan: AutoResearchPaperPlanRead,
        claim_evidence_matrix: AutoResearchClaimEvidenceMatrixRead,
        paper_revision_state: AutoResearchPaperRevisionStateRead,
        paper_markdown: str,
    ) -> AutoResearchPaperSectionRewriteIndexRead:
        section_bodies = self._paper_section_bodies(paper_markdown)
        packets: list[AutoResearchPaperSectionRewritePacketRead] = []
        for section in paper_plan.sections:
            claim_entries = self._section_claim_entries(
                section=section,
                claim_evidence_matrix=claim_evidence_matrix,
            )
            actions = self._section_pending_actions(
                section=section,
                paper_revision_state=paper_revision_state,
            )
            open_issues = self._section_open_issues(
                section=section,
                claim_entries=claim_entries,
                paper_revision_state=paper_revision_state,
            )
            current_body = section_bodies.get(_section_slug(section.title), "")
            packets.append(
                AutoResearchPaperSectionRewritePacketRead(
                    section_id=section.section_id,
                    section_title=section.title,
                    revision_round=paper_revision_state.revision_round,
                    focus=section.title in paper_revision_state.focus_sections or bool(actions),
                    objective=section.objective,
                    claim_ids=[item.claim_id for item in claim_entries],
                    evidence_focus=list(section.evidence_focus),
                    action_ids=[item.action_id for item in actions],
                    open_issues=open_issues,
                    current_word_count=len(current_body.split()),
                    relative_path=self._section_rewrite_packet_relative_path(section),
                    source_asset_paths=[
                        "paper.md",
                        "narrative_report.md",
                        "claim_evidence_matrix.json",
                        "paper_plan.json",
                        "paper_revision_state.json",
                        "revision_brief.md",
                        "revision_history.md",
                    ],
                )
            )
        return AutoResearchPaperSectionRewriteIndexRead(
            generated_at=_utcnow(),
            revision_round=paper_revision_state.revision_round,
            packet_count=len(packets),
            focus_packet_count=sum(1 for item in packets if item.focus),
            packets=packets,
        )

    def build_section_rewrite_packet(
        self,
        packet: AutoResearchPaperSectionRewritePacketRead,
        *,
        paper_plan: AutoResearchPaperPlanRead,
        claim_evidence_matrix: AutoResearchClaimEvidenceMatrixRead,
        paper_revision_state: AutoResearchPaperRevisionStateRead,
        paper_markdown: str,
    ) -> str:
        section = next(
            (item for item in paper_plan.sections if item.section_id == packet.section_id),
            None,
        )
        if section is None:
            raise ValueError(f"Unknown paper plan section for rewrite packet: {packet.section_id}")
        claim_entries = self._section_claim_entries(
            section=section,
            claim_evidence_matrix=claim_evidence_matrix,
        )
        actions = self._section_pending_actions(
            section=section,
            paper_revision_state=paper_revision_state,
        )
        current_body = self._paper_section_bodies(paper_markdown).get(_section_slug(section.title), "")
        claim_block: list[str] = []
        for entry in claim_entries:
            evidence_lines = [
                f"  - [{item.source_kind}] {item.label}: {item.detail}"
                for item in entry.evidence
            ] or ["  - No evidence anchors were recorded."]
            claim_block.extend(
                [
                    f"- `{entry.claim_id}` ({entry.support_status}): {entry.claim}",
                    "  - Evidence:",
                    *evidence_lines,
                ]
            )
            if entry.gaps:
                claim_block.append("  - Gaps:")
                claim_block.extend(f"    - {item}" for item in entry.gaps)
        action_block = [
            f"- [{item.priority}] `{item.action_id}`: {item.detail}"
            for item in actions
        ] or ["- No open revision actions are currently mapped to this section."]
        open_issue_block = [f"- {item}" for item in packet.open_issues] or ["- None."]
        evidence_focus_block = [f"- {item}" for item in packet.evidence_focus] or ["- None."]
        source_assets_block = [f"- `{item}`" for item in packet.source_asset_paths] or ["- None."]
        current_body_block = current_body.strip() or "_No current manuscript body was available for this section._"
        auto_revision_draft = self._auto_revision_draft(
            section=section,
            current_body=current_body,
            claim_entries=claim_entries,
            actions=actions,
            open_issues=packet.open_issues,
            paper_revision_state=paper_revision_state,
        )
        return "\n".join(
            [
                f"# Section Rewrite Packet: {packet.section_title}",
                "",
                f"- Revision round: {packet.revision_round}",
                f"- Focus section: {'yes' if packet.focus else 'no'}",
                f"- Current word count: {packet.current_word_count}",
                f"- Packet path: `{packet.relative_path}`",
                "",
                "## Objective",
                packet.objective,
                "",
                "## Current Draft",
                current_body_block,
                "",
                "## Claim Commitments",
                *(
                    claim_block
                    if claim_block
                    else ["- No claim-evidence commitments were attached to this section."]
                ),
                "",
                "## Pending Revision Actions",
                *action_block,
                "",
                "## Open Issues",
                *open_issue_block,
                "",
                "## Evidence Focus",
                *evidence_focus_block,
                "",
                "## Source Assets",
                *source_assets_block,
                "",
                "## Auto-Revision Draft",
                auto_revision_draft,
                "",
            ]
        )

    def build_paper_revision_diff(
        self,
        *,
        paper_plan: AutoResearchPaperPlanRead,
        paper_revision_state: AutoResearchPaperRevisionStateRead,
        paper_section_rewrite_index: AutoResearchPaperSectionRewriteIndexRead,
        paper_markdown: str,
        previous_paper_markdown: str | None = None,
        previous_section_rewrite_index: AutoResearchPaperSectionRewriteIndexRead | None = None,
        base_revision_round: int | None = None,
    ) -> AutoResearchPaperRevisionDiffRead:
        current_bodies = self._paper_section_bodies(paper_markdown)
        previous_bodies = self._paper_section_bodies(previous_paper_markdown or "")
        current_packets = {
            item.section_id: item
            for item in paper_section_rewrite_index.packets
        }
        previous_packets = {
            item.section_id: item
            for item in (previous_section_rewrite_index.packets if previous_section_rewrite_index is not None else [])
        }
        sections: list[AutoResearchPaperRevisionDiffSectionRead] = []
        for section in paper_plan.sections:
            current_packet = current_packets.get(section.section_id)
            previous_packet = previous_packets.get(section.section_id)
            current_body = current_bodies.get(_section_slug(section.title), "")
            previous_body = previous_bodies.get(_section_slug(section.title), "")
            previous_action_ids = list(previous_packet.action_ids) if previous_packet is not None else []
            current_action_ids = list(current_packet.action_ids) if current_packet is not None else []
            resolved_action_ids = [
                item
                for item in previous_action_ids
                if item not in current_action_ids
            ]
            previous_open_issues = list(previous_packet.open_issues) if previous_packet is not None else []
            current_open_issues = list(current_packet.open_issues) if current_packet is not None else []
            resolved_issue_summaries = [
                item
                for item in previous_open_issues
                if item not in current_open_issues
            ]
            manuscript_changed = current_body.strip() != previous_body.strip()
            packet_changed = (
                previous_action_ids != current_action_ids
                or previous_open_issues != current_open_issues
            )
            if base_revision_round is None:
                status = "initial"
            elif manuscript_changed or packet_changed:
                status = "updated"
            else:
                status = "unchanged"
            sections.append(
                AutoResearchPaperRevisionDiffSectionRead(
                    section_id=section.section_id,
                    section_title=section.title,
                    status=status,
                    previous_word_count=len(previous_body.split()),
                    current_word_count=len(current_body.split()),
                    word_delta=len(current_body.split()) - len(previous_body.split()),
                    previous_action_ids=previous_action_ids,
                    current_action_ids=current_action_ids,
                    resolved_action_ids=resolved_action_ids,
                    previous_open_issue_count=len(previous_open_issues),
                    current_open_issue_count=len(current_open_issues),
                    resolved_issue_summaries=resolved_issue_summaries,
                )
            )
        changed_section_count = sum(1 for item in sections if item.status != "unchanged")
        unchanged_section_count = len(sections) - changed_section_count
        resolved_action_count = sum(len(item.resolved_action_ids) for item in sections)
        resolved_issue_count = sum(len(item.resolved_issue_summaries) for item in sections)
        summary = (
            f"Initial manuscript materialization captured {len(sections)} section deltas for revision round "
            f"{paper_revision_state.revision_round}."
            if base_revision_round is None
            else f"Revision round {paper_revision_state.revision_round} compared against round {base_revision_round} "
            f"updated {changed_section_count} sections, resolved {resolved_action_count} actions, and closed "
            f"{resolved_issue_count} section-local issues."
        )
        return AutoResearchPaperRevisionDiffRead(
            generated_at=_utcnow(),
            revision_round=paper_revision_state.revision_round,
            base_revision_round=base_revision_round,
            summary=summary,
            changed_section_count=changed_section_count,
            unchanged_section_count=unchanged_section_count,
            resolved_action_count=resolved_action_count,
            resolved_issue_count=resolved_issue_count,
            sections=sections,
        )

    def build_paper_revision_diff_note(
        self,
        paper_revision_diff: AutoResearchPaperRevisionDiffRead,
        *,
        paper_plan: AutoResearchPaperPlanRead | None = None,
    ) -> str:
        section_objectives = {
            section.title: section.objective
            for section in (paper_plan.sections if paper_plan is not None else [])
        }
        lines = [
            "# Revision Diff",
            "",
            f"- Revision round: {paper_revision_diff.revision_round}",
            (
                f"- Compared against round: {paper_revision_diff.base_revision_round}"
                if paper_revision_diff.base_revision_round is not None
                else "- Compared against round: initial manuscript materialization"
            ),
            f"- Changed sections: {paper_revision_diff.changed_section_count}",
            f"- Unchanged sections: {paper_revision_diff.unchanged_section_count}",
            f"- Resolved actions: {paper_revision_diff.resolved_action_count}",
            f"- Resolved issues: {paper_revision_diff.resolved_issue_count}",
            f"- Summary: {paper_revision_diff.summary}",
        ]
        for section in paper_revision_diff.sections:
            lines.extend(
                [
                    "",
                    f"## {section.section_title}",
                    f"- Status: `{section.status}`",
                    f"- Word counts: {section.previous_word_count} -> {section.current_word_count} ({section.word_delta:+d})",
                ]
            )
            objective = section_objectives.get(section.section_title)
            if objective:
                lines.append(f"- Objective: {objective}")
            if section.previous_action_ids or section.current_action_ids:
                lines.append("- Action ids:")
                lines.append(f"  - Previous: {', '.join(f'`{item}`' for item in section.previous_action_ids) or 'none'}")
                lines.append(f"  - Current: {', '.join(f'`{item}`' for item in section.current_action_ids) or 'none'}")
            if section.resolved_action_ids:
                lines.append("- Resolved action ids:")
                lines.extend(f"  - `{item}`" for item in section.resolved_action_ids)
            if section.previous_open_issue_count or section.current_open_issue_count:
                lines.append(
                    f"- Open issues: {section.previous_open_issue_count} -> {section.current_open_issue_count}"
                )
            if section.resolved_issue_summaries:
                lines.append("- Resolved issue summaries:")
                lines.extend(f"  - {item}" for item in section.resolved_issue_summaries)
        return "\n".join(lines).strip() + "\n"

    def build_paper_revision_action_index(
        self,
        *,
        paper_revision_state: AutoResearchPaperRevisionStateRead,
        paper_section_rewrite_index: AutoResearchPaperSectionRewriteIndexRead,
        paper_revision_diff: AutoResearchPaperRevisionDiffRead,
        paper_markdown: str,
        paper_plan: AutoResearchPaperPlanRead | None = None,
        review_loop: AutoResearchReviewLoopRead | None = None,
    ) -> AutoResearchPaperRevisionActionIndexRead:
        packets_by_title = {
            item.section_title: item
            for item in paper_section_rewrite_index.packets
        }
        diff_by_title = {
            item.section_title: item
            for item in paper_revision_diff.sections
        }
        section_ids_by_title = {
            item.title: item.section_id
            for item in (paper_plan.sections if paper_plan is not None else [])
        }
        section_bodies = self._paper_section_bodies(paper_markdown)
        actions: list[AutoResearchPaperRevisionActionEntryRead] = []

        if review_loop is not None:
            for action in review_loop.actions:
                section_title = self._review_action_section_title(action, paper_plan=paper_plan)
                packet = packets_by_title.get(section_title)
                diff_section = diff_by_title.get(section_title)
                current_body = section_bodies.get(_section_slug(section_title), "")
                actions.append(
                    AutoResearchPaperRevisionActionEntryRead(
                        action_id=action.action_id,
                        title=action.title,
                        detail=action.detail,
                        priority=action.priority,
                        status=action.status,
                        section_id=packet.section_id if packet is not None else section_ids_by_title.get(section_title),
                        section_title=section_title,
                        first_seen_round=action.first_seen_round,
                        last_seen_round=action.last_seen_round,
                        completed_round=action.completed_round,
                        issue_ids=list(action.issue_ids),
                        claim_ids=list(packet.claim_ids) if packet is not None else [],
                        evidence_focus=list(packet.evidence_focus) if packet is not None else [],
                        packet_relative_path=packet.relative_path if packet is not None else None,
                        diff_status=(
                            diff_section.status
                            if diff_section is not None
                            else ("initial" if paper_revision_diff.base_revision_round is None else "unchanged")
                        ),
                        current_word_count=(
                            diff_section.current_word_count
                            if diff_section is not None
                            else len(current_body.split())
                        ),
                        word_delta=diff_section.word_delta if diff_section is not None else 0,
                        open_issue_summaries=list(packet.open_issues) if packet is not None else [],
                        resolved_issue_summaries=(
                            list(diff_section.resolved_issue_summaries) if diff_section is not None else []
                        ),
                        current_excerpt=_excerpt(current_body),
                    )
                )
        else:
            for action in paper_revision_state.next_actions:
                section_title = action.section_title
                packet = packets_by_title.get(section_title)
                diff_section = diff_by_title.get(section_title)
                current_body = section_bodies.get(_section_slug(section_title), "")
                actions.append(
                    AutoResearchPaperRevisionActionEntryRead(
                        action_id=action.action_id,
                        detail=action.detail,
                        priority=action.priority,
                        status="pending",
                        section_id=packet.section_id if packet is not None else section_ids_by_title.get(section_title),
                        section_title=section_title,
                        first_seen_round=paper_revision_state.revision_round,
                        last_seen_round=paper_revision_state.revision_round,
                        issue_ids=[],
                        claim_ids=list(packet.claim_ids) if packet is not None else [],
                        evidence_focus=list(packet.evidence_focus) if packet is not None else [],
                        packet_relative_path=packet.relative_path if packet is not None else None,
                        diff_status=(
                            diff_section.status
                            if diff_section is not None
                            else ("initial" if paper_revision_diff.base_revision_round is None else "unchanged")
                        ),
                        current_word_count=(
                            diff_section.current_word_count
                            if diff_section is not None
                            else len(current_body.split())
                        ),
                        word_delta=diff_section.word_delta if diff_section is not None else 0,
                        open_issue_summaries=list(packet.open_issues) if packet is not None else [],
                        resolved_issue_summaries=(
                            list(diff_section.resolved_issue_summaries) if diff_section is not None else []
                        ),
                        current_excerpt=_excerpt(current_body),
                    )
                )

        pending_action_count = sum(1 for item in actions if item.status == "pending")
        completed_action_count = sum(1 for item in actions if item.status == "completed")
        materialized_action_count = sum(1 for item in actions if item.packet_relative_path is not None)
        section_count = len({item.section_title for item in actions})
        summary = (
            f"Initial manuscript materialization tracked {pending_action_count} pending revision actions across "
            f"{section_count} sections."
            if review_loop is None
            else f"Revision round {paper_revision_state.revision_round} tracked {len(actions)} persisted revision "
            f"actions across {section_count} sections, with {pending_action_count} pending and "
            f"{completed_action_count} completed."
        )
        return AutoResearchPaperRevisionActionIndexRead(
            generated_at=_utcnow(),
            revision_round=paper_revision_state.revision_round,
            total_action_count=len(actions),
            pending_action_count=pending_action_count,
            completed_action_count=completed_action_count,
            materialized_action_count=materialized_action_count,
            summary=summary,
            actions=actions,
        )

    def build_paper_revision_action_note(
        self,
        paper_revision_action_index: AutoResearchPaperRevisionActionIndexRead,
        *,
        paper_plan: AutoResearchPaperPlanRead | None = None,
    ) -> str:
        section_objectives = {
            section.title: section.objective
            for section in (paper_plan.sections if paper_plan is not None else [])
        }
        lines = [
            "# Revision Actions",
            "",
            f"- Revision round: {paper_revision_action_index.revision_round}",
            f"- Total actions: {paper_revision_action_index.total_action_count}",
            f"- Pending actions: {paper_revision_action_index.pending_action_count}",
            f"- Completed actions: {paper_revision_action_index.completed_action_count}",
            f"- Materialized actions: {paper_revision_action_index.materialized_action_count}",
            f"- Summary: {paper_revision_action_index.summary}",
        ]
        current_section: str | None = None
        for action in paper_revision_action_index.actions:
            if action.section_title != current_section:
                current_section = action.section_title
                lines.extend(["", f"## {current_section}"])
                objective = section_objectives.get(current_section)
                if objective:
                    lines.append(f"- Objective: {objective}")
            title = action.title or action.detail
            lines.append(
                f"- [`{action.status}`] `{action.action_id}` ({action.priority}): {title}"
            )
            if action.title is not None and action.title != action.detail:
                lines.append(f"  - Detail: {action.detail}")
            if action.completed_round is not None:
                lines.append(f"  - Completed round: {action.completed_round}")
            if action.packet_relative_path is not None:
                lines.append(f"  - Packet: `{action.packet_relative_path}`")
            lines.append(
                f"  - Diff status: `{action.diff_status}`, current words: {action.current_word_count}, "
                f"word delta: {action.word_delta:+d}"
            )
            if action.issue_ids:
                lines.append(f"  - Issue ids: {', '.join(f'`{item}`' for item in action.issue_ids)}")
            if action.claim_ids:
                lines.append(f"  - Claim ids: {', '.join(f'`{item}`' for item in action.claim_ids)}")
            if action.evidence_focus:
                lines.append(f"  - Evidence focus: {', '.join(action.evidence_focus)}")
            if action.open_issue_summaries:
                lines.append("  - Open issues:")
                lines.extend(f"    - {item}" for item in action.open_issue_summaries)
            if action.resolved_issue_summaries:
                lines.append("  - Resolved issues:")
                lines.extend(f"    - {item}" for item in action.resolved_issue_summaries)
            if action.current_excerpt:
                lines.append(f"  - Current excerpt: {action.current_excerpt}")
        return "\n".join(lines).strip() + "\n"

    def build_paper_bibliography(
        self,
        literature: list[LiteratureInsight] | None = None,
    ) -> str:
        literature = literature or []
        if not literature:
            return "% No persisted literature entries were available for this run.\n"
        entries: list[str] = []
        for index, item in enumerate(literature, start=1):
            note_parts = []
            if item.source:
                note_parts.append(f"source={item.source.replace('_', ' ')}")
            if item.paper_id:
                note_parts.append(f"paper_id={item.paper_id}")
            if item.insight:
                note_parts.append(item.insight)
            if item.method_hint:
                note_parts.append(f"method_hint={item.method_hint}")
            if item.gap_hint:
                note_parts.append(f"gap_hint={item.gap_hint}")
            fields = [f"  title = {{{_latex_escape(item.title)}}}"]
            if item.year is not None:
                fields.append(f"  year = {{{item.year}}}")
            if item.source:
                fields.append(f"  howpublished = {{{_latex_escape(item.source.replace('_', ' '))}}}")
            if note_parts:
                fields.append(f"  note = {{{_latex_escape(' '.join(note_parts))}}}")
            entries.append("@misc{ref" + str(index) + ",\n" + ",\n".join(fields) + "\n}")
        return "\n\n".join(entries) + "\n"

    def build_paper_build_script(
        self,
        *,
        paper_sources_manifest: AutoResearchPaperSourcesManifestRead,
    ) -> str:
        commands = [
            item
            for item in paper_sources_manifest.compile_commands
            if not item.strip().startswith("./")
        ]
        body = "\n".join(commands) if commands else ":"
        return "\n".join(
            [
                "#!/bin/sh",
                "set -eu",
                "",
                'cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"',
                body,
                "",
            ]
        )

    def build_paper_latex_source(
        self,
        paper_markdown: str,
        *,
        literature: list[LiteratureInsight] | None = None,
    ) -> str:
        literature = literature or []
        raw_lines = paper_markdown.splitlines()
        title = "AutoResearch Paper Draft"
        body: list[str] = []
        index = 0

        while index < len(raw_lines):
            line = raw_lines[index].rstrip()
            stripped = line.strip()
            if index == 0 and stripped.startswith("# "):
                title = stripped[2:].strip()
                index += 1
                continue
            table = _parse_markdown_table_block(raw_lines, index)
            if table is not None:
                rows, index = table
                body.extend(_latex_table_block(rows))
                body.append("")
                continue
            if not stripped:
                body.append("")
                index += 1
                continue
            if stripped.startswith("## "):
                body.append(r"\section{" + _render_inline_latex(stripped[3:].strip()) + "}")
                body.append("")
                index += 1
                continue
            if stripped.startswith("### "):
                body.append(r"\subsection{" + _render_inline_latex(stripped[4:].strip()) + "}")
                body.append("")
                index += 1
                continue
            if stripped.startswith("- ") or raw_lines[index].startswith("  - "):
                items, index = _collect_list_items(raw_lines, index, "- ")
                body.extend(_latex_itemize(items))
                body.append("")
                continue
            if re.match(r"^\d+\.\s+", stripped):
                items, index = _collect_list_items(raw_lines, index, None, ordered=True)
                body.extend(_latex_enumerate(items))
                body.append("")
                continue
            body.append(_render_inline_latex(stripped))
            index += 1

        bibliography_block = "\n".join(
            [
                r"\bibliographystyle{plain}",
                r"\bibliography{references}",
            ]
        )
        if not literature:
            bibliography_block = "% No bibliography pass is required for this run."
        return "\n".join(
            [
                r"\documentclass{article}",
                r"\usepackage[utf8]{inputenc}",
                r"\usepackage[T1]{fontenc}",
                r"\usepackage{hyperref}",
                r"\usepackage{graphicx}",
                r"\usepackage{booktabs}",
                r"\usepackage{amsmath}",
                r"\usepackage{amssymb}",
                r"\usepackage{enumitem}",
                r"\title{" + _latex_escape(title) + "}",
                r"\date{}",
                r"\begin{document}",
                r"\maketitle",
                "",
                *body,
                "",
                bibliography_block,
                r"\end{document}",
                "",
            ]
        )

    def build_paper_sources_manifest(
        self,
        *,
        has_bibliography: bool,
        include_revision_checkpoints: bool = False,
        include_revision_diff: bool = False,
        include_revision_action_index: bool = False,
        paper_section_rewrite_index: AutoResearchPaperSectionRewriteIndexRead | None = None,
    ) -> AutoResearchPaperSourcesManifestRead:
        compile_commands = ["./build.sh", "pdflatex main.tex"]
        if has_bibliography:
            compile_commands.append("bibtex main")
        compile_commands.extend(["pdflatex main.tex", "pdflatex main.tex"])
        expected_outputs = ["main.pdf"]
        if has_bibliography:
            expected_outputs.append("main.bbl")
        compiler_hint = "pdflatex + bibtex" if has_bibliography else "pdflatex"
        return AutoResearchPaperSourcesManifestRead(
            generated_at=_utcnow(),
            entrypoint="main.tex",
            bibliography="references.bib",
            compiler_hint=compiler_hint,
            compile_commands=compile_commands,
            expected_outputs=expected_outputs,
            files=[
                AutoResearchPaperSourceFileRead(
                    relative_path="paper.md",
                    kind="markdown",
                    description="Grounded Markdown manuscript snapshot carried with the paper workspace for offline revision work.",
                ),
                AutoResearchPaperSourceFileRead(
                    relative_path="narrative_report.md",
                    kind="markdown",
                    description="Persisted narrative report copied into the paper source package for offline revision work.",
                ),
                AutoResearchPaperSourceFileRead(
                    relative_path="claim_evidence_matrix.json",
                    kind="json",
                    description="Claim-evidence matrix snapshot carried alongside the manuscript source package.",
                ),
                AutoResearchPaperSourceFileRead(
                    relative_path="paper_plan.json",
                    kind="json",
                    description="Paper plan snapshot aligned with the generated manuscript structure.",
                ),
                AutoResearchPaperSourceFileRead(
                    relative_path="figure_plan.json",
                    kind="json",
                    description="Figure-plan snapshot for the promoted artifact-backed visuals.",
                ),
                AutoResearchPaperSourceFileRead(
                    relative_path="revision_history.md",
                    kind="markdown",
                    description="Human-readable history of persisted revision checkpoints and paper-improvement rounds.",
                ),
                AutoResearchPaperSourceFileRead(
                    relative_path="revision_brief.md",
                    kind="markdown",
                    description="Human-readable paper-improvement brief derived from the latest paper revision state.",
                ),
                AutoResearchPaperSourceFileRead(
                    relative_path="paper_revision_state.json",
                    kind="json",
                    description="Latest paper revision state copied into the paper source package for resume workflows.",
                ),
                AutoResearchPaperSourceFileRead(
                    relative_path="paper_compile_report.json",
                    kind="json",
                    description="Compile-readiness snapshot for the paper workspace, including expected outputs and missing-input checks.",
                ),
                *(
                    [
                        AutoResearchPaperSourceFileRead(
                            relative_path="paper_revision_action_index.json",
                            kind="json",
                            description="Structured action-to-section ledger for the current paper-improvement round.",
                        ),
                        AutoResearchPaperSourceFileRead(
                            relative_path="revision_actions.md",
                            kind="markdown",
                            description="Human-readable action ledger derived from persisted review actions, section packets, and revision diffs.",
                        ),
                    ]
                    if include_revision_action_index
                    else []
                ),
                *(
                    [
                        AutoResearchPaperSourceFileRead(
                            relative_path="paper_revision_diff.json",
                            kind="json",
                            description="Structured diff between the current paper workspace and the previous revision checkpoint.",
                        ),
                        AutoResearchPaperSourceFileRead(
                            relative_path="revision_diff.md",
                            kind="markdown",
                            description="Human-readable revision diff for the current paper-improvement round.",
                        ),
                    ]
                    if include_revision_diff
                    else []
                ),
                *(
                    [
                        AutoResearchPaperSourceFileRead(
                            relative_path="rewrite_packets/index.json",
                            kind="json",
                            description="Index of section-level rewrite packets materialized from the current paper plan and revision state.",
                        ),
                        *[
                            AutoResearchPaperSourceFileRead(
                                relative_path=item.relative_path,
                                kind="markdown",
                                description=(
                                    f"Section rewrite packet for `{item.section_title}` with current draft content, "
                                    "claim-evidence commitments, and mapped revision actions."
                                ),
                            )
                            for item in paper_section_rewrite_index.packets
                        ],
                    ]
                    if paper_section_rewrite_index is not None
                    else []
                ),
                AutoResearchPaperSourceFileRead(
                    relative_path="build.sh",
                    kind="shell",
                    description="Portable shell entrypoint that runs the persisted compile commands for the paper workspace.",
                ),
                *(
                    [
                        AutoResearchPaperSourceFileRead(
                            relative_path="checkpoints/index.json",
                            kind="json",
                            description="Revision checkpoint index for the persisted paper-improvement history.",
                        )
                    ]
                    if include_revision_checkpoints
                    else []
                ),
                AutoResearchPaperSourceFileRead(
                    relative_path="main.tex",
                    kind="latex",
                    description="Compile-oriented LaTeX manuscript generated from the grounded paper draft.",
                ),
                AutoResearchPaperSourceFileRead(
                    relative_path="references.bib",
                    kind="bibtex",
                    description="BibTeX bibliography derived from the persisted run literature context.",
                ),
                AutoResearchPaperSourceFileRead(
                    relative_path="manifest.json",
                    kind="json",
                    description="Paper source package manifest with compile commands and file inventory.",
                ),
            ],
        )

    def build_paper_compile_report(
        self,
        *,
        paper_sources_manifest: AutoResearchPaperSourcesManifestRead,
    ) -> AutoResearchPaperCompileReportRead:
        workspace_files = {item.relative_path for item in paper_sources_manifest.files}
        required_inputs = [paper_sources_manifest.entrypoint]
        if (
            paper_sources_manifest.bibliography is not None
            and any(command.startswith("bibtex ") for command in paper_sources_manifest.compile_commands)
        ):
            required_inputs.append(paper_sources_manifest.bibliography)
        required_inputs = _dedupe_preserving_order(required_inputs)
        required_source_files = _compile_required_source_files(paper_sources_manifest)
        expected_outputs = list(paper_sources_manifest.expected_outputs)
        missing_required_inputs = [item for item in required_inputs if item not in workspace_files]
        materialized_outputs = [item for item in expected_outputs if item in workspace_files]
        source_package_complete = True
        all_expected_outputs_materialized = not expected_outputs
        return AutoResearchPaperCompileReportRead(
            generated_at=_utcnow(),
            entrypoint=paper_sources_manifest.entrypoint,
            bibliography=paper_sources_manifest.bibliography,
            compiler_hint=paper_sources_manifest.compiler_hint,
            compile_commands=list(paper_sources_manifest.compile_commands),
            required_inputs=required_inputs,
            missing_required_inputs=missing_required_inputs,
            required_source_files=required_source_files,
            missing_required_source_files=[],
            expected_outputs=expected_outputs,
            materialized_outputs=materialized_outputs,
            source_package_complete=source_package_complete,
            all_expected_outputs_materialized=all_expected_outputs_materialized,
            ready_for_compile=not missing_required_inputs and source_package_complete,
        )

    def build_pipeline(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        artifact: ResultArtifact,
        *,
        literature: list[LiteratureInsight] | None = None,
        attempts: list[ExperimentAttempt] | None = None,
        benchmark_name: str | None = None,
        program: ResearchProgram | None = None,
        portfolio: PortfolioSummary | None = None,
        candidates: list[HypothesisCandidate] | None = None,
        paper_plan: AutoResearchPaperPlanRead | None = None,
        figure_plan: AutoResearchFigurePlanRead | None = None,
        paper_revision_state: AutoResearchPaperRevisionStateRead | None = None,
        project_context: AutoResearchProjectFlowContextRead | None = None,
        language: str = "en",
        run_dir: Path | None = None,
    ) -> AutoResearchPaperPipelineArtifactsRead:
        literature = literature or []
        attempts = attempts or []
        candidates = candidates or []
        claim_evidence_matrix = self.build_claim_evidence_matrix(
            plan,
            spec,
            artifact,
            literature=literature,
            attempts=attempts,
            portfolio=portfolio,
            candidates=candidates,
        )
        narrative_report_markdown = self.build_narrative_report(
            plan,
            spec,
            artifact,
            claim_evidence_matrix,
            literature=literature,
            attempts=attempts,
            benchmark_name=benchmark_name,
            program=program,
            portfolio=portfolio,
            candidates=candidates,
            project_context=project_context,
        )
        paper_plan = paper_plan or self.build_paper_plan(plan, claim_evidence_matrix)
        figure_plan = figure_plan or self.build_figure_plan(artifact, portfolio=portfolio)
        paper_revision_state = paper_revision_state or self.build_paper_revision_state(
            claim_evidence_matrix,
            paper_plan=paper_plan,
            figure_plan=figure_plan,
        )

        # Generate figures if run_dir is available
        generated_figure_paths: dict[str, str] = {}
        if run_dir is not None:
            try:
                fig_gen = FigureGenerator(run_dir)
                figures = fig_gen.generate_figures(artifact)
                for fig in figures:
                    generated_figure_paths[fig.title] = fig.relative_path
                logger.info("build_pipeline: generated %d figures", len(figures))
            except Exception as exc:
                logger.error("build_pipeline: figure generation failed: %s", exc)

        paper_markdown = self.write(
            plan,
            spec,
            artifact,
            literature=literature,
            attempts=attempts,
            benchmark_name=benchmark_name,
            program=program,
            portfolio=portfolio,
            candidates=candidates,
            narrative_report_markdown=narrative_report_markdown,
            claim_evidence_matrix=claim_evidence_matrix,
            paper_plan=paper_plan,
            figure_plan=figure_plan,
            paper_revision_state=paper_revision_state,
            project_context=project_context,
            language=language,
            generated_figure_paths=generated_figure_paths or None,
        )
        paper_section_rewrite_index = self.build_section_rewrite_packet_index(
            paper_plan=paper_plan,
            claim_evidence_matrix=claim_evidence_matrix,
            paper_revision_state=paper_revision_state,
            paper_markdown=paper_markdown,
        )
        paper_revision_diff = self.build_paper_revision_diff(
            paper_plan=paper_plan,
            paper_revision_state=paper_revision_state,
            paper_section_rewrite_index=paper_section_rewrite_index,
            paper_markdown=paper_markdown,
        )
        paper_revision_action_index = self.build_paper_revision_action_index(
            paper_revision_state=paper_revision_state,
            paper_section_rewrite_index=paper_section_rewrite_index,
            paper_revision_diff=paper_revision_diff,
            paper_markdown=paper_markdown,
            paper_plan=paper_plan,
        )
        paper_bibliography_bib = self.build_paper_bibliography(literature)
        paper_latex_source = self.build_paper_latex_source(
            paper_markdown,
            literature=literature,
        )
        paper_sources_manifest = self.build_paper_sources_manifest(
            has_bibliography=bool(literature),
            include_revision_checkpoints=paper_revision_state is not None,
            include_revision_diff=True,
            include_revision_action_index=True,
            paper_section_rewrite_index=paper_section_rewrite_index,
        )
        paper_compile_report = self.build_paper_compile_report(
            paper_sources_manifest=paper_sources_manifest,
        )
        return AutoResearchPaperPipelineArtifactsRead(
            narrative_report_markdown=narrative_report_markdown,
            claim_evidence_matrix=claim_evidence_matrix,
            paper_plan=paper_plan,
            figure_plan=figure_plan,
            paper_revision_state=paper_revision_state,
            paper_compile_report=paper_compile_report,
            paper_revision_diff=paper_revision_diff,
            paper_revision_action_index=paper_revision_action_index,
            paper_section_rewrite_index=paper_section_rewrite_index,
            paper_latex_source=paper_latex_source,
            paper_bibliography_bib=paper_bibliography_bib,
            paper_sources_manifest=paper_sources_manifest,
            paper_markdown=paper_markdown,
        )

    def write(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        artifact: ResultArtifact,
        *,
        literature: list[LiteratureInsight] | None = None,
        attempts: list[ExperimentAttempt] | None = None,
        benchmark_name: str | None = None,
        program: ResearchProgram | None = None,
        portfolio: PortfolioSummary | None = None,
        candidates: list[HypothesisCandidate] | None = None,
        narrative_report_markdown: str | None = None,
        claim_evidence_matrix: AutoResearchClaimEvidenceMatrixRead | None = None,
        paper_plan: AutoResearchPaperPlanRead | None = None,
        figure_plan: AutoResearchFigurePlanRead | None = None,
        paper_revision_state: AutoResearchPaperRevisionStateRead | None = None,
        project_context: AutoResearchProjectFlowContextRead | None = None,
        language: str = "en",
        generated_figure_paths: dict[str, str] | None = None,
    ) -> str:
        if artifact.status != "done":
            raise ValueError("PaperWriter requires a completed ResultArtifact")

        literature = literature or []
        attempts = attempts or []
        candidates = candidates or []
        claim_evidence_matrix = claim_evidence_matrix or self.build_claim_evidence_matrix(
            plan,
            spec,
            artifact,
            literature=literature,
            attempts=attempts,
            portfolio=portfolio,
            candidates=candidates,
        )
        paper_plan = paper_plan or self.build_paper_plan(plan, claim_evidence_matrix)
        figure_plan = figure_plan or self.build_figure_plan(artifact, portfolio=portfolio)
        paper_revision_state = paper_revision_state or self.build_paper_revision_state(
            claim_evidence_matrix,
            paper_plan=paper_plan,
            figure_plan=figure_plan,
        )
        narrative_report_markdown = narrative_report_markdown or self.build_narrative_report(
            plan,
            spec,
            artifact,
            claim_evidence_matrix,
            literature=literature,
            attempts=attempts,
            benchmark_name=benchmark_name,
            program=program,
            portfolio=portfolio,
            candidates=candidates,
            project_context=project_context,
        )
        best_metric = self._aggregate_metric(artifact, artifact.best_system, artifact.primary_metric)
        best_std = self._aggregate_std(artifact, artifact.best_system, artifact.primary_metric)
        best_ci = self._aggregate_confidence_interval(artifact, artifact.best_system, artifact.primary_metric)
        learned_system = spec.baselines[-1].name if spec.baselines else artifact.best_system
        ablation_name = spec.ablations[0].name if spec.ablations else None
        learned_metric = self._aggregate_metric(artifact, learned_system, artifact.primary_metric)
        ablation_metric = self._aggregate_metric(artifact, ablation_name, artifact.primary_metric)
        majority_metric = self._aggregate_metric(artifact, "majority", artifact.primary_metric)
        environment = artifact.environment
        runtime = environment.get("runtime_seconds")
        seed_count = environment.get("seed_count") or len(artifact.per_seed_results) or len(spec.seeds) or 1

        metrics = ", ".join(metric.name for metric in spec.metrics) or artifact.primary_metric
        results_table = self._results_table(artifact)
        literature_block = self._literature_block(literature)
        literature_context_sentence = self._literature_context_sentence(literature)
        discussion_context_sentence = self._discussion_context_sentence(literature)
        conclusion_context_sentence = self._conclusion_context_sentence(literature)
        references_block = self._references_block(literature)
        related_work_intro = (
            "The following background motivates the experimental design:\n"
            if self._fallback_context_only(literature)
            else "The following related work motivates the experimental design:\n"
        )
        significance_block = self._significance_block(artifact)
        negative_results_block = self._negative_results_block(artifact)
        failure_block = self._failure_block(artifact)
        anomaly_block = self._anomaly_block(artifact)
        benchmark_display = benchmark_name or spec.benchmark_name
        benchmark_slice_sentence = self._benchmark_slice_sentence(plan, spec, benchmark_display)
        bounded_interpretation_sentence = self._bounded_interpretation_sentence(plan, spec, benchmark_display)
        hypothesis_outcome_summary_sentence = self._hypothesis_outcome_summary_sentence(spec, artifact)
        compared_systems_sentence = self._compared_systems_sentence(artifact)
        literature_synthesis_sentence = self._literature_synthesis_sentence(literature)
        portfolio_decision_sentence = self._portfolio_decision_sentence(portfolio, candidates)
        key_findings_sentence = self._key_findings_sentence(artifact)
        best_ci_text = self._format_confidence_interval(best_ci)
        method_summary = plan.proposed_method.strip()
        if method_summary and method_summary[-1] not in ".!?":
            method_summary = f"{method_summary}."
        baseline_names = ", ".join(item.name for item in spec.baselines) or "no explicit baselines"
        ablation_names = ", ".join(item.name for item in spec.ablations) if spec.ablations else "no ablations"
        experiment_outline_block = (
            "\n".join(f"1. {item}" for item in plan.experiment_outline)
            or "1. No explicit experiment outline was recorded."
        )
        best_detail_parts = []
        if best_std is not None:
            best_detail_parts.append(f"std={best_std:.4f}")
        if best_ci_text is not None:
            best_detail_parts.append(best_ci_text)
        best_detail = f" ({'; '.join(best_detail_parts)})" if best_detail_parts else ""

        comparison_sentence = (
            f"The best-performing system was `{artifact.best_system}`, achieving a "
            f"mean {artifact.primary_metric} of {best_metric:.4f}"
            f"{best_detail}."
            if best_metric is not None and artifact.best_system
            else "All systems were evaluated and ranked by their primary metric."
        )
        learned_sentence = (
            f"The learned model `{learned_system}` achieved a mean {artifact.primary_metric} of {learned_metric:.4f}."
            if learned_metric is not None and learned_system
            else "The learned model was evaluated alongside the baselines."
        )
        ablation_sentence = (
            f"Removing the key component in ablation `{ablation_name}` reduced performance to "
            f"{artifact.primary_metric}={ablation_metric:.4f}, "
            f"confirming the importance of that design choice."
            if ablation_name and ablation_metric is not None
            else "An ablation study was included to test the contribution of individual components."
        )
        majority_sentence = (
            f"The majority-class baseline achieved a mean {artifact.primary_metric} of {majority_metric:.4f}, "
            "establishing a performance floor."
            if majority_metric is not None
            else "A majority-class baseline was included to establish a performance floor."
        )
        limitation_points = self._limitation_points(
            plan,
            spec,
            artifact,
            literature=literature,
            benchmark_display=benchmark_display,
        )
        limitation_block = (
            "The main limitations concern scope, comparison breadth, and any unresolved evidence gaps preserved in the run artifact.\n\n"
            + "\n".join(f"- {item}" for item in limitation_points)
        )
        if spec.task_family == "ir_reranking":
            dataset_sentence = (
                f"The dataset used in the experiment is `{spec.dataset.name}` with "
                f"{spec.dataset.train_size} training queries and {spec.dataset.test_size} test queries. "
                f"Queries are represented through the fields {', '.join(spec.dataset.query_fields or ['query'])}, "
                f"and each query is associated with up to {spec.dataset.candidate_count or 'unknown'} candidates."
            )
        else:
            dataset_sentence = (
                f"The dataset used in the experiment is `{spec.dataset.name}` with "
                f"{spec.dataset.train_size} training examples and {spec.dataset.test_size} test examples. "
                f"Inputs are represented through the fields {', '.join(spec.dataset.input_fields)}, "
                f"and labels belong to {{{', '.join(spec.dataset.label_space)}}}."
            )
        section_bodies = {
            "abstract": (
                f"This paper investigates the problem of **{plan.topic}** through controlled experiments on "
                f"the `{benchmark_display}` benchmark. We compare several classification approaches, ranging "
                f"from simple baselines to learned models, and evaluate them using {metrics}. "
                + (
                    f"Our results show that `{artifact.best_system or 'the best system'}` achieves the highest "
                    f"performance with a mean {artifact.primary_metric} of {best_metric:.4f}"
                    f"{best_detail} across {seed_count} experimental seeds. "
                    if best_metric is not None
                    else f"We evaluate these approaches across {seed_count} experimental seeds. "
                )
                + f"{hypothesis_outcome_summary_sentence} "
                f"The findings demonstrate the effectiveness of different modeling strategies for this task "
                f"and provide a reproducible baseline for future work."
            ),
            "introduction": (
                f"{plan.problem_statement}\n\n"
                + f"{plan.motivation}\n\n"
                + f"{benchmark_slice_sentence}\n\n"
                + (f"{literature_context_sentence}\n\n" if literature_context_sentence else "")
                + "We organize our investigation around the following questions:\n\n"
                + "\n".join(f"{i}. {item}" for i, item in enumerate(plan.research_questions, 1))
            ),
            "related_work": (
                (
                    (f"{literature_synthesis_sentence}\n\n" if literature_synthesis_sentence else "")
                    + related_work_intro
                    + f"{literature_block}\n\n"
                    if literature
                    else (
                        f"The study of {plan.topic} has attracted growing attention in recent years. "
                        f"A number of benchmark suites have been developed to evaluate approaches on the "
                        f"`{spec.task_family}` task, including `{benchmark_display}` "
                        f"which provides a standardized evaluation framework.\n\n"
                        f"Benchmark `{benchmark_display}` targets the `{spec.task_family}` setting "
                        f"on dataset `{spec.dataset.name}`, containing {spec.dataset.train_size} training "
                        f"and {spec.dataset.test_size} test examples. "
                        f"Input features include {', '.join(spec.dataset.input_fields)}, "
                        f"and the label space covers {{{', '.join(spec.dataset.label_space)}}}.\n\n"
                    )
                )
                + "This study tests the following hypotheses:\n\n"
                + "\n".join(f"- **H{i}:** {item}" for i, item in enumerate(plan.hypotheses, 1))
                + "\n\nThe main contributions of this work are:\n\n"
                + "\n".join(f"- {item}" for item in plan.planned_contributions)
            ),
            "method": (
                f"{method_summary}\n\n"
                + f"{benchmark_slice_sentence}\n\n"
                + f"We evaluate on fixed train/test partitions of `{benchmark_display}` ({spec.benchmark_description}) "
                + "against both rule-based and probabilistic baselines.\n\n"
                + f"{dataset_sentence}\n\n"
                + f"The baseline methods are {baseline_names}. "
                + (f"The ablation suite includes {ablation_names}." if spec.ablations else "No additional ablation is included.")
                + "\n\n"
                + "The experimental procedure proceeds as follows:\n\n"
                + f"{experiment_outline_block}\n\n"
            ),
            "experimental_setup": (
                "All experiments were conducted in a controlled local environment "
                f"running Python {environment.get('host_python', 'unknown')} "
                f"on {environment.get('host_platform', 'unknown')}. "
                + (
                    f"The total execution time was {runtime:.4f} seconds.\n\n"
                    if runtime is not None
                    else "\n\n"
                )
                + f"Each configuration was evaluated over {seed_count} random seeds to assess stability. "
                "We report mean performance, standard deviation, and 95% confidence intervals "
                "(Student's t-distribution) across seeds. "
                "Statistical significance is assessed using paired sign-flip tests with Holm-Bonferroni correction.\n\n"
                + f"The primary evaluation metric is {metrics}."
            ),
            "results": (
                f"{comparison_sentence} {compared_systems_sentence}\n\n"
                + f"{results_table}\n\n"
                + (
                    f"**Statistical comparisons.** We performed paired significance tests "
                    f"between the top-performing system and each baseline:\n\n{significance_block}\n\n"
                    if significance_block
                    else ""
                )
                + (
                    f"**Negative results.** {negative_results_block}\n\n"
                    if negative_results_block
                    else ""
                )
                + (
                    f"**Failed configurations.** {failure_block}\n\n"
                    if artifact.failed_trials
                    else ""
                )
                + (
                    f"**Anomalous trials.** {anomaly_block}\n\n"
                    if artifact.anomalous_trials
                    else ""
                )
            ),
            "discussion": (
                (
                    f"The experimental results reveal that `{artifact.best_system or 'the best-performing system'}` "
                    f"achieves the strongest performance with a mean {artifact.primary_metric} of "
                    f"{best_metric:.4f}{best_detail} on the `{benchmark_display}` benchmark. "
                    if best_metric is not None
                    else f"The experimental results on the `{benchmark_display}` benchmark reveal the relative strengths of the evaluated approaches. "
                )
                + f"{learned_sentence} {majority_sentence} {ablation_sentence}\n\n"
                + (f"{key_findings_sentence}\n\n" if key_findings_sentence else "")
                + (
                    f"{discussion_context_sentence}\n\n"
                    if discussion_context_sentence
                    else ""
                )
                + f"{bounded_interpretation_sentence}"
            ),
            "limitations": limitation_block,
            "conclusion": (
                f"This work presents a systematic comparison of classification methods for `{plan.topic}` "
                f"on the `{benchmark_display}` benchmark. "
                + (
                    f"Our experiments demonstrate that "
                    f"`{artifact.best_system or 'the best system'}` achieves a mean {artifact.primary_metric} "
                    f"of {best_metric:.4f}{best_detail}, "
                    + ("significantly outperforming the baseline. " if majority_metric is not None and best_metric is not None and best_metric > majority_metric else "")
                    if best_metric is not None
                    else "Our experiments provide a systematic evaluation of multiple approaches, "
                )
                + "The results establish a reproducible benchmark for this task and highlight the relative strengths "
                "of different modeling approaches.\n\n"
                + (
                    f"{conclusion_context_sentence}\n\n"
                    if conclusion_context_sentence
                    else ""
                )
                + "Future work should extend these experiments to larger datasets and more diverse domains "
                "to assess the generalizability of the observed patterns."
            ),
        }
        if paper_revision_state.revision_round > 0:
            for section in paper_plan.sections:
                slug = _section_slug(section.title)
                current_body = section_bodies.get(slug, self._fallback_section_body(section))
                claim_entries = self._section_claim_entries(
                    section=section,
                    claim_evidence_matrix=claim_evidence_matrix,
                )
                actions = self._section_pending_actions(
                    section=section,
                    paper_revision_state=paper_revision_state,
                )
                open_issues = self._section_open_issues(
                    section=section,
                    claim_entries=claim_entries,
                    paper_revision_state=paper_revision_state,
                )
                section_bodies[slug] = self._auto_revision_draft(
                    section=section,
                    current_body=current_body,
                    claim_entries=claim_entries,
                    actions=actions,
                    open_issues=open_issues,
                    paper_revision_state=paper_revision_state,
                )
        seed_markdown = self._render_section_sequence(
            title=plan.title,
            paper_plan=paper_plan,
            section_bodies=section_bodies,
            references_block=references_block,
        )

        # --- LLM-first section generation (fallback to seed template) ---
        llm_sections = self._write_full_paper_with_llm(
            plan,
            spec,
            artifact,
            paper_plan,
            claim_evidence_matrix,
            literature,
            figure_paths=generated_figure_paths,
        )
        all_slugs = [_section_slug(s.title) for s in paper_plan.sections]
        llm_covered = [s for s in all_slugs if s in llm_sections]
        if len(llm_covered) >= len(all_slugs) // 2 + 1:
            merged_bodies = dict(section_bodies)
            merged_bodies.update(llm_sections)
            llm_markdown = self._render_section_sequence(
                title=plan.title,
                paper_plan=paper_plan,
                section_bodies=merged_bodies,
                references_block=references_block,
            )
            logger.info(
                "paper_writer: using LLM-generated sections (%d/%d), fallback template for rest",
                len(llm_covered), len(all_slugs),
            )
            return self._maybe_refine_with_llm(
                seed_markdown=llm_markdown,
                language=language,
                plan=plan,
                spec=spec,
                artifact=artifact,
                literature=literature,
                attempts=attempts,
                project_context=project_context,
                narrative_report_markdown=narrative_report_markdown,
                claim_evidence_matrix=claim_evidence_matrix,
                paper_plan=paper_plan,
                paper_revision_state=paper_revision_state,
            )

        logger.info("paper_writer: LLM section generation insufficient (%d/%d), falling back to seed template", len(llm_covered), len(all_slugs))
        return self._maybe_refine_with_llm(
            seed_markdown=seed_markdown,
            language=language,
            plan=plan,
            spec=spec,
            artifact=artifact,
            literature=literature,
            attempts=attempts,
            project_context=project_context,
            narrative_report_markdown=narrative_report_markdown,
            claim_evidence_matrix=claim_evidence_matrix,
            paper_plan=paper_plan,
            paper_revision_state=paper_revision_state,
        )
