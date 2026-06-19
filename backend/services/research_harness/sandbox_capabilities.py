"""ExperimentEngineer 可用的 sandbox 能力（Session 4 Step 0 实测，2026-06-16）。

实测结论（Session 4 Step 0）：
本机装了 Docker，所以 ExecutionBackendSpec() 默认 kind="auto" 会解析成
DockerSandboxBackend（python:3.11-slim），那个镜像里没有 numpy/sklearn/sentence-transformers，
实验必崩。因此所有 sandbox 调用必须显式 kind="local"，让代码在 ``sys.executable``
（即仓库根 .venv 的 python）里跑。

🔴 Session 4 关键变化（修复 Session 3 reviewer 的「方法-假设不匹配」major weakness）：
Session 3 时 .venv 只有 fastapi+litellm+标准库，所以句向量假设被迫降级成 TF-IDF。
Session 4 一次性把 numpy / scikit-learn / sentence-transformers 装进了 .venv（见
requirements-experiment.txt），实测 all-MiniLM-L6-v2 可加载（384 维）。因此 proposed method
现在**真正实现假设所述的句向量方法**，不再降级成 TF-IDF。

注意：LLM 网关 https://ai.saurlax.com/v1 **不提供 embeddings 接口**（/models 只有 11 个 chat
模型），所以 embedding 必须走本地 sentence-transformers，不能用 litellm.embedding。
"""
from __future__ import annotations

from services.research_harness import datasets

# 🔴 必须 local：本机有 Docker，auto 会跑没包的 slim 镜像必崩。
SANDBOX_BACKEND_KIND: str = "local"

# 单次实验时间上限（10 分钟，对齐 plan §4.3 / AGENTS.md）。
MAX_EXPERIMENT_SECONDS: int = 600

# 实测可用的第三方包（Session 4 Step 0 实测：已装进仓库根 .venv）。
ALLOWED_PACKAGES: tuple[str, ...] = ("numpy", "scikit-learn", "sentence-transformers")

# 实测（Session 4）：sentence-transformers 可用（all-MiniLM-L6-v2，384 维，~80MB，已缓存）。
SENTENCE_TRANSFORMERS_AVAILABLE: bool = True
# 实测：HuggingFace datasets 仍不可用（不能 load_dataset）——但实验用 stdlib json 直读
# 已 commit 的 seed_data 切片，不需要 datasets。
HF_DATASETS_AVAILABLE: bool = False

EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"


def domain_agnostic_note() -> str:
    """Domain-agnostic sandbox contract (Session 12).

    Budget, backend, allowed packages, the no-GPU / no-self-invented-URL / no-fake-data
    rules, and the **method-hypothesis consistency principle** (stated generically — the
    concrete method is chosen per domain by :func:`domain_method_note`).
    """
    available = ", ".join(ALLOWED_PACKAGES)
    return (
        "\n\n## 实际可用的 sandbox 能力（已实测，必须遵守）\n\n"
        f"- 执行后端：{SANDBOX_BACKEND_KIND}（直接用 sys.executable 运行，即仓库根 .venv）\n"
        "- 第三方数据科学包实测状态：\n"
        "  - numpy / scikit-learn: **可用**（已装进 .venv）。\n"
        f"  - sentence-transformers（{EMBEDDING_MODEL}）: **可用** ✅（仅 claim_verification 域需要；"
        "其它域用 sklearn 分类器，不要硬套句向量）。\n"
        "  - HuggingFace datasets: **不可用** → 不能 `from datasets import load_dataset`；数据走 seed_data。\n"
        f"- 因此允许导入的第三方包：{available}\n"
        "- 只允许使用 Python 标准库 + 上述已实测可用的包。\n"
        "## 🔴 方法-假设一致性（通用原则，违反即判失败）\n"
        "- **proposed method 必须真正实现假设所述的方法**（具体方法见下方「本域方法提示」）。"
        "禁止把 proposed 降级成一个与假设无关的简易方法——方法-假设不匹配是 major weakness。\n"
        "- 禁止用 GPU（no .cuda(), no device='cuda'）——CPU 推理即可。\n"
        "- 数据集策略：**必须使用 `DATASET_REGISTRY`（见下方注册表），用注册表给的绝对路径 loader "
        "原样粘进 load_data()。禁止 urllib.request 下载自创 URL；禁止随机生成的假数据作正式实验数据。**\n"
        f"- 单次运行必须 ≤ {MAX_EXPERIMENT_SECONDS} 秒；每个数据集截到 ≤ 500 条；降低模型/检索复杂度。\n"
    )


