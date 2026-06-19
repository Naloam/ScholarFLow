"""Curated 数据集注册表（Session 3 Step 1；Session 4 加第 3 个引用专属数据集）。

每个条目都是**真实、有出处、已提交到仓库**的平衡小切片（见 seed_data/README.md）。
codegen 必须从此表选数据集并用提供的绝对路径 loader，**禁止自创 URL / 自创数据**
（Session 2 就是栽在 codegen 猜的 404 URL 上 → n=3）。

数据已 commit，loader 只用标准库 json 直读——**零运行时网络依赖**，彻底消除 404 风险。

Session 4 起，三个数据集被统一成**同一个任务**：claim-evidence faithfulness 二分类
（faithful/support = 1 vs parsing-error/refute = 0）。这样 proposed（句向量相似度）能
在**同一个**任务框架下被三个数据集检验，且第三个数据集直接对应「检测引用解析错误」假设。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SEED_DIR: Path = Path(__file__).resolve().parent / "seed_data"


@dataclass(frozen=True)
class DatasetSpec:
    key: str                       # "scifact_claim_verification"
    task: str                      # "claim_verification" / "citation_faithfulness"
    description: str
    file_path: Path                # 绝对路径，experiment.py 直接 open()
    n_examples: int
    label_balance: str
    positive_label: str            # 正类（faithful/supportive）→ 预测 1
    negative_label: str            # 负类（parsing-error/refute）→ 预测 0
    metric_hint: str               # "macro_f1 / accuracy"
    attribution: str
    # Session 12 (cross-domain): which domain this dataset belongs to + how to load it.
    domain: str = "claim_verification"   # claim_verification / tabular / structured / code
    feature_schema: str = ""             # "" = text(claim,evidence); else feature-vector layout


DATASET_REGISTRY: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        key="scifact_claim_verification",
        task="claim_verification",
        description=(
            "Scientific claim verification (SciFact). Given a scientific claim and an evidence "
            "abstract, the citation is SUPPORT (faithful) or REFUTE (contradicts). Domain: "
            "biomedical/scientific abstracts."
        ),
        file_path=SEED_DIR / "scifact_slice.jsonl",
        n_examples=474,
        label_balance="237 SUPPORT / 237 REFUTE",
        positive_label="SUPPORT",
        negative_label="REFUTE",
        metric_hint="macro_f1 / accuracy",
        attribution=(
            "allenai/scifact (CC BY 4.0), balanced held-out slice of all labeled "
            "SUPPORT/REFUTE claims (dev + train; gold corpus abstract attached)"
        ),
    ),
    DatasetSpec(
        key="vitaminc_claim_verification",
        task="claim_verification",
        description=(
            "Wikipedia-edit claim verification (VitaminC). Given a claim and an evidence passage, "
            "the citation is SUPPORT (faithful) or REFUTE (contradicts). Domain: Wikipedia sentences "
            "(distinct from SciFact)."
        ),
        file_path=SEED_DIR / "vitaminc_slice.jsonl",
        n_examples=500,
        label_balance="250 SUPPORT / 250 REFUTE",
        positive_label="SUPPORT",
        negative_label="REFUTE",
        metric_hint="macro_f1 / accuracy",
        attribution="tals/vitaminc (CC BY-SA 4.0), 500-example balanced held-out dev slice",
    ),
    DatasetSpec(
        key="citation_faithfulness",
        task="citation_faithfulness",
        description=(
            "Citation faithfulness / parsing-error detection (Session 4 专属). Each example pairs a "
            "claim with an evidence abstract. FAITHFUL = the claim's own correct evidence; "
            "PARSING_ERROR = a mismatched abstract (the citation points to the wrong source — a "
            "realistic citation parsing error). This dataset directly operationalizes the hypothesis "
            "'detect citation parsing errors'. Derived deterministically from allenai/scifact."
        ),
        file_path=SEED_DIR / "citation_faithfulness_slice.jsonl",
        n_examples=474,
        label_balance="237 FAITHFUL / 237 PARSING_ERROR",
        positive_label="FAITHFUL",
        negative_label="PARSING_ERROR",
        metric_hint="macro_f1 / accuracy",
        attribution="derived from allenai/scifact (CC BY 4.0); deterministic faithful/mismatched pairs",
    ),
    # ------------------------------------------------------------------ #
    # Session 12: non-retrieval domains (proves the brain is not overfit).
    # Feature-vector layout, loaded by stdlib json (zero runtime network).
    # ------------------------------------------------------------------ #
    DatasetSpec(
        key="breast_cancer_tabular",
        task="tabular_classification",
        description=(
            "Clinical tabular binary classification (domain=tabular). 30 numeric diagnostic "
            "features → malignant(0)/benign(1). Real features from sklearn.datasets."
            "load_breast_cancer. Used to test a hypothesis OUTSIDE retrieval/abstention "
            "(e.g. feature-interaction modelling, calibration) — the method must be a tabular "
            "classifier, NOT sentence-transformer cosine."
        ),
        file_path=SEED_DIR / "breast_cancer_slice.jsonl",
        n_examples=424,
        label_balance="212 label-0 / 212 label-1",
        positive_label="1",
        negative_label="0",
        metric_hint="macro_f1 / accuracy",
        attribution="sklearn.datasets.load_breast_cancer (real clinical features), balanced held-out slice",
        domain="tabular",
        feature_schema='{"id","features":[30 floats],"label":0|1,"label_name"}',
    ),
    DatasetSpec(
        key="digits_structured",
        task="structured_image_classification",
        description=(
            "Handwritten-digit structured/image binary classification (domain=structured). 64 "
            "(8x8) pixel features (0..1) → parity label even(0)/odd(1) — a real binary "
            "structuring of the 10-class digit task. Real images from sklearn.datasets.load_digits. "
            "Method must be a feature classifier on the pixels, NOT sentence-transformer cosine."
        ),
        file_path=SEED_DIR / "digits_slice.jsonl",
        n_examples=500,
        label_balance="250 even / 250 odd",
        positive_label="1",
        negative_label="0",
        metric_hint="macro_f1 / accuracy",
        attribution="sklearn.datasets.load_digits (real handwritten digits), balanced held-out slice",
        domain="structured",
        feature_schema='{"id","features":[64 floats 0..1],"label":0|1,"label_name"}',
    ),
)


def loader_snippet(spec: DatasetSpec) -> str:
    """返回该数据集可直接粘进 experiment.py 的标准库 loader（绝对路径已嵌入）。

    Domain-aware (Session 12): text layout for claim_verification, feature-vector
    layout for tabular/structured/code. The loader body is identical (stdlib json
    read); only the embedded schema comment differs so codegen shapes ``X``/``y``
    correctly.
    """
    if spec.feature_schema:
        schema_comment = f"    # 每行 schema: {spec.feature_schema}（label: {spec.positive_label}=1, {spec.negative_label}=0）\n"
    else:
        schema_comment = (
            "    # 每行 schema:\n"
            '    # {"id","claim","evidence","evidence_title","label","source"}\n'
            f"    # label 词表: positive(faithful)={spec.positive_label}, negative(error)={spec.negative_label}\n"
        )
    return (
        "import json\n"
        f'_DATA_PATH = r"{spec.file_path}"\n'
        "def load_dataset(path=_DATA_PATH):\n"
        "    # 标准库直读，无网络。\n"
        + schema_comment +
        "    return [json.loads(line) for line in open(path, encoding='utf-8').read().splitlines() if line.strip()]\n"
    )


def _specs_by_domain() -> dict[str, list[DatasetSpec]]:
    grouped: dict[str, list[DatasetSpec]] = {}
    for spec in DATASET_REGISTRY:
        grouped.setdefault(spec.domain, []).append(spec)
    return grouped


def registry_note(domain: str | None = None) -> str:
    """拼进 codegen/planner/repair prompt：必须从注册表选，禁止自创 URL/数据。

    Session 12 (cross-domain): ``domain=None`` (default) preserves the exact
    claim-verification behaviour (the 3 claim-evidence datasets, "traverse all",
    label map). A non-``claim_verification`` ``domain`` scopes the note to that
    domain's datasets + instructions (the brain must not be dragged back to
    sentence-transformer cosine for a tabular/code hypothesis).
    """
    grouped = _specs_by_domain()
    active = domain if domain and domain != "claim_verification" else None

    lines: list[str] = [
        "\n\n## 🔴 数据集注册表（必须使用，禁止自创 URL / 禁止自创数据）\n",
        "Session 2 因 codegen 自创 GitHub URL 而 404，导致 n_test=3。本 session 起数据集必须从下表选，",
        "并用下面给的**绝对路径 loader 原样粘进 load_data()**（标准库 json 直读，无网络，不会 404）。\n",
    ]
    if active is None:
        lines.append(
            "\n**统一任务（claim_verification 域）**：三个数据集都是 **claim-evidence faithfulness 二分类**——"
            "正类(faithful)=1，负类(parsing-error/unfaithful)=0。每个数据集的 `label` 词表不同，"
            "必须按下表映射：`positive_label` → 1（faithful/supportive），`negative_label` → 0（error/refute）。\n"
        )
    else:
        lines.append(
            f"\n**本次实验 domain = `{active}`**：只用下方 `{active}` 域的数据集，"
            f"**不要遍历其它域**（其它域仅供注册表可发现性展示）。"
            f"feature-vector 数据集（非文本）：每行 `{{'features':[...], 'label':0|1}}`，"
            f"用 `X=np.array([r['features'] for r in rows]); y=np.array([r['label'] for r in rows])` 构造。\n"
        )

    target_specs = grouped.get(active, []) if active else grouped.get("claim_verification", [])
    for spec in target_specs:
        lines.append(f"### {spec.key} （{spec.task}, domain={spec.domain}）")
        lines.append(f"- {spec.description}")
        lines.append(f"- 规模 {spec.n_examples} 例（{spec.label_balance}），建议 metric: {spec.metric_hint}")
        if not spec.feature_schema:
            lines.append(f"- label 映射: `{spec.positive_label}`→1(faithful), `{spec.negative_label}`→0(error)")
        lines.append(f"- 出处: {spec.attribution}\n")

    lines.append(f"### 你必须在 experiment.py 里（domain={active or 'claim_verification'}）：")
    lines.append("1. 把所选数据集的 loader 原样粘进去（绝对路径，**不要改、不要换成自创 URL**）。")
    if active is None:
        lines.append("2. **必须用 claim_verification 域全部数据集**（3 个），对每个数据集都跑一遍实验。")
    else:
        lines.append(f"2. **遍历 `{active}` 域全部数据集**（{len(target_specs)} 个），对每个都跑一遍。")
    lines.append(
        "3. 每个数据集 × 每个 system 跑 **≥128 个 seed（尽量贴近 512）**。seed 机制 = **配对 bootstrap 重采样**："
        "对每个 seed，用 `random.Random(seed)` 生成 n 个有放回抽样下标（n=数据集大小），"
        "用**同一组下标**评估所有 system（保证配对）；这会给每个 system 一组 per-seed macro_f1，用于配对符号检验。"
        "（Session 10 实测：512 seed × 500 例 × 3 数据集计算量 <1 秒，预算远未触顶——"
        "seed 越多 paired sign-flip 检验功效越高；目标是不再 underpowered。）"
    )
    lines.append("4. 每条结果输出一行 `__RESULT__` row：")
    lines.append(
        "   `{\"system_name\":..., \"seed\":0, \"metric_name\":\"macro_f1\", \"metric_value\":0.xx, "
        "\"n_test\":N, \"dataset_name\":\"<注册表 key>\"}`"
    )
    lines.append("5. 最后 `print(\"__RESULT__\", json.dumps(results))`。\n")

    lines.append("### 各数据集 loader（原样复制，绝对路径已填好）\n")
    for spec in target_specs:
        lines.append(f"```python\n# {spec.key}\n{loader_snippet(spec)}```\n")
    return "\n".join(lines)


def keys() -> tuple[str, ...]:
    return tuple(spec.key for spec in DATASET_REGISTRY)
