"""Phase A2+A4 — paper engine v2: blueprint-driven per-section drafting with an
ARIS-style review-revision convergence loop.

Flow (replaces the June "3 calls + ≤1 lint patch" writer for new drafts):
1. ``build_blueprint`` (A1) — claims bound to evidence, tables/figures
   deterministic, references with real abstract digests.
2. Per-section drafting (related_work → methods → experiments → discussion →
   conclusion → introduction → abstract-last), each call carrying only that
   section's blueprint slice. Experiments section COPIES the deterministic
   table verbatim and emits audit-claim markers from the claim evidence.
3. Review loop: fresh-context rubric reviewer (novelty/soundness/clarity/
   significance/related-work depth, 1-10 + major/minor items). Converge when
   every dimension ≥ threshold AND no major items; at most ``max_rounds``
   revisions. Score trajectory persisted to ``paper/review_loop.json``.
4. Final passes: internal-jargon wash (A5), then the existing deterministic
   auditor gate still applies (unchanged — numbers stay anchored).

Language: ``lang="zh"`` emits the 中文核心期刊 structure; ``"en"`` the English
draft. Same blueprint, same loop.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from services.research_harness import evidence, paper_blueprint
from services.llm.client import chat
from services.llm.response_utils import get_message_content

logger = logging.getLogger(__name__)

# Section drafting order — abstract LAST (it summarizes the written paper).
SECTION_ORDER = ("related_work", "methods", "experiments", "discussion", "conclusion", "introduction", "abstract")

REVIEW_DIMENSIONS = ("novelty", "soundness", "clarity", "significance", "related_work_depth")
DEFAULT_SCORE_THRESHOLD = 6
DEFAULT_MAX_ROUNDS = 3

_ZH_SECTION_TITLES = {
    "abstract": "摘要", "introduction": "1 引言", "related_work": "2 相关研究",
    "methods": "3 方法", "experiments": "4 实验与结果", "discussion": "5 讨论",
    "conclusion": "6 结论",
}
_EN_SECTION_TITLES = {
    "abstract": "Abstract", "introduction": "1 Introduction", "related_work": "2 Related Work",
    "methods": "3 Methods", "experiments": "4 Experiments and Results", "discussion": "5 Discussion",
    "conclusion": "6 Conclusion",
}

# A5 — internal jargon that must never leak into a submitted manuscript.
JARGON_WASHES: tuple[tuple[str, str], ...] = (
    ("锚定结论", "预注册判定结论"),
    ("锚定主指标", "预注册主指标"),
    ("锚定判定", "预注册判定"),
    ("kill 准则", "预设终止准则"),
    ("kill准则", "预设终止准则"),
    ("beats_baseline 判定", "胜过基线的判定"),
    ("beats_baseline=False", "未胜过基线"),
    ("beats_baseline=True", "胜过基线"),
    ("证据包", "实验记录"),
    ("（设计层面）", ""),
)


# --------------------------------------------------------------------------- #
# Section prompts
# --------------------------------------------------------------------------- #


def _claim_markers(claims: list[dict[str, Any]]) -> str:
    """Ready-to-copy audit-claim markers from claim evidence (deterministic —
    the writer copies, never invents numbers)."""
    lines = []
    for c in claims:
        ev = c.get("evidence") or {}
        if "proposed" in ev and "baseline" in ev and ev.get("proposed") is not None:
            metric = "macro_f1"
            lines.append(
                f"- 论断 {c['id']}（{ev.get('dataset')}）后紧跟："
                f"`<!-- audit-claim metric={metric} proposed={ev['proposed']} baseline={ev['baseline']} -->`"
            )
    return "\n".join(lines) or "- （本节无标记论断）"


def _section_input(section: str, bp: dict[str, Any], lang: str) -> str:
    plan = (bp.get("plan") or {}).get("sections") or {}
    sec_plan = plan.get(section) or {}

    if section == "related_work":
        groupings = sec_plan.get("groupings") or []
        refs = bp["references"]
        default = [{"theme": "按主题分组", "markers": [r["marker"] for r in refs[:12]], "contrast": ""}]
        blocks = []
        for g in (groupings or default):
            entries = [r for r in refs if r["marker"] in set(g.get("markers") or [])]
            digest = "\n".join(
                f"{r['marker']} ({r['year']}) {r['title']}\n  摘要: {r['abstract_digest'][:300]}\n"
                f"  方法: {('; '.join(r['methods'])[:200]) or '（摘要未含）'}\n"
                f"  报告数字: {('; '.join(r['reported_results'])[:200]) or '（未报告）'}"
                for r in entries
            )
            blocks.append(f"### 主题：{g.get('theme','')}\n规划差异点：{g.get('contrast','')}\n{digest}")
        return "\n\n".join(blocks)

    if section == "methods":
        return json.dumps({
            "hypothesis": bp.get("hypothesis") or {},
            "must_explain": sec_plan.get("must_explain") or [],
            "数据集": [c["evidence"].get("dataset") for c in bp["claims"] if c["evidence"].get("dataset")],
        }, ensure_ascii=False, indent=2)[:4000]

    if section == "experiments":
        claims = [c for c in bp["claims"] if c.get("section") == "experiments"]
        return (
            f"锚定结论：{json.dumps(bp['verdict'], ensure_ascii=False)}\n\n"
            f"可用论断（数字逐字使用）：\n" + "\n".join(f"- {c['id']}: {c['text_hint']}" for c in claims)
            + "\n\n【必须逐字复制的表格】\n" + bp["tables"]["main"]
            + "\n\n【可引用的图】" + "、".join(bp["figures"])
            + "\n\n【论断标记（逐字复制到对应句子之后）】\n" + _claim_markers(claims)
        )

    if section == "discussion":
        return "锚定结论：" + json.dumps(bp["verdict"], ensure_ascii=False) + "\n规划讨论点：" + json.dumps(
            sec_plan.get("angles") or [], ensure_ascii=False)

    if section == "conclusion":
        return "锚定结论：" + json.dumps(bp["verdict"], ensure_ascii=False) + "\n表述边界：" + str(
            sec_plan.get("angle") or "限定于协议范围，不外推")

    if section == "introduction":
        claim_ids = sec_plan.get("claim_order") or [c["id"] for c in bp["claims"][:4]]
        claims = [c for c in bp["claims"] if c["id"] in claim_ids]
        refs = [r["marker"] for r in bp["references"]][:15]
        return ("研究问题：" + bp["idea"] + "\n关键论断：\n"
                + "\n".join(f"- {c['text_hint']}" for c in claims)
                + "\n可引用文献编号：" + ", ".join(refs))

    if section == "abstract":
        # summarize the already-written sections
        return "（摘要最后写：通读全文后总结目的/方法/结果/结论四要素，200-300字）"

    return ""


def _section_prompt(section: str, bp: dict[str, Any], lang: str, draft_so_far: str) -> str:
    titles = _ZH_SECTION_TITLES if lang == "zh" else _EN_SECTION_TITLES
    plan = (bp.get("plan") or {})
    title_hint = (plan.get("title_candidates") or ["（自拟准确标题）"])[0] if section == "abstract" else ""
    honesty = json.dumps(bp["verdict"], ensure_ascii=False)
    if lang == "zh":
        rules = f"""你正在为一篇中文核心期刊论文撰写「{titles[section]}」一节。全局锚定结论（不可违背）：{honesty}

