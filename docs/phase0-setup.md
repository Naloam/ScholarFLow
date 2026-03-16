# Phase 0 Setup Checklist

- 推荐环境：Python 3.11、Node 18+、Docker
- 当前仓库统一使用根目录 `.venv`；`backend/.venv` 不作为默认运行环境
- 复制 `.env.example` 到 `.env`，默认数据库账号需与 `docker-compose.yml` 保持一致
- 启动依赖服务：`docker-compose up -d postgres grobid`
- 运行迁移：`cd backend && ../.venv/bin/alembic -c alembic.ini upgrade head`
- 启动后端：`cd backend && PYTHONPATH=. ../.venv/bin/uvicorn main:app --reload`
- API Key 申请：见 `docs/api-keys.md`
- 低代码平台准备：Dify/Coze 账号 + workflow 草案
- 如使用 Python 3.13，可先用内置向量检索回退；完整 FAISS 能力建议使用 Python 3.11 + `backend[vectors]`
