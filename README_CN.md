# ScholarFlow

ScholarFlow 是一个 AI 驱动的自动化学术研究平台，在工作空间内编排完整的学术研究生命周期——从选题、实验执行到论文撰写与审稿。

## 快速开始

### 1. 环境要求

- Python 3.12+
- Node.js 18+
- 一个 LLM API 密钥（DeepSeek、OpenAI 或任何 litellm 兼容的提供商）

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，至少配置一个 LLM 提供商：

```bash
# 方案 A — DeepSeek（推荐，性价比高）
DEEPSEEK_API_KEY=sk-your-key-here
LLM_MODEL=deepseek/deepseek-chat
LLM_API_BASE=https://api.deepseek.com

# 方案 B — OpenAI
OPENAI_API_KEY=sk-your-key-here
LLM_MODEL=openai/gpt-4o-mini

# 数据库 — 本地开发使用 SQLite 即可
DATABASE_URL=sqlite:///backend/dev.db
```

### 3. 安装依赖

```bash
# 后端
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# 前端
cd frontend && npm install && cd ..
```

### 4. 启动服务

```bash
# 终端 1 — 后端（端口 8000）
cd backend && PYTHONPATH=. python -m uvicorn main:app --reload

# 终端 2 — 前端（端口 5173）
cd frontend && npm run dev
```

在浏览器打开 **http://localhost:5173**。

### 5. 使用工作空间

ScholarFlow 工作空间通过分阶段的研究工作流引导你完成整个流程：

| 阶段 | 面板                       | 操作                                                                           |
| ---- | -------------------------- | ------------------------------------------------------------------------------ |
| 1    | **项目启动器**（左侧边栏） | 输入标题、主题和模板，点击 **Create Project**                                  |
| 2    | **研究路线图**（左侧边栏） | 查看自动生成的研究计划和假设                                                   |
| 3    | **编辑器**（中央区域）     | 点击 **Generate Draft** 通过 LLM 生成完整论文大纲，使用富文本编辑器编辑        |
| 4    | **文件管理器**（左侧边栏） | 保存草稿、跟踪版本，点击 **Download Latest Export** 导出 Markdown              |
| 5    | **审阅面板**（右侧边栏）   | 点击 **Run Review** 检查证据覆盖率，标记 `[NEEDS_EVIDENCE]`，进行相似度筛查    |
| 6    | **操作控制台**（中央右侧） | 点击 **Start Run** 启动完整的自动研究流水线：规划 → 代码生成 → 执行 → 论文生成 |
| 7    | **部署**（右侧边栏）       | 导出并下载最终发布包                                                           |

**典型工作流：** 创建项目 → 生成草稿 → 编辑 → 保存 → 运行审阅 → 启动研究 → 下载最终发布包

### 6. 配置选项

主要环境变量（完整列表参见 `.env.example`）：

| 变量            | 默认值                     | 说明                                              |
| --------------- | -------------------------- | ------------------------------------------------- |
| `LLM_MODEL`     | `gpt-4o-mini`              | litellm 模型标识符（如 `deepseek/deepseek-chat`） |
| `LLM_API_BASE`  | —                          | 非 OpenAI 提供商的 API 地址                       |
| `DATABASE_URL`  | `sqlite:///backend/dev.db` | PostgreSQL 或 SQLite 连接字符串                   |
| `AUTH_REQUIRED` | `false`                    | 是否启用身份认证                                  |
| `DATA_DIR`      | `backend/data`             | 项目数据存储目录                                  |

## 文档索引

- `PROJECT_PLAN.md`：权威路线图和阶段优先级
- `docs/architecture.md`：当前和目标架构
- `docs/api-reference.md`：自动研究和注册表 API

## 开发入口

- 后端：`cd backend && PYTHONPATH=. ../.venv/bin/uvicorn main:app --reload`
- 前端：`cd frontend && npm run dev`
- 前端构建：`cd frontend && npm run build`

## 核心路径

- 自动研究编排：`backend/services/autoresearch/orchestrator.py`
- 实验执行：`backend/services/autoresearch/runner.py`
- 执行平面：`backend/services/autoresearch/execution.py`
- 持久化与清单：`backend/services/autoresearch/repository.py`
- 论文生成：`backend/services/autoresearch/writer.py`
- 数据模型：`backend/schemas/autoresearch.py`