def domain_method_note(domain: str | None = None) -> str:
    """Per-domain method guidance (Session 12). ``domain`` defaults to claim_verification.

    The claim_verification note preserves the Session-4/V2.4 sentence-transformer
    cosine requirement verbatim (byte-equivalent). Other domains route to sklearn
    classifiers so a tabular/code/structured hypothesis is NOT dragged back to ST
    cosine.
    """
    d = (domain or "claim_verification").strip().lower()
    if d in {"", "claim_verification"}:
        return (
            "## 🔴 本域方法提示（domain=claim_verification）\n"
            "- **proposed method 必须真正用 `SentenceTransformer('all-MiniLM-L6-v2')` 计算句向量**，"
            "用 L2 归一化后的余弦相似度作为 claim-evidence 匹配度，再做阈值校准预测 faithful/error。"
            "**禁止把 proposed 降级成 TF-IDF / Jaccard / 词法匹配**——那正是 Session 3 reviewer 戳的"
            "「方法-假设不匹配」major weakness。\n"
            "- **SentenceTransformer 模型只 load 一次并缓存复用**（module 级全局变量）。先对每个数据集的全部 "
            "(claim, evidence)（≤500 条）一次性算好归一化句向量，再在 bootstrap 重采样里只做下标取值 + 余弦"
            "——Session 10 实测该路径在 512 seed × 500 例 × 3 数据集下计算量 <1 秒，**seed 应贴近 512**。\n"
            "- baseline 分两层（Session 10）：① **弱基线** TF-IDF / Jaccard 词法相似度；"
            "② **强基线 `stronger_baseline`** = BM25 (Okapi) 词法检索 + 浅层分数融合/阈值校准——proposed 的 win "
            "**必须越过强基线 BM25**，不能只赢弱基线 TF-IDF（VICTOR / VERIRAG 见 Future Work，需 GPU/大模型）。\n"
            "- 三个 metric（每个 system 每个 seed 都算）：`macro_f1`（主指标）；"
            "`spearman_consistency_vs_label`（弃权①，越高越好）；`error_rate_at_20pct_abstain`（弃权②，越低越好）。\n"
            "- ablation 必须与 proposed 实质不同（例如 char-ngram TF-IDF，或 ST 向量但不做 L2 归一化）。\n"
        )
    if d == "tabular":
        return (
            "## 🔴 本域方法提示（domain=tabular，特征向量分类）\n"
            "- 数据是**数值特征向量**（非文本）：`X=np.array([r['features'] for r in rows]); y=np.array([r['label'] for r in rows])`。"
            "**禁止用 SentenceTransformer / TF-IDF / 文本相似度**——这里没有文本，那会立刻方法-假设不匹配。\n"
            "- **proposed method 必须真正实现假设所述的表格方法**（如显式特征交互建模、校准损失、特征选择等），"
            "用 sklearn（如 `LogisticRegression`/`RandomForestClassifier`/`GradientBoostingClassifier`/`MLPClassifier`）。"
            "baseline = 一个朴素 sklearn 分类器（如仅主效应 LogisticRegression）；stronger_baseline = RandomForest 或 "
            "GradientBoosting；proposed 必须越过 stronger_baseline。ablation 去掉 proposed 的关键组件。\n"
            "- metric：`macro_f1`（主指标）。若假设关于校准，**还**算 `calibration_error`（binned ECE，越低越好）作为"
            "primary_metric；若关于特征交互，可算 `auc`。primary_metric 必须是假设真正关心的那个。\n"
            "- 每个 system load/fit 一次模型（bootstrap 只对 (X,y) 重采样下标），保证 ≤ 预算跑完 ≥128 seed。\n"
        )
    if d == "structured":
        return (
            "## 🔴 本域方法提示（domain=structured，结构化/图像特征分类）\n"
            "- 数据是**结构化特征向量**（如 8x8=64 像素）：`X=np.array([r['features'] for r in rows]); y=np.array([r['label'] for r in rows])`。"
            "**禁止用 SentenceTransformer / 文本方法**——结构化特征不是文本。\n"
            "- **proposed 必须真正实现假设所述的结构化方法**（如空间结构感知、局部-全局特征融合、特定归一化），"
            "用 sklearn 分类器。baseline = 朴素 LogisticRegression；stronger_baseline = RandomForest/MLP；"
            "proposed 必须越过 stronger_baseline。ablation 去掉结构化组件。\n"
            "- metric：`macro_f1`（主指标），按假设可加 `auc`。primary_metric 必须匹配假设。\n"
            "- 每个 system fit 一次模型，bootstrap 只重采样下标，≥128 seed。\n"
        )
    if d == "code":
        return (
            "## 🔴 本域方法提示（domain=code，代码特征分类）\n"
            "- 数据是**从代码提取的特征向量**（如 token 频度/复杂度特征）：用 numpy 构造 X/y。"
            "**禁止用 SentenceTransformer 句向量**（除非假设明确要求语义代码嵌入）。\n"
            "- **proposed 必须实现假设所述的代码方法**，用 sklearn 分类器。baseline 朴素，stronger_baseline 更强，"
            "proposed 必须越过它。metric `macro_f1`/`auc`，primary_metric 匹配假设。\n"
            "- 每个 system fit 一次，bootstrap 重采样下标，≥128 seed。\n"
        )
    # Unknown domain: fall back to the consistency principle only (no method forced).
    return (
        f"## 🔴 本域方法提示（domain={d}）\n"
        "- **proposed method 必须真正实现假设所述的方法**（用 numpy/scikit-learn，no GPU）。"
        "baseline 朴素、stronger_baseline 更强、proposed 必须越过 stronger_baseline；ablation 去掉关键组件。\n"
        "- metric `macro_f1` 为主，primary_metric 必须匹配假设。\n"
    )


def capability_note(domain: str | None = None) -> str:
    """Compose the codegen/repair capability note.

    Session 12 (cross-domain): ``domain_agnostic_note()`` + ``domain_method_note(domain)``
    + ``datasets.registry_note(domain)``. ``domain=None`` (default) is byte-equivalent to
    the pre-Session-12 claim-verification note.
    """
    return domain_agnostic_note() + domain_method_note(domain) + datasets.registry_note(domain)
