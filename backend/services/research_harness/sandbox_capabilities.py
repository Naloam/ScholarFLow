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


def capability_note() -> str:
    """拼一段文字，追加进 codegen/repair prompt 的「允许的包」段，告诉 LLM 实际能用什么。

    Session 4：sentence-transformers 可用，proposed method **必须**用它真正实现句向量假设。
    """
    available = ", ".join(ALLOWED_PACKAGES)
    return (
        "\n\n## 实际可用的 sandbox 能力（已实测 2026-06-16，必须遵守）\n\n"
        f"- 执行后端：{SANDBOX_BACKEND_KIND}（直接用 sys.executable 运行，即仓库根 .venv）\n"
        "- 第三方数据科学包实测状态：\n"
        "  - numpy / scikit-learn: **可用**（已装进 .venv）。\n"
        f"  - sentence-transformers（{EMBEDDING_MODEL}）: **可用** ✅ —— 模型 ~80MB，首次加载已缓存，"
        "后续加载约 1-2 秒。**允许且鼓励**用 `SentenceTransformer('all-MiniLM-L6-v2')` 实现假设里"
        "的句向量方法。\n"
        "  - HuggingFace datasets: **不可用** → 不能 `from datasets import load_dataset`；数据走 seed_data。\n"
        f"- 因此允许导入的第三方包：{available}\n"
        "- 只允许使用 Python 标准库 + 上述已实测可用的包。\n"
        "## 🔴 方法-假设一致性（Session 4 核心，违反即判失败）\n"
        "- **proposed method 必须真正用 `SentenceTransformer('all-MiniLM-L6-v2')` 计算句向量**，"
        "用 L2 归一化后的余弦相似度作为 claim-evidence 匹配度，再做阈值校准预测 faithful/error。"
        "**禁止把 proposed 降级成 TF-IDF / Jaccard / 词法匹配**——那正是 Session 3 reviewer 戳的"
        "「方法-假设不匹配」major weakness，本 session 必须消除。\n"
        "- **SentenceTransformer 模型只 load 一次并缓存复用**（module 级全局变量），不要每个 seed/"
        "数据集都重新 load。先对每个数据集的 100 条 (claim, evidence) 一次性算好归一化句向量，"
        "再在 bootstrap 重采样里只做下标取值 + 余弦，保证 10 分钟内跑完。\n"
        "- baseline 可以保留 TF-IDF / Jaccard 词法相似度作为**弱基线**（用来证明句向量优于词法）。\n"
        "- ablation 必须与 proposed 实质不同（例如 char-ngram TF-IDF，或 ST 向量但不做 L2 归一化）。\n"
        "- 禁止用 GPU（no .cuda(), no device='cuda'）——CPU 推理即可。\n"
        "- 数据集策略：**必须使用 `DATASET_REGISTRY`（见下方注册表），用注册表给的绝对路径 loader "
        "原样粘进 load_data()。禁止 urllib.request 下载自创 URL；禁止随机生成的假数据作正式实验数据。**\n"
        f"- 单次运行必须 ≤ {MAX_EXPERIMENT_SECONDS} 秒；每个数据集截到 ≤ 500 条；降低模型/检索复杂度。\n"
    ) + datasets.registry_note()