硬性规则：
1. 数字只能来自下方输入中逐字给出的数值；禁止计算、外推、四舍五入到不同值。
2. 实验节必须逐字复制给定表格与论断标记（audit-claim 注释原样保留）；图以 "如图 X（文件名）所示" 方式引用。
3. 相关工作每个主题段必须实质性：提到具体方法名/机制/已发表数字，并说明与本文差异；禁止"[n]被用于[n]"式罗列。
4. 禁止内部术语（"锚定结论/kill 准则/beats_baseline/证据包"）；面向期刊读者写作。
5. 负结果按负结果写；不允许"competitive/promising/有前景"等粉饰词。
6. 只输出本节正文（可含小节标题 ###），不要输出解释或元话语。"""
    else:
        rules = f"""You are writing the "{titles[section]}" section of a journal paper. Anchored verdict (binding): {honesty}

Hard rules:
1. Numbers verbatim from the inputs only — no derivation, no rounding into different values.
2. The experiments section COPIES the given table and audit-claim markers verbatim; figures referenced as "Figure X (filename)".
3. Related work must be substantive per paragraph: specific method names / mechanisms / published numbers + contrast with this work.
4. No internal jargon; write for journal readers.
5. Negative result stays negative; no "competitive/promising" wording.
6. Output ONLY this section's prose (may include ### subheadings)."""
    prev = f"\n\n## 已写好的前文（保持术语与叙事一致，不要重复内容）\n{draft_so_far[-3000:]}" if draft_so_far else ""
    return f"{rules}\n\n## 本节输入\n{_section_input(section, bp, lang)}{prev}\n\n## 标题提示\n{title_hint}"


