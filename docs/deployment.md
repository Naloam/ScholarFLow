# Deployment Guide

## 目标

本项目在 Phase 7 提供两种部署方式：

- 本地单机开发部署
- 基于 Docker Compose 的全栈部署

当前仓库内优先支持单机 / 单 VM SaaS 形态。更高阶的多实例扩容可在此基础上继续演进。

## 一、环境变量

从根目录复制：

```bash
cp .env.example .env
```

至少建议设置：

```env
AUTH_SECRET=replace-with-a-long-random-secret
AUTH_REQUIRED=true
OPENAI_API_KEY=...
```

常用变量说明：

- `DATABASE_URL`: 后端数据库连接串
- `GROBID_URL`: GROBID 服务地址
- `AUTH_SECRET`: 用户 session token 签名密钥
- `AUTH_REQUIRED`: 是否强制登录
- `API_TOKEN`: 服务级 bearer token，可选
- `OPENAI_API_KEY` / `LITELLM_API_KEY`: LLM 能力入口
- `CORS_ORIGINS`: 跨域白名单
- `DATA_DIR`: 导出文件、项目数据目录

## 二、本地开发部署

### 1. 启动依赖

```bash
docker-compose up -d postgres grobid
```

### 2. 执行迁移

```bash
cd backend
../.venv/bin/alembic -c alembic.ini upgrade head
```

### 3. 启动后端

```bash
cd backend
PYTHONPATH=. ../.venv/bin/uvicorn main:app --reload
```

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问地址：

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8000`

## 三、Docker 全栈部署

### 1. 启动

```bash
docker compose -f docker-compose.deploy.yml up --build -d
```

### 2. 默认端口

- 前端：`http://localhost:8080`
- 后端健康检查：`http://localhost:8000/health`
- Postgres：`localhost:5432`
- GROBID：`localhost:8070`

### 3. 容器职责

- `frontend`
  - 构建 React 静态资源
  - 用 Nginx 对外提供页面
  - 反向代理 API 和 WebSocket
- `backend`
  - 启动前自动执行 Alembic migration
  - 提供 REST API 与项目进度 WebSocket
- `postgres`
  - 持久化项目、草稿、论文、反馈等数据
- `grobid`
  - 学术 PDF 结构化解析

## 四、云端 SaaS 推荐形态

当前最适合的仓库内方案是单 VM 部署：

- 一台云主机
- Docker Engine + Docker Compose
- 80/443 对外暴露前端
- 8000 仅内网或安全组限流开放
- Postgres volume 持久化
- ScholarFlow 数据目录独立 volume 持久化

建议生产配置：

- 使用 HTTPS 终止层，例如云负载均衡或上层反向代理
- 通过外部托管 Postgres 替代本地容器 Postgres
- 将 `.env` 中的密钥改为 Secret Manager 或 CI/CD 注入
- 对 `AUTH_REQUIRED` 保持开启
- 为 `AUTH_SECRET` 使用高强度随机值
- 对 `RATE_LIMIT_REQUESTS_PER_MINUTE` 设置非零值

## 五、发布检查单

- `alembic upgrade head` 可成功执行
- `backend/tests` 全部通过
- `frontend npm run build` 通过
- `AUTH_SECRET` 已配置
- LLM API key 已配置
- `frontend` 能访问 `/health`、`/api/*`、`/ws/*`
- 导出目录和数据库 volume 已持久化

## 六、回滚与故障排查

### 查看日志

```bash
docker compose -f docker-compose.deploy.yml logs -f backend
docker compose -f docker-compose.deploy.yml logs -f frontend
```

### 重建服务

```bash
docker compose -f docker-compose.deploy.yml up --build -d backend frontend
```

### 常见问题

- 前端空白页：检查 `frontend` 容器构建是否成功
- API 401：检查 `AUTH_REQUIRED`、`AUTH_SECRET`、登录流程
- GROBID 不可用：检查 `GROBID_URL` 是否指向 `http://grobid:8070`
- 迁移失败：检查 `DATABASE_URL` 和数据库连通性
