# ScholarFlow

ScholarFlow 是面向大学生的全流程学术论文写作 Agent 系统。

本仓库结构与开发规范以 `PROJECT_PLAN.md` 为唯一权威来源。

## 当前状态

- Phase 7 进行中：导师审阅模式与本地重合度筛查已落地
- 前后端与核心写作、审稿、导出链路已可运行
- Auto-research 现在带有 execution plane：job queue、worker 状态机、checkpoint-based `resume/retry/cancel`
- 仓库现在同时支持本地开发模式和 Docker 全栈部署模式

## 开发入口

- 后端：`cd backend && PYTHONPATH=. ../.venv/bin/uvicorn main:app --reload`
- 前端：`cd frontend && npm install && npm run dev`
- 迁移：`cd backend && ../.venv/bin/alembic -c alembic.ini upgrade head`

## 本地开发环境

- 推荐 Python 3.11；当前仓库在 Python 3.13 下可运行，但向量检索默认走 JSON fallback，完整 FAISS 能力建议使用 `backend[vectors]`
- 默认数据库连接与 `docker-compose.yml` 一致：`scholarflow:scholarflow@localhost:5432/scholarflow`
- 前端开发服务器默认端口为 `5173`，后端已放开本地 CORS
- 若要运行 Postgres / GROBID，需先启动本机 Docker daemon，再执行 `docker-compose up --build -d`

## Docker 全栈部署

1. 复制配置：`cp .env.example .env`
2. 至少设置 `AUTH_SECRET`，如需 LLM 检索/写作能力再设置 `OPENAI_API_KEY` 或 `LITELLM_API_KEY`
3. 启动全栈：`docker compose -f docker-compose.deploy.yml up --build -d`
4. 访问前端：`http://localhost:8080`
5. 访问后端健康检查：`http://localhost:8000/health`

这个部署栈会启动：
- `postgres`
- `grobid`
- `backend`
- `frontend`（Nginx 反向代理静态站点、API 和 WebSocket）

## 文档

- 部署说明：[docs/deployment.md](docs/deployment.md)
- 用户教程：[docs/user-guide.md](docs/user-guide.md)
- 架构说明：[docs/architecture.md](docs/architecture.md)
- API 概览：[docs/api-reference.md](docs/api-reference.md)
- Auto-research 执行平面：[docs/autoresearch-execution-plane.md](docs/autoresearch-execution-plane.md)
