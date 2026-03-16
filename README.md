# ScholarFlow

ScholarFlow 是面向大学生的全流程学术论文写作 Agent 系统。

本仓库结构与开发规范以 `PROJECT_PLAN.md` 为唯一权威来源。

## 当前开发入口

- 后端：`cd backend && PYTHONPATH=. ../.venv/bin/uvicorn main:app --reload`
- 前端：`cd frontend && npm install && npm run dev`
- 迁移：`cd backend && ../.venv/bin/alembic -c alembic.ini upgrade head`

## 环境说明

- 推荐 Python 3.11；当前仓库在 Python 3.13 下可运行，但向量检索默认走 JSON fallback，完整 FAISS 能力建议使用 `backend[vectors]`
- 默认数据库连接与 `docker-compose.yml` 一致：`scholarflow:scholarflow@localhost:5432/scholarflow`
- 前端开发服务器默认端口为 `5173`，后端已放开本地 CORS
- 若要运行 Postgres / GROBID，需先启动本机 Docker daemon，再执行 `docker-compose up --build -d`
