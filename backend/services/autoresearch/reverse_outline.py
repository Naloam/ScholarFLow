"""Reverse Outline Test — ARIS pattern.

Extract the first sentence of every paragraph from the paper,
then check whether those sentences form a coherent narrative when read in sequence.
This catches structural incoherence that section-level review misses.
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


def extract_topic_sentences(markdown: str) -> list[dict]:
    """Extract the first sentence of every paragraph.

    Returns list of {section, paragraph_index, topic_sentence, word_count}.
    """
    results = []
    current_section = "Title"

    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            current_section = stripped[3:].strip()
            continue

        # Skip empty lines, headings, list items, tables
        if not stripped or stripped.startswith("#") or stripped.startswith("|") or stripped.startswith("-"):
            continue
        # Skip very short lines (likely headings or labels)
        if len(stripped) < 30:
            continue

        # Extract first sentence
        sentence_end = _find_first_sentence_end(stripped)
        if sentence_end:
            topic = stripped[:sentence_end + 1].strip()
        else:
            topic = stripped.split(".")[0].strip() + "."
            if len(topic) < 20:
                topic = stripped[:80].strip()

        word_count = len(topic.split())
        results.append({
            "section": current_section,
            "topic_sentence": topic,
            "word_count": word_count,
        })

    return results


def _find_first_sentence_end(text: str) -> int | None:
    """Find the end of the first sentence (period, question mark, exclamation)."""
    # Skip abbreviations like "e.g.", "i.e.", "al.", "Fig."
    skip_patterns = {"e.g", "i.e", "al", "Fig", "Eq", "Tab", "Sec", "cf", "vs", "et al"}
    i = 0
    while i < len(text):
        if text[i] in ".!?":
            # Check if it's an abbreviation
            prefix = text[max(0, i-3):i].strip()
            if any(prefix.endswith(s) for s in skip_patterns):
                i += 1
                continue
            # Check if next char is uppercase (sentence boundary)
            if i + 1 < len(text) and text[i + 1].isupper():
                return i
            if i + 1 >= len(text) or text[i + 1] == " ":
                return i
        i += 1
    return None


def check_narrative_coherence(topic_sentences: list[dict]) -> list[str]:
    """Check for common coherence problems in the topic sentence sequence.

    Returns list of issues found.
    """
    issues = []
    if len(topic_sentences) < 3:
        return issues

    sentences = [s["topic_sentence"] for s in topic_sentences]
    sections = [s["section"] for s in topic_sentences]

    # Check 1: Repeated or near-identical topic sentences
    for i in range(len(sentences)):
        for j in range(i + 1, len(sentences)):
            if _sentence_similarity(sentences[i], sentences[j]) > 0.8:
                issues.append(
                    f"Paragraphs {i+1} and {j+1} (in '{sections[i]}' and '{sections[j]}') "
                    f"start with nearly identical sentences."
                )

    # Check 2: Missing transition between sections
    prev_section = None
    section_start_idx = 0
    for idx, (sent, section) in enumerate(zip(sentences, sections)):
        if section != prev_section and prev_section is not None:
            # Check if the last paragraph of previous section connects
            # to the first paragraph of this section
            if idx >= 2:
                prev_sent = sentences[idx - 1].lower()
                curr_sent = sent.lower()
                # Look for transition words
                transition_words = {
                    "however", "furthermore", "additionally", "in contrast",
                    "building on", "based on", "to evaluate", "to test",
                    "next", "then", "following", "we now", "we then",
                }
                has_transition = any(tw in curr_sent for tw in transition_words)
                # Check topic overlap between sections
                overlap = _keyword_overlap(prev_sent, curr_sent)
                if not has_transition and overlap < 0.15:
                    issues.append(
                        f"Section transition '{prev_section}' -> '{section}' "
                        f"lacks narrative connection (paragraph {idx} to {idx+1})."
                    )
        if section != prev_section:
            section_start_idx = idx
            prev_section = section

    # Check 3: Orphan paragraphs (no topic overlap with neighbors)
    for i in range(1, len(sentences) - 1):
        prev_overlap = _keyword_overlap(sentences[i-1], sentences[i])
        next_overlap = _keyword_overlap(sentences[i], sentences[i+1])
        if prev_overlap < 0.05 and next_overlap < 0.05:
            issues.append(
                f"Paragraph {i+1} in '{sections[i]}' appears disconnected "
                f"from its neighbors (topic overlap < 5%)."
            )

    # Check 4: Section-level narrative arc
    section_first_sentences = {}
    for sent_dict in topic_sentences:
        sec = sent_dict["section"]
        if sec not in section_first_sentences:
            section_first_sentences[sec] = sent_dict["topic_sentence"]

    if len(section_first_sentences) >= 4:
        section_order = list(section_first_sentences.keys())
        # Check if abstract/intro promises are delivered in results
        if "Abstract" in section_order and "Results" in section_order:
            abstract_sent = section_first_sentences.get("Abstract", "").lower()
            results_sent = section_first_sentences.get("Results", "").lower()
            if abstract_sent and results_sent:
                overlap = _keyword_overlap(abstract_sent, results_sent)
                if overlap < 0.1:
                    issues.append(
                        "Abstract and Results sections have very different topics. "
                        "The results section may not address what the abstract promises."
                    )

    return issues


def generate_reverse_outline(markdown: str) -> dict:
    """Run the full reverse outline test.

    Returns {
        topic_sentences: list,
        issues: list,
        outline_text: str (the extracted outline for review),
        coherence_score: float 0-1,
    }
    """
    topic_sentences = extract_topic_sentences(markdown)
    issues = check_narrative_coherence(topic_sentences)

    # Build outline text
    outline_lines = ["# Reverse Outline", ""]
    prev_section = None
    for i, s in enumerate(topic_sentences):
        if s["section"] != prev_section:
            outline_lines.append(f"## {s['section']}")
            prev_section = s["section"]
        outline_lines.append(f"{i+1}. {s['topic_sentence']}")

    # Compute coherence score
    total_checks = max(len(topic_sentences) * 2, 1)
    coherence = max(0.0, 1.0 - len(issues) / total_checks)

    return {
        "topic_sentences": topic_sentences,
        "issues": issues,
        "outline_text": "\n".join(outline_lines),
        "coherence_score": coherence,
        "total_paragraphs": len(topic_sentences),
        "total_issues": len(issues),
    }


def _sentence_similarity(a: str, b: str) -> float:
    """Simple word overlap similarity between two sentences."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / min(len(words_a), len(words_b))


def _keyword_overlap(a: str, b: str) -> float:
    """Compute keyword overlap ratio between two texts."""
    stop = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "of",
            "to", "for", "with", "we", "our", "this", "that", "and", "or"}
    words_a = {w for w in a.lower().split() if len(w) > 3 and w not in stop}
    words_b = {w for w in b.lower().split() if len(w) > 3 and w not in stop}
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / min(len(words_a), len(words_b))
