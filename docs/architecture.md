# Architecture

## 当前运行架构

ScholarFlow 当前仓库采用前后端分离架构：

- `frontend/`: React + Vite + Zustand + TipTap
- `backend/`: FastAPI + SQLAlchemy + Alembic
- `postgres`: 关系型数据存储
- `grobid`: PDF 学术解析

## 核心运行链路

1. 学生创建项目
2. WritingAgent 生成草稿
3. EvidenceAgent 生成 claim-evidence 关联
4. ReviewAgent 输出 7 维评分和改进建议
5. Analysis summary 汇总证据覆盖率、相似度筛查和评分
6. Mentor mode 允许导师只读进入项目并提交反馈

## 部署拓扑

### 本地开发

- 前端：Vite dev server `5173`
- 后端：Uvicorn `8000`
- 依赖：Postgres `5432`、GROBID `8070`

### Docker 全栈部署

- `frontend` 容器使用 Nginx 承载静态资源
- Nginx 反向代理：
  - `/api/*` -> `backend:8000`
  - `/ws/*` -> `backend:8000`
  - `/health` -> `backend:8000/health`
- `backend` 使用 Alembic 自动迁移数据库后启动 Uvicorn
- `postgres` 和 `backend_data` 使用 volume 持久化

## 目录要点

- `backend/api/`: FastAPI 路由
- `backend/services/`: 业务逻辑与仓储层
- `backend/migrations/`: Alembic 迁移
- `frontend/src/components/`: 工作区 UI
- `infra/docker/`: 容器镜像定义
- `infra/nginx/`: 反向代理配置

详细功能规划仍以 `PROJECT_PLAN.md` 为准。
