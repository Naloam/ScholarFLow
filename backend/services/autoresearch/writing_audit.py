"""5-Pass Writing Quality Audit — ARIS pattern.

Systematic sentence-level review of paper prose:
  Pass 1: Clutter Extraction (verbose -> concise)
  Pass 2: Active Voice (smothered verbs, passive -> active)
  Pass 3: Sentence Architecture (split >40 word sentences)
  Pass 4: Keyword Consistency ("Banana Rule" — same term everywhere)
  Pass 5: Numerical Integrity (cross-check numbers across sections)
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


# --- Pass 1: Clutter Extraction ---

_CLUTTER_REPLACEMENTS: list[tuple[str, str]] = [
    ("due to the fact that", "because"),
    ("in order to", "to"),
    ("a large number of", "many"),
    ("a number of", "several"),
    ("in the event that", "if"),
    ("prior to", "before"),
    ("subsequent to", "after"),
    ("at the present time", "now"),
    ("at this point in time", "now"),
    ("for the purpose of", "to"),
    ("in spite of the fact that", "although"),
    ("on the basis of", "based on"),
    ("with regard to", "regarding"),
    ("with respect to", "for"),
    ("it is important to note that", ""),
    ("it should be noted that", ""),
    ("it is worth noting that", ""),
    ("it is worth mentioning that", ""),
    ("we would like to point out that", ""),
    ("it is clear that", "clearly"),
    ("it is evident that", "evidently"),
    ("in the context of", "in"),
    ("in terms of", "for"),
    ("as a matter of fact", ""),
    ("as a result of", "because of"),
    ("by means of", "by"),
    ("for the reason that", "because"),
    ("in a manner of speaking", ""),
    ("in light of the fact that", "because"),
    ("on account of", "because"),
    ("the vast majority of", "most"),
    ("a considerable amount of", "much"),
    ("an appreciable number of", "many"),
    ("in the vicinity of", "near"),
    ("utilize", "use"),
    ("facilitate", "enable"),
    ("demonstrates", "shows"),
    ("necessitates", "requires"),
    ("endeavor", "try"),
    ("commence", "start"),
    ("terminate", "end"),
    ("ascertain", "determine"),
    ("subsequently", "then"),
    ("additionally", "also"),
    ("fundamentally", ""),
    ("essentially", ""),
    ("basically", ""),
    ("actually", ""),
    ("various", ""),
    ("certain", ""),
]


def pass1_clutter_extraction(text: str) -> tuple[str, list[str]]:
    """Remove verbose phrases. Returns (cleaned_text, changes_made)."""
    changes = []
    result = text
    for old, new in _CLUTTER_REPLACEMENTS:
        pattern = re.compile(re.escape(old), re.IGNORECASE)
        matches = pattern.findall(result)
        if matches:
            result = pattern.sub(new, result)
            changes.append(f"'{old}' -> '{new}'" if new else f"removed '{old}'")
    # Clean up double spaces left by removals
    result = re.sub(r"  +", " ", result)
    return result, changes


# --- Pass 2: Active Voice ---

_SMOTHERED_VERB_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bmake\s+a\s+comparison\b", re.I), "compare"),
    (re.compile(r"\bmake\s+an\s+evaluation\b", re.I), "evaluate"),
    (re.compile(r"\bmake\s+an\s+assessment\b", re.I), "assess"),
    (re.compile(r"\bmake\s+an\s+analysis\b", re.I), "analyze"),
    (re.compile(r"\bmake\s+a\s+decision\b", re.I), "decide"),
    (re.compile(r"\bgive\s+an\s+explanation\b", re.I), "explain"),
    (re.compile(r"\bgive\s+a\s+description\b", re.I), "describe"),
    (re.compile(r"\bprovide\s+an\s+explanation\b", re.I), "explain"),
    (re.compile(r"\bprovide\s+a\s+description\b", re.I), "describe"),
    (re.compile(r"\bcarry\s+out\s+an\s+investigation\b", re.I), "investigate"),
    (re.compile(r"\bcarry\s+out\s+experiments\b", re.I), "experiment"),
    (re.compile(r"\bperform\s+an\s+analysis\b", re.I), "analyze"),
    (re.compile(r"\bconduct\s+an\s+investigation\b", re.I), "investigate"),
    (re.compile(r"\btake\s+into\s+consideration\b", re.I), "consider"),
]


def pass2_active_voice(text: str) -> tuple[str, list[str]]:
    """Unsmother verbs and flag passive constructions."""
    changes = []
    result = text

    for pattern, replacement in _SMOTHERED_VERB_PATTERNS:
        matches = pattern.findall(result)
        if matches:
            result = pattern.sub(replacement, result)
            changes.append(f"unsmothered verb -> '{replacement}'")

    # Flag passive voice for LLM to fix (don't auto-fix, too context-dependent)
    passive_matches = re.findall(
        r"\b(is|are|was|were|be|been|being)\s+(\w+ed|\w+en)\b",
        result,
    )
    for aux, verb in passive_matches[:10]:
        changes.append(f"passive voice detected: '{aux} {verb}'")

    return result, changes


# --- Pass 3: Sentence Architecture ---

def pass3_sentence_architecture(text: str) -> tuple[str, list[str]]:
    """Flag sentences over 40 words for splitting."""
    changes = []
    sentences = re.split(r'(?<=[.!?])\s+', text)

    for sentence in sentences:
        word_count = len(sentence.split())
        if word_count > 40:
            changes.append(
                f"Long sentence ({word_count} words): '{sentence[:80]}...'"
            )

    return text, changes


# --- Pass 4: Keyword Consistency (Banana Rule) ---

def pass4_keyword_consistency(text: str) -> list[str]:
    """Check that key terms are used consistently throughout the paper.

    The 'Banana Rule': if you call it a 'banana' in section 1,
    call it a 'banana' everywhere, not 'fruit', 'yellow fruit', 'cavendish', etc.
    """
    issues = []

    # Extract technical terms that appear in the text
    # Look for quoted terms, bold terms, and capitalized multi-word terms
    terms: dict[str, set[str]] = {}

    # Method name patterns
    method_names = re.findall(r'\b([A-Z][a-z]+(?:[-\s][A-Z][a-z]+)+)\b', text)
    for name in method_names:
        key = name.lower().replace("-", " ").replace("  ", " ").strip()
        terms.setdefault(key, set()).add(name)

    # Abbreviated terms and their expansions
    abbrevs = re.findall(r'\b([A-Z]{2,})\b', text)
    abbrev_contexts: dict[str, list[str]] = {}
    for abbrev in abbrevs:
        if len(abbrev) <= 2:
            continue
        # Find expansions
        expansion = re.findall(
            rf'\b(\w+(?:\s+\w+){{0,3}})\s*\({abbrev}\)',
            text,
        )
        if expansion:
            abbrev_contexts[abbrev] = expansion

    # Check for same concept with multiple names
    for key, variants in terms.items():
        if len(variants) > 1:
            issues.append(
                f"Banana Rule violation: '{key}' appears as {variants}. "
                "Pick one name and use it consistently."
            )

    # Check abbreviations with multiple expansions
    for abbrev, expansions in abbrev_contexts.items():
        unique = set(e.lower() for e in expansions)
        if len(unique) > 1:
            issues.append(
                f"Abbreviation '{abbrev}' has multiple expansions: {expansions}. "
                "Use one expansion consistently."
            )

    # Check common synonym pairs
    synonym_groups = [
        ("model", "system", "method", "approach", "architecture"),
        ("dataset", "benchmark", "corpus", "data", "evaluation set"),
        ("performance", "accuracy", "score", "result", "metric"),
        ("experiment", "evaluation", "trial", "run"),
    ]
    text_lower = text.lower()
    for group in synonym_groups:
        # Count usage of each synonym in different sections
        section_texts = re.split(r'##\s+', text)
        if len(section_texts) < 2:
            continue
        for synonym in group:
            count = text_lower.count(synonym)
            if count < 2:
                continue
            # Check if the same concept is referred to differently in different sections
            for other in group:
                if other == synonym:
                    continue
                other_count = text_lower.count(other)
                if other_count >= 2 and synonym != other:
                    # Both terms used frequently — potential inconsistency
                    pass  # Too noisy to flag without context

    return issues


# --- Pass 5: Numerical Integrity ---

def pass5_numerical_integrity(text: str) -> list[str]:
    """Cross-check that numbers are consistent across sections."""
    issues = []

    # Extract all (number, nearby_context) pairs
    number_contexts: dict[str, list[tuple[str, str]]] = {}
    for match in re.finditer(r'(\d+\.?\d*)\s*%?', text):
        number = match.group(1)
        context_start = max(0, match.start() - 40)
        context_end = min(len(text), match.end() + 40)
        context = text[context_start:context_end].replace("\n", " ").strip()
        number_contexts.setdefault(number, []).append((number, context))

    # Find same metric with different values
    metric_patterns = [
        (r'(accuracy|macro_f1|F1|precision|recall|MRR|NDCG)\s*[=:]\s*(\d+\.?\d*)', "metric"),
        (r'(Table\s+\d+)[^.]*?(\d+\.?\d*)', "table_value"),
    ]

    for pattern, kind in metric_patterns:
        matches = re.findall(pattern, text, re.I)
        metric_values: dict[str, set[str]] = {}
        for label, value in matches:
            metric_values.setdefault(label.lower(), set()).add(value)

        for metric, values in metric_values.items():
            if len(values) > 1:
                issues.append(
                    f"Numerical inconsistency: '{metric}' has values {values}. "
                    "Same metric should have consistent values across sections."
                )

    # Check for impossible values
    for match in re.finditer(r'(\d+\.?\d*)\s*%', text):
        try:
            value = float(match.group(1))
            if value > 100:
                issues.append(f"Percentage value {value}% exceeds 100%")
        except ValueError:
            pass

    return issues


# --- Full Audit ---

def run_writing_audit(markdown: str) -> dict:
    """Run all 5 passes on paper markdown. Returns audit report."""
    report = {
        "pass1_clutter": {"changes": [], "count": 0},
        "pass2_active_voice": {"changes": [], "count": 0},
        "pass3_sentences": {"issues": [], "count": 0},
        "pass4_keywords": {"issues": [], "count": 0},
        "pass5_numbers": {"issues": [], "count": 0},
        "total_issues": 0,
        "cleaned_markdown": markdown,
    }

    # Pass 1
    cleaned, clutter_changes = pass1_clutter_extraction(markdown)
    report["pass1_clutter"]["changes"] = clutter_changes
    report["pass1_clutter"]["count"] = len(clutter_changes)

    # Pass 2
    cleaned, voice_changes = pass2_active_voice(cleaned)
    report["pass2_active_voice"]["changes"] = voice_changes
    report["pass2_active_voice"]["count"] = len(voice_changes)

    # Pass 3
    cleaned, sentence_issues = pass3_sentence_architecture(cleaned)
    report["pass3_sentences"]["issues"] = sentence_issues
    report["pass3_sentences"]["count"] = len(sentence_issues)

    # Pass 4
    keyword_issues = pass4_keyword_consistency(cleaned)
    report["pass4_keywords"]["issues"] = keyword_issues
    report["pass4_keywords"]["count"] = len(keyword_issues)

    # Pass 5
    number_issues = pass5_numerical_integrity(cleaned)
    report["pass5_numbers"]["issues"] = number_issues
    report["pass5_numbers"]["count"] = len(number_issues)

    report["total_issues"] = (
        len(clutter_changes) + len(voice_changes) +
        len(sentence_issues) + len(keyword_issues) + len(number_issues)
    )
    report["cleaned_markdown"] = cleaned
    return report


def audit_report_to_markdown(report: dict) -> str:
    """Convert audit report to human-readable markdown."""
    lines = ["# Writing Quality Audit Report", ""]

    total = report["total_issues"]
    lines.append(f"**Total issues found: {total}**")
    lines.append("")

    p1 = report["pass1_clutter"]
    if p1["count"]:
        lines.append(f"## Pass 1: Clutter Extraction ({p1['count']} items)")
        for change in p1["changes"][:20]:
            lines.append(f"- {change}")
        lines.append("")

    p2 = report["pass2_active_voice"]
    if p2["count"]:
        lines.append(f"## Pass 2: Active Voice ({p2['count']} items)")
        for change in p2["changes"][:20]:
            lines.append(f"- {change}")
        lines.append("")

    p3 = report["pass3_sentences"]
    if p3["count"]:
        lines.append(f"## Pass 3: Sentence Architecture ({p3['count']} long sentences)")
        for issue in p3["issues"][:10]:
            lines.append(f"- {issue}")
        lines.append("")

    p4 = report["pass4_keywords"]
    if p4["count"]:
        lines.append(f"## Pass 4: Keyword Consistency ({p4['count']} violations)")
        for issue in p4["issues"][:10]:
            lines.append(f"- {issue}")
        lines.append("")

    p5 = report["pass5_numbers"]
    if p5["count"]:
        lines.append(f"## Pass 5: Numerical Integrity ({p5['count']} issues)")
        for issue in p5["issues"][:10]:
            lines.append(f"- {issue}")
        lines.append("")

    if total == 0:
        lines.append("*No issues found. Paper passes all 5 quality checks.*")

    return "\n".join(lines)