# --------------------------------------------------------------------------- #
# A4 — fresh-context rubric reviewer + convergence loop
# --------------------------------------------------------------------------- #


def review_paper(draft: str, metrics_bounded: dict[str, Any], idea: str) -> dict[str, Any]:
    """Fresh-context reviewer: rubric scores + actionable items. Returns
    ``{scores: {dim: 1-10}, majors: [..], minors: [..], passed: bool}``."""
    prompt = f"""你是严格的期刊审稿人（零上下文，独立评审）。对以下论文草稿按五个维度打 1-10 分并列出可执行修改项。
只输出一个 JSON 对象：{{"scores": {{"novelty": x, "soundness": x, "clarity": x, "significance": x, "related_work_depth": x}}, "majors": ["重大问题+具体位置+怎么改"], "minors": ["小问题"]}}

维度校准：6=达到中文核心可投底线；7-8=良好；9-10=领域标杆。soundness 含数字与结论一致性；
related_work_depth 要求每段有具体方法/数字对比（仅罗列标题=2分）。负结果论文的 novelty/significance 按
"问题价值+证据质量"评，不因负结果本身扣分。

研究问题：{idea}

实验记录摘要（审稿基准，论文数字须与此一致）：
{json.dumps(metrics_bounded, ensure_ascii=False)[:6000]}

论文草稿：
{draft}"""
    content = get_message_content(chat([{"role": "user", "content": prompt}]))
    m = re.search(r"\{[\s\S]*\}", content or "")
    if not m:
        return {"scores": {}, "majors": ["审稿解析失败"], "minors": [], "passed": False, "raw": content[:500]}
    try:
        out = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"scores": {}, "majors": ["审稿解析失败"], "minors": [], "passed": False, "raw": content[:500]}
    scores = {d: int(out.get("scores", {}).get(d, 0)) for d in REVIEW_DIMENSIONS}
    majors = [str(x) for x in out.get("majors") or []][:8]
    minors = [str(x) for x in out.get("minors") or []][:10]
    return {
        "scores": scores,
        "majors": majors,
        "minors": minors,
        "passed": all(v >= DEFAULT_SCORE_THRESHOLD for v in scores.values()) and not majors and bool(scores),
    }


def _revise(draft: str, review: dict[str, Any], bp: dict[str, Any]) -> str:
    prompt = f"""你是论文修订作者。根据审稿意见修订全文。约束：
- 所有数字、表格、<!-- audit-claim ... --> 标记保持逐字不变（它们锚定实验记录）；
- 只改进论证、结构、相关工作深度、语言与术语；
- 输出完整修订稿 markdown，不要输出解释。

审稿意见（分数 {review.get('scores')}）：
重大问题：{json.dumps(review.get('majors', []), ensure_ascii=False)}
次要问题：{json.dumps(review.get('minors', []), ensure_ascii=False)}

当前稿件：
{draft}"""
    content = get_message_content(chat([{"role": "user", "content": prompt}]))
    return content.strip() if content and content.strip() != draft else draft


def wash_jargon(text: str) -> str:
    for old, new in JARGON_WASHES:
        text = text.replace(old, new)
    return text


# --------------------------------------------------------------------------- #
# Main entry
# --------------------------------------------------------------------------- #


