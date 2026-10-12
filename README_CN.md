# ScholarFlow

ScholarFlow 是一个自动科研系统：输入一个研究 idea，系统自动完成全流程——真实文献检索（arXiv / Semantic Scholar / Crossref）、假设生成、实验代码生成与执行（真实 subprocess、CPU 级）、统计评估、诚实的研究报告、论文草稿撰写，以及拒绝无依据论断的审计门。当前目标（P4）：把通过审计的 run 转化为核心期刊论文稿件（一作/独立作者），产出前必须经过人工编辑 + 重新审计闭环。

## 实际能力

一条命令跑完整流程：

```bash
cd backend && ../.venv/bin/python ../scripts/v0_run.py --idea "..." --project-id my_run
```

在 `backend/data/research_workspace/<project_id>/` 产出：

| 阶段 | 产出 | 保证 |
|---|---|---|
| literature | `papers.jsonl`、`notes.md`、`gap_map.md` | 真实检索论文，无伪造引用 |
| idea | `candidates.json`、`selected.json` | 假设带文献支撑的 `core_novelty` |
| experiment | `candidates/*/artifacts/metrics.json` | 真实数据集（SciFact、VitaminC、表格切片）上的真实数值，多 seed + 显著性检验 |
| review | `reviewer_round_1.md` | 引用 run 自身数字的具体批评 |
| report | `research_report.md`、`conclusion.md` | 负结果保持负结果（硬编码结论门） |
| write | `paper/draft.md` | 缺证据的论断内联 `[UNVERIFIED]` 标记 |
| audit | `ledger/claim_audit.json` | 确定性审计门（不用 LLM 审 LLM）；结构化 `audit-claim` 标记按数值核验 |
| publish | `publish_bundle.zip` | 任何诚实门不过则 `publishable=false` |

Portfolio 执行独立跑 top-K 个假设候选并诚实聚合（结论冲突时如实写 `mixed_portfolio`）。TipTap 编辑器允许人工修改草稿，保存后重新过审计门——人加的无依据论断同样会被标记。

## 架构

- **后端**（FastAPI，`backend/`）：研究大脑全部在 `services/research_harness/`（约 7k 行）——pipeline、实验工程师、evidence/auditor 诚实门、writer、publish。LLM 调用统一走 `services/llm/client.py`（基于 litellm）。2026 年 6 月物理退役了旧 `autoresearch` 系统（约 7.2 万行），仅按设计保留 `literature_connectors.py`。
- **前端**（React 19 + Vite + TipTap，`frontend/`）：五个页面——Projects、Run、Workspace、Report（论文编辑器 + 发布卡片）、Settings。
- **测试**：213 个离线测试（`cd backend && SCHOLARFLOW_OFFLINE_LLM=1 ../.venv/bin/python -m pytest tests/ -m "not live_research" -q`）；live 端到端需显式开启（`-m live_research`，真实 LLM + 额度）。

## 安装

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e "backend[dev]" -r backend/requirements-experiment.txt
cp .env.example .env   # 然后设置 LITELLM_API_KEY / LLM_MODEL / LLM_API_BASE
```

后端：`cd backend && PYTHONPATH=. ../.venv/bin/uvicorn main:app --reload`
前端：`cd frontend && npm install && npm run dev`

## 诚实的局限

- 数据切片 ≤500 例、单实验 ≤10 分钟 CPU（无 GPU）——workshop 级证据强度，不是 SOTA 竞争；扩容是 P4 工作项。
- "沙箱"用宿主 Python 直接执行生成代码（无隔离）——仅限可信单人环境。
- 审计门的 prose 启发式以英文为中心；中文草稿依赖结构化 `audit-claim` 标记（S17）。
- `publishable=true` 只代表诚实门通过，不代表可直接投稿。

## 文档

- `AGENTS.md` —— 贡献规则与当前目标
- `docs/research-harness-roadmap.md` —— 逐 session 历史记录、live run 基线表、P2–P4 计划
- `SCHOLARFLOW_CORE_REBUILD_PLAN_v2.md` —— 2026 年 6 月导致重建的失败诊断