def write_paper_v2(
    project_id: str,
    idea: str,
    selected: dict[str, Any],
    metrics: dict[str, Any],
    papers: list[dict[str, Any]],
    lang: str = "zh",
    workspace_root: Path | None = None,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
) -> dict[str, Any]:
    """Full v2 paper generation. Returns the review-loop ledger."""
    from services.research_harness.reviewer_agent import _metrics_for_prompt

    bp_path = paper_blueprint.build_blueprint(project_id, idea, selected, metrics, papers, workspace_root)
    bp = json.loads(bp_path.read_text(encoding="utf-8"))

    parts: list[str] = []
    for section in SECTION_ORDER:
        prompt = _section_prompt(section, bp, lang, "\n\n".join(parts))
        content = get_message_content(chat([{"role": "user", "content": prompt}]))
        if not content.strip():
            raise RuntimeError(f"section {section} returned empty (gateway degradation)")
        titles = _ZH_SECTION_TITLES if lang == "zh" else _EN_SECTION_TITLES
        body = content.strip()
        if section == "experiments":
            # Deterministic guarantees: the table is INLINED and the claim
            # markers APPENDED by the engine — neither depends on LLM
            # compliance (S18/S19 lesson: hand-copied tables dropped systems,
            # hand-written markers invented numbers).
            if "baseline" not in body or "|---|" not in body:
                body += "\n\n" + bp["tables"]["main"] + "\n"
            if bp["figures"]:
                fig_list = "、".join(bp["figures"])
                if not any(f in body for f in bp["figures"]):
                    body += f"\n（图：{fig_list}，见随稿图件）\n"
            exp_claims = [c for c in bp["claims"] if c.get("section") == "experiments"]
            expected = sum(
                1 for c in exp_claims if c.get("evidence", {}).get("proposed") is not None
                and c.get("evidence", {}).get("baseline") is not None
            )
            if body.count("audit-claim") < expected:
                marker_block = "\n\n".join(
                    re.findall(r"`(<!-- audit-claim[^`]*-->)`", _claim_markers(exp_claims))
                )
                if marker_block:
                    body += "\n\n" + marker_block + "\n"
        parts.append(f"## {titles[section]}\n\n{body}")

    draft = wash_jargon("\n\n".join(parts))

    # ---- review-revision convergence (A4) ----
    metrics_bounded = _metrics_for_prompt(metrics)
    trajectory: list[dict[str, Any]] = []
    final_review: dict[str, Any] = {}
    for rnd in range(1, max_rounds + 1):
        review = review_paper(draft, metrics_bounded, idea)
        trajectory.append({"round": rnd, "scores": review.get("scores"), "majors": review.get("majors", [])})
        final_review = review
        if review.get("passed"):
            break
        revised = _revise(draft, review, bp)
        if revised == draft:
            trajectory[-1]["note"] = "revision produced no change; stopping"
            break
        # numbers must stay anchored: if any audit-claim marker changed, revert
        old_markers = re.findall(r"<!-- audit-claim[^>]*-->", draft)
        new_markers = re.findall(r"<!-- audit-claim[^>]*-->", revised)
        if sorted(old_markers) != sorted(new_markers):
            trajectory[-1]["note"] = "revision altered claim markers; reverted"
            break
        draft = revised

    titles = _ZH_SECTION_TITLES if lang == "zh" else _EN_SECTION_TITLES
    # references section (deterministic, from the blueprint)
    refs_md = "## " + ("参考文献" if lang == "zh" else "References") + "\n\n" + "\n".join(
        f"{r['marker']} {r['entry_gbt']}" for r in bp["references"]
    )
    draft = draft + "\n\n" + refs_md

    root = Path(workspace_root) if workspace_root is not None else _ws_root()
    paper_dir = root / project_id / "paper"
    paper_dir.mkdir(parents=True, exist_ok=True)
    fname = "draft_journal_zh_v2.md" if lang == "zh" else "draft_v2.md"
    (paper_dir / fname).write_text(draft, encoding="utf-8")
    (paper_dir / (fname.replace(".md", ".raw.md"))).write_text(draft, encoding="utf-8")

    ledger = {
        "blueprint": str(bp_path),
        "figures": bp["figures"],
        "review_trajectory": trajectory,
        "final_scores": final_review.get("scores"),
        "passed": final_review.get("passed", False),
        "lang": lang,
    }
    (paper_dir / ("review_loop_zh.json" if lang == "zh" else "review_loop.json")).write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("[PaperV2] %s lang=%s rounds=%d passed=%s scores=%s",
                project_id, lang, len(trajectory), ledger["passed"], ledger["final_scores"])
    return ledger


def _ws_root() -> Path:
    from services.research_harness.pipeline import WORKSPACE_ROOT
    return WORKSPACE_ROOT
